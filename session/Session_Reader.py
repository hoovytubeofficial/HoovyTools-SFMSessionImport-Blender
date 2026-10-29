"""
Session_Reader.py  -  part of HoovyTools           [roadmap #20, #21]
====================================================================

Read animation straight out of an SFM session, so exporting from SFM first
becomes optional.

THE ANIMATION IS ALREADY IN THE SESSION
=======================================
Probed from real sessions, 2026-08-20. A session holds, per animation set:

    DmeAnimationSet     the set, named as it is in SFM
      .gameModel        DmeGameModel -> modelName, the .mdl path
        .children       the bone DAG tree, DmeDag per bone
        .bones          flat DmeTransform list, one per bone
    DmeChannelsClip     the channels, one clip per set
      .channels         bip_pelvis_p / bip_pelvis_o / flexWeight / camera...
        .log.layers[0]  times (SECONDS) and values

So everything an exported animation DMX carries is present. What differs:

    exported                          session
    --------                          -------
    root.skeleton is a DmeModel       gameModel is a DmeGameModel
    DAG bones named "root"            named "bone 0 (root)"
    clip has frameRate                clip has none
    times relative to timeFrame.start times are absolute seconds

FRAME RATE lives in settings.renderSettings.frameRate, overridden by
settings.movieSettings.OverridingFrameRate when IsOverridingFrameRate is
set. Both were 24.0 on the probed sessions, which matches SFM's timeline.

WHY RE-EMIT INSTEAD OF KEYING DIRECTLY
======================================
Keying bones from these channels means reproducing Blender Source Tools'
bone-space maths exactly - rest-pose-relative, parent-relative quaternions.
That maths already exists and is already trusted, so this module writes an
export-SHAPED DMX per animation set and hands it to the existing importer.

    SESSION -> extract per set -> normal .dmx -> Import_DMX_Animation

The pipeline downstream is unchanged, which means a fix to the standalone
importer still reaches this path. It also means the extracted files are
ordinary DMX: inspectable, diffable against a real SFM export, and usable
by anything else that reads them.

WHAT MAKES THE RE-EMIT FAITHFUL
===============================
Two details matter and both were verified against a real export:

  * `jointList` and `baseStates` are EMPTY in genuine SFM exports too, so
    leaving them empty is correct, not a shortcut. BST rebuilds the
    skeleton from the DAG tree and `upAxis`.
  * DAG nodes must be renamed from "bone 0 (root)" to "root", or the bones
    would not match an armature imported from the same model.

SPEED
=====
This is only practical because Datamodel element lookup was made O(1)
(see SST/datamodel.py:_element_by_id). Loading a 2.3 MB session went from
75 s to 0.4 s. Before that fix, reading a session on demand was not an
option at all.
"""

import bpy
import re
from pathlib import Path

from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, FloatProperty, IntProperty


class CameraNotResolved(Exception):
    """A camera set whose DmeCamera cannot be identified.

    Not a failure: a session can hold camera-shaped sets that no longer
    point at a camera. They are skipped with a reason rather than counted
    as errors, which is what an unresolvable one used to look like.
    """


BONE_NAME = re.compile(r"^bone \d+ \((.+)\)$")

#The game-model root transform - the character's world position and
#orientation. A session names these rootTransform_p / rootTransform_o; an
#SFM export names them unnamed_p / unnamed_o, which is what
#Import_DMX_Animation looks for. Renaming keeps root motion alive.
#
#NOT transform_pos / transform_rot: those are the CAMERA and LIGHT
#transforms. Mapping those by mistake silently dropped every character's
#root motion while appearing to work, bc bone animation was fine.
#rootTransform_scale is deliberately left alone - the importer already
#recognises that name
ROOT_CHANNELS = {"rootTransform_p": "unnamed_p",
                 "rootTransform_o": "unnamed_o"}

# A CAMERA set names its transform channels differently again, and
# Import_DMX_Camera matches channels by NAME SUFFIX (_p, _o, fieldOfView,
# aperture, focalDistance) - so these have to carry the names SFM's own
# exporter would have written
CAMERA_ROOT_CHANNELS = {"transform_pos": "unnamed_p",
                        "transform_rot": "unnamed_o"}

DEFAULT_FPS = 24.0


def _dm():
    from ..SST import get_datamodel
    return get_datamodel()


def plain_bone_name(name):
    """'bone 12 (bip_spine_0)' -> 'bip_spine_0'. Anything else unchanged."""
    if not name:
        return name
    m = BONE_NAME.match(name)
    return m.group(1) if m else name


# ─────────────────────────────────────────────────────────────────────────────
# Reading
# ─────────────────────────────────────────────────────────────────────────────

def session_fps(root):
    """
    The session's frame rate.

    renderSettings.frameRate is the timeline rate. movieSettings can override
    it for output, and when it does that is what the artist is working to.
    """
    try:
        settings = root.get("settings")
        if settings is None:
            return DEFAULT_FPS
        movie = settings.get("movieSettings")
        if movie is not None and movie.get("IsOverridingFrameRate"):
            rate = movie.get("OverridingFrameRate")
            if rate:
                return float(rate)
        render = settings.get("renderSettings")
        if render is not None and render.get("frameRate"):
            return float(render.get("frameRate"))
    except Exception:
        pass
    return DEFAULT_FPS


def _log_layer(channel):
    try:
        log = channel.get("log")
        if log is None:
            return None
        layers = log.get("layers")
        return layers[0] if layers else None
    except Exception:
        return None


def shot_clips(shot):
    """{clip name: DmeChannelsClip} for THIS shot's own channels clips.

    A shot DmeFilmClip carries a `channelTrackGroup` whose track
    (`animSetEditorChannels`) holds exactly ONE channels clip per animation
    set, named after the set. This is the only place a set's clip can be
    looked up by name SAFELY: within one shot, set names are unique; across
    a 17-shot film the same name appears seventeen times (measured on the
    Gomez session: 30 clips called `camera2` in one file).

    The result is cached on the shot dict, because read_session asks once
    per set and a Gomez-sized shot has two dozen of them.
    """
    cached = shot.get("_clip_index")
    if cached is not None:
        return cached
    out = {}
    element = shot.get("element")
    if element is not None:
        for tg in (element.get("trackGroups") or []):
            for tr in (tg.get("tracks") or []):
                for kid in (tr.get("children") or []):
                    if getattr(kid, "type", None) == "DmeChannelsClip":
                        out.setdefault(kid.name or "", kid)
    shot["_clip_index"] = out
    return out


def _clip_for_set(model, aset, shot=None):
    """
    The DmeChannelsClip carrying this set's channels.

    WITH A SHOT: the set's clip is looked up among that shot's OWN clips
    (see shot_clips) - by name, which is safe there and nowhere else.

    WITHOUT ONE: SFM names the clip after the animation set, so match by
    name first. If that fails, fall back to the clip whose channels target
    this set's own bone transforms - slower, but it cannot be fooled by a
    duplicate name. THE TRAP THAT MADE THE SHOT ROUTE NECESSARY: a camera
    or light set has no gameModel, so the bone fallback cannot run, and
    `named[0]` on a multi-shot film is the first same-named clip in FILE
    order - some other shot's. That is how the Gomez session imported a
    parked camera with a 55-second base shift: wrong clip, then a base
    correction computed for the wrong clip.
    """
    name = aset.name or ""
    if shot is not None and not shot.get("synthetic"):
        own = shot_clips(shot).get(name)
        if own is not None:
            return own
    clips = [e for e in model.elements if e.type == "DmeChannelsClip"]
    named = [c for c in clips if (c.name or "") == name]
    if len(named) == 1:
        return named[0]

    gm = aset.get("gameModel")
    if gm is None:
        return named[0] if named else None
    mine = {id(b) for b in (gm.get("bones") or [])}
    if not mine:
        return named[0] if named else None

    best, best_hits = None, 0
    for c in (named or clips):
        hits = 0
        for ch in (c.get("channels") or []):
            to = ch.get("toElement")
            if to is not None and id(to) in mine:
                hits += 1
        if hits > best_hits:
            best, best_hits = c, hits
    return best or (named[0] if named else None)


