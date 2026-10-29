"""
Utils_MDL.py  —  part of HoovyTools
=====================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Source Engine Utils ▸ MDL ▸
           Fix Eye Constraints
           Fix Rig

Standalone operators for already-imported SourceIO models.
Select the armature, then run either operator.
"""

bl_info = {
    "name":        "HoovyTools: Utils — MDL",
    "description": "Standalone MDL utilities for the HoovyTools pipeline",
    "author":      "HoovyTools",
    "version":     (1, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > Source Engine Utils > MDL",
    "category":    "Import-Export",
}

import bpy
from ..core import paths as _paths
from pathlib import Path
from bpy.types import Operator
from bpy.props import StringProperty, EnumProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper


# ──────────────────────────────────────────────────────────────────────────────
# icon helper
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
# operator — fix eye constraints
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_FixEyeConstraints(Operator):
    """Add the viewTarget bone and wire the eye empties to track it

Select the armature first.

SFM rigs carry a root-level viewTarget - the thing the eyes look at -
with its own animation channels. A rig that lacks it silently drops that
channel on import with one console line, which reads exactly like
"viewTarget is not animated". It appears in 831 of 4,108 corpus exports,
so this is not an edge case.

This creates the bone from the average of the eye empties and adds the
Track To constraints. It needs those empties to exist - if SourceIO did
not create them, it reports why rather than failing silently"""
    bl_idname  = "ht.fix_eye_constraints"
    bl_label   = "Fix Eye Constraints"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({"ERROR"}, "Select the model's armature first.")
            return {"CANCELLED"}

        from ..importers.Import_MDL import apply_eye_fix
        fix = apply_eye_fix(obj)

        if not fix["ok"]:
            self.report({"ERROR"}, f"Eye fix failed: {fix['error']}")
            return {"CANCELLED"}

        self.report({"INFO"},
                    f"viewTarget bone added — "
                    f"{fix['eyes_fixed']} eye(s) now tracking viewTarget.")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
# OPERATOR — FIX RIG  (singular, manual ref DMX picker)
# ──────────────────────────────────────────────────────────────────────────────

def _faulty_rigs_dir() -> str:
    """HoovyTools/Faulty Rigs/ — opens as the default browser location."""
    folder = _paths.faulty_rigs()
    folder.mkdir(exist_ok=True)
    return str(folder)


def start_path(arm) -> str:
    """Where Fix Rig's file browser opens: the best reference for *arm* (the one
    Fix All would pick for it), else the Faulty Rigs folder."""
    from ..session import Import_Session
    try:
        choices = Import_Session.reference_choices(arm)
    except Exception:                                   # noqa: BLE001
        choices = []
    return str(choices[0][0]) if choices else _faulty_rigs_dir() + "/"


_REF_ITEMS = []       # kept alive: Blender holds the strings of a dynamic enum
_BROWSE = "__BROWSE__"


def _reference_items(self, context):
    """The Faulty Rigs references, the active rig's best match first."""
    from ..session import Import_Session
    arm = context.active_object if context else None
    if arm is not None and arm.type != 'ARMATURE':
        arm = None
    _REF_ITEMS.clear()
    for path, label in Import_Session.reference_choices(arm):
        _REF_ITEMS.append((str(path), label, str(path)))
    _REF_ITEMS.append((_BROWSE, "Browse for another .dmx...",
                       "Pick a reference anywhere on disk"))
    return _REF_ITEMS


class HT_OT_FixRig(Operator, ImportHelper):
    """CHOOSE the reference in a file browser - it opens in the Faulty Rigs
        folder with the best match for the selected rig already picked; its
        search filters the folder, and any .dmx anywhere on disk will do

        Fix the ACTIVE armature's rest pose from one reference DMX

The single-rig version of Fix All Rig Rest Poses, and the SAME procedure:
both rests are stored, and animation already on the rig is kept and
re-keyed onto the new rest. Use it when one character came out wrong and
the rest of the scene should not be touched, or when its reference is not
named after it.

Almost all of what it changes is ROTATION - up to 240 degrees of bone
re-roll against about 0.03 units of movement - so judging it by bone
positions reads as if nothing happened.

THIS FEATURE WAS ADDED IN VERSION 1.24.0 AND IS IN EXPERIMENTAL STAGE."""
    bl_idname  = "ht.fix_rig"
    bl_label   = "Fix Rig"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".dmx"
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})
    # a script may still name the reference outright (reference=<path>); the
    # browser does not show it
    reference: EnumProperty(  # type: ignore
        name="Reference", items=_reference_items, options={"HIDDEN"},
        description="The reference DMX whose rest pose the rig takes")
    browse: BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})  # type: ignore

    def invoke(self, context, event):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({"ERROR"}, "Select the armature to fix first.")
            return {"CANCELLED"}
        self.filepath = start_path(obj)
        self.browse = True
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({"ERROR"}, "Select the armature to fix first.")
            return {"CANCELLED"}
        if not self.browse and self.reference == _BROWSE:
            bpy.ops.ht.fix_rig('INVOKE_DEFAULT', browse=True)
            return {"FINISHED"}
        dmx_path = Path(self.filepath if self.browse else self.reference)
        if not dmx_path.is_file() or dmx_path.suffix.lower() != ".dmx":
            self.report({"ERROR"}, f"Not a valid .dmx file: {dmx_path}")
            return {"CANCELLED"}

        from ..session import Import_Session
        try:
            r = Import_Session.fix_one_rig(obj, reference=dmx_path)
        except Exception as exc:
            self.report({"ERROR"}, f"Fix Rig failed: {exc}")
            return {"CANCELLED"}
        status = r.get("status", "")
        if status.startswith("✗"):
            self.report({"ERROR"}, f"'{obj.name}': {status}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"'{obj.name}' from '{dmx_path.name}': {status}")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
# menu
# ──────────────────────────────────────────────────────────────────────────────

class HT_MT_utils_mdl_submenu(bpy.types.Menu):
    bl_idname = "HT_MT_utils_mdl_submenu"
    bl_label  = "MDL"

    def draw(self, context):
        self.layout.operator(
            HT_OT_FixEyeConstraints.bl_idname,
            text="Fix Eye Constraints",
            **_icon_id("fix_eye_constraints", "BONE_DATA"),
        )
        self.layout.operator(
            HT_OT_FixRig.bl_idname,
            text="Fix Rig",
            **_icon_id("fix_rig", "ARMATURE_DATA"),
        )


def draw_utils_mdl_entry(layout):
    """Called from HT_MT_utils_submenu."""
    layout.menu(
        HT_MT_utils_mdl_submenu.bl_idname,
        text="MDL",
        **_icon_id("utils_mdl", "MESH_DATA"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# register / unregister
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (
    HT_OT_FixEyeConstraints,
    HT_OT_FixRig,
    HT_MT_utils_mdl_submenu,
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
