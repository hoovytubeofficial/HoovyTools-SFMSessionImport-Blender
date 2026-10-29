# ═════════════════════════════════════════════════════════════════════════════
# DEPENDENCIES
# bpy, mathutils                 the conversion
# core/anim_compat.py            layered (5.x) and legacy actions alike
# importers/Import_DMX_Animation fix_action_quat_flips - run first
# Called by session/Session_Orchestrator.py as the one-click's last step,
# and by the operator HT_OT_rotations_to_euler. Added in 1.16.0.
# ═════════════════════════════════════════════════════════════════════════════
"""
Euler_Output - the import ENDS on Euler rotations.

Everything here imports as QUATERNIONS on purpose - the sign fix, the stepped
resample and the camera re-rig all reason about quaternions, and they are the
right shape for that. This runs LAST and turns every animated rotation into
rotation_euler curves, so Blender's own Discontinuity (Euler) Filter, the
graph editor and hand-keying all work the way he expects.

1.17.3, FOR CAMERAS:
  - a key the importer HELD (CONSTANT - the frame before a hard cut) stays a
    step: the Euler key is CONSTANT too, and no frames are added after it
    (there is no path through a cut to sample). Before, every Euler key came
    out LINEAR and each cut became a one-frame whip of the whole turn.
  - a camera keeps XYZ unless it comes within camera_resample.GIMBAL_GUARD_DEG
    of XYZ's lock (a 90 degree Dutch roll); then the order with the most room.
    Measured on 33 real SFM cameras: none came near it.

A SIGN FLIP CANNOT SURVIVE THIS. q and -q convert to the same angles, so the
keys come out right whatever sign the quaternion keys had; step 1 only
protects the frames step 2 adds in between.
"""

import math

import bpy
from mathutils import Quaternion

ORDER = 'XYZ'
DENSIFY_DEG = 1.0
_QP = "rotation_quaternion"


def _groups(action, owner):
    from ..core import anim_compat
    out = {}
    for fc in anim_compat.iter_fcurves(action, owner):
        if fc.data_path.endswith(_QP) and 0 <= fc.array_index <= 3:
            out.setdefault(fc.data_path, [None] * 4)[fc.array_index] = fc
    return {k: v for k, v in out.items() if all(v)}


def _q_at(fcs, f):
    q = Quaternion([fc.evaluate(f) for fc in fcs])
    if q.magnitude < 1e-9:
        return None
    q.normalize()
    return q


def _held(fcs):
    """Frames whose key is CONSTANT in any of the four curves (1.17.3: the
    importer holds the frame before a hard cut)."""
    return {round(kp.co[0], 4) for fc in fcs for kp in fc.keyframe_points
            if kp.interpolation == 'CONSTANT'}


def _frames(fcs, held=()):
    times = sorted({kp.co[0] for fc in fcs for kp in fc.keyframe_points})
    out = []
    for i, t in enumerate(times):
        out.append(t)
        if i + 1 == len(times):
            break
        t2 = times[i + 1]
        if t2 - t <= 1.0 + 1e-6 or round(t, 4) in held:
            continue
        qa, qb = _q_at(fcs, t), _q_at(fcs, t2)
        if qa is None or qb is None:
            continue
        if math.degrees(qa.rotation_difference(qb).angle) <= DENSIFY_DEG:
            continue
        f = math.floor(t) + 1.0
        while f < t2 - 1e-6:
            out.append(f)
            f += 1.0
    return out


def _owner_of(ob, path):
    """The pose bone for a bone path, the object for an object path."""
    if path.startswith('pose.bones["'):
        name = path.split('"')[1]
        return ob.pose.bones.get(name) if ob.pose else None
    return ob