def describe_set(model, aset, fps, shot=None):
    """What one animation set holds. Cheap - counts, no conversion.

    Pass the owning shot when it is known - clip resolution is only
    name-safe inside one shot (see _clip_for_set)."""
    gm = aset.get("gameModel")
    clip = _clip_for_set(model, aset, shot)
    out = {
        "name": aset.name or "(unnamed)",
        "model": gm.get("modelName") if gm is not None else None,
        "has_gamemodel": gm is not None,
        "clip": clip,
        "aset": aset,
        "gamemodel": gm,
        "bones": 0, "flex": 0, "camera": 0, "root": 0, "other": 0,
        "keys": 0, "time_lo": None, "time_hi": None,
        "bone_names": [],
    }
    if clip is None:
        return out

    seen = set()
    for ch in (clip.get("channels") or []):
        attr = ch.get("toAttribute") or ""
        if (ch.name or "") in ROOT_CHANNELS:
            out["root"] += 1
        elif attr in ("position", "orientation"):
            out["bones"] += 1
            to = ch.get("toElement")
            nm = plain_bone_name(getattr(to, "name", None) or "")
            if nm and nm not in seen:
                seen.add(nm)
                if len(out["bone_names"]) < 400:
                    out["bone_names"].append(nm)
        elif attr == "flexWeight":
            out["flex"] += 1
        elif attr in ("fieldOfView", "focalDistance", "aperture"):
            out["camera"] += 1
        else:
            out["other"] += 1

        layer = _log_layer(ch)
        if layer is None:
            continue
        times = layer.get("times")
        if not times:
            continue
        out["keys"] += len(times)
        lo, hi = float(times[0]), float(times[-1])
        out["time_lo"] = lo if out["time_lo"] is None else min(out["time_lo"], lo)
        out["time_hi"] = hi if out["time_hi"] is None else max(out["time_hi"], hi)
    return out


def load_session_model(path):
    """Open a session .dmx, converting first if the reader cannot read it.

    A BINARY DMX IS NOT NECESSARILY UTF-8, AND THE READER ASSUMES IT IS.
    a real gothic session carries Polish filenames in its sound clips, so
    the bundled reader dies on

        UnicodeDecodeError: 'utf-8' codec can't decode byte 0xf3

    ...which is the one session with seventeen shots in it, i.e. the only file
    the shot list actually matters for. Read Session and List Shots both went
    through the plain loader and both failed on it.

    The session IMPORT path has always handled this by running Valve's
    dmxconvert to keyvalues2 text first. This does the same, but only AFTER
    the direct load fails - conversion spawns a process and rewrites megabytes,
    and every session that does not need it should not pay for it.
    """
    from ..core import DMX_Analyzer
    long = DMX_Analyzer.long_path(path)
    try:
        return _dm().load(long)
    except UnicodeDecodeError:
        pass
    except Exception:
        # anything else is a real failure; converting would only hide it
        raise

    import tempfile
    from . import Import_Session
    with tempfile.TemporaryDirectory() as tmp:
        text = Import_Session._convert_to_tex(Path(path), tmp)
        # _convert_to_tex hands back the TEXT, not a path
        tex = Path(tmp) / "session_reader.dmx"
        tex.write_text(text, encoding="utf-8")
        print(f"[SESSION]  {Path(path).name} is not UTF-8 - read via dmxconvert")
        return _dm().load(str(tex))


def read_session(path):
    """
    Open a session and describe every animation set in it.

    Returns a dict. Raises only if the file cannot be loaded at all.
    """
    path = Path(path)
    model = load_session_model(path)
    root = model.root

    fps = session_fps(root)
    clip = root.get("activeClip")
    duration = None
    start = 0.0
    if clip is not None:
        tf = clip.get("timeFrame")
        if tf is not None:
            duration = float(tf.get("duration") or 0.0)
            start = float(tf.get("start") or 0.0)

    # Shots first, sets second: each set's channels clip can only be
    # resolved safely inside the shot that owns it (see _clip_for_set)
    shot_list = shots(model, fps)
    shot_of = {}
    for sh in shot_list:
        for a in (sh.get("sets") or []):
            shot_of.setdefault(id(a), sh)

    sets = []
    for aset in [e for e in model.elements if e.type == "DmeAnimationSet"]:
        sets.append(describe_set(model, aset, fps,
                                 shot=shot_of.get(id(aset))))

    return {
        "path": str(path),
        "name": path.name,
        "model": model,
        "fps": fps,
        "shots": shot_list,
        "clip_name": getattr(clip, "name", None),
        "duration": duration,
        "start": start,
        "sets": sets,
        "animated": [s for s in sets if s["bones"] or s["flex"]],
        "cameras": [s for s in sets if s["camera"]],
    }


# ─────────────────────────────────────────────────────────────────────────────
# shots
# ─────────────────────────────────────────────────────────────────────────────
#
# what a session actually contains, and why importing one was all-or-nothing
#  --------------------------------------------------------------------------
# Everything in this add-on that finds animation sets does it the same way:
#
# [e for e in model.elements if e.type == "DmeAnimationSet"]
#
# On a one-shot session that's exactly right. On a real film it's a
# catastrophe, and the measurement is not close:
#
# test session (v1).dmx      1 shot     8 sets      8 elements
# new session2.dmx           1 shot    17 sets     17 elements
# particlestest.dmx          1 shot    28 sets     28 elements
# gothic2 - gomez - v3.dmx  17 shots   21-31 each  706 elements
#
# A SET is PER SHOT, NOT PER SESSION. `gomez` in shot 2 and `gomez` in shot 3
# are two DIFFERENT DmeAnimationSet elements carrying two different sets of
# channels, bc that's how SFM stores a cut. So scanning the element list
# on the gothic session finds 706 sets holding 51 distinct NAMES - seventeen
# overlapping copies of the same characters, every one of them imported on top
# of the last. That is why the workflow has been "strip the DMX down to one
# shot first": not a preference, the only thing that works
#
# WHERE THE SHOTS LIVE
#  --------------------
# root.activeClip                      DmeFilmClip - the MOVIE
# .subClipTrackGroup                 DmeTrackGroup, always this name
# .tracks -> DmeTrack "Film"       clipType 3
# .children -> [DmeFilmClip]     the SHOTS, in cut order
#
# Each shot carries its own `animationSets`, its own `camera`, and a
# `timeFrame` whose `start` is in MOVIE seconds. Measured on all four sessions
# above: `subClipTrackGroup` is present every time, and the movie clip's own
# `animationSets` list is EMPTY every time - the sets only ever hang off shots
#
# the property that makes this safe to adopt
#  ------------------------------------------
# On a one-shot session `shot_sets(shots[0])` and "every DmeAnimationSet in
# the file" are the SAME SET OF ELEMENTS - verified by identity, not by count,
# on all three one-shot sessions. So every consumer can switch to asking a
# shot for its sets and nothing changes for anybody who is not affected by the
# bug. That is the whole design: no flag, no second code path, no "legacy
# mode". A session with one shot has one shot

