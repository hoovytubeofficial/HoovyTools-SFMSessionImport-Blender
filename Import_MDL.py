"""
Import_MDL.py  —  part of HoovyTools
=====================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Source Model (.mdl)

Wraps SourceIO's MDL importer, then applies the HoovyTools eye constraint fix:
  1. Adds a 'viewTarget' bone to the imported armature
  2. Creates a 'viewTarget' Empty locked to that bone via Child Of
  3. Adds Track To → viewTarget on every eye empty (eye_0, eye_1, etc.)

Requires SourceIO to be installed and enabled.
"""

bl_info = {
    "name":        "HoovyTools: Import Source Model (.mdl)",
    "description": "Import MDL via SourceIO, then apply HoovyTools eye constraint fix",
    "author":      "HoovyTools",
    "version":     (1, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > Source Model (.mdl)",
    "category":    "Import-Export",
}

import bpy
from pathlib import Path
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy_extras.io_utils import ImportHelper


# ──────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────────────────────────────────────

# Distance in front of the head the viewTarget bone tail sits
VIEW_TARGET_FORWARD_DIST = 10.0

# Eye empty name prefixes/patterns to recognise
EYE_PREFIXES = ("eye_", "Eye_", "eyeball_", "Eyeball_")


# ──────────────────────────────────────────────────────────────────────────────
#  ICON HELPER
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
#  EYE FIX  (shared with Utils_MDL)
# ──────────────────────────────────────────────────────────────────────────────

def _is_eye_empty(obj) -> bool:
    return (obj.type == 'EMPTY'
            and any(obj.name.startswith(p) for p in EYE_PREFIXES))


def _find_armature_for_empty(eye_empty) -> bpy.types.Object | None:
    """Return the armature the eye empty is Child-Of constrained to."""
    for con in eye_empty.constraints:
        if con.type == 'CHILD_OF' and con.target and con.target.type == 'ARMATURE':
            return con.target
    return None


def _find_head_bone(armature) -> str | None:
    """
    Return the name of the most likely 'head' bone.
    Checks Child Of subtarget on the first eye empty found, then falls back to
    a name search.
    """
    # Try to read the subtarget from an existing eye empty
    for obj in bpy.data.objects:
        if _is_eye_empty(obj):
            for con in obj.constraints:
                if (con.type == 'CHILD_OF'
                        and con.target == armature
                        and con.subtarget):
                    return con.subtarget

    # Name-based fallback
    candidates = ('bip_head', 'ValveBiped.Bip01_Head1',
                  'head', 'Head', 'Bip01_Head1')
    for name in candidates:
        if name in armature.data.bones:
            return name
    return None


def apply_eye_fix(armature: bpy.types.Object) -> dict:
    """
    Full eye constraint fix for *armature*.

    Steps:
      1. Add 'viewTarget' edit bone (parented to head bone)
      2. Create 'viewTarget' Empty with Child Of → viewTarget bone
      3. For each eye empty: add / replace Track To → viewTarget Empty

    Returns a result dict:
      {"ok": bool, "error": str, "eyes_fixed": int, "vt_bone": str}
    """
    from mathutils import Vector

    result = {"ok": False, "error": "", "eyes_fixed": 0, "vt_bone": "viewTarget"}

    if armature.type != 'ARMATURE':
        result["error"] = "Object is not an armature"
        return result

    # ── Collect eye empties that belong to this armature ──────────────────
    eye_empties = [
        obj for obj in bpy.data.objects
        if _is_eye_empty(obj) and _find_armature_for_empty(obj) == armature
    ]

    if not eye_empties:
        result["error"] = "No eye empties found constrained to this armature"
        return result

    head_bone_name = _find_head_bone(armature)

    # ── Step 1: add viewTarget bone ───────────────────────────────────────
    linked_here = armature.name not in bpy.context.scene.collection.objects
    if linked_here:
        bpy.context.scene.collection.objects.link(armature)

    prev_active = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')

    edit_bones = armature.data.edit_bones

    # Remove stale viewTarget bone if it already exists
    if 'viewTarget' in edit_bones:
        edit_bones.remove(edit_bones['viewTarget'])

    # Position viewTarget at average eye-empty world location (in armature space)
    arm_mat_inv = armature.matrix_world.inverted()
    avg_pos_world = sum(
        (obj.matrix_world.translation for obj in eye_empties),
        Vector()
    ) / len(eye_empties)
    avg_pos_local = arm_mat_inv @ avg_pos_world

    arm_size    = max(armature.dimensions) if max(armature.dimensions) > 0 else 1.0
    bone_length = arm_size * 0.10

    vt_bone            = edit_bones.new('viewTarget')
    vt_bone.head       = avg_pos_local
    vt_bone.tail       = avg_pos_local + Vector((0, 0, bone_length))  # points up (+Z)
    vt_bone.use_deform = False
    # No parent — viewTarget must be root-level

    bpy.ops.object.mode_set(mode='OBJECT')

    if linked_here:
        bpy.context.scene.collection.objects.unlink(armature)
    bpy.context.view_layer.objects.active = prev_active

    # ── Step 2: viewTarget Empty (per-armature) ───────────────────────────
    vt_empty_name = f"viewTarget_{armature.name}"
    vt_empty = bpy.data.objects.get(vt_empty_name)
    if vt_empty is None:
        vt_empty = bpy.data.objects.new(vt_empty_name, None)
        vt_empty.empty_display_type = 'ARROWS'
        vt_empty.empty_display_size = 2.0
        vt_empty.show_in_front      = True

    # Make sure it lives in the same collection as the armature
    if vt_empty.name not in bpy.context.scene.collection.objects:
        for col in armature.users_collection:
            if vt_empty.name not in col.objects:
                col.objects.link(vt_empty)
                break
        else:
            bpy.context.scene.collection.objects.link(vt_empty)

    # Child Of → viewTarget bone  (clear any old Child Of first)
    for con in list(vt_empty.constraints):
        if con.type == 'CHILD_OF':
            vt_empty.constraints.remove(con)

    child_of         = vt_empty.constraints.new('CHILD_OF')
    child_of.target  = armature
    child_of.subtarget = 'viewTarget'
    child_of.inverse_matrix.identity()

    # ── Step 3: Track To on each eye empty ────────────────────────────────
    for eye_obj in eye_empties:
        # Remove any existing Track To so we don't stack them
        for con in list(eye_obj.constraints):
            if con.type == 'TRACK_TO':
                eye_obj.constraints.remove(con)

        track              = eye_obj.constraints.new('TRACK_TO')
        track.target       = vt_empty
        track.track_axis   = 'TRACK_NEGATIVE_Y'
        track.up_axis      = 'UP_Z'
        track.target_space = 'WORLD'
        track.owner_space  = 'WORLD'

        result["eyes_fixed"] += 1

    result["ok"] = True
    return result


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_ImportMDL(Operator, ImportHelper):
    """Import a Source Engine .mdl via SourceIO, then apply HoovyTools eye fix"""
    bl_idname  = "ht.import_mdl"
    bl_label   = "Source Model (.mdl)"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".mdl"
    filter_glob: StringProperty(default="*.mdl", options={"HIDDEN"})

    # ── HoovyTools addition ────────────────────────────────────────────────
    apply_eye_fix: BoolProperty(
        name="Apply Eye Fix",
        description="Add viewTarget bone + Track To constraints after import",
        default=True,
    )

    # ── SourceIO pass-through options (exact property names from ModelOptions) ──
    scale: FloatProperty(
        name="World Scale",
        default=0.01905, min=0.0001, precision=6,
    )
    use_bvlg: BoolProperty(
        name="Use BlenderVertexLitGeneric Shader",
        default=False,
    )
    write_qc: BoolProperty(
        name="Write QC",
        default=True,
    )
    import_physics: BoolProperty(
        name="Import Physics",
        default=False,
    )
    load_refpose: BoolProperty(
        name="Load Ref Pose",
        default=False,
    )
    import_animations: BoolProperty(
        name="Load Animations",
        default=False,
    )
    create_flex_drivers: BoolProperty(
        name="Create Drivers for Flexes",
        default=False,
    )
    bodygroup_grouping: BoolProperty(
        name="Group Meshes by Bodygroup",
        default=True,
    )
    import_textures: BoolProperty(
        name="Import Materials",
        default=True,
    )
    discover_resources: BoolProperty(
        name="Mount Discovered Content",
        default=True,
    )

    def execute(self, context):
        # ── Check SourceIO is available ───────────────────────────────────
        try:
            import SourceIO  # noqa: F401
        except ImportError:
            self.report({"ERROR"},
                        "SourceIO is not installed / enabled. "
                        "Install it first from https://github.com/REDxEYE/SourceIO")
            return {"CANCELLED"}

        # ── Snapshot objects before import ────────────────────────────────
        before = set(bpy.data.objects.keys())

        # ── Call SourceIO's MDL import operator ───────────────────────────
        try:
            mdl_path = Path(self.filepath)
            # directory is only a registered property on Blender 4.1+.
            # On older versions get_directory() derives it from filepath automatically.
            _mdl_kwargs = dict(
                filepath            = str(mdl_path),
                files               = [{"name": mdl_path.name}],
                scale               = self.scale,
                use_bvlg            = self.use_bvlg,
                write_qc            = self.write_qc,
                import_physics      = self.import_physics,
                load_refpose        = self.load_refpose,
                import_animations   = self.import_animations,
                create_flex_drivers = self.create_flex_drivers,
                bodygroup_grouping  = self.bodygroup_grouping,
                import_textures     = self.import_textures,
                discover_resources  = self.discover_resources,
            )
            if bpy.app.version >= (4, 1, 0):
                _mdl_kwargs["directory"] = str(mdl_path.parent)
            bpy.ops.sourceio.mdl(**_mdl_kwargs)
        except Exception as exc:
            self.report({"ERROR"}, f"SourceIO import failed: {exc}")
            return {"CANCELLED"}

        # ── Find the new armature ─────────────────────────────────────────
        after    = set(bpy.data.objects.keys())
        new_objs = [bpy.data.objects[n] for n in (after - before)]
        armatures = [o for o in new_objs if o.type == 'ARMATURE']

        if not armatures:
            self.report({"WARNING"},
                        "Import succeeded but no armature found — eye fix skipped.")
            return {"FINISHED"}

        armature = armatures[0]

        # ── Apply eye fix ─────────────────────────────────────────────────
        if self.apply_eye_fix:
            fix = apply_eye_fix(armature)
            if fix["ok"]:
                self.report({"INFO"},
                            f"Imported '{Path(self.filepath).name}'  "
                            f"— eye fix: {fix['eyes_fixed']} eye(s) tracked to viewTarget.")
            else:
                self.report({"WARNING"},
                            f"Imported OK but eye fix skipped: {fix['error']}")
        else:
            self.report({"INFO"}, f"Imported '{Path(self.filepath).name}'.")

        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU
# ──────────────────────────────────────────────────────────────────────────────

def draw_menu_item(layout):
    layout.operator(
        HT_OT_ImportMDL.bl_idname,
        text="Source Model (.mdl)",
        **_icon_id("import_mdl", "MESH_DATA"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (HT_OT_ImportMDL,)


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
    bpy.ops.ht.import_mdl("INVOKE_DEFAULT")
