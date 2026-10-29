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
from bpy.props import StringProperty, FloatProperty, BoolProperty, EnumProperty
from ..core import Common_Props
from bpy_extras.io_utils import ImportHelper

from ..core import start_folders
from ..core.anim_compat import make_action, iter_fcurves, count_fcurves, fc_find_or_new
from ..core import camera_resample as CR


# ──────────────────────────────────────────────────────────────────────────────
#  MODULE CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

LENS_MODE = "SFM"

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
    from ..SST import get_datamodel
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
    """Convert SFM horizontal FOV (degrees) to Blender lens (mm) - the LEGACY reading (plain horizontal)."""
    return 0.5 * sensor_width / math.tan(math.radians(fov_degrees) / 2)


def _render_aspect() -> float:
    r = bpy.context.scene.render
    return (r.resolution_x * r.pixel_aspect_x) / max(1e-9, r.resolution_y * r.pixel_aspect_y)


def _fov_to_lens_sfm(fov_degrees: float, sensor_width: float = 36.0) -> float:
    """1.18.2: SFM's fieldOfView (horizontal at 4:3, vertical fixed - Hor+) -> the lens that gives a Blender camera
    (sensor fit AUTO, this sensor width) the SAME vertical framing at the scene's render aspect."""
    t = math.tan(math.radians(fov_degrees) / 2.0) * 0.75          # tan(vertical fov / 2)
    a = _render_aspect()
    return 0.5 * sensor_width / (t * a) if a >= 1.0 else 0.5 * sensor_width / t


def _lens_for(fov_degrees: float, mode: str, offset: float) -> float:
    if mode == "LEGACY":
        return max(1.0, _fov_to_lens(fov_degrees) - offset)
    return max(1.0, _fov_to_lens_sfm(fov_degrees))


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