def convert_object(ob, order=ORDER):
    """Every animated quaternion rotation on *ob* -> Euler. Returns a count."""
    from ..core import anim_compat
    ad = ob.animation_data
    if ad is None or ad.action is None:
        return 0
    action = ad.action
    groups = _groups(action, ob)
    if not groups:
        return 0
    try:
        from ..importers.Import_DMX_Animation import fix_action_quat_flips
        fix_action_quat_flips(action, ob)
    except Exception as exc:                                  # noqa: BLE001
        print(f"[EULER]  {ob.name}: hemisphere walk skipped ({exc})")
    bag = anim_compat.get_channelbag(action, ob)
    if bag is None:
        return 0
    done = 0
    for path, fcs in groups.items():
        owner = _owner_of(ob, path)
        if owner is None:
            continue
        held = _held(fcs)
        frames = _frames(fcs, held)
        if not frames:
            continue
        use = order
        try:
            from .Camera_Bone_Rig import camera_owner
            if camera_owner(ob, path):
                from ..core import camera_resample
                qs = [q for q in (_q_at(fcs, f) for f in frames) if q is not None]
                use, margins = camera_resample.best_euler_order(qs, prefer=order)
                if use != order:
                    print(f"[EULER]  {ob.name}: {order} comes within "
                          f"{margins[order]:.1f} deg of its gimbal lock - "
                          f"{use} instead ({margins[use]:.1f} deg of room)")
        except Exception as exc:                              # noqa: BLE001
            print(f"[EULER]  {ob.name}: camera order check skipped ({exc})")
            use = order
        values = []
        prev = None
        for f in frames:
            q = _q_at(fcs, f)
            if q is None:
                q = Quaternion() if prev is None else prev.to_quaternion()
            e = q.to_euler(use, prev) if prev is not None else q.to_euler(use)
            values.append((f, (e.x, e.y, e.z)))
            prev = e
        group = fcs[0].group.name if fcs[0].group else None
        base = path[:-len(_QP)]
        for c in range(3):
            fc = anim_compat.fc_find_or_new(bag, base + "rotation_euler", c, group)
            fc.keyframe_points.clear()
            fc.keyframe_points.add(len(values))
            for kp, (f, v) in zip(fc.keyframe_points, values):
                kp.co = (f, v[c])
                kp.interpolation = 'CONSTANT' if round(f, 4) in held else 'LINEAR'
                kp.handle_left = (f - 0.333, v[c])
                kp.handle_right = (f + 0.333, v[c])
            fc.update()
        for fc in fcs:
            try:
                bag.fcurves.remove(fc)
            except Exception:                                 # noqa: BLE001
                try:
                    action.fcurves.remove(fc)
                except Exception:                             # noqa: BLE001
                    pass
        owner.rotation_mode = use
        done += 1
    return done


def convert_scene(objects=None, order=ORDER):
    """Every animated object (default: the whole scene). Returns a dict."""
    objs = objects if objects is not None else list(bpy.context.scene.objects)
    out = {"rotations": 0, "objects": 0}
    for ob in objs:
        try:
            n = convert_object(ob, order)
        except Exception as exc:                              # noqa: BLE001
            import traceback
            traceback.print_exc()
            print(f"[EULER]  {ob.name}: FAILED ({type(exc).__name__}: {exc})")
            continue
        if n:
            out["rotations"] += n
            out["objects"] += 1
    print(f"[EULER]  {out['rotations']} rotation(s) on {out['objects']} "
          f"object(s) now rotation_euler ({order})")
    return out


class HT_OT_rotations_to_euler(bpy.types.Operator):
    """Turn every animated quaternion rotation into Euler (XYZ) curves.

The import works in quaternions; this converts the result so Blender's
Discontinuity (Euler) Filter and the graph editor behave as expected. Each
rotation is walked for sign flips, then keyed in Euler at every existing key
- plus every whole frame of a long gap where it actually turns - using the
previous key's angles as the reference, so there are no 360-degree wraps.

Selected objects only when any are selected, otherwise the whole scene.

THIS FEATURE WAS ADDED IN VERSION 1.16.0 AND IS IN EXPERIMENTAL STAGE"""
    bl_idname = "ht.rotations_to_euler"
    bl_label = "Rotations to Euler"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sel = list(context.selected_objects)
        r = convert_scene(sel or None)
        self.report({"INFO"}, f"{r['rotations']} rotation(s) on "
                              f"{r['objects']} object(s) converted to Euler")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(HT_OT_rotations_to_euler)


def unregister():
    bpy.utils.unregister_class(HT_OT_rotations_to_euler)
