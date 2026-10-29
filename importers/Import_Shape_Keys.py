"""
Import_Shape_Keys.py  —  part of HoovyTools
============================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Shape Keys (Flex DMX)

No dependency on Blender Source Tools (io_scene_valvesource).
Uses the bundled HoovyTools/SST/datamodel.py.

PUBLIC API  — four standalone functions
────────────────────────────────────────
    from . import Import_Shape_Keys

    # 1. Strip shape key drivers
    removed = Import_Shape_Keys.remove_shapekey_drivers(obj)

    # 2. Stereo-split 'L' keys → L + R pairs
    created = Import_Shape_Keys.stereo_split(obj)

    # 3. Import flex animation from a DMX
    result  = Import_Shape_Keys.import_flex_dmx(dmx_path, obj)
    # → {"channels": int, "max_frame": float, "frame_rate": int}

    # 4. Bake HWM flex controllers → localvar shape keys
    result  = Import_Shape_Keys.bake_hwm_localvars(obj, qc_path)
    # → {"ok": bool, "baked": int, "keys": int, ...}

The orchestrator import_shape_keys() calls these 4 in sequence.
Old private names (_remove_shapekey_drivers, _stereo_split, run_hwm_bake)
are preserved as aliases so existing callers keep working.
"""

bl_info = {
    "name":        "HoovyTools: Import Shape Keys (Flex DMX)",
    "description": "Import SFM flex DMX animation + optional HWM localvar bake (no BST required)",
    "author":      "HoovyTools",
    "version":     (2, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > Shape Keys (Flex DMX)",
    "category":    "Import-Export",
}

import bpy
from ..core import paths as _ht_paths
from ..core import paths as _paths
import re as _re
import ast as _ast
import time
from math import ceil
from pathlib import Path
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper

from ..core import start_folders
from ..core.anim_compat import make_action, get_channelbag, fc_find_or_new, iter_fcurves, count_fcurves


# ──────────────────────────────────────────────────────────────────────────────
# config
# ──────────────────────────────────────────────────────────────────────────────

# The PARENT, not the folder: `_sfm_qc_folder()` runs the underscore ladder
# over it so `_QC Face Data` and `QC Face Data` are both found. The folder in
# the SFM tree was renamed to match the add-on's convention; anyone still
# holding the bare-named one keeps working
_QC_SFM_PARENT = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\SourceFilmmaker"
    r"\game\usermod\plugins\___SFM to Blender Session Importer\_Dev"
)

REMOVE_PREVIOUS_ANIMATION    = True
DETECT_HWM                   = True
HWM_PREFIX_MIN               = 10
HWM_LEFT_PREFIX              = "left_"
HWM_RIGHT_PREFIX             = "right_"

MAX_LOCALVARS                = 1255
ACTION_NAME                  = "HT_Flexcontroller_to_Localvar_BAKE"
LOCALVAR_SLIDER_MIN          = -10.0
LOCALVAR_SLIDER_MAX          =  10.0
CLAMP_LOCALVAR_0_1           = False
SMART_SHAPE_KEYS             = True
CLEAN_ADD                    = True
STORE_ANIMATION              = True
REPLACE_EXISTING_BAKE_ACTION = True

_STEREO_L_SUFFIX   = "L"
_STEREO_R_SUFFIX   = "R"
_STEREO_BLEED      = 0.10
_STEREO_AXIS       = 0
_STEREO_THRESHOLD  = 10
_STEREO_SLIDER_MIN = -10.0
_STEREO_SLIDER_MAX =  10.0


# ──────────────────────────────────────────────────────────────────────────────
# icon helper
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
# qc folder resolution
# ──────────────────────────────────────────────────────────────────────────────

def _addon_qc_folder() -> Path:
    """The QC set that ships inside the add-on - `_QC Face Data`."""
    return _paths.qc_face_data()


def _override_qc_folder() -> Path | None:
    """The user's own QC folder from add-on preferences, or None.

    WHY THIS IS A PREFERENCE AND NOT A README LINE. The shipped set is twelve
    TF2 QCs. A session built on any other character needs its QC added, and
    the only place to put it used to be INSIDE the installed add-on - which
    means the next update silently takes it away again. An override folder
    outside the add-on survives updates, and being searched first means one
    added file overrides one shipped file without displacing the other eleven.
    """
    try:
        prefs = _ht_paths.addon_prefs()
    except (KeyError, AttributeError):
        return None
    raw = (getattr(prefs, "qc_face_data_path", "") or "").strip()
    if not raw:
        return None
    p = Path(bpy.path.abspath(raw))
    return p if p.is_dir() else None


def _sfm_qc_folder() -> Path:
    """The QC copy in the SFM plugins tree, underscored or not."""
    return _paths.data_dir_at(_QC_SFM_PARENT, "QC Face Data")


def _qc_search_folders() -> list:
    """Every folder that may hold a .qc, in priority order:

      1. The preferences override - first, so it can beat a shipped file.
      2. The two folders the user added in the wiring section.
      3. The add-on's own `_QC Face Data`.
      4. The SFM-side `_Dev/_QC Face Data`, in every configured install.
      5. 3.0.0: the QCs written from imported models (`_QC Face Data/_Generated`, or Blender's config folder when
         the add-on is read-only) - LAST, so any hand-made QC of the same name wins.

    Only existing folders come back.
    """
    from ..core import user_paths as _user_paths
    from ..session.Import_Session import usermod_bases
    ladder = ([_override_qc_folder()]
              + _user_paths.folders("qc_face_data")
              + [_addon_qc_folder(), _sfm_qc_folder()]
              # The SFM-side copy inside every install. Someone running two
              # SFMs has two of these and only one was ever looked at
              + [_paths.data_dir_at(b / "plugins"
                                    / "___SFM to Blender Session Importer"
                                    / "_Dev", "QC Face Data")
                 for b in usermod_bases()]
              + _generated_qc_folders())
    out = []
    for f in ladder:
        if f is not None and f.is_dir() and f not in out:
            out.append(f)
    return out


def _generated_qc_folders() -> list:
    """Where ensure_face_qc() writes - existing or not (the ladder keeps only folders that exist)."""
    return [_paths.qc_face_data() / _paths.QC_GENERATED_NAME, _paths._config_qc_dir()]


def ensure_face_qc(mdl_path, objects=None):
    """3.0.0. The model's face data as a .qc the HWM bake reads.

    Stamps every armature in `objects` with `ht_mdl_path`, so the bake can find the model later. Then: a hand-made
    `<model>.qc` in any QC folder wins and nothing is written; otherwise core/mdl_flex reads the controllers, the
    rules, the stereo pairs and the eyelids out of the .mdl into `_Generated/<model>.qc` - rewritten only when the
    model changed.

    Returns (QC path or None, note, state) - state: wrote / current / handmade / none / error."""
    from ..core import mdl_flex
    mdl_path = Path(mdl_path)
    for o in (objects or ()):
        if getattr(o, "type", "") == "ARMATURE":
            try:
                o["ht_mdl_path"] = str(mdl_path)
            except Exception:                                 # noqa: BLE001
                pass
    generated = {d for d in _generated_qc_folders() if d is not None}
    for folder in _qc_search_folders():
        if folder in generated:
            continue
        hit = folder / (mdl_path.stem + ".qc")
        if hit.is_file():
            return hit, f"{hit.name} from {folder.name}", "handmade"
    if not mdl_path.is_file():
        return None, f"{mdl_path.name} is not on disk ({mdl_path})", "error"
    out = _paths.qc_generated(create=True)
    if out is None:
        return None, "no writable folder for the generated QC files", "error"
    try:
        path, counts, note = mdl_flex.write_qc(mdl_path, out)
    except mdl_flex.MdlFlexError as exc:
        return None, str(exc), "error"
    except Exception as exc:                                  # noqa: BLE001
        return None, f"could not read the face data of {mdl_path.name} ({mdl_path}): {exc}", "error"
    if path is None:
        return None, note, "none"
    return path, note, ("wrote" if counts is not None else "current")


