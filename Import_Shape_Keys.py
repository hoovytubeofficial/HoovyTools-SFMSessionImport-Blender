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
import re as _re
import ast as _ast
import time
from math import ceil
from pathlib import Path
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper
from .anim_compat import make_action, get_channelbag, fc_find_or_new, iter_fcurves, count_fcurves


# ──────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────────────────────────────────────

QC_SFM_FOLDER = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\SourceFilmmaker"
    r"\game\usermod\plugins\___SFM to Blender Session Importer\_Dev\QC Face Data"
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
#  ICON HELPER
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
#  QC FOLDER RESOLUTION
# ──────────────────────────────────────────────────────────────────────────────

def _addon_qc_folder() -> Path:
    return Path(__file__).parent / "QC Face Data"

def _qc_search_folders() -> list:
    return [f for f in [_addon_qc_folder(), QC_SFM_FOLDER] if f.is_dir()]


# ──────────────────────────────────────────────────────────────────────────────
#  FUNCTION 1 — REMOVE SHAPE KEY DRIVERS
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
#  FUNCTION 2 — STEREO SPLIT  (L → L + R)
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

            # Smooth 50/50 split centered at x_norm=0.5, transition width = 2*BLEED
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
#  FUNCTION 3 — IMPORT FLEX DMX
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
    from .SST import get_datamodel
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


def import_flex_dmx(dmx_path, obj) -> dict:
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

    bpy.context.scene.frame_start = 0
    if max_frame > bpy.context.scene.frame_end:
        bpy.context.scene.frame_end = int(ceil(max_frame))

    return {"channels": imported, "max_frame": max_frame, "frame_rate": frame_rate}


# ──────────────────────────────────────────────────────────────────────────────
#  FUNCTION 4 — BAKE HWM LOCALVARS
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

def _find_qc_for_rig(base_name: str) -> Path | None:
    # QC files live in HoovyTools/QC Face Data/<base_name>.qc
    # base_name comes from armature data name with _ARM_DATA stripped,
    # e.g. "calendar_girl_boots_ARM_DATA" -> "calendar_girl_boots" -> "calendar_girl_boots.qc"
    target = f"{base_name}.qc".lower()
    folder = _addon_qc_folder()
    if not folder.is_dir():
        return None
    for f in folder.iterdir():
        if f.suffix.lower() == ".qc" and f.name.lower() == target:
            return f
    return None

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

def _parse_localvar_expressions(qc_text: str) -> list:
    results = []
    for line in qc_text.splitlines():
        m = _re.match(r'^%([A-Za-z_]\w*)\s*=\s*(.+)$', _strip_comments(line))
        if m:
            results.append({"localvar": m.group(1), "expr": m.group(2).strip()})
    return results

# Two regex variants handle the two common QC formats:
#   $flexcontroller <type> range <lo> <hi> <NAME>
#   flexcontroller <NAME|"NAME"> range <lo> <hi> <NAME|"NAME">
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

    # 4 — contains (shortest match wins)
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


