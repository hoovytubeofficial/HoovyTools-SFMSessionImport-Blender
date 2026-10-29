"""
Camera_Tools.py  -  part of HoovyTools        [roadmap #10, #11]
===============================================================

Camera work that stands on its own, with no Session Importer involved.

    PRE / POST HANDLES     extend a shot past its cut so a later edit
                           still has motion to move into
    SHOT INSPECTOR         what a split actually produced, per shot

WHY HANDLES                                              [roadmap #11]
======================================================================
A split camera stops dead at its cut. Move the edit point later - even by
two frames - and the camera has nothing to show: it holds on the last key
it owns. So every shot gets extra motion built BEFORE its first frame and
AFTER its last, extrapolated from the movement already happening at that
boundary.

    PRE-HANDLE    about 10-20 frames before the shot
    POST-HANDLE   about 10-20 frames after the shot

THE THREE CHANNELS DO NOT SHARE A METHOD
========================================
The report is explicit that location, rotation and focal length must be
tested separately, and it is right - they fail differently.

    LOCATION   linear velocity from the last real interval, held constant.
               A camera mid-move keeps moving. Position is unbounded, so
               nothing has to be clamped.

    ROTATION   the delta QUATERNION between the last two keys, applied
               again per step. Extrapolating x/y/z/w independently drifts
               off the unit sphere and the camera visibly skews; composing
               the same relative rotation keeps the turn rate honest and
               the quaternion normalised. Each new key is also sign-aligned
               to its predecessor, or the shortest-path interpolation
               flips and the camera spins the long way round.

    LENS       linear like location, but CLAMPED to a sane focal range.
               Focal length is physically bounded - extrapolating a fast
               zoom for 20 frames otherwise sails to a negative or absurd
               millimetre value, which Blender clamps silently and which
               reads as the zoom stopping dead anyway.

Handles are written as real keys with LINEAR interpolation into the shot
edge, so the join is continuous. The boundary key itself is never moved.
"""

import bpy
import math
from mathutils import Quaternion, Vector
from bpy.types import Operator
from bpy.props import IntProperty, BoolProperty, FloatProperty, EnumProperty

from ..core.anim_compat import iter_fcurves


# Focal length is bounded in a way position is not. Blender's own camera
# lens limit is 1 mm at the low end; leave headroom above it.
LENS_MIN_MM = 1.0
LENS_MAX_MM = 5000.0

HANDLE_MARK = "ht_handle"


# ─────────────────────────────────────────────────────────────────────────────
#  Curve helpers
# ─────────────────────────────────────────────────────────────────────────────

def _curves_by_path(action, owner):
    out = {}
    for fc in iter_fcurves(action, owner):
        out.setdefault(fc.data_path, {})[fc.array_index] = fc
    return out


def _sorted_keys(fc):
    return sorted(fc.keyframe_points, key=lambda k: k.co[0])


def _edge_pair(fc, at_start):
    """
    The two keys that define the motion at a boundary.

    At the start that is (second, first) so the delta points BACKWARDS in
    time; at the end it is (second-last, last) pointing forwards.
    """
    kps = _sorted_keys(fc)
    if len(kps) < 2:
        return None, None
    return (kps[1], kps[0]) if at_start else (kps[-2], kps[-1])


def edge_velocity(fc, at_start, samples=1):
    """
    Per-frame rate of change at a boundary.               [roadmap #18]

    samples == 1 reproduces the original behaviour: the slope of the single
    last key interval. That is what a camera was doing at the instant it was
    cut, and it is also maximally sensitive to noise - one jittery final key
    and the handle flies off at the wrong speed.

    samples > 1 fits a least-squares line through the last N keys and takes
    ITS slope. SFM exports are resampled per frame and often carry small
    jitter, so averaging over a handful of keys gives a far steadier answer
    while still following a genuine acceleration.

    Returns (edge_key, per_frame_slope) or (None, 0.0).
    """
    kps = _sorted_keys(fc)
    if len(kps) < 2:
        return None, 0.0
    edge = kps[0] if at_start else kps[-1]

    n = max(2, min(int(samples), len(kps)))
    window = kps[:n] if at_start else kps[-n:]

    if n == 2:
        a, b = window[0], window[1]
        span = b.co[0] - a.co[0]
        if abs(span) < 1e-9:
            return edge, 0.0
        return edge, (b.co[1] - a.co[1]) / span

    # Least squares over the window.
    xs = [k.co[0] for k in window]
    ys = [k.co[1] for k in window]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    if abs(den) < 1e-12:
        return edge, 0.0
    return edge, num / den


