"""
Utils_Camera_Fix_Camera.py  —  part of HoovyTools
==================================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Source Engine Utils ▸ Camera
       └─ Split Camera Cuts (Intelligent)

Select any part of an imported HoovyTools camera hierarchy — the {cam}_axis
empty, the {cam}_root empty, OR the camera object — then run the operator. It
detects hard CUTS in the animation and splits the take into one camera per shot
inside a purple collection called  __HoovyTools Camera Split__ , binding a
timeline marker at each cut so the active camera switches shot-to-shot.

That collection is deliberately NOT one of the ones a session re-import clears.
Splitting is downstream work with edits hanging off it, and quietly deleting it
because the take was re-imported is a loss you only notice later.

Operates purely on existing keyframes — no re-import, no DMX parsing.

CUT DETECTION — POSITION ONLY  [replaced]
─────────────────────────────────────────────────────────────────────────
  1. POSITION  — a frame's move is a cut when it is POS_SPIKE_FACTOR times the
                 rolling average of what the camera was JUST doing, AND is big
                 in absolute terms.
  2. FLOOR     — "big" is derived from the take's own extent, so it scales with
                 the scene. Without it, a camera moving off from a dead stop has
                 a rolling average of ~0, the ratio is infinite, and every
                 move-off reads as a cut.
  3. COOLDOWN  — after a cut, suppress new cuts for N frames so one messy
                 transition can't spawn a dozen cameras.

  ROTATION IS OFF BY DEFAULT (USE_ROTATION). It used to vote on an ABSOLUTE
  threshold - any per-axis Euler change over 15° was a cut - and on a real take
  that produced HUNDREDS of cameras where there were twelve shots. Two reasons
  it could not work: a whip-pan is not a cut and routinely beats any threshold a
  real cut would clear, and Euler components jump by ~2π near gimbal, so the
  wrap guard turned one smooth pan into a string of false positives.

  Switched on, it now works the SAME WAY AS POSITION - relative, not absolute:
  a turn is a cut when it is ROT_SPIKE_FACTOR times the recent average turn AND
  is at least ROT_EPSILON_DEG. The angle is the true rotation between
  consecutive orientations (quaternion difference), which is wrap-free by
  construction, so the gimbal problem cannot come back.

  Position stays the primary signal: a cut is a TELEPORT, and a teleport shows
  up in POSITION.

CONTINUATION HANDLES
─────────────────────────────────────────────────────────────────────────
A split camera stops dead at its cut, so moving the edit even two frames later
leaves it holding on its last key — the cut gets welded in place at split time,
which is backwards. Every shot therefore gets extra motion written BEFORE its
first frame and AFTER its last, extrapolated from the speed measured AT the cut
and decayed to a dead stop over HANDLE_SECONDS.

The decay holds full speed for the first HOLD_FRACTION of the handle and then
eases out on a quintic (zero 1st AND 2nd derivative at both ends): no kick as
the deceleration starts, no snap as it lands, and a cut moved INTO the hold
window reads as original footage rather than as a handle.
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
from mathutils import Euler, Quaternion
from bpy.types import Operator
from bpy.props import FloatProperty, IntProperty, BoolProperty

try:
    from ..core.anim_compat import iter_fcurves
except ImportError:
    #1.17.3: the Text Editor camera standalone embeds this file (as
    #`camera_splitter`) and hands it its own iter_fcurves after import.
    iter_fcurves = None


# ──────────────────────────────────────────────────────────────────────────────
# CONFIG DEFAULTS  (also exposed as operator properties)
# ──────────────────────────────────────────────────────────────────────────────

ROT_EPSILON_DEG  = 15.0   # rotation FLOOR (deg) - a turn smaller never cuts
ROT_SPIKE_FACTOR = 20.0   # turn > this × recent average turn = a rotation cut
USE_ROTATION     = False  # leave OFF - position alone is doing the job
POS_SPIKE_FACTOR = 10.0   # move > this × rolling-average move = a cut
POS_MIN_SAMPLES  = 4      # moves needed before the position rule activates
POS_MIN_BASELINE = 1e-6   # ignore baselines smaller than this (avoids 0× blowup)
POS_MIN_MOVE     = 0.25   # absolute floor, units (the extent floor usually wins)
POS_MIN_EXTENT   = 0.02   # ...or 2% of the take's own extent, whichever is more
COOLDOWN_FRAMES  = 10     # suppress new cuts for this many frames after one
ROLLING_WINDOW   = 4      # how many recent moves the baseline average uses

# continuation handles
HANDLE_SECONDS   = 3.0    # runway written on EACH side of every cut
HOLD_FRACTION    = 0.30   # fraction of the handle held at full speed
VELOCITY_SAMPLES = 5      # keys least-squares-fitted to measure speed at a cut
LENS_MIN_MM      = 1.0    # focal length is physically bounded; position isn't
LENS_MAX_MM      = 5000.0

# Splits live in their own collection, not the importer's camera collection
# Session re-import deletes the importer's collections (see
# Session_Steps._clear_imported_cameras), which would silently throw away every
# split the moment the session was re-imported
SPLIT_COLLECTION = "__HoovyTools Camera Split__"
SPLIT_COLOR      = "COLOR_06"   #purple


# ──────────────────────────────────────────────────────────────────────────────
# icon helper
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
# selection → root
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
# read keyframes
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

    #position is sampled by frame, not by key index.
    #
    #This used to take n from the QUATERNION curves alone and then index the
    #LOCATION curves with the same i:
    #
    #n = min(len(fc.keyframe_points) for fc in quat_fc)
    #positions.append(loc_fc[c].keyframe_points[i]...)
    #
    #which crashes the moment a location curve is one key shorter than a
    #rotation curve - reported from a real camera as
    #"bpy_prop_collection[index]: index 539 out of range, size 539"
    #
    #It was also wrong in a quieter way even when it did not crash: it
    #assumed key #i on rotation sits at the same FRAME as key #i on location.
    #SFM doesn't promise that - channels are keyed independently and a
    #trimmed or repaired curve breaks the alignment - so a mismatch silently
    #paired a rotation with somebody else's position and moved every cut.
    #
    #Evaluating the location curves AT the rotation key's frame is immune to
    #both: different key counts, and keys that do not line up
    n = min(len(fc.keyframe_points) for fc in quat_fc)
    have_loc = all(loc_fc)
    frames, eulers, positions = [], [], []
    for i in range(n):
        kp = [fc.keyframe_points[i] for fc in quat_fc]
        fr = kp[0].co[0]
        q  = Quaternion((kp[0].co[1], kp[1].co[1], kp[2].co[1], kp[3].co[1]))
        e  = q.to_euler("XYZ")
        frames.append(fr)
        eulers.append((e.x, e.y, e.z))
        positions.append(tuple(loc_fc[c].evaluate(fr) for c in range(3))
                         if have_loc else (0.0, 0.0, 0.0))
    return frames, eulers, positions


# ──────────────────────────────────────────────────────────────────────────────
# cut detection
# ──────────────────────────────────────────────────────────────────────────────

def detect_cuts(frames, eulers, positions,
                rot_eps_deg=ROT_EPSILON_DEG,
                pos_factor=POS_SPIKE_FACTOR,
                pos_min_samples=POS_MIN_SAMPLES,
                pos_min_baseline=POS_MIN_BASELINE,
                pos_min_move=POS_MIN_MOVE,
                cooldown=COOLDOWN_FRAMES,
                window=ROLLING_WINDOW,
                use_rotation=USE_ROTATION,
                rot_factor=ROT_SPIKE_FACTOR):
    """
    Return (segments, reasons). Segment = (start_idx, end_idx) end-exclusive.

    POSITION ONLY by default - see the module header for why rotation was taken
    out. `use_rotation` still reaches the old behaviour, and should stay off.
    """
    n = len(frames)
    if n == 0:
        return [], []

    # A cut teleports the camera, so it must move a real fraction of the whole
    # path in one frame - not merely more than it was moving a moment ago,
    # which is also true every single time it starts moving
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    zs = [p[2] for p in positions]
    extent = math.dist((min(xs), min(ys), min(zs)),
                       (max(xs), max(ys), max(zs))) if positions else 0.0
    floor = max(pos_min_move, extent * POS_MIN_EXTENT)

    rot_eps = math.radians(rot_eps_deg)
    seg_starts = [0]
    seg_ends = []
    skip_until = -1
    reasons = []
    recent_moves = []
    recent_turns = []
    last_cut_frame = None

    for i in range(1, n):
        # INSIDE A TELEPORT ALREADY COUNTED. Its remaining frames must not
        # reach the rolling baseline either - one 155-unit frame in the
        # window raises the average enough to hide the next real cut
        if i <= skip_until:
            continue
        in_cooldown = (last_cut_frame is not None and
                       (frames[i] - last_cut_frame) < cooldown)

        #ROTATION, when enabled: the same relative rule as position. The turn
        #is the TRUE angle between consecutive orientations, taken from the
        #quaternion difference - always in [0, pi] and wrap-free, so the
        #gimbal jumps that made the old absolute test useless can't recur.
        rot_hit, turn = False, 0.0
        if use_rotation:
            q_prev = Euler(eulers[i - 1], "XYZ").to_quaternion()
            q_now = Euler(eulers[i], "XYZ").to_quaternion()
            turn = abs(q_prev.rotation_difference(q_now).angle)
            if turn > math.pi:
                turn = 2.0 * math.pi - turn
            if len(recent_turns) >= pos_min_samples:
                avg_t = sum(recent_turns) / len(recent_turns)
                # Same shape as the position rule: the floor is mandatory, the
                # ratio is waived when the camera was not turning at all.
                if turn >= rot_eps and (avg_t < 1e-9 or turn > rot_factor * avg_t):
                    rot_hit = True
            recent_turns.append(turn)
            if len(recent_turns) > window:
                recent_turns.pop(0)

        move = math.dist(positions[i], positions[i-1])
        pos_hit = False
        ratio = 0.0
        if len(recent_moves) >= pos_min_samples:
            avg = sum(recent_moves) / len(recent_moves)
            ratio = move / avg if avg > pos_min_baseline else float("inf")
            # the floor is mandatory, the ratio is waived when there is no
            # BASELINE. A cut out of a HOLD has a rolling average of zero, so
            # requiring `avg >= baseline` first threw those away - measured:
            # 9 shots found on a 12-shot take, and the three missing ones were
            # exactly the three that followed a still camera. When the camera
            # was not moving, any move big enough to clear the extent floor is
            # a teleport by definition; the floor is doing the work there
            if move >= floor and (avg < pos_min_baseline
                                  or move > pos_factor * avg):
                pos_hit = True
        recent_moves.append(move)
        if len(recent_moves) > window:
            recent_moves.pop(0)

        if (rot_hit or pos_hit) and not in_cooldown:
            j = i
            while (j + 1 < n
                   and math.dist(positions[j + 1], positions[j]) >= floor):
                j += 1
            skip_until = j
            # the transit frames belong to neither shot.
            #
            # Frames i..j are the camera in FLIGHT between two shots. The
            # outgoing segment therefore ends at i-1 - its last frame that
            # is still honestly the old shot - and the incoming one starts
            # at j, the first frame that has arrived. Whatever lies between
            # is dropped, and the trimmed outgoing action simply holds its
            # final value across it
            #
            # Segments stop being contiguous when that happens, which is
            # fine: the caller reads `frames[s] .. frames[e - 1]` per
            # segment and never assumes one ends where the next begins
            #
            # A ONE-FRAME CUT IS THE same ARITHMETIC with j == i, giving
            # end=i and start=i exactly as before - so the thirteen clean
            # cuts in the measured take do not move
            seg_ends.append(max(i, seg_starts[-1] + 1))
            seg_starts.append(j)
            last_cut_frame = frames[j]
            why = []
            if rot_hit:
                why.append(f"rot {math.degrees(turn):.0f}°")
            if pos_hit:
                r = "inf" if ratio == float("inf") else f"{ratio:.0f}"
                why.append(f"pos {move:.2f}u ×{r}")
            if j > i:
                why.append(f"+{j - i}f transit")
            reasons.append((j, frames[j], ", ".join(why)))

    seg_ends.append(n)
    segs = list(zip(seg_starts, seg_ends))
    return segs, reasons


# ──────────────────────────────────────────────────────────────────────────────
# CONTINUATION HANDLES
# ──────────────────────────────────────────────────────────────────────────────

def _sorted_keys(fc):
    return sorted(fc.keyframe_points, key=lambda k: k.co[0])


def _edge_velocity(keys, at_start, samples=VELOCITY_SAMPLES):
    """
    Per-frame rate of change at a boundary, as (edge_key, slope).

    One interval is what the camera was doing at the instant it was cut, and is
    also maximally sensitive to noise - one jittery final key and the handle
    flies off at the wrong speed. SFM exports are resampled per frame, so a
    least-squares line over the last few keys follows a genuine acceleration
    while ignoring the jitter.
    """
    if len(keys) < 2:
        return None, 0.0
    edge = keys[0] if at_start else keys[-1]
    n = max(2, min(int(samples), len(keys)))
    window = keys[:n] if at_start else keys[-n:]
    if n == 2:
        a, b = window
        span = b.co[0] - a.co[0]
        return (edge, 0.0) if abs(span) < 1e-9 else (edge, (b.co[1] - a.co[1]) / span)
    xs = [k.co[0] for k in window]
    ys = [k.co[1] for k in window]
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return (edge, 0.0) if abs(den) < 1e-12 else (edge, num / den)


def _velocity_multiplier(u, hold=HOLD_FRACTION):
    """How much of the speed at the cut survives at position u (0..1) along the
    handle. 1.0 at u=0, exactly 0.0 at u=1, so the camera always fully stops."""
    if u <= hold:
        return 1.0
    span = 1.0 - hold
    t = 0.0 if span <= 1e-9 else min(1.0, max(0.0, (u - hold) / span))
    # quintic: zero 1st and 2nd derivative at both ends
    return 1.0 - (6.0 * t ** 5 - 15.0 * t ** 4 + 10.0 * t ** 3)


def _travel_table(frames, hold=HOLD_FRACTION):
    """Cumulative travel per step, in units of 'frames at full speed'. Numeric
    integration, so any decay curve can be swapped in without solving it."""
    table, total = [], 0.0
    for i in range(1, frames + 1):
        total += _velocity_multiplier(i / float(frames), hold)
        table.append(total)
    return table


def _extend_scalar(fc, at_start, frames, table, clamp=None):
    keys = _sorted_keys(fc)
    edge, per_frame = _edge_velocity(keys, at_start)
    if edge is None or abs(per_frame) < 1e-12:
        return 0.0
    if not at_start and edge.interpolation == "CONSTANT":
        edge.interpolation = "LINEAR"      #1.17.3: a shot ending on a held cut key
    direction = -1.0 if at_start else 1.0
    base_f, base_v = edge.co[0], edge.co[1]
    for i in range(1, frames + 1):
        value = base_v + per_frame * table[i - 1] * direction
        if clamp:
            value = max(clamp[0], min(clamp[1], value))
        kp = fc.keyframe_points.insert(base_f + i * direction, value,
                                       options={"FAST"})
        kp.interpolation = "LINEAR"
    return abs(per_frame * table[-1])


def _extend_quaternion(fcs, at_start, frames, table):
    """
    Rotation continued as a decaying ANGLE about a fixed axis.

    The delta quaternion between the last two keys is the turn made in one
    frame. Convert to axis-angle, scale the ANGLE by the decay, compose.
    Extrapolating w/x/y/z as four independent scalars leaves the unit sphere and
    the camera visibly skews.
    """
    keys = [_sorted_keys(fcs[i]) for i in range(4)]
    if any(len(k) < 2 for k in keys):
        return 0.0
    i0, i1 = (0, 1) if at_start else (-1, -2)
    q_edge = Quaternion([keys[c][i0].co[1] for c in range(4)])
    q_prev = Quaternion([keys[c][i1].co[1] for c in range(4)])
    if q_edge.dot(q_prev) < 0.0:
        q_prev = Quaternion([-v for v in q_prev])
    q_edge.normalize()
    q_prev.normalize()
    delta = q_edge @ q_prev.inverted()
    axis, angle = delta.axis, delta.angle
    if angle > math.pi:
        angle -= 2.0 * math.pi
    if abs(angle) < 1e-9:
        return 0.0

    direction = -1.0 if at_start else 1.0
    if not at_start:
        for c in range(4):                 #1.17.3: a shot ending on a held cut key
            if keys[c][i0].interpolation == "CONSTANT":
                keys[c][i0].interpolation = "LINEAR"
    base_f = keys[0][i0].co[0]
    running = q_edge.copy()
    prev_written = q_edge.copy()
    for i in range(1, frames + 1):
        step = table[i - 1] - (table[i - 2] if i > 1 else 0.0)
        running = Quaternion(axis, angle * step * direction) @ running
        running.normalize()
        # sign-align or the shortest-path interpolation flips and the camera
        # spins the long way round.
        if running.dot(prev_written) < 0.0:
            running = Quaternion([-v for v in running])
        for c in range(4):
            kp = fcs[c].keyframe_points.insert(base_f + i * direction,
                                               running[c], options={"FAST"})
            kp.interpolation = "LINEAR"
        prev_written = running.copy()
    return abs(math.degrees(angle * table[-1]))


def add_handles(root, cam, fps, seconds=HANDLE_SECONDS, hold=HOLD_FRACTION):
    """
    Write continuation motion on both sides of a shot.

    Motion lives on the ROOT and lens on the CAMERA in a HoovyTools camera rig,
    so both are extended with the SAME decay table - a lens that keeps creeping
    after the camera has stopped is worse than no handle at all.

    Returns (frames_per_handle, drift_units, turn_degrees).
    """
    n = int(round(max(0.0, seconds) * max(1e-9, fps)))
    if n <= 0:
        return 0, 0.0, 0.0
    table = _travel_table(n, hold)
    drift = turn = 0.0

    root_action = root.animation_data.action if root.animation_data else None
    cam_action = (cam.animation_data.action
                  if cam is not None and cam.animation_data else None)

    for at_start in (True, False):
        loc, quat = {}, {}
        if root_action:
            for fc in iter_fcurves(root_action, root):
                if fc.data_path == "location":
                    loc[fc.array_index] = fc
                elif fc.data_path == "rotation_quaternion":
                    quat[fc.array_index] = fc
        moved = [0.0, 0.0, 0.0]
        for i, fc in loc.items():
            moved[i] = _extend_scalar(fc, at_start, n, table)
        drift += math.dist((0.0, 0.0, 0.0), moved)
        if len(quat) == 4:
            turn += _extend_quaternion([quat[i] for i in range(4)],
                                       at_start, n, table)
        if cam_action:
            for fc in iter_fcurves(cam_action, cam):
                if fc.data_path.endswith("lens"):
                    _extend_scalar(fc, at_start, n, table,
                                   clamp=(LENS_MIN_MM, LENS_MAX_MM))
                elif fc.data_path.startswith("dof."):
                    _extend_scalar(fc, at_start, n, table)
    return n, drift, turn


# ──────────────────────────────────────────────────────────────────────────────
# COLLECTION + DUPLICATION
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


# keys exported by SFM don't land on integer frames. Measured on the
# corpus: a 24 fps camera take keys at 4.0008, 4.9992, 6.0000, 7.0008 -
# a drift of about +/-0.0008 of a frame. Anything closer than this to a
# whole frame was meant to BE that whole frame.        [roadmap #9]
FRAME_SNAP_TOLERANCE = 0.01


def _snap_frame(f, tolerance=FRAME_SNAP_TOLERANCE):
    r = round(f)
    return float(r) if abs(f - r) <= tolerance else float(f)


def _trim_action(action, owner, f_start, f_end, snap=True):
    """
    Keep only the keys inside [f_start, f_end], with their curve shape.

    THE BUG THIS FIXES                                     [roadmap #9]
    ===================================================================
    The old version saved (frame, value, interpolation), deleted every
    key, and re-inserted with options={"FAST"}. Bezier handles were
    never carried across, so every re-inserted key got fresh auto
    handles. On a fast camera move the boundary keys of each shot then
    interpolate differently from the take they were cut out of - which
    is the jerk, and why it showed at a segment edge and nowhere else.

    Handle POSITIONS are only meaningful for handles the user (or the
    importer) placed - FREE, ALIGNED, VECTOR. AUTO and AUTO_CLAMPED are
    derived, and Blender recomputes them on update(), correctly. So the
    type is restored first and the position only written for the types
    that own their position.

    The tolerance on the range test is the same snap tolerance, not the
    old 1e-6: with keys sitting at 4.9992 a micro-epsilon window drops
    or keeps a boundary key essentially at random.
    """
    eps = FRAME_SNAP_TOLERANCE if snap else 1e-6
    _POSITIONAL = {"FREE", "ALIGNED", "VECTOR"}

    for fc in iter_fcurves(action, owner):
        kps = fc.keyframe_points
        keep = []
        for kp in kps:
            if not (f_start - eps <= kp.co[0] <= f_end + eps):
                continue
            frame = _snap_frame(kp.co[0]) if snap else float(kp.co[0])
            keep.append({
                "frame": frame,
                "value": float(kp.co[1]),
                "interp": kp.interpolation,
                "easing": kp.easing,
                "lt": kp.handle_left_type,
                "rt": kp.handle_right_type,
                #handles are stored RELATIVE to the key, so a snapped
                #frame carries its handles with it instead of shearing
                #the tangent by the snap distance.
                "ldx": float(kp.handle_left[0]) - float(kp.co[0]),
                "ldy": float(kp.handle_left[1]) - float(kp.co[1]),
                "rdx": float(kp.handle_right[0]) - float(kp.co[0]),
                "rdy": float(kp.handle_right[1]) - float(kp.co[1]),
            })

        for i in range(len(kps) - 1, -1, -1):
            kps.remove(kps[i])

        for k in keep:
            nkp = kps.insert(k["frame"], k["value"], options={"FAST"})
            nkp.interpolation = k["interp"]
            nkp.easing = k["easing"]
            nkp.handle_left_type = k["lt"]
            nkp.handle_right_type = k["rt"]
            if k["lt"] in _POSITIONAL:
                nkp.handle_left[0] = k["frame"] + k["ldx"]
                nkp.handle_left[1] = k["value"] + k["ldy"]
            if k["rt"] in _POSITIONAL:
                nkp.handle_right[0] = k["frame"] + k["rdx"]
                nkp.handle_right[1] = k["value"] + k["rdy"]
        fc.update()


def validate_boundaries(objs, f_start, f_end, tolerance=FRAME_SNAP_TOLERANCE):
    """
    Check the first and last frame of a finished shot.       [roadmap #9]

    Returns a list of complaint strings - empty means the shot is clean.
    A shot is clean when every animated curve on every object actually
    HAS a key at the shot's first and last frame, so nothing at the edge
    is left to constant extrapolation from somewhere inside the take.
    """
    problems = []
    for obj in objs:
        if obj is None:
            continue
        owners = [(obj, obj.animation_data)]
        if obj.type == 'CAMERA' and obj.data:
            owners.append((obj.data, obj.data.animation_data))
        for owner, ad in owners:
            if ad is None or ad.action is None:
                continue
            for fc in iter_fcurves(ad.action, owner):
                kps = fc.keyframe_points
                if not len(kps):
                    problems.append(
                        f"{obj.name}: {fc.data_path}[{fc.array_index}] has no "
                        f"keys left after the trim")
                    continue
                first, last = kps[0].co[0], kps[len(kps) - 1].co[0]
                label = f"{obj.name}: {fc.data_path}[{fc.array_index}]"
                if first > f_start + tolerance:
                    problems.append(
                        f"{label} starts at {first:.3f}, shot starts "
                        f"at {f_start:.3f}")
                if last < f_end - tolerance:
                    problems.append(
                        f"{label} ends at {last:.3f}, shot ends "
                        f"at {f_end:.3f}")
    return problems


def repair_boundaries(objs, f_start, f_end):
    """
    Give every curve a real key at both shot edges.          [roadmap #9]

    Where a curve has nothing at the boundary, sample the curve there and
    write that value as an explicit key. The sampled value is what Blender
    was already showing (constant extrapolation from the nearest key), so
    this changes no visible motion - it just stops the edge frame from
    depending on extrapolation, which is what made a moved edit point
    reveal an empty or frozen frame.

    Returns how many keys were added.
    """
    added = 0
    for obj in objs:
        if obj is None:
            continue
        owners = [(obj, obj.animation_data)]
        if obj.type == 'CAMERA' and obj.data:
            owners.append((obj.data, obj.data.animation_data))
        for owner, ad in owners:
            if ad is None or ad.action is None:
                continue
            for fc in iter_fcurves(ad.action, owner):
                kps = fc.keyframe_points
                if not len(kps):
                    continue
                for edge in (f_start, f_end):
                    have = any(abs(kp.co[0] - edge) <= FRAME_SNAP_TOLERANCE
                               for kp in kps)
                    if have:
                        continue
                    value = fc.evaluate(edge)
                    nkp = kps.insert(edge, value, options={"FAST"})
                    nkp.interpolation = kps[0].interpolation
                    added += 1
                fc.update()
    return added


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
# public api
# ──────────────────────────────────────────────────────────────────────────────

def shot_bounds_of(root):
    """
    The shot ranges SFM itself wrote, if the importer stamped them.

    Returns [(f_start, f_end), ...] or []. This beats cut DETECTION outright
    when it exists: detect_cuts infers a cut from a rotation or position
    spike and can be fooled by a fast whip pan, whereas ShotBoundsChannel is
    the session stating where the shot actually was.
    """
    raw = root.get("ht_shot_bounds") if root else None
    if not raw:
        return []
    try:
        vals = [float(v) for v in raw]
    except (TypeError, ValueError):
        return []
    if len(vals) < 2:
        return []
    return [(vals[i], vals[i + 1]) for i in range(0, len(vals) - 1, 2)]


def _segments_from_bounds(frames, spans, tolerance=0.5):
    """
    Turn authoritative frame spans into (start_idx, end_idx) index pairs
    over *frames*, end-exclusive, matching what detect_cuts returns.

    A span that covers no keys is dropped rather than producing an empty
    camera - which is exactly the class of bug #9 was about.
    """
    segs, reasons = [], []
    for k, (f0, f1) in enumerate(spans):
        lo = hi = None
        for i, f in enumerate(frames):
            if f >= f0 - tolerance and f <= f1 + tolerance:
                lo = i if lo is None else lo
                hi = i
        if lo is None:
            continue
        segs.append((lo, hi + 1))
        reasons.append((lo, frames[lo], f"shot bounds {f0:.0f}-{f1:.0f}"))
    return segs, reasons


def split_camera_cuts(selected, rot_eps_deg=ROT_EPSILON_DEG,
                      pos_factor=POS_SPIKE_FACTOR, cooldown=COOLDOWN_FRAMES,
                      bind_markers=True, delete_original=True,
                      snap_frames=True, fix_boundaries=True,
                      use_shot_bounds=True,
                      handle_seconds=HANDLE_SECONDS,
                      hold_fraction=HOLD_FRACTION,
                      use_rotation=USE_ROTATION,
                      rot_factor=ROT_SPIKE_FACTOR) -> dict:
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

    # authoritative data beats inference. Only fall back to detect_cuts when
    # the file never told us, or told us about a single shot that the take
    # clearly outgrew (one exported clip holding several shots)
    source = "detected"
    segs, reasons = [], []
    spans = shot_bounds_of(root) if use_shot_bounds else []
    if len(spans) > 1:
        segs, reasons = _segments_from_bounds(frames, spans)
        source = "shot bounds"
    if len(segs) <= 1:
        segs, reasons = detect_cuts(frames, eulers, positions,
                                    rot_eps_deg=rot_eps_deg,
                                    pos_factor=pos_factor,
                                    cooldown=cooldown,
                                    use_rotation=use_rotation,
                                    rot_factor=rot_factor)
        source = "detected"
    print(f"\n[CAM_SPLIT]  root '{root.name}': {len(frames)} keys -> "
          f"{len(segs)} shot(s) via {source}")
    for (i, fr, why) in reasons:
        print(f"[CAM_SPLIT]    cut at frame {fr:.0f}  ({why})")

    if len(segs) <= 1:
        return {"shots": 1, "cameras": [cam.name], "single": True,
                "markers": 0, "source": source, "repaired": 0,
                "problems": []}

    split_col = _get_split_collection()
    cameras, shot_markers = [], []

    repaired_total = 0
    problems_total = []

    for k, (s, e) in enumerate(segs, 1):
        f_start, f_end = frames[s], frames[e - 1]
        if snap_frames:
            f_start, f_end = _snap_frame(f_start), _snap_frame(f_end)
        n_axis, n_root, n_cam = _dup_hierarchy(axis, root, cam,
                                               f"_cut_{k:02d}", split_col)
        if n_root.animation_data and n_root.animation_data.action:
            _trim_action(n_root.animation_data.action, n_root,
                         f_start, f_end, snap=snap_frames)
        if n_cam.data.animation_data and n_cam.data.animation_data.action:
            _trim_action(n_cam.data.animation_data.action, n_cam.data,
                         f_start, f_end, snap=snap_frames)

        #[roadmap #9] Look at what the trim actually produced instead of
        #trusting it. The lens curve is the usual offender: its keys are
        #not the root's keys, so a range taken from the root can leave the
        #focal length with nothing at a shot edge
        shot_objs = [n_root, n_cam]
        problems = validate_boundaries(shot_objs, f_start, f_end)
        if problems and fix_boundaries:
            repaired = repair_boundaries(shot_objs, f_start, f_end)
            repaired_total += repaired
            still = validate_boundaries(shot_objs, f_start, f_end)
            for msg in still:
                problems_total.append(f"shot {k:02d}: {msg}")
            print(f"[CAM_SPLIT]  shot {k:02d}: repaired {repaired} boundary "
                  f"key(s), {len(still)} left")
        elif problems:
            for msg in problems:
                problems_total.append(f"shot {k:02d}: {msg}")

        # continuation handles last, after the trim and the boundary repair -
        # they read the velocity at the shot's edge key, so anything that
        # moves or adds an edge key has to have happened already
        handle_frames = drift = turn = 0.0
        if handle_seconds > 0.0:
            fps = (bpy.context.scene.render.fps
                   / max(1e-9, bpy.context.scene.render.fps_base))
            handle_frames, drift, turn = add_handles(
                n_root, n_cam, fps, seconds=handle_seconds, hold=hold_fraction)

        cameras.append(n_cam.name)
        shot_markers.append((f_start, n_cam))
        extra = ""
        if handle_frames:
            extra = (f"  +{handle_frames}f handles "
                     f"(drift {drift:.2f}u, turn {turn:.1f}°)")
        print(f"[CAM_SPLIT]  shot {k:02d}: frames {f_start:.0f}..{f_end:.0f} "
              f"-> {n_cam.name}{extra}")

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

    print(f"[CAM_SPLIT]  done — {len(segs)} cameras, {markers} marker(s), "
          f"{repaired_total} boundary key(s) repaired")
    for msg in problems_total:
        print(f"[CAM_SPLIT]  UNRESOLVED  {msg}")
    return {"shots": len(segs), "cameras": cameras, "markers": markers,
            "single": False, "repaired": repaired_total,
            "problems": problems_total, "source": source}


# ──────────────────────────────────────────────────────────────────────────────
# operator
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_SplitCameraCuts(Operator):
    """Split one imported camera take into a separate camera per shot

An SFM camera export often contains several shots back to back. This
finds the hard cuts and gives each shot its own camera, so they can be
edited independently.

Cuts come from SFM's OWN shot boundaries when the file carries them -
ShotBoundsChannel is authoritative and is preferred over guessing from
motion. Motion detection is the fallback for a single-take file.

Select the imported camera's root first. The report lists the shots
found; Camera Shot Report afterwards shows whether any boundary is
ragged"""
    bl_idname  = "ht.split_camera_cuts"
    bl_label   = "Split Camera Cuts (Intelligent)"
    # NO "REGISTER" - see the note in Report_UI/the constitution
    # REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    # touching any field in it RE-RUNS this operator. Re-running an
    # import re-reads the DMX and rebuilds every f-curve; nudging Scale
    # there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    # with the value you wanted is the safe way to change your mind
    bl_options = {"UNDO"}

    use_rotation: BoolProperty(
        name="Also Cut On Rotation",
        description=(
            "OFF by design. Position alone finds the cuts, and rotation used "
            "to fire on an absolute 15° threshold, which turned every whip pan "
            "into a string of false cuts - hundreds of cameras on a "
            "twelve-shot take.\n\n"
            "Switched on, it now behaves like the position rule: a turn counts "
            "only if it is the spike factor below times the recent average "
            "turn AND clears the floor. Measured wrap-free from the quaternion "
            "difference, so gimbal jumps cannot fake it"),
        default=USE_ROTATION,
    )
    rot_epsilon: FloatProperty(
        name="Rotation Floor (°)",
        description=(
            "Minimum turn between frames before rotation may call a cut at "
            "all. Only used when Also Cut On Rotation is on"),
        default=ROT_EPSILON_DEG, min=0.1, max=180.0,
    )
    rot_factor: FloatProperty(
        name="Rotation Spike (×)",
        description=(
            "A turn this many times the recent average turn marks a cut. "
            "Only used when Also Cut On Rotation is on"),
        default=ROT_SPIKE_FACTOR, min=1.5, max=200.0,
    )
    pos_factor: FloatProperty(
        name="Position Spike (×)",
        description="A move this many times the recent average move marks a cut",
        default=POS_SPIKE_FACTOR, min=1.5, max=200.0,
    )
    handle_seconds: FloatProperty(
        name="Handles (seconds)",
        description=(
            "Extra motion written on BOTH sides of every cut, so a shot does "
            "not stop dead at its edit. The speed is measured AT the cut and "
            "decayed to a full stop across this many seconds, which is what "
            "lets you move a cut later without the camera running out of "
            "movement. 0 disables handles"),
        default=HANDLE_SECONDS, min=0.0, max=30.0,
    )
    hold_fraction: FloatProperty(
        name="Hold Full Speed (fraction)",
        description=(
            "How much of the handle runs at the ORIGINAL speed before the "
            "decay starts. Inside this window the motion is indistinguishable "
            "from the real take, so a cut moved into it reads as footage "
            "rather than as a handle"),
        default=HOLD_FRACTION, min=0.0, max=0.9,
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
    use_shot_bounds: BoolProperty(
        name="Use Shot Bounds If Present",
        description=(
            "Prefer the shot ranges SFM itself wrote over guessing cuts from "
            "motion. The DMX Camera importer stamps them on the root empty "
            "when the file has a ShotBoundsChannel. Detection is a fallback: "
            "it infers a cut from a rotation or position spike and a fast "
            "whip pan can fool it, while the bounds are the session simply "
            "stating where the shot was"),
        default=True,
    )
    snap_frames: BoolProperty(
        name="Snap To Whole Frames",
        description=(
            "SFM exports keys a fraction off the frame - 4.0008, 4.9992, "
            "6.0000 on a 24 fps take. Round anything within a hundredth of "
            "a frame onto the frame, so shot edges and camera markers land "
            "on the same number instead of straddling it. Handles move with "
            "their key, so curve shapes are untouched"),
        default=True,
    )
    fix_boundaries: BoolProperty(
        name="Repair Shot Boundaries",
        description=(
            "After splitting, check that every curve really has a key on "
            "the first and last frame of its shot, and write one where it "
            "does not. Fixes the empty or frozen frame at a segment edge - "
            "most visible on a fast move, where it reads as a jerk. The "
            "written value is what the curve already evaluated to, so no "
            "motion changes"),
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
        col.prop(self, "use_shot_bounds")
        col.prop(self, "snap_frames")
        col.prop(self, "fix_boundaries")
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
                delete_original=self.delete_original,
                snap_frames=self.snap_frames,
                fix_boundaries=self.fix_boundaries,
                use_shot_bounds=self.use_shot_bounds,
                handle_seconds=self.handle_seconds,
                hold_fraction=self.hold_fraction,
                use_rotation=self.use_rotation,
                rot_factor=self.rot_factor)
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
                f"Source : {result.get('source', 'detected')}",
                f"Markers: {result.get('markers', 0)} bound",
                f"Collection: {SPLIT_COLLECTION} (purple)",
            ]
            if result.get("repaired"):
                lines.append(f"Repaired: {result['repaired']} boundary key(s)")
            problems = result.get("problems") or []
            if problems:
                lines.append("")
                lines.append(f"{len(problems)} boundary issue(s) left:")
                for msg in problems[:4]:
                    lines.append(f"  {msg}")
                if len(problems) > 4:
                    lines.append(f"  ... and {len(problems) - 4} more (console)")

        for line in lines:
            print(f"[CAM_SPLIT]  {line}")
        from ..core import Report_UI
        Report_UI.report(
            context, "utils_camera_fix",
            f"Split Camera Cuts - {result['shots']} shot(s)", lines,
            level='INFO', operator=self, prefix="CAM_SPLIT",
            summary=f"Split Camera Cuts - {result['shots']} camera(s)")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
# menu
# ──────────────────────────────────────────────────────────────────────────────

class HT_MT_utils_camera_submenu(bpy.types.Menu):
    bl_idname = "HT_MT_utils_camera_submenu"
    bl_label  = "Camera"

    def draw(self, context):
        self.layout.operator(
            HT_OT_SplitCameraCuts.bl_idname,
            text="Split Camera Cuts (Intelligent)",
            **_icon_id("split_camera", "CAMERA_DATA"),
        )


def draw_utils_camera_entry(layout):
    """Called from HT_MT_utils_submenu."""
    layout.menu(
        HT_MT_utils_camera_submenu.bl_idname,
        text="Camera",
        **_icon_id("utils_camera", "CAMERA_DATA"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# register / unregister
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (
    HT_OT_SplitCameraCuts,
    HT_MT_utils_camera_submenu,
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