def bake_hwm_localvars(obj, qc_path: Path) -> dict:
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

    if not localvars:
        return {**empty, "error": f"No %LocalVar expressions in {qc_path.name}"}

    flex_action    = sk.animation_data.action
    fcurve_map     = _build_fcurve_map(flex_action)
    f_start, f_end = _get_flex_frame_range(flex_action)
    kb             = sk.key_blocks
    kb_idx         = _build_kb_index(kb)
    cache          = {}

    # ── Pre-filter: collect tasks ─────────────────────────────────────────────
    # Each task: (localvar_name, expr, output_shape_key_name)
    tasks = []
    for lv in localvars[:MAX_LOCALVARS]:
        lv_name = lv["localvar"]
        resolved_name, _ = _resolve_flex_name(kb, lv_name, kb_idx, cache)
        if CLEAN_ADD and resolved_name is None:
            continue
        tasks.append(lv)

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

    for task in tasks:
        lv_name = task["localvar"]
        lv_expr = task["expr"]

        resolved_name, match_type = _resolve_flex_name(kb, lv_name, kb_idx, cache)

        if resolved_name is None:
            if not CLEAN_ADD:
                new_kb            = obj.shape_key_add(name=lv_name, from_mix=False)
                new_kb.slider_min = LOCALVAR_SLIDER_MIN
                new_kb.slider_max = LOCALVAR_SLIDER_MAX
                resolved_name     = lv_name
                match_type        = "added"
                added            += 1
                kb_idx            = _build_kb_index(kb)
                cache.clear()
            else:
                skipped += 1
                continue

        if match_type == "exact":                              exact_c += 1
        elif match_type == "added":                            pass
        elif match_type in ("iexact", "flex_channel",
                            "prefix", "contains"):
            fuzzy_c += 1
            if lv_name not in fuzzy_tokens:
                fuzzy_tokens.append(lv_name)
        else:
            unresolved_c += 1
            if lv_name not in unresolved_tokens:
                unresolved_tokens.append(lv_name)

        # Output fcurve — keyed by the RESOLVED shape key name
        out_path = f'key_blocks["{resolved_name}"].value'
        out_fc   = fc_find_or_new(bake_bag, out_path, group_name=resolved_name)

        # Collect input token names from the expression
        tokens = [t for t in _re.findall(r'\b([A-Za-z_]\w*)\b', lv_expr)
                  if t not in _ALLOWED_FUNCS]

        # Per-frame evaluation ──────────────────────────────────────────────
        frame_keys = 0
        for frame in range(f_start, f_end + 1):
            scope = {}
            for tok in tokens:
                # Resolve the token to the actual imported shape key name
                tok_name, _ = _resolve_flex_name(kb, tok, kb_idx, cache)
                if tok_name is None:
                    scope[tok] = 0.0
                    continue

                src = fcurve_map.get(f'key_blocks["{tok_name}"].value')
                if src is None:
                    scope[tok] = 0.0
                    continue

                # SFM flex DMX: values are stored normalised 0→1.
                # Clamp to safety, then remap to QC real-world range.
                v01 = _clamp01(float(src.evaluate(frame)))
                if tok in fc_ranges:
                    lo, hi = fc_ranges[tok]
                    scope[tok] = _remap_01(v01, lo, hi)
                else:
                    scope[tok] = v01

            try:
                val = _safe_eval(lv_expr, scope)
                val = (_clamp01(val) if CLAMP_LOCALVAR_0_1
                       else _clamp(val, LOCALVAR_SLIDER_MIN, LOCALVAR_SLIDER_MAX))
            except _SafeEvalError:
                val = 0.0

            kp = out_fc.keyframe_points.insert(float(frame), float(val),
                                               options={"FAST"})
            kp.interpolation = "LINEAR"
            frame_keys += 1

        out_fc.keyframe_points.update()
        keys  += frame_keys
        baked += 1

    print(f"[HWM_BAKE]  baked:{baked}  keys:{keys}  "
          f"exact:{exact_c}  fuzzy:{fuzzy_c}  unresolved:{unresolved_c}  "
          f"added:{added}  skipped:{skipped}")

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
        "t_pre":             t_pre,
        "t_bake":            round(time.time() - t1, 3),
    }

run_hwm_bake = bake_hwm_localvars   # legacy alias


# ──────────────────────────────────────────────────────────────────────────────
#  MISC HELPERS
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
#  ORCHESTRATOR
# ──────────────────────────────────────────────────────────────────────────────

def import_shape_keys(dmx_path, mesh_obj,
                      do_remove_drivers: bool = True,
                      do_stereo_split:   bool = False,
                      do_import_flex:    bool = True,
                      do_bake_hwm:       bool = True) -> dict:
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
        r          = import_flex_dmx(dmx_path, mesh_obj)
        imported   = r["channels"]
        max_frame  = r["max_frame"]
        frame_rate = r["frame_rate"]

    base_name   = _get_base_rig_name(mesh_obj)
    qc_path     = _find_qc_for_rig(base_name) if base_name else None
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
#  OPERATOR
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_ImportShapeKeys(Operator, ImportHelper):
    """Import SFM flex DMX as shape key animation + optional HWM bake"""
    bl_idname  = "ht.import_shape_keys"
    bl_label   = "Intelligent Flex Animation (.dmx)"
    bl_options = {"REGISTER", "UNDO"}

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
    auto_bake_hwm: BoolProperty(
        name="Auto Bake HWM",
        description="Run HWM localvar bake if a matching QC is found",
        default=True,
    )

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh object first.")
            return {"CANCELLED"}

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

        # ── Stage 3: Import flex DMX ──────────────────────────────────────────
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
            base_name = _get_base_rig_name(obj)
            if base_name:
                qc_path = _find_qc_for_rig(base_name)
            if qc_path:
                try:
                    bake_result = bake_hwm_localvars(obj, qc_path)
                except Exception as exc:
                    bake_result = {"ok": False, "error": str(exc)}

        # ── Popup report ──────────────────────────────────────────────────────
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
            lines.append(f"  Folder   : {'addon' if qc_path.parent == _addon_qc_folder() else 'SFM'}")
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

        _lines = list(lines)
        def draw(self, context):
            for line in _lines:
                self.layout.label(text=line)
        context.window_manager.popup_menu(draw, title=title, icon="CHECKMARK")
        self.report({"INFO"}, f"Imported {imported} flex channels in {t_total}s")
        return {"FINISHED"}

def draw_menu_item(layout):
    layout.operator(
        HT_OT_ImportShapeKeys.bl_idname,
        text="Intelligent Flex Animation (.dmx)",
        **_icon_id("import_shape_keys", "SHAPEKEY_DATA"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
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
