"""
Utils_Shape_Keys.py  —  part of HoovyTools
===========================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Source Engine Utils ▸ Shape Keys ▸
           Remove Drivers
           Symmetrize L Suffix Shape Keys
           Import Shape Keys (.dmx)
           Bake LOCALVARS (.qc)

All four operators act on the active MESH object in the scene.
They call into Import_Shape_Keys for their logic so there is no duplication.
"""

bl_info = {
    "name":        "HoovyTools: Utils — Shape Keys",
    "description": "Standalone shape key utilities for the HoovyTools pipeline",
    "author":      "HoovyTools",
    "version":     (2, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > Source Engine Utils > Shape Keys",
    "category":    "Import-Export",
}

import bpy
from ..core import paths as _paths
from math import ceil
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
#  OPERATOR 1 — REMOVE DRIVERS
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_RemoveDrivers(Operator):
    """Remove every shape key driver from the active mesh

SourceIO wires drivers between flex controllers and shape keys. They
fight imported flex ANIMATION - the driver keeps overwriting the value
the animation just set - so they are removed before facial animation
lands. The shape key import does this for you; this is the manual button
for a mesh you are fixing by hand.

The shape keys themselves are untouched. Only the drivers go"""
    bl_idname  = "ht.remove_drivers"
    bl_label   = "Remove Drivers"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh object first.")
            return {"CANCELLED"}

        from ..importers import Import_Shape_Keys
        removed = Import_Shape_Keys.remove_shapekey_drivers(obj)

        self.report({"INFO"}, f"Removed {removed} shape key driver(s) from '{obj.name}'.")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR 2 — SYMMETRIZE L SUFFIX SHAPE KEYS
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_SymmetrizeShapeKeys(Operator):
    """Create the missing right-side shape key for every left-side one

An HWM face is authored as a symmetric delta that the Source compiler
splits into a left and a right half. When only one side arrives, this
rebuilds the other by weighting the delta across the model's symmetry
plane, with a smooth blend so the seam does not crease.

The two weights sum to 1 at every vertex, so both halves at full strength
reproduce the original delta exactly - it is a SPLIT, not an invention.

Skips anything already split, so running it twice is safe"""
    bl_idname  = "ht.symmetrize_shape_keys"
    bl_label   = "Symmetrize L Suffix Shape Keys"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh object first.")
            return {"CANCELLED"}

        from ..importers import Import_Shape_Keys
        created = Import_Shape_Keys.stereo_split(obj)

        if created == 0:
            self.report({"WARNING"},
                        f"No R keys created — fewer than threshold 'L' keys found on '{obj.name}'.")
        else:
            self.report({"INFO"}, f"Created {created} R key(s) on '{obj.name}'.")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR 3 — IMPORT SHAPE KEYS (.dmx)  — flex only, no bake / no stereo
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_UtilImportShapeKeys(Operator, ImportHelper):
    """PICK .dmx (face / flex) - ONE file, raw, onto the ACTIVE MESH

        Write flex animation onto the active mesh, and nothing else

The plain version: no driver removal, no stereo split, no HWM bake. One
f-curve per flex controller the file animates.

Use it when you want the raw controller curves to look at. For a face
that actually moves, use Intelligent Flex Animation instead - the bake is
what makes combination controls fire, and without it most faces barely
move"""
    bl_idname  = "ht.util_import_shape_keys"
    bl_label   = "Import Shape Keys (.dmx)"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".dmx"
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh object first.")
            return {"CANCELLED"}

        from ..importers import Import_Shape_Keys
        try:
            # Call the public single-stage function directly — no flag mutation needed.
            result = Import_Shape_Keys.import_flex_dmx(self.filepath, obj)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        imported   = result["channels"]
        max_frame  = result["max_frame"]
        frame_rate = result["frame_rate"]
        dmx_name   = Path(self.filepath).name

        self.report({"INFO"},
                    f"Imported {imported} flex channel(s) from '{dmx_name}'  "
                    f"({frame_rate} fps  0–{int(ceil(max_frame))} fr).")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR 4 — BAKE LOCALVARS (.qc)
# ──────────────────────────────────────────────────────────────────────────────

def _qc_face_data_dir() -> str:
    """Absolute path to HoovyTools/QC Face Data/ as a string for the file browser."""
    folder = _paths.qc_face_data()
    folder.mkdir(exist_ok=True)
    return str(folder)


class HT_OT_BakeLocalvars(Operator, ImportHelper):
    """PICK .qc (compile script) - the model's QC, the one with the
        flexcontroller lines in it

        Evaluate the model's QC expressions and bake them onto its shape keys

Select the mesh. Needs the model's .qc in _QC Face Data.

A QC bridges the controllers SFM animates to the flexes the mesh has,
with %localvar expressions. Without evaluating them, a face driven by
combination controls barely moves.
    """
    #  BELOW THE TOOLTIP CAP. Blender truncates an operator description
    #  at 1023 characters, without a warning, mid-word. These paragraphs
    #  were part of the docstring and were already being cut off before
    #  anyone could read them, so they live here instead - kept, but out
    #  of the tooltip's budget.
    #  THREE THINGS THIS GETS RIGHT
    #  the % sigil    a QC refers to other localvars as %name. That is modulo
    #  in Python, so those expressions used to be a syntax
    #  error that silently evaluated to zero - and it was every
    #  expression that referenced another one
    #  intermediates  many localvars are not outputs at all; they exist to
    #  feed other expressions, and are evaluated in dependency
    #  order rather than read as zero
    #  eyelids        three collapsed targets reconstructed from the QC's own
    #  eyeball heights, which is what restores blinking
    #
    #  Reports what resolved, what is an intermediate, and what had no source
    #

    bl_idname  = "ht.bake_localvars"
    bl_label   = "Bake LOCALVARS (.qc)"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".qc"
    filter_glob: StringProperty(default="*.qc", options={"HIDDEN"})

    def invoke(self, context, event):
        self.filepath = _qc_face_data_dir() + "/"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh object first.")
            return {"CANCELLED"}

        qc_path = Path(self.filepath)
        if not qc_path.exists() or qc_path.suffix.lower() != ".qc":
            self.report({"ERROR"}, f"Not a valid .qc file: {self.filepath}")
            return {"CANCELLED"}

        sk = obj.data.shape_keys
        if not sk or not sk.animation_data or not sk.animation_data.action:
            self.report({"ERROR"},
                        "No flex animation found on the active mesh. "
                        "Import shape keys first.")
            return {"CANCELLED"}

        from ..importers import Import_Shape_Keys
        try:
            bake_result = Import_Shape_Keys.bake_hwm_localvars(obj, qc_path)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if not bake_result["ok"]:
            self.report({"ERROR"}, f"Bake failed: {bake_result['error']}")
            return {"CANCELLED"}

        b = bake_result
        self.report({"INFO"},
                    f"Baked {b['baked']} localvar(s) / {b['keys']} key(s)  "
                    f"exact={b['exact']}  fuzzy={b['fuzzy']}  "
                    f"unresolved={b['unresolved']}")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU DRAWING  (called from __init__.py)
# ──────────────────────────────────────────────────────────────────────────────

class HT_MT_utils_shapekeys_submenu(bpy.types.Menu):
    bl_idname = "HT_MT_utils_shapekeys_submenu"
    bl_label  = "Shape Keys"

    def draw(self, context):
        layout = self.layout
        layout.operator(HT_OT_RemoveDrivers.bl_idname,
                        text="Remove Drivers",
                        **_icon_id("remove_drivers", "DRIVER"))
        layout.operator(HT_OT_SymmetrizeShapeKeys.bl_idname,
                        text="Symmetrize L Suffix Shape Keys",
                        **_icon_id("symmetrize_shapekeys", "MOD_MIRROR"))
        layout.separator()
        layout.operator(HT_OT_UtilImportShapeKeys.bl_idname,
                        text="Import Shape Keys (.dmx)",
                        **_icon_id("util_import_shape_keys", "SHAPEKEY_DATA"))
        layout.operator(HT_OT_BakeLocalvars.bl_idname,
                        text="Bake LOCALVARS (.qc)",
                        **_icon_id("bake_localvars", "RENDER_ANIMATION"))


def draw_utils_shapekeys_entry(layout):
    """Called from HT_MT_utils_submenu to add the Shape Keys nested entry."""
    layout.menu(
        HT_MT_utils_shapekeys_submenu.bl_idname,
        text="Shape Keys",
        **_icon_id("utils_shape_keys", "SHAPEKEY_DATA"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (
    HT_OT_RemoveDrivers,
    HT_OT_SymmetrizeShapeKeys,
    HT_OT_UtilImportShapeKeys,
    HT_OT_BakeLocalvars,
    HT_MT_utils_shapekeys_submenu,
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
