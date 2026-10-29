"""
DMX_Analyzer.py  -  part of HoovyTools          [roadmap #6]
============================================================

The layer between a file and the importers.

    FILE -> ANALYZE -> ROUTE -> IMPORT

Nothing should start by assuming the user handed it the kind of DMX it
happens to import. analyze() reads the file and reports what is actually in
there. One DMX can hold several interesting categories at once, so the result
is a SET of kinds, never a single forced enum.

WHY THERE ARE TWO PASSES
========================
Measured on a real corpus (5084 files, 2026-08-20):

    full datamodel.load() of a 2.4 MB sfm_session   55.2  s
    raw byte scan of the same file                   0.0045 s

Sessions are pathological for the loader; exports are not (a 4.2 MB model
loads in 0.26 s). So:

    FAST pass   header + marker scan of the raw bytes. Always runs.
                Costs single-digit milliseconds on a 2.4 MB session.
                Every binary DMX stores each unique string once in its
                string dictionary, so "does the token flexWeight occur"
                is a reliable presence test without decoding one element.

    DEEP pass   real datamodel.load(). Adds FPS, frame range, channel
                census, bone/flex names, shot bounds - and for a session,
                its animation sets and the models they drive. Skipped only
                for oversized files now; see want_deep(). Sessions used to
                be excluded because they took ~55 s, which the O(1) element
                lookup in SST/datamodel.py removed.

Callers that need FPS must ask for a deep analysis and check `deep` on the
result: a fast-only analysis reports fps None, never a guess.

MARKERS AND WHAT THEY MEAN  (verified against the corpus)
=========================================================
    sfm_session (header format)  the file IS a session
    flexWeight                   facial / shape key animation channels
    fieldOfView + DmeCamera      a camera with its own animation
    unnamed_p / unnamed_o        root game-model transform channels
    ShotBoundsChannel            authoritative shot range, DmeBoolLog
    DmeGameModel                 models referenced by a session
    DmeProjectedLight / DmeLight lights  [roadmap #15, research only]

A session that contains facial animation reports SESSION *and* SHAPEKEY.
That is correct and deliberate - do not collapse it to one answer.
"""

import os
import re
import struct
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
#  Kinds
# ─────────────────────────────────────────────────────────────────────────────

SESSION   = "SESSION"
ANIMATION = "ANIMATION"
CAMERA    = "CAMERA"
SHAPEKEY  = "SHAPEKEY"
LIGHT     = "LIGHT"
MODEL     = "MODEL"

KIND_ORDER = (SESSION, ANIMATION, CAMERA, SHAPEKEY, LIGHT, MODEL)

KIND_LABEL = {
    SESSION:   "Session",
    ANIMATION: "Animation",
    CAMERA:    "Camera",
    SHAPEKEY:  "Shape Keys",
    LIGHT:     "Light",
    MODEL:     "Model / Reference",
}

KIND_ICON = {
    SESSION:   'SCENE_DATA',
    ANIMATION: 'ACTION',
    CAMERA:    'CAMERA_DATA',
    SHAPEKEY:  'SHAPEKEY_DATA',
    LIGHT:     'LIGHT_POINT',
    MODEL:     'MESH_DATA',
}

# Which operator each kind routes to. None = not built yet, see roadmap.
KIND_OPERATOR = {
    SESSION:   ("ht.import_session",       "Import Session Models"),
    ANIMATION: ("ht.import_dmx_animation", "Import DMX Animation"),
    CAMERA:    ("ht.import_dmx_camera",    "Import DMX Camera"),
    SHAPEKEY:  ("ht.import_shape_keys",    "Import Shape Keys"),
    LIGHT:     ("ht.import_lights",         "Import Lights (Experimental)"),
    MODEL:     ("ht.import_mdl",           "Import MDL Model"),
}


# ─────────────────────────────────────────────────────────────────────────────
#  Fast pass
# ─────────────────────────────────────────────────────────────────────────────

_HEADER_RE = re.compile(
    rb"<!--\s*dmx encoding (\S+) (\d+) format (\S+) (\d+)\s*-->")