FILM_TRACK_CLIP_TYPE = 3      # dmx_clip_film


def _tf(element):
    """(start, duration, offset, scale) in seconds. Missing reads as 0/1."""
    if element is None:
        return (0.0, 0.0, 0.0, 1.0)
    t = element.get("timeFrame")
    if t is None:
        return (0.0, 0.0, 0.0, 1.0)

    def g(key, default=0.0):
        v = t.get(key)
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    return (g("start"), g("duration"), g("offset"), g("scale", 1.0))


def _film_tracks(clip):
    """Every track that holds shots, subClipTrackGroup first.

    `trackGroups` is checked as well as `subClipTrackGroup` even though all
    four measured sessions put the Film track in the latter - the cost is one
    loop over a list that is two long, and the failure it guards against would
    read as "this session has no shots" rather than as "we looked in the wrong
    place", which is the failure this add-on has already been bitten by once.
    """
    out = []
    groups = []
    sctg = clip.get("subClipTrackGroup") if clip is not None else None
    if sctg is not None:
        groups.append(sctg)
    groups.extend(list(clip.get("trackGroups") or []) if clip is not None else [])

    for tg in groups:
        for tr in (tg.get("tracks") or []):
            try:
                ctype = tr.get("clipType")
            except Exception:
                ctype = None
            kids = list(tr.get("children") or [])
            if not kids:
                continue
            # By TYPE of the children, not by the track's name. "Film" is the
            # English default and a track can be renamed; a DmeFilmClip child
            # is what a shot actually is.
            if ctype == FILM_TRACK_CLIP_TYPE or \
                    all(getattr(k, "type", None) == "DmeFilmClip" for k in kids):
                if tr not in out:
                    out.append(tr)
    return out


def shot_sets(shot):
    """The DmeAnimationSet elements this shot uses, in file order."""
    if shot is None:
        return []
    return [a for a in (shot.get("animationSets") or [])
            if getattr(a, "type", None) == "DmeAnimationSet"]


def shots(model, fps=None):
    """Every shot in the session, in cut order. Never empty.

    A session with no `subClipTrackGroup` - or one whose Film track is empty -
    comes back as a single shot covering the whole movie and holding every
    animation set in the file. Callers therefore never need to ask "does this
    session have shots"; it has at least one, and asking it for its sets gives
    the same answer the old element scan gave.
    """
    root = model.root
    clip = root.get("activeClip")
    if fps is None:
        fps = session_fps(root) or 24.0

    m_start, m_dur, m_off, m_scale = _tf(clip)

    out = []
    for track in _film_tracks(clip):
        for element in (track.get("children") or []):
            if getattr(element, "type", None) != "DmeFilmClip":
                continue
            start, dur, off, scale = _tf(element)
            cam = element.get("camera")
            sets = shot_sets(element)
            out.append({
                "index":       len(out),
                "name":        element.name or f"shot{len(out) + 1}",
                "element":     element,
                "start":       start,
                "duration":    dur,
                "offset":      off,
                "scale":       scale,
                # ROUNDED, NOT TRUNCATED. A shot boundary at 25.625s on a 24
                # fps timeline is frame 615.0 exactly; int() on the float that
                # comes back as 614.9999 would put the cut one frame early and
                # the error would be invisible until two shots disagreed about
                # who owns a frame.
                "frame_start": int(round(start * fps)),
                "frame_end":   int(round((start + dur) * fps)),
                "sets":        sets,
                "set_names":   [a.name for a in sets],
                "camera":      getattr(cam, "name", None),
                "camera_element": cam,
                "synthetic":   False,
                # 3.0.0: SFM's placeholder cuts - a shot with no animation sets is a slug
                "slug":        not sets,
                "map":         str(element.get("mapname") or ""),
            })

    if out:
        return out

    # no FILM TRACK. Present the whole session as one shot rather than
    # returning nothing, so no caller needs a special case for it.
    every = [e for e in model.elements if e.type == "DmeAnimationSet"]
    return [{
        "index": 0,
        "name": getattr(clip, "name", None) or "whole session",
        "element": clip,
        "start": m_start, "duration": m_dur, "offset": m_off, "scale": m_scale,
        "frame_start": int(round(m_start * fps)),
        "frame_end": int(round((m_start + m_dur) * fps)),
        "sets": every,
        "set_names": [a.name for a in every],
        "camera": getattr(clip.get("camera"), "name", None) if clip else None,
        "camera_element": clip.get("camera") if clip else None,
        "synthetic": True,
    }]



def _clip_time_frames(model, shot):
    """Every (start, offset, scale) triple among a shot's channels clips."""
    out = []
    for aset in (shot.get("sets") or ()):
        clip = _clip_for_set(model, aset, shot)
        if clip is None:
            continue
        s, _d, o, sc = _tf(clip)
        out.append((s, o, sc if sc else 1.0))
    return out


def shot_time_base(model, shot):
    """
    How to turn MOVIE seconds into the EXTRACT seconds the animation uses.

    Returns a dict:
        to_raw(movie_seconds) -> float
        movie_lo / movie_hi    the shot's own span, in movie seconds
        agreed                 True when every clip in the shot maps the same
        variants               the distinct (start, offset, scale) triples seen

    A shot whose clips disagree is not a failure - the MOST COMMON triple wins
    and `agreed` says so, because one odd set must not silently re-time the
    other twenty. Nothing here reads a key; it is arithmetic on four numbers.
    """
    s_start = float(shot.get("start") or 0.0)
    s_off = float(shot.get("offset") or 0.0)
    s_scale = float(shot.get("scale") or 1.0) or 1.0
    s_dur = float(shot.get("duration") or 0.0)

    triples = _clip_time_frames(model, shot)
    variants = sorted(set(triples))
    if triples:
        # most common wins; ties break on the first in file order, which is
        # the same rule `shots()` uses for everything else
        best = max(variants, key=lambda t: (triples.count(t), -variants.index(t)))
    else:
        # A shot with no channels clip at all - a slug. Identity is the only
        # honest answer, and it is never used, bc a slug has no sets
        best = (0.0, 0.0, 1.0)

    c_start, c_off, c_scale = best
    c_scale = c_scale or 1.0

    def to_raw(movie_seconds):
        shot_local = (float(movie_seconds) - s_start) * s_scale + s_off
        return (shot_local - c_start) * c_scale + c_off

    # AGREEMENT IS ABOUT THE MAPPING, not THE NUMBERS. gman1 writes
    # `(-5.0, -0.0417)` where its twelve shot-mates write `(-4.9583, 0.0)`,
    # and those are the SAME affine map. Comparing the triples flags that as
    # a disagreement and sends somebody looking for a bug in the one file
    # that is behaving. Compare what the triples do - two points settle an
    # affine map - and only differ when the result differs
    def _map_of(t):
        cs, co, csc = t[0], t[1], (t[2] or 1.0)
        return (round((0.0 - cs) * csc + co, 6),
                round((1.0 - cs) * csc + co, 6))

    distinct_maps = {_map_of(t) for t in variants}

    return {
        "to_raw": to_raw,
        "movie_lo": s_start,
        "movie_hi": s_start + s_dur,
        "agreed": len(distinct_maps) <= 1,
        "variants": variants,
        "clip_tf": best,
        "shot_tf": (s_start, s_off, s_scale),
        # what the whole mapping amounts to at movie second 0, in seconds.
        # Only meaningful when both scales are 1, which they are in every
        # session measured - it's for the report line, not for the maths.
        "offset_seconds": to_raw(0.0),
    }



