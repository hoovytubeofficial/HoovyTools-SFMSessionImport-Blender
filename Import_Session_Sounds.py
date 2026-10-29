"""
Import_Session_Sounds.py
========================

"6 Session Sounds" - reads every sound clip out of an SFM session .dmx and
drops it into Blender's Video Sequencer as a trimmed sound strip, placed at
the correct time.

No settings popup: pick the session .dmx and it does the rest.

FPS TRANSPOSE
-------------
SFM stores clip times in seconds, but those seconds were authored on the
session's frame grid (e.g. 24 fps). Blender's scene has its own fps (e.g. 30).
We keep wall-clock timing identical:

    sfm_frame     = round(seconds * sfm_fps)      # snap to SFM's grid
    clean_seconds = sfm_frame / sfm_fps           # kill stored float noise
    blender_frame = scene.frame_start + round(clean_seconds * blender_fps)

So a sound at SFM second 1.0 (24 fps) lands on Blender frame 30 in a 30 fps
scene. Trim in-point and duration transpose the same way.

PATHS
-----
The DMX stores 'foley\\gear\\x.wav'. We resolve it to a real file under the
usermod path from HoovyTools preferences, searching usermod\\sound\\ (and the
tf / hl2 sibling mounts) case-insensitively.
"""

import bpy
import os
from pathlib import Path
from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy.types import Operator

# ──────────────────────────────────────────────────────────────────────────────
#  Icon bridge (wired by __init__.register)
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None


def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


SIBLING_MOUNTS = ("tf", "hl2", "platform")
EPS = 1e-4


# ──────────────────────────────────────────────────────────────────────────────
#  DMX loading (uses the bundled SST datamodel, same as the rest of the addon)
# ──────────────────────────────────────────────────────────────────────────────

def _load_datamodel():
    """Return the datamodel module HoovyTools ships in SST, or raise."""
    try:
        from .SST import datamodel  # bundled with the addon
        return datamodel
    except Exception:
        pass
    try:
        import datamodel  # if it happens to be importable globally
        return datamodel
    except Exception as exc:
        raise RuntimeError(
            "Could not import a DMX 'datamodel' library. Session sound import "
            "needs it (normally bundled in HoovyTools/SST)."
        ) from exc


def _fast_load(datamodel, path):
    """
    Load a DMX with a temporary O(1) id-collision check.

    The stock datamodel validates every new element by scanning the whole
    element list (`self.elements.index(elem)`), which is O(n^2) in the number
    of elements and compares UUIDs on every step. On a real session (~17k
    elements) that is ~140 million comparisons - about 35-40 seconds, far
    slower than the animation import even though we only want four sound
    clips. Replacing the check with a dict keyed by id makes it O(1) per
    element (~0.3 s total, a ~100x win) with identical results: DMX ids are
    unique by spec, and placeholder collisions are still detected.

    The swap is scoped to this one call and always restored, so the shared
    SST library other tools use is never mutated on disk or left patched.
    """
    DataModel = datamodel.DataModel
    original = DataModel.validate_element

    def fast_validate(self, elem):
        if elem._is_placeholder:
            return
        idx = getattr(self, "_ht_id_index", None)
        if idx is None:
            idx = self._ht_id_index = {}
        prior = idx.get(elem.id)
        if prior is not None and not prior._is_placeholder:
            raise datamodel.IDCollisionError(
                "ID collision on {}".format(elem.id))
        idx[elem.id] = elem

    DataModel.validate_element = fast_validate
    try:
        return datamodel.load(str(path))
    finally:
        DataModel.validate_element = original


# ──────────────────────────────────────────────────────────────────────────────
#  FPS
# ──────────────────────────────────────────────────────────────────────────────

def _blender_fps(scene):
    base = scene.render.fps_base or 1.0
    return scene.render.fps / base