def import_dmx_camera(dmx_path, scale: float = 1.0, fix_quat_flips: bool = False,
                      lens_offset: float = None,
                      collection=None, lens_mode: str = None) -> dict:
    """
    Import an SFM DMX camera animation.

    Parameters
    ──────────
    dmx_path        : str | Path   path to the camera .dmx file
    scale           : float        world scale multiplier (default 1.0, set to
                                   match your session import scale if needed)
    fix_quat_flips  : bool         True = the SMOOTH path: keys at SFM's own
                                   fractional times plus a dot<0 sign fix.
                                   False = the RAW/STEPPED path: resampled onto
                                   every integer frame, LINEAR.
                                   DEFAULT FALSE, AND THE DEFAULT IS LOAD-BEARING.
                                   The flag does not just toggle a sign fix - it
                                   selects between two whole import paths, and
                                   only the stepped one survives SFM's cut pairs
                                   (two keys ~0.001 frame apart). The smooth path
                                   keys them at fractional times, where Blender's
                                   keyframe_insert MERGES the pair and every hard
                                   cut smears into a slow visible spin. Measured
                                   on the user's 18-shot take: smooth kept 2 of
                                   21 cuts sharp and the splitter found 12 shots;
                                   stepped kept all 21 and found 18. The session
                                   orchestrator used to inherit True here while
                                   the standalone operator shipped False - the
                                   same file imported broken from a session and
                                   clean by hand, which read as an extraction bug
                                   and was not (extract vs export measured
                                   IDENTICAL: 0.000 units, 0.05 deg noise)
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

    #  THE NAME SFM KNOWS IT BY, KEPT SEPARATELY.
    #  The Blender objects are named after the FILE stem, deliberately - SFM
    #  gives nearly every camera the same internal name ("camera"), so naming
    #  from the element would collapse a whole batch onto one object. But that
    #  means the name the user typed in SFM is nowhere in the scene, and
    #  anything matching on it - the Developer tab's auto-split, a report, a
    #  search - would never find it. Stamp it on all three so it survives.
    sfm_name = str(getattr(camera_info, "name", "") or "")
    for _obj in (axis_empty, root_empty, camera_obj):
        _obj["ht_sfm_name"] = sfm_name
        _obj["ht_source_file"] = dmx_path.name
    if sfm_name:
        print(f"[DMX_CAM]  SFM name '{sfm_name}' -> objects '{cam_name}*'")

    camera_data = camera_obj.data
    _offset = LENS_OFFSET_MM if lens_offset is None else float(lens_offset)
    _mode = (lens_mode or LENS_MODE).upper()
    if _mode != "LEGACY":
        camera_data.sensor_fit = "AUTO"                 # the rule below assumes these two
        camera_data.sensor_width = 36.0
    camera_data.lens = _lens_for(fov_static, _mode, _offset)

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
    walked = 0          # 1.17.3: SFM samples put on the hemisphere of the one before
    cuts = set()        # 1.17.3: frames keyed CONSTANT before a hard cut

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
                #  1.17.3: core/camera_resample - the same linear in-between,
                #  except at a cut pair (never blended; the frame before it held).
                psamples = [(frame_for(t), (float(v[1]) * scale, -float(v[0]) * scale,
                                            float(v[2]) * scale))
                            for t, v in zip(times, values)]
                pkeys, pinfo = CR.resample_values(psamples)
                cuts |= pinfo["cuts"]
                for frame, loc in pkeys:
                    hold = "CONSTANT" if frame in pinfo["cuts"] else "LINEAR"
                    for i in range(3):
                        _key(root_bag, "location", i, group,
                             frame, loc[i], interp=hold)

        # ── Orientation  (camera_loader.py formula — verified correct for cameras) ──
        # Component reorder: DMX (x,y,z,w) → Quaternion(y, w, x, z)
        elif ch_name.endswith("_o"):
            if fix_quat_flips:
                # smooth/fixed path — mathutils canonicalises + LINEAR ramps,
                # aligned per-key by rotate(); flip-fix pass runs later.
                #  1.17.3: walked BEFORE keying, like every other path
                ssamples = []
                for t, v in zip(times, values):
                    quat = Quaternion((float(v[1]), float(v[3]),
                                       float(v[0]), float(v[2])))
                    quat.rotate(Euler((-pi / 2, 0.0, -pi)))
                    ssamples.append((frame_for(t), quat))
                ssamples, n_walk = CR.hemisphere_walk(sorted(ssamples, key=lambda s: s[0]))
                walked += n_walk
                for fr, quat in ssamples:
                    for i in range(4):
                        _key(root_bag, "rotation_quaternion", i, group, fr, quat[i])
            else:
                samples = []
                for t, v in zip(times, values):
                    quat = Quaternion((float(v[1]), float(v[3]),
                                       float(v[0]), float(v[2])))
                    quat.rotate(Euler((-pi / 2, 0.0, -pi)))   # original correct aim
                    samples.append((frame_for(t), quat))
                qkeys, qinfo = CR.resample_rotation(samples)
                walked += qinfo["flips"]
                cuts |= qinfo["cuts"]
                for frame, q in qkeys:
                    hold = "CONSTANT" if frame in qinfo["cuts"] else "LINEAR"
                    for i in range(4):
                        _key(root_bag, "rotation_quaternion", i, group,
                             frame, q[i], interp=hold)

        # ── FOV / lens ─────────────────────────────────────────────────────────
        elif ch_name.endswith("_fieldOfView") or ch_name.endswith("fieldOfView"):
            if cam_action is None:
                cam_action, cam_bag = make_action(f"{cam_name}_lens", camera_data)
            if fix_quat_flips:
                # smooth path — original behaviour, key fractional sample times.
                for t, v in zip(times, values):
                    fr   = frame_for(t)
                    lens = _lens_for(float(v), _mode, _offset)
                    _key(cam_bag, "lens", 0, "lens", fr, lens)
            else:
                # raw/stepped path — RESAMPLE ON EVERY INTEGER FRAME by LINEAR
                # interpolation, same as rotation/position, so lens keyframes
                # land on whole frames (a focal-length change between frames
                # otherwise gets no keyframe on a whole frame). Interpolate FOV
                # then convert to lens per frame.
                lkeys, linfo = CR.resample_values(
                    [(frame_for(t), float(v)) for t, v in zip(times, values)])  # FOV degrees
                for frame, fov in lkeys:
                    _key(cam_bag, "lens", 0, "lens", frame,
                         _lens_for(fov, _mode, _offset),
                         interp="CONSTANT" if frame in linfo["cuts"] else "LINEAR")

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
                akeys, ainfo = CR.resample_values(
                    [(frame_for(t), float(v)) for t, v in zip(times, values)])
                for frame, ap in akeys:
                    _key(cam_bag, "dof.aperture_fstop", 0, "dof",
                         frame, _aperture_to_fstop(ap),
                         interp="CONSTANT" if frame in ainfo["cuts"] else "LINEAR")

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
                dkeys, dinfo = CR.resample_values(
                    [(frame_for(t), float(v)) for t, v in zip(times, values)])
                for frame, fd in dkeys:
                    _key(cam_bag, "dof.focus_distance", 0, "dof",
                         frame, _focal_distance(fd, scale),
                         interp="CONSTANT" if frame in dinfo["cuts"] else "LINEAR")

    # ── Quaternion flip fix ──────────────────────────────────────────────────
    #  ON BOTH PATHS SINCE 1.16.0. `fix_quat_flips` picks smooth vs raw, and
    #  the hemisphere fix used to ride along with "smooth" only - so the raw
    #  path, the one a session import uses, kept every sign flip SFM wrote.
    #  Measured on the CSdeals session: camera wood_planks4 turned 1183
    #  degrees inside frame 368 (one flip between two whole-frame keys,
    #  LINEAR, so the in-between went the long way - which is what motion
    #  blur and a scrub actually show). Negating a key is the SAME
    #  orientation and moves nothing in time, so it cannot soften a cut; it
    #  only stops the path between keys from going round the back.
    #  1.17.3: the samples were walked BEFORE the resample, so this finds
    #  nothing on a fresh import - it stays as the belt to those braces.
    quat_flips = _fix_quaternion_flips(root_action, root_empty)

    # ── Finalise F-curves ─────────────────────────────────────────────────────
    for fc in iter_fcurves(root_action, root_empty):
        fc.update()
    if cam_action:
        for fc in iter_fcurves(cam_action, camera_data):
            fc.update()

    # ── Stamp what the FILE said, for tools that run later ───────────────
    #
    #  ShotBoundsChannel is a DmeBoolLog that SFM writes: it flips true while
    #  a shot is live. That makes it an AUTHORITATIVE shot range - we are not
    #  inferring it from motion. The camera splitter would otherwise have to
    #  guess cuts from rotation and position spikes, so stash the real answer
    #  on the root empty where it survives into the .blend.
    #
    #  Custom properties take plain Python types, so the spans go in as a
    #  flat list of floats, two per shot.
    try:
        from ..core import DMX_Analyzer
        spans = DMX_Analyzer.read_shot_bounds(clip, frame_for)
        if spans:
            flat = []
            for a, b in spans:
                flat.extend((float(a), float(b)))
            root_empty["ht_shot_bounds"] = flat
            print(f"[DMX_CAM]  shot bounds: {len(spans)} shot(s) "
                  f"{[(round(a), round(b)) for a, b in spans]}")
        root_empty["ht_source_fps"] = float(fps)
        root_empty["ht_cut_frames"] = [float(f) for f in sorted(cuts)]
        root_empty["ht_source_dmx"] = str(dmx_path)
    except Exception as exc:
        print(f"[DMX_CAM]  shot bounds unavailable: {exc}")

    root_curves = count_fcurves(root_action, root_empty)
    lens_curves = count_fcurves(cam_action, camera_data) if cam_action else 0
    print(f"[DMX_CAM]  done — root: {root_curves} F-curve(s), lens: {lens_curves} F-curve(s); "
          f"{walked} SFM sample(s) on the other sign walked, {len(cuts)} cut(s) held")

    return {
        "camera_obj":  camera_obj,
        "root_empty":  root_empty,
        "axis_empty":  axis_empty,
        "root_action": root_action,
        "cam_action":  cam_action,
        "quat_flips":  quat_flips,
        "walked":      walked,
        "cut_frames":  sorted(cuts),
        "root_curves": root_curves,
        "lens_curves": lens_curves,
    }


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR
# ──────────────────────────────────────────────────────────────────────────────

@start_folders.browser_at("camera")          # 3.0.0: opens where you work, learns your folder
class HT_OT_ImportDmxCamera(Operator, ImportHelper):
    """PICK .dmx (camera) - ONE SFM camera export, not a session

        Build a Blender camera from an SFM camera .dmx