TIMING_MOVIE = "MOVIE"
TIMING_RAW = "RAW"


def timing_mode(scene=None):
    """MOVIE (the default) or RAW - the project's choice of where shots land."""
    try:
        scene = scene or bpy.context.scene
        pr = getattr(scene, "ht_project", None)
        return TIMING_RAW if getattr(pr, "shot_timing", "") == TIMING_RAW \
            else TIMING_MOVIE
    except Exception:                                         # noqa: BLE001
        return TIMING_MOVIE


def place_shift(model, shot, mode=None, base=None):
    """Seconds added to a shot's REFERENCE raw time to put it on the Blender
    timeline. MOVIE: shot.start - to_raw(shot.start), so the reference clip's
    raw seconds become SFM movie seconds. RAW: 0.0 - extract time, where every
    version before 1.17.0 put it. Exact at the cut; a scaled shot or clip
    (none measured) is only exact there and is reported by the callers' own
    scale checks."""
    if shot is None or (mode or timing_mode()) == TIMING_RAW:
        return 0.0
    tb = base if base is not None else shot_time_base(model, shot)
    s0 = float(shot.get("start") or 0.0)
    return s0 - tb["to_raw"](s0)


def whole_frames(seconds, fps):
    """`seconds` on the frame grid. SFM writes times in 0.0001 s ticks, so the
    gothic shot's offset -10.7666 is -323/30 rounded - a shift built from it
    is 232.998 frames, which put every key 0.002 of a frame off its frame.
    Rounding the TOTAL shift recovers the frame SFM meant and keeps keys on
    whole frames (the clips' raw keys already sit on them)."""
    if not fps:
        return seconds
    return round(float(seconds) * float(fps)) / float(fps)


def clip_timeline_shift(model, shot, clip, mode=None, base=None, fps=None):
    """Seconds added to THIS clip's raw key times to put them on the Blender
    timeline: the rebase onto the shot's reference clip (see clip_base_shift)
    plus the shot's own placement (place_shift). The reference cancels out -
    in MOVIE mode this is (clip.start - clip.offset) + (shot.start -
    shot.offset), each clip on its own map, which is why the gothic intro's
    six disagreeing clip triples all land on one timeline."""
    if shot is None or clip is None:
        return 0.0
    mode = mode or timing_mode()
    tb = base if base is not None else shot_time_base(model, shot)
    c_s, _d, c_o, c_sc = _tf(clip)
    C_s, C_o, C_sc = tb["clip_tf"]
    rebase = 0.0
    if abs((c_sc or 1.0) - 1.0) <= 1e-6 and abs((C_sc or 1.0) - 1.0) <= 1e-6:
        rebase = (c_s - c_o) - (C_s - C_o)
    total = rebase + place_shift(model, shot, mode, base=tb)
    if mode == TIMING_MOVIE:
        total = whole_frames(total, fps)
    return total


def shot_timeline_frames(model, shot, fps, mode=None, base=None):
    """(start, end) frames of a shot ON THE BLENDER TIMELINE - its movie frames
    in MOVIE mode, its extract frames in RAW mode."""
    tb = base if base is not None else shot_time_base(model, shot)
    m = place_shift(model, shot, mode, base=tb)
    s0 = float(shot.get("start") or 0.0)
    s1 = s0 + float(shot.get("duration") or 0.0)
    return (int(round((tb["to_raw"](s0) + m) * fps)),
            int(round((tb["to_raw"](s1) + m) * fps)))


ELEMENT_KEYS = ("gameModel", "light", "camera", "particle system")


def element_shots(shot_list):
    """{id(element): shot} - the shot whose animation set points at each game
    model, light, camera and particle system. A whole-session import times
    each element through ITS OWN shot; a shot import has one answer anyway."""
    out = {}
    for sh in shot_list or ():
        for a in (sh.get("sets") or ()):
            for key in ELEMENT_KEYS:
                try:
                    v = a.get(key)
                except Exception:                             # noqa: BLE001
                    v = None
                if v is not None:
                    out.setdefault(id(v), sh)
    return out


def timeline_shift(info, entry, mode=None):
    """The extracted file's tf.start for one set: clip_base_shift() plus its
    shot's placement. Equal to clip_base_shift() in RAW mode."""
    mode = mode or timing_mode()
    base = clip_base_shift(info, entry)
    if mode == TIMING_RAW:
        return base
    aset = entry.get("aset")
    shot = None
    for sh in info.get("shots") or []:
        if any(a is aset for a in (sh.get("sets") or ())):
            shot = sh
            break
    if shot is None:
        return base
    return whole_frames(base + place_shift(info["model"], shot, mode),
                        info.get("fps"))



def shot_for_span(shot_list, movie_start, movie_duration=0.0):
    """
    (shot, overlaps) for a movie-time span. `overlaps` lists every shot it
    touches, longest first, so a caller can say "this one straddles a cut".

    Returns (None, []) when the span touches no shot at all.
    """
    lo = float(movie_start)
    hi = lo + max(0.0, float(movie_duration))
    if hi <= lo:
        hi = lo + 1e-6          #a zero-length clip still sits somewhere

    scored = []
    for s in shot_list:
        a = float(s.get("start") or 0.0)
        b = a + float(s.get("duration") or 0.0)
        over = min(hi, b) - max(lo, a)
        if over > 0.0:
            scored.append((over, len(s.get("sets") or ()) > 0, s))

    if not scored:
        return None, []

    scored.sort(key=lambda r: (r[1], r[0]), reverse=True)
    return scored[0][2], [r[2] for r in scored]


def shot_lines(info, shot_list=None):
    """The shot list as report text."""
    model = info["model"]
    fps = info["fps"]
    sl = shot_list if shot_list is not None else shots(model, fps)
    total = len([e for e in model.elements if e.type == "DmeAnimationSet"])

    L = [f"{info['name']}",
         f"  {len(sl)} shot(s)  @ {fps:g} fps",
         f"  {total} animation set element(s) in the file",
         ""]
    if len(sl) == 1 and sl[0]["synthetic"]:
        L.append("  No Film track - the whole session is one shot.")
        L.append("")

    for s in sl:
        span = s["frame_end"] - s["frame_start"]
        L.append(f"  {s['index'] + 1:>3}. {s['name'][:26]:<28}"
                 f"frames {s['frame_start']:>6}-{s['frame_end']:<7}"
                 f"({span:>5}) "
                 f"{len(s['sets']):>4} set(s)"
                 + (f"  cam {s['camera']}" if s["camera"] else ""))

    if len(sl) > 1:
        biggest = max(sl, key=lambda s: len(s["sets"]))
        L += ["",
              f"  Importing the whole session loads all {total} set element(s)",
              f"  - seventeen overlapping copies of the same characters, on a",
              f"  seventeen-shot film. One shot needs at most "
              f"{len(biggest['sets'])}."]
    return L


