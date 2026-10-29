"""
Panel.py - HoovyTools sidebar (3D View, N key)
==============================================

    Main  |  Tools  |  Dev

  Main    The session: load it, pick a shot, IMPORT SHOT / WHOLE SESSION, or
          run its seven elements one at a time.
  Tools   MAIN TOOLS (the five one-file importers), then the shelves: Batch,
          Shape Keys, Source IO Help, Scene Organizers, Cleanup.
  Dev     DEVELOPER MODE, Wiring (Where It Looks inside), Behavior Report
          (PRINT HELP, Logs inside), Configure (Layouts, Popups, Anims
          Folder, Shot Timing, Frame Rate, Session Automation) and Imported
          Session (the scene readout and the rig roster). Body lives in
          Developer.py.

  The rig roster colours: ORANGE = model imported, YELLOW = animation on the
  rig, GREEN = shape key animation on its meshes.

DRAW-TIME RULES
===============
draw() runs on every redraw and must never mutate the blend file.
Status detection is read-only introspection. The cleanup operators do
mutate, but they are operators (button-triggered), never called from
draw().
"""

import os
import re

import bpy
from bpy.props import EnumProperty, BoolProperty, StringProperty
from bpy.types import Panel, Operator, PropertyGroup

# ─────────────────────────────────────────────────────────────────────────────
# Status colours (RGBA, matched to Blender's dark theme)
# ─────────────────────────────────────────────────────────────────────────────

C_MODEL = (0.90, 0.55, 0.18, 1.0)   # orange - model imported, nothing else
C_ANIM  = (0.92, 0.84, 0.25, 1.0)   # yellow - animation imported
C_FULL  = (0.35, 0.78, 0.42, 1.0)   # green  - shape key animation present

# collection color_tag values used by the harvester
TAG_OK   = "COLOR_04"   #green
TAG_FAIL = "COLOR_06"   #red
TAG_NONE = "NONE"       #white / default


def _dot(layout, color):
    """Colour swatch via the node-socket template (only arbitrary-RGBA call)."""
    try:
        layout.template_node_socket(color=color)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Icon bridge (wired by __init__.register)
# ─────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None


def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────

TAB_ITEMS = [
    ('MAIN',  "Main",     "The session workflow: connect a session, then import "
                          "it - whole, or one element at a time. The rig "
                          "roster lives at the bottom", 'HOME', 0),
    ('TOOLS', "Tools",    "Every operator the addon has, grouped: the session "
                          "workflow, the standalone importers, utilities and "
                          "scene organisers", 'TOOL_SETTINGS', 1),
    ('DEV',   "Dev",      "Developer - Wiring (is everything found), Behavior "
                          "Report (PRINT HELP: the .txt to send), Developer Mode, "
                          "Configure, the model importer and credits", 'CONSOLE', 2),
]

DEV_TIER_ITEMS = [
    ('ALL',     "All",     "Every roadmap item, all three tiers"),
    ('HIGH',    "High",    "Blocking work only"),
    ('MEDIUM',  "Medium",  "Structural work only"),
    ('BACKLOG', "Backlog", "Experimental and research only"),
]


def _layout_choice_changed(self, _context):
    """Persist the after-import layout choice - the update callback catches
    every route into the value, the same reasoning as the popup switches."""
    try:
        from ..tools import Layout_Builder
        Layout_Builder.save_choice(layout=self.layout_after_import)
    except Exception:                                         # noqa: BLE001
        pass


def _render_choice_changed(self, _context):
    """Persist the after-import render-engine choice, same doctrine."""
    try:
        from ..tools import Layout_Builder
        Layout_Builder.save_choice(render=self.render_after_import)
    except Exception:                                         # noqa: BLE001
        pass


class HoovyToolsPanelSettings(PropertyGroup):
    active_tab: EnumProperty(  # type: ignore
        name="Tab", items=TAB_ITEMS, default='MAIN',
    )
    dev_tier: EnumProperty(  # type: ignore
        name="Tier", items=DEV_TIER_ITEMS, default='ALL',
        description="Which roadmap tier the priorities list shows",
    )
    dev_hide_done: BoolProperty(  # type: ignore
        name="Hide done", default=False,
        description="Leave finished roadmap items out of the list",
    )
    developer_mode: BoolProperty(  # type: ignore
        name="Developer Mode", default=False,
        description=(
            "Show extra options and experimental tools throughout the UI.\n\n"
            "This changes what the PANEL displays, never what an operator can "
            "do - press any import and its full option set is in the dialog "
            "and in the redo panel either way"),
    )
    #DEFAULT ON. Naming a camera "hoovy" IS the request to split it - that
    #is the whole point of the magic name, and a toggle that ships off means
    #the name silently does nothing on a fresh scene, which reads as "the
    #feature doesn't register". The match string is specific enough that
    #nothing is ever split by accident
    auto_split_hoovy_camera: BoolProperty(  # type: ignore
        name="Auto-split 'hoovy' cameras", default=True,
        description=(
            "During a session import, any camera whose name contains the match "
            "string is run through Split Camera Cuts automatically.\n\n"
            "ON by default: naming a camera hoovy in SFM is the request. "
            "Shots land in the purple __HoovyTools Camera Split__ collection, "
            "which is deliberately NOT one of the collections a re-import "
            "clears - so re-importing replaces the take without throwing the "
            "splits away with it"),
    )
    auto_split_match: bpy.props.StringProperty(  # type: ignore
        name="Camera name contains", default="hoovy",
        description=(
            "Case-insensitive substring, matched against the camera and its "
            "root/axis empties. Only cameras that match are split"),
    )
    auto_fps: BoolProperty(  # type: ignore
        name="Auto-match frame rate", default=True,
        description=(
            "Set the scene's frame rate to the session's the moment a "
            "session is connected. Off: the Frame Rate section still warns "
            "on a mismatch and offers the one-click fix, exactly as before"),
    )
    layout_after_import: EnumProperty(  # type: ignore
        name="After session import",
        items=[('OFF', "Off", "Leave the workspace alone"),
               ('DEFAULT', "Default", "Build Blender's stock layout"),
               ('TWO', "Two Screen", "Build the two-screen layout"),
               ('THREE', "Three Monitor", "Build the three-monitor layout")],
        default='OFF',
        update=lambda self, ctx: _layout_choice_changed(self, ctx),
        description=(
            "Build one of the captured workspace layouts automatically "
            "when Import Whole Session finishes. Saved to the add-on's "
            "config, so the choice survives into every future .blend"),
    )
    render_after_import: EnumProperty(  # type: ignore
        name="Engine after import",
        items=[('OFF', "Off", "Leave the render engine alone"),
               ('EEVEE', "EEVEE", "Apply the tuned EEVEE preset"),
               ('CYCLES', "Cycles", "Apply the tuned Cycles preset")],
        default='OFF',
        update=lambda self, ctx: _render_choice_changed(self, ctx),
        description=(
            "Apply a render-engine preset automatically when Import Whole "
            "Session finishes - the same tuned settings as the Layouts "
            "box's EEVEE / Cycles buttons. Saved to the add-on's config, "
            "so the choice survives into every future .blend"),
    )