_HEADER_PROTO_RE = re.compile(rb"<!--\s*DMXVersion binary_v(\d+)\s*-->")

# token -> what its presence proves
_MARKERS = {
    b"flexWeight":        "flex",
    b"fieldOfView":       "fov",
    b"DmeCamera":         "camera_elem",
    b"unnamed_p":         "root_pos",
    b"unnamed_o":         "root_rot",
    b"ShotBoundsChannel": "shot_bounds",
    b"DmeGameModel":      "game_model",
    b"DmeAnimationSet":   "anim_set",
    b"DmeFilmClip":       "film_clip",
    b"DmeProjectedLight": "proj_light",
    b"DmeLight":          "light",
    b"DmeChannel":        "channel",
    b"DmeTrackGroup":     "track_group",
    b"skeleton":          "skeleton",
    b"DmeDag":            "dag",
    b"DmeMesh":           "mesh",
    b"frameRate":         "frame_rate",
}

# Files bigger than this never get a deep pass unless deep=True is forced.
DEEP_SIZE_LIMIT = 8 * 1024 * 1024


def long_path(path):
    """
    Windows refuses paths past 260 characters unless they carry the \\?\
    prefix. a real corpus nests deeply enough to hit that - a sweep of
    5083 files found 6 that os.walk could list and open() could not touch.

    The prefix demands an absolute path with no forward slashes and no
    relative parts, so normalise before prefixing. Anything already
    prefixed, any UNC path, and every non-Windows path is handed back
    untouched.
    """
    s = str(path)
    if os.name != "nt" or s.startswith("\\\\?\\"):
        return s
    try:
        s = os.path.abspath(s)
    except (OSError, ValueError):
        return s
    if s.startswith("\\\\"):
        return "\\\\?\\UNC" + s[1:]
    return "\\\\?\\" + s


def read_header(path):
    """(encoding, encoding_ver, format, format_ver) or None. Reads 256 bytes."""
    try:
        with open(long_path(path), "rb") as f:
            head = f.read(256)
    except OSError:
        return None
    m = _HEADER_RE.search(head)
    if m:
        return (m.group(1).decode("ascii", "replace"), int(m.group(2)),
                m.group(3).decode("ascii", "replace"), int(m.group(4)))
    m = _HEADER_PROTO_RE.search(head)
    if m:
        return ("binary_proto", int(m.group(1)), "unknown", 0)
    return None


def scan_markers(path, limit=None):
    """Set of marker tags present in the raw bytes. Milliseconds, not seconds."""
    try:
        with open(long_path(path), "rb") as f:
            blob = f.read() if limit is None else f.read(limit)
    except OSError:
        return set()
    return {tag for token, tag in _MARKERS.items() if token in blob}


def want_deep(path, fmt):
    """
    Should the deep pass run for this file, when deep='auto'?

    Sessions used to be excluded outright: a 2.4 MB session took 55 s to
    load. That was an O(n^2) element lookup in the Datamodel loader, fixed
    in SST/datamodel.py (_element_by_id) - the same file now loads in 0.4 s,
    a 179x speedup. So sessions are read like anything else and only the
    size limit applies.
    """
    try:
        return os.path.getsize(long_path(path)) <= DEEP_SIZE_LIMIT
    except OSError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  Deep pass
# ─────────────────────────────────────────────────────────────────────────────

def _get_datamodel():
    from ..SST import get_datamodel
    return get_datamodel()


def find_clip(root):
    """SFM writes either a top-level channelsClip or nests it in animationList."""
    try:
        if "channelsClip" in root:
            return root["channelsClip"]
    except Exception:
        pass
    try:
        al = root.get("animationList")
        if al is not None:
            anims = al.get("animations")
            if anims:
                return anims[0]
    except Exception:
        pass
    return None


def _log_layer(channel):
    try:
        log = channel.get("log")
        if log is None:
            return None
        layers = log.get("layers")
        if not layers:
            return None
        return layers[0]
    except Exception:
        return None