def report_lines(info, max_sets=30):
    L = [f"{info['name']}",
         f"  clip     : {info['clip_name']!r}",
         f"  fps      : {info['fps']:g}"]
    if info["duration"]:
        L.append(f"  duration : {info['duration']:g}s  "
                 f"({info['duration'] * info['fps']:.0f} frames)")
    L.append(f"  sets     : {len(info['sets'])}  "
             f"({len(info['animated'])} with animation, "
             f"{len(info['cameras'])} camera)")
    L.append("")
    for s in info["sets"][:max_sets]:
        bits = []
        if s["bones"]:
            bits.append(f"{s['bones']} bone ch")
        if s["flex"]:
            bits.append(f"{s['flex']} flex")
        if s["camera"]:
            bits.append(f"{s['camera']} cam")
        if s["root"]:
            bits.append("root")
        span = ""
        if s["time_lo"] is not None:
            span = (f"  frames {s['time_lo'] * info['fps']:.0f}"
                    f"-{s['time_hi'] * info['fps']:.0f}")
        L.append(f"  {s['name'][:30]:<32}{', '.join(bits) or 'no channels':<26}"
                 f"{s['keys']:>7} keys{span}")
        if s["model"]:
            L.append(f"      {s['model']}")
    if len(info["sets"]) > max_sets:
        L.append(f"  ... and {len(info['sets']) - max_sets} more")
    return L


# ─────────────────────────────────────────────────────────────────────────────
# Re-emitting an export-shaped DMX
# ─────────────────────────────────────────────────────────────────────────────

def extract_set(info, entry, out_path, rebase=True, rename_bones=True):
    """
    Write one animation set as an ordinary export-shaped animation DMX.

    *rebase* puts the set's first key at frame 0 instead of preserving its
    absolute position on the session timeline. Off keeps session timing, so
    several sets stay in sync with each other.

    Returns {"path", "frames", "channels", "bones"}.
    """
    dm = _dm()
    clip = entry["clip"]
    gm = entry["gamemodel"]
    if clip is None:
        raise RuntimeError(f"{entry['name']}: no channels clip")
    if gm is None:
        raise RuntimeError(f"{entry['name']}: no game model")

    fps = info["fps"]
    channels = list(clip.get("channels") or [])
    if not channels:
        raise RuntimeError(f"{entry['name']}: clip holds no channels")

    # Bone DAG names must match an armature imported from the same model,
    # so strip SFM's "bone N (...)" decoration. This mutates the loaded
    # session in memory only - it's discarded after the write.
    if rename_bones:
        def walk(node, seen):
            if node is None or id(node) in seen:
                return
            seen.add(id(node))
            nm = getattr(node, "name", None)
            if nm:
                plain = plain_bone_name(nm)
                if plain != nm:
                    node.name = plain
            for kid in (node.get("children") or []):
                walk(kid, seen)
        seen = set()
        for kid in (gm.get("children") or []):
            walk(kid, seen)
        for b in (gm.get("bones") or []):
            nm = getattr(b, "name", None)
            if nm:
                b.name = plain_bone_name(nm)

    # the root game-model transform: exports name these unnamed_p/unnamed_o
    # and the importer keys them onto the root empty. Rename so that the
    # existing code path recognises them
    for ch in channels:
        nm = getattr(ch, "name", None)
        if nm in ROOT_CHANNELS:
            ch.name = ROOT_CHANNELS[nm]

    # time -> frame is (t + start) * fps, so a rebase is just a negative
    # start, exactly the way SFM writes its own exports. Without rebase,
    # the start carries the CLIP BASE SHIFT - zero when this clip agrees
    # with its shot, the Szturm-camera correction when it does not (see
    # clip_base_shift).
    lo = entry["time_lo"] or 0.0
    #1.17.0: timeline_shift = clip_base_shift + the shot's placement on
    #SFM's movie clock (see WHERE A SHOT LANDS).
    start = -lo if rebase else timeline_shift(info, entry)
    hi = entry["time_hi"] or 0.0

    out = dm.DataModel("model", 18)
    root = out.add_element(entry["name"], "DmElement")
    out.root = root

    skeleton = out.add_element(entry["name"], "DmeModel")
    skeleton["transform"] = out.add_element("transform", "DmeTransform")
    skeleton["transform"]["position"] = dm.Vector3([0.0, 0.0, 0.0])
    skeleton["transform"]["orientation"] = dm.Quaternion([0.0, 0.0, 0.0, 1.0])
    skeleton["visible"] = True
    # DECLARE WHAT WAS ACTUALLY WRITTEN, NOT WHAT SFM WRITES.
    #
    # A genuine SFM export says upAxis = 'Y', and this used to copy that
    # bc matching the export exactly looked like the safe choice. It is
    # not. SFM's EXPORTER converts to Y-up on the way out; the DAG transforms
    # copied here come straight out of the live session, which is ordinary
    # Source Z-up. Saying 'Y' asks the importer to correct data that needs no
    # correcting, and the character arrives lying on the ground.
    #
    # Measured on one scout rig, pelvis -> head:
    # genuine export  , corrected   : (-0.038,  0.030,  0.999)  upright
    # genuine export  , uncorrected : (-0.038,  0.999, -0.030)  on its side
    # session extract , corrected   : ( 0.008, -1.000,  0.000)  on its side
    # session extract , uncorrected : ( 0.008,  0.000,  1.000)  upright
    #
    # This is why a scene could arrive half upright and half flat: exported
    # animations and session-extracted ones were being told the same thing and
    # only one of them was hurt by it
    skeleton["upAxis"] = "Z"
    # genuine exports leave both of these EMPTY - verified against
    # binder.dmx - so this matches, it doesn't cut a corner. BST rebuilds
    # the skeleton from the DAG tree
    skeleton["jointList"] = dm.make_array([], dm.Element)
    skeleton["baseStates"] = dm.make_array([], dm.Element)
    skeleton["children"] = dm.make_array(
        list(gm.get("children") or []), dm.Element)
    if gm.get("modelName"):
        skeleton["modelName"] = str(gm.get("modelName"))
    root["skeleton"] = skeleton

    anim = out.add_element(entry["name"], "DmeChannelsClip")
    anim["channels"] = dm.make_array(channels, dm.Element)
    anim["frameRate"] = float(fps)
    tf = out.add_element("timeFrame", "DmeTimeFrame")
    tf["start"] = dm.Time(start)
    tf["duration"] = dm.Time(max(0.0, hi - lo))
    tf["offset"] = dm.Time(0.0)
    tf["scale"] = 1.0
    anim["timeFrame"] = tf

    alist = out.add_element("animationList", "DmeAnimationList")
    alist["animations"] = dm.make_array([anim], dm.Element)
    root["animationList"] = alist

    tags = out.add_element("exportTags", "DmElement")
    tags["app"] = "HoovyTools session extract"
    tags["frameRate"] = float(fps)
    tags["mdl"] = str(gm.get("modelName") or "")
    tags["session"] = str(info["name"])
    tags["upAxis"] = "Z"          # must agree with skeleton["upAxis"] above
    root["exportTags"] = tags

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.write(str(out_path), "binary", 5)

    return {
        "path": out_path,
        "frames": ((hi - lo) * fps) if entry["time_hi"] is not None else 0.0,
        "channels": len(channels),
        "bones": entry["bones"],
        "flex": entry["flex"],
    }


def default_out_dir(session_path):
    """
    Where extracted animations go by default: an `anims` folder beside the
    session itself.

    Beside the session rather than in some configured location, because the
    session is the thing being taken apart - the pieces belong next to it,
    and a second .blend pointed at the same session finds them already
    there.
    """
    return Path(session_path).parent / "anims"