SECTIONS = (
    ("sec_session",        True),
    ("sec_elements",       True),
    # TOOLS - Main Tools open, every shelf below it closed
    ("sec_main_tools",     True),
    ("sec_tool_mdl",       False),
    ("sec_tool_anim",      False),
    ("sec_tool_shapekeys", False),
    ("sec_tool_camera",    False),
    ("sec_tool_particles", False),
    ("sec_hoovy_importers", True),
    ("sec_tool_mdl_hoovy", False),
    ("sec_tool_vmt",       False),
    ("sec_tool_vtf",       False),
    ("sec_batch",          False),
    ("sec_shapekeys",      False),
    ("sec_sourceio",       False),
    ("sec_organizers",     False),
    ("sec_camera_work",    True),      # inside Scene Organizers
    ("sec_cleanup",        False),
    ("sec_clean_rigs",     True),      # inside Cleanup
    ("sec_clean_scene",    True),
    ("sec_clean_world",    True),
    # DEV - closed
    ("sec_wiring",         False),
    ("sec_folders",        False),     # Where It Looks, inside Wiring
    ("sec_behavior",       False),
    ("sec_logs",           False),     # inside Behavior Report
    ("sec_configure",      False),
    ("sec_layouts",        True),      # inside Configure, the first thing
    ("sec_render_presets", False),     # inside Layouts
    ("sec_popups",         False),
    ("sec_popup_list",     False),     # inside Popups
    ("sec_anims_folder",   False),
    ("sec_shot_timing",    False),
    ("sec_framerate",      False),
    ("sec_autosplit",      False),
    ("sec_scene",          False),     # imported session
    ("sec_rigs",           True),      # its rig roster
    ("sec_model_engine",   False),     # 1.21.0 MODEL IMPORTER, above Misc
    ("sec_misc",           False),     # 1.19.0 MISC, above Credits
    ("sec_mdl_embedded",   True),      # inside Misc: MDL Import (Standalone)
    ("sec_credits",        False),     # the last section of the Dev tab
)

HoovyToolsPanelSettings.__annotations__.update({
    key: BoolProperty(
        name="Open Section",
        description="Fold or unfold this section. Nothing inside changes - "
                    "a folded section's tools all still work from menus and "
                    "search",
        default=default,
    )
    for key, default in SECTIONS
})


def fold_section(layout, st, key, title, icon_kw, default_open=True):
    """A titled section box that CLOSES.

    Returns (box, head): `box` is the section body to draw into, or None
    when the section is folded - the caller draws nothing and moves on.
    `head` is the header row, for the callers that hang a button or a count
    on the right side (wiring's recheck, the logs tally).

    THE HEADER IS ALWAYS DRAWN, and it always carries the section's OWN
    coloured icon - one colour per section, the user's rule. The arrow is
    the fold control; clicking the coloured icon does nothing, so the two
    cannot be confused.
    """
    box = layout.box()
    head = box.row(align=True)
    is_open = bool(getattr(st, key, default_open)) if st else default_open
    if st is not None and hasattr(st, key):
        head.prop(st, key, text="", emboss=False,
                  icon='DOWNARROW_HLT' if is_open else 'RIGHTARROW')
    head.label(text=title, **icon_kw)
    return (box if is_open else None), head


def settings(context):
    return getattr(context.scene, "ht_panel", None)


# ─────────────────────────────────────────────────────────────────────────────
# Status detection (read-only, draw-safe)
# ─────────────────────────────────────────────────────────────────────────────

def _action_has_keys(action):
    if action is None:
        return False
    try:
        from ..core import anim_compat
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
# Cleanup helpers (shared by the operators)
# ─────────────────────────────────────────────────────────────────────────────

