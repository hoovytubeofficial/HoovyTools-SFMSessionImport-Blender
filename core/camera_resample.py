# ═════════════════════════════════════════════════════════════════════════════
#  DEPENDENCIES
#    math, mathutils           pure maths - NO bpy, so the Text Editor
#                              standalone can embed this very file
#  Used by importers/Import_DMX_Camera.py (session cameras and File > Import),
#  importers/Light_Import.py (light orientation keys), tools/Euler_Output.py
#  (a camera's Euler order, cut keys kept as steps), tools/Utils_Misc.py
#  (Delete Rotation Spins repairs one-frame camera flips) and the standalone
#  ___Architecture/DMX Animation - Camera, which Shared/bundle_standalone.py
#  builds with THIS file inside it. Added in 1.17.3.
# ═════════════════════════════════════════════════════════════════════════════
"""
camera_resample - SFM camera samples onto whole frames, with no flips.

THE CAUSE
---------
A session camera is imported on the stepped path: one key on every whole
frame, each one interpolated between the two SFM samples around it. 1.17.2
did that by blending the four quaternion NUMBERS (w, x, y, z) and only THEN
ran the sign fix. SFM may write a sample as -q, which is the same orientation
as q. Blend q and -q and the numbers pass through zero: the frame halfway
between two samples 8 degrees apart came out 180 DEGREES off - a one-frame
flip, baked into the key. The sign fix that ran afterwards cannot repair it,
because it only negates keys (that never changes a pose) and that frame's
pose is already wrong. The Euler step then converts the wrong frame
faithfully. The bone importer always knew this ("the flip fix MUST run
first", Import_DMX_Animation.fix_action_quat_flips); the camera did not.

It is "odd" rather than constant because it needs a sign change between two
samples more than a frame apart, and a whole frame landing in between - but
the import formula puts a level camera facing SFM yaw 0 right on the sign
boundary, so a pan across that heading is enough.

THE FIX, IN ORDER
-----------------
  1  hemisphere_walk   every SFM sample on the side of the one before it
  2  slerp             the in-between frames turn along the real path
  3  cut pairs         SFM writes a hard cut as two samples one tick apart
                       (0.0001 s). A frame never blends INSIDE a pair - it
                       takes the nearer sample - and the last frame before
                       the cut is keyed CONSTANT, so the cut is a cut: no
                       one-frame whip of the whole turn in motion blur, in a
                       scrub, or in the Euler graph. ONLY there: an earlier
                       version held EVERY key and smooth pans became a
                       staircase (the note in Import_DMX_Camera says so).
  4  the keys are walked once more (a cut snaps between two samples)

Also here, because everything that touches a camera should agree:
  one_frame_flips      find a frame turned far from BOTH neighbours while the
                       neighbours agree and the position runs straight
                       through - what 1.17.2 baked into old scenes
  best_euler_order     XYZ unless a camera comes within GIMBAL_GUARD_DEG of
                       XYZ's lock (a 90 degree Dutch roll)
  component_lerp_1172  the old resample, kept ONLY to show what changed
"""

import math

from mathutils import Quaternion

CUT_GAP = 0.05             # frames: closer than this, two samples are a cut pair
CUT_TURN_DEG = 0.01        # a close pair that turns less is not a cut
CUT_MOVE = 1e-6            # ...or that moves less (scene units)
CUT_VALUE = 1e-6           # ...or whose lens / aperture / focus changes less
SPIKE_MIN_DEG = 30.0       # a one-frame flip turns at least this far from both neighbours
SPIKE_RATIO = 0.25         # ...while the neighbours agree within this share of it
GIMBAL_GUARD_DEG = 10.0    # an Euler order closer than this to its lock is not used
ORDERS = ("XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX")


# ──────────────────────────────────────────────────────────────────────────────
#  SMALL PIECES
# ──────────────────────────────────────────────────────────────────────────────

def quat(v):
    """(w, x, y, z) -> a normalised Quaternion (always a copy)."""
    q = Quaternion(tuple(float(c) for c in v))
    if q.magnitude > 1e-12:
        q.normalize()
    return q


def neg(q):
    """-q: every number negated. The SAME orientation."""
    return Quaternion((-q[0], -q[1], -q[2], -q[3]))