def _rescale_of(channel):
    """
    The (lo, hi) a camera channel's value is lerped through, or None.

    WHY CAMERAS NEED THIS AND MODELS DO NOT
    ======================================
    A session does not store camera settings in their real units. It stores
    a NORMALISED 0..1 slider value and routes it through a
    DmeExpressionOperator named <attr>_rescale whose expr is
    `lerp(value, lo, hi)`:

        fieldOfView   raw 0.2036  lo 10   hi 120  ->  32.4 degrees
        focalDistance raw 0.3568  lo 1    hi 200  ->  72.0

    SFM's own exporter collapses that chain and writes real units. Extract
    the raw value instead and you get a 0.2 degree camera, so this reads the
    operator's own lo/hi and applies the same lerp.
    """
    to = channel.get("toElement")
    if to is None or (to.type or "") != "DmeExpressionOperator":
        return None
    try:
        expr = str(to.get("expr") or "")
        if "lerp" not in expr:
            return None
        lo = to.get("lo")
        hi = to.get("hi")
        if lo is None or hi is None:
            return None
        return float(lo), float(hi)
    except Exception:
        return None


def _camera_of(model, clip, set_name=None):
    """
    The DmeCamera this clip drives, or None.

    Three routes, most specific first. The last one is deliberately NOT
    "just take the first camera": a session with several cameras would then
    hand every set the same one, which is worse than admitting defeat.
    """
    # 1. a channel that writes straight into a camera
    for ch in (clip.get("channels") or []):
        to = ch.get("toElement")
        if to is not None and (to.type or "") == "DmeCamera":
            return to

    cams = [e for e in model.elements if e.type == "DmeCamera"]

    # 1b. a channel that drives a camera's TRANSFORM - the movement channels
    # (transform_pos / transform_rot) target the DmeTransform, not the
    # camera, so route 1 misses an animated camera whose value channels
    # are all behind operators. Identity again, never name: the Gomez
    # session holds 95 DmeCameras and thirty of them are called
    # "camera2"
    by_transform = {id(c.get("transform")): c for c in cams
                    if c.get("transform") is not None}
    for ch in (clip.get("channels") or []):
        to = ch.get("toElement")
        if to is not None and id(to) in by_transform:
            return by_transform[id(to)]

    #2. a camera named after the set - SFM names them in step
    if set_name:
        want = str(set_name).strip().lower()
        for c in cams:
            if (c.name or "").strip().lower() == want:
                return c

    #3. an unambiguous session with exactly one camera
    return cams[0] if len(cams) == 1 else None


def clip_base_shift(info, entry, _cache={}):
    """Seconds the extracted timeFrame.start must carry so THIS set's raw
    key times land on the same timeline as the rest of its shot.

    MEASURED ON THE GOMEZ SESSION (2026-08-27, shot 'Szturm'): the model
    clips in the shot share timeFrame.start -5.0, but the shot's camera
    clip says start -60.625 - raw key times are in each clip's OWN media
    time, so the camera's raw 60.04s and gerold's raw 4.88s are the SAME
    INSTANT. Extracting both with tf.start 0 put the camera 55.6 seconds
    away from the characters it was filming. shot_time_base() already
    elects a REFERENCE triple per shot (sounds and the frame range use
    it); this returns the shift that maps this clip's raw times onto that
    reference:

        shift = (clip.start - clip.offset) - (ref.start - ref.offset)

    A clip that matches the reference gets EXACTLY 0.0 - which is every
    set in every session measured before this one, so old sessions
    extract byte-identically.
    """
    model = info["model"]
    aset = entry.get("aset")
    clip = entry.get("clip")
    if aset is None or clip is None:
        return 0.0
    key = id(model)
    if _cache.get("model_key") != key:
        _cache.clear()
        _cache["model_key"] = key
        _cache["by_set"] = {}
        try:
            for sh in info.get("shots") or []:
                tb = shot_time_base(model, sh)
                ref = tb["clip_tf"]
                for a in (sh.get("sets") or []):
                    _cache["by_set"][id(a)] = ref
        except Exception:                                     # noqa: BLE001
            pass
    ref = _cache.get("by_set", {}).get(id(aset))
    if ref is None:
        return 0.0
    c_s, _d, c_o, c_scale = _tf(clip)
    C_s, C_o, C_scale = ref
    if abs((c_scale or 1.0) - 1.0) > 1e-6 or abs((C_scale or 1.0) - 1.0) > 1e-6:
        # A scaled clip needs the full affine treatment; none measured yet
        print(f"[EXTRACT]  {entry.get('name')}: scaled timeFrame - "
              f"base shift skipped")
        return 0.0
    shift = (c_s - c_o) - (C_s - C_o)
    if abs(shift) > 1e-6:
        print(f"[EXTRACT]  {entry.get('name')}: clip base differs from the "
              f"shot's by {shift:+.4f}s - rebased onto the shot timeline")
    return shift


def extract_camera_set(info, entry, out_path):
    """
    Write one camera animation set as an ordinary camera-export DMX.

    Camera sets have no gameModel, which is exactly why they used to be
    skipped entirely - the session extractor only understood characters.
    Their shape differs from an animation export in three ways, and all
    three have to be handled or the file imports as nothing:

      * the root carries `camera`, not `skeleton`
      * the transform channels are transform_pos / transform_rot
      * every camera setting is a normalised 0..1 value behind a rescale
        operator (see _rescale_of)
    """
    dm = _dm()
    model = info["model"]
    clip = entry["clip"]
    if clip is None:
        raise RuntimeError(f"{entry['name']}: no channels clip")
    camera = _camera_of(model, clip, entry.get("name"))
    if camera is None:
        raise CameraNotResolved(
            f"{entry['name']}: no camera element could be matched")

    fps = info["fps"]
    lo_t = entry["time_lo"] or 0.0
    hi_t = entry["time_hi"] or 0.0

    out = dm.DataModel("model", 18)
    root = out.add_element(entry["name"], "DmElement")
    out.root = root
    root["camera"] = camera

    kept = []
    rescaled = 0
    for ch in (clip.get("channels") or []):
        name = ch.name or ""

        #the 0-key mirror channels SFM keeps between the operator and the
        #camera - they carry nothing and their names match nothing
        if name.startswith("scaled_") and name.endswith("_channel"):
            continue

        if name in CAMERA_ROOT_CHANNELS:
            ch.name = CAMERA_ROOT_CHANNELS[name]
            kept.append(ch)
            continue

        span = _rescale_of(ch)
        if span is None:
            continue

        layer = _log_layer(ch)
        if layer is None:
            continue
        times = layer.get("times")
        values = layer.get("values")
        if not times or not values:
            continue

        lo, hi = span
        new_ch = out.add_element(name, "DmeChannel")
        new_ch["toAttribute"] = name
        log = out.add_element(name, "DmeFloatLog")
        lay = out.add_element(name, "DmeFloatLogLayer")
        lay["times"] = dm.make_array([dm.Time(float(t)) for t in times],
                                     dm.Time)
        lay["values"] = dm.make_array(
            [float(lo) + float(v) * (float(hi) - float(lo)) for v in values],
            float)
        log["layers"] = dm.make_array([lay], dm.Element)
        new_ch["log"] = log
        kept.append(new_ch)
        rescaled += 1

    if not kept:
        raise RuntimeError(f"{entry['name']}: nothing usable in the clip")

    anim = out.add_element(entry["name"], "DmeChannelsClip")
    anim["channels"] = dm.make_array(kept, dm.Element)
    anim["frameRate"] = float(fps)
    tf = out.add_element("timeFrame", "DmeTimeFrame")
    # not 0.0 ANY MORE: the shift that puts this clip's raw times on the
    # same timeline as its shot-mates - see clip_base_shift(). Zero for
    # every clip that agrees with its shot, which is every set in every
    # session measured before the Gomez one.
    tf["start"] = dm.Time(timeline_shift(info, entry))         # 1.17.0
    tf["duration"] = dm.Time(max(0.0, hi_t - lo_t))
    tf["offset"] = dm.Time(0.0)
    tf["scale"] = 1.0
    anim["timeFrame"] = tf

    alist = out.add_element("animationList", "DmeAnimationList")
    alist["animations"] = dm.make_array([anim], dm.Element)
    root["animationList"] = alist

    tags = out.add_element("exportTags", "DmElement")
    tags["app"] = "HoovyTools session extract"
    tags["frameRate"] = float(fps)
    tags["type"] = "camera"
    tags["session"] = str(info["name"])
    root["exportTags"] = tags

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.write(str(out_path), "binary", 5)
    return {"path": out_path, "channels": len(kept), "rescaled": rescaled,
            "camera": getattr(camera, "name", "camera"),
            "frames": (hi_t - lo_t) * fps, "bones": 0, "flex": 0}


