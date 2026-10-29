"""
Panel.py - HoovyTools sidebar (3D View, N key)
==============================================

One panel, three tabs:

    Anim Set  |  Import  |  Tutorial

  Anim Set    The "Animation Set Editor" - a live status board of every
              armature in the scene, colored by import progress:
                  ORANGE = model imported (mesh + rig present)
                  YELLOW = animation imported onto the rig
                  GREEN  = shape key animation present on its meshes
              Plus two cleanup operators: purge model-only rigs, and
              strip all animation back to a clean model state.

  Import      Every import + utility operator the addon registers.

  Tutorial    The session workflow, plus a live environment readout:
              current usermod path and whether SourceIO is installed.

DRAW-TIME RULES
===============
draw() runs on every redraw and must never mutate the blend file.
Status detection is read-only introspection. The cleanup operators do
mutate, but they are operators (button-triggered), never called from
draw().
"""

import bpy
from bpy.props import EnumProperty
from bpy.types import Panel, Operator, PropertyGroup

# ─────────────────────────────────────────────────────────────────────────────
#  Status colours (RGBA, matched to Blender's dark theme)
# ─────────────────────────────────────────────────────────────────────────────

C_MODEL = (0.90, 0.55, 0.18, 1.0)   # orange - model imported, nothing else
C_ANIM  = (0.92, 0.84, 0.25, 1.0)   # yellow - animation imported
C_FULL  = (0.35, 0.78, 0.42, 1.0)   # green  - shape key animation present

# Collection color_tag values used by the harvester
TAG_OK   = "COLOR_04"   # green
TAG_FAIL = "COLOR_06"   # red
TAG_NONE = "NONE"       # white / default


def _dot(layout, color):
    """Colour swatch via the node-socket template (only arbitrary-RGBA call)."""
    try:
        layout.template_node_socket(color=color)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  Icon bridge (wired by __init__.register)
# ─────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None


def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ─────────────────────────────────────────────────────────────────────────────
#  Settings
# ─────────────────────────────────────────────────────────────────────────────

TAB_ITEMS = [
    ('ASE',      "Anim Set",  "Animation Set Editor - live import status for every "
                              "armature in the scene, with cleanup tools", 'OUTLINER_OB_ARMATURE', 0),
    ('IMPORT',   "Import",    "All import and utility operators, grouped the same way "
                              "as the File > Import menu", 'IMPORT', 1),
    ('TUTORIAL', "Tutorial",  "The session import workflow plus a live readout of Your "
                              "usermod path and SourceIO status", 'HELP', 2),
]


class HoovyToolsPanelSettings(PropertyGroup):
    active_tab: EnumProperty(  # type: ignore
        name="Tab", items=TAB_ITEMS, default='ASE',
    )


def settings(context):
    return getattr(context.scene, "ht_panel", None)


# ─────────────────────────────────────────────────────────────────────────────
#  Status detection (read-only, draw-safe)
# ─────────────────────────────────────────────────────────────────────────────

def _action_has_keys(action):
    if action is None:
        return False
    try:
        from . import anim_compat
        for fc in anim_compat.iter_fcurves(action):
            if len(fc.keyframe_points):
                return True
    except Exception:
        try:
            for fc in action.fcurves:
                if len(fc.keyframe_points):
                    return True
        except Exception:
            pass
    return False


def _root_empty(arm):
    return bpy.data.objects.get(f"{arm.name}_root")


def _axis_empty(arm):
    return bpy.data.objects.get(f"{arm.name}_axis")


def _armature_has_animation(arm):
    ad = arm.animation_data
    if ad and _action_has_keys(ad.action):
        return True
    root = _root_empty(arm)
    if root and root.animation_data and _action_has_keys(root.animation_data.action):
        return True
    return False


def _armature_meshes(arm):
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        if obj.parent == arm:
            yield obj
            continue
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == arm:
                yield obj
                break


def _armature_has_shapekey_animation(arm):
    for mesh in _armature_meshes(arm):
        sk = getattr(mesh.data, "shape_keys", None)
        if sk is None:
            continue
        ad = sk.animation_data
        if ad is None:
            continue
        if _action_has_keys(ad.action):
            return True
        try:
            if ad.drivers and len(ad.drivers):
                return True
        except Exception:
            pass
    return False


