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
from pathlib import Path
from bpy.types import Operator
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper


# ──────────────────────────────────────────────────────────────────────────────
#  ICON HELPER
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR — FIX EYE CONSTRAINTS
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_FixEyeConstraints(Operator):
    """Add viewTarget bone + Empty, wire Track To on eye empties (select the armature first)"""
    bl_idname  = "ht.fix_eye_constraints"
    bl_label   = "Fix Eye Constraints"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({"ERROR"}, "Select the model's armature first.")
            return {"CANCELLED"}

        from .Import_MDL import apply_eye_fix
        fix = apply_eye_fix(obj)

        if not fix["ok"]:
            self.report({"ERROR"}, f"Eye fix failed: {fix['error']}")
            return {"CANCELLED"}

        self.report({"INFO"},
                    f"viewTarget bone added — "
                    f"{fix['eyes_fixed']} eye(s) now tracking viewTarget.")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR — FIX RIG  (singular, manual ref DMX picker)
# ──────────────────────────────────────────────────────────────────────────────

def _faulty_rigs_dir() -> str:
    """HoovyTools/Faulty Rigs/ — opens as the default browser location."""
    folder = Path(__file__).parent / "Faulty Rigs"
    folder.mkdir(exist_ok=True)
    return str(folder)


class HT_OT_FixRig(Operator, ImportHelper):
    """Apply a reference DMX as rest pose on the active armature (singular rig fix)"""
    bl_idname  = "ht.fix_rig"
    bl_label   = "Fix Rig"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".dmx"
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})

    def invoke(self, context, event):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({"ERROR"}, "Select the armature to fix first.")
            return {"CANCELLED"}
        # Open browser directly in Faulty Rigs/
        self.filepath = _faulty_rigs_dir() + "/"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({"ERROR"}, "Select the armature to fix first.")
            return {"CANCELLED"}

        dmx_path = Path(self.filepath)
        if not dmx_path.exists() or dmx_path.suffix.lower() != ".dmx":
            self.report({"ERROR"}, f"Not a valid .dmx file: {self.filepath}")
            return {"CANCELLED"}

        # Delegate to Import_Session's private helpers directly
        from . import Import_Session
        try:
            action = Import_Session._import_reference_dmx(dmx_path, obj)
            if action is None:
                self.report({"ERROR"}, "DMX imported but no action was created.")
                return {"CANCELLED"}
            Import_Session._detach_action(obj)
            Import_Session._apply_pose_as_rest(obj)
            Import_Session._mark_collection_yellow(obj)
        except Exception as exc:
            self.report({"ERROR"}, f"Fix Rig failed: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"},
                    f"Rest pose applied to '{obj.name}' from '{dmx_path.name}'.")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU
# ──────────────────────────────────────────────────────────────────────────────

class MT_HT_utils_mdl_submenu(bpy.types.Menu):
    bl_idname = "MT_HT_utils_mdl_submenu"
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
    """Called from MT_HT_utils_submenu."""
    layout.menu(
        MT_HT_utils_mdl_submenu.bl_idname,
        text="MDL",
        **_icon_id("utils_mdl", "MESH_DATA"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (
    HT_OT_FixEyeConstraints,
    HT_OT_FixRig,
    MT_HT_utils_mdl_submenu,
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
