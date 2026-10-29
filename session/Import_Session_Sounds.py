"""
Import_Session_Sounds.py
========================

"6 Session Sounds" - reads every sound clip out of an SFM session .dmx and
drops it into Blender's Video Sequencer as a trimmed sound strip, placed at
the correct time.

No settings popup: pick the session .dmx and it does the rest.

WHICH CLOCK  ** THE WHOLE POINT OF THIS MODULE **
-------------------------------------------------
A sound clip's `timeFrame.start` is in MOVIE seconds. The animation this
add-on imports is NOT: `Session_Reader.extract_set` copies each channels
clip's RAW key times and writes `tf.start = 0`, so bone animation lands
wherever that clip's own origin happens to be - five seconds of pre-roll
before the shot, in every session measured.

Measured on a real test session: camera2's first key is raw frame 120
and shot1 begins at movie frame 48. Placing sounds in movie time therefore
put every one of them SEVENTY-TWO FRAMES EARLY against shot1's animation,
and would have put them ONE HUNDRED AND TWENTY FRAMES LATE against
ShotWithChangedName's - opposite corrections, which is exactly why the
Global Offset field could never fix it. One slider, two shots.

`Session_Reader.shot_time_base()` owns that conversion now; this module
asks it and does no time arithmetic of its own beyond rounding.

1.17.0: THE ANIMATION MOVED TO MOVIE TIME (Session_Reader, WHERE A SHOT
LANDS), so `to_raw + place_shift` is the identity there and a sound's movie
second IS its frame. The RAW timing switch brings back the extract clock.

AND THE GRID IS SFM'S, NOT BLENDER'S
------------------------------------
This used to transpose onto the scene's frame rate to keep WALL-CLOCK timing
when the two disagreed. That is a defensible thing to want and it is the
wrong thing here, because the animation does not do it:
`Import_DMX_Animation` reads `animation["frameRate"]` out of the file and
lays keys at `(t + start) * that`. So at 24 fps session / 30 fps scene the
old code moved the sound and left the picture, which is the one outcome
nobody wants. Sounds go on SFM's grid, with the rig. FPS_Safety already
exists to say when the scene rate does not match.

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
from ..core import paths as _paths
from ..core import Progress

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



# ──────────────────────────────────────────────────────────────────────────────
#  FPS
# ──────────────────────────────────────────────────────────────────────────────

def _blender_fps(scene):
    base = scene.render.fps_base or 1.0
    return scene.render.fps / base


def read_session_fps(dm, default=24.0):
    """Frame rate the session was authored at. Returns (fps, source_str).

    Kept because `Session_Reader.session_fps` answers only the first half and
    the panel prints the second - which of the two places the number came
    from. `movieSettings.OverridingFrameRate` beats `renderSettings.frameRate`
    and only when `IsOverridingFrameRate` says so.
    """
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


def _to_frame(seconds, fps):
    """Seconds on SFM's grid -> a whole frame number.

    ONE rounding, at the end. The old version snapped to the SFM grid, divided
    back into seconds and multiplied by a DIFFERENT rate, which is two
    roundings and a rate change to buy nothing - the grid we land on is the
    same grid the seconds were authored on.
    """
    return int(round(float(seconds) * float(fps)))


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
    """Every `sound/` folder SFM could be sourcing a wave from, usermod first.

    `SIBLING_MOUNTS` used to be ("tf", "hl2", "platform") - three names, chosen
    because they are the three a default install has. A real install has more,
    and Workshop content is the case people actually hit: it lands in
    `game/workshop`, which was not on that list, so a Workshop sound reported
    as "not found under usermod" when it was sitting right there.

    core.paths.mod_dirs reads the folder instead of carrying a list of names,
    and it is the same scan the model resolver and the particle finder use -
    which is the point. Three modules each had their own hardcoded subset and
    no two of them agreed.
    """
    roots = []
    #  The configured sound folder leads, for the same reason particles do:
    #  a shared wav library does not have to live inside an SFM install.
    try:
        from ..core import config as _config
        from . import Import_Session as _IS
        for p in _config.folders("sound", _IS.usermod_bases(),
                                 _IS._DEFAULT_SFM_USERMOD):
            s = str(p)
            if s not in roots:
                roots.append(s)
    except Exception:
        pass
    if not (usermod and os.path.isdir(usermod)):
        return roots
    #  Every configured install's mounts, not only the one handed in. A wave
    #  referenced by a session can live in whichever SFM the mod was installed
    #  into, and the session file does not say which.
    mounts = []
    try:
        from . import Import_Session
        for base in Import_Session.usermod_bases():
            for m in _paths.mod_dirs(base):
                if m not in mounts:
                    mounts.append(m)
    except Exception:
        pass
    for m in _paths.mod_dirs(usermod):
        if m not in mounts:
            mounts.append(m)
    for mount in mounts:
        s = os.path.join(str(mount), "sound")
        if os.path.isdir(s):
            roots.append(s)
    #  The old fixed list ran even when a mount had no sound/ - keep the
    #  named ones as a backstop in case one lives outside game/ entirely.
    game_dir = os.path.dirname(usermod)
    for sib in SIBLING_MOUNTS:
        s2 = os.path.join(game_dir, sib, "sound")
        if os.path.isdir(s2) and s2 not in roots:
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
                             global_offset_seconds=0.0,
                             shot_index=None, shot_name=None,
                             place_out_of_shot=True):
    """
    Parse *dmx_path* and place its sound clips into *scene*'s Sequencer,
    on the same clock the animation lands on. Returns a result dict.

    shot_index / shot_name    which cut the .blend holds. Every sound is timed
                              through THAT shot's mapping, because that is the
                              shot the rigs were extracted from. Omit them and
                              each sound is timed through the shot it overlaps
                              most, which is the best available answer for a
                              whole-session import.
    place_out_of_shot         a sound that touches no part of the chosen shot
                              is still placed, at that shot's mapping, and
                              flagged. False skips it instead. Placing is the
                              default because a strip in the wrong place can be
                              seen and dragged; a strip that was never created
                              looks like a failed import.
    global_offset_seconds     a nudge on top, for an animation that does not
                              start where you want it. It is now what its name
                              says - a preference - rather than the only tool
                              available for a job it could not do.
    """
    from . import Session_Reader as SR

    #  Through Session_Reader, not a private loader: it survives a non-UTF-8
    #  session via dmxconvert, and it hands back the shot list this needs.
    info = SR.read_session(dmx_path)
    dm = info["model"]
    shot_list = info["shots"]

    _sfps, fps_src = read_session_fps(dm)
    sfm_fps = float(info["fps"] or _sfps or 24.0)
    bl_fps = _blender_fps(scene)

    #  THE CHOSEN SHOT, IF THERE IS ONE. Resolved the same way steps 3-5
    #  resolve it, so "which cut am I working on" has one answer in the file.
    chosen = None
    shot_note = ""
    if shot_index is not None and int(shot_index) >= 0:
        try:
            from . import Session_Paths
            chosen, shot_note = Session_Paths.resolve_shot(
                shot_list, index=int(shot_index), name=shot_name or "")
        except Exception:
            chosen = None
    if chosen is None and len(shot_list) == 1:
        #  One cut is not a choice. Using it silently keeps a one-shot session
        #  behaving identically whether or not anybody touched the picker.
        chosen = shot_list[0]

    #  Cache one time base per shot - it is four numbers and a closure, but it
    #  walks every set in the shot to find them, and a 30-clip session would
    #  otherwise do that 30 times.
    _bases = {}

    def base_for(shot):
        key = id(shot)
        if key not in _bases:
            _bases[key] = SR.shot_time_base(dm, shot)
        return _bases[key]

    #  Global offset: seconds -> whole frames on SFM's grid, like everything
    #  else here. It used to convert at the SCENE rate while the times it was
    #  added to were converted at another, so the nudge itself drifted.
    global_offset_frames = _to_frame(global_offset_seconds, sfm_fps)

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
    rescaled = []
    disagreed = set()
    max_end = scene.frame_end

    sound_clips = [e for e in dm.elements if e.type == "DmeSoundClip"]

    _active = dm.root.get("activeClip") if hasattr(dm, "root") else None
    _active_ids = set()
    if _active is not None:
        try:
            for _tg in (_active["trackGroups"]
                        if "trackGroups" in _active.keys() else []) or []:
                for _tr in (_tg["tracks"] if "tracks" in _tg.keys() else []):
                    for _k in (_tr["children"]
                               if "children" in _tr.keys() else []):
                        if getattr(_k, "type", "") == "DmeSoundClip":
                            _active_ids.add(id(_k))
        except Exception:                                     # noqa: BLE001
            _active_ids = set()

    def _dedupe_key(c):
        _tf = c["timeFrame"] if "timeFrame" in c.keys() else None
        _st = _seconds(_tf["start"]) if _tf else 0.0
        _sn = c["sound"] if "sound" in c.keys() else None
        _rel = (_sn["soundname"]
                if (_sn and "soundname" in _sn.keys()) else None)
        if not _rel:
            return None
        #  Rounded to the frame: two clips a microsecond apart are the same
        #  clip saved twice, not a deliberate flam.
        return (str(_rel).lower().replace("/", "\\"),
                round(_st * sfm_fps))

    def _duration(c):
        _tf = c["timeFrame"] if "timeFrame" in c.keys() else None
        return _seconds(_tf["duration"]) if _tf else 0.0

    _groups = {}
    for _c in sound_clips:
        _k = _dedupe_key(_c)
        if _k is None:
            continue
        _groups.setdefault(_k, []).append(_c)

    duplicates = []
    _drop = set()
    for _k, _members in _groups.items():
        if len(_members) < 2:
            continue
        _members.sort(key=lambda c: (id(c) not in _active_ids, -_duration(c)))
        _keep = _members[0]
        for _loser in _members[1:]:
            _drop.add(id(_loser))
        duplicates.append({
            "sound": _k[0],
            "start_frame": _k[1],
            "copies": len(_members),
            "kept_duration": round(_duration(_keep), 2),
            "kept_from_active": id(_keep) in _active_ids,
            "dropped_durations": [round(_duration(m), 2)
                                  for m in _members[1:]],
        })
    if _drop:
        sound_clips = [c for c in sound_clips if id(c) not in _drop]
        print("[SND]  %d duplicate sound clip(s) collapsed - %d remain"
              % (len(_drop), len(sound_clips)))
        for _d in duplicates:
            print("[SND]    %s @f%d  x%d -> kept %.2fs%s"
                  % (_d["sound"], _d["start_frame"], _d["copies"],
                     _d["kept_duration"],
                     "  (active clip)" if _d["kept_from_active"] else ""))

    for _n_clip, sc in enumerate(sound_clips, 1):
        Progress.update(_n_clip, len(sound_clips), getattr(sc, "name", "") or "sound")
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

        #  ── MOVIE TIME -> THE CLOCK THE ANIMATION IS ON ──────────────────
        #  `start_s` is movie seconds. The rigs are not. See the module
        #  docstring; the conversion belongs to Session_Reader.
        shot = chosen
        overlaps = []
        if shot is None:
            shot, overlaps = SR.shot_for_span(shot_list, start_s, dur_s)
        else:
            _s, overlaps = SR.shot_for_span(shot_list, start_s, dur_s)

        out_of_shot = False
        if shot is None:
            #  Touches no cut at all - sound sitting in the film's dead air.
            #  There is no animation to be in sync with, so movie time is the
            #  only meaningful answer and it is reported as such.
            raw_s = start_s
            out_of_shot = True
        else:
            tb = base_for(shot)
            out_of_shot = not (tb["movie_lo"] <= start_s < tb["movie_hi"]
                               or any(o is shot for o in overlaps))
            if out_of_shot and not place_out_of_shot:
                missing.append({"name": rel,
                                "reason": f"not in {shot.get('name')}"})
                continue
            #  1.17.0: + the shot's placement - movie time by default, so
            #  this is start_s itself when both scales are 1.
            raw_s = tb["to_raw"](start_s) + SR.place_shift(dm, shot, base=tb)
            if not tb["agreed"]:
                disagreed.add(shot.get("name") or "?")

        target_frame = _to_frame(raw_s, sfm_fps) + global_offset_frames

        #  offset and duration are DURATIONS, not instants - the shot mapping
        #  is affine with scale 1 in every session measured, so they convert
        #  by rate alone. A shot that really did carry a time scale would need
        #  them scaled too; `straddles` and the report say when that is in
        #  play rather than pretending it cannot be.
        trim_in = _to_frame(offset_s, sfm_fps)
        window = _to_frame(dur_s, sfm_fps)

        #  SFM'S OWN TIME SCALE ON THE CLIP. `timeFrame.scale` says the media
        #  plays at that rate: 0.5 stretches the wav across twice the window.
        #  BLENDER 5.2 CANNOT DO IT - `SoundStrip` has no `pitch` and no
        #  `speed_factor`, only `pitch_correction`, so there is no way to
        #  retime a sound strip from Python. Measured, not assumed.
        #  So the strip gets the RIGHT LENGTH on the timeline and the wrong
        #  rate inside it, and the report names the clip. Silently placing a
        #  natural-rate 20-frame strip where SFM plays 97 frames is the one
        #  outcome that cannot be noticed.
        clip_scale = 1.0
        if tf is not None and "scale" in tf.keys():
            try:
                clip_scale = float(tf["scale"]) or 1.0
            except Exception:
                clip_scale = 1.0
        if abs(clip_scale - 1.0) > EPS:
            rescaled.append({"name": rel, "scale": clip_scale,
                             "window": window})

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
        #  ONLY A SOUND THAT BELONGS TO THIS SHOT MAY STRETCH THE SCENE.
        #  A clip from another cut is placed and flagged (see above), and it
        #  can land hundreds of frames past the shot - dragging frame_end out
        #  there makes the timeline mostly empty and hides the shot the user
        #  asked for. Measured on shot1: the conga from the next cut sits at
        #  f342-379 against a shot ending at 312.
        if not out_of_shot:
            max_end = max(max_end, s1)
        placed.append({
            "file": os.path.basename(abs_path),
            "track": track,
            "channel": strip.channel,
            "start_frame": s0,
            "end_frame": s1,
            "movie_second": round(start_s, 4),
            "movie_frame": _to_frame(start_s, sfm_fps),
            "shot": (shot.get("name") if shot is not None else None),
            "out_of_shot": out_of_shot,
            #  EVERY OTHER CUT IT TOUCHES - excluding the one it was timed
            #  through. Slicing [1:] was right only while the chosen shot
            #  happened to sort first, which it does not when a shot is
            #  picked by hand: a sound then reported that it also straddled
            #  the very shot it had just been placed in.
            "straddles": [o.get("name") for o in overlaps if o is not shot],
            "scale": clip_scale,
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
        "rescaled": rescaled,
        "clip_disagreement": sorted(disagreed),
        "shot": (chosen.get("name") if chosen is not None else None),
        "shot_note": shot_note,
        "shot_offset_frames": (
            _to_frame(base_for(chosen)["offset_seconds"]
                      + SR.place_shift(dm, chosen, base=base_for(chosen)),
                      sfm_fps)
            if chosen is not None else None),
        "shots": len(shot_list),
        "total": len(sound_clips),
        "duplicates": duplicates,
    }


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_ImportSessionSounds(Operator):
    """NO INPUT on the Main tab - runs on the connected session. Sound lives
        inside the session; there is no separate sound file.

        Lay the session's game sounds onto the Video Sequencer at their shot times