def armature_status(arm):
    if _armature_has_shapekey_animation(arm):
        return 'FULL'
    if _armature_has_animation(arm):
        return 'ANIM'
    return 'MODEL'


_STATUS_META = {
    'MODEL': (C_MODEL, "model only"),
    'ANIM':  (C_ANIM,  "animated"),
    'FULL':  (C_FULL,  "anim + shape keys"),
}


# ─────────────────────────────────────────────────────────────────────────────
#  Cleanup helpers (shared by the operators)
# ─────────────────────────────────────────────────────────────────────────────

def _top_collection(arm):
    """Direct child of the Scene Collection that holds *arm*, if any."""
    scene_root = bpy.context.scene.collection

    def search(col, obj):
        if obj.name in col.objects:
            return col
        for child in col.children:
            hit = search(child, obj)
            if hit is not None:
                return child if hit in col.children else hit
        return None

    for top in scene_root.children:
        if search(top, arm) is not None:
            return top
    return None


def _delete_object_tree(obj):
    """Delete *obj* and every descendant, from mesh data up. Returns count."""
    victims = []
    stack = [obj]
    while stack:
        cur = stack.pop()
        victims.append(cur)
        stack.extend(list(cur.children))
    n = 0
    for o in victims:
        try:
            bpy.data.objects.remove(o, do_unlink=True)
            n += 1
        except Exception:
            pass
    return n


def _clear_shapekey_animation(arm):
    """
    Remove shape-key animation from every mesh bound to *arm* and return the
    shape keys to rest (all values 0). Without this, clearing only the armature
    action leaves the face frozen in whatever expression the last frame held -
    the mesh keeps its own shape-key animation, which lives on
    mesh.data.shape_keys, not on the armature.

    Returns the number of meshes cleaned.
    """
    n = 0
    for mesh in _armature_meshes(arm):
        sk = getattr(mesh.data, "shape_keys", None)
        if sk is None:
            continue
        cleared = False

        # Drop the whole animation_data block (action + drivers + NLA) in one go
        if sk.animation_data is not None:
            try:
                sk.animation_data_clear()
                cleared = True
            except Exception:
                # Fall back to clearing the action alone
                try:
                    sk.animation_data.action = None
                    cleared = True
                except Exception:
                    pass

        # Reset every non-basis key to 0 so the mesh sits at rest
        try:
            for kb in sk.key_blocks:
                if kb.value != 0.0:
                    kb.value = 0.0
                    cleared = True
        except Exception:
            pass

        if cleared:
            n += 1
    return n


def _strip_animation(arm):
    """
    Return *arm* to the exact state it was in BEFORE animation was imported,
    so a re-import reproduces the original result rather than a rotated one:
      - unparent the armature from its root empty, keeping its LOCAL transform
        (matrix_basis) untouched - NOT its world transform
      - delete the <arm>_root and <arm>_axis empties
      - clear the armature's own action (bones fall back to rest)
      - recolor its top collection to white (NONE)
    Returns a dict of what was removed.

    Why local, not world
    --------------------
    The axis empty carries a static +90 deg X correction (SFM Y-up -> Blender
    Z-up); the animation import parents  armature -> root -> axis  with an
    identity parent-inverse, leaving the armature's own matrix_basis (call it
    B) exactly as the model importer left it. So:

        matrix_world = axis(+90 X) @ root(anim) @ B

    If we unparented while *preserving world* (matrix_world = world), that whole
    product - including the +90 deg - would get baked into matrix_basis. The
    next animation import then parents the rig under a FRESH +90 deg axis, and
    the two stack: everything ends up rotated ~90 deg off. Keeping matrix_basis
    (= B) instead means the rig returns to its pre-animation orientation, and a
    re-import rebuilds  axis @ root @ B  identically to the first time.

    Plain `arm.parent = None` (not object.parent_clear KEEP_TRANSFORM) is
    exactly this: it leaves matrix_basis alone and lets matrix_world recompute
    down to B.
    """
    removed = {"empties": 0, "action": False, "recolored": False, "meshes": 0}

    root = _root_empty(arm)
    axis = _axis_empty(arm)

    # Unparent the armature but leave its local (basis) transform intact.
    if arm.parent in (root, axis) and arm.parent is not None:
        arm.parent = None
        # Reset the parent-inverse so a later manual reparent starts clean.
        # (The animation importer sets this to identity itself, so this is
        # just tidiness - matrix_basis is what actually matters above.)
        try:
            from mathutils import Matrix
            arm.matrix_parent_inverse = Matrix.Identity(4)
        except Exception:
            pass

    for empty in (root, axis):
        if empty is not None:
            try:
                bpy.data.objects.remove(empty, do_unlink=True)
                removed["empties"] += 1
            except Exception:
                pass

    ad = arm.animation_data
    if ad and ad.action:
        ad.action = None
        removed["action"] = True

    # Clear shape-key animation on bound meshes and reset them to rest.
    removed["meshes"] = _clear_shapekey_animation(arm)

    top = _top_collection(arm)
    if top is not None and top.color_tag != TAG_NONE:
        top.color_tag = TAG_NONE
        removed["recolored"] = True

    return removed