def read_session_fps(dm, default=24.0):
    """Frame rate the session was authored at. Returns (fps, source_str)."""
    try:
        settings = dm.root["settings"]
    except Exception:
        return default, "default (no settings)"

    ms = settings["movieSettings"] if "movieSettings" in settings.keys() else None
    if ms is not None:
        try:
            if ms["IsOverridingFrameRate"] and float(ms["OverridingFrameRate"]) > 0:
                return float(ms["OverridingFrameRate"]), "movieSettings"
        except Exception:
            pass

    rs = settings["renderSettings"] if "renderSettings" in settings.keys() else None
    if rs is not None and "frameRate" in rs.keys():
        try:
            fr = float(rs["frameRate"])
            if fr > 0:
                return fr, "renderSettings"
        except Exception:
            pass

    return default, "default"


def _snap_seconds(seconds, sfm_fps):
    """Snap a raw DMX second value to the nearest SFM frame boundary."""
    if sfm_fps <= 0:
        return seconds
    return round(seconds * sfm_fps) / sfm_fps


def _to_blender_frame(seconds, sfm_fps, blender_fps, frame_start):
    clean = _snap_seconds(seconds, sfm_fps)
    return frame_start + int(round(clean * blender_fps))


def _to_blender_frame_delta(seconds, sfm_fps, blender_fps):
    """A duration/offset in seconds -> whole Blender frames (no frame_start)."""
    clean = _snap_seconds(seconds, sfm_fps)
    return int(round(clean * blender_fps))


# ──────────────────────────────────────────────────────────────────────────────
#  Element graph + path resolution
# ──────────────────────────────────────────────────────────────────────────────