# ──────────────────────────────────────────────────────────────────────────────
# function 1 — remove shape key drivers
# ──────────────────────────────────────────────────────────────────────────────

def remove_shapekey_drivers(obj) -> int:
    """
    Remove all shape-key value drivers from *obj*.
    Returns the number removed.
    """
    sk = obj.data.shape_keys
    if not sk or not sk.animation_data:
        return 0
    ad      = sk.animation_data
    removed = 0
    for fc in list(ad.drivers):
        if fc.data_path.startswith('key_blocks["') and fc.data_path.endswith('"].value'):
            try:
                sk.driver_remove(fc.data_path, fc.array_index)
            except TypeError:
                sk.driver_remove(fc.data_path)
            removed += 1
    for fc in list(getattr(ad, "drivers", [])):
        try:
            ad.drivers.remove(fc)
            removed += 1
        except Exception:
            pass
    return removed

_remove_shapekey_drivers = remove_shapekey_drivers   # legacy alias


# ──────────────────────────────────────────────────────────────────────────────
# FUNCTION 2 — STEREO SPLIT  (L → L + R)
# ──────────────────────────────────────────────────────────────────────────────

def stereo_split(obj) -> int:
    """
    For every shape key ending with capital 'L', create a matching 'R' key
    weighted by vertex X-position. Runs only when L-key count > _STEREO_THRESHOLD.
    Returns number of R keys created.
    """
    sk = obj.data.shape_keys
    if not sk:
        return 0

    l_keys = [kb for kb in sk.key_blocks
              if kb.name != "Basis" and kb.name.endswith(_STEREO_L_SUFFIX)]
    if len(l_keys) <= _STEREO_THRESHOLD:
        return 0

    mesh    = obj.data
    n_verts = len(mesh.vertices)
    xs      = [v.co[_STEREO_AXIS] for v in mesh.vertices]
    x_min   = min(xs)
    x_range = (max(xs) - x_min) or 1.0

    created = 0
    for l_kb in l_keys:
        r_name = l_kb.name[:-len(_STEREO_L_SUFFIX)] + _STEREO_R_SUFFIX
        if r_name in sk.key_blocks:
            continue

        r_kb = obj.shape_key_add(name=r_name, from_mix=False)

        for i in range(n_verts):
            x_norm = (xs[i] - x_min) / x_range
            delta  = l_kb.data[i].co - mesh.vertices[i].co

            # smooth 50/50 split centered at x_norm=0.5, transition width = 2*BLEED
            # R: 0 on left side, 1 on right side
            # L: mirror of R — l_blend + r_blend always = 1.0
            t       = (x_norm - (0.5 - _STEREO_BLEED)) / (2.0 * _STEREO_BLEED)
            r_blend = max(0.0, min(1.0, t))
            l_blend = 1.0 - r_blend

            r_kb.data[i].co = mesh.vertices[i].co + delta * r_blend
            l_kb.data[i].co = mesh.vertices[i].co + delta * l_blend

        l_kb.slider_min = _STEREO_SLIDER_MIN
        l_kb.slider_max = _STEREO_SLIDER_MAX
        r_kb.slider_min = _STEREO_SLIDER_MIN
        r_kb.slider_max = _STEREO_SLIDER_MAX

        # Move R key immediately after L in the stack
        l_idx = list(sk.key_blocks).index(l_kb)
        r_idx = len(sk.key_blocks) - 1
        for _ in range(r_idx - l_idx - 1):
            bpy.context.view_layer.objects.active = obj
            obj.active_shape_key_index = len(sk.key_blocks) - 1
            bpy.ops.object.shape_key_move(type="UP")

        created += 1

    return created

_stereo_split = stereo_split   # legacy alias


# ──────────────────────────────────────────────────────────────────────────────
# FUNCTION 3 — IMPORT FLEX DMX
# ──────────────────────────────────────────────────────────────────────────────

def _clear_previous_flex_animation(obj) -> int:
    sk = obj.data.shape_keys
    if not sk:
        return 0
    cleared = 0
    if sk.animation_data and sk.animation_data.action:
        action = sk.animation_data.action
        bag = get_channelbag(action, sk)
        for fc in list(bag.fcurves):
            if fc.data_path.endswith(".value"):
                bag.fcurves.remove(fc)
                cleared += 1
    for kb in sk.key_blocks:
        kb.value = 0.0
    return cleared


def _parse_flex_channels(dmx_path: Path) -> tuple:
    """Returns (frame_rate, start, channels_list). Uses bundled SST/datamodel.

    *start* is the timeFrame.start offset in seconds — identical to the value
    Import_DMX_Animation uses so that flex keyframes land on the same frames as
    bone keyframes when both come from the same SFM session.
    """
    from ..SST import get_datamodel
    dm    = get_datamodel()
    model = dm.load(str(dmx_path))

    frame_rate = 30
    start      = 0.0
    try:
        anim_list = model.root.get("animationList")
        if anim_list:
            anims = anim_list.get("animations")
            if anims:
                anim       = anims[0]
                frame_rate = anim.get("frameRate", 30)
                time_frame = anim.get("timeFrame")
                if time_frame is not None:
                    start = float(
                        time_frame.get("start") or
                        time_frame.get("offsetTime") or 0
                    )
    except Exception:
        pass

    channels = []
    for elem in model.elements:
        if elem.type != "DmeChannel":
            continue
        if elem.get("toAttribute") != "flexWeight":
            continue
        to_element = elem.get("toElement")
        if not to_element:
            continue
        flex_name = to_element.get("name") or to_element.name
        if not flex_name:
            continue
        log_elem = elem.get("log")
        if not log_elem:
            continue
        layers = log_elem.get("layers")
        if not layers:
            continue
        layer  = layers[0]
        times  = layer.get("times")
        values = layer.get("values")
        if not times or not values or len(times) != len(values):
            continue
        channels.append({"flex_name": flex_name,
                         "times":     list(times),
                         "values":    list(values)})
    return frame_rate, start, channels


def _build_shape_key_animation(obj, frame_rate: int, channels: list,
                               start: float = 0.0) -> tuple:
    """Returns (imported_count, max_frame, min_frame).

    *start* is the timeFrame.start offset in seconds (same as Import_DMX_Animation).
    Frame number = (time + start) * frame_rate.
    """
    sk = obj.data.shape_keys
    if not sk:
        obj.shape_key_add(name="Basis", from_mix=False)
        sk = obj.data.shape_keys

    if not sk.animation_data:
        sk.animation_data_create()
    if not sk.animation_data.action:
        _, _ = make_action(f"FlexAnim_{obj.name}", sk)

    action    = sk.animation_data.action
    bag       = get_channelbag(action, sk)
    imported  = 0
    max_frame = 0.0
    min_frame = None

    for ch in channels:
        flex_name = ch["flex_name"]
        times     = ch["times"]
        values    = ch["values"]

        if flex_name not in sk.key_blocks:
            obj.shape_key_add(name=flex_name, from_mix=False)

        shape_key       = sk.key_blocks[flex_name]
        shape_key.value = 0.0
        data_path = shape_key.path_from_id("value")
        fcurve    = fc_find_or_new(bag, data_path)

        kf_data = []
        for t, v in zip(times, values):
            frame = (float(t) + start) * frame_rate
            kf_data.append((frame, float(v)))
            if min_frame is None or frame < min_frame:
                min_frame = frame
            max_frame = max(max_frame, frame)

        kps = fcurve.keyframe_points
        kps.add(len(kf_data))
        for i, (frame, val) in enumerate(kf_data):
            kps[i].co            = (frame, val)
            kps[i].interpolation = "LINEAR"
        kps.update()
        imported += 1

    return imported, max_frame, min_frame


