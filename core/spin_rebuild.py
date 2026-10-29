# ═════════════════════════════════════════════════════════════════════════════
#  DEPENDENCIES
#    math, mathutils           pure maths - NO bpy, so a Text Editor
#                              standalone can embed this very file
#  Used by tools/Utils_Misc.py (Delete Rotation Spins, the BAKED SPINS pass).
#  Added in 1.22.0.
# ═════════════════════════════════════════════════════════════════════════════
"""
spin_rebuild - a rotation that goes the long way round ACROSS SEVERAL BAKED
FRAMES, put back on the short way.

You, 2026-10-16, on CSDeals Scene3 and the camera selected in Pose Mode: "I
need to remove that goofy euler spin from it, and our current euler cleaner
doesn't appear to fix that."

WHAT IT WAS
-----------
wood_planks4_rig > bone `camera`, one key on every frame. Frames 455 and 465
are 2 degrees apart. The keys between them turn the camera a full 360 on the
way: 0.27, 0.44, 0.89, 2.7, 173, 176, 2.7, 0.89, 0.44, 0.27 degrees per frame.
That is the shape of a BLEND OF QUATERNION NUMBERS between two samples that
SFM wrote with opposite signs (q and -q are one orientation): the numbers pass
through zero halfway, the turn piles up in the middle two frames and creeps in
at the ends. The camera really points backwards on frame 460.

WHY THE OTHER PASSES COULD NOT SEE IT
------------------------------------
Every other pass of Delete Rotation Spins changes HOW a pose is written (a
sign, a gimbal twin, a whole turn) and never the pose. Here the POSES are
wrong, so no rewriting of them can help:
  quaternion sign flip   the curves are Euler (the import ends on Euler)
  euler gimbal flip      the twin of frame 460 is no nearer frame 459
  euler wrap             no single channel jumps more than 177 per key; the
                         300 threshold never fires (and 180 would not either)
  one-frame camera flip  fixes frame 460 alone: the creep on 456-459 and
                         461-464 stays (4 degrees each way), and frame 461
                         is left a whole Euler turn from the repaired 460,
                         a spin the wrap pass has already run past
Blender's own Discontinuity (Euler) Filter is a representation fix as well,
and finds nothing.

WHAT THIS DOES
--------------
  1  walk          every key on the side of the one before (q, not -q)
  2  spikes        a key that turns at least SPIKE_DEG from the one before,
                   per frame, with keys at most MAX_GAP frames apart (a
                   spin between sparse keys is the wrap pass's job). An
                   EVENT only: at most MAX_SPIKE_STEPS fast keys, and the
                   keys around it turning slower than STAND_OUT of it - a
                   fan spinning on every frame is left alone
  3  window        from the spikes outward, frame by frame, while a key's
                   turn differs from the motion further out by more than
                   TOL_DEG (or TOL_RATIO of that motion) - the creep at the
                   ends - then PAD more frames each side, MAX_WINDOW at most
  4  is it a spin  the window must travel at least MIN_EXCESS_DEG further
                   than its two ends are apart. A real snap turns as far
                   as it ends up turned and is left alone; so is a cut
                   (the position jumps on the spike, CUT_RATIO x its usual
                   step) and any frame stamped in ht_cut_frames
  5  rebuild       the frames inside the window go along the SHORT arc
                   between its two ends. SMOOTH: a cubic that leaves each
                   end at the speed the camera had there (no hitch on a
                   drifting camera). LINEAR: constant speed (a plain slerp).
                   A window that did not grow (one frame turned the long
                   way, exact keys either side) always gets its neighbours'
                   slerp and no PAD - the One-Frame Camera Flips repair,
                   so its neighbours stay exactly as they were.

The two end keys never change; nothing outside the window changes its pose.
"""

import math

from mathutils import Matrix, Quaternion, Vector

SPIKE_DEG = 45.0         # deg per frame: a turn this fast between keys is a spike
                         # (1350 deg/s at 30 fps - no camera move does that)
MAX_GAP = 2.0001         # keys further apart than this (frames) are not baked
TOL_DEG = 0.02           # deg per frame: a key's turn this close to the motion
                         # further out is clean
