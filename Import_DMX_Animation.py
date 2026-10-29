"""
Import_DMX_Animation.py  —  part of HoovyTools
===============================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ DMX Animation

PUBLIC API  (call from other HoovyTools scripts)
────────────────────────────────────────────────
    from . import Import_DMX_Animation

    result = Import_DMX_Animation.import_dmx_animation(
        dmx_path = Path("my_anim.dmx"),
        armature = bpy.data.objects["MyArm"],
    )
    # returns:
    # {
    #   "action"      : bpy.types.Action,        # bone pos/rot (from BST)
    #   "root_action" : bpy.types.Action | None, # root-empty action
    #   "root_empty"  : bpy.types.Object | None, # root Empty
    #   "scale_bones" : int,
    #   "root_curves" : int,
    # }
"""

bl_info = {
    "name":        "HoovyTools: Import DMX Animation",
    "description": "Import SFM DMX animation — bones, scale, root transform",
    "author":      "HoovyTools",
    "version":     (1, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > DMX Animation",
    "category":    "Import-Export",
}

import bpy
from math import pi
from pathlib import Path
from mathutils import Matrix, Quaternion, Vector
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy_extras.io_utils import ImportHelper
from .anim_compat import make_action, get_channelbag, fc_find_or_new, iter_fcurves, count_fcurves


# ──────────────────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _get_datamodel():
    """Return the datamodel module via SST's bundled copy."""
    from .SST import get_datamodel
    return get_datamodel()


def _fc(bag, data_path, index, group):
    return fc_find_or_new(bag, data_path, index=index, group_name=group)


def _key(bag, data_path, index, group, frame, value):
    kp = _fc(bag, data_path, index, group).keyframe_points.insert(
        float(frame), float(value), options={"FAST"}
    )
    kp.interpolation = "LINEAR"


def _get_or_create_axis_empty(armature):
    """
    A static empty at 0,0,0 rotated +90° on X.
    Corrects SFM Y-up root transform into Blender Z-up without touching keyframes.
    The animated root empty is parented to this.
    """
    name  = f"{armature.name}_axis"
    empty = bpy.data.objects.get(name)
    if empty is None:
        empty = bpy.data.objects.new(name, None)
        empty.empty_display_type = "ARROWS"
        empty.empty_display_size = 15.0
        empty.rotation_mode      = "XYZ"
        empty.rotation_euler     = (pi / 2, 0.0, 0.0)   # +90 deg X
        empty.location           = (0.0, 0.0, 0.0)
        for col in armature.users_collection:
            col.objects.link(empty)
        print(f"[DMX_ANIM]  created axis empty '{name}'")
    return empty


def _get_or_create_root_empty(armature):
    """
    Animated empty that receives root transform keyframes.
    Parented to the axis empty so the +90 deg X correction is inherited.
    The armature is then parented to this empty.
    """
    axis_empty = _get_or_create_axis_empty(armature)

    name  = f"{armature.name}_root"
    empty = bpy.data.objects.get(name)
    if empty is None:
        empty = bpy.data.objects.new(name, None)
        empty.empty_display_type = "ARROWS"
        empty.empty_display_size = 10.0
        for col in armature.users_collection:
            col.objects.link(empty)
        print(f"[DMX_ANIM]  created root empty '{name}'")

    # Parent root → axis (static correction layer)
    if empty.parent != axis_empty:
        empty.parent                = axis_empty
        empty.matrix_parent_inverse = Matrix.Identity(4)
        print(f"[DMX_ANIM]  '{name}' parented to '{axis_empty.name}'")

    # Parent armature → root (animated layer)
    if armature.parent != empty:
        armature.parent                = empty
        armature.matrix_parent_inverse = Matrix.Identity(4)
        print(f"[DMX_ANIM]  '{armature.name}' parented to '{name}'")

    return empty


def _run_bst_import(dmx_path: Path, armature):
    """Run the SMD importer. Uses SST's bundled ht.import_smd operator."""
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    before = {a.name for a in bpy.data.actions}
    result = bpy.ops.ht.import_smd(filepath=str(dmx_path))

    if "FINISHED" not in result:
        raise RuntimeError(f"SMD importer returned {result}")

    new_names = {a.name for a in bpy.data.actions} - before
    if not new_names:
        raise RuntimeError("SMD importer finished but created no new action")

    stem   = dmx_path.stem.lower()
    scored = sorted(new_names, key=lambda n: stem in n.lower(), reverse=True)
    action = bpy.data.actions[scored[0]]

    anim_data = armature.animation_data or armature.animation_data_create()
    anim_data.action = action
    return action


def _patch_scale_and_root(dmx_path: Path, armature, action,
                          add_root_helpers: bool = True):
    """
    Second pass: add scale + root-transform keys that BST skips.

    SCALE
      toAttribute == "scale" carries a DmeFloatLog (uniform scalar).
      Applied identically to X, Y, Z scale axes.

    ROOT TRANSFORM
      Channels "unnamed_p" / "unnamed_o" → location / rotation_quaternion
      on a root Empty named {armature.name}_root. Armature is parented to it.

    FRAME OFFSET
      timeFrame["start"] is added to every raw time before frame conversion,
      matching BST's own behaviour (import_smd.py line 1685).

    AXIS CONVERSION  (SFM Y-up → Blender Z-up)
      position:    (x, y, z) → (x,  z, -y)
      orientation: mirrors BST's getUpAxisMat('Y').inverted() matrix chain
    """
    dm    = _get_datamodel()
    model = dm.load(str(dmx_path))

    anim_list = model.root.get("animationList")
    if not anim_list:
        return {"scale_bones": 0, "root_curves": 0, "root_action": None, "root_empty": None}
    anims = anim_list.get("animations")
    if not anims:
        return {"scale_bones": 0, "root_curves": 0, "root_action": None, "root_empty": None}

    animation  = anims[0]
    frame_rate = animation.get("frameRate", 30)
    channels   = animation.get("channels") or []

    time_frame = animation.get("timeFrame")
    start = float(time_frame.get("start", 0)) if time_frame is not None else 0.0

    def frame_for(t):
        return (float(t) + start) * frame_rate

    bone_lower  = {pb.name.lower(): pb for pb in armature.pose.bones}
    scale_bones = 0

    # Create axis + root empty hierarchy so the armature gets the +90 X
    # correction even if this DMX has no unnamed_p/unnamed_o channels (e.g.
    # models whose root motion lives on a bone instead of the game model).
    # When add_root_helpers is False (SMD-clean), skip it entirely: no empty,
    # no parenting, bone + scale channels only.
    if add_root_helpers:
        root_empty = _get_or_create_root_empty(armature)
    else:
        root_empty = None
        print("[DMX_ANIM]  add_root_helpers=False — skipping root empty "
              "(SMD-clean: bone channels only)")
    root_action = None
    root_bag    = None

    # Get the channelbag for the main armature action (for bone scale keys)
    action_bag = get_channelbag(action, armature)

    def _add_scale_keys(bag, path, group_name, frame, val):
        """Unpack Vector3 or uniform float → 3 scale keys."""
        try:
            sv = (float(val[0]), float(val[1]), float(val[2]))   # Vector3
        except TypeError:
            sv = (float(val), float(val), float(val))             # uniform float
        for i in range(3):
            _key(bag, path, i, group_name, frame, sv[i])

    for ch in channels:
        ch_name = ch.name or ""
        to_elem = ch.get("toElement")
        to_attr = ch.get("toAttribute", "") or ""

        try:
            log_elem = ch.get("log")
            if not log_elem:
                continue
            layers = log_elem.get("layers")
            if not layers:
                continue
            layer  = layers[0]
            times  = layer.get("times")
            values = layer.get("values")
            if not times or not values or len(times) != len(values):
                continue
        except Exception as e:
            print(f"[DMX_ANIM]  ch '{ch_name}' log read failed: {e}")
            continue

        # ── Bone scale ────────────────────────────────────────────────────────
        # Guard: rootTransform_scale belongs to the root empty, not a bone.
        if ch_name != "rootTransform_scale" and ((to_attr == "scale") or ch_name.endswith("_scale")):
            b_name = (to_elem.name if to_elem else None) or ch_name.removesuffix("_scale")
            bone   = bone_lower.get(b_name.lower()) if b_name else None
            if not bone:
                continue
            path = f'pose.bones["{bone.name}"].scale'
            for t, v in zip(times, values):
                _add_scale_keys(action_bag, path, bone.name, frame_for(t), v)
            scale_bones += 1
            continue

        # ── Root transform ─────────────────────────────────────────────────────
        if ch_name not in ("unnamed_p", "unnamed_o", "rootTransform_scale"):
            continue

        # SMD-clean: no root empty was created, so skip root motion entirely.
        if root_empty is None:
            continue

        if root_action is None:
            root_action, root_bag = make_action(f"{action.name}_root", root_empty)
            root_empty.rotation_mode = "QUATERNION"

        group = "root_transform"
        for t, v in zip(times, values):
            fr = frame_for(t)
            if ch_name == "unnamed_p":
                # SFM→Blender via axis_empty (+90° X): world = (lx, -lz, ly)
                # Key (v[1], v[2], v[0]) → world_x=v[1], world_y=-v[0], world_z=v[2]
                loc = Vector((float(v[1]), float(v[2]), float(v[0])))
                for i in range(3):
                    _key(root_bag, "location", i, group, fr, loc[i])
            elif ch_name == "unnamed_o":
                # Root quat needs conjugation + axis remap vs per-bone quats
                # (Evan Purr fix — world-space root vs BST bone-space pipeline)
                q_bst    = Quaternion((-float(v[3]), -float(v[1]), float(v[0]), -float(v[2])))
                axis_mat = Matrix.Rotation(-pi / 2, 4, 'X')
                q        = (axis_mat @ q_bst.to_matrix().to_4x4() @ axis_mat.inverted()).to_quaternion()
                for i in range(4):
                    _key(root_bag, "rotation_quaternion", i, group, fr, q[i])
            elif ch_name == "rootTransform_scale":
                _add_scale_keys(root_bag, "scale", group, fr, v)

    for fc in iter_fcurves(action, armature):
        fc.update()
    root_curves = 0
    if root_action:
        for fc in iter_fcurves(root_action, root_empty):
            fc.update()
        root_curves = count_fcurves(root_action, root_empty)

    return {
        "scale_bones": scale_bones,
        "root_curves": root_curves,
        "root_action": root_action,
        "root_empty":  root_empty,
    }


# ──────────────────────────────────────────────────────────────────────────────
#  PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def _apply_anim_scale(action, root_action, factor: float) -> int:
    """Multiply every location key (bones + root) by *factor*, handles too.
    Rotation and scale channels are left alone. Returns curves touched."""
    from . import anim_compat
    touched = 0
    for act in (action, root_action):
        if act is None:
            continue
        for fc in anim_compat.iter_fcurves(act):
            dp = fc.data_path
            if not (dp == "location" or dp.endswith(".location")):
                continue
            for kp in fc.keyframe_points:
                kp.co[1]           *= factor
                kp.handle_left[1]  *= factor
                kp.handle_right[1] *= factor
            fc.update()
            touched += 1
    return touched


def import_dmx_animation(dmx_path, armature, add_root_helpers: bool = True,
                         anim_scale: float = 1.0):
    """
    Import an SFM DMX animation onto *armature*.

    Parameters
    ──────────
    dmx_path         : str | Path          path to the .dmx file
    armature         : bpy.types.Object    must be type 'ARMATURE'
    add_root_helpers : bool
        True  — create the axis + root empty hierarchy (the +90° X correction
                and unnamed_p/unnamed_o root motion). Default; correct for
                normal SFM-to-Blender work.
        False — skip the root empty entirely and import bone (+ scale) channels
                only. Use for clean SMD export, where the extra root transform
                breaks the hierarchy Source expects.

    Returns
    ───────
    {
        "action"      : bpy.types.Action,
        "root_action" : bpy.types.Action | None,
        "root_empty"  : bpy.types.Object | None,
        "scale_bones" : int,
        "root_curves" : int,
    }

    Raises FileNotFoundError, TypeError, RuntimeError on hard failures.
    """
    dmx_path = Path(dmx_path)
    if not dmx_path.exists():
        raise FileNotFoundError(f"DMX file not found: {dmx_path}")
    if armature.type != "ARMATURE":
        raise TypeError(f"Expected ARMATURE, got '{armature.type}'")

    action = _run_bst_import(dmx_path, armature)
    print(f"[DMX_ANIM]  BST imported action '{action.name}'")

    try:
        patch = _patch_scale_and_root(dmx_path, armature, action,
                                      add_root_helpers=add_root_helpers)
    except Exception as exc:
        print(f"[DMX_ANIM]  patch WARNING: {exc}")
        patch = {"scale_bones": 0, "root_curves": 0, "root_action": None, "root_empty": None}

    scaled_curves = 0
    if anim_scale != 1.0:
        try:
            scaled_curves = _apply_anim_scale(action, patch["root_action"], anim_scale)
            print(f"[DMX_ANIM]  anim scale ×{anim_scale:g} on {scaled_curves} curve(s)")
        except Exception as exc:
            print(f"[DMX_ANIM]  anim scale WARNING: {exc}")

    print(f"[DMX_ANIM]  done — scale: {patch['scale_bones']} bone(s), "
          f"root: {patch['root_curves']} F-curve(s)"
          + ("" if add_root_helpers else "  (root helpers disabled — SMD-clean)"))

    return {
        "action":        action,
        "root_action":   patch["root_action"],
        "root_empty":    patch["root_empty"],
        "scale_bones":   patch["scale_bones"],
        "root_curves":   patch["root_curves"],
        "anim_scale":    anim_scale,
        "scaled_curves": scaled_curves,
    }


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_ImportDmxAnimation(Operator, ImportHelper):
    """Import SFM DMX animation — bones, scale, root transform"""
    bl_idname  = "ht.import_dmx_animation"
    bl_label   = "DMX Animation"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".dmx"
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})

    add_root_helpers: BoolProperty(
        name="Add Root Transform",
        description=(
            "Create the axis + root empty hierarchy and key the root "
            "game-model motion (unnamed_p/unnamed_o) onto it. KEEP ON for "
            "normal SFM-to-Blender work. Turn OFF for clean SMD export later — "
            "the extra root transform breaks the bone hierarchy Source expects, "
            "so disabling it imports bone channels only"
        ),
        default=True,
    )

    anim_scale: FloatProperty(
        name="Animation Scale",
        description=(
            "Multiply every location key (bone locations + root motion) by "
            "this factor after import. 1.0 imports the animation untouched. "
            "Use when the target model was resized: a model at 0.5x scale "
            "needs its animation at 0.5 too, or the rig walks in place while "
            "the root flies off. Rotations are never touched"
        ),
        default=1.0, min=0.001, soft_min=0.01, soft_max=100.0,
    )

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "add_root_helpers")
        if not self.add_root_helpers:
            box = col.box()
            box.label(text="SMD-clean: no root transform", icon="INFO")
            box.label(text="bone channels only")
        col.prop(self, "anim_scale")

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != "ARMATURE":
            self.report({"ERROR"}, "Select an armature first.")
            return {"CANCELLED"}

        try:
            result = import_dmx_animation(self.filepath, armature,
                                          add_root_helpers=self.add_root_helpers,
                                          anim_scale=self.anim_scale)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        action = result["action"]
        lines  = [
            f"File   : {Path(self.filepath).name}",
            f"Action : {action.name}",
            f"Frames : {action.frame_range[0]:.0f} – {action.frame_range[1]:.0f}",
        ]
        if result["scale_bones"]:
            lines.append(f"Scale  : {result['scale_bones']} bone(s)")
        if result.get("root_curves"):
            lines.append(f"Root   : {result['root_curves']} F-curve(s) on {armature.name}_root")
        elif not self.add_root_helpers:
            lines.append("Root   : skipped (SMD-clean — bone channels only)")

        def draw(self, context):
            for line in lines:
                self.layout.label(text=line)
        context.window_manager.popup_menu(draw, title="DMX Animation Imported", icon="CHECKMARK")
        self.report({"INFO"}, f"Imported '{action.name}'")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU ITEM  (called directly by MT_HT_import_submenu.draw in __init__.py)
# ──────────────────────────────────────────────────────────────────────────────

# Set by __init__.py during register() — direct reference to icon_id().
_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


def draw_menu_item(layout):
    """Draw this module's entry. Called from MT_HT_import_submenu.draw()."""
    layout.operator(
        HT_OT_ImportDmxAnimation.bl_idname,
        text="DMX Animation",
        **_icon_id("import_dmx_anim", "ACTION"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (HT_OT_ImportDmxAnimation,)


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


# Standalone launch (run as a script, not imported as a module)
if __name__ == "__main__":
    register()
    bpy.ops.ht.import_dmx_animation("INVOKE_DEFAULT")