def _shift_to_frame_1(action, current_min: float) -> float:
    if current_min is None:
        return 0.0
    offset = 1.0 - current_min
    if offset == 0.0:
        return 0.0
    for fc in iter_fcurves(action):
        for kp in fc.keyframe_points:
            kp.co.x += offset
        fc.keyframe_points.update()
    return offset


def fix_flex_stepped_keys(obj, mode='AUTO'):
    """Give facial animation the same stepped-key treatment as bone animation.

    THE BUG THIS FIXES
    ------------------
    Reported: "GMAN begins with a stepped shape key, which loads as a
    3 frame tween on my end."

    Flex channels are written at the raw SFM key time,
    `(t + start) * frame_rate`, with LINEAR interpolation and - until now - no
    stepped-key handling of any kind. That is the exact problem the bone
    importer already solves:

      * SFM keys almost nothing on a whole frame;
      * it writes a HOLD as a PAIR of keys about 0.002 of a frame apart.

    Blender only ever EVALUATES whole frames. A step written at 3.9992 ->
    4.0008 is therefore sampled halfway, and with the neighbouring keys also
    off-frame the instant change reads as a soft ramp across about three
    frames. That is not a rounding artefact, it is the step being sampled
    everywhere except where it happens.

    Resampling onto whole frames turns it back into a one-frame change, which
    is as close to instant as a frame-based system can be - and is exactly
    what `Import_DMX_Animation` does for bones and `Import_DMX_Camera` does
    for cuts. The three now agree instead of two out of three.

    MUST RUN BEFORE THE HWM BAKE. The baker READS these curves and samples
    them per integer frame; if it reads them while they are still smeared, it
    bakes the smear into the localvar output and no later pass can recover it.
    """
    from . import Import_DMX_Animation as IDA
    sk = obj.data.shape_keys if obj.data else None
    ad = sk.animation_data if sk else None
    action = ad.action if ad else None
    if action is None:
        return {"curves": 0, "stepped_curves": 0, "resampled_curves": 0,
                "keys_before": 0, "keys_after": 0, "snapped": 0, "steps": 0}
    return IDA.fix_stepped_keys(action, sk, mode=mode)


def import_flex_dmx(dmx_path, obj, stepped_keys='AUTO') -> dict:
    """
    Parse a flex DMX and write F-curves onto *obj*'s shape keys.

    Does NOT remove drivers, run stereo split, or bake HWM.
    Call the other three functions explicitly if needed.

    Returns {"channels": int, "max_frame": float, "frame_rate": int}
    """
    dmx_path = Path(dmx_path)
    if not dmx_path.exists():
        raise FileNotFoundError(f"DMX not found: {dmx_path}")
    if obj.type != "MESH":
        raise TypeError(f"Expected MESH, got '{obj.type}'")

    if REMOVE_PREVIOUS_ANIMATION:
        _clear_previous_flex_animation(obj)

    frame_rate, start, channels = _parse_flex_channels(dmx_path)
    if not channels:
        raise ValueError(f"No flexWeight channels in {dmx_path.name}")

    imported, max_frame, _ = _build_shape_key_animation(obj, frame_rate, channels, start)

    #straight after the curves exist and before anything reads them.
    stepped = {"steps": 0, "resampled_curves": 0, "snapped": 0}
    if stepped_keys != 'OFF':
        try:
            stepped = fix_flex_stepped_keys(obj, mode=stepped_keys)
            if stepped["resampled_curves"]:
                print(f"[SHAPEKEYS]  stepped: {stepped['steps']} step(s) across "
                      f"{stepped['stepped_curves']} curve(s); resampled "
                      f"{stepped['resampled_curves']} onto whole frames "
                      f"({stepped['keys_before']} -> {stepped['keys_after']} "
                      f"keys); {stepped['snapped']} snapped")
            else:
                print(f"[SHAPEKEYS]  stepped: none detected; "
                      f"{stepped['snapped']} key(s) snapped to whole frames")
        except Exception as exc:
            print(f"[SHAPEKEYS]  stepped-key WARNING: {exc}")

    if max_frame > bpy.context.scene.frame_end:
        bpy.context.scene.frame_end = int(ceil(max_frame))

    return {"channels": imported, "max_frame": max_frame,
            "frame_rate": frame_rate, "stepped": stepped}


# ──────────────────────────────────────────────────────────────────────────────
# function 4 — bake hwm localvars
# ──────────────────────────────────────────────────────────────────────────────

# ── rig helpers ───────────────────────────────────────────────────────────────

_ARM_DATA_RE = _re.compile(r'_arm_data.*$', _re.IGNORECASE)

def _get_base_rig_name(obj) -> str | None:
    for mod in obj.modifiers:
        if mod.type == "ARMATURE" and mod.object:
            return _ARM_DATA_RE.sub("", mod.object.data.name).strip()
    if obj.parent and obj.parent.type == "ARMATURE":
        return _ARM_DATA_RE.sub("", obj.parent.data.name).strip()
    return None

def _armature_of(obj):
    for mod in obj.modifiers:
        if mod.type == "ARMATURE" and mod.object:
            return mod.object
    if obj.parent and obj.parent.type == "ARMATURE":
        return obj.parent
    return None


def _find_qc_for_mesh(obj):
    """(base name, QC path or None) for a face mesh. By name first, as always; 3.0.0: when no QC carries the rig's
    name, the model the rig was imported from (`ht_mdl_path`) writes one - the bake runs on any model."""
    base_name = _get_base_rig_name(obj)
    qc_path = _find_qc_for_rig(base_name) if base_name else None
    if qc_path is None:
        arm = _armature_of(obj)
        mdl = arm.get("ht_mdl_path") if arm is not None else None
        if mdl:
            qc_path, note, _state = ensure_face_qc(mdl)
            print(f"[SHAPE_KEYS]  QC for '{base_name}': {note}")
    return base_name, qc_path


def _find_qc_for_rig(base_name: str) -> Path | None:
    """
    The QC face-data file for a rig, tolerant of SFM's naming.

    The name handed in comes from the armature, and a rig imported from a
    session is called `scout1` - SFM appends an INSTANCE NUMBER - so an exact
    match looks for `scout1.qc` and finds nothing. That is why the HWM bake
    silently did nothing on every session import: "Baker skipped - no QC for
    'scout1'". Same candidate ladder the rig fixer uses, so the two cannot
    disagree about what a rig is called.

    ALL THREE FOLDERS ARE SEARCHED, EARLIEST WINS. `_qc_search_folders()` has
    existed for as long as this function has, and this function ignored it and
    read the add-on's folder directly - so the SFM-side copy was dead code and
    there was nowhere to put a QC of your own. Building ONE table across the
    folders in priority order, with `setdefault`, means an override file beats
    a shipped file of the same name while every name the override does not
    mention still resolves.
    """
    folders = _qc_search_folders()
    if not folders or not base_name:
        return None

    available = {}
    for folder in folders:
        for f in sorted(folder.iterdir()):
            if f.suffix.lower() == ".qc":
                available.setdefault(f.stem.lower(), f)

    try:
        from ..session.Import_Session import _name_candidates
        candidates = _name_candidates(base_name)
    except Exception:
        candidates = [base_name]

    for c in candidates:
        hit = available.get(c.lower())
        if hit is not None:
            if c.lower() != base_name.lower():
                print(f"[SHAPE_KEYS]  QC '{base_name}' -> {hit.name}")
            return hit

    # longest QC stem that prefixes a candidate, so scout_toga is never
    # satisfied by scout
    best, best_len = None, 0
    for c in candidates:
        cl = c.lower()
        for stem, path in available.items():
            if cl.startswith(stem) and len(stem) > best_len:
                best, best_len = path, len(stem)
    if best is not None:
        print(f"[SHAPE_KEYS]  QC '{base_name}' -> {best.name} (prefix match)")
    return best