def angle_deg(a, b):
    """The true turn between two orientations in degrees, 0..180. q and -q
    are one orientation, so the sign of either never matters.

    4 * atan2(|a - b|, |a + b|), NOT 2 * acos(|a . b|): acos is flat at 1,
    so float rounding in the dot read two IDENTICAL orientations as 0.04
    degrees apart (mathutils keeps 32-bit floats). This form is exact at
    both ends."""
    s = 1.0 if a.dot(b) >= 0.0 else -1.0
    ma, mb = max(a.magnitude, 1e-12), max(b.magnitude, 1e-12)
    d = math.sqrt(sum((x / ma - s * y / mb) ** 2 for x, y in zip(a, b)))
    p = math.sqrt(sum((x / ma + s * y / mb) ** 2 for x, y in zip(a, b)))
    return math.degrees(4.0 * math.atan2(d, p))


def _dist(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _lerp(a, b, t):
    if isinstance(a, (tuple, list)):
        return tuple(float(x) + (float(y) - float(x)) * t for x, y in zip(a, b))
    return float(a) + (float(b) - float(a)) * t


# ──────────────────────────────────────────────────────────────────────────────
#  1  THE HEMISPHERE WALK
# ──────────────────────────────────────────────────────────────────────────────

def hemisphere_walk(samples):
    """[(frame, q)] sorted by frame -> ([(frame, Quaternion)], negated count).

    Each quaternion is put on the side of the one before it. Negating is the
    same orientation, so no pose moves - only the in-between stops going
    round the back. MUST run before anything blends two samples."""
    out, flips, prev = [], 0, None
    for f, q in samples:
        q = quat(q)
        if prev is not None and prev.dot(q) < 0.0:
            q = neg(q)
            flips += 1
        out.append((float(f), q))
        prev = q
    return out, flips


# ──────────────────────────────────────────────────────────────────────────────
#  2 + 3  ONE VALUE PER WHOLE FRAME, CUTS KEPT AS CUTS
# ──────────────────────────────────────────────────────────────────────────────

def _cut_test(samples, distance, threshold):
    def cut(i):
        (f0, v0), (f1, v1) = samples[i], samples[i + 1]
        return (f1 - f0) < CUT_GAP and distance(v0, v1) > threshold
    return cut


def _resample(samples, blend, cut):
    """The 1.17.2 loop - a value on every whole frame from floor(first) to
    ceil(last), interpolated between the samples that bracket it - except that
    a cut pair never blends: a frame inside one takes the nearer sample."""
    if not samples:
        return []
    f_lo = int(math.floor(samples[0][0]))
    f_hi = int(math.ceil(samples[-1][0]))
    n = len(samples)
    si = 0
    out = []
    for frame in range(f_lo, f_hi + 1):
        while si < n and samples[si][0] < frame:
            si += 1
        if si == 0:
            v = samples[0][1]
        elif si >= n:
            v = samples[-1][1]
        else:
            f0, v0 = samples[si - 1]
            f1, v1 = samples[si]
            if f1 == f0:
                v = v1
            elif cut(si - 1):
                v = v0 if (frame - f0) < (f1 - frame) else v1
            else:
                v = blend(v0, v1, (frame - f0) / (f1 - f0))
        out.append((frame, v))
    return out


def cut_frames(samples, cut):
    """{whole frame} whose key must be CONSTANT: the last frame that still
    shows the shot before each cut pair (and that has a frame after it)."""
    if len(samples) < 2:
        return set()
    f_hi = int(math.ceil(samples[-1][0]))
    out = set()
    for i in range(len(samples) - 1):
        if not cut(i):
            continue
        f0, f1 = samples[i][0], samples[i + 1][0]
        pre = int(math.floor(f0 + 1e-9))
        inside = pre + 1
        if f0 < inside < f1 and (inside - f0) < (f1 - inside):
            pre = inside                       # the frame inside takes f0's side
        if pre + 1 <= f_hi:
            out.add(pre)
    return out


def resample_rotation(samples):
    """SFM orientation samples [(frame, (w, x, y, z))] -> keys + facts.

    Returns ([(frame, (w, x, y, z))] on every whole frame, {"flips": samples
    negated by the walk, "cuts": set of CONSTANT frames}). Walk, slerp, keep
    cuts, walk the keys - see the module notes for why each step."""
    s = sorted(((float(f), q) for f, q in samples), key=lambda x: x[0])
    s, flips = hemisphere_walk(s)
    cut = _cut_test(s, angle_deg, CUT_TURN_DEG)
    keys = _resample(s, lambda a, b, t: a.slerp(b, t), cut)
    keys, _again = hemisphere_walk(keys)
    return ([(int(f), (q[0], q[1], q[2], q[3])) for f, q in keys],
            {"flips": flips, "cuts": cut_frames(s, cut)})


def resample_values(samples, threshold=None):
    """Position / lens / aperture / focus samples [(frame, value or tuple)] ->
    ([(frame, value)], {"cuts": set of CONSTANT frames}). Linear between
    samples exactly as 1.17.2, except at a cut pair."""
    s = sorted(((float(f), v) for f, v in samples), key=lambda x: x[0])
    if not s:
        return [], {"cuts": set()}
    vec = isinstance(s[0][1], (tuple, list))
    dist = _dist if vec else (lambda a, b: abs(float(a) - float(b)))
    thr = (CUT_MOVE if vec else CUT_VALUE) if threshold is None else threshold
    cut = _cut_test(s, dist, thr)
    return _resample(s, _lerp, cut), {"cuts": cut_frames(s, cut)}


# ──────────────────────────────────────────────────────────────────────────────
#  WHAT 1.17.2 DID - kept ONLY so a report can show what changed
# ──────────────────────────────────────────────────────────────────────────────

def component_lerp_1172(samples):
    """The 1.17.2 stepped resample of an orientation: the four numbers blended
    as they came, no walk, no cut rule. [(frame, Quaternion normalised)]."""
    s = sorted(((float(f), tuple(float(c) for c in q)) for f, q in samples),
               key=lambda x: x[0])
    keys = _resample(s, lambda a, b, t: tuple(x + (y - x) * t for x, y in zip(a, b)),
                     lambda i: False)
    return [(f, quat(v)) for f, v in keys]


# ──────────────────────────────────────────────────────────────────────────────
#  ONE-FRAME FLIPS ALREADY IN A SCENE
# ──────────────────────────────────────────────────────────────────────────────

def one_frame_flips(keys, positions=None, min_deg=SPIKE_MIN_DEG, ratio=SPIKE_RATIO):
    """[(frame, Quaternion)] on consecutive whole frames (+ optional
    {frame: (x, y, z)}) -> [(index, frame, degrees off)].

    A flip: the frame turned at least `min_deg` away from BOTH neighbours,
    the neighbours agree within `ratio` of that, and - when positions are
    given - the position runs straight through. A real one-frame shot jumps
    in position as well, so it is never called a flip."""
    out = []
    if len(keys) < 3:
        return out
    step = None
    if positions:
        moves = sorted(_dist(positions[keys[i][0]], positions[keys[i + 1][0]])
                       for i in range(len(keys) - 1)
                       if keys[i][0] in positions and keys[i + 1][0] in positions)
        step = moves[len(moves) // 2] if moves else 0.0
    for i in range(1, len(keys) - 1):
        (fa, qa), (fb, qb), (fc, qc) = keys[i - 1], keys[i], keys[i + 1]
        if fc - fa > 2.0001:
            continue
        a, b, c = angle_deg(qa, qb), angle_deg(qb, qc), angle_deg(qa, qc)
        if min(a, b) < min_deg or c > ratio * min(a, b):
            continue
        if positions and all(f in positions for f in (fa, fb, fc)):
            mid = _lerp(positions[fa], positions[fc], (fb - fa) / max(fc - fa, 1e-9))
            dev = _dist(positions[fb], mid)
            if dev > max(_dist(positions[fa], positions[fc]), 3.0 * step, 1e-4):
                continue                       # it moved too: a real cut
        out.append((i, fb, min(a, b)))
    return out


def repaired(keys, index):
    """The orientation a flipped key should have had: its neighbours slerped."""
    (fa, qa), (fb, _qb), (fc, qc) = keys[index - 1], keys[index], keys[index + 1]
    if qa.dot(qc) < 0.0:
        qc = neg(qc)
    return qa.slerp(qc, (fb - fa) / max(fc - fa, 1e-9))


# ──────────────────────────────────────────────────────────────────────────────
#  THE EULER ORDER OF A CAMERA
# ──────────────────────────────────────────────────────────────────────────────

def lock_margin_deg(quats, order):
    """How close an Euler order comes to its gimbal lock over these
    orientations: 90 minus the largest |middle angle|, in degrees."""
    worst = 90.0
    k = "XYZ".index(order[1])
    for q in quats:
        m = abs(math.degrees(q.to_euler(order)[k]))
        m = 180.0 - m if m > 90.0 else m
        worst = min(worst, 90.0 - m)
    return worst


def best_euler_order(quats, prefer="XYZ", guard=GIMBAL_GUARD_DEG):
    """(order, {order: margin}). `prefer` unless it comes within `guard`
    degrees of its lock somewhere; then the order with the most room."""
    quats = list(quats)
    margins = {prefer: lock_margin_deg(quats, prefer)}
    if margins[prefer] >= guard or not quats:
        return prefer, margins
    for o in ORDERS:
        if o not in margins:
            margins[o] = lock_margin_deg(quats, o)
    best = max(ORDERS, key=lambda o: (margins[o], o == prefer))
    return best, margins