def read_shot_bounds(clip, frame_for):
    """
    Shot ranges from ShotBoundsChannel, a DmeBoolLog whose value flips
    True while the shot is live. Returns [(frame_start, frame_end), ...].

    This is AUTHORITATIVE - SFM wrote it, we did not infer it from motion.
    Verified on the corpus: every camera export carries exactly one shot
    (3 keys: off just before, on, off at the end).
    """
    for ch in (clip.get("channels") or []):
        if (ch.name or "") != "ShotBoundsChannel":
            continue
        layer = _log_layer(ch)
        if layer is None:
            return []
        times = layer.get("times") or []
        values = layer.get("values") or []
        spans, open_at = [], None
        for t, v in zip(times, values):
            on = bool(float(v) >= 0.5)
            f = frame_for(t)
            if on and open_at is None:
                open_at = f
            elif not on and open_at is not None:
                spans.append((open_at, f))
                open_at = None
        if open_at is not None:
            spans.append((open_at, frame_for(times[-1])))
        return spans
    return []


def _deep_read_session(model, out):
    """
    Summarise a session: frame rate, duration, animation sets.

    Deliberately shallow - counts and names, never channel conversion - so
    analysing a folder of sessions stays fast. Session_Reader does the real
    work when someone actually wants the animation out.
    """
    root = model.root

    # Frame rate: renderSettings is the timeline, movieSettings can override
    # it for output. Same rule as Session_Reader.session_fps.
    try:
        settings = root.get("settings")
        if settings is not None:
            movie = settings.get("movieSettings")
            if (movie is not None and movie.get("IsOverridingFrameRate")
                    and movie.get("OverridingFrameRate")):
                out["fps"] = float(movie.get("OverridingFrameRate"))
            if out["fps"] is None:
                render = settings.get("renderSettings")
                if render is not None and render.get("frameRate"):
                    out["fps"] = float(render.get("frameRate"))
    except Exception:
        pass

    clip = root.get("activeClip")
    if clip is not None:
        try:
            tf = clip.get("timeFrame")
            if tf is not None:
                dur = float(tf.get("duration") or 0.0)
                out["time_duration"] = dur
                if out["fps"]:
                    out["frame_start"] = 0.0
                    out["frame_end"] = dur * out["fps"]
        except Exception:
            pass

    sets = [e for e in model.elements if e.type == "DmeAnimationSet"]
    out["sets"] = len(sets)
    models = []
    for a in sets:
        try:
            gm = a.get("gameModel")
            if gm is not None and gm.get("modelName"):
                models.append(str(gm.get("modelName")))
        except Exception:
            continue
    out["set_models"] = models

    counts = {}
    keys = 0
    for c in [e for e in model.elements if e.type == "DmeChannelsClip"]:
        for ch in (c.get("channels") or []):
            attr = ch.get("toAttribute") or ""
            counts[attr] = counts.get(attr, 0) + 1
            layer = _log_layer(ch)
            if layer is not None:
                times = layer.get("times")
                if times:
                    keys += len(times)
    out["counts"] = counts
    out["channels"] = sum(counts.values())
    out["keys"] = keys
    if counts.get("flexWeight"):
        out["kinds"].add(SHAPEKEY)
    if counts.get("fieldOfView"):
        out["kinds"].add(CAMERA)
    out["notes"].append(
        f"{len(sets)} animation set(s), {len(models)} with a game model")
    return out