# ── safe expression evaluator ─────────────────────────────────────────────────
# Proper recursive evaluator — ported from the reference baker (safer than
# eval(compile(...)) because it never reaches Python's built-in eval path).

_ALLOWED_FUNCS = {"min": min, "max": max}
_ALLOWED_NODES = (
    _ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Call,
    _ast.Name, _ast.Load, _ast.Constant,
    _ast.Add, _ast.Sub, _ast.Mult, _ast.Div,
    _ast.USub, _ast.UAdd,
)

class _SafeEvalError(Exception):
    pass

def _safe_eval(expr: str, names: dict) -> float:
    try:
        tree = _ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise _SafeEvalError(f"SyntaxError: {e}")
    for node in _ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise _SafeEvalError(type(node).__name__)
        if isinstance(node, _ast.Call):
            if not isinstance(node.func, _ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise _SafeEvalError("Illegal function")
    def _ev(n):
        if isinstance(n, _ast.Expression): return _ev(n.body)
        if isinstance(n, _ast.Constant):   return float(n.value)
        if isinstance(n, _ast.Name):       return float(names.get(n.id, 0.0))
        if isinstance(n, _ast.UnaryOp):
            v = _ev(n.operand)
            return -v if isinstance(n.op, _ast.USub) else v
        if isinstance(n, _ast.BinOp):
            a, b = _ev(n.left), _ev(n.right)
            if isinstance(n.op, _ast.Add):  return a + b
            if isinstance(n.op, _ast.Sub):  return a - b
            if isinstance(n.op, _ast.Mult): return a * b
            if isinstance(n.op, _ast.Div):  return a / b if b else 0.0
        if isinstance(n, _ast.Call):
            return _ALLOWED_FUNCS[n.func.id](*[_ev(a) for a in n.args])
        raise _SafeEvalError("Unsupported node")
    return float(_ev(tree))

def _clamp01(v):          return max(0.0, min(1.0, v))
def _clamp(v, lo, hi):    return max(min(lo, hi), min(max(lo, hi), v))
def _remap_01(v, lo, hi): return lo + v * (hi - lo)
def _strip_comments(line): return line.split("//")[0].split("#")[0].strip()


# ── QC parsers ────────────────────────────────────────────────────────────────

# A QC expression refers to another localvar WITH its SIGIL:
# %right_lip_suppressor = 1 / %right_open * (1 - presser) * (1 - bite)
# %AU12R = right_corner_puller * right_corner_puller * %right_corner_suppressor
#
# THIS is why GMAN'S MOUTH WAS DEAD. `%` is the MODULO operator in Python, so
# `1 / %right_open` is a SyntaxError - _safe_eval raised, the handler
# substituted 0.0, and every expression that referenced another localvar
# silently produced nothing. The ones that worked (AU4, AU6, AU2, AU9, AU38,
# the eyelids) are exactly the ones with no `%` in their bodies.
#
# The sigil carries no meaning beyond "this is a localvar" - QC has no modulo
# operator - so it is stripped here, once, before anything parses
_RX_LV_SIGIL = _re.compile(r'%(?=[A-Za-z_])')


def _parse_localvar_expressions(qc_text: str) -> list:
    results = []
    for line in qc_text.splitlines():
        m = _re.match(r'^%([A-Za-z_]\w*)\s*=\s*(.+)$', _strip_comments(line))
        if m:
            results.append({"localvar": m.group(1),
                            "expr": _RX_LV_SIGIL.sub("", m.group(2)).strip()})
    return results

# two regex variants handle the two common QC formats:
# $flexcontroller <type> range <lo> <hi> <NAME>
# flexcontroller <NAME|"NAME"> range <lo> <hi> <NAME|"NAME">
_RX_FC_A = _re.compile(
    r'^\$flexcontroller\s+(".*?"|\S+)\s+range\s+([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s+([A-Za-z_]\w*)\s*$',
    _re.IGNORECASE
)
_RX_FC_B = _re.compile(
    r'^flexcontroller\s+("([^"]+)"|([A-Za-z_]\w*))\s+range\s+([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s+("([^"]+)"|([A-Za-z_]\w*))\s*$',
    _re.IGNORECASE
)

def _parse_flexcontroller_ranges(qc_text: str) -> dict:
    """
    Returns {controller_name: (lo, hi)}.
    The controller NAME is the identifier used in %localvar expressions —
    it is the last token on the line in both QC formats.
    """
    ranges = {}
    for raw in qc_text.splitlines():
        line = _strip_comments(raw)
        if not line:
            continue
        m = _RX_FC_A.match(line)
        if m:
            ranges[m.group(4)] = (float(m.group(2)), float(m.group(3)))
            continue
        m = _RX_FC_B.match(line)
        if m:
            last = m.group(7) or m.group(8)   # quoted or unquoted last name
            ranges[last] = (float(m.group(4)), float(m.group(5)))
    return ranges


# ── shape key index + resolver ────────────────────────────────────────────────

def _build_kb_index(kb) -> tuple:
    """Returns (keys_list, lower_map, lower_list) for scored resolving."""
    keys_list  = list(k.name for k in kb)
    lower_map  = {}
    lower_list = []
    for name in keys_list:
        nl = name.lower()
        if nl not in lower_map:
            lower_map[nl] = name
        lower_list.append((nl, name))
    return keys_list, lower_map, lower_list

def _resolve_flex_name(kb, token: str, idx: tuple, cache: dict):
    """
    Scored resolver — returns (resolved_name_str, match_kind) or (None, "none").

    Priority:
      0  exact
      1  case-insensitive exact
      2  token + "_flex_channel"  (case-insensitive)
      3  prefix match             (shortest wins, then lexicographic)
      4  contains match           (shortest wins, then lexicographic)
    """
    if token in cache:
        return cache[token]

    keys_list, lower_map, lower_list = idx
    tl = token.lower()

    # 0 — exact
    if token in keys_list:
        cache[token] = (token, "exact")
        return cache[token]

    # 1 — case-insensitive exact
    if tl in lower_map:
        cache[token] = (lower_map[tl], "iexact")
        return cache[token]

    # 2 — _flex_channel suffix
    fc_key = (token + "_flex_channel").lower()
    if fc_key in lower_map:
        cache[token] = (lower_map[fc_key], "flex_channel")
        return cache[token]

    # 3 — prefix (shortest match wins)
    prefix_hits = sorted(
        [name for nl, name in lower_list if nl.startswith(tl)],
        key=lambda s: (len(s), s.lower())
    )
    if prefix_hits:
        cache[token] = (prefix_hits[0], "prefix")
        return cache[token]

    #4 — contains (shortest match wins)
    contains_hits = sorted(
        [name for nl, name in lower_list if tl in nl],
        key=lambda s: (len(s), s.lower())
    )
    if contains_hits:
        cache[token] = (contains_hits[0], "contains")
        return cache[token]

    cache[token] = (None, "none")
    return cache[token]

def _build_fcurve_map(action) -> dict:
    return {fc.data_path: fc for fc in iter_fcurves(action)}

def _get_flex_frame_range(action) -> tuple:
    if not action:
        return 1, 1
    all_frames = [kp.co.x for fc in iter_fcurves(action)
                  if fc.data_path.endswith(".value")
                  for kp in fc.keyframe_points]
    return (int(min(all_frames)), int(max(all_frames))) if all_frames else (1, 1)



_RX_EYELID = _re.compile(
    r'^\s*eyelid\s+(\S+)\s+"[^"]*"'
    r'\s+lowerer\s+(-?\d+)\s+(-?[\d.]+)'
    r'\s+neutral\s+(-?\d+)\s+(-?[\d.]+)'
    r'\s+raiser\s+(-?\d+)\s+(-?[\d.]+)', _re.IGNORECASE)

_RX_FLEXPAIR = _re.compile(r'^\s*flexpair\s+"([^"]+)"', _re.IGNORECASE)


def parse_eyelids(qc_text: str) -> dict:
    """{flex_name: k} - how much the LOWERER weight moves the surviving key.

    See the block above for where k comes from. A degenerate line (raiser and
    neutral at the same height) is skipped rather than dividing by zero."""
    out = {}
    for raw in qc_text.splitlines():
        m = _RX_EYELID.match(_strip_comments(raw))
        if not m:
            continue
        name = m.group(1).strip('"')
        low_h = float(m.group(3))
        neu_h = float(m.group(5))
        rai_h = float(m.group(7))
        span = rai_h - neu_h
        if abs(span) < 1e-6:
            continue
        out[name] = (low_h - neu_h) / span
    return out


def parse_flexpairs(qc_text: str) -> list:
    """The flex names the QC declares as PAIRS, in order, deduplicated.

    `flexpair "AU12"` appears twice in gman.qc (two VTA frames for an
    asymmetric pair). Only the name matters here, so once is enough."""
    out = []
    for raw in qc_text.splitlines():
        m = _RX_FLEXPAIR.match(_strip_comments(raw))
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


# which side of the model is the character's RIGHT. gman: right = -X,
# measured from the eyelid keys (see note 3 above). Exposed rather than
# hard-coded inline so a model that disagrees can be corrected in one place
RIGHT_IS_NEGATIVE_X = True
SPLIT_BLEED = 0.15          #in model units, half-width of the blend across x=0


def split_flexpairs(obj, qc_text: str, report=print) -> dict:
    """Turn each `<X>R` that secretly holds BOTH sides into a real `<X>R`+`<X>L`.

    SourceIO gives one key per flexpair, named `...R`, carrying the whole
    symmetric delta. The compiler would have weighted it left and right. This
    does the same: `<X>L` gets a new key with the delta scaled by a smooth
    left-side weight, and `<X>R` is re-scaled in place by the right-side
    weight. The two weights sum to 1 at every vertex, so R+L at full strength
    reproduces the original delta exactly - which is the property that makes
    this a SPLIT and not an invention.

    Skips anything already split (an `<X>L` present), so it is idempotent and
    safe on a model SourceIO did handle properly.

    Returns {"split": n, "skipped": n, "names": [...]}.
    """
    sk = obj.data.shape_keys
    if not sk:
        return {"split": 0, "skipped": 0, "names": []}
    kb = sk.key_blocks
    basis = kb[0]
    verts = obj.data.vertices
    pairs = parse_flexpairs(qc_text)

    done, skipped, names = 0, 0, []
    for base_name in pairs:
        r_name = base_name + "R"
        l_name = base_name + "L"
        r_kb = kb.get(r_name)
        if r_kb is None or kb.get(l_name) is not None:
            skipped += 1
            continue

        # does it actually straddle the middle? A key that's already
        # one-sided was split by something else and must be left alone -
        # re-splitting it would delete half of a correct shape
        both = False
        for i, d in enumerate(r_kb.data):
            if (d.co - basis.data[i].co).length > 1e-5:
                x = verts[i].co.x
                if x > SPLIT_BLEED:
                    both = both or True
                    if RIGHT_IS_NEGATIVE_X:
                        break
        if not both:
            skipped += 1
            continue

        l_kb = obj.shape_key_add(name=l_name, from_mix=False)
        l_kb.slider_min = LOCALVAR_SLIDER_MIN
        l_kb.slider_max = LOCALVAR_SLIDER_MAX

        for i, v in enumerate(verts):
            delta = r_kb.data[i].co - basis.data[i].co
            # Smooth weight across the symmetry plane so the seam does not
            # crease. t = 1 on the character's LEFT, 0 on the RIGHT.
            x = v.co.x
            t = (x + SPLIT_BLEED) / (2.0 * SPLIT_BLEED)
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
            left_w = t if RIGHT_IS_NEGATIVE_X else (1.0 - t)
            l_kb.data[i].co = basis.data[i].co + delta * left_w
            r_kb.data[i].co = basis.data[i].co + delta * (1.0 - left_w)

        done += 1
        names.append(l_name)

    if done:
        report(f"[HWM_FACE]  flexpair split: {done} created "
               f"({', '.join(names[:8])}{' ...' if len(names) > 8 else ''}), "
               f"{skipped} already fine")
    return {"split": done, "skipped": skipped, "names": names}


def _topo_order(exprs: dict) -> list:
    """Localvar names in dependency order.

    THE BUG THIS EXISTS TO FIX. A QC's %localvars are not all outputs - many
    are INTERMEDIATE values that later expressions consume:

        localvar right_open
        %right_open = ...
        %AU25R = ... right_open ...

    The old baker resolved every token in an expression to a SHAPE KEY. An
    intermediate is not a shape key, so it resolved to nothing and was
    silently substituted with 0.0 - quietly wrong for every expression that
    depended on one, on every HWM model, not just gman. gman.qc has 13 of
    them feeding the entire mouth.

    Evaluating in dependency order lets an intermediate be computed once and
    handed to whatever needs it. A cycle (Source allows none) falls back to
    declaration order rather than looping forever."""
    order, state = [], {}

    def visit(n):
        st = state.get(n)
        if st == 2:
            return
        if st == 1:            # cycle - take it as it comes
            return
        state[n] = 1
        for tok in _re.findall(r'\b([A-Za-z_]\w*)\b', exprs.get(n, "")):
            if tok in exprs and tok != n and tok not in _ALLOWED_FUNCS:
                visit(tok)
        state[n] = 2
        order.append(n)

    for name in exprs:
        visit(name)
    return order


def bake_hwm_localvars(obj, qc_path: Path, do_split_pairs: bool = True) -> dict:
    """
    Evaluate HWM $flexcontroller / %localvar expressions frame-by-frame
    and bake results as F-curves onto *obj*'s shape keys.

    INPUT CONVENTION (matches SFM / BST behaviour):
      Flex DMX stores all flexcontroller values as normalised 0→1.
      The QC $flexcontroller range (lo, hi) defines the real-world mapping.
      So a neck_tilt stored as 0.75 with range -1→1 evaluates to +0.5.

    Returns a result dict: ok, baked, keys, exact, fuzzy, unresolved, etc.
    """
    empty = {"ok": False, "error": "",
             "baked": 0, "keys": 0,
             "exact": 0, "fuzzy": 0, "unresolved": 0,
             "added": 0, "skipped": 0,
             "unresolved_tokens": [], "fuzzy_tokens": [],
             "t_pre": 0.0, "t_bake": 0.0}

    if obj.type != "MESH":
        return {**empty, "error": "Object is not a mesh"}

    sk = obj.data.shape_keys
    if not sk or not sk.animation_data or not sk.animation_data.action:
        return {**empty, "error": "No flex animation on mesh — import shape keys first"}

    qc_path = Path(qc_path)
    if not qc_path.exists():
        return {**empty, "error": f"QC not found: {qc_path}"}

    t0        = time.time()
    qc_text   = qc_path.read_text(encoding="utf-8", errors="replace")
    localvars = _parse_localvar_expressions(qc_text)
    fc_ranges = _parse_flexcontroller_ranges(qc_text)
    eyelids   = parse_eyelids(qc_text)

    if not localvars:
        return {**empty, "error": f"No %LocalVar expressions in {qc_path.name}"}

    #before ANYTHING READS the SHAPE KEYS. SourceIO leaves every flexpair as
    #a single `...R` holding both sides of the face, so the `...L` half of
    #every expression has nothing to write to. Split them first and the
    #ordinary resolver finds both halves
    split_info = ({"split": 0, "skipped": 0, "names": []} if not do_split_pairs
                  else split_flexpairs(obj, qc_text))

    flex_action    = sk.animation_data.action
    fcurve_map     = _build_fcurve_map(flex_action)
    f_start, f_end = _get_flex_frame_range(flex_action)
    kb             = sk.key_blocks
    kb_idx         = _build_kb_index(kb)
    cache          = {}

    # ── Everything the QC defines, and what each one is FOR ──────────────────
    #
    # Two kinds of %localvar, and the old code treated them as one:
    #
    # OUTPUT        its name is a flex, so its value is written to that
    # shape key       (e.g. %AU25R)
    # INTERMEDIATE  its name is not a flex; it exists only to be read by
    # other expressions   (e.g. %right_open)
    #
    # An intermediate has no shape key, so the old resolver returned None for
    # it and CLEAN_ADD dropped it - AND, worse, any expression that mentioned
    # it got 0.0 substituted for that token with no warning. gman.qc has 13
    # intermediates feeding the whole mouth, so most of the face was being
    # computed from zeros
    #
    # Now: every expression is evaluated, in dependency order, into one shared
    # per-frame scope. Only the outputs get curves.
    exprs = {}
    for lv in localvars[:MAX_LOCALVARS]:
        exprs[lv["localvar"]] = lv["expr"]
    order = _topo_order(exprs)

    # which localvars actually reach a shape key
    # EXACT MATCHES ONLY. The fuzzy resolver (prefix / contains) exists to
    # cope with importers that decorate names, and it is the wrong tool here:
    # a QC localvar that IS a flex matches its shape key exactly, and an
    # INTERMEDIATE like `mouth` will happily fuzzy-match `mouth_something`
    # and start driving a shape key nothing asked it to drive. An
    # intermediate silently writing to a real flex is worse than one that
    # writes nowhere, bc the face moves and the reason is invisible
    outputs = {}
    intermediates = []
    for lv_name in order:
        resolved_name, match_type = _resolve_flex_name(kb, lv_name, kb_idx,
                                                       cache)
        if resolved_name is not None and match_type in ("exact", "iexact"):
            outputs[lv_name] = (resolved_name, match_type)
        else:
            intermediates.append(lv_name)

    # EYELIDS. `upper_right` is one shape key standing in for a three-target
    # flex, so three localvars - _raiser, _neutral, _lowerer - land on it.
    # _neutral is the base mesh and contributes nothing; _lowerer is the
    # missing target, reconstructed from the QC's own eyeball heights
    # See the note above parse_eyelids for the arithmetic
    eyelid_outputs = {}
    for flex_name, k in eyelids.items():
        target, _mt = _resolve_flex_name(kb, flex_name, kb_idx, cache)
        if target is None:
            continue
        r_lv = f"{flex_name}_raiser"
        l_lv = f"{flex_name}_lowerer"
        if r_lv not in exprs and l_lv not in exprs:
            continue
        eyelid_outputs[flex_name] = (target, r_lv, l_lv, k)
        # A blink drives this to roughly k (about -5.6 on gman), so the
        # default 0..1 slider would clip the entire closing motion
        blk = kb.get(target)
        if blk is not None:
            blk.slider_min = min(blk.slider_min, LOCALVAR_SLIDER_MIN)
            blk.slider_max = max(blk.slider_max, LOCALVAR_SLIDER_MAX)
        # these three are consumed here, not written individually
        for n in (r_lv, l_lv, f"{flex_name}_neutral"):
            outputs.pop(n, None)

    tasks = [{"localvar": n, "expr": exprs[n]} for n in order]

    t_pre = round(time.time() - t0, 3)

    if not tasks:
        return {**empty, "t_pre": t_pre,
                "error": "No matching localvars (CLEAN_ADD — no shape keys matched)"}

    # ── Create / replace bake action ──────────────────────────────────────────
    if REPLACE_EXISTING_BAKE_ACTION:
        old = bpy.data.actions.get(ACTION_NAME)
        if old and old.users == 0:
            bpy.data.actions.remove(old)

    if not sk.animation_data:
        sk.animation_data_create()
    bake_action, bake_bag = make_action(ACTION_NAME, sk)
    if STORE_ANIMATION:
        sk.animation_data.action = bake_action

    t1 = time.time()
    baked = keys = added = skipped = exact_c = fuzzy_c = unresolved_c = 0
    fuzzy_tokens      = []
    unresolved_tokens = []

    for lv_name, (_rn, match_type) in outputs.items():
        if match_type == "exact":
            exact_c += 1
        elif match_type in ("iexact", "flex_channel", "prefix", "contains"):
            fuzzy_c += 1
            if lv_name not in fuzzy_tokens:
                fuzzy_tokens.append(lv_name)
    # An INTERMEDIATE isn't "unresolved" - it's doing its job. Only a
    # CONTROLLER token with no source curve is a genuine miss, and those are
    # collected below where they are discovered
    eyelid_consumed = set()
    for fn, (_t, r, l, _k) in eyelid_outputs.items():
        eyelid_consumed.update((r, l, f"{fn}_neutral"))
    intermediates = [n for n in intermediates if n not in eyelid_consumed]

    # one f-curve per OUTPUT, made once rather than per frame
    out_fcs = {}
    for lv_name, (resolved_name, _mt) in outputs.items():
        path = f'key_blocks["{resolved_name}"].value'
        out_fcs[lv_name] = fc_find_or_new(bake_bag, path,
                                          group_name=resolved_name)
    for flex_name, (target, _r, _l, _k) in eyelid_outputs.items():
        path = f'key_blocks["{target}"].value'
        out_fcs["<eyelid>" + flex_name] = fc_find_or_new(
            bake_bag, path, group_name=target)

    # CONTROLLER INPUTS, resolved once. The old loop re-resolved every token
    # of every expression on every frame - the same name lookup a thousand
    # times over. The set of tokens doesn't change between frames
    controller_src = {}
    for expr in exprs.values():
        for tok in _re.findall(r'\b([A-Za-z_]\w*)\b', expr):
            if tok in _ALLOWED_FUNCS or tok in exprs or tok in controller_src:
                continue
            tok_name, _ = _resolve_flex_name(kb, tok, kb_idx, cache)
            src = (fcurve_map.get(f'key_blocks["{tok_name}"].value')
                   if tok_name else None)
            controller_src[tok] = src
            if src is None and tok not in unresolved_tokens:
                unresolved_c += 1
                unresolved_tokens.append(tok)

    for frame in range(f_start, f_end + 1):
        # ONE scope for the whole frame. Intermediates computed here are
        # visible to every expression after them - which is the entire point
        scope = {}
        for tok, src in controller_src.items():
            if src is None:
                scope[tok] = 0.0
                continue
            v01 = _clamp01(float(src.evaluate(frame)))
            if tok in fc_ranges:
                lo, hi = fc_ranges[tok]
                scope[tok] = _remap_01(v01, lo, hi)
            else:
                scope[tok] = v01

        for lv_name in order:
            try:
                val = _safe_eval(exprs[lv_name], scope)
            except _SafeEvalError:
                val = 0.0
            scope[lv_name] = val          # available to everything downstream

        for lv_name, fc in out_fcs.items():
            if lv_name.startswith("<eyelid>"):
                flex_name = lv_name[len("<eyelid>"):]
                _t, r_lv, l_lv, k = eyelid_outputs[flex_name]
                val = scope.get(r_lv, 0.0) + k * scope.get(l_lv, 0.0)
            else:
                val = scope.get(lv_name, 0.0)
            val = (_clamp01(val) if CLAMP_LOCALVAR_0_1
                   else _clamp(val, LOCALVAR_SLIDER_MIN, LOCALVAR_SLIDER_MAX))
            kp = fc.keyframe_points.insert(float(frame), float(val),
                                           options={"FAST"})
            kp.interpolation = "LINEAR"
            keys += 1

    for fc in out_fcs.values():
        fc.keyframe_points.update()
    baked = len(out_fcs)

    print(f"[HWM_BAKE]  baked:{baked}  keys:{keys}  "
          f"exact:{exact_c}  fuzzy:{fuzzy_c}  unresolved:{unresolved_c}  "
          f"added:{added}  skipped:{skipped}")
    print(f"[HWM_BAKE]  localvars:{len(exprs)}  outputs:{len(outputs)}  "
          f"eyelids:{len(eyelid_outputs)}  "
          f"intermediates:{len(intermediates)}  "
          f"pairs split:{split_info['split']}")
    if intermediates:
        print(f"[HWM_BAKE]  intermediate (evaluated, not written): "
              f"{', '.join(intermediates[:8])}"
              + (" ..." if len(intermediates) > 8 else ""))
    if unresolved_tokens:
        print(f"[HWM_BAKE]  NO SOURCE for: {', '.join(unresolved_tokens[:10])}"
              + (" ..." if len(unresolved_tokens) > 10 else ""))

    return {
        "ok":                True,
        "error":             "",
        "baked":             baked,
        "keys":              keys,
        "exact":             exact_c,
        "fuzzy":             fuzzy_c,
        "unresolved":        unresolved_c,
        "added":             added,
        "skipped":           skipped,
        "unresolved_tokens": unresolved_tokens,
        "fuzzy_tokens":      fuzzy_tokens,
        "localvars":         len(exprs),
        "outputs":           len(outputs),
        "eyelids":           len(eyelid_outputs),
        "intermediates":     len(intermediates),
        "pairs_split":       split_info["split"],
        "t_pre":             t_pre,
        "t_bake":            round(time.time() - t1, 3),
    }

run_hwm_bake = bake_hwm_localvars   # legacy alias


# ──────────────────────────────────────────────────────────────────────────────
# misc helpers
# ──────────────────────────────────────────────────────────────────────────────

def _detect_hwm(obj) -> tuple:
    sk = obj.data.shape_keys
    if not sk:
        return False, 0, 0
    lc = rc = 0
    for kb in sk.key_blocks:
        n = kb.name.lower()
        if n.startswith(HWM_LEFT_PREFIX):
            lc += 1
        elif n.startswith(HWM_RIGHT_PREFIX):
            rc += 1
    return lc >= HWM_PREFIX_MIN and rc >= HWM_PREFIX_MIN, lc, rc


# ──────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ──────────────────────────────────────────────────────────────────────────────

def import_shape_keys(dmx_path, mesh_obj,
                      do_remove_drivers: bool = True,
                      do_stereo_split:   bool = False,
                      do_import_flex:    bool = True,
                      do_bake_hwm:       bool = True,
                      stepped_keys:      str = 'AUTO') -> dict:
    """
    Run up to 4 pipeline stages on *mesh_obj*.  All stages are individually
    toggled by keyword arguments — no global mutation required.
    """
    dmx_path = Path(dmx_path)
    if not dmx_path.exists():
        raise FileNotFoundError(f"DMX not found: {dmx_path}")
    if mesh_obj.type != "MESH":
        raise TypeError(f"Expected MESH, got '{mesh_obj.type}'")

    t_total = time.time()

    if do_remove_drivers:
        remove_shapekey_drivers(mesh_obj)

    stereo_created = stereo_split(mesh_obj) if do_stereo_split else 0

    imported = max_frame = 0
    frame_rate = 30
    if do_import_flex:
        r          = import_flex_dmx(dmx_path, mesh_obj,
                                    stepped_keys=stepped_keys)
        imported   = r["channels"]
        max_frame  = r["max_frame"]
        frame_rate = r["frame_rate"]

    base_name, qc_path = _find_qc_for_mesh(mesh_obj)
    bake_result = None

    if do_bake_hwm:
        if qc_path:
            bake_result = bake_hwm_localvars(mesh_obj, qc_path)
        else:
            reason = f"no QC for '{base_name}'" if base_name else "no armature parent"
            print(f"[SHAPE_KEYS]  Baker skipped — {reason}")

    print(f"[SHAPE_KEYS]  done in {round(time.time()-t_total, 2)}s")

    return {
        "channels":       imported,
        "max_frame":      max_frame,
        "frame_rate":     frame_rate,
        "qc_path":        qc_path,
        "bake_result":    bake_result,
        "stereo_created": stereo_created,
    }


# ──────────────────────────────────────────────────────────────────────────────
# operator
# ──────────────────────────────────────────────────────────────────────────────

@start_folders.browser_at("shapekeys")          #3.0.0: opens where you work, learns your folder
class HT_OT_ImportShapeKeys(Operator, ImportHelper):
    """PICK .dmx (face / flex) - ONE file, onto the SELECTED MESH

        Facial animation from a flex .dmx onto the SELECTED MESH, with the HWM bake

Without the bake the combination controls never fire and the face
barely moves. IN ORDER: drivers removed, optional stereo split, one
f-curve per flex controller the file animates, then the QC %localvar
expressions BAKED - the arithmetic mapping named controllers onto the
mesh's real flexes.

WHAT ONLY THE BAKE FIXES
  flexpairs  SourceIO imports "AU1R" holding BOTH sides; the real AU1L
             never arrives. Split here.
  eyelids    three targets collapsed into one key, the survivor being
             the RAISER - the lowerer is rebuilt from the QC's eyeball
             heights, or the model cannot blink.
  localvars  ones that only feed others are evaluated in dependency
             order, not read as zero
    """
    # BELOW the TOOLTIP CAP. Blender truncates an operator description
    # at 1023 characters, without a warning, mid-word. These paragraphs
    # were part of the docstring and were already being cut off before
    # anyone could read them, so they live here instead - kept, but out
    # of the tooltip's budget
    # Needs the model's .qc. Twelve TF2 ones ship in _QC Face Data; for any
    # other character point "QC Face Data (override)" in preferences at a
    # folder of your own. Without a QC only the bake is skipped, and it says so
    #

    bl_idname  = "ht.import_shape_keys"
    bl_label   = "Intelligent Flex Animation (.dmx)"
    # NO "REGISTER" - see the note in Report_UI/the constitution
    # REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    # touching any field in it RE-RUNS this operator. Re-running an
    # import re-reads the DMX and rebuilds every f-curve; nudging Scale
    # there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    # with the value you wanted is the safe way to change your mind
    bl_options = {"UNDO"}

    filename_ext = ".dmx"
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})

    remove_drivers: BoolProperty(
        name="Remove Drivers",
        description="Strip existing shape key drivers before importing",
        default=True,
    )
    symmetrize_l: BoolProperty(
        name="Symmetrize L \u2192 R (if 10+ L keys)",
        description="Run stereo split before importing",
        default=False,
    )
    do_import_shape_keys: BoolProperty(
        name="Import Shape Keys",
        description="Parse and apply flex animation from the DMX",
        default=True,
    )
    stepped_keys: EnumProperty(  # type: ignore
        name="Stepped Keys",
        description=(
            "SFM keys facial animation off whole frames and writes a HOLD as "
            "two keys about a thousandth of a frame apart. Blender only "
            "evaluates whole frames, so a step lands between its own two keys "
            "and reads as a soft ramp over about three frames instead of an "
            "instant change.\n\n"
            "AUTO snaps near-integer keys and resamples the curves that "
            "contain a step, which is what the bone and camera importers "
            "already do. OFF keeps the raw key times"),
        items=[
            ('AUTO', "Auto",
             "Snap near-integer keys; resample only curves with a step"),
            ('ALL', "All Curves", "Resample every flex curve"),
            ('OFF', "Off", "Keep the raw fractional key times"),
        ],
        default='AUTO',
    )

    auto_bake_hwm: BoolProperty(
        name="Auto Bake HWM",
        description="Run HWM localvar bake if a matching QC is found",
        default=True,
    )
    proxy_if_no_target: BoolProperty(
        name="Proxy If No Character",
        description=(
            "With no compatible mesh selected, build a procedural Shape Key "
            "Proxy instead of refusing: one labelled segment per flex, each "
            "driven by a real shape key of that name. Lets you see which "
            "flexes exist, which are animated and when, without owning the "
            "face. Untick to get the old error instead"),
        default=True,
    )

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "do_import_shape_keys")
        col.prop(self, "remove_drivers")
        col.prop(self, "symmetrize_l")
        col.prop(self, "auto_bake_hwm")
        col.prop(self, "stepped_keys")
        col.separator()
        col.prop(self, "proxy_if_no_target")
        obj = context.active_object
        if not obj or obj.type != "MESH":
            box = col.box().column(align=True)
            box.scale_y = 0.85
            if self.proxy_if_no_target:
                box.label(text="No mesh selected - a proxy", icon='INFO')
                box.label(text="will be built instead.")
            else:
                box.alert = True
                box.label(text="No mesh selected.", icon='ERROR')

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            #[roadmap #12] A missing target mesh is not the end of the
            #operation. Build the procedural stand-in so the data can still
            #be inspected, rather than dead-ending on "select a mesh".
            if not self.proxy_if_no_target:
                self.report({"ERROR"}, "Select a mesh object first.")
                return {"CANCELLED"}
            try:
                from ..tools import ShapeKey_Proxy
                r = ShapeKey_Proxy.build_proxy_from_dmx(self.filepath)
            except Exception as exc:
                self.report({"ERROR"},
                            f"No mesh selected, and the proxy failed: {exc}")
                return {"CANCELLED"}
            msg = (f"No character selected - built a proxy: "
                   f"{r['shape_keys']} shape key(s), {r['animated']} animated")
            print(f"[SHAPEKEYS]  {msg}")
            from ..core import Report_UI
            Report_UI.report(
                context, "shapekey_proxy", "Shape Key Proxy",
                ["No compatible mesh was selected.",
                 "Built a Shape Key Proxy instead:",
                 f"  {r['shape_keys']} shape key(s), {r['animated']} animated",
                 f"  in {r['collection']}"],
                level='WARNING', icon='SHAPEKEY_DATA', prefix="SHAPEKEYS",
                operator=self,
                summary=msg)
            self.report({"INFO"}, msg)
            return {"FINISHED"}

        t_total = time.time()

        # ── Stage 1: Remove drivers ───────────────────────────────────────────
        drivers_removed = 0
        if self.remove_drivers:
            try:
                drivers_removed = remove_shapekey_drivers(obj)
            except Exception as exc:
                self.report({"ERROR"}, f"Remove drivers failed: {exc}")
                return {"CANCELLED"}

        # ── Stage 2: Stereo split ─────────────────────────────────────────────
        stereo_created = 0
        if self.symmetrize_l:
            try:
                stereo_created = stereo_split(obj)
            except Exception as exc:
                self.report({"ERROR"}, f"Stereo split failed: {exc}")
                return {"CANCELLED"}

        #── Stage 3: Import flex DMX ──────────────────────────────────────────
        imported   = 0
        max_frame  = 0.0
        frame_rate = 30
        if self.do_import_shape_keys:
            try:
                flex_result = import_flex_dmx(self.filepath, obj)
                imported    = flex_result["channels"]
                max_frame   = flex_result["max_frame"]
                frame_rate  = flex_result["frame_rate"]
            except Exception as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}

        # ── Stage 4: HWM bake ─────────────────────────────────────────────────
        qc_path     = None
        bake_result = None
        if self.auto_bake_hwm and self.do_import_shape_keys:
            base_name, qc_path = _find_qc_for_mesh(obj)
            if qc_path:
                try:
                    bake_result = bake_hwm_localvars(obj, qc_path)
                except Exception as exc:
                    bake_result = {"ok": False, "error": str(exc)}

        #── Popup report ──────────────────────────────────────────────────────
        t_total    = round(time.time() - t_total, 2)
        dmx_name   = Path(self.filepath).name
        is_hwm, lc, rc = _detect_hwm(obj) if DETECT_HWM else (False, 0, 0)

        lines = [
            "\u2500\u2500 FLEX IMPORT \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
            f"  DMX      : {dmx_name}",
            f"  FPS      : {frame_rate}",
            f"  Channels : {imported} imported",
            f"  Frames   : {int(bpy.context.scene.frame_start)} \u2013 {int(ceil(max_frame))}",
        ]
        if drivers_removed:
            lines.append(f"  Drivers  : {drivers_removed} removed")
        if stereo_created:
            lines.append(f"  Stereo   : {stereo_created} R keys created")
        if is_hwm:
            lines.append(f"  HWM      : {lc} left_  /  {rc} right_")

        lines.append("\u2500\u2500 RIG LOOKUP \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
        base_name = _get_base_rig_name(obj)
        lines.append(f"  Rig      : {base_name or '(no armature parent)'}")
        if qc_path:
            lines.append(f"  QC       : {qc_path.name}  \u2713")
            lines.append(f"  Folder   : {qc_path.parent.name}")
        else:
            lines.append("  QC       : not found \u2014 baker skipped")

        if bake_result:
            lines.append("\u2500\u2500 HWM BAKE \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
            if bake_result["ok"]:
                lines += [
                    f"  Baked    : {bake_result['baked']} localvars  /  {bake_result['keys']} keys",
                    f"  Resolve  : exact={bake_result['exact']}  fuzzy={bake_result['fuzzy']}  unresolved={bake_result['unresolved']}",
                    f"  Time     : pre={bake_result['t_pre']}s  bake={bake_result['t_bake']}s",
                ]
                if bake_result.get("added"):
                    lines.append(f"  Added    : {bake_result['added']} new shape keys")
                if bake_result.get("skipped"):
                    lines.append(f"  Skipped  : {bake_result['skipped']} missing (CLEAN_ADD)")
                if bake_result.get("unresolved_tokens"):
                    lines.append(f"  Unresolved: {', '.join(bake_result['unresolved_tokens'][:6])}")
                if bake_result.get("fuzzy_tokens"):
                    lines.append(f"  Fuzzy    : {', '.join(bake_result['fuzzy_tokens'][:4])}")
            else:
                lines.append(f"  ERROR    : {bake_result['error']}")

        lines += ["\u2500" * 40, f"  Total    : {t_total}s"]

        title = f"Flex \u2014 {imported} channels"
        if bake_result and bake_result["ok"]:
            title += f" + {bake_result['baked']} localvars"

        from ..core import Report_UI
        Report_UI.report(context, "import_shape_keys", title, lines,
                         level=('WARNING' if (bake_result
                                              and not bake_result["ok"])
                                else 'INFO'),
                         prefix="SHAPEKEYS", operator=self, summary=title)
        self.report({"INFO"}, f"Imported {imported} flex channels in {t_total}s")
        return {"FINISHED"}

def draw_menu_item(layout):
    layout.operator(
        HT_OT_ImportShapeKeys.bl_idname,
        text="Intelligent Flex Animation (.dmx)",
        **_icon_id("import_shape_keys", "SHAPEKEY_DATA"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# register / unregister
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (HT_OT_ImportShapeKeys,)


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


if __name__ == "__main__":
    register()
    bpy.ops.ht.import_shape_keys("INVOKE_DEFAULT")
