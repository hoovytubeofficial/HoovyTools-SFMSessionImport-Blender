"""
Import_MDL.py  —  part of HoovyTools
=====================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Source Model (.mdl)

Wraps SourceIO's MDL importer at scale 1.0, then does what a session's
1 Import Models does to every model:
  - a $staticprop (meshes only) gets its one-bone rig
  - the eye fix: a 'viewTarget' bone + Track To on every eye empty
  - the rest pose from the rig's reference .dmx in Faulty Rigs, the same
    procedure as Fix All Rig Rest Poses
No straightener: SourceIO lands Source models Z-up already (measured on
40s_spy and body_man_generic_a, 2-4 degrees off +Z); a prop's longest side is
not its up - money_stack_a lies flat because it is flat - so turning by the
bounding box would tip props over. The report says whether a character
stands Z-up.

THE ENGINE: SourceIO when it is installed and enabled, else the EMBEDDED
importer - the user's standalone IMPORT SOURCE MDL.py, carried as
importers/Standalone_MDL.py (SourceIO's own code + the texture decoder in one
file). Engine: Auto / SourceIO / Embedded on the operator; DEVELOPER > MISC
draws HT_OT_ImportMDLEmbedded, the same import forced through the embedded
engine, with or without textures. Everything after the import - skin, static
prop rig, eye fix, rest pose, the up check - is the same for both engines.
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
from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper

from ..core import start_folders


def _browsed_path(op, context):
    """The .mdl the file browser has selected right now - the operator's own
    filepath only catches up when you press Import, the browser's params
    follow every click."""
    try:
        params = context.space_data.params
        d, f = params.directory, params.filename
        d = d.decode("utf-8", "replace") if isinstance(d, bytes) else d
        if f:
            return str(Path(d) / f)
    except Exception:                                         # noqa: BLE001
        pass
    return getattr(op, "filepath", "") or ""


def sourceio_ready():
    """1.19.0: SourceIO's MDL operator is registered (installed AND enabled)"""
    try:
        bpy.ops.sourceio.mdl.get_rna_type()
        return True
    except Exception:                                         # noqa: BLE001
        return False


def import_embedded(filepath, scale=1.0, import_textures=True, use_bvlg=False, import_physics=False):
    """1.19.0: one .mdl through the embedded importer (no SourceIO needed) - the user's standalone's own
    import_mdl_file(); returns its report dict. Also the headless entry: a script can call this directly."""
    from . import Standalone_MDL
    return Standalone_MDL.import_mdl_file(filepath, (), float(scale), bool(use_bvlg), bool(import_physics),
                                          import_textures=bool(import_textures))


def _skin_items(self, context):
    from ..core import mdl_skins
    return mdl_skins.enum_items(_browsed_path(self, context) if context else
                                getattr(self, "filepath", ""))


# ──────────────────────────────────────────────────────────────────────────────
# config
# ──────────────────────────────────────────────────────────────────────────────

# distance in front of the head the viewTarget bone tail sits
VIEW_TARGET_FORWARD_DIST = 10.0

#eye empty name prefixes/patterns to recognise
EYE_PREFIXES = ("eye_", "Eye_", "eyeball_", "Eyeball_")


# ──────────────────────────────────────────────────────────────────────────────
# icon helper
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
# EYE FIX  (shared with Utils_MDL)
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
    # try to read the subtarget from an existing eye empty
    for obj in bpy.data.objects:
        if _is_eye_empty(obj):
            for con in obj.constraints:
                if (con.type == 'CHILD_OF'
                        and con.target == armature
                        and con.subtarget):
                    return con.subtarget

    # name-based fallback
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

    #Position viewTarget at average eye-empty world location (in armature space)
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

    # make sure it lives in the same collection as the armature
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
        # remove any existing Track To so we don't stack them
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
# operator
# ──────────────────────────────────────────────────────────────────────────────