Creates the camera, a root empty carrying its motion, and an axis empty,
in their own collection. Position, orientation and focal length all come
from the file.

THE CONVERSION IS VERIFIED - DO NOT "FIX" IT
  Measured across 363 real SFM camera exports: median roll 0.16 degrees,
  358 of 363 within 5 degrees of level, none anywhere near 90. If a
  camera looks wrong, check the ROOT MOTION of what it is pointing at
  before suspecting the camera.

THE LENS IS SFM'S FRAMING (1.18.2)
  SFM's field of view is horizontal at 4:3 with the vertical fixed; the
  lens is set so Blender shows the same vertical framing at your render
  aspect. Export the camera back out to SFM
  and you get the same file. The old lens (minus a 10 mm fudge)
  is Lens: Legacy.
    """
    #  BELOW THE TOOLTIP CAP. Blender truncates an operator description
    #  at 1023 characters, without a warning, mid-word. These paragraphs
    #  were part of the docstring and were already being cut off before
    #  anyone could read them, so they live here instead - kept, but out
    #  of the tooltip's budget.
    #  FROM A SESSION, camera settings are normalised 0..1 values behind rescale
    #  operators, so extraction converts them; a raw read would give you a
    #  0.2 degree camera
    #

    bl_idname  = "ht.import_dmx_camera"
    bl_label   = "DMX Camera"
    #  NO "REGISTER" - see the note in Report_UI/the constitution.
    #  REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    #  touching any field in it RE-RUNS this operator. Re-running an
    #  import re-reads the DMX and rebuilds every f-curve; nudging Scale
    #  there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    #  with the value you wanted is the safe way to change your mind.
    bl_options = {"UNDO"}

    filename_ext = ".dmx"
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})

    # [roadmap #1] same precision fix as the animation importers.
    scale: FloatProperty(**Common_Props.scale_prop(
        name="Scale",
        description=("World scale - match to your session import scale. "
                     "Full precision is kept, so Hammer Unit factors survive"),
    ))

    scale_preset: EnumProperty(**Common_Props.scale_preset_prop())

    lens_mode: EnumProperty(  # type: ignore
        name="Lens",
        items=[("SFM", "SFM Framing", "SFM's own rule: its field of view is horizontal at 4:3 with the vertical fixed, "
                                      "so Blender shows exactly SFM's framing at your render aspect - and the camera "
                                      "exports back to the same file (1.18.2 default)"),
               ("LEGACY", "Legacy (Offset)", "The old reading: horizontal on the full sensor, minus Lens Offset")],
        default="SFM",
    )

    lens_offset: FloatProperty(  # type: ignore
        name="Lens Offset (mm)",
        description=(
            "Subtracted from the focal length the DMX asks for. "
            "A session camera reporting 32.4 degrees wants 61.96 mm; "
            "the default 10 mm offset yields 51.96 mm, about 5.8 "
            "degrees WIDER than SFM. Set this to 0 to match SFM's "
            "stated field of view exactly"),
        default=LENS_OFFSET_MM, min=0.0, soft_max=40.0, precision=3,
    )

    fix_quat_flips: BoolProperty(
        name="Fix Quaternion Flips",
        description=("OFF (default - what a session uses): one key on every whole frame, in-betweens slerped, "
                     "hard cuts kept instant. ON: keys at SFM's own sample times - SFM's cut pairs merge and a cut "
                     "smears into a spin. Both are sign-walked: no flips either way (1.17.3)"),
        default=False,
    )

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "fix_quat_flips")
        col.separator()
        Common_Props.draw_scale(col, self, "scale")
        col.prop(self, "lens_mode")
        sub = col.row()
        sub.active = self.lens_mode == "LEGACY"
        sub.prop(self, "lens_offset")

    def execute(self, context):
        try:
            result = import_dmx_camera(self.filepath, scale=self.scale,
                                       lens_offset=self.lens_offset,
                                       fix_quat_flips=self.fix_quat_flips,
                                       lens_mode=self.lens_mode)
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
        lines.append(f"Samples sign-walked : {result['walked']}")
        lines.append(f"Cuts held : {len(result['cut_frames'])}")

        from ..core import Report_UI
        Report_UI.report(
            context, "import_dmx_camera", "DMX Camera Imported", lines,
            level='INFO', prefix="DMX_CAM", operator=self,
            summary=f"DMX Camera - {cam.name} "
                    f"({result['root_curves']} root F-curve(s))")
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
    """Draw this module's entry. Called from HT_MT_import_submenu.draw()."""
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