def ease_profile(i, count, mode):
    """
    How far along the extrapolated motion we are at step *i*.  [roadmap #18]

    CONSTANT  travel grows linearly - the camera keeps its speed forever.
              Correct for a handle you intend to cut into, wrong if you let
              it run: after 20 frames it has gone 20 frames' worth.

    EASE      travel follows a decelerating curve that comes to a full stop
              exactly at the end of the handle. Integral of a linear ramp
              from v to 0, normalised so the first step still matches the
              real velocity. Reads as the camera settling rather than
              flying away, which is usually what a handle wants.

    Returns a multiplier on (velocity * i), not on velocity, so both modes
    share one call site.
    """
    if mode == 'CONSTANT' or count <= 0:
        return float(i)
    t = i / float(count)
    # distance = v * count * (t - t^2/2) * 2 ... normalised so slope at t=0
    # is v and velocity reaches 0 at t=1.
    return count * (t - 0.5 * t * t)


def _write_key(fc, frame, value):
    kp = fc.keyframe_points.insert(float(frame), float(value),
                                   options={"FAST"})
    kp.interpolation = 'LINEAR'
    return kp


# ─────────────────────────────────────────────────────────────────────────────
#  Per-channel extrapolation
# ─────────────────────────────────────────────────────────────────────────────

def extend_linear(curves, at_start, frames, step=1.0, clamp=None,
                  mode='CONSTANT', samples=1):
    """
    Velocity extrapolation. Used for location and for lens.

    The velocity comes from edge_velocity() - one interval, or a
    least-squares fit over the last N keys - and ease_profile() decides
    whether it holds or decays. Returns the number of keys written.
    """
    written = 0
    count = int(frames / step)
    for fc in curves.values():
        edge, per_frame = edge_velocity(fc, at_start, samples)
        if edge is None or abs(per_frame) < 1e-12:
            continue
        if not at_start and edge.interpolation == 'CONSTANT':
            edge.interpolation = 'LINEAR'     # 1.17.3: a shot ending on a held cut key
        direction = -1.0 if at_start else 1.0
        for i in range(1, count + 1):
            travel = ease_profile(i, count, mode) * step
            frame = edge.co[0] + i * step * direction
            value = edge.co[1] + per_frame * travel * direction
            if clamp is not None:
                value = max(clamp[0], min(clamp[1], value))
            _write_key(fc, frame, value)
            written += 1
    return written