def _top_collection(arm):
    """Direct child of the Scene Collection whose subtree holds *arm*.

    `in` ON A bpy_prop_collection IS A NAME LOOKUP, NOT MEMBERSHIP. The inner
    search used to end `return child if hit in col.children else hit`, and
    `hit` is a Collection, so Blender raised

        TypeError: bpy_prop_collection.__contains__:
                   expected a string or a tuple of strings

    the moment a rig sat two collection levels deep - which is exactly the
    shape a session import builds, so Remove All Animation died on any scene
    that had been organised. A flat import never nested, which is why it
    survived every test.

    The returned collection was never used for anything either: the caller
    only asks WHICH top-level collection, and takes `top` from its own loop.
    So the recursion answers a yes/no question now, `col.objects` is the one
    remaining `in`, and that one is correct because it IS keyed by name."""

    def holds(col, obj):
        if obj.name in col.objects:
            return True
        return any(holds(child, obj) for child in col.children)

    for top in bpy.context.scene.collection.children:
        if holds(top, arm):
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

        #drop the whole animation_data block (action + drivers + NLA) in one go
        if sk.animation_data is not None:
            try:
                sk.animation_data_clear()
                cleared = True
            except Exception:
                # fall back to clearing the action alone
                try:
                    sk.animation_data.action = None
                    cleared = True
                except Exception:
                    pass

        # reset every non-basis key to 0 so the mesh sits at rest
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

    #unparent the armature but leave its local (basis) transform intact
    if arm.parent in (root, axis) and arm.parent is not None:
        arm.parent = None
        # reset the parent-inverse so a later manual reparent starts clean.
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

    # clear shape-key animation on bound meshes and reset them to rest
    removed["meshes"] = _clear_shapekey_animation(arm)

    top = _top_collection(arm)
    if top is not None and top.color_tag != TAG_NONE:
        top.color_tag = TAG_NONE
        removed["recolored"] = True

    return removed


# ─────────────────────────────────────────────────────────────────────────────
# Operators
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_purge_model_only(Operator):
    """Delete every rig in the scene that has no animation on it

A model-only rig is one that was imported but never received bone or
flex animation - usually a leftover from a partial or repeated import.

It removes the armature, its meshes and its now-empty collections, and
lists what went. Rigs carrying ANY animation are never touched, so this
cannot eat work you have done.

Undoable, but read the list in the report first"""
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
            #delete the top collection if it's now empty of objects
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

        from ..core import Report_UI
        Report_UI.report(context, "panel_tools", "Purge Model-Only Rigs",
                         lines, level='WARNING', icon="TRASH", operator=self,
                         prefix="PANEL",
                         summary=f"Purged {len(names)} model-only rig(s), "
                                 f"{removed_objs} object(s) deleted")
        return {"FINISHED"}


class HT_OT_strip_all_animation(Operator):
    """Return every rig in the scene to its pre-animation state

Removes the bone action AND the shape key animation from every rig, puts
the flex sliders back to rest, deletes the root and axis empties, and
re-applies the reference rest poses so the rigs end up model-only again.

Use it to re-import a session cleanly rather than importing on top of
what is already there.

Unparenting preserves each armature's local transform, so strip and
re-import is idempotent - the axis correction is applied once, not
stacked, and rigs do not rotate 90 degrees on the second pass"""
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

        # restore rest poses via the Rig Fixer, then recolor white last so the
        # fixer's own yellow tagging doesn't leave the scene mislabeled
        rest_line = None
        if self.restore_rest_poses:
            try:
                from ..session import Import_Session
                fx = Import_Session.run_rig_fixer()
                rest_line = (f"Rest poses  : {fx['fixed']} fixed, "
                             f"{fx['skipped']} skipped")
                if fx["errors"]:
                    rest_line += f", {fx['errors']} error(s)"
                # Rig Fixer recolors fixed rigs yellow - reset to white so the
                # final state reads as clean model-only
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

        from ..core import Report_UI
        Report_UI.report(context, "panel_tools", "Remove All Animation",
                         lines, level='WARNING', icon="TRASH", operator=self,
                         prefix="PANEL",
                         summary=f"Removed animation from {touched} rig(s), "
                                 f"{empties} empties")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# Environment detection (Tutorial tab)
# ─────────────────────────────────────────────────────────────────────────────

def _usermod_path():
    """Current resolved usermod base, or None if it can't be read."""
    try:
        from ..session import Import_Session
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
# Tab: Animation Set Editor
# ─────────────────────────────────────────────────────────────────────────────