class _ImportMDLBase:
    """PICK .mdl (compiled model) - the COMPILED file. Not the .qc, not the
        .smd

        Import one Source model, ready for SFM animation

SourceIO does the model at scale 1.0; then the same three things a session's
1 Import Models does: a static prop gets its one-bone rig, the eyes are
wired to viewTarget, and the rig takes the rest pose from its reference
.dmx in the Faulty Rigs folder.

SCALE DEFAULTS TO 1.0, NOT SOURCEIO'S 0.01905. Everything else in this
add-on - reference DMXs, session extracts, cameras, lights - works in
raw Source units; at 0.01905 a reference rest pose flings every bone
about 52x.

Source models already stand Z-up; the report says so for a character"""
    # 1.19.0: a MIXIN, not the operator - two operators share it. Subclassing a
    # REGISTERED operator class breaks the parent: bpy.ops.ht.import_mdl then
    # returned FINISHED w/o ever running execute (measured).
    bl_label   = "Source Model (.mdl)"
    # NO "REGISTER" - see the note in Report_UI/the constitution
    # REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    # touching any field in it RE-RUNS this operator. Re-running an
    # import re-reads the DMX and rebuilds every f-curve; nudging Scale
    # there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    # with the value you wanted is the safe way to change your mind
    bl_options = {"UNDO"}

    filename_ext = ".mdl"
    filter_glob: StringProperty(default="*.mdl", options={"HIDDEN"})

    # ── HoovyTools additions ───────────────────────────────────────────────
    # first, so it sits at the top of the browser's sidebar: click a .mdl
    # and its skins are listed here before anything is imported.
    skin: EnumProperty(  # type: ignore
        name="Import Skin",
        description=("Which of the model's skins to put on it. The list fills "
                     "in as soon as you click a .mdl in the browser: the skin "
                     "number, then the materials it changes from the default "
                     "(red / blue team, a damaged version, glowing eyes).\n"
                     "THIS FEATURE WAS ADDED IN VERSION 1.18.1 AND IS IN "
                     "EXPERIMENTAL STAGE"),
        items=_skin_items,
    )
    apply_eye_fix: BoolProperty(
        name="Apply Eye Fix",
        description="Add viewTarget bone + Track To constraints after import",
        default=True,
    )
    fix_rig: BoolProperty(  # type: ignore
        name="Fix Rig Rest Pose",
        description=("Give the rig the rest pose SFM animates it in, from its "
                     "reference .dmx in the Faulty Rigs folder - the same as "
                     "Source IO Help > Fix All Rig Rest Poses, for this model. "
                     "A model with no reference keeps SourceIO's rest.\n"
                     "THIS FEATURE WAS ADDED IN VERSION 1.18.0 AND IS IN "
                     "EXPERIMENTAL STAGE"),
        default=True,
    )
    rig_static_prop: BoolProperty(  # type: ignore
        name="Rig Static Props",
        description=("A $staticprop model comes in as meshes only. Give it the "
                     "one 'static_prop' bone SFM animates it by, the meshes "
                     "weighted to it - the same as a session import does.\n"
                     "THIS FEATURE WAS ADDED IN VERSION 1.18.0 AND IS IN "
                     "EXPERIMENTAL STAGE"),
        default=True,
    )

    engine: EnumProperty(  # type: ignore
        name="Engine",
        description=("Which importer reads the .mdl. Auto: SourceIO when it is installed and enabled, else the "
                     "embedded importer that ships inside HoovyTools (no SourceIO needed). Everything after the "
                     "import is the same for both.\n" + "THIS FEATURE WAS ADDED IN VERSION 1.19.0 AND IS IN EXPERIMENTAL STAGE"),
        items=(("AUTO", "Auto", "SourceIO when installed, else the embedded importer"),
               ("SOURCEIO", "SourceIO", "SourceIO's own MDL importer (must be installed and enabled)"),
               ("EMBEDDED", "Embedded", "The importer inside HoovyTools - SourceIO's code carried in one file")),
        default="AUTO",
    )

    # ── SourceIO pass-thru options (exact property names from ModelOptions) ──
    scale: FloatProperty(
        name="World Scale",
        description=(
            "1.0 keeps Source units, which is what the rest of HoovyTools "
            "works in: the session importer, the reference DMX files the rig "
            "fixer applies, camera placement and the light energy scale all "
            "assume it. SourceIO's own default of 0.01905 converts to metres "
            "and makes a model about 52x smaller than everything else - a rig "
            "imported that way is shredded by the rig fixer, because the "
            "reference pose it applies is 52x too large. Change this only if "
            "you are importing a model to use on its own"),
        default=1.0, min=0.0001, precision=6,
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
        # ── Which engine (1.19.0) ─────────────────────────────────────────
        have_sio = sourceio_ready()
        engine = self.engine
        if engine == "AUTO":
            # 1.21.0: Auto also obeys DEVELOPER > Model Importer > Use SourceIO
            from ..core import model_engine
            engine = "SOURCEIO" if (have_sio and model_engine.use_sourceio()) else "EMBEDDED"
        if engine == "SOURCEIO" and not have_sio:
            self.report({"ERROR"},
                        "SourceIO is not installed / enabled - pick Engine: Auto or Embedded, "
                        "or install it from https://github.com/REDxEYE/SourceIO")
            return {"CANCELLED"}

        # ── Snapshot objects before import ────────────────────────────────
        before = set(bpy.data.objects.keys())
        before_objs = set(bpy.data.objects)

        if engine == "EMBEDDED":
            try:
                import_embedded(self.filepath, self.scale, self.import_textures, self.use_bvlg,
                                self.import_physics)
            except Exception as exc:                          # noqa: BLE001
                self.report({"ERROR"}, f"Embedded MDL import failed: {exc}")
                return {"CANCELLED"}
            return self._after(context, before_objs, engine, have_sio)

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
        return self._after(context, before_objs, engine, have_sio)

    def _after(self, context, before_objs, engine, have_sio):
        """everything after the import - the same for both engines"""
        # ── Find the new armature ─────────────────────────────────────────
        new_objs = [o for o in bpy.data.objects if o not in before_objs]
        armatures = [o for o in new_objs if o.type == 'ARMATURE']
        name = Path(self.filepath).name
        lines = [f"Model  : {name}"]
        level = "INFO"
        if engine == "EMBEDDED":
            lines.append("Engine : embedded importer" + ("" if have_sio else " (SourceIO is not installed)")
                         + ("" if self.import_textures else " - no textures"))
        else:
            lines.append("Engine : SourceIO" + ("" if self.import_textures else " - no textures"))

        # ── Skin ─────────────────────────────────────────────────────────
        try:
            want = int(self.skin or 0)
        except (TypeError, ValueError):
            want = 0
        if want:
            from ..core import mdl_skins
            fams = mdl_skins.read_skins(self.filepath)
            if want >= len(fams):
                lines.append(f"Skin   : {want} - this model has {len(fams)} skin(s), "
                             "kept the default")
                level = "WARNING"
            else:
                s = mdl_skins.apply_skin(new_objs, want)
                lines.append(f"Skin   : {mdl_skins.skin_label(fams, want)} "
                             f"({s['slots']} material slot(s) on {s['meshes']} mesh(es))")
                if s["missing"]:
                    lines.append(f"         not found: {', '.join(s['missing'][:4])}")
                    level = "WARNING"
                elif not s["slots"] and not self.import_textures:
                    lines.append("         (Import Materials is off - nothing to swap)")

        if not armatures:
            meshes = [o for o in new_objs if o.type == 'MESH']
            if meshes and self.rig_static_prop:
                from ..session import Import_Session
                arm = Import_Session.build_static_prop_rig(
                    meshes, Path(self.filepath).stem)
                if arm is not None:
                    armatures = [arm]
                    lines.append(f"Static : one-bone rig '{arm.name}' built "
                                 f"for {len(meshes)} mesh(es)")
            if not armatures:
                lines.append("Rig    : none (meshes only)")
                self._report(context, lines, "INFO")
                return {"FINISHED"}

        armature = armatures[0]

        # ── Face data (3.0.0): the model's flex rules as a .qc for the HWM bake ──
        try:
            from .Import_Shape_Keys import ensure_face_qc
            _qc, qnote, qstate = ensure_face_qc(self.filepath, new_objs)
            if qstate != "none":
                lines.append(f"Face   : {qnote}")
            if qstate == "error":
                level = "WARNING"
        except Exception as exc:                              # noqa: BLE001
            lines.append(f"Face   : skipped - {exc}")

        # ── Eye fix ───────────────────────────────────────────────────────
        if self.apply_eye_fix:
            fix = apply_eye_fix(armature)
            if fix["ok"]:
                lines.append(f"Eyes   : {fix['eyes_fixed']} eye(s) tracked to "
                             f"viewTarget")
            else:
                lines.append(f"Eyes   : skipped - {fix['error']}")

        #── Rest pose, the same procedure as Fix All Rig Rest Poses ───────
        if self.fix_rig:
            try:
                from ..session import Import_Session
                r = Import_Session.fix_one_rig(armature)
                lines.append(f"Rest   : {r.get('status', '?')}")
                if str(r.get("status", "")).startswith("✗"):
                    level = "WARNING"
            except Exception as exc:                          # noqa: BLE001
                lines.append(f"Rest   : failed - {exc}")
                level = "WARNING"

        # ── Up axis - a check, not a turn (see the module notes) ─────────
        try:
            from mathutils import Vector
            bones = {b.name.lower(): b for b in armature.data.bones}
            head = next((bones[n] for n in ("bip_head", "valvebiped.bip01_head1",
                                            "head") if n in bones), None)
            pel = next((bones[n] for n in ("bip_pelvis", "valvebiped.bip01_pelvis",
                                           "pelvis", "hips") if n in bones), None)
            if head is not None and pel is not None:
                v = (armature.matrix_world @ head.head_local
                     - armature.matrix_world @ pel.head_local)
                if v.length > 1e-6:
                    import math
                    off = math.degrees(v.normalized().angle(Vector((0, 0, 1))))
                    lines.append(f"Up     : Z" if off < 30.0 else
                                 f"Up     : NOT Z - pelvis to head is {off:.0f} "
                                 f"deg off +Z")
                    if off >= 30.0:
                        level = "WARNING"
        except Exception:                                     # noqa: BLE001
            pass

        self._report(context, lines, level)
        return {"FINISHED"}

    def _report(self, context, lines, level):
        try:
            from ..core import Report_UI
            Report_UI.report(context, "session_models", "Model Imported", lines,
                             level=level, operator=self, prefix="MDL")
        except Exception:                                     # noqa: BLE001
            self.report({level}, "  |  ".join(lines))


# ──────────────────────────────────────────────────────────────────────────────
# menu
# ──────────────────────────────────────────────────────────────────────────────

@start_folders.browser_at("model")          #3.0.0: opens where you work, learns your folder
class HT_OT_ImportMDL(_ImportMDLBase, Operator, ImportHelper):
    __doc__ = _ImportMDLBase.__doc__
    bl_idname = "ht.import_mdl"
    bl_label = "Source Model (.mdl)"
    bl_options = {"UNDO"}


def draw_menu_item(layout):
    layout.operator(
        HT_OT_ImportMDL.bl_idname,
        text="Source Model (.mdl)",
        **_icon_id("import_mdl", "MESH_DATA"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# register / unregister
# ──────────────────────────────────────────────────────────────────────────────

@start_folders.browser_at("model")          #3.0.0: opens where you work, learns your folder
class HT_OT_ImportMDLEmbedded(_ImportMDLBase, Operator, ImportHelper):
    """PICK .mdl (compiled model) - Import Model through the EMBEDDED importer

The same import as Import Model (skin, static prop rig, eye fix, rest pose),
read by the importer that ships inside HoovyTools - SourceIO's own code
carried in one file - whether SourceIO is installed or not. Import Materials
off = geometry, rig, shape keys and eyes only: much quicker, for checking a
pose or a clip.
THIS FEATURE WAS ADDED IN VERSION 1.19.0 AND IS IN EXPERIMENTAL STAGE"""
    bl_idname = "ht.import_mdl_embedded"
    bl_label = "Source Model (.mdl) - Embedded Importer"
    bl_options = {"UNDO"}

    engine: EnumProperty(  # type: ignore
        name="Engine",
        description="This button always uses the embedded importer.\n" + "THIS FEATURE WAS ADDED IN VERSION 1.19.0 AND IS IN EXPERIMENTAL STAGE",
        items=(("EMBEDDED", "Embedded", "The importer inside HoovyTools"),),
        default="EMBEDDED",
    )


_CLASSES = (HT_OT_ImportMDL, HT_OT_ImportMDLEmbedded)


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