def _deep_read(path, out):
    """Fill fps / frame range / channel census / names. Mutates *out*."""
    dm = _get_datamodel()
    model = dm.load(long_path(path))
    root = model.root
    out["deep"] = True
    out["root_type"] = getattr(root, "type", "")

    try:
        out["root_keys"] = sorted(root.keys())
    except Exception:
        out["root_keys"] = []

    # A session keeps its animation under activeClip rather than in an
    # animationList, so it gets its own summary instead of the single-clip
    # path below.
    if "activeClip" in out["root_keys"]:
        _deep_read_session(model, out)
        return

    clip = find_clip(root)
    if clip is None:
        # A model/reference DMX: skeleton and mesh, no channels.
        if "skeleton" in out["root_keys"] or "mesh" in out["marker_tags"]:
            out["kinds"].add(MODEL)
        return

    fps = clip.get("frameRate")
    out["fps"] = float(fps) if fps else None

    tf = clip.get("timeFrame")
    start = float(tf.get("start", 0)) if tf is not None else 0.0
    out["time_start"] = start
    if tf is not None and tf.get("duration") is not None:
        out["time_duration"] = float(tf.get("duration"))

    rate = out["fps"] or 30.0

    def frame_for(t):
        return (float(t) + start) * rate

    channels = clip.get("channels") or []
    out["channels"] = len(channels)

    counts = {}
    bones, flexes = [], []
    lo = hi = None

    for ch in channels:
        attr = ch.get("toAttribute") or ""
        counts[attr] = counts.get(attr, 0) + 1

        if attr == "flexWeight":
            to = ch.get("toElement")
            nm = None
            if to is not None:
                nm = to.get("name") or getattr(to, "name", None)
            if nm and len(flexes) < 512:
                flexes.append(str(nm))
        elif attr in ("position", "orientation"):
            to = ch.get("toElement")
            nm = getattr(to, "name", None) if to is not None else None
            # "unnamed" is the game-model root channel's target, not a bone.
            if (nm and nm != "unnamed" and attr == "position"
                    and len(bones) < 512):
                bones.append(str(nm))

        if (ch.name or "") == "ShotBoundsChannel":
            continue
        layer = _log_layer(ch)
        if layer is None:
            continue
        times = layer.get("times")
        if not times:
            continue
        a, b = frame_for(times[0]), frame_for(times[-1])
        lo = a if lo is None else min(lo, a)
        hi = b if hi is None else max(hi, b)

    out["counts"] = counts
    out["bones"] = bones
    out["flexes"] = flexes
    out["frame_start"] = lo
    out["frame_end"] = hi
    out["shot_bounds"] = read_shot_bounds(clip, frame_for)

    # Sub-frame drift: SFM exports land on 4.0008 / 4.9992 / 6.0000 rather
    # than clean integers. The splitter and the FPS check both care.
    if lo is not None:
        drift = max(abs(v - round(v)) for v in (lo, hi))
        out["subframe_drift"] = drift
        if drift > 0.002:
            out["notes"].append(
                f"keys are off-frame by up to {drift:.4f} of a frame")

    # A rest pose is not an animation. Reference DMX files carry a full
    # channel set whose logs each hold a single key, so the whole frame span
    # collapses to zero. Importing one as animation yields a frame of nothing,
    # so call it what it is.
    static = (lo is not None and hi is not None and abs(hi - lo) < 1e-6)
    out["static"] = static

    # ...unless WE wrote it, out of a session. A session extract of a STATIC
    # PROP also holds one key per channel, and by the rule above that made it a
    # "reference / rest pose" - so the animation step ignored it and the prop
    # never received its rootTransform. It then sat at the world origin
    # unrotated while every character around it got the SFM -> Blender map. In
    # `new session.dmx` that was `pit_a1`: the ground the whole shot stands on,
    # 90 degrees out from the six characters standing on it.
    #
    # A rest pose has no placement to apply. A placed prop does. Who wrote the
    # file tells them apart unambiguously.
    session_extract = False
    try:
        tags = root.get("exportTags")
        if tags is not None:
            session_extract = "session extract" in str(tags.get("app") or "").lower()
    except Exception:
        pass
    out["session_extract"] = session_extract

    if static:
        # The deep pass outranks the fast one. The fast scan saw unnamed_p
        # and flexWeight tokens and guessed ANIMATION / SHAPEKEY; now that
        # the logs are decoded and every one holds a single key, those
        # guesses are wrong and get withdrawn rather than sitting alongside
        # the truth.
        out["kinds"].discard(SHAPEKEY)
        out["kinds"].add(MODEL)
        if session_extract and (counts.get("position") or counts.get("orientation")):
            out["kinds"].add(ANIMATION)
            out["notes"].append(
                "one key per channel, but this is a session extract - a "
                "PLACED PROP, imported so it receives its rootTransform")
        else:
            out["kinds"].discard(ANIMATION)
            out["notes"].append(
                "every channel holds one key - reference / rest pose, "
                "not an animation")

    # ── Kinds implied by what the channels actually target ────────────────
    if counts.get("flexWeight") and not static:
        out["kinds"].add(SHAPEKEY)

    if counts.get("fieldOfView") or "camera" in out["root_keys"]:
        out["kinds"].add(CAMERA)
        cam = root.get("camera") if "camera" in out["root_keys"] else None
        if cam is not None:
            out["camera_name"] = getattr(cam, "name", None)
            fov = cam.get("fieldOfView")
            if fov is not None:
                out["camera_fov"] = float(fov)

    if not static and (counts.get("position") or counts.get("orientation")):
        # A camera export also carries one position + one orientation
        # channel; a real animation has them per bone. Two is the camera.
        if (counts.get("position", 0) + counts.get("orientation", 0)) > 2:
            out["kinds"].add(ANIMATION)
        elif CAMERA not in out["kinds"]:
            out["kinds"].add(ANIMATION)