def draw_imported_session(layout, context, st):
    """IMPORTED SESSION - on the Dev tab since 1.18.0. The
    scene readout, then the rig roster. Each rig row keeps its UPDATE button,
    which re-imports that one rig's animation from whatever is wired in - the
    connected animations folder, or a fresh extract of the session."""
    from ..session import Session_Paths
    arms = [o for o in context.scene.objects if o.type == 'ARMATURE']
    box, head = fold_section(layout, st, "sec_scene", "Imported Session",
                             _icon_id("sec_scene", 'OUTLINER'))
    if head is not None and arms:
        tally = head.row()
        tally.alignment = 'RIGHT'
        tally.enabled = False
        tally.label(text=f"{len(arms)}")
    if box is None:
        return

    grid = box.column(align=True)
    grid.scale_y = 0.85
    animated = sum(1 for a in arms if _armature_has_animation(a))
    faces = sum(1 for a in arms if _armature_has_shapekey_animation(a))
    grid.label(text=f"{len(arms)} rig(s), {animated} animated, "
                    f"{faces} with facial", icon='ARMATURE_DATA')
    cams = [o for o in context.scene.objects if o.type == 'CAMERA']
    lights = [o for o in context.scene.objects if o.type == 'LIGHT']
    grid.label(text=f"{len(cams)} camera(s), {len(lights)} light(s), "
                    f"{len(context.scene.timeline_markers)} marker(s)",
               icon='CAMERA_DATA')
    grid.label(text=f"frames {context.scene.frame_start} - "
                    f"{context.scene.frame_end}", icon='TIME')
    if not arms:
        return

    rbox, _rh = fold_section(box, st, "sec_rigs", "Rigs",
                             _icon_id("sec_rigs", 'ARMATURE_DATA'))
    if rbox is None:
        return
    wired = (Session_Paths.session_file(context.scene) is not None
             or Session_Paths.animations_dir(context.scene) is not None)

    counts = {'MODEL': 0, 'ANIM': 0, 'FULL': 0}
    statuses = []
    for arm in sorted(arms, key=lambda a: a.name.lower()):
        status = armature_status(arm)
        counts[status] += 1
        statuses.append((arm, status))

    row = rbox.row(align=True)
    for key in ('MODEL', 'ANIM', 'FULL'):
        color, label = _STATUS_META[key]
        sub = row.row(align=True)
        if not _dot(sub, color):
            sub.label(text="●")
        sub.label(text=label)

    col = rbox.column(align=True)
    for arm, status in statuses:
        color, label = _STATUS_META[status]
        row = col.row(align=True)
        if not _dot(row, color):
            row.label(text="●")
        row.label(text=arm.name, icon='OUTLINER_OB_ARMATURE')
        row.label(text=label)
        btn = row.row(align=True)
        btn.enabled = wired
        btn.operator("ht.update_rig_anim", text="",
                     icon='FILE_REFRESH').rig_name = arm.name

    foot = rbox.row(align=True)
    foot.enabled = False
    foot.label(text=f"{counts['MODEL']} model  ·  {counts['ANIM']} animated  ·  "
                    f"{counts['FULL']} complete")


# ─────────────────────────────────────────────────────────────────────────────
# Tab: Tools
# ─────────────────────────────────────────────────────────────────────────────

def _section(layout, st, key, title, icon_key, fallback='TOOL_SETTINGS'):
    """A titled box that folds. THE TITLE IS THE WHOLE EXPLANATION.

    This used to print two lines of grey prose under every heading - four
    sections, eight lines, on a sidebar. Persistent text is read once and then
    becomes furniture you scroll past forever, and it was pushing the buttons
    it described off the bottom of the panel.

    THE TOOLTIPS ARE WHERE THE EXPLANATION LIVES. Every operator here has a
    docstring written to be read on hover - that work is already done, it
    costs nothing until somebody wants it, and it is attached to the exact
    button they are pointing at.

    CLOSABLE, AND ONE COLOUR PER SECTION: every
    section binds a fold arrow to its SECTIONS key and wears its own coloured
    icon. Returns the body column, or None when folded - the caller guards
    its body with `if col is not None`.
    """
    box, _head = fold_section(layout, st, key, title,
                              _icon_id(icon_key, fallback))
    return box.column(align=True) if box is not None else None


MAIN_TOOLS = (
    ("ht.import_mdl",           "1  Import Model (.mdl)",      "import_mdl",        'MESH_DATA'),
    ("ht.import_dmx_animation", "2  Import Animation (.dmx)",  "import_dmx_anim",   'ACTION'),
    ("ht.import_shape_keys",    "3  Import Shape Keys (.dmx)", "import_shape_keys", 'SHAPEKEY_DATA'),
    ("ht.import_dmx_camera",    "4  Import Camera (.dmx)",     "import_dmx_camera", 'CAMERA_DATA'),
)
# 3.0.0: the fold each main tool's ribbon uses
MAIN_TOOL_FOLDS = {"ht.import_mdl": "sec_tool_mdl", "ht.import_dmx_animation": "sec_tool_anim",
                   "ht.import_shape_keys": "sec_tool_shapekeys", "ht.import_dmx_camera": "sec_tool_camera"}
HOOVY_IMPORTERS = (
    ("ht.import_mdl_embedded", "1  Import MDL",  "import_mdl", 'MESH_DATA',       "sec_tool_mdl_hoovy", None),
    ("ht.import_vmt",          "2  Import VMT",  "import_vmt", 'MATERIAL',        "sec_tool_vmt", "Import VMT"),
    ("ht.import_vtf",          "3  Import VTF",  "import_vtf", 'IMAGE_DATA',      "sec_tool_vtf", "Import VTF"),
)
TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "# tools")


def tool_script(tool):
    """The newest '<tool> (Vn).py' in # tools\\<tool>, or None."""
    folder = os.path.join(TOOLS_DIR, tool)
    best = None
    for f in os.listdir(folder) if os.path.isdir(folder) else ():
        m = re.fullmatch(re.escape(tool) + r" \(V(\d+)\)\.py", f)
        if m and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), os.path.join(folder, f))
    return best[1] if best else None


def tool_variables(props):
    """A tool's variables for its ribbon: wm.operator_properties_last() is exactly what the next press uses - minus
    what Blender does not carry between presses (hidden, skip-save) and what a panel cannot draw."""
    out = []
    if props is None:
        return out
    for prop in props.bl_rna.properties:
        if prop.identifier == "rna_type" or prop.is_hidden or prop.is_skip_save:
            continue
        if prop.type in ("POINTER", "COLLECTION"):
            continue
        out.append(prop.identifier)
    return out