def extend_quaternion(curves, at_start, frames, step=1.0, mode='CONSTANT'):
    """
    Rotation, extrapolated as a repeated relative rotation.  [roadmap #11]

    q_delta = q_edge * q_inner^-1 is the turn that happened over the last
    real interval. Applying it again per step continues that turn at the
    same rate instead of letting four independent linear curves wander off
    the unit sphere.

    Every emitted key is sign-aligned against the previous one: a
    quaternion and its negation are the same orientation, but Blender
    interpolates the components, so an unaligned sign makes the camera
    take the long way round.
    """
    need = {i: curves.get(i) for i in range(4)}
    if any(need[i] is None for i in range(4)):
        return 0

    pairs = [_edge_pair(need[i], at_start) for i in range(4)]
    if any(p[0] is None for p in pairs):
        return 0

    inner = Quaternion([pairs[i][0].co[1] for i in range(4)])
    edge = Quaternion([pairs[i][1].co[1] for i in range(4)])
    span = pairs[0][1].co[0] - pairs[0][0].co[0]
    if abs(span) < 1e-9:
        return 0

    if inner.dot(edge) < 0.0:
        inner.negate()

    try:
        delta = edge @ inner.inverted()
    except (ValueError, ZeroDivisionError):
        return 0
    delta.normalize()

    # Scale the turn to exactly one step via AXIS-ANGLE, not slerp.
    #
    # slerp's factor is documented for 0..1 and raises outside it, and the
    # factor here is 1/span - keys land 0.9984 frames apart on a real SFM
    # export, which makes the factor 1.0016 and slerp refuse. Axis-angle
    # has no such range limit: the axis is the direction of the turn and
    # the angle is simply divided by how long the turn took, so the rate
    # is correct whether the source was keyed every frame, every third
    # frame, or at some drifting fraction in between.
    axis = delta.axis
    angle = delta.angle
    if angle > math.pi:                 # take the short way round
        angle -= 2.0 * math.pi
    per_step_angle = (angle / abs(span)) * step
    if at_start:
        per_step_angle = -per_step_angle
    if abs(per_step_angle) < 1e-12 or axis.length < 1e-9:
        return 0                        # a still camera stays still
    increment = Quaternion(axis, per_step_angle)

    direction = -1.0 if at_start else 1.0
    edge_frame = pairs[0][1].co[0]
    if not at_start:
        for p in pairs:                       # 1.17.3: a shot ending on a held cut key
            if p[1].interpolation == 'CONSTANT':
                p[1].interpolation = 'LINEAR'

    # In EASE mode the turn decays to a stop over the handle, exactly like
    # the linear channels - so a pan settles instead of spinning on. The
    # per-step angle is rebuilt from the travel delta rather than composed
    # blindly, or the two channels would drift apart.
    count = int(frames / step)
    written = 0
    previous = edge.copy()
    prev_travel = 0.0
    current = edge.copy()
    for i in range(1, count + 1):
        travel = ease_profile(i, count, mode) * step
        delta_angle = (travel - prev_travel) * (per_step_angle / step)
        prev_travel = travel
        current = (Quaternion(axis, delta_angle) @ current).normalized()
        if current.dot(previous) < 0.0:
            current.negate()
        frame = edge_frame + i * step * direction
        for c in range(4):
            _write_key(need[c], frame, current[c])
            written += 1
        previous = current.copy()
    return written


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────

def add_handles(obj, pre=12, post=12, do_location=True, do_rotation=True,
                do_lens=True, mode='CONSTANT', samples=1):
    """
    Give one camera hierarchy pre and post handles.

    *obj* may be the camera or its root empty - both are walked, since the
    transform lives on the root and the lens on the camera data.

    Returns a per-channel count of the keys written.
    """
    out = {"location": 0, "rotation": 0, "lens": 0, "objects": []}

    targets = []
    seen = set()
    for candidate in (obj, obj.parent if obj else None,
                      *(obj.children if obj else ())):
        if candidate is not None and candidate.name not in seen:
            seen.add(candidate.name)
            targets.append(candidate)

    for target in targets:
        ad = target.animation_data
        if ad and ad.action:
            by_path = _curves_by_path(ad.action, target)
            touched = False
            if do_location and "location" in by_path:
                for at_start, n in ((True, pre), (False, post)):
                    if n > 0:
                        out["location"] += extend_linear(
                            by_path["location"], at_start, n,
                            mode=mode, samples=samples)
                        touched = True
            if do_rotation and "rotation_quaternion" in by_path:
                for at_start, n in ((True, pre), (False, post)):
                    if n > 0:
                        out["rotation"] += extend_quaternion(
                            by_path["rotation_quaternion"], at_start, n,
                            mode=mode)
                        touched = True
            if touched:
                for fc in iter_fcurves(ad.action, target):
                    fc.update()
                out["objects"].append(target.name)

        if do_lens and target.type == 'CAMERA' and target.data:
            cad = target.data.animation_data
            if cad and cad.action:
                by_path = _curves_by_path(cad.action, target.data)
                for path in ("lens", "sensor_width"):
                    if path not in by_path:
                        continue
                    clamp = (LENS_MIN_MM, LENS_MAX_MM) if path == "lens" else None
                    for at_start, n in ((True, pre), (False, post)):
                        if n > 0:
                            out["lens"] += extend_linear(
                                by_path[path], at_start, n, clamp=clamp,
                                mode=mode, samples=samples)
                    for fc in iter_fcurves(cad.action, target.data):
                        fc.update()

    return out


