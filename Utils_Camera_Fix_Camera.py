"""
Utils_Camera_Fix_Camera.py  —  part of HoovyTools
==================================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Source Engine Utils ▸ Camera
       └─ Split Camera Cuts (Intelligent)

Select any part of an imported HoovyTools camera hierarchy — the {cam}_axis
empty, the {cam}_root empty, OR the camera object — then run the operator. It
detects hard CUTS in the animation and splits the take into one camera per shot
inside a purple collection called  ___HoovyTools Cameras___ , binding a timeline
marker at each cut so the active camera switches shot-to-shot.

Operates purely on existing keyframes — no re-import, no DMX parsing.

CUT DETECTION  (a cut fires when EITHER trigger hits, subject to cooldown)
─────────────────────────────────────────────────────────────────────────
  1. ROTATION  — per-axis Euler change between adjacent keyframes exceeds the
                 rotation threshold (default 15°) on X, Y, or Z.
  2. POSITION  — frame-to-frame move distance spikes to more than the spike
                 factor (default 20×) the rolling average of recent moves AND
                 exceeds an absolute minimum, catching teleports.
  3. COOLDOWN  — after a cut, suppress new cuts for N frames (default 10) so one
                 messy transition can't spawn a dozen cameras.
"""

bl_info = {
    "name":        "HoovyTools: Camera Utils (Split Cuts)",
    "description": "Split an imported SFM camera take into a camera per shot",
    "author":      "HoovyTools",
    "version":     (1, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > Source Engine Utils > Camera",
    "category":    "Import-Export",
}

import bpy
import math
from mathutils import Quaternion
from bpy.types import Operator
from bpy.props import FloatProperty, IntProperty, BoolProperty

from .anim_compat import iter_fcurves


# ──────────────────────────────────────────────────────────────────────────────
#  CONFIG DEFAULTS  (also exposed as operator properties)
# ──────────────────────────────────────────────────────────────────────────────

ROT_EPSILON_DEG  = 15.0   # per-axis Euler change (deg) marking a rotation cut
POS_SPIKE_FACTOR = 20.0   # move > this × rolling-average move = a cut
POS_MIN_SAMPLES  = 4      # moves needed before the position rule activates
POS_MIN_BASELINE = 1e-3   # ignore baselines smaller than this (avoids 0× blowup)
POS_MIN_MOVE     = 0.25   # spiking move must exceed this absolute floor (units)
COOLDOWN_FRAMES  = 10     # suppress new cuts for this many frames after one
ROLLING_WINDOW   = 6      # how many recent moves the baseline average uses

SPLIT_COLLECTION = "___HoovyTools Cameras___"
SPLIT_COLOR      = "COLOR_06"   # purple


# ──────────────────────────────────────────────────────────────────────────────
#  ICON HELPER
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
#  SELECTION → ROOT
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_root(obj):
    """From any selected part of the hierarchy return the animated ROOT empty."""
    if obj is None:
        return None
    if obj.type == "CAMERA":
        return obj.parent
    if obj.type == "EMPTY":
        name = obj.name
        if name.endswith("_axis"):
            for child in obj.children:
                if child.type == "EMPTY" and child.name.endswith("_root"):
                    return child
            for child in obj.children:
                if child.type == "EMPTY":
                    return child
        if name.endswith("_root"):
            return obj
        if obj.animation_data and obj.animation_data.action:
            return obj
    p = obj.parent
    while p is not None:
        if p.type == "EMPTY" and p.animation_data and p.animation_data.action:
            return p
        p = p.parent
    return None


def _hierarchy_from_root(root):
    axis = root.parent if (root.parent and root.parent.type == "EMPTY") else None
    cam  = next((c for c in root.children if c.type == "CAMERA"), None)
    return axis, root, cam


# ──────────────────────────────────────────────────────────────────────────────
#  READ KEYFRAMES
# ──────────────────────────────────────────────────────────────────────────────

def _read_transform_keys(root):
    """Return (frames, eulers, positions) from the root's rotation+location keys."""
    action = root.animation_data.action if root.animation_data else None
    if action is None:
        return [], [], []

    quat_fc = [None, None, None, None]
    loc_fc  = [None, None, None]
    for fc in iter_fcurves(action, root):
        if fc.data_path == "rotation_quaternion" and 0 <= fc.array_index <= 3:
            quat_fc[fc.array_index] = fc
        elif fc.data_path == "location" and 0 <= fc.array_index <= 2:
            loc_fc[fc.array_index] = fc

    if not all(quat_fc):
        return [], [], []

    n = min(len(fc.keyframe_points) for fc in quat_fc)
    frames, eulers, positions = [], [], []
    for i in range(n):
        fr = quat_fc[0].keyframe_points[i].co[0]
        q  = Quaternion((quat_fc[0].keyframe_points[i].co[1],
                         quat_fc[1].keyframe_points[i].co[1],
                         quat_fc[2].keyframe_points[i].co[1],
                         quat_fc[3].keyframe_points[i].co[1]))
        e  = q.to_euler("XYZ")
        frames.append(fr)
        eulers.append((e.x, e.y, e.z))
        if all(loc_fc):
            positions.append(tuple(loc_fc[c].keyframe_points[i].co[1] for c in range(3)))
        else:
            positions.append((0.0, 0.0, 0.0))
    return frames, eulers, positions


# ──────────────────────────────────────────────────────────────────────────────
#  CUT DETECTION
# ──────────────────────────────────────────────────────────────────────────────

def detect_cuts(frames, eulers, positions,
                rot_eps_deg=ROT_EPSILON_DEG,
                pos_factor=POS_SPIKE_FACTOR,
                pos_min_samples=POS_MIN_SAMPLES,
                pos_min_baseline=POS_MIN_BASELINE,
                pos_min_move=POS_MIN_MOVE,
                cooldown=COOLDOWN_FRAMES,
                window=ROLLING_WINDOW):
    """Return (segments, reasons). Segment = (start_idx, end_idx) end-exclusive."""
    n = len(frames)
    if n == 0:
        return [], []

    rot_eps = math.radians(rot_eps_deg)
    cut_idx = [0]
    reasons = []
    recent_moves = []
    last_cut_frame = None

    for i in range(1, n):
        in_cooldown = (last_cut_frame is not None and
                       (frames[i] - last_cut_frame) < cooldown)

        de = [abs(eulers[i][a] - eulers[i-1][a]) for a in range(3)]
        de = [min(d, 2*math.pi - d) for d in de]
        rot_hit = any(d > rot_eps for d in de)

        move = math.dist(positions[i], positions[i-1])
        pos_hit = False
        if len(recent_moves) >= pos_min_samples:
            avg = sum(recent_moves) / len(recent_moves)
            if (avg >= pos_min_baseline and move > pos_factor * avg
                    and move >= pos_min_move):
                pos_hit = True
        recent_moves.append(move)
        if len(recent_moves) > window:
            recent_moves.pop(0)

        if (rot_hit or pos_hit) and not in_cooldown:
            cut_idx.append(i)
            last_cut_frame = frames[i]
            why = []
            if rot_hit:
                why.append(f"rot {max(de)*180/math.pi:.0f}°")
            if pos_hit:
                why.append(f"pos {move:.2f}u")
            reasons.append((i, frames[i], ", ".join(why)))

    cut_idx.append(n)
    segs = [(cut_idx[k], cut_idx[k+1]) for k in range(len(cut_idx) - 1)]
    return segs, reasons


# ──────────────────────────────────────────────────────────────────────────────
#  COLLECTION + DUPLICATION
# ──────────────────────────────────────────────────────────────────────────────

def _get_split_collection():
    col = bpy.data.collections.get(SPLIT_COLLECTION)
    if col is None:
        col = bpy.data.collections.new(SPLIT_COLLECTION)
        bpy.context.scene.collection.children.link(col)
        print(f"[CAM_SPLIT]  created collection '{SPLIT_COLLECTION}'")
    col.color_tag = SPLIT_COLOR
    return col


def _move_to(obj, target):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    if obj.name not in target.objects:
        target.objects.link(obj)


def _trim_action(action, owner, f_start, f_end):
    for fc in iter_fcurves(action, owner):
        kps = fc.keyframe_points
        keep = [(kp.co[0], kp.co[1], kp.interpolation) for kp in kps
                if f_start - 1e-6 <= kp.co[0] <= f_end + 1e-6]
        for i in range(len(kps) - 1, -1, -1):
            kps.remove(kps[i])
        for (fr, val, interp) in keep:
            nkp = kps.insert(fr, val, options={"FAST"})
            nkp.interpolation = interp
        fc.update()


def _dup_hierarchy(axis, root, cam, suffix, collection):
    n_root = root.copy()
    n_cam  = cam.copy() if cam else None
    n_axis = axis.copy() if axis else None

    n_root.name = f"{root.name}{suffix}"
    if n_root.animation_data and n_root.animation_data.action:
        n_root.animation_data.action = n_root.animation_data.action.copy()

    if n_axis:
        n_axis.name = f"{axis.name}{suffix}"
    if n_cam:
        n_cam.name = f"{cam.name}{suffix}"
        n_cam.data = cam.data.copy()
        if n_cam.data.animation_data and n_cam.data.animation_data.action:
            n_cam.data.animation_data.action = n_cam.data.animation_data.action.copy()

    for o in (n_axis, n_root, n_cam):
        if o:
            _move_to(o, collection)

    if n_axis:
        n_root.parent = n_axis
        n_root.matrix_parent_inverse = root.matrix_parent_inverse.copy()
    if n_cam:
        n_cam.parent = n_root
        n_cam.matrix_parent_inverse = cam.matrix_parent_inverse.copy()

    return n_axis, n_root, n_cam


# ──────────────────────────────────────────────────────────────────────────────
#  PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def split_camera_cuts(selected, rot_eps_deg=ROT_EPSILON_DEG,
                      pos_factor=POS_SPIKE_FACTOR, cooldown=COOLDOWN_FRAMES,
                      bind_markers=True, delete_original=True) -> dict:
    root = _resolve_root(selected)
    if root is None:
        raise RuntimeError("Could not resolve a camera root from the selection. "
                           "Select the camera, its _root, or its _axis empty.")
    axis, root, cam = _hierarchy_from_root(root)
    if cam is None:
        raise RuntimeError(f"No camera found under root '{root.name}'.")

    frames, eulers, positions = _read_transform_keys(root)
    if not frames:
        raise RuntimeError("No rotation_quaternion keyframes on the root empty.")

    segs, reasons = detect_cuts(frames, eulers, positions,
                                rot_eps_deg=rot_eps_deg, pos_factor=pos_factor,
                                cooldown=cooldown)
    print(f"\n[CAM_SPLIT]  root '{root.name}': {len(frames)} keys -> {len(segs)} shot(s)")
    for (i, fr, why) in reasons:
        print(f"[CAM_SPLIT]    cut at frame {fr:.0f}  ({why})")

    if len(segs) <= 1:
        return {"shots": 1, "cameras": [cam.name], "single": True, "markers": 0}

    split_col = _get_split_collection()
    cameras, shot_markers = [], []

    for k, (s, e) in enumerate(segs, 1):
        f_start, f_end = frames[s], frames[e-1]
        n_axis, n_root, n_cam = _dup_hierarchy(axis, root, cam,
                                               f"_cut_{k:02d}", split_col)
        if n_root.animation_data and n_root.animation_data.action:
            _trim_action(n_root.animation_data.action, n_root, f_start, f_end)
        if n_cam.data.animation_data and n_cam.data.animation_data.action:
            _trim_action(n_cam.data.animation_data.action, n_cam.data, f_start, f_end)
        cameras.append(n_cam.name)
        shot_markers.append((f_start, n_cam))
        print(f"[CAM_SPLIT]  shot {k:02d}: frames {f_start:.0f}..{f_end:.0f} -> {n_cam.name}")

    if delete_original:
        cam_data = cam.data
        for o in (cam, root, axis):
            if o:
                try: bpy.data.objects.remove(o, do_unlink=True)
                except Exception: pass
        try: bpy.data.cameras.remove(cam_data, do_unlink=True)
        except Exception: pass

    markers = 0
    if bind_markers:
        tm = bpy.context.scene.timeline_markers
        for (f_start, cam_obj) in shot_markers:
            fr = int(round(f_start))
            mk = next((m for m in tm if m.frame == fr), None)
            if mk is None:
                mk = tm.new(name=f"cut_{cam_obj.name}", frame=fr)
            mk.camera = cam_obj
            markers += 1

    print(f"[CAM_SPLIT]  done — {len(segs)} cameras, {markers} marker(s)")
    return {"shots": len(segs), "cameras": cameras, "markers": markers,
            "single": False}


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_SplitCameraCuts(Operator):
    """Split the selected imported camera take into one camera per shot at hard cuts"""
    bl_idname  = "ht.split_camera_cuts"
    bl_label   = "Split Camera Cuts (Intelligent)"
    bl_options = {"REGISTER", "UNDO"}

    rot_epsilon: FloatProperty(
        name="Rotation Threshold (°)",
        description="Per-axis Euler change between keyframes that marks a cut",
        default=ROT_EPSILON_DEG, min=0.1, max=180.0,
    )
    pos_factor: FloatProperty(
        name="Position Spike (×)",
        description="A move this many times the recent average move marks a cut",
        default=POS_SPIKE_FACTOR, min=1.5, max=200.0,
    )
    cooldown: IntProperty(
        name="Cooldown (frames)",
        description="Suppress new cuts for this many frames after a cut",
        default=COOLDOWN_FRAMES, min=0, max=240,
    )
    bind_markers: BoolProperty(
        name="Bind Timeline Markers",
        description="Bind a camera marker at each cut so the scene switches "
                    "camera shot-to-shot on the timeline",
        default=True,
    )
    delete_original: BoolProperty(
        name="Delete Original Take",
        description="Remove the source camera after splitting",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "rot_epsilon")
        col.prop(self, "pos_factor")
        col.prop(self, "cooldown")
        col.separator()
        col.prop(self, "bind_markers")
        col.prop(self, "delete_original")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        sel = context.active_object or (
            context.selected_objects[0] if context.selected_objects else None)
        try:
            result = split_camera_cuts(
                sel, rot_eps_deg=self.rot_epsilon, pos_factor=self.pos_factor,
                cooldown=self.cooldown, bind_markers=self.bind_markers,
                delete_original=self.delete_original)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if result.get("single"):
            lines = [
                "Result : 1 shot (no cuts found)",
                "Tip    : lower the thresholds if you expected cuts",
            ]
        else:
            lines = [
                f"Shots  : {result['shots']} camera(s)",
                f"Markers: {result.get('markers', 0)} bound",
                f"Collection: {SPLIT_COLLECTION} (purple)",
            ]
        def draw_popup(self, context):
            for line in lines:
                self.layout.label(text=line)
        context.window_manager.popup_menu(
            draw_popup, title=f"Split Camera Cuts — {result['shots']} shot(s)",
            icon="CHECKMARK")
        self.report({"INFO"}, f"Split into {result['shots']} camera(s)")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU
# ──────────────────────────────────────────────────────────────────────────────

class MT_HT_utils_camera_submenu(bpy.types.Menu):
    bl_idname = "MT_HT_utils_camera_submenu"
    bl_label  = "Camera"

    def draw(self, context):
        self.layout.operator(
            HT_OT_SplitCameraCuts.bl_idname,
            text="Split Camera Cuts (Intelligent)",
            **_icon_id("split_camera", "CAMERA_DATA"),
        )


def draw_utils_camera_entry(layout):
    """Called from MT_HT_utils_submenu."""
    layout.menu(
        MT_HT_utils_camera_submenu.bl_idname,
        text="Camera",
        **_icon_id("utils_camera", "CAMERA_DATA"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (
    HT_OT_SplitCameraCuts,
    MT_HT_utils_camera_submenu,
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