def ribbon(layout, context, st, key, idname, text, icon_kw, enabled=True, tool=None):
    """3.0.0: one tool, the shape both add-ons share - [arrow] [the tool's button], and unfolded its variables.
    `tool` (Developer Mode): a folder button for its Text Editor version."""
    box = layout.box()
    head = box.row(align=True)
    head.use_property_split = False
    try:
        props = context.window_manager.operator_properties_last(idname) if context is not None else None
    except Exception:                                         # noqa: BLE001
        props = None
    names = tool_variables(props)
    is_open = bool(getattr(st, key, False)) if (st is not None and key) else False
    if names and st is not None and key and hasattr(st, key):
        head.prop(st, key, text="", emboss=False, icon='DOWNARROW_HLT' if is_open else 'RIGHTARROW')
    else:
        head.label(text="", icon='BLANK1')
    btn = head.row(align=True)
    btn.enabled = enabled
    btn.operator(idname, text=text, **icon_kw)
    if tool:
        head.operator("ht.open_tool_folder", text="", icon='FILE_FOLDER').tool = tool
    if not (is_open and names):
        return
    col = box.column()
    col.use_property_split = True
    col.use_property_decorate = False
    for n in names:
        col.prop(props, n)
#5 is the HoovyTools Particle Import add-on's own .pcf importer, drawn as
#it's - a copy here would be the one that drifts.
PARTICLE_TOOL = ("htp.choose_particle_system", "5  Import Particles (.pcf)",
                 "import_pcf", 'PARTICLES')

# What Developer Mode shows under each main importer - the same properties
# its file browser sidebar has; this only decides whether you have to open
# the browser to see them.
MAIN_TOOL_OPTIONS = {
    "ht.import_mdl":           ("apply_eye_fix", "fix_rig", "rig_static_prop",
                                "scale"),
    "ht.import_dmx_animation": ("rig_mode", "add_root_helpers", "up_axis",
                                "anim_scale"),
    "ht.import_shape_keys":    (),
    "ht.import_dmx_camera":    ("fix_quat_flips", "scale", "lens_offset"),
}


def particles_ready():
    """(registered, installed) for the Particle Import add-on's .pcf importer."""
    try:
        if "choose_particle_system" in dir(bpy.ops.htp):
            return True, True
    except Exception:                                         # noqa: BLE001
        pass
    try:
        import addon_utils
        from ..core import siblings
        for name in siblings.names("particles"):
            loaded, _enabled = addon_utils.check(name)
            if loaded or name in {m.__name__ for m in addon_utils.modules()}:
                return False, True
    except Exception:                                         # noqa: BLE001
        pass
    return False, False


def draw_main_tool_buttons(layout, context=None, dev=False, st=None):
    """The five main importers, in order. File > Import draws them as buttons; the panel (st given, 3.0.0) as
    ribbons - each one folds on its own and unfolds to its variables."""
    for idname, text, icon_key, fallback in MAIN_TOOLS:
        if st is not None:
            ribbon(layout, context, st, MAIN_TOOL_FOLDS[idname], idname, text, _icon_id(icon_key, fallback))
        else:
            layout.operator(idname, text=text, **_icon_id(icon_key, fallback))
    ready, installed = particles_ready()
    op_id, text, icon_key, fallback = PARTICLE_TOOL
    if ready and st is not None:
        ribbon(layout, context, st, "sec_tool_particles", op_id, text, _icon_id(icon_key, fallback))
    elif ready:
        layout.operator(op_id, text=text, **_icon_id(icon_key, fallback))
    elif installed:
        layout.operator("ht.enable_addon", text=text + " - enable",
                        **_icon_id(icon_key, fallback)).which = "particles"
    else:
        row = layout.row()
        row.enabled = False
        row.label(text=text + " - needs Particle Import",
                  **_icon_id(icon_key, fallback))


