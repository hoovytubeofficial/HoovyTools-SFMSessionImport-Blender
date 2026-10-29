"""
Utils_Misc.py  —  part of HoovyTools
====================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Source Engine Utils ▸ Misc ▸
           Organize Scene
           Reduce Lag With Epsilon Filter
           Delete Rotation Spins

Three scene-wide housekeeping tools for SourceIO imports.

────────────────────────────────────────────────────────────────────────────
ORGANIZE SCENE
────────────────────────────────────────────────────────────────────────────
Sorts every imported SourceIO rig into a tidy nested collection hierarchy.

Each rig already lives in its own SourceIO collection (axis/root empties,
armature, mesh + _ATTACHMENTS sub-collections, viewTarget empty + constraints).
The whole collection is moved as a unit, then the emptied source folders are
removed so the outliner isn't left full of stale collections.

  • PATH-BASED MODELS — a mesh name like
        tf2_enhanced\\foliage\\mediterranean\\asphodel_grass_a_enhanced.m_…smd_MESH
    becomes  ___Models___ / TF2 Enhanced / Foliage / Mediterranean /
    Asphodel Grass A Enhanced  (split on backslash; first dot in the final
    segment ends the path; Title Case with TF2/HL2 acronyms preserved).
  • CHARACTERS — any rig whose armature name matches a  Faulty Rigs/
    {character}_reference.dmx  goes to  ___Characters___ / {Character Name}
    (longest stem wins).
  Rerunnable: clears the destination roots and re-sorts fresh.

────────────────────────────────────────────────────────────────────────────
REDUCE LAG WITH EPSILON FILTER
────────────────────────────────────────────────────────────────────────────
Reduces keyframe count on EVERY armature in the scene without destroying the
motion, using Ramer–Douglas–Peucker simplification: a keyframe is kept only if
removing it would bend the interpolated curve away from the real motion by more
than an epsilon. Activations (0→1) and corners are kept; dither (0.01→0.02) and
redundant ramp samples are dropped. Endpoints are always kept.

  • ROTATION  — 'rotation_quaternion' simplified by ORIENTATION ANGLE (the four
    components together), epsilon in degrees.
  • SHAPE KEYS — 'value' curves on connected meshes, epsilon in influence units.
  Location is intentionally NOT processed (rotation-only keeps it fast).

  Optional toggle skips rigs matching a  Faulty Rigs/  reference.

───────────────────────────────────────────────────────────────────────────
DELETE ROTATION SPINS
───────────────────────────────────────────────────────────────────────────
Two frames can hold the SAME pose two different ways, and when consecutive
frames pick differently the interpolation takes the long way round - a full
spin backwards between poses that barely moved.

  QUATERNION SIGN FLIP  q and -q are the same orientation. This is the one
                        that fires on an imported session: every importer here
                        writes quaternions.
  EULER GIMBAL FLIP     (x, y, z) and (x+180, 180-y, z+180) are the same
                        orientation - 180 on every axis at once, which no
                        "jump bigger than 300 degrees" test can see.
  EULER WRAP            179.9 then -179.9; add whole turns.

No pose changes and nothing moves in time: every keyed frame comes out
identical and only the path between keys does. Bezier handles travel with
their key - they are absolute, and leaving them behind turns the fix into a
spike the size of the shift. Pose bones and objects both. Idempotent.

  BAKED SPINS (1.22.0)  the one pass that DOES change poses, because the
                        poses are the fault: baked keys that themselves turn
                        a full 360 over a few frames (a blend of quaternion
                        numbers across q / -q). The window is rebuilt along
                        the short arc at the speed the motion had at its ends
                        and every key after it is moved by whole turns.
                        core/spin_rebuild.py holds the maths and the story
                        (CSDeals Scene3, wood_planks4_rig > camera).

1.22.0 also made the button work on the SELECTION by default (Pose Mode: the
selected bones only), with an optional frame range, so a press on a big
session touches the one camera you meant and nothing else.
"""

