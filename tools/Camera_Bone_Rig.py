# ═════════════════════════════════════════════════════════════════════════════
#  DEPENDENCIES
#    bpy, mathutils            armature, bone, re-parenting, verification
#    core/anim_compat.py       layered actions (5.x) and legacy ones alike
#  Called by session/Session_Orchestrator.py after the cameras are imported
#  and auto-split, and by the operator HT_OT_rig_cameras_on_bones.
#  Added in 1.16.0.
# ═════════════════════════════════════════════════════════════════════════════
"""
Camera_Bone_Rig - cameras ride a BONE, not an empty.

BEFORE                              AFTER
    <cam>_axis   empty, +90 X           <cam>_axis   empty, +90 X  (unchanged)
      <cam>_root empty, ANIMATED          <cam>_rig  ARMATURE, still
        <cam>    camera                     bone "camera"  ANIMATED
                                              <cam>  camera, BONE-parented

The same shape a character has: an axis empty carrying the Y-up -> Z-up turn,
an armature under it, the motion on a bone. So a camera is posed, keyed,
retimed and exported the way everything else in the scene is.

WHY THE NUMBERS DO NOT MOVE
---------------------------
The bone is built with an IDENTITY rest: head at the armature origin, tail
along +Y, roll 0. A pose bone with an identity rest takes location / rotation
/ scale in the armature's own space - exactly the space the root empty's
object channels were in, because the armature sits where the root empty sat
(same parent, same parent-inverse, identity local). So the curves move across
VERBATIM: `location[i]` becomes `pose.bones["camera"].location[i]`, every key,
every handle, every interpolation, untouched.

BONE PARENTING ATTACHES AT THE TAIL. A child parented to a bone sits at the
bone's tail, one bone-length along +Y. The camera's parent inverse is set to
the translation that cancels exactly that length - nothing else - so the
camera ends up where it was.

AND IT IS CHECKED, NOT ASSUMED: the camera's world matrix is sampled across
the take before and after, and a rig whose camera moved by more than
VERIFY_TOLERANCE is put back the way it was and reported.
"""

import bpy
from mathutils import Matrix, Vector

BONE_NAME = "camera"
BONE_LENGTH = 10.0           # Source units - display only, cancelled below
VERIFY_TOLERANCE = 1e-3
VERIFY_SAMPLES = 120
_CHANNELS = ("location", "rotation_quaternion", "rotation_euler", "scale")


def _is_empty(ob):
    return ob is not None and ob.type == 'EMPTY'


def camera_rig_parts(cam):
    """(axis_empty, root_empty) for a camera still on the empty rig, else None."""
    root = cam.parent
    if not _is_empty(root) or not _is_empty(root.parent):
        return None
    return root.parent, root