# ─────────────────────────────────────────────────────────────────────────────
#  Operators
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_purge_model_only(Operator):
    """Delete every armature still at ORANGE status - model imported but never \
animated - along with all of its meshes, empties and its now-empty top \
collection. Rigs that carry any animation or shape-key animation are left \
untouched. Use this to clear reference models You pulled in but decided not \
to animate, so the scene only keeps the rigs You are actually working on. \
This permanently removes objects; undo with Ctrl+Z if it catches too much"""
    bl_idname = "ht.purge_model_only"
    bl_label = "Remove Model-Only Rigs"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'ARMATURE' for o in context.scene.objects)

    def execute(self, context):
        targets = [o for o in list(context.scene.objects)
                   if o.type == 'ARMATURE' and armature_status(o) == 'MODEL']
        if not targets:
            self.report({"INFO"}, "No model-only rigs to remove.")
            return {"CANCELLED"}

        removed_objs = 0
        removed_cols = 0
        names = []
        for arm in targets:
            names.append(arm.name)
            top = _top_collection(arm)
            removed_objs += _delete_object_tree(arm)
            # Delete the top collection if it is now empty of objects
            if top is not None and not top.all_objects:
                try:
                    bpy.data.collections.remove(top)
                    removed_cols += 1
                except Exception:
                    pass

        lines = [f"Removed {len(names)} model-only rig(s):"] + \
                [f"  • {n}" for n in names[:12]]
        if len(names) > 12:
            lines.append(f"  … and {len(names) - 12} more")
        lines.append(f"Objects deleted : {removed_objs}")
        if removed_cols:
            lines.append(f"Collections     : {removed_cols}")

        _lines = list(lines)
        def draw(self, context):
            for ln in _lines:
                self.layout.label(text=ln)
        context.window_manager.popup_menu(draw, title="Purge Model-Only Rigs",
                                          icon="TRASH")
        self.report({"INFO"}, f"Removed {len(names)} model-only rig(s)")
        return {"FINISHED"}