def safe_name(name):
    keep = "".join(c if (c.isalnum() or c in " _-.") else "_" for c in name)
    return keep.strip() or "set"


def sets_for_shot(info, shot):
    """The entries of `info["sets"]` belonging to one shot. None -> all of them.

    MATCHED BY ELEMENT IDENTITY, NOT BY NAME. On a multi-shot film the same
    character appears once per cut under the same name, as a DIFFERENT
    DmeAnimationSet element with different channels - so matching on the name
    would pull all seventeen `gomez` sets back in and undo the whole point.
    `describe_set` already keeps the element as `entry["aset"]`, so this is an
    identity test and cannot be fooled.
    """
    if shot is None:
        return list(info["sets"])
    wanted = {id(a) for a in shot.get("sets") or ()}
    return [e for e in info["sets"] if id(e.get("aset")) in wanted]


def extract_session(path, out_dir=None, rebase=True, only_animated=True,
                    name_filter="", cameras=True, shot=None,
                    shot_index=None, shot_name=None, skip_names=None):
    """Extract every animation set in a session. Returns a summary dict.

    `shot` limits the extract to one cut. Pass the shot dict, or pass
    `shot_index`/`shot_name` and it is resolved against this file's shot list -
    which is what a caller holding only the scene's stored choice has.
    """
    info = read_session(path)
    out_dir = Path(out_dir) if out_dir else default_out_dir(path)

    shot_note = ""
    if shot is None and shot_index is not None and int(shot_index) >= 0:
        from . import Session_Paths
        shot, shot_note = Session_Paths.resolve_shot(
            info["shots"], index=shot_index, name=shot_name)

    #FILTER FIRST, THEN "only animated". The other order asks "is this set
    #animated anywhere in the film" and keeps a set that moves in some OTHER
    #cut but is a single static key in this one
    sets = sets_for_shot(info, shot)
    if only_animated:
        sets = [e for e in sets if e["bones"] or e["flex"]]
    if name_filter:
        needle = name_filter.lower()
        sets = [s for s in sets if needle in s["name"].lower()]

    written, skipped, failed = [], [], []
    # 1.26.0 SKIP HIDDEN OBJECTS: {set name: what hides it} - no file, so no
    # animation and no camera for a set SFM hides
    if skip_names:
        for s in sets:
            if s["name"] in skip_names:
                skipped.append((s["name"], f"hidden in SFM (by {skip_names[s['name']]})"
                                if isinstance(skip_names, dict) else "hidden in SFM"))
        sets = [s for s in sets if s["name"] not in skip_names]
    from ..core import Progress
    for s_idx, entry in enumerate(sets, 1):
        Progress.update(s_idx, len(sets), f"extract  {entry['name']}")
        # A camera set has no gameModel, which is why every one of them used
        # to be skipped and no camera animation ever came out of a session.
        if entry["camera"] and not entry["has_gamemodel"]:
            if not cameras:
                skipped.append((entry["name"], "camera (skipped by request)"))
                continue
            target = out_dir / f"{safe_name(entry['name'])}.dmx"
            try:
                written.append(extract_camera_set(info, entry, target))
            except CameraNotResolved as exc:
                skipped.append((entry["name"], str(exc)))
            except Exception as exc:
                failed.append((entry["name"],
                               f"{type(exc).__name__}: {exc}"))
            continue

        if not entry["has_gamemodel"]:
            skipped.append((entry["name"], "no game model and no camera"))
            continue
        if not entry["bones"]:
            skipped.append((entry["name"], "no bone channels"))
            continue
        # A set whose whole timeline collapses to one instant is a PLACED PROP.
        # These used to be skipped on the grounds that there is no animation to
        # import - true, and beside the point. The prop still has a PLACEMENT:
        # a rootTransform saying where in the scene it stands and which way it
        # faces. Skip the file and the prop never receives it, so it sits at the
        # world origin with no rotation while every animated character around it
        # gets the SFM -> Blender map. In `new session.dmx` that left `pit_a1` -
        # the ground the whole shot stands on - exactly 90 degrees out from the
        # six characters on top of it
        #
        # So it's written like any other set. One key per channel is a shape
        # the importer already handles; it just lands as placement instead of
        # motion
        static = (entry["time_lo"] is not None
                  and abs(entry["time_hi"] - entry["time_lo"]) < 1e-9)
        target = out_dir / f"{safe_name(entry['name'])}.dmx"
        try:
            r = extract_set(info, entry, target, rebase=rebase)
            r["static"] = static
            written.append(r)
        except Exception as exc:
            failed.append((entry["name"], f"{type(exc).__name__}: {exc}"))

    return {"info": info, "written": written, "skipped": skipped,
            "failed": failed, "out_dir": out_dir,
            "shot": shot, "shot_note": shot_note}


# ─────────────────────────────────────────────────────────────────────────────
# Operators
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_session_shots(Operator):
    """NEEDS a connected session - set it with Connect Session. Reads it and
        changes nothing

        List the SHOTS in the connected session, with their frame ranges

An SFM session is a film, and a film is a list of cuts. Each shot carries
its OWN animation sets - `gomez` in shot 2 and `gomez` in shot 3 are two
different elements holding two different sets of channels, because that is
how SFM stores a cut.

Which is why importing a multi-shot session has been all-or-nothing.
Measured on a real 17-shot film: 706 animation set elements in the file,
holding 51 distinct names - seventeen overlapping copies of the same
characters, every one imported on top of the last. Each shot needs 21 to
31 of them.

This is the list you would pick from. It shows every shot in cut order,
its frame range on the movie timeline, how many sets it uses and which
camera it cuts to. A one-shot session shows one shot covering everything,
which is exactly what importing it already does today"""
    bl_idname = "ht.session_shots"
    bl_label = "List Shots"
    bl_options = {"REGISTER"}

    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})  # type: ignore

    def execute(self, context):
        from . import Session_Paths
        path = self.filepath or None
        if not path:
            p = Session_Paths.session_file(context.scene)
            path = str(p) if p else None
        if not path:
            self.report({"ERROR"},
                        "No session connected - set one in the Main tab")
            return {"CANCELLED"}

        try:
            info = read_session(path)
        except Exception as exc:                              # noqa: BLE001
            self.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}

        sl = info["shots"]
        lines = shot_lines(info, sl)

        # the per-shot set names go to the console and the Text block only -
        # seventeen shots times twenty-four names isn't a popup.
        full = list(lines) + ["", "── SETS PER SHOT " + "─" * 40]
        for s in sl:
            full.append(f"  {s['index'] + 1:>3}. {s['name']}")
            for n in s["set_names"]:
                full.append(f"         {n}")

        print()
        for line in full:
            print(f"[SHOTS]  {line}")

        name = f"HT_shots_{Path(path).stem}"[:60]
        txt = bpy.data.texts.get(name) or bpy.data.texts.new(name)
        txt.clear()
        txt.write("\n".join(full))

        from ..core import Report_UI
        Report_UI.report(
            context, "session_report", "Shots", lines[:26], level='INFO',
            icon='SEQUENCE', operator=self, prefix="SHOTS",
            summary=(f"{len(sl)} shot(s)"
                     + (f", {len(sl[0]['sets'])} set(s)" if len(sl) == 1
                        else f", {min(len(s['sets']) for s in sl)}-"
                             f"{max(len(s['sets']) for s in sl)} sets each")
                     + f" - full list in Text '{name}'"))
        return {"FINISHED"}