def _sample_frames(action, scene):
    lo, hi = scene.frame_start, scene.frame_end
    if action is not None:
        try:
            r = action.frame_range
            lo, hi = int(r[0]), int(r[1]) + 1
        except Exception:                                     # noqa: BLE001
            pass
    if hi <= lo:
        return [lo]
    step = max(1, (hi - lo) // VERIFY_SAMPLES)
    return list(range(lo, hi + 1, step))


def _world(cam, frames, scene):
    out = []
    for f in frames:
        scene.frame_set(f)
        out.append(cam.matrix_world.copy())
    return out


def _max_diff(a, b):
    return max(max(abs(x - y) for x, y in zip(ra, rb))
               for ma, mb in zip(a, b) for ra, rb in zip(ma, mb))


def _copy_curve(src, bag, data_path, index, group):
    from ..core import anim_compat
    dst = anim_compat.fc_find_or_new(bag, data_path, index, group)
    dst.keyframe_points.clear()
    dst.keyframe_points.add(len(src.keyframe_points))
    for k_dst, k_src in zip(dst.keyframe_points, src.keyframe_points):
        k_dst.co = k_src.co
        k_dst.interpolation = k_src.interpolation
        k_dst.handle_left_type = k_src.handle_left_type
        k_dst.handle_right_type = k_src.handle_right_type
        k_dst.handle_left = k_src.handle_left
        k_dst.handle_right = k_src.handle_right
        k_dst.easing = k_src.easing
    dst.extrapolation = src.extrapolation
    dst.update()
    return dst


def _make_armature(name, root, scene):
    data = bpy.data.armatures.new(name)
    data.display_type = 'STICK'
    arm = bpy.data.objects.new(name, data)
    for col in root.users_collection:
        col.objects.link(arm)
    arm.parent = root.parent
    arm.matrix_parent_inverse = root.matrix_parent_inverse.copy()
    arm.matrix_basis = Matrix.Identity(4)
    #  edit bones need edit mode - the one place this cannot be avoided
    vl = bpy.context.view_layer
    prev_active = vl.objects.active
    with bpy.context.temp_override(active_object=arm, object=arm,
                                   selected_objects=[arm]):
        vl.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        eb = data.edit_bones.new(BONE_NAME)
        eb.head = (0.0, 0.0, 0.0)
        eb.tail = (0.0, BONE_LENGTH, 0.0)
        eb.roll = 0.0
        bpy.ops.object.mode_set(mode='OBJECT')
    vl.objects.active = prev_active
    return arm


def rig_camera_on_bone(cam, scene=None):
    """Move one camera from the empty rig onto an armature bone.

    Returns a dict: status ("rigged" / "skipped" / "reverted" / "failed"),
    the armature, curves moved, and the measured drift."""
    from ..core import anim_compat
    scene = scene or bpy.context.scene
    parts = camera_rig_parts(cam)
    if parts is None:
        kind = cam.parent.type if cam.parent else "nothing"
        return {"status": "skipped", "camera": cam.name,
                "reason": f"parent is {kind}, not the axis/root empty rig"}
    axis, root = parts
    ad = root.animation_data
    action = ad.action if ad else None
    frames = _sample_frames(action, scene)
    keep_frame = scene.frame_current
    before = _world(cam, frames, scene)

    name = root.name[:-5] + "_rig" if root.name.endswith("_root") \
        else f"{cam.name}_rig"
    arm = _make_armature(name, root, scene)
    pb = arm.pose.bones[BONE_NAME]
    pb.rotation_mode = root.rotation_mode
    #  channels with no curve keep the root's static value
    pb.location = root.location
    pb.rotation_quaternion = root.rotation_quaternion
    pb.rotation_euler = root.rotation_euler
    pb.scale = root.scale

    moved = 0
    if action is not None:
        new_act, bag = anim_compat.make_action(f"{name}_action", arm)
        for fc in anim_compat.iter_fcurves(action, root):
            if fc.data_path not in _CHANNELS:
                continue
            _copy_curve(fc, bag, f'pose.bones["{BONE_NAME}"].{fc.data_path}',
                        fc.array_index, BONE_NAME)
            moved += 1

    #  The keys arrive verbatim, flips included: the shot split re-keys the
    #  per-shot rigs after the importer's own flip fix ran. Walk the
    #  hemisphere once more on the bone - negation is the same orientation,
    #  so it moves nothing and only stops the in-between going round the
    #  back (camera wood_planks4 turned 1183 degrees inside frame 368).
    if moved:
        try:
            from ..importers.Import_DMX_Animation import fix_action_quat_flips
            fl = fix_action_quat_flips(new_act, arm)["flipped_keys"]
            if fl:
                print(f"[CAM_RIG]  {cam.name}: {fl} quaternion key(s) negated")
        except Exception as exc:                              # noqa: BLE001
            print(f"[CAM_RIG]  {cam.name}: flip walk skipped ({exc})")

    for key in list(root.keys()):                 # ht_shot_bounds and friends
        try:
            arm[key] = root[key]
        except Exception:                                     # noqa: BLE001
            pass

    cam_basis = cam.matrix_basis.copy()
    cam.parent = arm
    cam.parent_type = 'BONE'
    cam.parent_bone = BONE_NAME
    cam.matrix_parent_inverse = Matrix.Translation(Vector((0.0, -BONE_LENGTH, 0.0)))
    cam.matrix_basis = cam_basis

    after = _world(cam, frames, scene)
    drift = _max_diff(before, after)
    if drift > VERIFY_TOLERANCE:
        #  put it back exactly as it was - a wrong rig is worse than none
        cam.parent = root
        cam.parent_type = 'OBJECT'
        cam.matrix_parent_inverse = Matrix.Identity(4)
        cam.matrix_basis = cam_basis
        if arm.animation_data and arm.animation_data.action:
            bpy.data.actions.remove(arm.animation_data.action)
        data = arm.data
        bpy.data.objects.remove(arm, do_unlink=True)
        bpy.data.armatures.remove(data)
        scene.frame_set(keep_frame)
        print(f"[CAM_RIG]  {cam.name}: REVERTED - the camera moved {drift:.5f} "
              f"after re-parenting (tolerance {VERIFY_TOLERANCE})")
        return {"status": "reverted", "camera": cam.name, "drift": drift}

    old_action = action
    bpy.data.objects.remove(root, do_unlink=True)
    if old_action is not None and old_action.users <= (1 if old_action.use_fake_user else 0):
        bpy.data.actions.remove(old_action)
    scene.frame_set(keep_frame)
    print(f"[CAM_RIG]  {cam.name}: on bone '{BONE_NAME}' of '{arm.name}' under "
          f"'{axis.name}' - {moved} curve(s) moved, drift {drift:.2e} over "
          f"{len(frames)} frame(s)")
    return {"status": "rigged", "camera": cam.name, "armature": arm,
            "curves": moved, "drift": drift, "frames": len(frames)}


def camera_owner(ob, data_path=""):
    """True when `ob` (and, for a bone, `data_path`) carries an IMPORTED
    camera's motion: the camera itself, the root empty of the empty rig, or
    the bone of the 1.16.0 rig that a camera is parented to. Imported = it
    carries the importer's stamps (ht_sfm_name / ht_source_file, which the
    rig copies from the root), so a character's empty that happens to hold a
    camera is never treated as one. Used by Euler_Output (a camera's Euler
    order, its held cut keys) and Delete Rotation Spins (one-frame camera
    flips). Added in 1.17.3."""
    if ob is None or not ("ht_sfm_name" in ob or "ht_source_file" in ob):
        return False
    if ob.type == 'CAMERA':
        return not data_path.startswith("pose.")
    if data_path.startswith('pose.bones["'):
        bone = data_path.split('"')[1]
        return any(c.type == 'CAMERA' and c.parent_type == 'BONE'
                   and c.parent_bone == bone for c in ob.children)
    return any(c.type == 'CAMERA' and c.parent_type == 'OBJECT'
               for c in ob.children)


def rig_all_cameras(cameras=None, scene=None):
    """Every camera still on the empty rig. Returns a list of result dicts."""
    scene = scene or bpy.context.scene
    cams = cameras if cameras is not None else \
        [ob for ob in scene.objects if ob.type == 'CAMERA']
    out = []
    for cam in cams:
        try:
            out.append(rig_camera_on_bone(cam, scene))
        except Exception as exc:                              # noqa: BLE001
            import traceback
            traceback.print_exc()
            out.append({"status": "failed", "camera": cam.name,
                        "reason": f"{type(exc).__name__}: {exc}"})
    return out


class HT_OT_rig_cameras_on_bones(bpy.types.Operator):
    """Put every camera on a bone: axis empty > armature > camera bone > camera.

The imported camera rig used to be axis empty > animated root empty > camera.
This builds an armature in the root empty's place, moves the root's keys onto
a bone called "camera" verbatim, parents the camera to that bone, and deletes
the root empty. The camera's position is sampled across the take before and
after; if it moved at all, that camera is put back and reported.

Selected cameras only when any are selected, otherwise every camera.

THIS FEATURE WAS ADDED IN VERSION 1.16.0 AND IS IN EXPERIMENTAL STAGE"""
    bl_idname = "ht.rig_cameras_on_bones"
    bl_label = "Rig Cameras on Bones"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sel = [o for o in context.selected_objects if o.type == 'CAMERA']
        res = rig_all_cameras(sel or None, context.scene)
        n = sum(1 for r in res if r["status"] == "rigged")
        bad = [r for r in res if r["status"] in ("reverted", "failed")]
        msg = f"{n} camera(s) rigged on bones"
        if bad:
            msg += f", {len(bad)} put back: " + ", ".join(r["camera"] for r in bad)
            self.report({"WARNING"}, msg)
        else:
            self.report({"INFO"}, msg)
        return {"FINISHED"}


def register():
    bpy.utils.register_class(HT_OT_rig_cameras_on_bones)


def unregister():
    bpy.utils.unregister_class(HT_OT_rig_cameras_on_bones)
