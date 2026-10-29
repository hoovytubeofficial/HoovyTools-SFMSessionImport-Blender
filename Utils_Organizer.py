"""
Utils_Organizer.py  —  part of HoovyTools
=========================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Source Engine Utils ▸
           Organize Scene

Sorts every imported SourceIO rig (armature + its meshes + constraints) into a
tidy nested collection hierarchy, derived from the import path that SourceIO
bakes into the mesh names.

PATH-BASED MODELS
─────────────────
A mesh imported by SourceIO carries a name like:

    tf2_enhanced\\foliage\\mediterranean\\asphodel_grass_a_enhanced.m_asphodel…smd_MESH

The path before the FIRST DOT (in the final segment) is the meaningful path:

    tf2_enhanced / foliage / mediterranean / asphodel_grass_a_enhanced

Each level becomes a nested collection under  ___Models___ , formatted
(underscores → spaces, Title Case, known acronyms like TF2/HL2 preserved):

    ___Models___ / TF2 Enhanced / Foliage / Mediterranean / Asphodel Grass A Enhanced

The armature and all its meshes are moved into that leaf collection.

CHARACTERS  (intelligent folder)
────────────────────────────────
Any rig whose armature name matches a reference in  HoovyTools/Faulty Rigs/
(files named  {character}_reference.dmx ) is treated as a CHARACTER and routed
to  ___Characters___ / {Character Name}  instead of the path tree. Matching is
LONGEST-STEM-WINS so  heavy_toga_a  matches  heavy_toga_a_reference  rather than
the shorter  heavy_reference .

RERUNNABLE
──────────
Re-running first clears  ___Models___  and  ___Characters___  (and their nested
collections) so objects are re-sorted fresh rather than duplicated. Objects are
moved, never copied — so no data is lost if a path can't be parsed (those rigs
are left where they are and reported).
"""

bl_info = {
    "name":        "HoovyTools: Utils — Scene Organizer",
    "description": "Sort imported SourceIO rigs into nested collections by import path",
    "author":      "HoovyTools",
    "version":     (1, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > Source Engine Utils > Organize Scene",
    "category":    "Import-Export",
}

import bpy
from pathlib import Path
from bpy.types import Operator
from bpy.props import BoolProperty


# ──────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────────────────────────────────────

MODELS_ROOT     = "___Models___"
CHARACTERS_ROOT = "___Characters___"
COLOR_MODELS    = "COLOR_05"   # blue
COLOR_CHARS     = "COLOR_04"   # green

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
    """Return the longest stem contained in rig_name (lowercased), or None."""
    n = (rig_name or "").lower()
    for stem in stems:          # already longest-first
        if stem in n:
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
            leaf = _chain_collection([_fmt_segment(char)], chars_root, COLOR_CHARS)
            for obj in members:
                _move_object(obj, leaf)
                claimed.add(obj)
            results["characters"].append((arm.name, _fmt_segment(char)))
            print(f"[ORGANIZE]  CHAR  '{arm.name}' -> {CHARACTERS_ROOT}/{_fmt_segment(char)}")
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
#  MENU
# ──────────────────────────────────────────────────────────────────────────────

def draw_utils_organizer_entry(layout):
    """Called from MT_HT_utils_submenu — a direct operator entry."""
    layout.operator(
        HT_OT_OrganizeScene.bl_idname,
        text="Organize Scene",
        **_icon_id("organize_scene", "OUTLINER"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (HT_OT_OrganizeScene,)


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