def _seconds(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def _build_parent_map(dm):
    refs = {}
    for el in dm.elements:
        for key in el.keys():
            try:
                val = el[key]
            except Exception:
                continue
            items = val if isinstance(val, list) else [val]
            for x in items:
                if hasattr(x, "type") and hasattr(x, "name"):
                    refs.setdefault(id(x), []).append((el, key))
    return refs


def _track_name(sound_clip, refs):
    for parent, _key in refs.get(id(sound_clip), []):
        if parent.type == "DmeTrack":
            return parent.name
    return None


def _usermod_path():
    """usermod folder from HoovyTools preferences, or None."""
    try:
        from . import Import_Session
        base = Import_Session.get_gameinfo_base()
        return str(base) if base else None
    except Exception:
        return None


def _search_roots(usermod):
    roots = []
    if usermod and os.path.isdir(usermod):
        s = os.path.join(usermod, "sound")
        if os.path.isdir(s):
            roots.append(s)
        game_dir = os.path.dirname(usermod)
        for sib in SIBLING_MOUNTS:
            s2 = os.path.join(game_dir, sib, "sound")
            if os.path.isdir(s2):
                roots.append(s2)
    return roots


def _resolve_ci(root, rel):
    rel = rel.replace("\\", "/").lstrip("/")
    if rel.lower().startswith("sound/"):
        rel = rel[6:]
    cur = root
    for part in rel.split("/"):
        if not part:
            continue
        if not os.path.isdir(cur):
            return None
        try:
            entries = os.listdir(cur)
        except Exception:
            return None
        match = None
        for e in entries:
            if e == part:
                match = e
                break
        if match is None:
            low = part.lower()
            for e in entries:
                if e.lower() == low:
                    match = e
                    break
        if match is None:
            return None
        cur = os.path.join(cur, match)
    return cur if os.path.isfile(cur) else None


def _resolve(rel, roots):
    for root in roots:
        hit = _resolve_ci(root, rel)
        if hit:
            return os.path.abspath(hit)
    return None


# ──────────────────────────────────────────────────────────────────────────────
#  Sequencer helpers (Blender 5.x `strips`, older `sequences`)
# ──────────────────────────────────────────────────────────────────────────────

def _strip_collection(se):
    strips = getattr(se, "strips", None)
    if strips is not None and hasattr(strips, "new_sound"):
        return strips
    sequences = getattr(se, "sequences", None)
    if sequences is not None and hasattr(sequences, "new_sound"):
        return sequences
    raise RuntimeError("Could not access the Sequencer strip collection.")


def _all_strips(se):
    for attr in ("strips_all", "sequences_all"):
        coll = getattr(se, attr, None)
        if coll is not None:
            return list(coll)
    return list(_strip_collection(se))


def _new_sound(coll, name, filepath, channel, frame_start):
    try:
        return coll.new_sound(name, filepath, channel, frame_start)
    except TypeError:
        try:
            return coll.new_sound(name=name, filepath=filepath,
                                  channel=channel, frame_start=frame_start)
        except TypeError:
            return coll.new_sound(name, filepath, channel, frame_start, False)


def _strip_range(strip):
    return int(strip.frame_final_start), int(strip.frame_final_end)


def _overlaps(a0, a1, b0, b1):
    return a0 < b1 and a1 > b0


def _free_channel(se, strip, min_channel=1):
    s0, s1 = _strip_range(strip)
    others = [x for x in _all_strips(se) if x != strip]
    top = max([getattr(x, "channel", 1) for x in others], default=0)
    for ch in range(min_channel, top + 2):
        clash = False
        for o in others:
            if getattr(o, "channel", 1) != ch:
                continue
            o0, o1 = _strip_range(o)
            if _overlaps(s0, s1, o0, o1):
                clash = True
                break
        if not clash:
            return ch
    return top + 1


# ──────────────────────────────────────────────────────────────────────────────
#  Core import
# ──────────────────────────────────────────────────────────────────────────────

def run_session_sound_import(dmx_path, scene,
                             enable_audio_scrub=True,
                             global_offset_seconds=0.0):
    """
    Parse *dmx_path* and place its sound clips into *scene*'s Sequencer.
    Returns a result dict for reporting.

    global_offset_seconds shifts every placed sound later (or earlier, if
    negative) on the Blender timeline. It is given in seconds and converted
    to whole Blender frames once, then added to every clip's start.
    """
    datamodel = _load_datamodel()
    dm = _fast_load(datamodel, dmx_path)

    sfm_fps, fps_src = read_session_fps(dm)
    bl_fps = _blender_fps(scene)
    frame_start = scene.frame_start

    # Global offset: seconds -> whole Blender frames, applied to every clip.
    global_offset_frames = int(round(global_offset_seconds * bl_fps))

    # Targeted track map: only DmeTrack children, not a full-graph parent walk.
    track_of = {}
    for tr in (e for e in dm.elements if e.type == "DmeTrack"):
        if "children" in tr.keys():
            for kid in tr["children"]:
                if hasattr(kid, "type") and kid.type == "DmeSoundClip":
                    track_of[id(kid)] = tr.name

    usermod = _usermod_path()
    roots = _search_roots(usermod)

    se = scene.sequence_editor_create()
    coll = _strip_collection(se)

    placed = []
    missing = []
    max_end = scene.frame_end

    sound_clips = [e for e in dm.elements if e.type == "DmeSoundClip"]

    for sc in sound_clips:
        tf = sc["timeFrame"] if "timeFrame" in sc.keys() else None
        start_s = _seconds(tf["start"]) if tf else 0.0
        dur_s = _seconds(tf["duration"]) if tf else 0.0
        offset_s = _seconds(tf["offset"]) if tf else 0.0

        snd = sc["sound"] if "sound" in sc.keys() else None
        rel = snd["soundname"] if (snd and "soundname" in snd.keys()) else None
        vol = 1.0
        if snd is not None and "volume" in snd.keys():
            try:
                vol = float(snd["volume"])
            except Exception:
                vol = 1.0

        track = track_of.get(id(sc))
        muted = bool(sc["mute"]) if "mute" in sc.keys() else False

        if not rel:
            missing.append({"name": sc.name, "reason": "no sound path"})
            continue

        abs_path = _resolve(rel, roots)
        if not abs_path:
            missing.append({"name": rel, "reason": "not found under usermod"})
            continue

        # Transpose times SFM-seconds -> Blender frames, then apply global offset
        target_frame = _to_blender_frame(start_s, sfm_fps, bl_fps, frame_start)
        target_frame += global_offset_frames
        trim_in = _to_blender_frame_delta(offset_s, sfm_fps, bl_fps)
        window = _to_blender_frame_delta(dur_s, sfm_fps, bl_fps)

        # Place raw strip so that after trim-in, its visible start == target.
        raw_start = target_frame - trim_in
        temp_ch = max([getattr(s, "channel", 1) for s in _all_strips(se)],
                      default=0) + 1

        name = os.path.splitext(os.path.basename(abs_path))[0]
        try:
            strip = _new_sound(coll, name, abs_path, temp_ch, raw_start)
        except Exception as exc:
            missing.append({"name": rel, "reason": f"strip failed: {exc}"})
            continue

        src_frames = int(strip.frame_duration)
        # trim-in from the head; trim the tail so the visible window == duration
        strip.frame_offset_start = max(0, min(trim_in, max(0, src_frames - 1)))
        tail = src_frames - strip.frame_offset_start - window
        strip.frame_offset_end = max(0, tail)

        # correct any 1-frame rounding drift on the visible start
        vis = int(strip.frame_final_start)
        diff = target_frame - vis
        if diff:
            strip.frame_start += diff

        strip.channel = _free_channel(se, strip, min_channel=1)
        try:
            strip.volume = vol
        except Exception:
            pass
        if hasattr(strip, "mute"):
            strip.mute = muted
        if hasattr(strip, "show_waveform"):
            strip.show_waveform = True

        s0, s1 = _strip_range(strip)
        max_end = max(max_end, s1)
        placed.append({
            "file": os.path.basename(abs_path),
            "track": track,
            "channel": strip.channel,
            "start_frame": s0,
            "end_frame": s1,
            "start_second": round(_snap_seconds(start_s, sfm_fps), 4),
            "muted": muted,
        })

    # Extend scene end to cover the audio
    if max_end > scene.frame_end:
        scene.frame_end = int(max_end)

    # Audio playback niceties
    if enable_audio_scrub:
        try:
            scene.sync_mode = "AUDIO_SYNC"
        except Exception:
            pass
        if hasattr(scene, "use_audio_scrub"):
            scene.use_audio_scrub = True

    return {
        "dmx": os.path.basename(str(dmx_path)),
        "sfm_fps": sfm_fps,
        "fps_source": fps_src,
        "blender_fps": bl_fps,
        "global_offset_seconds": global_offset_seconds,
        "global_offset_frames": global_offset_frames,
        "usermod": usermod,
        "roots_found": bool(roots),
        "placed": placed,
        "missing": missing,
        "total": len(sound_clips),
    }


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_ImportSessionSounds(Operator):
    """Import every sound from an SFM session .dmx into the Video Sequencer.

Reads each sound clip's timeline position, in-point trim and length, then \
transposes them from the session's frame rate to the current Blender scene's \
frame rate so timing stays identical in wall-clock seconds (a sound at SFM \
second 1.0 lands on frame 30 in a 30 fps scene). Sound file paths are \
resolved under Your HoovyTools usermod path. No settings dialog - just pick \
the session .dmx. Turns on audio scrubbing and A/V sync so You can hear \
sounds while scrubbing the timeline"""
    bl_idname  = "ht.import_session_sounds"
    bl_label   = "Session Sounds"
    bl_options = {"REGISTER", "UNDO"}

    filepath:    StringProperty(subtype="FILE_PATH")  # type: ignore
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    enable_audio_scrub: BoolProperty(  # type: ignore
        name="Enable Audio Scrubbing",
        description=("Turn on A/V sync and audio scrubbing so You hear sounds "
                     "while dragging the playhead. Recommended for lip-sync "
                     "and timing work"),
        default=True,
    )

    global_offset_seconds: FloatProperty(  # type: ignore
        name="Global Offset (seconds)",
        description=(
            "Shift every placed sound by this many seconds on the Blender "
            "timeline. Given in seconds but applied as whole Blender frames at "
            "the scene fps (e.g. +1.0 s in a 30 fps scene moves every sound 30 "
            "frames later). Use it to line the whole audio track up with an "
            "animation that does not start on frame 0. Positive = later, "
            "negative = earlier. Default 0"
        ),
        default=0.0, soft_min=-60.0, soft_max=60.0,
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        # Shown in the file browser's right-hand panel, not a blocking popup.
        col = self.layout.column()
        col.prop(self, "enable_audio_scrub")
        col.prop(self, "global_offset_seconds")

    def execute(self, context):
        path = Path(self.filepath)
        if path.suffix.lower() != ".dmx" or not path.is_file():
            self.report({"ERROR"}, "Pick a session .dmx file.")
            return {"CANCELLED"}

        try:
            result = run_session_sound_import(
                path, context.scene,
                enable_audio_scrub=self.enable_audio_scrub,
                global_offset_seconds=self.global_offset_seconds)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        placed = result["placed"]
        missing = result["missing"]

        lines = [
            f"Session   : {result['dmx']}",
            f"FPS       : SFM {result['sfm_fps']:g} ({result['fps_source']}) "
            f"-> Blender {result['blender_fps']:g}",
            f"Placed    : {len(placed)} / {result['total']} sound(s)",
        ]
        if result["global_offset_frames"]:
            lines.append(f"Offset    : {result['global_offset_seconds']:+g} s "
                         f"({result['global_offset_frames']:+d} frames)")
        if not result["roots_found"]:
            lines.append("Usermod   : sound/ not found - check the path in Prefs")
        # Where to find the strips - Source-native navigation terms
        lines.append("─" * 46)
        lines.append("Find them in:")
        lines.append("  Video Sequencer  (Sequencer editor,")
        lines.append("  the triangle-and-dot 'Sequence Strip'")
        lines.append("  icon in the editor-type menu)")
        lines.append("  -> Sound Strips on the channels below,")
        lines.append("     one per shot's game sound.")
        lines.append("─" * 46)
        for p in placed:
            mute = "  [MUTED]" if p["muted"] else ""
            lines.append(f"ch{p['channel']}  f{p['start_frame']}-{p['end_frame']}"
                         f"  {p['file']}{mute}")
        if missing:
            lines.append("─" * 46)
            lines.append(f"Not placed ({len(missing)}):")
            for m in missing[:10]:
                lines.append(f"  {m['name']}  — {m['reason']}")

        _lines = list(lines)
        def draw_popup(self, context):
            for ln in _lines:
                self.layout.label(text=ln)
        context.window_manager.popup_menu(
            draw_popup,
            title=f"Session Sounds — {len(placed)}/{result['total']}",
            icon="CHECKMARK" if not missing else "INFO",
        )

        self.report({"INFO"},
                    f"Placed {len(placed)} sound(s). Open the Video Sequencer "
                    f"(Sequencer editor) to see the sound strips.")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU ITEMS
# ──────────────────────────────────────────────────────────────────────────────

def draw_menu_item(layout):
    layout.operator(
        HT_OT_ImportSessionSounds.bl_idname,
        text="Session Sounds",
        **_icon_id("import_session_sounds", "SOUND"),
    )


def draw_session_entry(layout):
    """Entry 6 inside the IMPORT SESSION submenu."""
    layout.operator(
        HT_OT_ImportSessionSounds.bl_idname,
        text="6  Import DMX Session Sounds",
        **_icon_id("import_session_sounds", "SOUND"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (HT_OT_ImportSessionSounds,)


def register(icon_id_fn=None):
    global _ht_icon_id
    _ht_icon_id = icon_id_fn
    for cls in _CLASSES:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