class HT_OT_strip_all_animation(Operator):
    """Strip animation off every armature in the scene and return each rig to \
the exact state it had BEFORE animation was imported. For each rig this \
unparents it from its root empty while keeping its original local orientation \
(so it is not rotated), deletes the <rig>_root and <rig>_axis empties, clears \
its bone action, and clears shape-key animation on its meshes (resetting faces \
to rest). With Restore Rest Poses on, it then re-runs the Rig Fixer so every \
rig's rest pose matches its reference DMX - the same step 2 You ran after \
import - leaving the scene in a clean, ready-to-re-import state. Finally each \
top collection is recolored white. Because the rig is restored to its \
pre-animation orientation, re-importing animation reproduces the original \
poses and rotation instead of stacking a second 90-degree axis correction. \
Undo with Ctrl+Z"""
    bl_idname = "ht.strip_all_animation"
    bl_label = "Remove All Animation"
    bl_options = {"REGISTER", "UNDO"}

    restore_rest_poses: bpy.props.BoolProperty(
        name="Restore Rest Poses",
        description=(
            "After removing animation, re-run the Rig Fixer to restore every "
            "rig's original rest pose from its reference DMX (the same as step "
            "2 in the import workflow). Leave on unless You have no reference "
            "files - then it simply reports that none were found and changes "
            "nothing"
        ),
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return any(o.type == 'ARMATURE' for o in context.scene.objects)

    def execute(self, context):
        arms = [o for o in context.scene.objects if o.type == 'ARMATURE']
        touched = 0
        empties = 0
        meshes = 0
        for arm in arms:
            r = _strip_animation(arm)
            if r["empties"] or r["action"] or r["recolored"] or r["meshes"]:
                touched += 1
            empties += r["empties"]
            meshes += r["meshes"]

        # Restore rest poses via the Rig Fixer, then recolor white last so the
        # fixer's own yellow tagging doesn't leave the scene mislabeled.
        rest_line = None
        if self.restore_rest_poses:
            try:
                from . import Import_Session
                fx = Import_Session.run_rig_fixer()
                rest_line = (f"Rest poses  : {fx['fixed']} fixed, "
                             f"{fx['skipped']} skipped")
                if fx["errors"]:
                    rest_line += f", {fx['errors']} error(s)"
                # Rig Fixer recolors fixed rigs yellow - reset to white so the
                # final state reads as clean model-only.
                for arm in arms:
                    top = _top_collection(arm)
                    if top is not None and top.color_tag != TAG_NONE:
                        top.color_tag = TAG_NONE
            except Exception as exc:
                rest_line = f"Rest poses  : skipped ({exc})"

        if not touched and rest_line is None:
            self.report({"INFO"}, "No animation to remove - scene already clean.")
            return {"CANCELLED"}

        lines = [
            f"Cleaned     : {touched} rig(s)",
            f"Empties     : {empties} removed (root + axis)",
            f"Shape keys  : {meshes} mesh(es) reset to rest",
        ]
        if rest_line:
            lines.append(rest_line)
        lines.append("Folders     : recolored white")

        _lines = list(lines)
        def draw(self, context):
            for ln in _lines:
                self.layout.label(text=ln)
        context.window_manager.popup_menu(draw, title="Remove All Animation",
                                          icon="TRASH")
        self.report({"INFO"}, f"Stripped animation from {touched} rig(s)")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
#  Environment detection (Tutorial tab)
# ─────────────────────────────────────────────────────────────────────────────

def _usermod_path():
    """Current resolved usermod base, or None if it can't be read."""
    try:
        from . import Import_Session
        return Import_Session.get_gameinfo_base()
    except Exception:
        return None


def _sourceio_installed():
    """True when the SourceIO addon is enabled or importable."""
    try:
        prefs = bpy.context.preferences
        for key in prefs.addons.keys():
            if "sourceio" in key.lower() or "source_io" in key.lower():
                return True
    except Exception:
        pass
    import importlib.util
    for mod in ("SourceIO", "sourceio", "source_io"):
        try:
            if importlib.util.find_spec(mod) is not None:
                return True
        except Exception:
            continue
    return False


# ─────────────────────────────────────────────────────────────────────────────
#  Tab: Animation Set Editor
# ─────────────────────────────────────────────────────────────────────────────

def draw_ase(layout, context, st):
    arms = [o for o in context.scene.objects if o.type == 'ARMATURE']

    if not arms:
        box = layout.box()
        box.label(text="Nothing imported yet.", icon='INFO')
        box.label(text="Import tab → 1 Session Models.")
        return

    # Legend
    leg = layout.box()
    row = leg.row(align=True)
    row.label(text="Legend:")
    for key in ('MODEL', 'ANIM', 'FULL'):
        color, label = _STATUS_META[key]
        sub = row.row(align=True)
        if not _dot(sub, color):
            sub.label(text="●")
        sub.label(text=label)

    layout.separator(factor=0.5)

    counts = {'MODEL': 0, 'ANIM': 0, 'FULL': 0}
    col = layout.column(align=True)
    for arm in sorted(arms, key=lambda a: a.name.lower()):
        status = armature_status(arm)
        counts[status] += 1
        color, label = _STATUS_META[status]

        row = col.row(align=True)
        if not _dot(row, color):
            row.label(text="●")
        row.label(text=arm.name, icon='OUTLINER_OB_ARMATURE')
        row.label(text=label)

    layout.separator(factor=0.5)
    foot = layout.row(align=True)
    foot.label(text=f"{len(arms)} rig(s)  ·  "
                    f"{counts['MODEL']} model  ·  "
                    f"{counts['ANIM']} animated  ·  "
                    f"{counts['FULL']} complete")

    # Cleanup tools
    layout.separator()
    box = layout.box()
    box.label(text="Cleanup", icon='TRASH')
    col = box.column(align=True)
    col.scale_y = 1.1
    r = col.row(align=True)
    r.enabled = counts['MODEL'] > 0
    r.operator("ht.purge_model_only",
               text=f"Remove Model-Only Rigs ({counts['MODEL']})",
               icon='TRASH')
    r = col.row(align=True)
    r.enabled = (counts['ANIM'] + counts['FULL']) > 0
    r.operator("ht.strip_all_animation", text="Remove All Animation",
               icon='TRASH')


# ─────────────────────────────────────────────────────────────────────────────
#  Tab: Import
# ─────────────────────────────────────────────────────────────────────────────

def draw_import(layout, context, st):
    box = layout.box()
    box.label(text="Import Session", **_icon_id("import_session", 'SCENE_DATA'))
    col = box.column(align=True)
    col.scale_y = 1.15
    col.operator("ht.import_session", text="1  Session Models",
                 **_icon_id("import_session_models", 'SCENE_DATA'))
    col.operator("ht.rig_fixer", text="2  Fix Rig Rest Poses",
                 **_icon_id("rig_fixer", 'ARMATURE_DATA'))
    col.operator("ht.import_animations", text="3  Animations (Folder)",
                 **_icon_id("import_animations", 'ANIM'))
    col.operator("ht.import_camera_animations", text="4  Camera Animations (Folder)",
                 **_icon_id("import_camera_animations", 'CAMERA_DATA'))
    col.operator("ht.import_shape_key_animations", text="5  Shape Key Anims (Folder)",
                 **_icon_id("import_shape_key_animations", 'SHAPEKEY_DATA'))
    col.operator("ht.import_session_sounds", text="6  Session Sounds",
                 **_icon_id("import_session_sounds", 'SOUND'))

    box = layout.box()
    box.label(text="Standalone", icon='IMPORT')
    col = box.column(align=True)
    col.operator("ht.import_mdl", text="MDL Model",
                 **_icon_id("import_mdl", 'MESH_DATA'))
    col.operator("ht.import_dmx_animation", text="DMX Animation",
                 **_icon_id("import_dmx_anim", 'ACTION'))
    col.operator("ht.import_dmx_camera", text="DMX Camera",
                 **_icon_id("import_dmx_camera", 'CAMERA_DATA'))
    col.operator("ht.import_shape_keys", text="Shape Keys (DMX)",
                 **_icon_id("import_shape_keys", 'SHAPEKEY_DATA'))

    box = layout.box()
    box.label(text="Source Engine Utils",
              **_icon_id("source_engine_utils", 'TOOL_SETTINGS'))
    col = box.column(align=True)
    col.operator("ht.remove_drivers", text="Remove Drivers",
                 **_icon_id("remove_drivers", 'DRIVER'))
    col.operator("ht.symmetrize_shape_keys", text="Symmetrize Shape Keys",
                 **_icon_id("symmetrize_shapekeys", 'MOD_MIRROR'))
    col.operator("ht.util_import_shape_keys", text="Util: Import Shape Keys",
                 **_icon_id("util_import_shape_keys", 'SHAPEKEY_DATA'))
    col.operator("ht.bake_localvars", text="Bake Localvars",
                 **_icon_id("bake_localvars", 'RENDER_ANIMATION'))
    col.separator()
    col.operator("ht.fix_eye_constraints", text="Fix Eye Constraints",
                 **_icon_id("fix_eye_constraints", 'CONSTRAINT_BONE'))
    col.operator("ht.fix_rig", text="Fix Rig (Reference DMX)",
                 **_icon_id("fix_rig", 'ARMATURE_DATA'))
    col.separator()
    col.operator("ht.split_camera_cuts", text="Split Camera Cuts",
                 **_icon_id("split_camera", 'SEQUENCE'))
    col.separator()
    col.operator("ht.organize_scene", text="Organize Scene",
                 **_icon_id("organize_scene", 'OUTLINER'))
    col.operator("ht.reduce_lag_epsilon", text="Reduce Lag (Epsilon)",
                 **_icon_id("reduce_lag", 'MOD_SMOOTH'))


# ─────────────────────────────────────────────────────────────────────────────
#  Tab: Tutorial
# ─────────────────────────────────────────────────────────────────────────────

_TUTORIAL = (
    ("The Session Workflow", (
        "1.  Set Your SFM usermod path in Preferences.",
        "2.  Import tab → 1 Session Models.",
        "     Re-run until 'Remaining: 0' - chunked.",
        "3.  2 Fix Rig Rest Poses.",
        "4.  3 Animations (Folder).",
        "5.  4 Camera Animations if exported.",
        "6.  5 Shape Key Anims for facial animation.",
    )),
    ("Reading the Anim Set tab", (
        "Orange  = model imported, nothing else yet.",
        "Yellow  = rig has an animation.",
        "Green   = shape key animation on its meshes.",
    )),
    ("Cleanup tools", (
        "Remove Model-Only Rigs deletes every orange",
        "rig and its meshes - clears unused imports.",
        "Remove All Animation fully resets rigs: strips",
        "root/axis empties, clears bone AND shape-key",
        "animation, restores rest poses via the Rig",
        "Fixer, recolors folders white - ready to",
        "re-import animation cleanly.",
    )),
    ("Animation Scale", (
        "DMX Animation and Animations (Folder) have an",
        "Animation Scale option. It multiplies location",
        "keys (bones + root) to fit a resized model.",
    )),
)


def _tick(col, ok, label_ok, label_no):
    row = col.row(align=True)
    if ok:
        row.label(text="", icon='CHECKMARK')
        row.label(text=label_ok)
    else:
        row.label(text="", icon='X')
        row.label(text=label_no)


def draw_tutorial(layout, context, st):
    # ── Live environment readout ──
    box = layout.box()
    box.label(text="Environment", icon='SETTINGS')
    col = box.column(align=True)

    base = _usermod_path()
    if base is not None and base.exists():
        col.row(align=True).label(text="", icon='CHECKMARK')
        c2 = col.column(align=True)
        c2.scale_y = 0.8
        c2.label(text="Usermod path OK:")
        # Show the tail of the path so it fits the sidebar
        s = str(base)
        c2.label(text=s if len(s) <= 42 else "…" + s[-41:])
    else:
        col.row(align=True).label(text="Usermod path NOT set / missing",
                                  icon='X')
        col.label(text="Set it in Preferences → HoovyTools.")

    col.separator()
    _tick(col, _sourceio_installed(),
          "SourceIO installed", "SourceIO not installed")

    # ── Static workflow help ──
    for title, lines in _TUTORIAL:
        box = layout.box()
        box.label(text=title, icon='HELP')
        c = box.column(align=True)
        c.scale_y = 0.85
        for line in lines:
            c.label(text=line)


# ─────────────────────────────────────────────────────────────────────────────
#  The panel
# ─────────────────────────────────────────────────────────────────────────────

class HT_PT_sidebar(Panel):
    bl_idname = "HT_PT_sidebar"
    bl_label = "HoovyTools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HoovyTools"

    def draw_header(self, context):
        self.layout.label(text="", **_icon_id("hoovy_logo", 'CONSOLE'))

    def draw(self, context):
        layout = self.layout
        st = settings(context)

        if st is None:
            box = layout.box()
            box.alert = True
            box.label(text="Panel settings unavailable.", icon='ERROR')
            box.label(text="Re-enable the addon and restart Blender.")
            return

        row = layout.row(align=True)
        row.scale_y = 1.3
        row.prop(st, "active_tab", expand=True)
        layout.separator()

        tab = st.active_tab
        if tab == 'ASE':
            draw_ase(layout, context, st)
        elif tab == 'IMPORT':
            draw_import(layout, context, st)
        else:
            draw_tutorial(layout, context, st)


# ─────────────────────────────────────────────────────────────────────────────
#  Register
# ─────────────────────────────────────────────────────────────────────────────

_CLASSES = (
    HoovyToolsPanelSettings,
    HT_OT_purge_model_only,
    HT_OT_strip_all_animation,
    HT_PT_sidebar,
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
    bpy.types.Scene.ht_panel = bpy.props.PointerProperty(type=HoovyToolsPanelSettings)


def unregister():
    try:
        del bpy.types.Scene.ht_panel
    except Exception:
        pass
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