Reads every DmeSoundClip in the session and places each sound as a
trimmed strip at the time SFM plays it.

Clip times are authored at the SESSION's frame rate and re-timed to the
scene's, so wall-clock timing survives a frame-rate difference. The clip
offset drives the strip in-point and its duration the visible window, so
a sound trimmed in SFM stays trimmed.

Turns on A/V sync and audio scrubbing so the sounds are audible while
scrubbing. Global Offset shifts everything if the animation does not
start on frame 0.

Look in the Video Sequencer afterwards - nothing appears in the 3D
viewport
        """
    bl_idname  = "ht.import_session_sounds"
    bl_label   = "Session Sounds"
    #  NO "REGISTER" - see the note in Report_UI/the constitution.
    #  REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    #  touching any field in it RE-RUNS this operator. Re-running an
    #  import re-reads the DMX and rebuilds every f-curve; nudging Scale
    #  there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    #  with the value you wanted is the safe way to change your mind.
    bl_options = {"UNDO"}

    filepath:    StringProperty(subtype="FILE_PATH")  # type: ignore
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    reads_session = True

    #  PICKED, NOT CONNECTED. Set by the Tools drawer; empty everywhere else.
    #  This one already had a file browser, so all the flag has to do is stop
    #  it short-circuiting to the connected session.
    pick_session: BoolProperty(default=False, options={"HIDDEN"})  # type: ignore

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

    @staticmethod
    def _connected_session(context):
        """The session already connected in the panel, if there is one."""
        try:
            from . import Session_Paths
            return Session_Paths.session_file(context.scene)
        except Exception:
            return None

    def invoke(self, context, event):
        # Every other numbered step runs off the connected session. This one
        # alone opened a file browser, which broke the rhythm of working
        # through Import Session Elements in order - and with no filepath set
        # it failed with "Pick a session .dmx file" against a session that was
        # already connected. Use that when it is there; ask only when it isn't.
        if not self.filepath and not self.pick_session:
            session = self._connected_session(context)
            if session is not None:
                self.filepath = str(session)
                return self.execute(context)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        # Shown in the file browser's right-hand panel, not a blocking popup.
        col = self.layout.column()
        col.prop(self, "enable_audio_scrub")
        col.prop(self, "global_offset_seconds")

    @Progress.jobbed_execute("SFM Session Importer - 5  Import Sounds")
    def execute(self, context):
        # Same fallback on the execute side, so a scripted call and the
        # one-click both work without being handed a path.
        if not self.filepath and not self.pick_session:
            session = self._connected_session(context)
            if session is not None:
                self.filepath = str(session)

        path = Path(self.filepath) if self.filepath else None
        if path is None or path.suffix.lower() != ".dmx" or not path.is_file():
            self.report({"ERROR"},
                        "No session .dmx - connect one in the panel or pick "
                        "a file.")
            return {"CANCELLED"}

        #  THE SAME SHOT STEPS 3-5 USED. Sound has to be timed through the cut
        #  the rigs came out of or it is in the wrong place by construction -
        #  72 frames one way for one shot, 120 the other way for the next.
        #  Read here rather than inside the importer so a scripted call can
        #  still say "no shot, work it out per sound".
        s_idx, s_name = -1, ""
        try:
            from . import Session_Paths
            s_idx, s_name = Session_Paths.shot_choice(context.scene)
        except Exception:
            pass

        try:
            result = run_session_sound_import(
                path, context.scene,
                enable_audio_scrub=self.enable_audio_scrub,
                global_offset_seconds=self.global_offset_seconds,
                shot_index=s_idx, shot_name=s_name)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        placed = result["placed"]
        missing = result["missing"]

        lines = [
            f"Session   : {result['dmx']}",
            f"FPS       : SFM {result['sfm_fps']:g} ({result['fps_source']})"
            + ("" if abs(result['sfm_fps'] - result['blender_fps']) < 1e-6
               else f"   SCENE IS {result['blender_fps']:g} - see Frame Rate"),
            f"Placed    : {len(placed)} / {result['total']} sound(s)",
        ]
        #  THE LINE THAT MAKES THE TIMING FALSIFIABLE. A reader who thinks the
        #  sound is out can compare this number against the shot's own frame
        #  range without opening the DMX.
        if result.get("shot"):
            off = result.get("shot_offset_frames")
            lines.append(
                f"Shot      : {result['shot']}"
                + (f"   movie -> timeline {off:+d} frames" if off is not None
                   else ""))
        elif result.get("shots", 1) > 1:
            lines.append(f"Shot      : none chosen - each sound timed through "
                         f"the cut it overlaps ({result['shots']} shots)")
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
            flags = "  [MUTED]" if p["muted"] else ""
            if p.get("out_of_shot"):
                flags += "  [OUTSIDE THIS SHOT]"
            if p.get("straddles"):
                flags += "  [also in " + ", ".join(p["straddles"]) + "]"
            lines.append(f"ch{p['channel']}  f{p['start_frame']}-{p['end_frame']}"
                         f"  (movie f{p['movie_frame']})  {p['file']}{flags}")
        if result.get("rescaled"):
            lines.append("─" * 46)
            lines.append("Time-scaled in SFM - Blender cannot retime a sound")
            lines.append("strip, so these have the right LENGTH and the")
            lines.append("wrong RATE:")
            for r in result["rescaled"]:
                lines.append(f"  x{r['scale']:g} over {r['window']} frames"
                             f"  {r['name']}")
        if result.get("clip_disagreement"):
            lines.append("─" * 46)
            lines.append("Shots whose sets disagree about their own time base "
                         "(the most common one was used): "
                         + ", ".join(result["clip_disagreement"]))
        if missing:
            lines.append("─" * 46)
            lines.append(f"Not placed ({len(missing)}):")
            for m in missing[:10]:
                lines.append(f"  {m['name']}  — {m['reason']}")

        _lines = list(lines)
        for ln in _lines:
            print(f"[SESSION_SOUNDS]  {ln}")

        # GUARD THE POPUP. Every other module in this addon checks
        # bpy.app.background before drawing one; this was the only one that
        # did not, and in `blender -b` there is no window to draw into -
        # Blender walks a dead icon and dies with EXCEPTION_ACCESS_VIOLATION.
        # It went unnoticed while sounds were a button a person pressed by
        # hand; wiring them into Import Whole Session made a headless run of
        # the whole pipeline crash at the second-to-last step.
        from ..core import Report_UI
        Report_UI.report(
            context, "import_sounds",
            f"Session Sounds - {len(placed)}/{result['total']}", _lines,
            level=('WARNING' if missing else 'INFO'), operator=self,
            prefix="SESSION_SOUNDS",
            summary=f"Session Sounds - {len(placed)}/{result['total']} placed"
                    + (f", {len(missing)} file(s) not found" if missing
                       else "  (see the Video Sequencer)"))
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
        text="5  Import DMX Session Sounds",
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