def draw_tools(layout, context, st):
    """
    THE TOOLS TAB, AS A HIERARCHY.

        MAIN TOOLS          the five importers - one file each
        SFM UTILS - BATCH   the connected Animations folder, and folders at a time
        SHAPE KEYS          repairs on the selected mesh's shape keys
        SOURCE IO HELP      rest poses and eyes, for rigs already in the scene
        SCENE ORGANIZERS    Camera Work
        CLEANUP             Rigs And Animation / Scene / Materials And World

    Every operator is drawn ONCE. The session steps live on Main and nowhere
    else - the olive "pick a session file" copies that used to sit here were
    the same eight operators a second time.
    """
    dev = bool(getattr(st, "developer_mode", False))
    from ..session import Session_Paths as _SP

    #── main tools ───────────────────────────────────────────────────────
    col = _section(layout, st, "sec_main_tools", "Main Tools",
                   "sec_main_tools", 'IMPORT')
    if col is not None:
        draw_main_tool_buttons(col, context, dev=dev, st=st)

    # ── hoovytools importers (3.0.0) ─────────────────────────────────────
    # MDL / VMT / VTF thru HoovyTools' own code - SourceIO isn't needed for any of them (maps still go
    # through SourceIO, as the session import's last step).
    col = _section(layout, st, "sec_hoovy_importers", "HoovyTools Importers",
                   "sec_hoovy_importers", 'IMPORT')
    if col is not None:
        for idname, text, icon_key, fallback, key, tool in HOOVY_IMPORTERS:
            ribbon(col, context, st, key, idname, text, _icon_id(icon_key, fallback), tool=tool if dev else None)

    col = _section(layout, st, "sec_batch", "SFM Utils - Batch", "sec_batch",
                   'FILE_REFRESH')
    if col is not None:
        anim = _SP.animations_dir(context.scene)
        row = col.row(align=True)
        row.scale_y = 1.15
        if anim is not None:
            row.label(text=anim.name[:26],
                      **_icon_id("anims_folder", 'FILE_FOLDER'))
            row.operator("ht.open_search_folder", text="",
                         icon='FILE_FOLDER').path = str(anim)
            row.operator("ht.connect_animations", text="", icon='FILEBROWSER')
        else:
            row.operator("ht.connect_animations",
                         text="LOAD ANIMATIONS FOLDER",
                         **_icon_id("anims_folder", 'FILEBROWSER'))
        sub = col.row(align=True)
        sub.enabled = anim is not None
        sub.operator("ht.update_animations", text="Rescan Animations Folder",
                     **_icon_id("rescan_animations", 'FILE_REFRESH'))
        try:
            col.separator(type='LINE')
        except TypeError:
            col.separator()
        col.operator("ht.import_animations", text="Import Animations (Folder)",
                     **_icon_id("import_animations", 'ANIM'))
        col.operator("ht.import_camera_animations",
                     text="Import Camera Animations (Folder)",
                     **_icon_id("import_camera_animations", 'CAMERA_DATA'))
        col.operator("ht.import_shape_key_animations",
                     text="Import Shape Key Anims (Folder)",
                     **_icon_id("import_shape_key_animations", 'SHAPEKEY_DATA'))

    col = _section(layout, st, "sec_shapekeys", "Shape Keys",
                   "utils_shape_keys", 'SHAPEKEY_DATA')
    if col is not None:
        col.operator("ht.util_import_shape_keys",
                     text="Import Shape Keys Only",
                     **_icon_id("util_import_shape_keys", 'SHAPEKEY_DATA'))
        col.operator("ht.remove_drivers", text="Remove Shape Key Drivers",
                     **_icon_id("remove_drivers", 'DRIVER'))
        col.operator("ht.symmetrize_shape_keys", text="Symmetrize Shape Keys",
                     **_icon_id("symmetrize_shapekeys", 'MOD_MIRROR'))
        col.operator("ht.bake_localvars", text="Bake HWM Localvars",
                     **_icon_id("bake_localvars", 'RENDER_ANIMATION'))

    #── SOURCE IO HELP ───────────────────────────────────────────────────
    #For rigs already in the scene. Import Model and Import Models do the
    #rest pose and the eyes by themselves since 1.18.0
    col = _section(layout, st, "sec_sourceio", "Source IO Help",
                   "sec_sourceio", 'ARMATURE_DATA')
    if col is not None:
        col.operator("ht.rig_fixer", text="Fix All Rig Rest Poses",
                     **_icon_id("sio_rig_fixer", 'ARMATURE_DATA'))
        col.operator("ht.fix_rig", text="Fix Rig From Reference DMX",
                     **_icon_id("sio_fix_rig", 'ARMATURE_DATA'))
        col.operator("ht.fix_eye_constraints", text="Fix Eye Constraints",
                     **_icon_id("sio_fix_eyes", 'CONSTRAINT_BONE'))

    # ── SCENE ORGANIZERS ─────────────────────────────────────────────────
    col = _section(layout, st, "sec_organizers", "Scene Organizers",
                   "sec_organizers", 'OUTLINER')
    if col is not None:
        cam, _h = fold_section(col, st, "sec_camera_work", "Camera Work",
                               _icon_id("split_camera", 'SEQUENCE'))
        if cam is not None:
            cc = cam.column(align=True)
            cc.operator("ht.split_camera_cuts", text="Split Camera Into Shots",
                        **_icon_id("split_camera", 'SEQUENCE'))
            cc.operator("ht.camera_handles", text="Add Pre/Post Handles",
                        **_icon_id("camera_handles", 'IPO_BEZIER'))
            cc.operator("ht.camera_shot_report", text="Report Shot Boundaries",
                        **_icon_id("camera_shot_report", 'INFO'))
            cc.operator("ht.rig_cameras_on_bones", text="Rig Cameras On Bones",
                        **_icon_id("utils_camera", 'BONE_DATA'))

    counts = {'MODEL': 0, 'ANIM': 0, 'FULL': 0}
    for o in context.scene.objects:
        if o.type == 'ARMATURE':
            counts[armature_status(o)] += 1
    col = _section(layout, st, "sec_cleanup", "Cleanup", "sec_cleanup",
                   'TRASH')
    if col is not None:
        sub, _h = fold_section(col, st, "sec_clean_rigs", "Rigs And Animation",
                               _icon_id("purge_model_only", 'ARMATURE_DATA'))
        if sub is not None:
            c = sub.column(align=True)
            r = c.row(align=True)
            r.enabled = counts['MODEL'] > 0
            r.operator("ht.purge_model_only",
                       text=f"Remove Model-Only Rigs ({counts['MODEL']})",
                       **_icon_id("purge_model_only", 'TRASH'))
            r = c.row(align=True)
            r.enabled = (counts['ANIM'] + counts['FULL']) > 0
            r.operator("ht.strip_all_animation", text="Remove All Animation",
                       **_icon_id("strip_all_animation", 'TRASH'))
            c.operator("ht.delete_euler_spins", text="Delete Rotation Spins",
                       **_icon_id("delete_euler_spins", 'ORIENTATION_GIMBAL'))
            c.operator("ht.offset_everything", text="Offset Everything",
                       **_icon_id("offset_everything", 'NEXT_KEYFRAME'))
        sub, _h = fold_section(col, st, "sec_clean_scene", "Scene",
                               _icon_id("organize_scene", 'OUTLINER'))
        if sub is not None:
            c = sub.column(align=True)
            c.operator("ht.organize_scene", text="Sort Into Collections",
                       **_icon_id("organize_scene", 'OUTLINER'))
            c.operator("ht.reduce_lag_epsilon", text="Reduce Viewport Lag",
                       **_icon_id("reduce_lag", 'MOD_SMOOTH'))
            c.operator("ht.match_sfm_visibility",
                       text="Match SFM Visibility + Camera",
                       **_icon_id("match_sfm_visibility", 'HIDE_ON'))
        sub, _h = fold_section(col, st, "sec_clean_world", "Materials And World",
                               _icon_id("vertexlit_fix", 'MATERIAL'))
        if sub is not None:
            c = sub.column(align=True)
            c.operator("ht.vertexlit_fix", text="Source IO VertexlitGeneric Fix",
                       **_icon_id("vertexlit_fix", 'MATERIAL'))
            c.operator("ht.register_skydome", text="Register Skydome",
                       **_icon_id("register_skydome", 'WORLD'))