# ─────────────────────────────────────────────────────────────────────────────
#  Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def blank(path):
    return {
        "path": str(path),
        "name": Path(path).name,
        "size": 0,
        "ok": False,
        "error": None,
        "encoding": None,
        "encoding_ver": None,
        "format": None,
        "format_ver": None,
        "kinds": set(),
        "marker_tags": set(),
        "deep": False,
        "deep_skipped": None,
        "root_type": "",
        "root_keys": [],
        "fps": None,
        "time_start": None,
        "time_duration": None,
        "frame_start": None,
        "frame_end": None,
        "subframe_drift": None,
        "static": False,
        "sets": 0,
        "set_models": [],
        "keys": 0,
        "shot_bounds": [],
        "channels": 0,
        "counts": {},
        "bones": [],
        "flexes": [],
        "camera_name": None,
        "camera_fov": None,
        "notes": [],
    }


def analyze(path, deep="auto"):
    """
    Inspect one DMX and report what it holds.

    deep : True | False | "auto"
        "auto" runs the deep pass for everything except sessions and
        oversized files. See want_deep().

    Never raises for a readable file - a failed deep pass degrades to the
    fast result with the error recorded in out["error"].
    """
    path = Path(path)
    out = blank(path)

    if not os.path.exists(long_path(path)):
        out["error"] = "file not found"
        return out
    try:
        out["size"] = os.path.getsize(long_path(path))
    except OSError:
        pass

    hdr = read_header(path)
    if hdr is None:
        out["error"] = "not a DMX file (no encoding header)"
        return out
    out["encoding"], out["encoding_ver"], out["format"], out["format_ver"] = hdr
    out["ok"] = True

    tags = scan_markers(path)
    out["marker_tags"] = tags

    # ── Kinds from the fast pass ──────────────────────────────────────────
    fmt = out["format"] or ""
    if fmt.startswith("sfm_session") or "film_clip" in tags:
        out["kinds"].add(SESSION)
    if "flex" in tags:
        out["kinds"].add(SHAPEKEY)
    if "fov" in tags or "camera_elem" in tags:
        out["kinds"].add(CAMERA)
    if "proj_light" in tags or "light" in tags:
        out["kinds"].add(LIGHT)
    if "mesh" in tags and "channel" not in tags:
        out["kinds"].add(MODEL)
    if ("root_pos" in tags or "root_rot" in tags) and SESSION not in out["kinds"]:
        out["kinds"].add(ANIMATION)

    # ── Deep pass ─────────────────────────────────────────────────────────
    run_deep = deep is True or (deep == "auto" and want_deep(path, fmt))
    if not run_deep:
        out["deep_skipped"] = f"file over {DEEP_SIZE_LIMIT // (1024*1024)} MB"
        return out

    try:
        _deep_read(path, out)
    except Exception as exc:
        out["error"] = f"deep read failed: {type(exc).__name__}: {exc}"
        out["notes"].append("fell back to the fast scan")

    if not out["kinds"]:
        out["kinds"].add(MODEL)
    return out


def analyze_many(paths, deep="auto"):
    return [analyze(p, deep=deep) for p in paths]


# ─────────────────────────────────────────────────────────────────────────────
#  Router
# ─────────────────────────────────────────────────────────────────────────────

