"""
Utils_Misc.py  —  part of HoovyTools
====================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Source Engine Utils ▸ Misc ▸
           Organize Scene
           Reduce Lag With Epsilon Filter

Two scene-wide housekeeping tools for SourceIO imports.

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
import math
import re
from pathlib import Path
from mathutils import Quaternion
from bpy.types import Operator
from bpy.props import BoolProperty, FloatProperty


# ──────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────────────────────────────────────

MODELS_ROOT     = "___Models___"
CHARACTERS_ROOT = "___Characters___"
COLOR_MODELS    = "COLOR_05"   # blue
COLOR_CHARS     = "COLOR_04"   # green

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
        from .anim_compat import iter_fcurves as _ac
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
    chain = parts[:-1] + [leaf]
    return [_fmt_segment(c) for c in chain]


# ──────────────────────────────────────────────────────────────────────────────
#  CHARACTER MATCHING  (against HoovyTools/Faulty Rigs/)
# ──────────────────────────────────────────────────────────────────────────────

def _faulty_rigs_dir() -> Path:
    return Path(__file__).parent / "Faulty Rigs"


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

def _get_or_create_child(name: str, parent_col, color=None):
    """Get/create a collection named *name* as a child of *parent_col*."""
    existing = parent_col.children.get(name)
    if existing is not None:
        if color:
            existing.color_tag = color
        return existing
    # reuse a same-named collection if it exists but isn't yet linked here
    col = bpy.data.collections.get(name)
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
    if cleared:
        print(f"[ORGANIZE]  cleared previous organization ({cleared} object(s))")

    stems = _character_stems() if do_characters else []
    print(f"[ORGANIZE]  {len(stems)} character reference(s) in Faulty Rigs/")

    results = {"characters": [], "models": [], "skipped": []}
    models_root = chars_root = None
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

        # ── path-based model ──
        if do_models:
            chain = _rig_source_path(members)
            if chain:
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
    """Sort imported SourceIO rigs into nested collections by import path / character"""
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
        ]
        if ns:
            lines.append(f"Skipped    : {ns} (no path / no match)")
            lines.append("─" * 40)
            for name in res["skipped"][:12]:
                lines.append(f"  • {name}")

        def draw_popup(self, context):
            for line in lines:
                self.layout.label(text=line)
        context.window_manager.popup_menu(
            draw_popup,
            title=f"Organize Scene — {nc + nm} rig(s) sorted",
            icon="OUTLINER" if not ns else "INFO",
        )
        self.report({"INFO"}, f"Organized {nc + nm} rig(s), {ns} skipped")
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
    """Reduce keyframe count on every armature in the scene (rotation + shape keys)"""
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
        def draw_popup(self, context):
            for line in lines:
                self.layout.label(text=line)
        context.window_manager.popup_menu(
            draw_popup, title=f"Epsilon Filter — {res['models']} model(s)",
            icon="CHECKMARK")
        self.report({"INFO"}, f"Filtered {res['models']} model(s), "
                              f"{res['removed']} keys removed")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU
# ──────────────────────────────────────────────────────────────────────────────

class MT_HT_utils_misc_submenu(bpy.types.Menu):
    bl_idname = "MT_HT_utils_misc_submenu"
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


def draw_utils_misc_entry(layout):
    """Called from MT_HT_utils_submenu."""
    layout.menu(
        MT_HT_utils_misc_submenu.bl_idname,
        text="Misc",
        **_icon_id("utils_misc", "TOOL_SETTINGS"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (
    HT_OT_OrganizeScene,
    HT_OT_ReduceLagEpsilon,
    MT_HT_utils_misc_submenu,
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