TOL_RATIO = 0.25         # ...or this share of that motion's speed
BASE_KEYS = 5            # how many steps further out make "the motion there"
TANGENT_KEYS = 2         # steps averaged for the speed at each end (SMOOTH)
PAD = 1                  # frames rebuilt beyond the detected creep, each side
MAX_WINDOW = 48          # frames: the search stops growing a window here
MIN_EXCESS_DEG = 90.0    # path minus chord: less than this is real motion
CUT_RATIO = 4.0          # position step on a spike / usual step: above = a cut
MERGE_STEPS = 3          # spikes this close are one spin
MAX_SPIKE_STEPS = 3      # more fast keys than this in one spin = a real fast turn
STAND_OUT = 0.25         # the keys around a spike must turn slower than this share of it


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
    """-q: the SAME orientation."""
    return Quaternion((-q[0], -q[1], -q[2], -q[3]))


def angle_deg(a, b):
    """The true turn between two orientations, 0..180 degrees.
    4 * atan2(|a - b|, |a + b|): exact at both ends (camera_resample.angle_deg)."""
    s = 1.0 if a.dot(b) >= 0.0 else -1.0
    ma, mb = max(a.magnitude, 1e-12), max(b.magnitude, 1e-12)
    d = math.sqrt(sum((x / ma - s * y / mb) ** 2 for x, y in zip(a, b)))
    p = math.sqrt(sum((x / ma + s * y / mb) ** 2 for x, y in zip(a, b)))
    return math.degrees(4.0 * math.atan2(d, p))


def walk(quats):
    """Every quaternion on the side of the one before it (copies)."""
    out, prev = [], None
    for q in quats:
        q = quat(q)
        if prev is not None and prev.dot(q) < 0.0:
            q = neg(q)
        out.append(q)
        prev = q
    return out


def log_vec(q):
    """Unit quaternion -> rotation vector (axis * angle, radians), short way."""
    w, x, y, z = q[0], q[1], q[2], q[3]
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    s = math.sqrt(x * x + y * y + z * z)
    if s < 1e-12:
        return Vector((0.0, 0.0, 0.0))
    k = 2.0 * math.atan2(s, w) / s
    return Vector((x * k, y * k, z * k))


def exp_vec(v):
    """Rotation vector -> unit quaternion."""
    ang = v.length
    if ang < 1e-12:
        return Quaternion((1.0, 0.0, 0.0, 0.0))
    s = math.sin(0.5 * ang) / ang
    return Quaternion((math.cos(0.5 * ang), v.x * s, v.y * s, v.z * s))


def _skew(v):
    return Matrix(((0.0, -v.z, v.y), (v.z, 0.0, -v.x), (-v.y, v.x, 0.0)))


def _jr_inv(p):
    """Inverse right Jacobian of SO(3) at rotation vector p: turns a body
    angular velocity at exp(p) into the rate of p. Identity for small p."""
    th = p.length
    if th < 1e-6:
        return Matrix.Identity(3)
    K = _skew(p)
    c = (1.0 / (th * th)) - (1.0 + math.cos(th)) / (2.0 * th * math.sin(th)) \
        if abs(math.sin(th)) > 1e-9 else 0.0
    return Matrix.Identity(3) + K * 0.5 + (K @ K) * c


def _mean(vecs):
    vecs = [v for v in vecs if v is not None]
    if not vecs:
        return None
    s = Vector((0.0, 0.0, 0.0))
    for v in vecs:
        s += v
    return s / len(vecs)


def step_rates(frames, quats):
    """[None, r1, r2, ...]: r_i = the turn from key i-1 to key i as a rotation
    vector PER FRAME, in key i-1's own frame. `quats` must be walked."""
    rates = [None]
    for i in range(1, len(quats)):
        g = max(float(frames[i]) - float(frames[i - 1]), 1e-9)
        d = quats[i - 1].conjugated() @ quats[i]
        rates.append(log_vec(d) / g)
    return rates


# ──────────────────────────────────────────────────────────────────────────────
#  FIND
# ──────────────────────────────────────────────────────────────────────────────