STEP_BUTTONS = (
    ("ht.step_models",           "1  Import Models",      "import_session_models", 'MESH_DATA'),
    ("ht.step_animations",       "2  Import Animations",  "session_animations", 'ANIM'),
    ("ht.step_shapekeys",        "3  Import Shape Keys",  "session_shape_key_animations", 'SHAPEKEY_DATA'),
    ("ht.step_cameras",          "4  Import Cameras",     "session_camera_animations", 'CAMERA_DATA'),
    ("ht.import_session_sounds", "5  Import Sounds",      "import_session_sounds", 'SOUND'),
    ("ht.step_lights",           "6  Import Lights",      "import_lights", 'LIGHT_POINT'),
    ("ht.step_particles",        "7  Import Particles",   "import_particles", 'PARTICLES'),
    ("ht.step_map",              "8  Import Map",         "import_map", 'WORLD'),
)

# which properties Developer Mode shows inline per step. The operator still
# owns them all; this is only the shortlist the panel surfaces
STEP_OPTIONS = {
    "ht.step_models":     ("fix_rigs",),
    "ht.step_animations": ("root_motion", "up_axis", "extract_first",
                           "rebase", "anim_scale"),
    "ht.step_shapekeys":  ("extract_first", "allow_proxy"),
    "ht.step_cameras":    ("extract_first", "scale"),
    "ht.step_lights":     ("energy_scale", "scale", "do_animation"),
    "ht.step_particles":  ("scale", "only_emitting"),
}

# the one-click's switches - Developer Mode shows them under the IMPORT SHOT
# button, and the button asks with all of them before it runs
ONECLICK_OPTIONS = ("do_models", "do_extract", "do_fps", "do_animation",
                    "do_sounds", "do_lights", "do_particles", "do_organize",
                    "do_euler", "do_visibility", "do_map")


def _draw_props_box(col, context, idname, names):
    """An operator's own properties inline, from its last-used settings -
    `wm.operator_properties_last` is exactly what the button will use next,
    so editing them here edits what actually happens."""
    if not names:
        return
    try:
        props = context.window_manager.operator_properties_last(idname)
    except Exception:                                         # noqa: BLE001
        props = None
    box = col.box().column(align=True)
    box.scale_y = 0.9
    if props is None:
        box.label(text="options appear after first use", icon='INFO')
        return
    for n in names:
        if hasattr(props, n):
            box.prop(props, n)


def _draw_step_options(col, context, idname):
    """A session step's own properties inline (Developer Mode)."""
    _draw_props_box(col, context, idname, STEP_OPTIONS.get(idname, ()))