def shot_report(obj):
    """Frame span of every animated curve on a camera hierarchy."""
    rows = []
    targets = [obj]
    if obj.parent:
        targets.append(obj.parent)
    targets.extend(obj.children)
    for target in targets:
        pairs = [(target, target.animation_data)]
        if target.type == 'CAMERA' and target.data:
            pairs.append((target.data, target.data.animation_data))
        for owner, ad in pairs:
            if ad is None or ad.action is None:
                continue
            for fc in iter_fcurves(ad.action, owner):
                kps = _sorted_keys(fc)
                if not kps:
                    continue
                rows.append((target.name, fc.data_path, fc.array_index,
                             kps[0].co[0], kps[-1].co[0], len(kps)))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
#  Operators
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_camera_handles(Operator):
    """Extend a split camera past its cut so a later edit still has motion

Each selected shot gets extra keys before its first frame and after its
last, extrapolated from the movement already happening at that boundary.
Move the edit point afterwards and the camera keeps going instead of
freezing on the key it stopped at.

Location extrapolates at constant velocity. Rotation repeats the turn that
was in progress, as a quaternion, so it neither skews nor spins the long
way. Focal length extrapolates linearly but stays inside a real lens range.

Run it on the cameras in ___HoovyTools Cameras___ after Split Camera Cuts"""
    bl_idname = "ht.camera_handles"
    bl_label = "Add Camera Pre/Post Handles"
    #  NO "REGISTER" - see the note in Report_UI/the constitution.
    #  REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    #  touching any field in it RE-RUNS this operator. Re-running an
    #  import re-reads the DMX and rebuilds every f-curve; nudging Scale
    #  there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    #  with the value you wanted is the safe way to change your mind.
    bl_options = {"UNDO"}

    pre_frames: IntProperty(  # type: ignore
        name="Pre-Handle",
        description="Frames of extrapolated motion BEFORE the shot starts",
        default=12, min=0, max=240,
    )
    post_frames: IntProperty(  # type: ignore
        name="Post-Handle",
        description="Frames of extrapolated motion AFTER the shot ends",
        default=12, min=0, max=240,
    )
    do_location: BoolProperty(  # type: ignore
        name="Location",
        description="Extend position at the velocity it had at the boundary",
        default=True,
    )
    do_rotation: BoolProperty(  # type: ignore
        name="Rotation",
        description=("Extend rotation by repeating the turn in progress. "
                     "Quaternion-composed, so the camera does not skew or "
                     "take the long way round"),
        default=True,
    )
    do_lens: BoolProperty(  # type: ignore
        name="Focal Length",
        description=("Extend the lens animation, clamped to a real focal "
                     "range. A fast zoom extrapolated raw would run past "
                     "zero millimetres"),
        default=True,
    )
    mode: EnumProperty(  # type: ignore
        name="Falloff",
        description="How the extrapolated motion behaves over the handle",
        items=[
            ('CONSTANT', "Constant",
             "Keep the speed the camera had at the cut, for the whole "
             "handle. Right when you intend to cut into the handle - the "
             "motion matches the take exactly wherever you land"),
            ('EASE', "Ease Out",
             "Decelerate to a full stop by the end of the handle. The "
             "first frame still matches the real speed, so the join is "
             "seamless, but the camera settles instead of flying away. "
             "Usually the nicer default for a long handle"),
        ],
        default='CONSTANT',
    )
    samples: IntProperty(  # type: ignore
        name="Velocity Samples",
        description=(
            "How many keys at the boundary the speed is measured over. "
            "1 uses the single last interval - exactly what the camera was "
            "doing, and maximally sensitive to a jittery final key. Higher "
            "values fit a line through the last N keys, which is much "
            "steadier on per-frame resampled SFM exports"),
        default=1, min=1, max=32,
    )

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def draw(self, context):
        col = self.layout.column()
        row = col.row(align=True)
        row.prop(self, "pre_frames")
        row.prop(self, "post_frames")
        col.separator()
        col.prop(self, "mode")
        col.prop(self, "samples")
        col.separator()
        col.label(text="Channels - each extrapolates differently:")
        col.prop(self, "do_location")
        col.prop(self, "do_rotation")
        col.prop(self, "do_lens")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        roots, seen = [], set()
        for obj in context.selected_objects:
            key = (obj.parent or obj).name
            if key in seen:
                continue
            seen.add(key)
            roots.append(obj)

        total = {"location": 0, "rotation": 0, "lens": 0}
        names = []
        for obj in roots:
            try:
                r = add_handles(obj, pre=self.pre_frames, post=self.post_frames,
                                do_location=self.do_location,
                                do_rotation=self.do_rotation,
                                do_lens=self.do_lens,
                                mode=self.mode, samples=self.samples)
            except Exception as exc:
                self.report({"ERROR"}, f"{obj.name}: {exc}")
                return {"CANCELLED"}
            for k in total:
                total[k] += r[k]
            names.extend(r["objects"])

        lines = [
            f"Cameras : {len(roots)}",
            f"Pre/Post: {self.pre_frames} / {self.post_frames} frames",
            f"Falloff : {self.mode.title()}  (velocity over "
            f"{self.samples} key interval(s))",
            f"Location: {total['location']} key(s)",
            f"Rotation: {total['rotation']} key(s)",
            f"Lens    : {total['lens']} key(s)",
        ]
        for line in lines:
            print(f"[CAM_HANDLES]  {line}")

        if not any(total.values()):
            self.report({"WARNING"},
                        "Nothing extended - the selection has no animated "
                        "camera curves with at least two keys")
            return {"CANCELLED"}

        from ..core import Report_UI
        Report_UI.report(context, "camera_tools", "Camera Handles", lines,
                         level='INFO', icon='IPO_BEZIER', operator=self,
                         prefix="CAM_HANDLES",
                         summary=f"Camera Handles - extended {len(roots)} "
                                 f"camera(s), {sum(total.values())} key(s)")
        return {"FINISHED"}


