"""
Import_DMX_Camera.py  —  part of HoovyTools
============================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ DMX Camera

Imports an SFM DMX camera animation into Blender, mirroring the axis-correction
hierarchy used by Import_DMX_Animation for armatures:

    {cam}_axis   — static Empty, +90° X  (SFM Y-up → Blender Z-up correction)
        └─ {cam}_root — animated Empty   (receives position + rotation keyframes)
               └─ camera object          (receives FOV / lens keyframes only)

This keeps the camera in the same coordinate space as armatures imported by
Import_DMX_Animation, so they stay in sync with no manual correction needed.

PUBLIC API
──────────
    from . import Import_DMX_Camera

    result = Import_DMX_Camera.import_dmx_camera(
        dmx_path = Path("shot1_camera.dmx"),
    )
    # returns:
    # {
    #   "camera_obj"  : bpy.types.Object,        # the camera object
    #   "root_empty"  : bpy.types.Object,         # animated root empty
    #   "axis_empty"  : bpy.types.Object,         # static axis empty
    #   "root_action" : bpy.types.Action,         # position + rotation action
    #   "cam_action"  : bpy.types.Action | None,  # lens/FOV action (if keyed)
    # }
"""

bl_info = {
    "name":        "HoovyTools: Import DMX Camera",
    "description": "Import SFM DMX camera animation with axis correction",
    "author":      "HoovyTools",
    "version":     (1, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > DMX Camera",
    "category":    "Import-Export",
}

import bpy
import math
from math import pi
from pathlib import Path
from mathutils import Matrix, Quaternion, Vector, Euler
from bpy.types import Operator
from bpy.props import StringProperty, FloatProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper
from .anim_compat import make_action, iter_fcurves, count_fcurves, fc_find_or_new


# ──────────────────────────────────────────────────────────────────────────────
#  MODULE CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

# SFM imports come in ~10mm too zoomed; subtract a flat offset from the lens.
LENS_OFFSET_MM = 10.0

# Camera near/far clip presets, chosen per import scale (hand-tuned, not a single
# formula). Each entry: scale -> (clip_start_m, clip_end_m). For other scales the
# nearest preset by scale is used.
CLIP_PRESETS = {
    1.0:     (1.0,   150000.0),
    0.01905: (0.01,  1000.0),
}


def _clip_range_for_scale(scale: float):
    """Pick the (clip_start, clip_end) preset whose scale is nearest to *scale*."""
    nearest = min(CLIP_PRESETS, key=lambda s: abs(s - scale))
    return CLIP_PRESETS[nearest]

# Single-camera imports go in the blue collection; intelligent-split imports go
# in the purple plural collection.
COLLECTION_SINGLE = "___HoovyTools Camera___"     # blue
COLOR_SINGLE      = "COLOR_05"   # blue



# ──────────────────────────────────────────────────────────────────────────────
#  DATAMODEL LOADER
# ──────────────────────────────────────────────────────────────────────────────

def _get_datamodel():
    """Return the datamodel module via SST's bundled copy."""
    from .SST import get_datamodel
    return get_datamodel()


# ──────────────────────────────────────────────────────────────────────────────
#  KEYFRAME HELPERS  (same as Import_DMX_Animation)
# ──────────────────────────────────────────────────────────────────────────────

def _fc(bag, data_path, index, group):
    return fc_find_or_new(bag, data_path, index=index, group_name=group)


def _key(bag, data_path, index, group, frame, value, interp="LINEAR"):
    kp = _fc(bag, data_path, index, group).keyframe_points.insert(
        float(frame), float(value), options={"FAST"}
    )
    kp.interpolation = interp


# ──────────────────────────────────────────────────────────────────────────────
#  HIERARCHY BUILDERS
# ──────────────────────────────────────────────────────────────────────────────

def _get_or_create_axis_empty(cam_name: str, collection) -> bpy.types.Object:
    """
    Static empty at 0,0,0 rotated +90° on X.
    Corrects SFM Y-up root transform into Blender Z-up without touching keyframes.
    The animated root empty is parented to this.
    Mirrors Import_DMX_Animation._get_or_create_axis_empty().
    """
    name  = f"{cam_name}_axis"
    empty = bpy.data.objects.get(name)
    if empty is None:
        empty = bpy.data.objects.new(name, None)
        empty.empty_display_type = "ARROWS"
        empty.empty_display_size = 15.0
        empty.rotation_mode      = "XYZ"
        empty.rotation_euler     = (0.0, 0.0, 0.0)
        empty.location           = (0.0, 0.0, 0.0)
        collection.objects.link(empty)
        print(f"[DMX_CAM]  created axis empty '{name}'")
    return empty


def _get_or_create_root_empty(cam_name: str, axis_empty, collection) -> bpy.types.Object:
    """
    Animated empty that receives position + rotation keyframes.
    Parented to the axis empty so the +90° X correction is inherited.
    Camera is then parented to this empty.
    Mirrors Import_DMX_Animation._get_or_create_root_empty().
    """
    name  = f"{cam_name}_root"
    empty = bpy.data.objects.get(name)
    if empty is None:
        empty = bpy.data.objects.new(name, None)
        empty.empty_display_type = "ARROWS"
        empty.empty_display_size = 10.0
        collection.objects.link(empty)
        print(f"[DMX_CAM]  created root empty '{name}'")

    if empty.parent != axis_empty:
        empty.parent                = axis_empty
        empty.matrix_parent_inverse = Matrix.Identity(4)
        print(f"[DMX_CAM]  '{name}' parented to '{axis_empty.name}'")

    return empty


def _get_or_create_camera(cam_name: str, root_empty, collection,
                          local_align=None) -> bpy.types.Object:
    """
    Create (or reuse) the camera object and parent it to the root empty.
    The camera sits at the origin of the root empty — all motion comes
    from the parent hierarchy, not from the camera object itself.

    local_align : Quaternion | None
        Static local rotation for the camera. In the smooth path the
        camera-forward alignment is baked into each keyframe via quat.rotate(),
        so this is None (identity). In the raw/stepped path the keyframes are
        written verbatim, so the constant alignment is applied HERE instead, as
        the camera's local rotation — a single static value that post-multiplies
        the root's stepped quaternion (reproducing the per-key rotate) WITHOUT
        touching the stepped keyframes.
    """
    obj = bpy.data.objects.get(cam_name)
    if obj is None:
        cam_data = bpy.data.cameras.new(name=cam_name)
        obj      = bpy.data.objects.new(cam_name, cam_data)
        collection.objects.link(obj)
        print(f"[DMX_CAM]  created camera '{cam_name}'")
    else:
        print(f"[DMX_CAM]  reusing camera '{cam_name}'")

    obj.rotation_mode = "QUATERNION"

    if obj.parent != root_empty:
        obj.parent                = root_empty
        obj.matrix_parent_inverse = Matrix.Identity(4)
        # Reset local transform — all motion lives on the root empty
        obj.location           = (0.0, 0.0, 0.0)
        if local_align is not None:
            obj.rotation_quaternion = local_align
        else:
            obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        print(f"[DMX_CAM]  '{cam_name}' parented to '{root_empty.name}'")

    return obj


# ──────────────────────────────────────────────────────────────────────────────
#  FOV → LENS CONVERSION  (same formula as camera_loader.py)
# ──────────────────────────────────────────────────────────────────────────────

def _fov_to_lens(fov_degrees: float, sensor_width: float = 36.0) -> float:
    """Convert SFM horizontal FOV (degrees) to Blender lens (mm)."""
    return 0.5 * sensor_width / math.tan(math.radians(fov_degrees) / 2)


# Aperture mapping (SFM aperture -> Blender DOF f-stop), exponential fit.
#   f = 2.8 * exp(-k * aperture),  k chosen so SFM 10 -> f/0.075.
#   Exact at SFM 0 (f/2.8) and SFM 10 (f/0.075); diverges past ~20.
_APERTURE_F0 = 2.8
_APERTURE_K  = -math.log(0.075 / 2.8) / 10.0   # ~0.36199

def _aperture_to_fstop(aperture: float) -> float:
    """Convert SFM camera aperture to Blender DOF f-stop (exponential fit)."""
    f = _APERTURE_F0 * math.exp(-_APERTURE_K * float(aperture))
    # Blender requires f-stop > 0; clamp to a tiny positive floor.
    return max(f, 1e-4)


def _focal_distance(value: float, scale: float = 1.0) -> float:
    """SFM focal distance -> Blender focus distance. 1:1 (times import scale)."""
    return float(value) * scale


# ──────────────────────────────────────────────────────────────────────────────
#  QUATERNION FLIP FIX
# ──────────────────────────────────────────────────────────────────────────────

def _fix_quaternion_flips(action, owner) -> int:
    """
    Walk rotation_quaternion F-curves and negate keyframes where
    dot(q_prev, q_curr) < 0, forcing shortest-path interpolation.
    Kills 180° spin artifacts carried over from SFM exports.

    Returns the number of flipped keyframes.
    """
    fcs = [None] * 4
    for fc in iter_fcurves(action, owner):
        if fc.data_path == "rotation_quaternion" and 0 <= fc.array_index <= 3:
            fcs[fc.array_index] = fc
    if not all(fcs):
        return 0

    n = len(fcs[0].keyframe_points)
    for fc in fcs[1:]:
        if len(fc.keyframe_points) != n:
            print("[DMX_CAM]  WARNING: mismatched quat keyframe counts, skipping flip fix")
            return 0
    if n < 2:
        return 0

    flipped = 0
    prev = [fcs[c].keyframe_points[0].co[1] for c in range(4)]

    for i in range(1, n):
        curr = [fcs[c].keyframe_points[i].co[1] for c in range(4)]
        dot  = sum(a * b for a, b in zip(prev, curr))

        if dot < 0.0:
            for c in range(4):
                kp = fcs[c].keyframe_points[i]
                kp.co[1]           = -curr[c]
                kp.handle_left[1]  = -kp.handle_left[1]
                kp.handle_right[1] = -kp.handle_right[1]
            curr = [-v for v in curr]
            flipped += 1

        prev = curr

    if flipped:
        print(f"[DMX_CAM]  quaternion flip fix: {flipped}/{n} keyframes corrected")
    return flipped


# ──────────────────────────────────────────────────────────────────────────────
#  CORE IMPORT
# ──────────────────────────────────────────────────────────────────────────────

def _get_or_create_collection(name: str, color_tag: str) -> bpy.types.Collection:
    """Return (creating if needed) a scene-level collection with the given color."""
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
        print(f"[DMX_CAM]  created collection '{name}'")
    col.color_tag = color_tag
    return col


def import_dmx_camera(dmx_path, scale: float = 1.0, fix_quat_flips: bool = True,
                      collection=None) -> dict:
    """
    Import an SFM DMX camera animation.

    Parameters
    ──────────
    dmx_path        : str | Path   path to the camera .dmx file
    scale           : float        world scale multiplier (default 1.0, set to
                                   match your session import scale if needed)
    fix_quat_flips  : bool         negate quaternion keyframes where dot < 0
                                   to prevent 180° spin artifacts (default True)
    collection      : bpy.types.Collection | None
                                   target collection for the camera hierarchy.
                                   Defaults to the blue single-camera collection.

    Returns
    ───────
    {
        "camera_obj"  : bpy.types.Object,
        "root_empty"  : bpy.types.Object,
        "axis_empty"  : bpy.types.Object,
        "root_action" : bpy.types.Action,
        "cam_action"  : bpy.types.Action | None,
    }

    Raises FileNotFoundError, RuntimeError on hard failures.
    """
    dmx_path = Path(dmx_path)
    if not dmx_path.exists():
        raise FileNotFoundError(f"DMX file not found: {dmx_path}")

    dm    = _get_datamodel()
    model = dm.load(str(dmx_path))
    scene = model.root

    # ── Read static camera info ───────────────────────────────────────────────
    camera_info = scene.get("camera")
    if camera_info is None:
        raise RuntimeError("No 'camera' element found in DMX root")

    # Always use the filename stem as the unique identifier — SFM often gives
    # every camera the same internal name (e.g. "camera"), which would cause
    # _get_or_create_camera to reuse the same object for every file in a batch.
    cam_name = dmx_path.stem or camera_info.name
    fov_static  = camera_info.get("fieldOfView", 75.0)

    # ── Resolve animation clip ────────────────────────────────────────────────
    # SFM writes either a top-level 'channelsClip' or nests it inside
    # 'animationList'. Mirror camera_loader.py's fallback logic.
    if "channelsClip" in scene:
        clip = scene["channelsClip"]
    elif "animationList" in scene:
        clip = scene["animationList"]["animations"][0]
    else:
        raise RuntimeError("No channelsClip or animationList found in DMX")

    fps        = clip.get("frameRate", 30)
    channels   = clip.get("channels") or []

    # Frame offset — same as Import_DMX_Animation._patch_scale_and_root()
    time_frame = clip.get("timeFrame")
    start      = float(time_frame.get("start", 0)) if time_frame is not None else 0.0

    def frame_for(t):
        return (float(t) + start) * fps

    # ── Build hierarchy ───────────────────────────────────────────────────────
    target_col = collection or _get_or_create_collection(COLLECTION_SINGLE, COLOR_SINGLE)
    axis_empty  = _get_or_create_axis_empty(cam_name, target_col)
    root_empty  = _get_or_create_root_empty(cam_name, axis_empty, target_col)

    # Camera keeps identity local rotation (no static aim offset).
    local_align = None

    camera_obj  = _get_or_create_camera(cam_name, root_empty, target_col,
                                        local_align=local_align)

    camera_data = camera_obj.data
    camera_data.lens = _fov_to_lens(fov_static) - LENS_OFFSET_MM

    # Near/far clip planes, chosen by import scale.
    clip_start, clip_end = _clip_range_for_scale(scale)
    camera_data.clip_start = clip_start
    camera_data.clip_end   = clip_end

    # ── Create actions ────────────────────────────────────────────────────────
    root_action, root_bag = make_action(f"{cam_name}_root", root_empty)
    root_empty.rotation_mode = "QUATERNION"

    cam_action = None   # created lazily only if FOV is animated
    cam_bag    = None

    # ── Process channels ──────────────────────────────────────────────────────
    group = "camera_transform"

    for channel in channels:
        ch_name = channel.name or ""

        try:
            log_elem = channel.get("log")
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
            print(f"[DMX_CAM]  ch '{ch_name}' log read failed: {e}")
            continue

        # ── Position  (camera_loader.py formula — verified correct for cameras) ──
        # SFM (x, y, z) → Blender (y, -x, z)
        # Cameras use a different axis mapping than armature root transforms.
        if ch_name.endswith("_p"):
            if fix_quat_flips:
                # smooth path — original behaviour, key fractional sample times.
                for t, v in zip(times, values):
                    fr  = frame_for(t)
                    loc = Vector((float(v[1]), -float(v[0]), float(v[2]))) * scale
                    for i in range(3):
                        _key(root_bag, "location", i, group, fr, loc[i])
            else:
                # raw/stepped path — RESAMPLE ON EVERY INTEGER FRAME by LINEAR
                # interpolation between bracketing samples, keyed LINEAR. Same
                # reasoning as orientation: keeps smooth moves smooth while a cut
                # stays a near-vertical one-frame jump, and guarantees a keyframe
                # on every whole frame so between-frame cuts aren't skipped.
                psamples = []
                for t, v in zip(times, values):
                    f   = frame_for(t)
                    loc = (float(v[1]) * scale, -float(v[0]) * scale, float(v[2]) * scale)
                    psamples.append((f, loc))
                psamples.sort(key=lambda s: s[0])

                if psamples:
                    f_lo = int(math.floor(psamples[0][0]))
                    f_hi = int(math.ceil(psamples[-1][0]))
                    n_s  = len(psamples)
                    si   = 0

                    for frame in range(f_lo, f_hi + 1):
                        while si < n_s and psamples[si][0] < frame:
                            si += 1
                        if si == 0:
                            loc = psamples[0][1]
                        elif si >= n_s:
                            loc = psamples[-1][1]
                        else:
                            f0, l0 = psamples[si - 1]
                            f1, l1 = psamples[si]
                            if f1 == f0:
                                loc = l1
                            else:
                                a = (frame - f0) / (f1 - f0)
                                loc = tuple(l0[k] + (l1[k] - l0[k]) * a
                                            for k in range(3))
                        for i in range(3):
                            _key(root_bag, "location", i, group,
                                 frame, loc[i], interp="LINEAR")

        # ── Orientation  (camera_loader.py formula — verified correct for cameras) ──
        # Component reorder: DMX (x,y,z,w) → Quaternion(y, w, x, z)
        elif ch_name.endswith("_o"):
            if fix_quat_flips:
                # smooth/fixed path — mathutils canonicalises + LINEAR ramps,
                # aligned per-key by rotate(); flip-fix pass runs later.
                for t, v in zip(times, values):
                    fr   = frame_for(t)
                    quat = Quaternion((float(v[1]), float(v[3]),
                                       float(v[0]), float(v[2])))
                    quat.rotate(Euler((-pi / 2, 0.0, -pi)))
                    for i in range(4):
                        _key(root_bag, "rotation_quaternion", i, group, fr, quat[i])
            else:
                # raw/stepped path — RESAMPLE ON EVERY INTEGER FRAME by LINEAR
                # interpolation between bracketing SFM samples, keyed LINEAR.
                #
                # Why linear, not hold-previous/CONSTANT: SFM data contains BOTH
                # smooth moves and hard cuts. Hold-previous made everything step,
                # turning smooth pans into a staircase. Linear interpolation
                # between the surrounding samples keeps smooth moves smooth, and
                # a hard cut still reads as a near-vertical one-frame jump because
                # its samples are close together in time. Resampling onto integer
                # frames is what ensures a cut that falls BETWEEN frames still
                # gets a keyframe on a whole frame (the original skipping bug).
                samples = []
                for t, v in zip(times, values):
                    f = frame_for(t)
                    quat = Quaternion((float(v[1]), float(v[3]),
                                       float(v[0]), float(v[2])))
                    quat.rotate(Euler((-pi / 2, 0.0, -pi)))   # original correct aim
                    samples.append((f, (quat[0], quat[1], quat[2], quat[3])))
                samples.sort(key=lambda s: s[0])

                if samples:
                    f_lo = int(math.floor(samples[0][0]))
                    f_hi = int(math.ceil(samples[-1][0]))
                    n_s  = len(samples)
                    si   = 0   # index of the first sample with frame >= current

                    for frame in range(f_lo, f_hi + 1):
                        # advance si so samples[si-1].f <= frame <= samples[si].f
                        while si < n_s and samples[si][0] < frame:
                            si += 1
                        if si == 0:
                            q = samples[0][1]
                        elif si >= n_s:
                            q = samples[-1][1]
                        else:
                            f0, q0 = samples[si - 1]
                            f1, q1 = samples[si]
                            if f1 == f0:
                                q = q1
                            else:
                                a = (frame - f0) / (f1 - f0)
                                q = tuple(q0[k] + (q1[k] - q0[k]) * a
                                          for k in range(4))
                        for i in range(4):
                            _key(root_bag, "rotation_quaternion", i, group,
                                 frame, q[i], interp="LINEAR")

        # ── FOV / lens ─────────────────────────────────────────────────────────
        elif ch_name.endswith("_fieldOfView") or ch_name.endswith("fieldOfView"):
            if cam_action is None:
                cam_action, cam_bag = make_action(f"{cam_name}_lens", camera_data)
            if fix_quat_flips:
                # smooth path — original behaviour, key fractional sample times.
                for t, v in zip(times, values):
                    fr   = frame_for(t)
                    lens = _fov_to_lens(float(v)) - LENS_OFFSET_MM
                    _key(cam_bag, "lens", 0, "lens", fr, lens)
            else:
                # raw/stepped path — RESAMPLE ON EVERY INTEGER FRAME by LINEAR
                # interpolation, same as rotation/position, so lens keyframes
                # land on whole frames (a focal-length change between frames
                # otherwise gets no keyframe on a whole frame). Interpolate FOV
                # then convert to lens per frame.
                lsamples = []
                for t, v in zip(times, values):
                    f = frame_for(t)
                    lsamples.append((f, float(v)))   # store FOV degrees
                lsamples.sort(key=lambda s: s[0])

                if lsamples:
                    f_lo = int(math.floor(lsamples[0][0]))
                    f_hi = int(math.ceil(lsamples[-1][0]))
                    n_s  = len(lsamples)
                    si   = 0

                    for frame in range(f_lo, f_hi + 1):
                        while si < n_s and lsamples[si][0] < frame:
                            si += 1
                        if si == 0:
                            fov = lsamples[0][1]
                        elif si >= n_s:
                            fov = lsamples[-1][1]
                        else:
                            f0, v0 = lsamples[si - 1]
                            f1, v1 = lsamples[si]
                            if f1 == f0:
                                fov = v1
                            else:
                                a = (frame - f0) / (f1 - f0)
                                fov = v0 + (v1 - v0) * a
                        _key(cam_bag, "lens", 0, "lens", frame,
                             _fov_to_lens(fov) - LENS_OFFSET_MM, interp="LINEAR")

        # ── Aperture -> DOF f-stop ───────────────────────────────────────────────
        elif ch_name.endswith("_aperture") or ch_name.endswith("aperture"):
            if cam_action is None:
                cam_action, cam_bag = make_action(f"{cam_name}_lens", camera_data)
            camera_data.dof.use_dof = True
            if fix_quat_flips:
                for t, v in zip(times, values):
                    fr = frame_for(t)
                    _key(cam_bag, "dof.aperture_fstop", 0, "dof",
                         fr, _aperture_to_fstop(float(v)))
            else:
                asamples = sorted((frame_for(t), float(v)) for t, v in zip(times, values))
                if asamples:
                    f_lo = int(math.floor(asamples[0][0]))
                    f_hi = int(math.ceil(asamples[-1][0]))
                    n_s  = len(asamples); si = 0
                    for frame in range(f_lo, f_hi + 1):
                        while si < n_s and asamples[si][0] < frame:
                            si += 1
                        if si == 0:
                            ap = asamples[0][1]
                        elif si >= n_s:
                            ap = asamples[-1][1]
                        else:
                            f0, v0 = asamples[si - 1]; f1, v1 = asamples[si]
                            ap = v1 if f1 == f0 else v0 + (v1 - v0) * (frame - f0) / (f1 - f0)
                        _key(cam_bag, "dof.aperture_fstop", 0, "dof",
                             frame, _aperture_to_fstop(ap), interp="LINEAR")

        # ── Focal distance -> DOF focus distance (1:1, * scale) ──────────────────
        elif ch_name.endswith("_focalDistance") or ch_name.endswith("focalDistance"):
            if cam_action is None:
                cam_action, cam_bag = make_action(f"{cam_name}_lens", camera_data)
            camera_data.dof.use_dof = True
            if fix_quat_flips:
                for t, v in zip(times, values):
                    fr = frame_for(t)
                    _key(cam_bag, "dof.focus_distance", 0, "dof",
                         fr, _focal_distance(float(v), scale))
            else:
                dsamples = sorted((frame_for(t), float(v)) for t, v in zip(times, values))
                if dsamples:
                    f_lo = int(math.floor(dsamples[0][0]))
                    f_hi = int(math.ceil(dsamples[-1][0]))
                    n_s  = len(dsamples); si = 0
                    for frame in range(f_lo, f_hi + 1):
                        while si < n_s and dsamples[si][0] < frame:
                            si += 1
                        if si == 0:
                            fd = dsamples[0][1]
                        elif si >= n_s:
                            fd = dsamples[-1][1]
                        else:
                            f0, v0 = dsamples[si - 1]; f1, v1 = dsamples[si]
                            fd = v1 if f1 == f0 else v0 + (v1 - v0) * (frame - f0) / (f1 - f0)
                        _key(cam_bag, "dof.focus_distance", 0, "dof",
                             frame, _focal_distance(fd, scale), interp="LINEAR")

    # ── Quaternion flip fix ──────────────────────────────────────────────────
    quat_flips = 0
    if fix_quat_flips:
        quat_flips = _fix_quaternion_flips(root_action, root_empty)

    # ── Finalise F-curves ─────────────────────────────────────────────────────
    for fc in iter_fcurves(root_action, root_empty):
        fc.update()
    if cam_action:
        for fc in iter_fcurves(cam_action, camera_data):
            fc.update()

    root_curves = count_fcurves(root_action, root_empty)
    lens_curves = count_fcurves(cam_action, camera_data) if cam_action else 0
    print(f"[DMX_CAM]  done — root: {root_curves} F-curve(s), lens: {lens_curves} F-curve(s)")

    return {
        "camera_obj":  camera_obj,
        "root_empty":  root_empty,
        "axis_empty":  axis_empty,
        "root_action": root_action,
        "cam_action":  cam_action,
        "quat_flips":  quat_flips,
        "root_curves": root_curves,
        "lens_curves": lens_curves,
    }


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_ImportDmxCamera(Operator, ImportHelper):
    """Import SFM DMX camera animation with axis correction"""
    bl_idname  = "ht.import_dmx_camera"
    bl_label   = "DMX Camera"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".dmx"
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})

    scale: FloatProperty(
        name="Scale",
        description="World scale — match to your session import scale",
        default=1.0,
        min=0.001,
    )

    fix_quat_flips: BoolProperty(
        name="Fix Quaternion Flips",
        description="Negate quaternion keyframes where dot(prev,curr) < 0 to prevent 180° spin artifacts from SFM. OFF preserves raw stepped SFM rotation (no discontinuity smoothing).",
        default=False,
    )

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "fix_quat_flips")
        col.separator()
        col.prop(self, "scale")

    def execute(self, context):
        try:
            result = import_dmx_camera(self.filepath, scale=self.scale,
                                       fix_quat_flips=self.fix_quat_flips)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        cam   = result["camera_obj"]
        root  = result["root_empty"]
        lines = [
            f"File   : {Path(self.filepath).name}",
            f"Camera : {cam.name}",
            f"Root   : {root.name}",
            f"Axis   : {result['axis_empty'].name}",
            f"Root F-curves : {result['root_curves']}",
            "Collection: ___HoovyTools Camera___ (blue)",
        ]
        if result["cam_action"]:
            lines.append(f"Lens F-curves : {result['lens_curves']}")
        if self.fix_quat_flips:
            lines.append(f"Quat flips fixed : {result['quat_flips']}")

        def draw(self, context):
            for line in lines:
                self.layout.label(text=line)
        context.window_manager.popup_menu(draw, title="DMX Camera Imported", icon="CHECKMARK")
        self.report({"INFO"}, f"Imported camera '{cam.name}'")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU ITEM
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


def draw_menu_item(layout):
    """Draw this module's entry. Called from MT_HT_import_submenu.draw()."""
    layout.operator(
        HT_OT_ImportDmxCamera.bl_idname,
        text="DMX Camera",
        **_icon_id("import_dmx_camera", "CAMERA_DATA"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (HT_OT_ImportDmxCamera,)


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
    bpy.ops.ht.import_dmx_camera("INVOKE_DEFAULT")