bl_info = {
    "name":        "HoovyTools: Utils — Misc",
    "description": "Scene organizer + keyframe epsilon filter for SourceIO imports",
    "author":      "HoovyTools",
    "version":     (1, 1, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > Source Engine Utils > Misc",
    "category":    "Import-Export",
}

import bpy
from ..core import paths as _paths
import math
import re
from pathlib import Path
from mathutils import Quaternion
from bpy.types import Operator
from bpy.props import BoolProperty, FloatProperty, EnumProperty, IntProperty


# ──────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────────────────────────────────────

MODELS_ROOT     = "__Models__"
CHARACTERS_ROOT = "__Characters__"
PROPS_ROOT      = "__Props__"
LEGACY_ROOTS    = ("___Models___", "___Characters___")   # pre-1.16.0 names
COLOR_MODELS    = "COLOR_05"   # blue
COLOR_CHARS     = "COLOR_04"   # green
COLOR_PROPS     = "COLOR_03"   # yellow

#  "Props are animated, with at least 30 frames of animation on a single
#  bone." Measured as the SPAN over which one bone's value really changes -
#  first moving key to last - not as a key count: SFM bakes a static channel
#  as a key on every frame (thousands of keys, no motion), and a two-key move
#  sixty frames apart is a sixty-frame animation.
PROP_MIN_FRAMES = 30
PROP_EPS = 1e-4

# Epsilon filter defaults (rotation + shape keys only; location not processed)
EPS_ROTATION = 0.5     # degrees — orientation deviation for quaternion curves
EPS_SHAPEKEY = 0.02    # shape-key value deviation (0..1 influence)

# Armatures containing ANY of these bones are skipped by the epsilon filter
# (these are the TF2/HL2 biped skeleton bones — i.e. character rigs, whose bone
# animation we don't want to thin).
SKIP_IF_BONES = (
    "bip_spine_0", "bip_pelvis", "bip_head", "bip_neck", "bip_lowerArm_L",
)

# Acronyms that .title() would mangle (Tf2 → TF2). Extend as needed.
_ACRONYM_FIXUPS = {
    "Tf2": "TF2", "Hl2": "HL2", "Hl1": "HL1", "Csgo": "CSGO",
    "Cs2": "CS2", "Css": "CSS", "Hwm": "HWM", "Sfm": "SFM",
    "L4d": "L4D", "L4d2": "L4D2", "Tf": "TF",
}


# ──────────────────────────────────────────────────────────────────────────────
#  ICON HELPER
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
#  ITER_FCURVES  (layered-action safe; reuse anim_compat, local fallback)
# ──────────────────────────────────────────────────────────────────────────────

def _iter_fcurves(action, target_obj=None):
    try:
        from ..core.anim_compat import iter_fcurves as _ac
        yield from _ac(action, target_obj)
        return
    except Exception:
        pass
    if hasattr(action, "fcurves") and len(action.fcurves):
        for fc in action.fcurves:
            yield fc
        return
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            if strip.type != "KEYFRAME":
                continue
            try:
                bags = ([strip.channelbag(target_obj.animation_data.action_slot)]
                        if target_obj else list(strip.channelbags))
            except Exception:
                bags = list(getattr(strip, "channelbags", []))
            for bag in bags:
                if bag:
                    for fc in bag.fcurves:
                        yield fc


# ──────────────────────────────────────────────────────────────────────────────
#  FORMATTING + PATH PARSING
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_segment(seg: str) -> str:
    """underscores → spaces, Title Case, with acronym fix-ups (tf2 → TF2)."""
    s = seg.replace("_", " ").title()
    return " ".join(_ACRONYM_FIXUPS.get(w, w) for w in s.split())


def _parse_source_path(mesh_name: str):
    """
    Return the formatted collection chain from a SourceIO mesh name, or None.

    'tf2_enhanced\\foliage\\mediterranean\\asphodel_grass_a_enhanced.m_…smd_MESH'
      → ['TF2 Enhanced', 'Foliage', 'Mediterranean', 'Asphodel Grass A Enhanced']

    The path is split on backslashes; in the FINAL segment everything from the
    first dot onward is dropped (that's the SourceIO material/mesh suffix).
    """
    if mesh_name is None:
        return None
    # SourceIO uses Windows-style backslash separators in the baked name
    raw = mesh_name.replace("/", "\\")
    if "\\" not in raw:
        return None
    parts = [p for p in raw.split("\\") if p]
    if len(parts) < 2:
        return None
    leaf = parts[-1].split(".")[0]
    if not leaf:
        return None
    chain = [_fmt_segment(c) for c in parts[:-1] + [leaf]]
    out = []
    for seg in chain:
        if not out or out[-1] != seg:
            out.append(seg)
    return out


# ──────────────────────────────────────────────────────────────────────────────
#  CHARACTER MATCHING  (against HoovyTools/Faulty Rigs/)
# ──────────────────────────────────────────────────────────────────────────────

def _faulty_rigs_dir() -> Path:
    return _paths.faulty_rigs()


def _character_stems():
    """
    Return character stems from Faulty Rigs/*_reference.dmx, longest first so
    the most specific stem wins (heavy_toga_a before heavy).
    """
    folder = _faulty_rigs_dir()
    stems = []
    if folder.is_dir():
        for f in folder.glob("*_reference.dmx"):
            stem = f.stem
            if stem.endswith("_reference"):
                stem = stem[:-len("_reference")]
            if stem:
                stems.append(stem.lower())
    return sorted(set(stems), key=len, reverse=True)


def _match_character(rig_name: str, stems) -> str:
    """
    Return the matching character stem, or None.

    STRICT: the rig name must BE the stem or the stem followed only by an
    instance suffix (digits / separators) — e.g. 'scout', 'scout_1',
    'heavy.001'. A stem followed by MORE WORDS (alphabetic) is a cosmetic/prop,
    NOT the character, so it's rejected: 'heavy_hockeyhair1',
    'heavy_mages_mane_style_beard_a1' → None. Longest stem is tried first, so
    real variants with their own reference ('heavy_toga_a') still match.
    """
    n = (rig_name or "").lower()
    for stem in stems:                      # longest-first
        if not n.startswith(stem):
            continue
        rest = n[len(stem):]
        # accept end-of-name, or only separators + digits (an instance suffix)
        if rest == "" or re.fullmatch(r"[._]*\d*([._]\d+)*", rest):
            return stem
    return None


# ──────────────────────────────────────────────────────────────────────────────
#  COLLECTION HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _contains_collection(col, target, _seen=None):
    """Is *target* anywhere in *col*'s subtree? Guarded against cycles."""
    if _seen is None:
        _seen = set()
    if col in _seen:
        return False
    _seen.add(col)
    for child in col.children:
        if child is target or _contains_collection(child, target, _seen):
            return True
    return False


def _linked_anywhere(col):
    """True when *col* already hangs under some collection in the file."""
    if col.name in bpy.context.scene.collection.children:
        return True
    return any(col.name in c.children for c in bpy.data.collections
               if c is not col)


def _get_or_create_child(name: str, parent_col, color=None):
    """Get/create a collection named *name* as a child of *parent_col*."""
    #  A child called "name" or Blender's own "name.001" for it - a tree
    #  re-organized after a name clash must find its own copy again.
    existing = parent_col.children.get(name) or next(
        (c for c in parent_col.children
         if c.name.startswith(name + ".") and c.name[len(name) + 1:].isdigit()),
        None)
    if existing is not None:
        if color:
            existing.color_tag = color
        return existing
    #  Reuse a same-named collection ONLY if nothing else holds it. 1.16.0:
    #  collection names are global, so "TF2 Enhanced" made under __Models__
    #  was re-linked under __Props__ - one collection, two parents - and
    #  every building showed up as a prop. A collection already in some
    #  tree is someone else's; this tree gets its own ("TF2 Enhanced.001").
    col = bpy.data.collections.get(name)
    if col is not None and _linked_anywhere(col):
        col = None
    #  ...unless reusing it would make a CYCLE: the by-name lookup can
    #  return the parent itself (chain 'Axis'/'Axis') or an ancestor
    #  (leaf named like a folder higher up), and children.link() then
    #  raises and takes the whole Organize step down. A fresh collection
    #  (Blender names it 'Axis.001') is always safe.
    if col is not None and (col is parent_col
                            or _contains_collection(col, parent_col)):
        col = None
    if col is None:
        col = bpy.data.collections.new(name)
    if col.name not in parent_col.children:
        parent_col.children.link(col)
    if color:
        col.color_tag = color
    return col


def _ensure_root(name: str, color: str):
    """Get/create a scene-level root collection."""
    scene_col = bpy.context.scene.collection
    return _get_or_create_child(name, scene_col, color)


def _chain_collection(chain, root_col, leaf_color=None):
    """Create/return the nested collection for *chain* under *root_col*."""
    cur = root_col
    for i, seg in enumerate(chain):
        is_leaf = (i == len(chain) - 1)
        cur = _get_or_create_child(seg, cur, leaf_color if is_leaf else None)
    return cur


def _move_object(obj, target):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    if obj.name not in target.objects:
        target.objects.link(obj)


def _remove_collection_tree(col, protect_root=None):
    """
    Recursively remove *col* and its sub-collections IF they hold no objects
    anymore (after the rig's objects have been moved out). Never removes
    *protect_root* (the scene collection). Leaves non-empty collections intact.
    """
    if col is None or col is protect_root:
        return 0
    removed = 0
    for child in list(col.children):
        removed += _remove_collection_tree(child, protect_root)
    if len(col.objects) == 0 and len(col.children) == 0:
        try:
            bpy.data.collections.remove(col)
            removed += 1
        except Exception:
            pass
    return removed


def _prune_empty_collections():
    """Global sweep: remove any empty collections left under the scene root."""
    scene_col = bpy.context.scene.collection
    removed = 1
    total = 0
    while removed:
        removed = 0
        for col in list(bpy.data.collections):
            if col is scene_col:
                continue
            if col.name in (MODELS_ROOT, CHARACTERS_ROOT):
                continue
            if len(col.objects) == 0 and len(col.children) == 0:
                try:
                    bpy.data.collections.remove(col)
                    removed += 1
                    total += 1
                except Exception:
                    pass
    return total


def _unlink_collection_tree(root_name):
    """
    Unlink (from the scene) the root organizer collection and all its nested
    children, WITHOUT deleting the objects inside — objects revert to the scene
    collection so a fresh organize pass can re-sort them.
    """
    root = bpy.data.collections.get(root_name)
    if root is None:
        return 0

    scene_col = bpy.context.scene.collection
    moved = 0

    def _recurse(col):
        nonlocal moved
        for child in list(col.children):
            _recurse(child)
        for obj in list(col.objects):
            col.objects.unlink(obj)
            if obj.name not in scene_col.objects:
                scene_col.objects.link(obj)
            moved += 1
        # remove the now-empty collection
        try:
            bpy.data.collections.remove(col)
        except Exception:
            pass

    _recurse(root)
    return moved


# ──────────────────────────────────────────────────────────────────────────────
#  RIG DISCOVERY
# ──────────────────────────────────────────────────────────────────────────────

def _channel_motion_span(fc):
    """(first, last) frame where *fc* actually changes, or None if it never
    moves by more than PROP_EPS."""
    kps = fc.keyframe_points
    if len(kps) < 2:
        return None
    first = last = None
    v0 = kps[0].co[1]
    prev = v0
    for kp in kps:
        v = kp.co[1]
        if abs(v - prev) > PROP_EPS or abs(v - v0) > PROP_EPS:
            f = kp.co[0]
            first = f if first is None else min(first, f)
            last = f if last is None else max(last, f)
        prev = v
    if first is None:
        return None
    #  the move starts at the key BEFORE the first changed one
    i = next(i for i, kp in enumerate(kps) if kp.co[0] == first)
    start = kps[max(0, i - 1)].co[0]
    return (start, last)


def prop_motion(objs):
    """The longest single-bone (or root) motion span among *objs*, in frames,
    and what carried it. A rig's root motion lives on its root EMPTY in this
    importer, which in SFM is the root bone - so object-level animation on a
    rig member counts as a bone too."""
    from ..core import anim_compat
    best, who = 0.0, None
    for ob in objs:
        ad = getattr(ob, "animation_data", None)
        if ad is None or ad.action is None:
            continue
        spans = {}
        for fc in anim_compat.iter_fcurves(ad.action, ob):
            dp = fc.data_path
            if dp.startswith('pose.bones["'):
                key = dp.split('"')[1]
            elif dp in ("location", "rotation_quaternion", "rotation_euler",
                        "scale"):
                key = "(object %s)" % ob.name
            else:
                continue
            s = _channel_motion_span(fc)
            if s is None:
                continue
            lo, hi = spans.get(key, (s[0], s[1]))
            spans[key] = (min(lo, s[0]), max(hi, s[1]))
        for key, (lo, hi) in spans.items():
            if hi - lo > best:
                best, who = hi - lo, "%s: %s" % (ob.name, key)
    return best, who


def _iter_rigs():
    """Yield armature objects in the scene (each rig is an armature)."""
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE":
            yield obj


def _constraint_targets(obj):
    """Yield objects referenced by *obj*'s object-level and bone constraints."""
    for con in obj.constraints:
        for attr in ("target", "pole_target"):
            t = getattr(con, attr, None)
            if t is not None:
                yield t
    if obj.type == "ARMATURE" and obj.pose:
        for pbone in obj.pose.bones:
            for con in pbone.constraints:
                for attr in ("target", "pole_target"):
                    t = getattr(con, attr, None)
                    if t is not None:
                        yield t


def _rig_cluster(arm):
    """
    Fallback discovery when the rig isn't in its own SourceIO collection
    (e.g. on a rerun after objects were moved). Grows a connected component
    from the armature via parent chain, children, constraint targets, and
    armature-modifier links.
    """
    scene_objs = list(bpy.context.scene.objects)
    cluster = {arm}
    frontier = [arm]
    while frontier:
        obj = frontier.pop()
        if obj.parent is not None and obj.parent not in cluster:
            cluster.add(obj.parent); frontier.append(obj.parent)
        for child in obj.children:
            if child not in cluster:
                cluster.add(child); frontier.append(child)
        for t in _constraint_targets(obj):
            if t not in cluster:
                cluster.add(t); frontier.append(t)
        if obj.type == "MESH":
            for mod in obj.modifiers:
                mo = getattr(mod, "object", None)
                if mo is not None and mo not in cluster:
                    cluster.add(mo); frontier.append(mo)
        for other in scene_objs:
            if other in cluster or other.type != "MESH":
                continue
            for mod in other.modifiers:
                if getattr(mod, "object", None) in cluster:
                    cluster.add(other); frontier.append(other); break
    return list(cluster)


def _collection_all_objects(col):
    """All objects in *col* and every nested sub-collection (recursive, unique)."""
    seen = []
    stack = [col]
    visited = set()
    while stack:
        c = stack.pop()
        if c in visited:
            continue
        visited.add(c)
        for obj in c.objects:
            if obj not in seen:
                seen.append(obj)
        stack.extend(c.children)
    return seen


def _find_rig_collection(arm):
    """
    Find the SourceIO rig collection that owns this armature — the unit to move.

    SourceIO imports each rig into its own collection (e.g. 'scout_1') that
    holds the axis/root empties, the armature, the mesh sub-collection, the
    _ATTACHMENTS sub-collection, and the viewTarget empty (with its
    constraints). We want the TOP-MOST such collection under the scene root that
    contains the armature — moving that whole unit grabs everything at once.
    """
    scene_col = bpy.context.scene.collection

    # Build child -> parent map for all collections reachable from the scene.
    parent_of = {}
    stack = [scene_col]
    while stack:
        c = stack.pop()
        for ch in c.children:
            parent_of[ch] = c
            stack.append(ch)

    # Start from a collection that directly contains the armature (not the
    # scene root itself), then walk up until the parent is the scene root.
    start = None
    for c in arm.users_collection:
        if c is not scene_col:
            start = c
            break
    if start is None:
        return None

    cur = start
    while parent_of.get(cur) is not None and parent_of[cur] is not scene_col:
        cur = parent_of[cur]
    return cur


def _rig_source_path(members):
    """
    Find a SourceIO-style path among the cluster's objects, mesh-data names, AND
    the names of the collections they live in (SourceIO often names the mesh
    sub-collection with the path, e.g. 'tf2_enhanced\\foliage\\...').
    """
    # object + mesh-data names
    for obj in members:
        chain = _parse_source_path(obj.name)
        if chain:
            return chain
        if obj.type == "MESH" and obj.data is not None:
            chain = _parse_source_path(obj.data.name)
            if chain:
                return chain
    # collection names the objects belong to
    for obj in members:
        for col in obj.users_collection:
            chain = _parse_source_path(col.name)
            if chain:
                return chain
    return None


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────────────────────

def organize_scene(do_characters=True, do_models=True) -> dict:
    # rerunnable: tear down previous organizer trees first (objects preserved)
    cleared = _unlink_collection_tree(MODELS_ROOT)
    cleared += _unlink_collection_tree(CHARACTERS_ROOT)
    cleared += _unlink_collection_tree(PROPS_ROOT)
    for legacy in LEGACY_ROOTS:
        cleared += _unlink_collection_tree(legacy)
    if cleared:
        print(f"[ORGANIZE]  cleared previous organization ({cleared} object(s))")

    stems = _character_stems() if do_characters else []
    print(f"[ORGANIZE]  {len(stems)} character reference(s) in Faulty Rigs/")

    results = {"characters": [], "models": [], "props": [], "skipped": []}
    models_root = chars_root = props_root = None
    claimed = set()        # objects already assigned this pass
    source_cols = set()    # rig source collections to tear down afterward

    for arm in list(_iter_rigs()):
        # The rig already lives in its own SourceIO collection (e.g. 'scout_1')
        # holding the axis/root empties, armature, mesh + _ATTACHMENTS
        # sub-collections, and the viewTarget empty with its constraints.
        # Grab that whole collection's objects — this captures everything.
        rig_col = _find_rig_collection(arm)
        if rig_col is not None:
            members = _collection_all_objects(rig_col)
            source_cols.add(rig_col)
        else:
            # no dedicated source collection (e.g. rerun) — fall back to the
            # object-relationship cluster so we still grab root/axis/viewTarget
            members = _rig_cluster(arm)

        members = [o for o in members if o not in claimed]
        if arm not in members:
            members.append(arm)

        # ── character? (match armature name against Faulty Rigs stems) ──
        char = _match_character(arm.name, stems) if do_characters else None
        if char:
            if chars_root is None:
                chars_root = _ensure_root(CHARACTERS_ROOT, COLOR_CHARS)
            # Nest by character TYPE then INSTANCE so multiple rigs of the same
            # character don't collapse into one folder:
            #   ___Characters___ / Scout / scout_1
            #   ___Characters___ / Scout / scout_2
            # If the rig name IS just the bare stem (single instance), the
            # instance folder equals the type and we don't double-nest.
            type_name = _fmt_segment(char)
            inst_name = arm.name
            chain = [type_name] if inst_name.lower() == char.lower() else \
                    [type_name, inst_name]
            leaf = _chain_collection(chain, chars_root, COLOR_CHARS)
            for obj in members:
                _move_object(obj, leaf)
                claimed.add(obj)
            results["characters"].append((arm.name, " / ".join(chain)))
            print(f"[ORGANIZE]  CHAR  '{arm.name}' -> {CHARACTERS_ROOT}/{' / '.join(chain)}")
            continue

        # ── path-based model - or a PROP, if one of its bones really moves ──
        if do_models:
            chain = _rig_source_path(members)
            if chain:
                span, mover = prop_motion(members)
                if span >= PROP_MIN_FRAMES:
                    if props_root is None:
                        props_root = _ensure_root(PROPS_ROOT, COLOR_PROPS)
                    leaf = _chain_collection(chain, props_root, COLOR_PROPS)
                    for obj in members:
                        _move_object(obj, leaf)
                        claimed.add(obj)
                    results["props"].append((arm.name, " / ".join(chain)))
                    print(f"[ORGANIZE]  PROP  '{arm.name}' -> {PROPS_ROOT}/"
                          f"{' / '.join(chain)}  ({span:.0f} frames on {mover})")
                    continue
                if models_root is None:
                    models_root = _ensure_root(MODELS_ROOT, COLOR_MODELS)
                leaf = _chain_collection(chain, models_root, COLOR_MODELS)
                for obj in members:
                    _move_object(obj, leaf)
                    claimed.add(obj)
                results["models"].append((arm.name, " / ".join(chain)))
                print(f"[ORGANIZE]  MODEL '{arm.name}' -> {MODELS_ROOT}/{' / '.join(chain)}")
                continue

        # ── couldn't classify — leave it, report it ──
        results["skipped"].append(arm.name)
        print(f"[ORGANIZE]  SKIP  '{arm.name}' (no character match, no parseable path)")

    # tear down the emptied SourceIO source collections, then sweep up any
    # other empties left behind — so we don't leave hundreds of stale folders.
    scene_col = bpy.context.scene.collection
    for col in source_cols:
        _remove_collection_tree(col, protect_root=scene_col)
    pruned = _prune_empty_collections()
    if pruned:
        print(f"[ORGANIZE]  pruned {pruned} empty collection(s)")

    return results


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_OrganizeScene(Operator):
    """Sort imported rigs into nested collections by model path

Walks every SourceIO-imported armature, works out which .mdl it came
from, and files it under a characters or models collection tree that
mirrors the source path.

A session import drops dozens of objects into one flat list; this makes
the outliner navigable again. Rigs whose source path cannot be determined
are left where they are and reported, never moved somewhere wrong"""
    bl_idname  = "ht.organize_scene"
    bl_label   = "Organize Scene"
    bl_options = {"REGISTER", "UNDO"}

    do_characters: BoolProperty(
        name="Sort Characters",
        description="Route rigs matching a Faulty Rigs reference into "
                    "___Characters___",
        default=True,
    )
    do_models: BoolProperty(
        name="Sort Models By Path",
        description="Route remaining rigs into ___Models___ by their SourceIO "
                    "import path",
        default=True,
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "do_characters")
        col.prop(self, "do_models")

    def execute(self, context):
        try:
            res = organize_scene(do_characters=self.do_characters,
                                 do_models=self.do_models)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        nc, nm, ns = (len(res["characters"]), len(res["models"]), len(res["skipped"]))
        lines = [
            f"Characters : {nc}  -> {CHARACTERS_ROOT}",
            f"Models     : {nm}  -> {MODELS_ROOT}",
            f"Props      : {len(res.get('props', []))}  -> {PROPS_ROOT}"
            f"  (a bone moving for {PROP_MIN_FRAMES}+ frames)",
        ]
        if ns:
            lines.append(f"Skipped    : {ns} (no path / no match)")
            lines.append("─" * 40)
            for name in res["skipped"][:12]:
                lines.append(f"  • {name}")

        from ..core import Report_UI
        Report_UI.report(
            context, "utils_misc",
            f"Organize Scene - {nc + nm} rig(s) sorted", lines,
            level=('WARNING' if ns else 'INFO'),
            icon=("OUTLINER" if not ns else "INFO"), operator=self,
            prefix="ORGANIZE",
            summary=f"Organize Scene - {nc + nm} rig(s) sorted, "
                    f"{ns} skipped")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  EPSILON FILTER  (keyframe decimation — rotation + shape keys only)
# ──────────────────────────────────────────────────────────────────────────────

def _rdp_keep(frames, values, eps):
    """Keep indices so the linear curve never deviates from samples by > eps."""
    n = len(frames)
    if n <= 2:
        return set(range(n))
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        fa, va = frames[a], values[a]
        fb, vb = frames[b], values[b]
        span = (fb - fa) or 1.0
        max_dev, idx = -1.0, -1
        for i in range(a + 1, b):
            t = (frames[i] - fa) / span
            lin = va + (vb - va) * t
            dev = abs(values[i] - lin)
            if dev > max_dev:
                max_dev, idx = dev, i
        if max_dev > eps and idx != -1:
            keep[idx] = True
            stack.append((a, idx)); stack.append((idx, b))
    return set(i for i, k in enumerate(keep) if k)


def _quat_angle(qa, qb):
    dot = abs(qa[0]*qb[0] + qa[1]*qb[1] + qa[2]*qb[2] + qa[3]*qb[3])
    return math.degrees(2.0 * math.acos(min(dot, 1.0)))


def _rdp_keep_quat(frames, quats, eps_deg):
    """RDP on orientation: deviation = angle between actual and slerped quat."""
    n = len(frames)
    if n <= 2:
        return set(range(n))
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        qa = Quaternion(quats[a]); qb = Quaternion(quats[b])
        fa, fb = frames[a], frames[b]
        span = (fb - fa) or 1.0
        max_dev, idx = -1.0, -1
        for i in range(a + 1, b):
            t = max(0.0, min(1.0, (frames[i] - fa) / span))
            lp = qa.slerp(qb, t)
            dev = _quat_angle(quats[i], (lp.w, lp.x, lp.y, lp.z))
            if dev > max_dev:
                max_dev, idx = dev, i
        if max_dev > eps_deg and idx != -1:
            keep[idx] = True
            stack.append((a, idx)); stack.append((idx, b))
    return set(i for i, k in enumerate(keep) if k)


def _trim_fcurve(fc, keep):
    kps = fc.keyframe_points
    survivors = [(kp.co[0], kp.co[1], kp.interpolation)
                 for i, kp in enumerate(kps) if i in keep]
    removed = len(kps) - len(survivors)
    if removed <= 0:
        return 0
    for i in range(len(kps) - 1, -1, -1):
        kps.remove(kps[i])
    for (fr, val, interp) in survivors:
        nkp = kps.insert(fr, val, options={"FAST"})
        nkp.interpolation = interp
    fc.update()
    return removed


def _simplify_rotation_and_shapekeys(action, owner, eps_rot, eps_sk,
                                     diag=None, do_armatures=True,
                                     do_shapekeys=True):
    """
    Simplify rotation (quaternion OR euler) and shape-key 'value' curves.
    Location/scale are left untouched (rotation-only = fast). Returns
    (keys_before_on_processed_curves, keys_removed).

    do_armatures : process rotation_quaternion / rotation_euler curves.
    do_shapekeys : process shape-key 'value' curves.
    Either can be disabled to restrict the filter to one domain.

    Quaternion curves are grouped PER DATA-PATH (per bone) and simplified by
    orientation angle. Euler rotation curves are simplified per-component with
    the rotation epsilon converted to radians (since SourceIO/SFM rigs are
    frequently euler, not quaternion). If *diag* (a set) is passed, every
    distinct data_path seen is added to it for troubleshooting.
    """
    fcurves = list(_iter_fcurves(action, owner))
    quat_groups = {}     # data_path -> {array_index: fcurve}
    euler_curves = []
    value_curves = []
    for fc in fcurves:
        dp = fc.data_path
        if diag is not None:
            diag.add(dp.rsplit(".", 1)[-1])   # record the leaf token
        if dp.endswith("rotation_quaternion"):
            quat_groups.setdefault(dp, {})[fc.array_index] = fc
        elif dp.endswith("rotation_euler"):
            euler_curves.append(fc)
        elif dp.endswith("value"):
            value_curves.append(fc)

    before = removed = 0
    eps_rot_rad = math.radians(eps_rot)

    # ── quaternion bones (4 components together, orientation angle) ──
    if do_armatures:
        for dp, comps in quat_groups.items():
            if len(comps) != 4:
                continue
            fcs = [comps[i] for i in range(4)]
            before += sum(len(fc.keyframe_points) for fc in fcs)
            npts = min(len(fc.keyframe_points) for fc in fcs)
            if npts < 3:
                continue
            frames = [fcs[0].keyframe_points[i].co[0] for i in range(npts)]
            quats  = [tuple(fcs[c].keyframe_points[i].co[1] for c in range(4))
                      for i in range(npts)]
            keep = _rdp_keep_quat(frames, quats, eps_rot)
            for fc in fcs:
                removed += _trim_fcurve(fc, keep)

    # ── euler rotation (per-component, eps in radians) ──
    if do_armatures:
        for fc in euler_curves:
            kps = fc.keyframe_points
            before += len(kps)
            frames = [kp.co[0] for kp in kps]
            values = [kp.co[1] for kp in kps]
            keep = _rdp_keep(frames, values, eps_rot_rad)
            removed += _trim_fcurve(fc, keep)

    # ── shape-key value curves ──
    if do_shapekeys:
        for fc in value_curves:
            kps = fc.keyframe_points
            before += len(kps)
            frames = [kp.co[0] for kp in kps]
            values = [kp.co[1] for kp in kps]
            keep = _rdp_keep(frames, values, eps_sk)
            removed += _trim_fcurve(fc, keep)

    return before, removed


def _has_biped_bones(arm):
    """True if the armature contains ANY of the SKIP_IF_BONES (character rig)."""
    if arm.type != "ARMATURE" or arm.data is None:
        return False
    bone_names = {b.name.lower() for b in arm.data.bones}
    targets = {b.lower() for b in SKIP_IF_BONES}
    return bool(bone_names & targets)


def _process_mesh_shapekeys(mesh, eps_sk, diag=None, do_shapekeys=True):
    """Simplify a mesh's shape-key 'value' curves. Returns (before, removed)."""
    if not do_shapekeys:
        return 0, 0
    sk = mesh.data.shape_keys if mesh.data else None
    if sk and sk.animation_data and sk.animation_data.action:
        # eps_rot is irrelevant here (no rotation on shape-key actions); pass 0.
        # do_armatures=False since a shape-key action has no rotation curves.
        return _simplify_rotation_and_shapekeys(
            sk.animation_data.action, sk, 0.0, eps_sk, diag=diag,
            do_armatures=False, do_shapekeys=True)
    return 0, 0


def _connected_meshes(arm):
    out = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if obj.parent is arm:
            out.append(obj); continue
        for mod in obj.modifiers:
            if getattr(mod, "object", None) is arm:
                out.append(obj); break
    return out


def reduce_lag(eps_rot=EPS_ROTATION, eps_sk=EPS_SHAPEKEY,
               skip_faulty=False, skip_biped=True, only_selected=False,
               do_armatures=True, do_shapekeys=True) -> dict:
    """Epsilon-filter armatures (rotation + shape keys).

    only_selected=False : every armature in the scene.
    only_selected=True  : only selected armatures (their attached shape-key
                          meshes are processed regardless, since the filter
                          gathers them via _connected_meshes).
    do_armatures : process bone rotation curves (quaternion/euler).
    do_shapekeys : process shape-key 'value' curves.
    Both default True (= unchanged behaviour); untick one to do only the other.
    """
    if only_selected:
        arms = [o for o in bpy.context.selected_objects if o.type == "ARMATURE"]
        sel_meshes = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    else:
        arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
        sel_meshes = []
    if not arms and not sel_meshes:
        msg = ("no armature or mesh selected" if only_selected
               else "no armature in scene")
        print(f"[EPSILON]  Nothing to do — {msg}.")
        return {"models": 0, "skipped": 0, "skipped_biped": 0,
                "before": 0, "removed": 0, "diag": [], "empty_reason": msg}
    if not do_armatures and not do_shapekeys:
        msg = "both priority toggles off — nothing to process"
        print(f"[EPSILON]  Nothing to do — {msg}.")
        return {"models": 0, "skipped": 0, "skipped_biped": 0,
                "before": 0, "removed": 0, "diag": [], "empty_reason": msg}
    stems = _character_stems() if skip_faulty else []

    processed = skipped = 0
    skipped_biped = 0
    total_before = total_removed = 0
    diag = set()   # distinct data_path tokens seen, for troubleshooting

    scope = "selected" if only_selected else "scene"
    print(f"\n[EPSILON]  {'='*50}")
    print(f"[EPSILON]  {len(arms)} armature(s)"
          + (f" + {len(sel_meshes)} mesh(es)" if sel_meshes else "")
          + f" [{scope}]  (skip_faulty={skip_faulty}, skip_biped={skip_biped}, "
          + f"armatures={do_armatures}, shapekeys={do_shapekeys})")

    done_meshes = set()   # meshes whose shape keys were already processed

    for arm in arms:
        if skip_faulty and _match_character(arm.name, stems):
            skipped += 1
            print(f"[EPSILON]  SKIP (faulty) '{arm.name}'")
            continue

        # skip character rigs detected by their biped skeleton bones
        if skip_biped and _has_biped_bones(arm):
            skipped_biped += 1
            print(f"[EPSILON]  SKIP (biped bones) '{arm.name}'")
            continue

        rb = rr = 0
        ad = arm.animation_data
        if ad and ad.action:
            b, r = _simplify_rotation_and_shapekeys(
                ad.action, arm, eps_rot, eps_sk, diag=diag,
                do_armatures=do_armatures, do_shapekeys=do_shapekeys)
            rb += b; rr += r
        for mesh in _connected_meshes(arm):
            b, r = _process_mesh_shapekeys(mesh, eps_sk, diag=diag,
                                           do_shapekeys=do_shapekeys)
            rb += b; rr += r
            done_meshes.add(mesh.name)

        processed += 1
        total_before += rb; total_removed += rr
        pct = (100.0 * rr / rb) if rb else 0.0
        print(f"[EPSILON]  '{arm.name}': {rr}/{rb} keys removed ({pct:.1f}%)")

    # ── directly-selected meshes → shape keys only ───────────────────────────
    # (a mesh already handled via its armature above is skipped to avoid
    #  double-processing)
    for mesh in sel_meshes:
        if mesh.name in done_meshes:
            continue
        b, r = _process_mesh_shapekeys(mesh, eps_sk, diag=diag,
                                       do_shapekeys=do_shapekeys)
        if b == 0:
            print(f"[EPSILON]  mesh '{mesh.name}': no shape-key animation")
            continue
        done_meshes.add(mesh.name)
        processed += 1
        total_before += b; total_removed += r
        pct = (100.0 * r / b) if b else 0.0
        print(f"[EPSILON]  mesh '{mesh.name}' (shape keys): "
              f"{r}/{b} keys removed ({pct:.1f}%)")

    pct = (100.0 * total_removed / total_before) if total_before else 0.0
    print(f"[EPSILON]  processed {processed} model(s), "
          f"skipped {skipped} (faulty) + {skipped_biped} (biped) — "
          f"{total_removed}/{total_before} keys removed ({pct:.1f}%)")
    if total_before == 0 and processed:
        print(f"[EPSILON]  NOTE: 0 curves matched. data_path tokens seen: "
              f"{sorted(diag) if diag else '(none — no actions found)'}")
        print(f"[EPSILON]  (filter handles rotation_quaternion, rotation_euler, "
              f"and shape-key 'value' — anything else is intentionally ignored)")
    return {"models": processed, "skipped": skipped,
            "skipped_biped": skipped_biped,
            "before": total_before, "removed": total_removed,
            "diag": sorted(diag)}


class HT_OT_ReduceLagEpsilon(Operator):
    """Thin out keyframes on every rig in the scene, within a tolerance

SFM exports are dense - thousands of keys per curve, most of them
indistinguishable from their neighbours. This removes keys whose value is
within the epsilon of what interpolation would have produced anyway, on
rotation curves and shape keys.

The point is viewport responsiveness on a heavy session. Raise the
epsilon for a bigger reduction and a looser curve.

Faulty rigs are skipped rather than risked, and the report gives the
before and after counts so you can see what it cost"""
    bl_idname  = "ht.reduce_lag_epsilon"
    bl_label   = "Reduce Lag With Epsilon Filter"
    bl_options = {"REGISTER", "UNDO"}

    eps_rotation: FloatProperty(
        name="Rotation Epsilon (°)",
        description="Keep a rotation keyframe only if dropping it would change "
                    "the orientation by more than this many degrees",
        default=EPS_ROTATION, min=0.0, max=45.0,
    )
    eps_shapekey: FloatProperty(
        name="Shape Key Epsilon",
        description="Keep a shape-key keyframe only if dropping it would change "
                    "the influence (0..1) by more than this",
        default=EPS_SHAPEKEY, min=0.0, max=1.0,
    )
    do_armatures: BoolProperty(
        name="Process Armatures (Rotation)",
        description="Simplify bone rotation curves (quaternion / euler). "
                    "Untick to process shape keys only",
        default=True,
    )
    do_shapekeys: BoolProperty(
        name="Process Shape Keys",
        description="Simplify shape-key value curves. "
                    "Untick to process armature rotation only",
        default=True,
    )
    skip_faulty: BoolProperty(
        name="Skip Faulty Rigs",
        description="Don't process rigs matching a Faulty Rigs reference",
        default=False,
    )
    skip_biped: BoolProperty(
        name="Skip Biped Rigs",
        description="Don't process armatures that contain TF2/HL2 biped bones "
                    "(bip_spine_0, bip_pelvis, bip_head, bip_neck, "
                    "bip_lowerArm_L) — i.e. character rigs",
        default=True,
    )
    only_selected: BoolProperty(
        name="Only Process Selected Rigs",
        description="Process only the selection instead of the whole scene. "
                    "Selected armatures get rotation + their attached shape "
                    "keys; a selected mesh gets ONLY its shape keys processed",
        default=False,
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "eps_rotation")
        col.prop(self, "eps_shapekey")
        col.separator()
        col.label(text="Process:")
        row = col.row(align=True)
        row.prop(self, "do_armatures", toggle=True)
        row.prop(self, "do_shapekeys", toggle=True)
        if not self.do_armatures and not self.do_shapekeys:
            col.label(text="Nothing selected to process", icon="ERROR")
        col.separator()
        col.prop(self, "only_selected")
        col.prop(self, "skip_faulty")
        col.prop(self, "skip_biped")

    def execute(self, context):
        try:
            res = reduce_lag(eps_rot=self.eps_rotation, eps_sk=self.eps_shapekey,
                             skip_faulty=self.skip_faulty,
                             skip_biped=self.skip_biped,
                             only_selected=self.only_selected,
                             do_armatures=self.do_armatures,
                             do_shapekeys=self.do_shapekeys)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if res.get("empty_reason"):
            self.report({"WARNING"}, f"Epsilon filter: {res['empty_reason']}.")
            return {"CANCELLED"}

        pct = (100.0 * res["removed"] / res["before"]) if res["before"] else 0.0
        lines = [
            f"Models processed : {res['models']}",
            f"Skipped (faulty) : {res['skipped']}",
            f"Skipped (biped)  : {res.get('skipped_biped', 0)}",
            f"Keys removed     : {res['removed']} / {res['before']}  ({pct:.1f}%)",
        ]
        from ..core import Report_UI
        Report_UI.report(
            context, "utils_misc",
            f"Epsilon Filter - {res['models']} model(s)", lines, level='INFO',
            operator=self, prefix="EPSILON",
            summary=f"Epsilon Filter - {res['models']} model(s), "
                    f"{res['removed']} key(s) removed")
        return {"FINISHED"}



_TAU = 2.0 * math.pi
_PI = math.pi

#  A wrap worth fixing is most of a full turn. 180 is the theoretical boundary
#  but a real 180-degree step between two keys is legitimate on a fast spin, so
#  this sits well above it. Only used by the WRAP pass - the gimbal-flip pass
#  has its own test and does not look at this at all.
EULER_JUMP_THRESHOLD_DEG = 300.0


def _curve_groups(action, target, suffix):
    """{data_path: {array_index: fcurve}} for one rotation kind.

    GROUPED BY DATA PATH because a rotation is its channels TOGETHER. Handling
    `pose.bones["head"].rotation_quaternion` one array index at a time is
    meaningless - the sign flip is a property of the four of them.
    """
    from ..core import anim_compat
    out = {}
    for fc in anim_compat.iter_fcurves(action, target):
        try:
            path = fc.data_path
        except Exception:
            continue
        if not path.endswith(suffix):
            continue
        out.setdefault(path, {})[fc.array_index] = fc
    return out


def _aligned_keys(fcs, count):
    """[(frame, [kp, ...])] for frames present in EVERY channel.

    MATCHED BY FRAME, NOT BY INDEX. The camera importer's version bailed out
    when the four channels had different key counts, which is the case a
    partially hand-edited curve produces - and bailing means the rig keeps its
    spin. Matching on the frame number handles it, and a channel missing a key
    at some frame simply means that frame is not processed.
    """
    if len(fcs) != count:
        return []
    tables = []
    for i in range(count):
        kps = fcs[i].keyframe_points
        tables.append({round(kp.co[0], 4): kp for kp in kps})
    common = set(tables[0])
    for t in tables[1:]:
        common &= set(t)
    return [(f, [t[f] for t in tables]) for f in sorted(common)]


def _shift_key(kp, delta):
    """Move a key's value, taking its handles with it."""
    kp.co[1] += delta
    kp.handle_left[1] += delta
    kp.handle_right[1] += delta


def _negate_key(kp):
    kp.co[1] = -kp.co[1]
    kp.handle_left[1] = -kp.handle_left[1]
    kp.handle_right[1] = -kp.handle_right[1]


def _unflip_quaternions(fcs):
    """Pass 1 - negate keys whose quaternion faces the other way.

    Returns (keys_flipped, worst_degrees_removed).
    """
    rows = _aligned_keys(fcs, 4)
    if len(rows) < 2:
        return 0, 0.0

    flipped = 0
    worst = 0.0
    prev = [kp.co[1] for kp in rows[0][1]]
    for _frame, kps in rows[1:]:
        curr = [kp.co[1] for kp in kps]
        dot = sum(a * b for a, b in zip(prev, curr))
        if dot < 0.0:
            for kp in kps:
                _negate_key(kp)
            curr = [-v for v in curr]
            flipped += 1
            #  How far the interpolation was travelling that it now will not.
            #  2*acos(|dot|) is the angle between the two orientations; the
            #  wrong-signed path is 360 minus that.
            ang = 2.0 * math.degrees(math.acos(min(1.0, abs(dot))))
            worst = max(worst, 360.0 - ang)
        prev = curr

    for fc in fcs.values():
        fc.update()
    return flipped, worst


def _euler_alternative(x, y, z):
    """The other euler triple for the same orientation."""
    return (x + _PI, _PI - y, z + _PI)


def _dist(a, b):
    return sum(abs(p - q) for p, q in zip(a, b))


def _unflip_eulers(fcs):
    """Pass 2 - the 180-on-every-axis gimbal flip.

    (x, y, z) and (x+180, 180-y, z+180) are the same orientation, so a
    conversion that picks per frame with no memory can jump by 180 on all
    three at once. No single channel moves 300 degrees, so the wrap pass
    below cannot see it. Whichever triple is nearer the previous frame wins.
    """
    rows = _aligned_keys(fcs, 3)
    if len(rows) < 2:
        return 0, 0.0

    flipped = 0
    worst = 0.0
    prev = tuple(kp.co[1] for kp in rows[0][1])
    for _frame, kps in rows[1:]:
        curr = tuple(kp.co[1] for kp in kps)
        alt = _euler_alternative(*curr)
        #  Compare AFTER unwrapping each candidate to the previous frame, or
        #  the winner is decided by an arbitrary multiple of 360 rather than
        #  by which pose is actually nearer.
        cur_u = tuple(v - _TAU * round((v - p) / _TAU)
                      for v, p in zip(curr, prev))
        alt_u = tuple(v - _TAU * round((v - p) / _TAU)
                      for v, p in zip(alt, prev))
        if _dist(alt_u, prev) < _dist(cur_u, prev) - 1e-9:
            for kp, new in zip(kps, alt_u):
                _shift_key(kp, new - kp.co[1])
            worst = max(worst, math.degrees(_dist(cur_u, prev)
                                            - _dist(alt_u, prev)))
            flipped += 1
            prev = alt_u
        else:
            prev = cur_u
    for fc in fcs.values():
        fc.update()
    return flipped, worst


def _unwrap_fcurve(fc, threshold):
    """Pass 3 - rewrite one channel so consecutive keys never jump a turn.

    Returns (keys_shifted, largest_spin_removed_in_degrees).
    """
    kps = fc.keyframe_points
    if len(kps) < 2:
        return 0, 0.0

    shifted = 0
    worst = 0.0
    offset = 0.0                      # accumulated correction, radians
    prev = kps[0].co[1]

    for kp in kps[1:]:
        raw = kp.co[1]
        delta = (raw + offset) - prev
        if abs(delta) > threshold:
            #  Round to the NEAREST whole turn rather than adding one. A
            #  double wrap shows up on bakes of fast spins, and a single-step
            #  fix would leave half of it behind.
            turns = round(delta / _TAU)
            if turns:
                offset -= turns * _TAU
                worst = max(worst, abs(turns) * 360.0)
        newval = raw + offset
        if newval != raw:
            _shift_key(kp, newval - raw)
            shifted += 1
        prev = newval

    if shifted:
        fc.update()
    return shifted, worst


def _repair_camera_flips(action, obj, path, fcs, kind):
    """1.17.3 - put back a camera frame that 1.17.2 baked turned the wrong way.

    1.17.2 blended a camera's quaternion NUMBERS between SFM samples; across a
    sign change that put one frame up to 180 degrees off (his armor vlk babe3_
    camera1: 180 at f1830). Negating keys - pass 1 - cannot fix it: that frame's
    POSE is wrong. A frame turned at least SPIKE_MIN_DEG from both neighbours
    while they agree, with the position running straight through, gets the
    neighbours' slerp. Imported cameras only (camera_owner). Returns (keys,
    worst degrees)."""
    from mathutils import Euler
    from ..core import camera_resample as CR
    n = 4 if kind == "quaternion" else 3
    rows = _aligned_keys(fcs, n)
    if len(rows) < 3:
        return 0, 0.0
    if path.startswith('pose.bones["'):
        owner = obj.pose.bones.get(path.split('"')[1]) if obj.pose else None
    else:
        owner = obj
    order = getattr(owner, "rotation_mode", "XYZ")
    if order not in CR.ORDERS:
        order = "XYZ"
    keys = []
    for f, kps in rows:
        vals = [kp.co[1] for kp in kps]
        keys.append((f, CR.quat(vals) if n == 4 else Euler(vals, order).to_quaternion()))
    base = path[:-len("rotation_quaternion" if n == 4 else "rotation_euler")]
    loc = _curve_groups(action, obj, "location").get(base + "location", {})
    positions = None
    if all(i in loc for i in range(3)):
        positions = {f: tuple(loc[i].evaluate(f) for i in range(3)) for f, _q in keys}
    flips = CR.one_frame_flips(keys, positions)
    worst = 0.0
    for i, _f, deg in flips:
        q = CR.repaired(keys, i)
        kps = rows[i][1]
        if n == 4:
            if q.dot(keys[i - 1][1]) < 0.0:
                q = CR.neg(q)
            new = [q[c] for c in range(4)]
        else:
            prev = Euler([kp.co[1] for kp in rows[i - 1][1]], order)
            e = q.to_euler(order, prev)
            new = [e[c] for c in range(3)]
        for kp, v in zip(kps, new):
            _shift_key(kp, v - kp.co[1])
        keys[i] = (keys[i][0], q)
        worst = max(worst, deg)
    if flips:
        for fc in fcs.values():
            fc.update()
    return len(flips), worst


def _rotation_order(obj, path):
    """The Euler order of whoever owns `path` (a pose bone or the object)."""
    from ..core import camera_resample as CR
    owner = obj
    if path.startswith('pose.bones["'):
        owner = obj.pose.bones.get(path.split('"')[1]) if obj.pose else None
    order = getattr(owner, "rotation_mode", "XYZ")
    return order if order in CR.ORDERS else "XYZ"


def _cut_frames(obj):
    """Frames the camera importer stamped as cuts (`ht_cut_frames`) on this
    object or any parent - the rig copies the root's stamps, the axis empty
    may hold them. A spin is never rebuilt across a cut."""
    out = []
    ob = obj
    while ob is not None:
        try:
            out += [float(f) for f in ob.get("ht_cut_frames", ())]
        except Exception:                                     # noqa: BLE001
            pass
        ob = ob.parent
    return out


def _rebuild_baked_spins(action, obj, path, fcs, kind, frame_range=None,
                         spike_deg=None, max_window=None, pad=None,
                         interp="SMOOTH"):
    """Pass 2 (1.22.0) - BAKED SPINS: baked keys that turn a full 360 over a
    few frames. The window is rebuilt along the short arc (core/spin_rebuild)
    and every key after it is carried by whole turns (Euler) or walked to the
    same side (quaternion), so nothing after the window moves.

    Returns (keys_rewritten, worst_degrees, [spin dicts], [left-alone dicts])."""
    from mathutils import Euler
    from ..core import spin_rebuild as SR
    n = 4 if kind == "quaternion" else 3
    rows = _aligned_keys(fcs, n)
    if len(rows) < 3:
        return 0, 0.0, [], []
    order = _rotation_order(obj, path)
    frames = [f for f, _kps in rows]
    vals = [[kp.co[1] for kp in kps] for _f, kps in rows]
    quats = [SR.quat(v) if n == 4 else Euler(v, order).to_quaternion() for v in vals]

    suffix = "rotation_quaternion" if n == 4 else "rotation_euler"
    loc = _curve_groups(action, obj, "location").get(path[:-len(suffix)] + "location", {})
    positions = None
    if all(i in loc for i in range(3)):
        positions = {f: tuple(loc[i].evaluate(f) for i in range(3)) for f in frames}

    kw = {}
    if spike_deg is not None:
        kw["spike_deg"] = float(spike_deg)
    if max_window is not None:
        kw["max_window"] = float(max_window)
    if pad is not None:
        kw["pad"] = int(pad)
    found = SR.find_spins(frames, quats, positions, _cut_frames(obj), frame_range, **kw)
    if not found["spins"]:
        return 0, 0.0, [], found["left"]

    new_q = {}
    for sp in found["spins"]:
        how = interp if sp.get("grown", True) else "LINEAR"   # a lone flipped frame: neighbours' slerp
        for i, q in SR.rebuild(frames, quats, sp["a"], sp["b"], how):
            new_q[i] = q
    first = min(new_q)

    written = 0
    if n == 3:
        prev = Euler(vals[first - 1], order)
        carry = None             # whole turns carried into the keys after a window
        for i in range(first, len(rows)):
            if i in new_q:
                e = new_q[i].to_euler(order, prev)
                new = [e[c] for c in range(3)]
                carry = None
            else:
                if carry is None:
                    e = quats[i].to_euler(order, prev)
                    d = [e[c] - vals[i][c] for c in range(3)]
                    if all(abs(x - _TAU * round(x / _TAU)) < 1e-4 for x in d):
                        carry = [_TAU * round(x / _TAU) for x in d]
                    else:
                        carry = "convert"        # landed on the gimbal twin
                if carry == "convert":
                    e = quats[i].to_euler(order, prev)
                    new = [e[c] for c in range(3)]
                else:
                    new = [vals[i][c] + carry[c] for c in range(3)]
            moved = False
            for kp, v in zip(rows[i][1], new):
                if abs(v - kp.co[1]) > 1e-9:
                    _shift_key(kp, v - kp.co[1])
                    moved = True
            written += moved
            prev = Euler(new, order)
    else:
        prev = Quaternion(vals[first - 1])
        for i in range(first, len(rows)):
            kps = rows[i][1]
            if i in new_q:
                q = new_q[i]
                if prev.dot(q) < 0.0:
                    q = Quaternion((-q[0], -q[1], -q[2], -q[3]))
                for kp, v in zip(kps, q):
                    _shift_key(kp, v - kp.co[1])
                written += 1
            else:
                q = Quaternion([kp.co[1] for kp in kps])
                if prev.dot(q) < 0.0:
                    for kp in kps:
                        _negate_key(kp)
                    q = Quaternion((-q[0], -q[1], -q[2], -q[3]))
                    written += 1
            prev = q
    for fc in fcs.values():
        fc.update()
    worst = max(sp["worst"] for sp in found["spins"])
    return written, worst, found["spins"], found["left"]


def _selected_bone_paths(obj):
    """{'pose.bones["name"].'} for the selected bones of an armature in Pose
    Mode, or None when the whole object is in scope (Object Mode)."""
    if obj.type != 'ARMATURE' or obj.mode != 'POSE' or not obj.pose:
        return None
    out = set()
    for pb in obj.pose.bones:
        try:
            sel = pb.select                       # 5.x: selection is on the pose bone
        except AttributeError:
            sel = pb.bone.select
        if sel:
            out.add('pose.bones["%s"].' % pb.name)
    return out


def delete_euler_spins(only_selected=False, include_objects=True,
                       threshold_deg=EULER_JUMP_THRESHOLD_DEG,
                       do_quaternions=True, do_eulers=True,
                       do_camera_flips=True, do_baked_spins=True,
                       selected_bones_only=False, frame_range=None,
                       spike_deg=None, max_window=None, pad=None,
                       interp="SMOOTH"):
    """Unwrap every rotation curve in scope. Returns a summary dict.

    `include_objects` covers OBJECT-level rotation as well as pose bones: an
    imported camera, light or static prop is animated on the object, and those
    flip for exactly the same reason.

    1.22.0: `selected_bones_only` - an armature in Pose Mode is cut down to
    its selected bones (its object-level curves are left alone); `frame_range`
    (start, end) limits the BAKED SPINS pass to spins inside it; the baked-spin
    knobs default to core/spin_rebuild's constants.
    """
    threshold = math.radians(max(1.0, float(threshold_deg)))

    objs = (list(bpy.context.selected_objects) if only_selected
            else list(bpy.context.scene.objects))
    if only_selected and selected_bones_only:
        #  The armature you are posing is the active object even when its
        #  object is not selected (Pose Mode lets you tab in that way).
        act = bpy.context.view_layer.objects.active
        if act is not None and act.mode == 'POSE' and act not in objs:
            objs.append(act)
    if not objs:
        return {"empty_reason": "nothing selected", "scanned": 0, "objects": 0,
                "curves": 0, "keys": 0, "quats": 0, "gimbals": 0, "wraps": 0,
                "camera_flips": 0, "baked_spins": 0, "baked_keys": 0,
                "worst": 0.0, "names": [], "spins": [], "left": []}

    #  One action can be shared by several objects. Unwrapping it twice is
    #  harmless - the second pass finds nothing - but it would double-count in
    #  the report, and a report that overstates is one nobody trusts next time.
    seen = set()
    touched_objs = curves = keys = 0
    quats = gimbals = wraps = cam_flips = baked = baked_keys = 0
    worst = 0.0
    names = []
    spins_out = []
    left_out = []

    for obj in objs:
        if not include_objects and obj.type != 'ARMATURE':
            continue
        ad = getattr(obj, "animation_data", None)
        action = getattr(ad, "action", None) if ad else None
        if action is None:
            continue
        akey = action.as_pointer()
        if akey in seen:
            continue
        seen.add(akey)

        bone_paths = _selected_bone_paths(obj) if selected_bones_only else None

        def groups(suffix, _a=action, _o=obj, _b=bone_paths):
            g = _curve_groups(_a, _o, suffix)
            if _b is None:
                return g
            return {p: f for p, f in g.items()
                    if any(p.startswith(b) for b in _b)}

        obj_curves = obj_keys = 0

        if do_quaternions:
            for _path, fcs in groups("rotation_quaternion").items():
                n, w = _unflip_quaternions(fcs)
                if n:
                    obj_curves += len(fcs)
                    obj_keys += n
                    quats += n
                    worst = max(worst, w)

        if do_baked_spins:
            for kind, suffix in (("quaternion", "rotation_quaternion"),
                                 ("euler", "rotation_euler")):
                for path, fcs in groups(suffix).items():
                    n, w, sp, left = _rebuild_baked_spins(
                        action, obj, path, fcs, kind, frame_range=frame_range,
                        spike_deg=spike_deg, max_window=max_window, pad=pad,
                        interp=interp)
                    owner = path.split('"')[1] if path.startswith('pose.bones["') else obj.name
                    for s in sp:
                        s["where"] = "%s > %s" % (obj.name, owner) if owner != obj.name else obj.name
                    for s in left:
                        s["where"] = "%s > %s" % (obj.name, owner) if owner != obj.name else obj.name
                    spins_out += sp
                    left_out += left
                    if n:
                        obj_curves += len(fcs)
                        obj_keys += n
                        baked += len(sp)
                        baked_keys += n
                        worst = max(worst, w)

        if do_eulers:
            for _path, fcs in groups("rotation_euler").items():
                n, w = _unflip_eulers(fcs)
                if n:
                    obj_curves += len(fcs)
                    obj_keys += n
                    gimbals += n
                    worst = max(worst, w)
                for fc in fcs.values():
                    n2, w2 = _unwrap_fcurve(fc, threshold)
                    if n2:
                        obj_curves += 1
                        obj_keys += n2
                        wraps += n2
                        worst = max(worst, w2)

        if do_camera_flips:
            from .Camera_Bone_Rig import camera_owner
            for kind, suffix in (("quaternion", "rotation_quaternion"),
                                 ("euler", "rotation_euler")):
                for path, fcs in groups(suffix).items():
                    if not camera_owner(obj, path):
                        continue
                    n, w = _repair_camera_flips(action, obj, path, fcs, kind)
                    if n:
                        obj_curves += len(fcs)
                        obj_keys += n
                        cam_flips += n
                        worst = max(worst, w)

        if obj_keys:
            touched_objs += 1
            curves += obj_curves
            keys += obj_keys
            names.append(f"{obj.name} ({obj_curves} curve(s), {obj_keys} key(s))")

    return {"empty_reason": None, "scanned": len(objs), "objects": touched_objs,
            "curves": curves, "keys": keys, "quats": quats, "gimbals": gimbals,
            "wraps": wraps, "camera_flips": cam_flips, "baked_spins": baked,
            "baked_keys": baked_keys, "worst": worst, "names": names,
            "spins": spins_out, "left": left_out}


class HT_OT_DeleteEulerSpins(Operator):
    """Remove 360-degree spins from rotation curves - the selection, or the scene

Two frames can hold the SAME pose two ways, and when consecutive frames pick
differently the interpolation takes the long way round - a full spin between
poses that barely moved.

QUATERNIONS: q and -q are the same orientation, so a sign flip between
frames is a 360-degree spin. Every importer here writes quaternions.

EULER: the 180-on-every-axis gimbal flip, and plain 360 wraps.

BAKED SPINS (1.22.0): baked keys that themselves turn a full 360 over a few
frames - those poses are wrong, so that window is rebuilt along the short
way at the speed the motion had at its ends. Every other key keeps its pose.

In Pose Mode the button works on the selected bones only. Undoable"""
    bl_idname  = "ht.delete_euler_spins"
    bl_label   = "Delete Rotation Spins"
    bl_options = {"REGISTER", "UNDO"}

    scope: EnumProperty(
        name="Scope",
        description="What the button works on",
        items=(
            ('SELECTION', "Selection",
             "Pose Mode: the selected bones only. Object Mode: the selected "
             "objects (their own rotation and all their bones). Fast - a big "
             "session is never touched outside what you picked.\n"
             "THIS FEATURE WAS ADDED IN VERSION 1.22.0 AND IS IN EXPERIMENTAL STAGE"),
            ('SCENE', "Whole Scene",
             "Every object in the scene - what this button did before 1.22.0. "
             "Use it right after a session import, when a spin is wherever "
             "the flip happened to fall"),
        ),
        default='SELECTION',
    )
    include_objects: BoolProperty(
        name="Include Object Rotation",
        description="Also fix rotation on the objects themselves, not only "
                    "pose bones. Cameras, lights and static props are animated "
                    "on the object, so turning this off skips them entirely",
        default=True,
    )
    do_quaternions: BoolProperty(
        name="Quaternion Sign Flips",
        description="Negate a quaternion key that faces the opposite way to "
                    "the one before it. This is the one that fires on an "
                    "imported session - everything here is imported as "
                    "quaternion",
        default=True,
    )
    do_eulers: BoolProperty(
        name="Euler Flips And Wraps",
        description="Fix euler curves too: the 180-on-every-axis gimbal flip, "
                    "and 360 wraps. Only does anything on rigs converted to "
                    "euler by hand",
        default=True,
    )
    do_camera_flips: BoolProperty(
        name="One-Frame Camera Flips",
        description="Imported cameras only: a frame turned at least 30 degrees "
                    "from BOTH neighbours while they agree and the position "
                    "runs straight through gets the neighbours' in-between. "
                    "HoovyTools 1.17.2 and older baked these into a session "
                    "camera (one frame up to 180 degrees off where SFM wrote "
                    "a sign change); a re-import with 1.17.3 has none. A real "
                    "one-frame shot moves too, so it is left alone.\n"
                    "THIS FEATURE WAS ADDED IN VERSION 1.17.3 AND IS IN "
                    "EXPERIMENTAL STAGE",
        default=True,
    )
    threshold_deg: FloatProperty(
        name="Wrap Threshold (deg)",
        description="A gap between consecutive EULER keys wider than this is "
                    "read as a wrap rather than as motion. 180 is the "
                    "theoretical boundary; the default sits well above it so a "
                    "genuine fast spin is left alone. Does not affect "
                    "quaternions or gimbal flips",
        default=EULER_JUMP_THRESHOLD_DEG, min=90.0, max=359.0,
    )
    do_baked_spins: BoolProperty(
        name="Baked Spins (Multi-Frame)",
        description="Baked keys that themselves turn a full 360 over a few "
                    "frames - a quaternion blend across q / -q bakes them in "
                    "(CSDeals Scene3 camera: 173 and 176 degrees on frames "
                    "460-461, creep from 456 to 464). The other passes only "
                    "rewrite how a pose is written, and these poses are wrong, "
                    "so the window is rebuilt along the short way. A real snap "
                    "(turns as far as it ends up turned) and a cut (the "
                    "position jumps too) are left alone.\n"
                    "THIS FEATURE WAS ADDED IN VERSION 1.22.0 AND IS IN "
                    "EXPERIMENTAL STAGE",
        default=True,
    )
    interp: EnumProperty(
        name="Rebuild",
        description="How a baked spin's window is rebuilt",
        items=(
            ('SMOOTH', "Smooth",
             "Leaves each end at the speed the motion had there - no hitch "
             "on a drifting camera"),
            ('LINEAR', "Linear",
             "Constant speed between the two ends (a plain slerp)"),
        ),
        default='SMOOTH',
    )
    spike_deg: FloatProperty(
        name="Spike (deg / frame)",
        description="A turn this fast between two baked keys starts a search "
                    "for a baked spin. 45 per frame is 1350 degrees a second at "
                    "30 fps, faster than any camera move. Lower it to catch a "
                    "slower wind-up, raise it if a real whip pan gets touched.\n"
                    "THIS FEATURE WAS ADDED IN VERSION 1.22.0 AND IS IN "
                    "EXPERIMENTAL STAGE",
        default=45.0, min=5.0, max=179.0,
    )
    max_window: IntProperty(
        name="Max Window (frames)",
        description="The longest stretch either side of a spike the search may "
                    "rebuild. The window stops by itself where the keys move "
                    "like the motion around them again",
        default=48, min=2, max=1000,
    )
    pad: IntProperty(
        name="Pad (frames)",
        description="Extra frames rebuilt beyond the detected creep on each "
                    "side, so the join is smooth",
        default=1, min=0, max=24,
    )
    use_frame_range: BoolProperty(
        name="Frame Range",
        description="Only rebuild baked spins inside this range (the other "
                    "passes always run on the whole curve).\n"
                    "THIS FEATURE WAS ADDED IN VERSION 1.22.0 AND IS IN "
                    "EXPERIMENTAL STAGE",
        default=False,
    )
    frame_start: IntProperty(name="Start", default=1)
    frame_end: IntProperty(name="End", default=250)

    def invoke(self, context, event):
        if not self.use_frame_range:
            self.frame_start = context.scene.frame_start
            self.frame_end = context.scene.frame_end
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        lay = self.layout
        lay.prop(self, "scope", expand=True)
        if self.scope == 'SELECTION':
            ob = context.view_layer.objects.active
            if ob is not None and ob.mode == 'POSE':
                n = len(_selected_bone_paths(ob) or ())
                lay.label(text=f"{ob.name}: {n} selected bone(s)", icon='BONE_DATA')
            else:
                lay.label(text=f"{len(context.selected_objects)} selected object(s)",
                          icon='OBJECT_DATA')
        col = lay.column(align=True)
        col.prop(self, "do_quaternions")
        col.prop(self, "do_baked_spins")
        col.prop(self, "do_eulers")
        col.prop(self, "do_camera_flips")
        col.prop(self, "include_objects")
        if self.do_baked_spins:
            box = lay.box()
            box.label(text="Baked Spins", icon='ORIENTATION_GIMBAL')
            box.prop(self, "interp", expand=True)
            box.prop(self, "spike_deg")
            row = box.row(align=True)
            row.prop(self, "max_window")
            row.prop(self, "pad")
            box.prop(self, "use_frame_range")
            if self.use_frame_range:
                row = box.row(align=True)
                row.prop(self, "frame_start")
                row.prop(self, "frame_end")
        if self.do_eulers:
            lay.prop(self, "threshold_deg")

    def execute(self, context):
        try:
            res = delete_euler_spins(only_selected=(self.scope == 'SELECTION'),
                                     include_objects=self.include_objects,
                                     threshold_deg=self.threshold_deg,
                                     do_quaternions=self.do_quaternions,
                                     do_eulers=self.do_eulers,
                                     do_camera_flips=self.do_camera_flips,
                                     do_baked_spins=self.do_baked_spins,
                                     selected_bones_only=(self.scope == 'SELECTION'),
                                     frame_range=((self.frame_start, self.frame_end)
                                                  if self.use_frame_range else None),
                                     spike_deg=self.spike_deg,
                                     max_window=self.max_window,
                                     pad=self.pad,
                                     interp=self.interp)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if res["empty_reason"]:
            self.report({"WARNING"}, f"Rotation filter: {res['empty_reason']}.")
            return {"CANCELLED"}
        if not res["keys"]:
            left = res.get("left", [])
            extra = (f"; {len(left)} fast turn(s) left alone: "
                     + ", ".join(f"{s['where']} f{s['frames'][0]:.0f} ({s['why']})"
                                 for s in left[:3])) if left else ""
            self.report({"INFO"}, f"No rotation spins found "
                                  f"({res['scanned']} object(s) checked){extra}.")
            return {"CANCELLED"}

        lines = [
            f"Objects scanned : {res['scanned']}",
            f"Objects fixed   : {res['objects']}",
            f"Curves          : {res['curves']}",
            f"Keys rewritten  : {res['keys']}",
            f"  quaternion    : {res['quats']} sign flip(s)",
            f"  euler gimbal  : {res['gimbals']} flip(s)",
            f"  euler wrap    : {res['wraps']} key(s)",
            f"  camera flip   : {res['camera_flips']} frame(s)",
            f"  baked spin    : {res['baked_spins']} spin(s), "
            f"{res['baked_keys']} key(s)",
            f"Largest spin    : {res['worst']:.0f} degrees",
        ]
        for s in res.get("spins", [])[:12]:
            lines.append(f"  rebuilt {s['where']}: frames {s['frames'][0]:.0f}-"
                         f"{s['frames'][1]:.0f} ({s['worst']:.0f} deg/frame on "
                         f"{', '.join('%.0f' % f for f in s['spike_frames'])})")
        for s in res.get("left", [])[:6]:
            lines.append(f"  left alone {s['where']}: frame(s) "
                         f"{', '.join('%.0f' % f for f in s['frames'])} - {s['why']}")
        if res["names"]:
            lines.append("── WHAT MOVED ────────────────")
            lines += [f"  • {n}" for n in res["names"][:12]]
            if len(res["names"]) > 12:
                lines.append(f"  … and {len(res['names']) - 12} more")

        from ..core import Report_UI
        Report_UI.report(
            context, "utils_misc",
            f"Delete Rotation Spins - {res['objects']} object(s)", lines,
            level='INFO', operator=self, prefix="SPINS",
            summary=f"Rotation filter - {res['keys']} key(s) fixed on "
                    f"{res['curves']} curve(s)")
        return {"FINISHED"}



#  The experimental keyword table. FIRST MATCH WINS, and the order is the
#  precedence: skin before metal, because "hand_rail" should read as a rail,
#  but a character's "metal_hand" glove reading as skin is the safer miss.
#  Values are taste, not physics - tuned to read right in EEVEE at a glance.
_VLG_RULES = (
    #  key         needles                                           settings
    #  NO "arm" OR "leg" NEEDLES: "arm" is inside armor, farm and alarm, and
    #  the very first test scene had "armor_metal_sheet" reading as skin.
    #  A greedy needle in the FIRST rule poisons every rule after it.
    ("skin",   ("skin", "face", "head", "hand", "body", "flesh", "eyeball"),
     {"Roughness": 0.25, "Metallic": 0.125,
      "Subsurface Weight": 0.15,
      "Subsurface Radius": (1.0, 0.2, 0.1)}),
    ("metal",  ("metal", "metalic", "metallic", "sheet", "steel", "iron",
                "chrome", "silver", "copper", "brass", "blade", "sword"),
     {"Metallic": 0.9, "Roughness": 0.01}),
    ("wood",   ("wood", "plank", "timber", "bark", "log_"),
     {"Roughness": 0.6, "Metallic": 0.0}),
    ("leather", ("leather", "belt", "boot", "strap", "saddle"),
     {"Roughness": 0.5, "Metallic": 0.0}),
    ("cloth",  ("cloth", "fabric", "shirt", "pants", "coat", "cape",
                "robe", "wool", "linen", "rag"),
     {"Roughness": 0.8, "Metallic": 0.0, "Sheen Weight": 0.3}),
    ("hair",   ("hair", "beard", "brow"),
     {"Roughness": 0.4, "Metallic": 0.0}),
    ("glass",  ("glass", "window", "lens", "bottle"),
     {"Roughness": 0.05, "Metallic": 0.0}),
    ("stone",  ("stone", "rock", "concrete", "brick", "marble"),
     {"Roughness": 0.9, "Metallic": 0.0}),
)

#  What everything else gets - and the WHOLE pass in non-experimental mode.
_VLG_DEFAULT = {"Roughness": 0.25}


def _vlg_apply(bsdf, settings):
    """Set the Principled inputs that exist on this Blender's node. Input
    names moved between 3.x and 4.x (Subsurface -> Subsurface Weight), so
    absent names are skipped rather than raised on."""
    touched = 0
    for name, value in settings.items():
        sock = bsdf.inputs.get(name)
        if sock is None:
            continue
        try:
            sock.default_value = value
            touched += 1
        except Exception:                                     # noqa: BLE001
            pass
    return touched


def run_vertexlit_fix(experimental=False):
    """Retune every mesh material's Principled BSDF.

    Returns {"materials", "skipped", "by_rule": {rule: count}}.
    """
    seen = set()
    by_rule = {}
    skipped = 0
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            mat = slot.material
            if mat is None or mat.name in seen:
                continue
            seen.add(mat.name)
            bsdf = None
            if mat.use_nodes and mat.node_tree:
                for node in mat.node_tree.nodes:
                    if node.bl_idname == "ShaderNodeBsdfPrincipled":
                        bsdf = node
                        break
            if bsdf is None:
                skipped += 1
                continue
            rule_name, settings = "default", _VLG_DEFAULT
            if experimental:
                low = mat.name.lower()
                for name, needles, cfg in _VLG_RULES:
                    if any(n in low for n in needles):
                        rule_name, settings = name, cfg
                        break
            _vlg_apply(bsdf, settings)
            by_rule[rule_name] = by_rule.get(rule_name, 0) + 1
    return {"materials": sum(by_rule.values()), "skipped": skipped,
            "by_rule": by_rule}


class HT_OT_VertexlitFix(Operator):
    """NO INPUT - retunes every mesh material's Principled BSDF in the file

        Fix SourceIO's flat VertexLitGeneric materials

SourceIO leaves every imported material at Blender's defaults, so a whole
scene reads as one grey plastic. Default mode sets roughness 0.25 on every
material - one flat, safe improvement.

EXPERIMENTAL (off by default) guesses a surface type from each material's
NAME and tunes it: metal/sheet/steel -> metallic 0.9 + roughness 0.01,
skin/face/body -> roughness 0.25 + a touch of subsurface, wood, leather,
cloth, hair, glass and stone each get their own numbers. First matching
keyword wins; anything unmatched gets the default 0.25.

Values are viewport taste, not physics. Materials without a Principled
BSDF are counted and skipped, never touched"""
    bl_idname = "ht.vertexlit_fix"
    bl_label = "Source IO VertexlitGeneric Fix"
    bl_options = {"REGISTER", "UNDO"}

    experimental: BoolProperty(  # type: ignore
        name="Experimental (guess by name)",
        description=("Guess each material's surface type from keywords in "
                     "its name - metal, skin, wood, leather, cloth, hair, "
                     "glass, stone - and tune metallic / roughness / "
                     "subsurface per type. OFF: every material simply gets "
                     "roughness 0.25"),
        default=False,
    )

    def execute(self, context):
        r = run_vertexlit_fix(experimental=self.experimental)
        lines = [f"Materials : {r['materials']} retuned"
                 + ("  (experimental, by name)" if self.experimental
                    else "  (roughness 0.25)")]
        if self.experimental:
            for rule, n in sorted(r["by_rule"].items(),
                                  key=lambda kv: -kv[1]):
                lines.append(f"  {rule:<9}: {n}")
        if r["skipped"]:
            lines.append(f"Skipped   : {r['skipped']} without a Principled "
                         f"BSDF")
        from ..core import Report_UI
        Report_UI.report(
            context, "vertexlit_fix", "VertexlitGeneric Fix", lines,
            level='INFO', operator=self, prefix="VLG_FIX",
            summary=f"VertexlitGeneric Fix - {r['materials']} material(s)"
                    + (" (experimental)" if self.experimental else ""))
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU
# ──────────────────────────────────────────────────────────────────────────────

class HT_MT_utils_misc_submenu(bpy.types.Menu):
    bl_idname = "HT_MT_utils_misc_submenu"
    bl_label  = "Misc"

    def draw(self, context):
        self.layout.operator(
            HT_OT_OrganizeScene.bl_idname,
            text="Organize Scene",
            **_icon_id("organize_scene", "OUTLINER"),
        )
        self.layout.operator(
            HT_OT_ReduceLagEpsilon.bl_idname,
            text="Reduce Lag With Epsilon Filter",
            **_icon_id("reduce_lag", "GRAPH"),
        )
        self.layout.operator(
            HT_OT_DeleteEulerSpins.bl_idname,
            text="Delete Rotation Spins",
            **_icon_id("delete_euler_spins", "ORIENTATION_GIMBAL"),
        )
        self.layout.operator(
            HT_OT_VertexlitFix.bl_idname,
            text="Source IO VertexlitGeneric Fix",
            **_icon_id("vertexlit_fix", "MATERIAL"),
        )


def draw_utils_misc_entry(layout):
    """Called from HT_MT_utils_submenu."""
    layout.menu(
        HT_MT_utils_misc_submenu.bl_idname,
        text="Misc",
        **_icon_id("utils_misc", "TOOL_SETTINGS"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (
    HT_OT_OrganizeScene,
    HT_OT_ReduceLagEpsilon,
    HT_OT_DeleteEulerSpins,
    HT_OT_VertexlitFix,
    HT_MT_utils_misc_submenu,
)


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