def _dist(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def find_spins(frames, quats, positions=None, cut_frames=(), frame_range=None,
               spike_deg=SPIKE_DEG, tol_deg=TOL_DEG, tol_ratio=TOL_RATIO,
               base_keys=BASE_KEYS, pad=PAD, max_window=MAX_WINDOW,
               min_excess_deg=MIN_EXCESS_DEG, cut_ratio=CUT_RATIO,
               max_gap=MAX_GAP, max_spike_steps=MAX_SPIKE_STEPS,
               stand_out=STAND_OUT):
    """frames [f, ...] sorted, quats [Quaternion, ...] (any signs) and optional
    positions {frame: (x, y, z)} -> {"spins": [...], "left": [...]}.

    A spin: {"a": index, "b": index (the two end keys, kept), "frames":
    (fa, fb), "spike_frames": [...], "path": deg travelled, "chord": deg
    between the ends, "worst": biggest one-frame turn, "capped": bool}.
    "left" lists spikes NOT treated, each with its reason (a cut, real
    motion), so the report can say why."""
    out = {"spins": [], "left": []}
    n = len(quats)
    if n < 3 or len(frames) != n:
        return out
    Q = walk(quats)
    R = step_rates(frames, Q)
    deg = [0.0] + [math.degrees(R[i].length) for i in range(1, n)]

    def baked(i):                       # step i: key i-1 -> key i
        return float(frames[i]) - float(frames[i - 1]) <= max_gap

    def in_range(i):
        if frame_range is None:
            return True
        lo, hi = frame_range
        return float(frames[i]) >= lo and float(frames[i - 1]) <= hi

    spikes = [i for i in range(1, n) if baked(i) and deg[i] >= spike_deg and in_range(i)]
    if not spikes:
        return out

    clusters = [[spikes[0]]]
    for i in spikes[1:]:
        if i - clusters[-1][-1] <= MERGE_STEPS:
            clusters[-1].append(i)
        else:
            clusters.append([i])

    step_len = None
    if positions:
        moves = sorted(_dist(positions[frames[i - 1]], positions[frames[i]])
                       for i in range(1, n)
                       if frames[i - 1] in positions and frames[i] in positions)
        step_len = moves[len(moves) // 2] if moves else 0.0
    cut_set = [float(c) for c in (cut_frames or ())]

    def clean(i, ref):
        if ref is None:
            return True
        dev = math.degrees((R[i] - ref).length)
        return dev <= max(tol_deg, tol_ratio * math.degrees(ref.length))

    for cl in clusters:
        s, e = cl[0], cl[-1]
        spike_frames = [float(frames[i]) for i in cl]
        worst = max(deg[i] for i in cl)

        # a baked spin is an EVENT: one or two keys whip round while the
        # motion either side is slow. Many fast keys in a row is a real fast
        # turn (a fan, a wheel); no keys around it means it cannot be told
        # apart from one (a 4-key hand-made wrap test, suite 9).
        if len(cl) > max_spike_steps:
            out["left"].append({"frames": spike_frames, "worst": worst,
                                "why": "a sustained fast turn over %d keys (real motion)" % len(cl)})
            continue
        around = [deg[k] for k in range(max(1, s - base_keys), s) if baked(k)] + \
                 [deg[k] for k in range(e + 1, min(n, e + 1 + base_keys)) if baked(k)]
        if not around:
            out["left"].append({"frames": spike_frames, "worst": worst,
                                "why": "too few keys around it to tell a spin from motion"})
            continue
        around.sort()
        if around[len(around) // 2] > stand_out * worst:
            out["left"].append({"frames": spike_frames, "worst": worst,
                                "why": "the motion around it is fast too (real motion)"})
            continue

        # a cut: the camera jumped too, or the importer stamped one here
        if any(abs(sf - c) <= 1.0001 or abs(float(frames[i - 1]) - c) <= 1.0001
               for i, sf in zip(cl, spike_frames) for c in cut_set):
            out["left"].append({"frames": spike_frames, "worst": worst,
                                "why": "a cut stamped by the importer"})
            continue
        if positions and step_len is not None:
            jumped = False
            for i in cl:
                fa, fb = frames[i - 1], frames[i]
                if fa in positions and fb in positions:
                    if _dist(positions[fa], positions[fb]) > cut_ratio * step_len + 1e-6:
                        jumped = True
            if jumped:
                out["left"].append({"frames": spike_frames, "worst": worst,
                                    "why": "the position jumps too (a cut)"})
                continue

        # grow the window over the creep at both ends
        capped = False
        a = s - 1
        while a > 0 and baked(a):
            ref = _mean([R[k] for k in range(max(1, a - base_keys), a) if baked(k)])
            if ref is None or clean(a, ref):
                break
            a -= 1
            if float(frames[s]) - float(frames[a]) > max_window:
                capped = True
                break
        b = e
        while b < n - 1 and baked(b + 1):
            ref = _mean([R[k] for k in range(b + 2, min(n, b + 2 + base_keys)) if baked(k)])
            if ref is None or clean(b + 1, ref):
                break
            b += 1
            if float(frames[b]) - float(frames[e]) > max_window:
                capped = True
                break
        #  PAD only where creep was found: a single frame turned the long way
        #  with exact keys either side keeps those keys (the One-Frame Camera
        #  Flips case - its neighbours are true samples).
        grown = a < s - 1 or b > e
        if a < s - 1:
            a = max(0, a - pad)
        if b > e:
            b = min(n - 1, b + pad)

        path = sum(deg[i] * (float(frames[i]) - float(frames[i - 1])) for i in range(a + 1, b + 1))
        chord = angle_deg(Q[a], Q[b])
        if path - chord < min_excess_deg:
            out["left"].append({"frames": spike_frames, "worst": worst,
                                "why": "real motion (turns %.0f, ends %.0f apart)" % (path, chord)})
            continue
        # two spins grown into each other: merge with the one before
        if out["spins"] and a <= out["spins"][-1]["b"]:
            prev = out["spins"].pop()
            a = prev["a"]
            spike_frames = prev["spike_frames"] + spike_frames
            worst = max(worst, prev["worst"])
            capped = capped or prev["capped"]
            grown = True
            path = sum(deg[i] * (float(frames[i]) - float(frames[i - 1])) for i in range(a + 1, b + 1))
            chord = angle_deg(Q[a], Q[b])
        out["spins"].append({"a": a, "b": b, "frames": (float(frames[a]), float(frames[b])),
                             "spike_frames": spike_frames, "path": path, "chord": chord,
                             "worst": worst, "capped": capped, "grown": grown})
    return out


# ──────────────────────────────────────────────────────────────────────────────
#  REBUILD
# ──────────────────────────────────────────────────────────────────────────────

def rebuild(frames, quats, a, b, interp="SMOOTH", tangent_keys=TANGENT_KEYS,
            max_gap=MAX_GAP):
    """The keys strictly between a and b, rebuilt along the short arc:
    [(index, Quaternion)]. Keys a and b are the ends and do not change.

    SMOOTH leaves key a at the speed the motion had arriving there and
    reaches key b at the speed it leaves with (a cubic on the rotation
    vector, exact at both ends). LINEAR is a constant-speed slerp."""
    n = len(quats)
    Q = walk(quats)
    qa = Q[a]
    qb = Q[b] if qa.dot(Q[b]) >= 0.0 else neg(Q[b])
    F = float(frames[b]) - float(frames[a])
    if F <= 0.0 or b - a < 2:
        return []
    p1 = log_vec(qa.conjugated() @ qb)

    m0 = m1 = None
    if interp == "SMOOTH":
        R = step_rates(frames, Q)
        m0 = _mean([R[k] for k in range(max(1, a - tangent_keys + 1), a + 1)
                    if float(frames[k]) - float(frames[k - 1]) <= max_gap])
        out_rates = [R[k] for k in range(b + 1, min(n, b + 1 + tangent_keys))
                     if float(frames[k]) - float(frames[k - 1]) <= max_gap]
        m1 = _mean(out_rates)
        if m1 is not None:
            m1 = _jr_inv(p1) @ m1
    if m0 is None:
        m0 = p1 / F
    if m1 is None:
        m1 = p1 / F

    out = []
    for i in range(a + 1, b):
        t = (float(frames[i]) - float(frames[a])) / F
        if interp == "SMOOTH":
            t2, t3 = t * t, t * t * t
            v = m0 * ((t3 - 2.0 * t2 + t) * F) + p1 * (-2.0 * t3 + 3.0 * t2) \
                + m1 * ((t3 - t2) * F)
        else:
            v = p1 * t
        q = qa @ exp_vec(v)
        q.normalize()
        out.append((i, q))
    return out