def draw_main(layout, context, st):
    """
    THE MAIN TAB: one session, imported whole or one element at a time.

    COMPACT BY DEFAULT. Developer Mode adds the session readout buttons, the
    one-click's switches under its button (and the button then asks with all
    of them before it runs), and every step's own options under the step.

    Nothing below the loader is drawn until a session is connected - without
    one every button would be dead or would ask for the file again. The scene
    readout and the rig roster are on the Dev tab, as IMPORTED SESSION.
    """
    from ..session import Session_Paths
    dev = bool(getattr(st, "developer_mode", False))
    pr = Session_Paths.project(context)
    session = Session_Paths.session_file(context.scene)

    box, head = fold_section(layout, st, "sec_session",
                             "DMX Session" if session is None else session.stem,
                             _icon_id("session_load", 'FILE_FOLDER'))
    if session is not None:
        right = head.row(align=True)
        right.alignment = 'RIGHT'
        right.operator("ht.connect_session", text="",
                       **_icon_id("session_load", 'FILE_FOLDER'))
        right.operator("ht.clear_project_paths", text="", icon='X')
    if box is not None:
        if session is None:
            load = box.column(align=True)
            load.scale_y = 2.4
            load.operator("ht.connect_session", text="LOAD DMX SESSION",
                          **_icon_id("session_load", 'FILE_FOLDER'))
        else:
            # which shot - ABOVE the import button, because it changes what
            # that button does
            Session_Paths.draw_shot_grid(box, context, icon_id=_icon_id)


            box.separator(factor=0.5)
            idx_btn, _nm_btn = Session_Paths.shot_choice(context.scene)
            run = box.column(align=True)
            run.scale_y = 2.0
            run.operator("ht.session_one_click",
                         text=("IMPORT WHOLE SESSION"
                               if idx_btn is None or idx_btn < 0
                               else f"IMPORT SHOT {idx_btn + 1}"),
                         **_icon_id("import_session", 'PLAY'))
            if dev:
                row = box.row(align=True)
                if pr is not None and pr.session_sets >= 0:
                    row.label(text=f"{pr.session_sets} set(s)")
                row.operator("ht.session_report", text="Read Session",
                             **_icon_id("session_report", 'VIEWZOOM'))
                row.operator("ht.session_shots", text="Shots",
                             **_icon_id("shots", 'SEQUENCE'))
                _draw_props_box(box, context, "ht.session_one_click",
                                ONECLICK_OPTIONS)

    if session is None:
        return

    # ── ...or one element at a time ──────────────────────────────────────
    box, head = fold_section(layout, st, "sec_elements",
                             "Import Session Elements",
                             _icon_id("sec_elements", 'PRESET'))
    if box is not None:
        col = box.column(align=True)
        for idname, text, icon_key, fallback in STEP_BUTTONS:
            icon_kw = (_icon_id(icon_key, fallback) if icon_key
                       else {"icon": fallback})
            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator(idname, text=text, **icon_kw)
            if dev:
                _draw_step_options(col, context, idname)
                col.separator()


def _tick(col, ok, label_ok, label_no):
    row = col.row(align=True)
    row.label(text="", icon='CHECKMARK' if ok else 'X')
    row.label(text=label_ok if ok else label_no)



class HT_OT_set_panel_tab(Operator):
    """Switch the panel's tab"""
    bl_idname = "ht.set_panel_tab"
    bl_label = "Tab"
    bl_options = {'INTERNAL'}

    tab: EnumProperty(  # type: ignore
        items=[(i, n, d) for i, n, d, _icon, _num in TAB_ITEMS], options={'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        return {i: d for i, _n, d, _icon, _num in TAB_ITEMS}.get(properties.tab, "")

    def execute(self, context):
        st = settings(context)
        if st is not None:
            st.active_tab = self.tab
        return {'FINISHED'}


class HT_OT_open_tool_folder(Operator):
    """Open the folder holding this tool's Text Editor version"""
    bl_idname = "ht.open_tool_folder"
    bl_label = "Open Tool Folder"
    bl_options = {'INTERNAL'}

    tool: StringProperty(options={'HIDDEN'})  # type: ignore

    @classmethod
    def description(cls, context, properties):
        script = tool_script(properties.tool) if properties.tool else None
        if script is None:
            return ""
        return ("Open the folder holding the Text Editor version of %s.\n\n"
                "\"%s\" does the same from Blender's Text Editor: set the values at its top, press Run "
                "Script.\n\nTHIS FEATURE WAS ADDED IN VERSION 3.0.0 AND IS IN EXPERIMENTAL STAGE"
                % (properties.tool, os.path.basename(script)))

    def execute(self, context):
        folder = os.path.join(TOOLS_DIR, self.tool)
        if not self.tool or tool_script(self.tool) is None:
            self.report({'ERROR'}, "Missing: %s" % folder)
            return {'CANCELLED'}
        if bpy.app.background:
            print("[TOOLS]  tool folder: %s" % folder)
            return {'FINISHED'}
        bpy.ops.wm.path_open(filepath=folder)
        return {'FINISHED'}


class HT_PT_sidebar(Panel):
    bl_idname = "HT_PT_sidebar"
    bl_label = "SFM Session Importer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HoovyTools"
    bl_order = 0

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

        # MAIN carries the workflow, so it gets the room. The other
        # three share what is left. prop_enum draws one enum value at a
        # time, which is the only way to give them different widths
        # 3.0.0: buttons that wear the add-on's own icons (an enum tab can only show Blender's), Dev a small
        # icon-only tab at the right - its tooltip names it
        bar = layout.row()
        bar.scale_y = 1.3
        row = bar.row(align=True)
        tab_now = st.active_tab
        for ident, label, key, fallback in (('MAIN', "Main", "tab_main", 'HOME'),
                                            ('TOOLS', "Tools", "tab_tools", 'TOOL_SETTINGS')):
            row.operator("ht.set_panel_tab", text=label, depress=(tab_now == ident),
                         **_icon_id(key, fallback)).tab = ident
        bar.separator(factor=1.0)
        dev = bar.row(align=True)
        dev.ui_units_x = 1.6
        dev.operator("ht.set_panel_tab", text="", depress=(tab_now == 'DEV'),
                     **_icon_id("tab_dev", 'CONSOLE')).tab = 'DEV'
        layout.separator()

        tab = st.active_tab
        if tab == 'TOOLS':
            draw_tools(layout, context, st)
        elif tab == 'DEV':
            from . import Developer
            Developer.draw_developer(layout, context, st)
        else:
            # MAIN, and also whatever a stale saved enum resolves to
            draw_main(layout, context, st)


# ─────────────────────────────────────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────────────────────────────────────

_CLASSES = (
    HoovyToolsPanelSettings,
    HT_OT_set_panel_tab,
    HT_OT_open_tool_folder,
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