class HT_OT_camera_shot_report(Operator):
    """Print the frame span of every animated curve on the selected cameras

The quickest way to see whether a split left a shot ragged: a curve that
starts late or ends early is the boundary frame where the camera has
nothing to evaluate, and it shows up as a jump on playback.

Reports each curve's first and last key, so a location curve ending three
frames before the rotation curve is visible at a glance rather than as a
mystery hitch.

Select the camera roots first. Read-only - it changes nothing"""
    bl_idname = "ht.camera_shot_report"
    bl_label = "Camera Shot Report"

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def execute(self, context):
        rows = []
        for obj in context.selected_objects:
            rows.extend(shot_report(obj))
        if not rows:
            self.report({"WARNING"}, "No animated curves in the selection")
            return {"CANCELLED"}

        print("\n[CAM_SHOT]  object / path[idx] : first .. last (keys)")
        spans = {}
        for name, path, idx, first, last, n in rows:
            print(f"[CAM_SHOT]  {name} / {path}[{idx}] : "
                  f"{first:.3f} .. {last:.3f}  ({n} keys)")
            spans.setdefault(name, []).append((first, last))

        ragged = []
        for name, pairs in spans.items():
            firsts = {round(f, 3) for f, _ in pairs}
            lasts = {round(l, 3) for _, l in pairs}
            if len(firsts) > 1 or len(lasts) > 1:
                ragged.append(name)
                print(f"[CAM_SHOT]  RAGGED {name}: starts {sorted(firsts)} "
                      f"ends {sorted(lasts)}")

        if ragged:
            self.report({"WARNING"},
                        f"{len(ragged)} camera(s) have curves that do not "
                        f"share a span - see console")
        else:
            self.report({"INFO"},
                        f"{len(rows)} curve(s), all spans aligned")
        return {"FINISHED"}


_CLASSES = (
    HT_OT_camera_handles,
    HT_OT_camera_shot_report,
)


def register(icon_id_fn=None):
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