def kinds_sorted(analysis):
    return [k for k in KIND_ORDER if k in analysis["kinds"]]


def route(analysis):
    """
    What should run for this file, in the order it should run.

    Returns [(kind, operator_idname_or_None, label), ...]. The Session
    Importer uses this to decide which standalone module to call; the
    Analyze DMX operator uses it to offer the user the right buttons.
    """
    out = []
    for kind in kinds_sorted(analysis):
        op, label = KIND_OPERATOR.get(kind, (None, kind))
        out.append((kind, op, label))
    return out


def summary_line(analysis):
    if not analysis["ok"]:
        return f"{analysis['name']}: {analysis['error']}"
    kinds = kinds_sorted(analysis)
    tail = ", ".join(KIND_LABEL[k] for k in kinds) or "nothing recognised"
    fps = f"  {analysis['fps']:g} fps" if analysis["fps"] else ""
    return f"{analysis['name']}: {tail}{fps}"


def report_lines(analysis):
    """Multi-line human report - console dump and the operator popup."""
    a = analysis
    L = [f"{a['name']}   {a['size'] / 1024:.0f} KB"]
    if not a["ok"]:
        L.append(f"  ERROR: {a['error']}")
        return L
    L.append(f"  encoding : {a['encoding']} {a['encoding_ver']}"
             f"   format: {a['format']} {a['format_ver']}")
    kinds = kinds_sorted(a)
    L.append("  contains : " + (", ".join(KIND_LABEL[k] for k in kinds)
                                or "nothing recognised"))
    if a["deep"]:
        if a["fps"]:
            L.append(f"  fps      : {a['fps']:g}")
        if a["frame_start"] is not None:
            L.append(f"  frames   : {a['frame_start']:.2f} .. {a['frame_end']:.2f}")
        if a["shot_bounds"]:
            spans = ", ".join(f"{s:.0f}-{e:.0f}" for s, e in a["shot_bounds"])
            L.append(f"  shots    : {len(a['shot_bounds'])}  [{spans}]")
        if a["sets"]:
            L.append(f"  sets     : {a['sets']} animation set(s)")
            for m in a["set_models"][:4]:
                L.append(f"             {m}")
            if len(a["set_models"]) > 4:
                L.append(f"             ... and "
                         f"{len(a['set_models']) - 4} more model(s)")
        if a["channels"]:
            L.append(f"  channels : {a['channels']}"
                     + (f", {a['keys']} key(s)" if a["keys"] else ""))
            top = sorted(a["counts"].items(), key=lambda kv: -kv[1])[:6]
            L.append("             " + ", ".join(
                f"{k or '(none)'}={v}" for k, v in top))
        if a["bones"]:
            L.append(f"  bones    : {len(a['bones'])}"
                     f"  e.g. {', '.join(a['bones'][:4])}")
        if a["flexes"]:
            L.append(f"  flexes   : {len(a['flexes'])}"
                     f"  e.g. {', '.join(a['flexes'][:4])}")
        if a["camera_name"]:
            fov = f", fov {a['camera_fov']:g}" if a["camera_fov"] else ""
            L.append(f"  camera   : {a['camera_name']}{fov}")
    else:
        L.append(f"  detail   : fast scan only ({a['deep_skipped']})")
    if a["error"]:
        L.append(f"  warning  : {a['error']}")
    for n in a["notes"]:
        L.append(f"  note     : {n}")
    return L


# ─────────────────────────────────────────────────────────────────────────────
#  Operator  -  Analyze DMX                                        [roadmap #6]
# ─────────────────────────────────────────────────────────────────────────────

import bpy
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, CollectionProperty
from bpy_extras.io_utils import ImportHelper


_ht_icon_id = None


def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