class HT_OT_session_report(Operator):
    """NEEDS a connected session - set it with Connect Session. Reads it and
        changes nothing

        Read the connected session and list what is actually in it

Opens the .dmx and describes every animation set: the model behind it,
how many bone and flex channels it has, its key count and frame range,
plus the session's frame rate and duration.

The fastest way to answer "why did nothing import?" - it shows which sets
carry animation, which are cameras or lights, and which are a single
static placement key.

It also surfaces things that become invisible once imported, such as
which sets carry BONE SCALE channels.

Reading a session used to be impractical: the DMX loader was O(n^2) and a
2.3 MB session took 75 seconds. It takes about 0.4 now, which is what
makes this button worth pressing. The full text also goes to a Text
datablock"""
    bl_idname = "ht.session_report"
    bl_label = "Read Session"
    bl_options = {"REGISTER"}

    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})  # type: ignore

    def execute(self, context):
        from . import Session_Paths
        path = self.filepath or None
        if not path:
            p = Session_Paths.session_file(context.scene)
            path = str(p) if p else None
        if not path:
            self.report({"ERROR"},
                        "No session connected - set one in the Main tab")
            return {"CANCELLED"}

        try:
            info = read_session(path)
        except Exception as exc:
            self.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}

        lines = report_lines(info)
        print()
        for line in lines:
            print(f"[SESSION]  {line}")

        name = f"HT_session_{Path(path).stem}"[:60]
        txt = bpy.data.texts.get(name) or bpy.data.texts.new(name)
        txt.clear()
        txt.write("\n".join(lines))

        from ..core import Report_UI
        Report_UI.report(
            context, "session_report", "Session", lines[:24], level='INFO',
            icon='SCENE_DATA', operator=self, prefix="SESSION_READ",
            summary=f"Session - {len(info['sets'])} set(s), "
                    f"{len(info['animated'])} animated, {info['fps']:g} fps")
        return {"FINISHED"}


class HT_OT_session_extract(Operator):
    """NEEDS a connected session - set it with Connect Session. Writes .dmx
        (animation) files into an anims folder beside it

        Write each of the session's animation sets out as an ordinary .dmx

Turns the session into export-shaped animation files in an anims folder
beside it - exactly the files SFM would have written had you exported by
hand. Exporting from SFM becomes optional.

WHY YOU WANT THE FILES ON DISK
  Handing ONE of them to the standalone DMX Animation importer is how you
  tell an EXTRACTION problem apart from an IMPORT problem. Without them
  that distinction is guesswork.

Rebase off keeps every set in sync with the others, which is what a whole
scene wants. Rebase on puts each set's first key at frame 0, which is
what a single reusable take wants.

Static sets are written too. Skipping them once meant the ground the
whole shot stands on never received its placement and sat at the origin
while six characters on it did not - one key is placement, and placement
matters"""
    bl_idname = "ht.session_extract"
    bl_label = "Extract Animations From Session"
    bl_options = {"REGISTER"}

    directory: StringProperty(subtype="DIR_PATH", options={"SKIP_SAVE"})  # type: ignore
    rebase: BoolProperty(  # type: ignore
        name="Rebase To Frame 0",
        description=("Put each set's first key at frame 0. Turn OFF to keep "
                     "every set where it sits on the session timeline, which "
                     "is what you want when several sets have to stay in "
                     "sync with each other"),
        default=False,
    )
    only_animated: BoolProperty(  # type: ignore
        name="Only Animated Sets",
        description="Skip sets with no keys at all",
        default=True,
    )
    name_filter: StringProperty(  # type: ignore
        name="Filter",
        description="Only sets whose name contains this text",
        default="",
    )
    connect_after: BoolProperty(  # type: ignore
        name="Connect Folder After",
        description=("Point this .blend's Animations folder at wherever the "
                     "files were written, so Import Animations is ready to "
                     "run straight away"),
        default=True,
    )

    def invoke(self, context, event):
        from . import Session_Paths
        # default beside the session, not into whatever folder happens to be
        # connected - the extracted files belong with the file they came out
        # of, and that keeps a re-extract idempotent
        p = Session_Paths.session_file(context.scene)
        if p is not None:
            self.directory = str(default_out_dir(p))
        else:
            d = Session_Paths.animations_dir(context.scene)
            if d is not None:
                self.directory = str(d)
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        from . import Session_Paths
        col = self.layout.column()
        p = Session_Paths.session_file(context.scene)
        if p is None:
            box = col.box()
            box.alert = True
            box.label(text="No session connected", icon='ERROR')
            box.label(text="Set one in the Main tab first.")
            return
        col.label(text=f"Session: {p.name}", icon='SCENE_DATA')
        col.separator()
        col.prop(self, "directory", text="Write to")
        col.prop(self, "name_filter")
        col.prop(self, "only_animated")
        col.prop(self, "rebase")
        col.prop(self, "connect_after")

    def execute(self, context):
        from . import Session_Paths
        p = Session_Paths.session_file(context.scene)
        if p is None:
            self.report({"ERROR"},
                        "No session connected - set one in the Main tab")
            return {"CANCELLED"}
        out_dir = self.directory or str(default_out_dir(p))

        try:
            r = extract_session(p, out_dir, rebase=self.rebase,
                                only_animated=self.only_animated,
                                name_filter=self.name_filter)
        except Exception as exc:
            self.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}

        lines = [
            f"Session : {r['info']['name']}",
            f"FPS     : {r['info']['fps']:g}",
            f"Written : {len(r['written'])} file(s)",
            f"Skipped : {len(r['skipped'])}",
            f"Failed  : {len(r['failed'])}",
            f"Folder  : {r['out_dir']}",
        ]
        print()
        for line in lines:
            print(f"[EXTRACT]  {line}")
        for w in r["written"]:
            print(f"[EXTRACT]    {w['path'].name:<40} "
                  f"{w['bones']} bone ch, {w['frames']:.0f} frames")
        for n, why in r["skipped"]:
            print(f"[EXTRACT]    skip {n}: {why}")
        for n, why in r["failed"]:
            print(f"[EXTRACT]    FAIL {n}: {why}")

        if self.connect_after and r["written"]:
            pr = Session_Paths.project(context)
            if pr is not None:
                pr.animations_path = str(r["out_dir"])
                pr.scanned = False
                lines.append("Animations folder now points here.")

        level = "WARNING" if r["failed"] else "INFO"
        from ..core import Report_UI
        Report_UI.report(
            context, "session_extract", "Extracted From Session", lines,
            level=level, icon='FILE_TICK', operator=self,
            prefix="SESSION_EXTRACT",
            summary=f"Extracted {len(r['written'])} animation(s)"
                    + (f", {len(r['failed'])} failed" if r["failed"] else ""))
        return {"FINISHED"}


_CLASSES = (
    HT_OT_session_report,
    HT_OT_session_extract,
    HT_OT_session_shots,
)


def register(icon_id_fn=None):
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