class HT_OT_analyze_dmx(Operator, ImportHelper):
    """PICK .dmx (any kind, multi-select allowed) - session, animation, camera
        or flex; it works out which and reads it without importing

        Report what a DMX file actually contains, before importing it

Two passes. A fast one reads the header and scans the raw bytes for
marker strings - about 4 ms even on a large session, and it never parses.
A deep one builds the element graph and reports channels, key counts,
frame rate and time span.

It answers the questions that decide what to do next: is this an
animation, a camera, a model or a whole session; is its encoding one the
reader understands or does it need dmxconvert first; how many keys are
off a whole frame.

For a single file it also offers to route it straight to the right
importer. Pick several files at once to triage a folder"""
    bl_idname = "ht.analyze_dmx"
    bl_label = "Analyze DMX"
    bl_options = {"REGISTER"}

    filename_ext = ".dmx"
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement,
                              options={"HIDDEN", "SKIP_SAVE"})  # type: ignore
    directory: StringProperty(subtype="DIR_PATH", options={"HIDDEN"})  # type: ignore

    force_deep: BoolProperty(  # type: ignore
        name="Force Full Read",
        description=("Load the file properly even when the fast scan would do. "
                     "Gives FPS, frame range and the channel census for any "
                     "file - but a session can take a minute, and Blender is "
                     "frozen while it works"),
        default=False,
    )

    def draw(self, context):
        self.layout.prop(self, "force_deep")

    def execute(self, context):
        from pathlib import Path
        paths = []
        if self.files and self.directory:
            for f in self.files:
                if f.name:
                    paths.append(Path(self.directory) / f.name)
        if not paths and self.filepath:
            paths = [Path(self.filepath)]
        if not paths:
            self.report({"WARNING"}, "No file selected")
            return {"CANCELLED"}

        deep = True if self.force_deep else "auto"
        results = [analyze(p, deep=deep) for p in paths]

        print()
        for a in results:
            for line in report_lines(a):
                print(f"[DMX_ANALYZE]  {line}")
            print(f"[DMX_ANALYZE]    route: "
                  f"{[k for k, _op, _l in route(a)] or 'nothing'}")

        self._results = results
        if len(results) == 1:
            a = results[0]
            if not a["ok"]:
                self.report({"ERROR"}, f"{a['name']}: {a['error']}")
                return {"CANCELLED"}
            self.report({"INFO"}, summary_line(a))
        else:
            hist = {}
            for a in results:
                for k in kinds_sorted(a):
                    hist[k] = hist.get(k, 0) + 1
            self.report({"INFO"}, f"{len(results)} file(s): " + ", ".join(
                f"{KIND_LABEL[k]} {v}" for k, v in hist.items()) or "nothing")

        def popup(layout, ctx):
            col = layout.column(align=True)
            for a in results[:12]:
                for line in report_lines(a):
                    col.label(text=line)
                if len(results) > 1:
                    col.separator()
            if len(results) > 12:
                col.label(text=f"... and {len(results) - 12} more, see console")
            if len(results) == 1:
                col.separator()
                col.label(text="Route:")
                for kind, op, label in route(results[0]):
                    row = col.row(align=True)
                    if op:
                        row.operator(op, text=label, icon=KIND_ICON[kind])
                    else:
                        row.enabled = False
                        row.label(text=label, icon=KIND_ICON[kind])

        #  This is the ONE popup that is not just text - a single-file
        #  analysis offers "route it to..." buttons, and losing those would
        #  turn the analyzer back into a thing you read and then act on by
        #  hand. Report_UI takes the draw callback as `body_draw`; the plain
        #  lines below are what the console and the coloured bar get.
        flat = []
        for a in results[:12]:
            flat.extend(report_lines(a))
        from . import Report_UI
        Report_UI.report(
            context, "dmx_analyzer", "DMX Analysis", flat,
            level=('ERROR' if any(not a["ok"] for a in results) else 'INFO'),
            icon='VIEWZOOM', prefix="DMX_ANALYZE", operator=self,
            summary=(summary_line(results[0]) if len(results) == 1
                     else f"DMX Analysis - {len(results)} file(s)"),
            body_draw=popup)
        return {"FINISHED"}


def draw_menu_item(layout):
    layout.operator(HT_OT_analyze_dmx.bl_idname, text="Analyze DMX",
                    **_icon_id("analyze_dmx", 'VIEWZOOM'))


_CLASSES = (HT_OT_analyze_dmx,)


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
