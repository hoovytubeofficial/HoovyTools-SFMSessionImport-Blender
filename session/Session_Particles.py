"""
Session_Particles.py  -  part of HoovyTools
===========================================

Step 8: bring the session's particle effects in, through the HoovyTools
Particle Import add-on.

WHAT A SESSION STORES
=====================
Probed from `new session.dmx`, 2026-08-21. One element type carries it:

    DmeGameParticleSystem
        particleSystemType   "AA__Gasoline-Fire_A_100CM"   the EFFECT NAME
        transform            DmeTransform -> where it sits
        controlPoints        [ controlPoint0, ... ]  each with its own dag
        emitting  visible  simulating      booleans, and they are KEYED
        randomSeed           int
        simulationTimeScale  float

Note what is NOT there: the effect itself. `particleSystemDefinition` is
None, so the session names an effect and expects the game to find it. The
definition lives in a .pcf under `usermod/particles`, which is exactly what
HoovyToolsParticleImport reads - so this module resolves the name to a file
and hands the job over.

WHY IT GOES THROUGH api.py
==========================
The particle add-on exposes a deliberate integration surface for this:

    api = siblings.submodule("particles", "api")
    api.list_systems(pcf)  ->  what definitions a .pcf holds
    api.build_effect(...)  ->  build one, return the created objects

Its own docstring names HoovyTools as the caller. Reaching around it into
the operators would couple two add-ons through code that is explicitly
allowed to change; everything here goes through api.

SCALE AND PLACEMENT
===================
Position is mapped with the session world map, `(x, y, z) -> (y, -x, z)`,
the same one the camera, the lights and the character root transforms use.
Get that wrong and the fire burns somewhere the characters are not.

A PARTICLE TRANSFORM IS LOCAL TO ITS PARENT DAG - AND ONLY PARTICLES ARE
=======================================================================
Everything else in a session hangs off a parent sitting at the origin, so
reading an element's own transform and calling it the world position worked
by luck for lights, cameras and characters alike. Particle systems do not:

    light1    parent 'Lights'  DmeDag at (0, 0, 0)
    camera3   parent 'Cameras' DmeDag at (0, 0, 0)
    scout1    parent 'scout1'  DmeDag at (0, 0, 0)
    fire1     parent DmeDag at (84.7385, -2.4922, 49.0953)      <-- not zero

So the placement is `parent_matrix(elem) @ own_transform`, THEN the world map.
Measured: both fires were landing at z = -47.7, about 47 units underground
(scout stands at z = 0), and compose to z = 1.378, which is ground level.

WHAT MOVES, AND WHERE ITS KEYS LIVE
===================================
Two separate things animate, and for a while only one of them was read:

    TRANSFORM       the effect's own DmeTransform. Channels `transform_pos`
                    and `transform_rot` - the same arrangement a LIGHT uses.
                    Keyed onto the effect ROOT, so the whole tree follows.
    CONTROLPOINT<n> a DmeTransform per control point, holding a LOCAL offset
                    from the effect origin. Channels `controlPoint<n>_pos`
                    and `_rot`. Keyed onto the `. CP<n>` empties.

`AA__Beam-Thor_A_25CM1` in `new session.dmx` is the case that exposed the
gap - TRANSFORM, CONTROLPOINT0 and CONTROLPOINT1, of which only the control
points were being animated. Times in both are ABSOLUTE SECONDS, so the frame
is `t * fps`, not `(t + start) * fps`.

ONE OBJECT PER SYSTEM, NOT PER INSTANCE
=======================================
HoovyToolsParticleImport names what it builds after the particle SYSTEM. Two
instances of the same effect in one session therefore come back sharing one
root and one set of control-point empties, and whichever is placed second
overwrites the first. `ht_effect_owner` / `ht_cp_owner` are stamped so the
second instance reports it and stands aside instead. The proper fix is
per-instance naming in that add-on.
"""

import bpy
import math
from pathlib import Path
from mathutils import Matrix, Quaternion, Vector

from bpy.types import Operator

from ..core import Progress
from bpy.props import (BoolProperty, EnumProperty, FloatProperty,
                       StringProperty)


COLLECTION = "___HoovyTools Particles___"
COLLECTION_COLOR = "COLOR_01"      # red

PARTICLE_TYPES = ("DmeGameParticleSystem",)


# ─────────────────────────────────────────────────────────────────────────────
#  The other add-on
# ─────────────────────────────────────────────────────────────────────────────

def particle_api():
    """The Particle Import add-on's stable API, or None with a reason."""
    #  THE NAME IS NOT ONE NAME. core.siblings knows every folder this
    #  add-on has shipped under - the current hyphenated one, the old
    #  run-together one, and the "-main" that GitHub's zip unpacks to - and
    #  a hyphenated name cannot be reached with `from X import y` at all.
    try:
        from ..core import siblings
        import addon_utils
        for name in siblings.names("particles"):
            try:
                if not addon_utils.check(name)[1]:
                    addon_utils.enable(name, default_set=False)
            except Exception:
                pass
        api = siblings.submodule("particles", "api")
        if api is not None:
            return api, ""
        return None, ("Source Particle Import is not available. Install and "
                      "enable the Source Particle Import add-on "
                      "(HoovyTools-ParticleImport-Blender).")
    except Exception as exc:
        return None, (f"Source Particle Import is not available ({exc}). "
                      f"Install and enable the Source Particle Import add-on "
                      f"(HoovyTools-ParticleImport-Blender).")


def particle_dirs():
    """Folders to search for .pcf files, best first."""
    out = []
    #  THE CONFIG LEADS, AHEAD OF THE PARTICLE ADD-ON'S OWN FOLDER.
    #  `_startupconfig.json` resolves to usermod/particles, which is the same
    #  answer that add-on gives, so on a normal install the order does not
    #  matter. It matters the moment somebody writes a path into
    #  `customizedconfig.json` - a shared library on a network drive, say -
    #  because a preference stated by hand has to beat one inferred by another
    #  add-on, or stating it does nothing.
    try:
        from ..core import config as _config
        from . import Import_Session as _IS
        for p in _config.folders("particles", _IS.usermod_bases(),
                                 _IS._DEFAULT_SFM_USERMOD):
            if p not in out:
                out.append(p)
    except Exception:
        pass

    try:
        from ..core import siblings
        paths = siblings.submodule("particles", "paths")
        d = paths.subdir("particles") if paths else None
        if d and Path(d) not in out:
            out.append(Path(d))
    except Exception:
        pass

    try:
        from . import Import_Session
        from ..core import paths as _paths
        #  EVERY mount under game/ of EVERY configured install, not the four
        #  mod names that were hardcoded here.
        #  usermod comes back first from mod_dirs, so the priority order is
        #  unchanged and this can only add folders. A Workshop effect lives in
        #  `game/workshop/particles` - that one WAS on the old list, but
        #  `ep2_workshop`, `left4dead2_movies` and whatever else an install
        #  has picked up were not, and no list of names could have known.
        for base in Import_Session.usermod_bases():
            for mount in _paths.mod_dirs(base):
                p = mount / "particles"
                if p.is_dir() and p not in out:
                    out.append(p)
    except Exception:
        pass
    return [p for p in out if p.is_dir()]


def _index_pcfs(api, dirs, wanted=None, report=print):
    """
    {system name -> .pcf path} across the particle folders.

    STOPS AS SOON AS EVERY WANTED NAME IS FOUND. a real particles tree
    is 3,986 .pcf files holding 18,369 systems; parsing all of it to place
    two fires is a minute of work for nothing. A session usually names a
    handful of effects, so the scan is bounded by the search, not the library.

    A .pcf that will not parse is reported and skipped rather than aborting -
    one bad file in a mod folder must not cost the user every effect in the
    session. (Nine in the user's tree are unreadable: bad DMX headers and
    one path over Windows MAX_PATH.)
    """
    index = {}
    need = set(wanted or ())
    scanned = failed = 0
    for d in dirs:
        for pcf in sorted(d.rglob("*.pcf")):
            scanned += 1
            try:
                names = api.list_systems(str(pcf))
            except Exception as exc:
                failed += 1
                report(f"[PARTICLES]  unreadable {pcf.name}: {exc}")
                continue
            for n in names.get("order") or []:
                index.setdefault(n, pcf)
                need.discard(n)
            if wanted and not need:
                report(f"[PARTICLES]  found every system after {scanned} "
                       f"file(s) - stopping the search")
                return index
    report(f"[PARTICLES]  indexed {len(index)} system(s) from {scanned} .pcf "
           f"file(s)" + (f", {failed} unreadable" if failed else ""))
    return index


# ─────────────────────────────────────────────────────────────────────────────
#  Reading the session
# ─────────────────────────────────────────────────────────────────────────────

def sfm_position(v, scale=1.0):
    """SFM (x, y, z) -> Blender (y, -x, z). The session world map."""
    return Vector((float(v[1]), -float(v[0]), float(v[2]))) * scale


def world_position(v, parent_mat, scale=1.0):
    """A LOCAL SFM position -> a Blender world location.

    Two steps, in this order and no other:
      1. lift the local offset into SFM world space through the parent chain
         (see parent_matrix - particles are the one element type where this
         is not the identity);
      2. apply the one world map, (x, y, z) -> (y, -x, z).
    Doing it the other way round maps the parent's offset a second time."""
    local = Vector((float(v[0]), float(v[1]), float(v[2])))
    return sfm_position(parent_mat @ local, scale)


#  The world map as a rotation. (x, y, z) -> (y, -x, z) is Rz(-90).
WORLD_ROT = Matrix.Rotation(-math.pi / 2.0, 3, 'Z')


def sfm_quaternion(v):
    """DMX (x, y, z, w) -> mathutils Quaternion(w, x, y, z). No mapping."""
    return Quaternion((float(v[3]), float(v[0]), float(v[1]), float(v[2])))


def world_rotation(local_rot, parent_mat):
    """A rotation expressed in SFM space -> the effect root's Blender rotation.

    R_blender = W . R_sfm . W-inverse,  with W = Rz(-90).

    WHY CONJUGATED AND NOT JUST `W . R_sfm`
    ---------------------------------------
    Both forms put the effect in the right place; they differ in what the
    CHILDREN then need, and only one of them matches what this module already
    does to control points.

    Control-point offsets are written through `sfm_position`, i.e. they are
    ALREADY in Blender space by the time they become a local location under
    the root. For a control point to land where SFM puts it, the root's
    rotation has to act on an already-mapped offset:

        truth          : W . (pos + R_sfm . cp)
        what we build  : (W . pos) + R_blender . (W . cp)
        so             : R_blender . W == W . R_sfm
                         R_blender     == W . R_sfm . W-inverse

    `W . R_sfm` would instead require the control points to go in RAW, which
    is the arrangement the CHARACTER rigs use (one axis empty above the whole
    stack). Either is self-consistent; mixing them is not, and mixing them is
    what a half-finished change would produce.

    THE PRACTICAL POINT: with R_sfm identity - which is every particle in
    `new session.dmx` - this returns identity, so nothing about the current
    output changes. It is here so that the first session that DOES rotate an
    effect is right the first time rather than after another round of
    measuring. It has NOT been verified against rotated data yet; when such a
    session exists, check a control point's world position against the
    session's own numbers, not the effect's look."""
    m = (parent_mat.to_3x3() @ local_rot.to_matrix())
    return (WORLD_ROT @ m @ WORLD_ROT.transposed()).to_quaternion()


def dag_parents(model):
    """{id(child) -> parent element} across every DAG in the session.

    Built once per import: the session is one graph and walking it per element
    would be quadratic on a file with 18,000 elements."""
    out = {}
    for e in model.elements:
        try:
            kids = e.get("children")
        except Exception:
            continue
        if not kids:
            continue
        for k in kids:
            if k is not None:
                out.setdefault(id(k), e)
    return out


def _elem_matrix(elem):
    """One DAG node's own transform as a 4x4, in SFM space."""
    try:
        tr = elem.get("transform")
    except Exception:
        return Matrix.Identity(4)
    if tr is None:
        return Matrix.Identity(4)
    pos = tr.get("position")
    rot = tr.get("orientation")
    m = Matrix.Identity(4)
    if rot is not None:
        m = Quaternion((float(rot[3]), float(rot[0]),
                        float(rot[1]), float(rot[2]))).to_matrix().to_4x4()
    if pos is not None:
        m.translation = Vector((float(pos[0]), float(pos[1]), float(pos[2])))
    return m


def parent_matrix(elem, parents):
    """Everything ABOVE *elem* composed into one 4x4, in SFM space.

    THE BUG THIS FIXES - AND WHY IT ONLY EVER SHOWED UP ON PARTICLES
    ---------------------------------------------------------------
    A particle system's `transform` is LOCAL to its parent DAG node, not a
    world placement. Every other kind of element in a session happens to hang
    off a parent sitting at the origin, so reading the local transform and
    calling it the world position worked - and kept working - by luck:

        light1    parent 'Lights'  DmeDag at (0, 0, 0)
        camera3   parent 'Cameras' DmeDag at (0, 0, 0)
        scout1    parent 'scout1'  DmeDag at (0, 0, 0)
        fire1     parent DmeDag at (84.7385, -2.4922, 49.0953)   <-- not zero

    Measured on `new session.dmx`:

        effect  own transform              parent            world
        fire1   141.817 -74.271 -47.718    84.74 -2.49 49.10  226.555 -76.763  1.378
        fire2   164.786  47.675 -47.718    84.74 -2.49 49.10  249.524  45.183  1.378
        thor    248.909  18.741 -38.570   134.18 -51.27 78.41 383.093 -32.527 39.840

    The Z is the giveaway. Both fires were landing at -47.7 - about 47 units
    UNDERGROUND, since scout stands at z = 0 - and compose to 1.378, which is
    ground level. The effect was not slightly off; it was buried.

    Composed as MATRICES, not as a sum of positions, so a parent that carries
    a rotation rotates its child's offset rather than merely displacing it.
    Nothing in the test session rotates, but a sum would be quietly wrong the
    first time something did."""
    chain = []
    cur = parents.get(id(elem))
    seen = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        chain.append(cur)
        cur = parents.get(id(cur))
    m = Matrix.Identity(4)
    for node in reversed(chain):          # scene root first, downwards
        m = m @ _elem_matrix(node)
    return m


def find_particle_systems(model):
    """Every DmeGameParticleSystem in a loaded session, from every shot."""
    return [e for e in model.elements if (e.type or "") in PARTICLE_TYPES]


def shot_particle_systems(shot):
    """The particle systems THIS shot owns - the lights lesson, again. Measured on the Gomez film: 4 systems in the file,
    owned by exactly two shots - one by '(do kaIkuIacji)', three by
    'Suicide attack' - and the whole-file scan built all 4 into every cut.

    BY IDENTITY, TWO ROUTES, UNION OF BOTH: the animation set's own
    reference - the attribute is literally named 'particle system', WITH
    THE SPACE (measured; a camelCase guess finds nothing and reads as
    "this shot has no particles") - and a walk of the shot's scene DAG,
    because a hand-edited session can hold a system no set points at.
    """
    out, seen = [], set()
    for aset in (shot.get("sets") or ()):
        try:
            v = aset.get("particle system")
        except Exception:                                     # noqa: BLE001
            v = None
        if v is not None and (getattr(v, "type", "") or "") in PARTICLE_TYPES \
                and id(v) not in seen:
            seen.add(id(v))
            out.append(v)
    scene = None
    element = shot.get("element")
    if element is not None:
        try:
            scene = element.get("scene")
        except Exception:                                     # noqa: BLE001
            scene = None
    walked = set()

    def walk(dag):
        if dag is None or id(dag) in walked:
            return
        walked.add(id(dag))
        if (getattr(dag, "type", "") or "") in PARTICLE_TYPES:
            if id(dag) not in seen:
                seen.add(id(dag))
                out.append(dag)
            return
        try:
            kids = dag.get("children") or []
        except Exception:                                     # noqa: BLE001
            kids = []
        for kid in kids:
            walk(kid)

    walk(scene)
    return out


def describe(elem, parents=None):
    """What one particle system asks for.

    *parents* is the map from dag_parents(); without it the parent chain is
    treated as identity, which is what the old behaviour was."""
    out = {"name": elem.name or "particle",
           "system": None, "pos": None, "rot": None,
           "transform_elem": None, "elem": elem,
           "parent_matrix": (parent_matrix(elem, parents)
                             if parents else Matrix.Identity(4)),
           "emitting": True, "visible": True, "seed": None,
           "time_scale": 1.0}
    try:
        out["system"] = str(elem.get("particleSystemType") or "") or None
    except Exception:
        pass
    #  THESE TWO ARE A SNAPSHOT AND MUST NOT BE TRUSTED ON THEIR OWN.
    #  `emitting` and `visible` on the element are whatever they happened to be
    #  at the frame the artist left the playhead on - the same class of trap as
    #  a session having no bind pose. Measured in `new session.dmx`: two of the
    #  three effects carry visible=False statically while their CHANNELS say
    #  they are on for hundreds of frames. Hiding from the snapshot is what
    #  made every imported effect invisible.
    #  Kept for reporting only; `_visibility_spans` reads the channels.
    for key, dst in (("emitting", "emitting"), ("visible", "visible")):
        try:
            v = elem.get(key)
            if v is not None:
                out[dst] = bool(v)
        except Exception:
            pass
    out["elem"] = elem
    try:
        s = elem.get("simulationTimeScale")
        if s:
            out["time_scale"] = float(s)
    except Exception:
        pass
    try:
        out["seed"] = int(elem.get("randomSeed"))
    except Exception:
        pass
    # THE TRANSFORM IS AN ELEMENT, AND IT IS ANIMATED.
    #
    # Only its static position/orientation used to be read, so an effect that
    # MOVES arrived parked wherever the session's transform happened to sit.
    # Probed from `new session.dmx`: every DmeGameParticleSystem's transform
    # carries `transform_pos` and `transform_rot` channels - the same names,
    # and the same arrangement, as a LIGHT's transform. AA__Beam-Thor_A_25CM1
    # is the case that showed it: it has TRANSFORM + CONTROLPOINT0 +
    # CONTROLPOINT1, and only the two control points were being animated.
    #
    # The element has to be kept, not just its values, because a channel is
    # found by matching `toElement` identity - see _channel_index.
    tr = elem.get("transform")
    out["transform_elem"] = tr
    if tr is not None:
        p = tr.get("position")
        o = tr.get("orientation")
        if p is not None:
            out["pos"] = [float(x) for x in p]
        if o is not None:
            out["rot"] = [float(x) for x in o]

    # CONTROL POINTS. Source effects are driven by them - a beam runs from
    # CP0 to CP1, a fire tracks whatever CP0 follows - so an effect imported
    # without them is a static prop, not the thing the session showed.
    #
    # They are plain DmeTransforms holding a LOCAL offset from the effect
    # origin: measured against system positions of 140-250 units, the control
    # points sit within about +/-100. So they get the same world map as
    # everything else, applied as a local offset rather than a placement.
    cps = []
    for i, cp in enumerate(elem.get("controlPoints") or []):
        pos = cp.get("position") if cp is not None else None
        cps.append({"index": i, "elem": cp,
                    "pos": [float(x) for x in pos] if pos is not None else None})
    out["control_points"] = cps
    return out


def _channel_index(model):
    """{id(target element) -> [channels]} so a control point can find its own."""
    out = {}
    for e in model.elements:
        if (e.type or "") != "DmeChannel":
            continue
        to = e.get("toElement")
        if to is not None:
            out.setdefault(id(to), []).append(e)
    return out


def _log(ch):
    """(times, values) for a channel, or (None, None)."""
    try:
        lay = ch["log"]["layers"][0]
        t = lay.get("times")
        v = lay.get("values")
        if not t or not v or len(t) != len(v):
            return None, None
        return t, v
    except Exception:
        return None, None


_CP_NAME = None


def _cp_empties(roots, fresh):
    """
    {index -> empty} for one effect's control points.

    The add-on names them `<system> · CP<n>` and parents them under
    `<system> · TRANSFORM`, below the effect's own CONTROL root. They are NOT
    in build_effect's return value, so they have to be found in the scene.

    Searched by HIERARCHY, walking down from this effect's roots, rather than
    by "objects that appeared during this build". Two instances of the same
    system do not necessarily each get their own empty - the add-on reused
    one, so the second fire came back with zero control points when the
    freshly-created set was used instead.
    """
    import re
    pat = re.compile(r"CP(\d+)(?:\.\d+)?$")

    def descend(ob, seen):
        if id(ob) in seen:
            return
        seen.add(id(ob))
        yield ob
        for c in ob.children:
            yield from descend(c, seen)

    out = {}
    seen = set()
    for r in roots:
        for o in descend(r, seen):
            if o.type != 'EMPTY':
                continue
            m = pat.search(o.name)
            if m:
                out.setdefault(int(m.group(1)), o)
    # anything created by this build that the hierarchy walk missed
    for o in fresh:
        if o.type != 'EMPTY':
            continue
        m = pat.search(o.name)
        if m:
            out.setdefault(int(m.group(1)), o)
    return out


def _apply_control_points(w, chans, cps, fps, scale, report=print, shift=0.0):
    """
    Place and animate the control point empties.

    Times in a session are ABSOLUTE SECONDS, so the frame is simply t * fps -
    the same convention Session_Reader extracts with when rebase is off.
    """
    keyed = placed = 0
    for cp in w.get("control_points") or []:
        ob = cps.get(cp["index"])
        if ob is None:
            continue

        # TWO INSTANCES OF THE SAME EFFECT SHARE ONE CONTROL POINT EMPTY.
        # The add-on names them after the SYSTEM, not the instance, so the
        # session's second `AA__Gasoline-Fire_A_100CM` lands on the first
        # one's `· CP0`. Say so instead of silently letting the second
        # placement fight the first one's animation - one of the two will be
        # wrong and it would look like the import inventing motion.
        owner = ob.get("ht_cp_owner")
        if owner and owner != w["name"]:
            report(f"[PARTICLES]  [WARN] '{w['name']}' shares control point "
                   f"CP{cp['index']} with '{owner}' - the add-on names control "
                   f"points after the system, so two instances of the same "
                   f"effect cannot have different ones. Leaving the first "
                   f"one's animation alone.")
            continue
        ob["ht_cp_owner"] = w["name"]
        if cp["pos"] is not None:
            ob.location = sfm_position(cp["pos"], scale)
            placed += 1

        for ch in chans.get(id(cp["elem"]), []):
            attr = ch.get("toAttribute") or ""
            times, values = _log(ch)
            if times is None:
                continue
            if attr == "position":
                for t, v in zip(times, values):
                    loc = sfm_position(v, scale)
                    ob.location = loc
                    ob.keyframe_insert("location",
                                       frame=(float(t) + shift) * fps)
                    keyed += 1
            elif attr == "orientation":
                ob.rotation_mode = 'QUATERNION'
                for t, v in zip(times, values):
                    ob.rotation_quaternion = Quaternion(
                        (float(v[3]), float(v[0]), float(v[1]), float(v[2])))
                    ob.keyframe_insert("rotation_quaternion",
                                       frame=(float(t) + shift) * fps)
                    keyed += 1
    if placed or keyed:
        report(f"[PARTICLES]    control points: {placed} placed, "
               f"{keyed} keyframe(s)")
    return placed, keyed


def _apply_transform(w, chans, roots, fps, scale, report=print, shift=0.0):
    """Place and animate the effect's own root - its DmeTransform.

    Same shape as _apply_control_points, and for the same reason: session
    times are ABSOLUTE SECONDS, so the frame is t * fps.

    Control points are LOCAL offsets under this root, so animating here moves
    the whole effect and its control points together, exactly as SFM plays
    it. That is why the root is keyed rather than every control point being
    given the root's motion added in.

    A channel with ONE key is still keyed rather than treated as a static
    placement. It costs nothing, and it means the static and animated paths
    cannot drift apart - which matters because that is precisely how this bug
    hid: every transform channel in the test session has exactly one key, so
    "the static value happened to be right" looked like "transforms work"."""
    tr = w.get("transform_elem")
    if tr is None or not roots:
        return 0, 0
    keyed = 0
    channels = 0
    for ch in chans.get(id(tr), []):
        attr = ch.get("toAttribute") or ""
        times, values = _log(ch)
        if times is None:
            continue
        channels += 1
        if attr == "position":
            for t, v in zip(times, values):
                #  The CHANNEL drives the system's own local transform, so its
                #  keys are local too and need the same lift. Miss this and a
                #  moving effect snaps to a different place the instant its
                #  first key lands.
                loc = world_position(v, w["parent_matrix"], scale)
                for r in roots:
                    r.location = loc
                    r.keyframe_insert("location", frame=(float(t) + shift) * fps)
                    keyed += 1
        elif attr == "orientation":
            for t, v in zip(times, values):
                q = world_rotation(sfm_quaternion(v), w["parent_matrix"])
                for r in roots:
                    r.rotation_mode = 'QUATERNION'
                    r.rotation_quaternion = q
                    r.keyframe_insert("rotation_quaternion",
                                      frame=(float(t) + shift) * fps)
                    keyed += 1
    if keyed:
        report(f"[PARTICLES]    transform: {channels} channel(s), "
               f"{keyed} keyframe(s) on {len(roots)} root(s)")
    return channels, keyed


def claim_instance_names(fresh, system, label, report=print):
    """Rename everything this build made so the NEXT build cannot reuse it.

    THE BUG THIS FIXES
    ------------------
    HoovyToolsParticleImport names what it builds after the particle SYSTEM,
    not after the instance. Two `AA__Gasoline-Fire_A_100CM` in one session
    therefore came back as literally the SAME objects - verified by object id,
    not by name - so the second fire's placement landed on the first fire's
    root and the first fire ceased to exist. Worse, the first one's hide flag
    was still set, so the second one was invisible too.

    Renaming immediately after each build breaks the cycle: the next
    build_effect() looks for `<system> . CONTROL`, finds nothing, and builds a
    genuinely separate tree. SFM already gives us a unique label per instance
    (`...100CM1`, `...100CM2`), so the new names are stable and readable.

    This is the fix for "we cannot add two particles that are named the same
    way", and it lives HERE rather than in the particle add-on because this is
    the only place that knows an instance from a system.
    """
    renamed = 0
    for o in fresh:
        nm = o.name
        if nm == system:
            new = label
        elif nm.startswith(system):
            new = label + nm[len(system):]
        else:
            #  Not named after the system at all - still make it unique, or a
            #  second instance will collide on it just the same.
            new = "%s %s" % (label, nm)
        if new == nm:
            continue
        o.name = new                 # Blender appends .001 if that is taken
        renamed += 1
    if renamed:
        report(f"[PARTICLES]    renamed {renamed} object(s) "
               f"'{system}...' -> '{label}...'")
    return renamed


def _visibility_spans(elem, chans, fps, shift=0.0):
    """[(frame, bool)] state changes from the `visible` channel, or None.

    SFM writes an on/off change as a PAIR of keys at almost the same instant:
        (503.998, False), (504.000, True), (1344.0, True), (1344.0, False)
    the same step-pair trick its animation curves use.

    HANDING THAT PAIR STRAIGHT TO keyframe_insert DOES NOT WORK. The two keys
    are 0.002 of a frame apart, so Blender merges them and keeps the LAST
    value at the FIRST time - which silently threw away the "off before it
    starts" half. The effect then showed from frame 1 and only ever turned
    off, which is wrong in the safe direction and therefore easy to miss.

    So: snap to whole frames, let the last value at a frame win (that is what
    the frame ends up as, which is what a step means), and re-introduce the
    leading OFF one frame earlier where the pair implied one. The result is a
    clean, readable curve: hidden until 503, visible 504-1343, hidden after."""
    for ch in chans.get(id(elem), []):
        if (ch.get("toAttribute") or "") != "visible":
            continue
        times, values = _log(ch)
        if not times:
            continue
        raw = [((float(t) + shift) * fps, bool(v)) for t, v in zip(times, values)]

        changes = []
        for f, vis in raw:
            fr = int(round(f))
            if changes and changes[-1][0] == fr:
                changes[-1] = (fr, vis)      # last value at a frame wins
            else:
                changes.append((fr, vis))

        #  The pair said "off, then on, at this instant". Snapping collapsed
        #  the off; put it back a frame earlier so the state before the effect
        #  starts is the state SFM actually stored.
        if changes and changes[0][1] and any(not v for _f, v in raw[:1]):
            changes.insert(0, (changes[0][0] - 1, False))
        return changes
    return None


def _span_summary(spans):
    """'visible 504-1344' - the human answer to 'where do I scrub?'"""
    if not spans:
        return None
    on = None
    out = []
    for frame, vis in spans:
        if vis and on is None:
            on = frame
        elif not vis and on is not None:
            out.append((on, frame))
            on = None
    if on is not None:
        out.append((on, None))
    if not out:
        return "never visible"
    return ", ".join("%.0f-%s" % (a, "end" if b is None else "%.0f" % b)
                     for a, b in out)


def apply_visibility(w, chans, objs, fps, mode='KEYED', report=print, shift=0.0):
    """Make the effect visible when the session says it is.

    mode  KEYED   key hide_viewport/hide_render from the `visible` channel
          ALWAYS  leave everything visible, ignore the session
          STATIC  the old behaviour - hide from the element's snapshot.
                  Kept only so the bug can be reproduced on purpose.

    Returns (keys_written, summary_string)."""
    if mode == 'ALWAYS':
        for o in objs:
            o.hide_viewport = False
            o.hide_render = False
        return 0, "forced visible (session visibility ignored)"

    if mode == 'STATIC':
        if not w["visible"]:
            for o in objs:
                if o.type != 'EMPTY':          # see the note below
                    o.hide_viewport = True
                    o.hide_render = True
        return 0, "static %s" % ("visible" if w["visible"] else "HIDDEN")

    hideable = [o for o in objs if o.type != 'EMPTY']
    for o in objs:
        if o.type == 'EMPTY':
            o.hide_viewport = False
            o.hide_render = False

    spans = _visibility_spans(w.get("elem"), chans, fps, shift=shift)
    if not spans:
        #  No channel: the snapshot is all there is, and an effect placed in a
        #  session is there to be seen. Show it rather than hide it - an
        #  unwanted visible effect is obvious and fixable, an invisible one
        #  looks like the importer failed.
        for o in objs:
            o.hide_viewport = False
            o.hide_render = False
        return 0, "no visibility channel - left visible"

    keys = 0
    for o in hideable:
        for frame, vis in spans:
            o.hide_viewport = not vis
            o.hide_render = not vis
            o.keyframe_insert("hide_viewport", frame=frame)
            o.keyframe_insert("hide_render", frame=frame)
            keys += 2
        #  Booleans must step, never ramp. Blender will happily interpolate a
        #  hide flag through 0.5 otherwise, which reads as a flicker.
        ad = o.animation_data
        act = ad.action if ad else None
        if act is not None:
            for fc in _iter_fcurves(act, o):
                if fc.data_path in ("hide_viewport", "hide_render"):
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'
    return keys, "visible frames %s" % _span_summary(spans)


def _iter_fcurves(action, owner):
    """Blender 5.2 removed `action.fcurves` (slotted actions). Go through the
    addon's compatibility shim when it is there, fall back when it is not."""
    try:
        from ..core.anim_compat import iter_fcurves
        return list(iter_fcurves(action, owner))
    except Exception:
        return list(getattr(action, "fcurves", []) or [])


def _get_collection():
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        col.color_tag = COLLECTION_COLOR
        bpy.context.scene.collection.children.link(col)
    return col


# ─────────────────────────────────────────────────────────────────────────────
#  Public
# ─────────────────────────────────────────────────────────────────────────────

def import_session_particles(session_path, scale=1.0, time_scale=None,
                             only_emitting=False, visibility='KEYED',
                             report=print,
                             shot_index=None, shot_name=None):
    """
    Build every particle effect the session references - narrowed to ONE
    shot when one is chosen, exactly like the light importer.

    Never raises for one effect it cannot place - it records the reason and
    carries on, the same rule the rest of the session pipeline follows.
    """
    api, why = particle_api()
    if api is None:
        raise RuntimeError(why)

    from ..SST import get_datamodel
    dm = get_datamodel()
    model = dm.load(str(session_path))

    systems = find_particle_systems(model)
    total_in_file = len(systems)
    shot_note = ""
    time_shot = None          # 1.17.0: the chosen shot, for its timeline shift
    #  NARROW TO ONE CUT, the same doctrine as import_lights: only when a
    #  shot was actually chosen; whole-file stays the no-choice behaviour.
    #  Unlike lights there is NO fallback to the whole file when the shot
    #  owns nothing - most cuts genuinely have no effects, and importing
    #  another shot's fires into them is the exact reported leak.
    if shot_index is not None and int(shot_index) >= 0:
        try:
            from . import Session_Reader as _SR, Session_Paths as _SP
            shot_list = _SR.shots(model)
            shot, shot_note = _SP.resolve_shot(shot_list,
                                               index=int(shot_index),
                                               name=shot_name or "")
            if shot is not None:
                systems = shot_particle_systems(shot)
                time_shot = shot
                report(f"[PARTICLES]  shot {shot.get('name')!r}: "
                       f"{len(systems)} of {total_in_file} system(s) in "
                       f"the file belong to this cut")
        except Exception as exc:                              # noqa: BLE001
            report(f"[PARTICLES]  shot filter unavailable ({exc}) - "
                   f"importing every system")

    if not systems:
        return {"made": [], "skipped": [], "failed": [], "wanted": [],
                "in_file": total_in_file, "shot_note": shot_note}

    parents = dag_parents(model)
    wanted = [describe(e, parents) for e in systems]
    names = sorted({w["system"] for w in wanted if w["system"]})
    report(f"[PARTICLES]  {len(wanted)} system(s) in the session: "
           + ", ".join(names))

    chans = _channel_index(model)
    from . import Session_Reader
    fps = Session_Reader.session_fps(model.root)
    report(f"[PARTICLES]  session fps {fps:g}")

    #  1.17.0: WHERE AN EFFECT'S KEYS LAND. Raw seconds used to go straight
    #  to `t * fps`, which was right only while an effect's channels clip
    #  matched its shot's reference AND the shot sat on extract time. Now the
    #  same shift the rigs get: the clip's rebase + the shot's placement on
    #  SFM's movie clock (Session_Reader.clip_timeline_shift). A whole-session
    #  import times each effect through its own shot.
    _mode = Session_Reader.timing_mode()
    _own_shot = {}
    if time_shot is None and _mode == Session_Reader.TIMING_MOVIE:
        try:
            _own_shot = Session_Reader.element_shots(Session_Reader.shots(model))
        except Exception:                                     # noqa: BLE001
            _own_shot = {}
    _clip_of = {}
    for _cl in model.elements:
        if (_cl.type or "") == "DmeChannelsClip":
            for _ch in (_cl.get("channels") or []):
                _clip_of[id(_ch)] = _cl
    _bases = {}

    def _shift_for(w):
        sh = time_shot if time_shot is not None else _own_shot.get(id(w["elem"]))
        if sh is None:
            return 0.0
        if id(sh) not in _bases:
            _bases[id(sh)] = Session_Reader.shot_time_base(model, sh)
        targets = [w["elem"], w.get("transform_elem")] + \
            [cp.get("elem") for cp in (w.get("control_points") or [])]
        for tgt in targets:
            if tgt is None:
                continue
            for ch in chans.get(id(tgt), []):
                cl = _clip_of.get(id(ch))
                if cl is not None:
                    return Session_Reader.clip_timeline_shift(
                        model, sh, cl, mode=_mode, base=_bases[id(sh)],
                        fps=fps)
        return Session_Reader.place_shift(model, sh, mode=_mode,
                                          base=_bases[id(sh)])

    dirs = particle_dirs()
    if not dirs:
        raise RuntimeError(
            "No particles folder found. Set the SFM usermod path in the "
            "HoovyTools add-on preferences.")
    report("[PARTICLES]  searching: " + "; ".join(str(d) for d in dirs))
    index = _index_pcfs(api, dirs, wanted=names, report=report)

    col = _get_collection()
    made, skipped, failed = [], [], []

    for _n_sys, w in enumerate(wanted, 1):
        label = w["name"]
        Progress.update(_n_sys, len(wanted), label)
        if not w["system"]:
            skipped.append((label, "no particleSystemType"))
            continue
        if only_emitting and not w["emitting"]:
            skipped.append((label, "not emitting"))
            continue
        pcf = index.get(w["system"])
        if pcf is None:
            skipped.append((label, f"no .pcf defines '{w['system']}'"))
            continue

        before = set(bpy.data.objects)
        try:
            #  NAME THE INSTANCE UP FRONT.
            #
            #  The particle add-on RE-FINDS its objects by name -
            #  `bpy.data.objects.get(f"{name} . CONTROL")` and the same for
            #  . TRANSFORM, . CP<n>, container anchors and CP overrides. That
            #  is deliberate and right for a person re-importing one effect.
            #
            #  It is wrong for a session holding TWO of one definition: the
            #  second build re-finds the first one's objects and one of the two
            #  fires stops existing. Renaming afterwards does NOT fix it -
            #  every one of those lookups happens at its own moment inside the
            #  build, so a post-hoc rename is always racing one of them. The
            #  name has to be right BEFORE the build starts.
            #
            #  `name_prefix` was added to the add-on's api for exactly this.
            #  Older copies of it do not have the parameter, so fall back to
            #  the rename rather than failing outright.
            build_kw = dict(
                system=w["system"], collection=col,
                time_scale=(w["time_scale"] if time_scale is None
                            else float(time_scale)))
            try:
                objs = api.build_effect(bpy.context, str(pcf),
                                        name_prefix=label, **build_kw)
                prefixed = True
            except TypeError as exc:
                if "name_prefix" not in str(exc):
                    raise
                report(f"[PARTICLES]  [WARN] this ParticleImport build is "
                       f"older than the name_prefix parameter - falling back "
                       f"to renaming after the build, which cannot fully "
                       f"separate two instances of one effect. Update that "
                       f"add-on.")
                objs = api.build_effect(bpy.context, str(pcf), **build_kw)
                prefixed = False
        except Exception as exc:
            failed.append((label, f"{type(exc).__name__}: {exc}"))
            continue
        fresh = [o for o in bpy.data.objects if o not in before]

        #  Only needed on the fallback path - with name_prefix the add-on
        #  already built everything under this instance's name.
        if not prefixed:
            claim_instance_names(fresh, w["system"], label, report=report)

        # Place it. The effect's own root is whichever created object has no
        # parent inside the set; move that and the tree follows.
        roots = [o for o in objs if o.parent is None or o.parent not in objs]

        # the control points, which are what actually drive the effect
        cp_objs = _cp_empties(roots, fresh)
        tshift = _shift_for(w)
        if abs(tshift) > 1e-6:
            report(f"[PARTICLES]    keys shifted {tshift:+.4f}s onto the "
                   f"Blender timeline")
        cp_placed, cp_keyed = _apply_control_points(
            w, chans, cp_objs, fps, scale, report=report, shift=tshift)
        #  The ownership stamp stays as a BACKSTOP. claim_instance_names()
        #  above should mean no two instances ever reach the same object now,
        #  so this loop is expected to keep everything - if it ever starts
        #  warning again, the renaming did not take, and that is worth knowing
        #  immediately rather than discovering it as a missing effect.
        owned = []
        for r in roots:
            owner = r.get("ht_effect_owner")
            if owner and owner != label:
                report(f"[PARTICLES]  [WARN] '{label}' would reuse the root "
                       f"'{r.name}' already placed by '{owner}' - the add-on "
                       f"names objects after the system, so two instances of "
                       f"'{w['system']}' cannot be placed separately. "
                       f"Leaving the first one alone.")
                continue
            r["ht_effect_owner"] = label
            owned.append(r)

        # Static placement FIRST, then the transform channels key over it.
        # In that order a system whose transform carries no channels at all
        # still lands where the session put it, and one that is animated is
        # not left with a stale un-keyed value underneath its curves.
        if w["pos"] is not None:
            loc = world_position(w["pos"], w["parent_matrix"], scale)
            for r in owned:
                r.location = loc
        if w["rot"] is not None:
            q = world_rotation(sfm_quaternion(w["rot"]), w["parent_matrix"])
            for r in owned:
                r.rotation_mode = 'QUATERNION'
                r.rotation_quaternion = q

        tr_channels, tr_keyed = _apply_transform(
            w, chans, owned, fps, scale, report=report, shift=tshift)
        shared_root = len(roots) - len(owned)

        #  EVERYTHING this instance owns, not just what build_effect chose to
        #  return. `fresh` catches the carriers and helper objects that hang
        #  off the emitters - object-level hide_viewport does NOT cascade to
        #  children in Blender, so a parent-only hide leaves them on screen.
        mine = list(objs) + [o for o in fresh if o not in set(objs)]
        vis_keys, vis_note = apply_visibility(
            w, chans, mine, fps, mode=visibility, report=report, shift=tshift)
        report(f"[PARTICLES]    visibility: {vis_note}"
               + (f"  ({vis_keys} key(s))" if vis_keys else ""))

        #  WHICH .pcf DEFINED IT. The session names a system; the
        #  definition lives in a .pcf found by searching thousands of files,
        #  and which one won is the thing you need to open when an effect
        #  looks wrong.
        try:
            from ..core import sources
            sources.add("particle", f"{label}  ({w['system']})", pcf)
        except Exception:
            pass

        made.append({"name": label, "system": w["system"], "pcf": pcf,
                     "objects": objs, "roots": roots,
                     "control_points": len(cp_objs),
                     "cp_placed": cp_placed, "cp_keys": cp_keyed,
                     "tf_channels": tr_channels, "tf_keys": tr_keyed,
                     "shared_root": shared_root,
                     "vis_keys": vis_keys, "vis_note": vis_note,
                     "location": (list(world_position(w["pos"],
                                                       w["parent_matrix"],
                                                       scale))
                                  if w["pos"] else None)})
        report(f"[PARTICLES]  {label}: '{w['system']}' from {pcf.name} "
               f"-> {len(objs)} object(s), {len(cp_objs)} control point(s), "
               f"transform {tr_keyed} key(s)")

    return {"made": made, "skipped": skipped, "failed": failed,
            "wanted": wanted}


# ─────────────────────────────────────────────────────────────────────────────
#  Operator
# ─────────────────────────────────────────────────────────────────────────────

#  THE THREE OPTIONS, DEFINED ONCE AND USED BY BOTH OPERATORS. The step and
#  the standalone file importer must offer the same choices with the same
#  defaults and the same wording - two copies of a description this long drift
#  the first time one of them is edited. Blender is happy for one property
#  definition to be annotated onto more than one class; each gets its own
#  storage, they only share the declaration.
_P_SCALE = FloatProperty(  # type: ignore
    name="Scale",
    description="World scale - match the rest of the session import",
    default=1.0, min=1e-6, soft_min=0.0001, soft_max=100.0,
    precision=6,
)
_P_ONLY_EMITTING = BoolProperty(  # type: ignore
    name="Only Emitting",
    description=("Skip systems the session has switched off. A session "
                 "often carries effects that are placed but not "
                 "firing.\n\n"
                 "Reads the element's STATIC emitting flag, which is a "
                 "playhead snapshot - an effect that fires later in the "
                 "shot can read as 'not emitting'. Off by default for "
                 "exactly that reason"),
    default=False,
)
_P_VISIBILITY = EnumProperty(  # type: ignore
    name="Visibility",
    description=(
        "SFM keys an effect on and off. The element also carries a static "
        "visible flag, but that is only a snapshot of wherever the "
        "playhead was left - trusting it is what made every imported "
        "effect invisible"),
    items=[
        ('KEYED', "Keyed From Session",
         "Key hide/show from the session's visible channel - the effect "
         "appears on the frames SFM shows it"),
        ('ALWAYS', "Always Visible",
         "Ignore the session and leave everything visible. Use this when "
         "you just want to see what was built"),
        ('STATIC', "Static Flag (old)",
         "Hide from the element's static visible flag. This is the old "
         "behaviour and it is the bug - kept only to reproduce it"),
    ],
    default='KEYED',
)


class HT_OT_step_particles(Operator):
    """NO INPUT - runs on the session connected on the Main tab. Needs the
        HoovyTools-ParticleImport-Blender-Master add-on.

        Build the session's particle effects, through HoovyTools Particle Import

A session does not contain its particle effects. It names them - a
DmeGameParticleSystem carries `particleSystemType`, e.g.
"AA__Gasoline-Fire_A_100CM" - and expects the game to find the definition.
The definitions live in .pcf files under usermod/particles.

So this reads the names and the placements out of the session, searches the
particle folders for a .pcf that defines each one, and hands the build to the
Particle Import add-on through its own api module. That add-on must be
enabled; nothing here re-implements a .pcf reader.

Effects land in their own collection, placed with the same world map the
cameras, lights and characters use
        """
    bl_idname = "ht.step_particles"
    bl_label = "7  Import Particles"
    #  NO "REGISTER" - see the note in Report_UI/the constitution.
    #  REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    #  touching any field in it RE-RUNS this operator. Re-running an
    #  import re-reads the DMX and rebuilds every f-curve; nudging Scale
    #  there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    #  with the value you wanted is the safe way to change your mind.
    bl_options = {"UNDO"}

    reads_session = True

    #  PICKED, NOT CONNECTED. Set by the Tools drawer; empty everywhere else,
    #  and empty means "use the session this .blend is wired to".
    pick_session: BoolProperty(default=False, options={"HIDDEN"})  # type: ignore
    filepath:    StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})  # type: ignore
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    def invoke(self, context, event):
        from .Session_Steps import pick_or_run
        return pick_or_run(self, context, event)

    scale: _P_SCALE  # type: ignore
    only_emitting: _P_ONLY_EMITTING  # type: ignore
    visibility: _P_VISIBILITY  # type: ignore

    @classmethod
    def poll(cls, context):
        from .Session_Steps import (session_of, _session_for,
                                    no_session_error)
        return True

    @Progress.jobbed_execute("SFM Session Importer - 7  Import Particles")
    def execute(self, context):
        from .Session_Steps import (session_of, _session_for,
                                    no_session_error)
        session = _session_for(self, context)
        if session is None:
            self.report({"ERROR"}, no_session_error(self))
            return {"CANCELLED"}
        return _run_particles(self, context, session, self.scale,
                              self.only_emitting, self.visibility)


def _run_particles(op, context, session, scale, only_emitting, visibility):
    """Build one session's particles and report. Shared by both entries.

    EXTRACTED BECAUSE A poll() CANNOT SEE A FILEPATH. The standalone importer
    first routed through `bpy.ops.ht.step_particles(filepath=...)`, which
    Blender refused with "poll() failed, context is incorrect" - the step's
    poll requires a CONNECTED SESSION, and no session connected is precisely
    the case the standalone entry exists for. One operator calling another is
    only safe when the callee's poll can be satisfied; a shared function has
    no poll to satisfy.
    """
    from .Session_Steps import _popup
    try:
        from . import Session_Paths as _SP
        from .Session_Steps import session_of as _so
        idx, nm = (None, "")
        connected = _so(context) if context else None
        if connected is not None and str(connected) == str(session):
            idx, nm = _SP.shot_choice(context.scene)
        r = import_session_particles(session, scale=scale,
                                     only_emitting=only_emitting,
                                     visibility=visibility,
                                     shot_index=idx, shot_name=nm)
    except Exception as exc:
        op.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
        return {"CANCELLED"}

    lines = [f"In session : {len(r['wanted'])} particle system(s)",
             f"Built      : {len(r['made'])}",
             f"Skipped    : {len(r['skipped'])}",
             f"Failed     : {len(r['failed'])}"]
    tf_keys = sum(m.get("tf_keys", 0) for m in r["made"])
    cp_keys = sum(m.get("cp_keys", 0) for m in r["made"])
    shared = [m for m in r["made"] if m.get("shared_root")]
    lines.append(f"Keys       : {tf_keys} transform, {cp_keys} control pt")
    #  WHERE TO SCRUB. An effect keyed to appear at frame 504 is invisible
    #  at frame 1 and that is correct - but "I imported particles and saw
    #  nothing" is the same sentence either way, so say the frames out loud.
    for m in r["made"]:
        if m.get("vis_note"):
            lines.append(f"  {m['name'][:22]:<24}{m['vis_note'][:34]}")
    if shared:
        lines.append(f"Shared     : {len(shared)} instance(s) reuse another")
        lines.append("             effect's objects - see the console.")
    for m in r["made"][:8]:
        lines.append(f"  {m['name'][:24]:<26}{m['system'][:26]}")
    if r["skipped"]:
        lines.append("")
        for n, why in r["skipped"][:6]:
            lines.append(f"  skip {n[:20]:<22}{why[:34]}")
    if r["failed"]:
        lines.append("")
        for n, why in r["failed"][:4]:
            lines.append(f"  FAIL {n[:20]:<22}{why[:34]}")
    if not r["made"] and r["skipped"]:
        lines.append("")
        lines.append("If the .pcf is not in usermod/particles, copy it")
        lines.append("there or set the usermod path in preferences.")

    _popup(context, "Import Particles", lines, icon='PARTICLES',
           key="step_particles",
           level=("WARNING" if (r["failed"] or r["skipped"]) else "INFO"),
           operator=op)
    return {"FINISHED"}


_ht_icon_id = None


def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


class HT_OT_import_particles_file(Operator):
    """PICK .dmx (session) - the effects are read out of the session, NOT out
        of a .pcf

        Import the particle effects out of ONE session file you pick

The same importer as step 8, pointed at a file instead of at the connected
session - so you can pull the effects out of a shot without loading it as
the project.

Needs the HoovyTools-ParticleImport-Blender-Master add-on, which does the .pcf
work; this
reads the names and placements and hands the build over. Effects land in
their own collection, placed with the same world map the cameras, lights and
characters use.

Scale, visibility and only-emitting are whatever step 8 last ran with"""
    bl_idname = "ht.import_particles_file"
    bl_label = "Session Particles"
    bl_options = {"UNDO"}

    filepath:    StringProperty(subtype="FILE_PATH")  # type: ignore
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    #  THE SAME THREE OPTIONS AS THE STEP, from the same definitions - so the
    #  two entries cannot offer different defaults or different wording.
    scale: _P_SCALE  # type: ignore
    only_emitting: _P_ONLY_EMITTING  # type: ignore
    visibility: _P_VISIBILITY  # type: ignore

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    @Progress.jobbed_execute("SFM Session Importer - Import Particles")
    def execute(self, context):
        raw = (self.filepath or "").strip()
        if not raw:
            self.report({"WARNING"}, "No file picked.")
            return {"CANCELLED"}
        session = Path(bpy.path.abspath(raw))
        if not session.is_file():
            self.report({"ERROR"}, f"Not a file: {session}")
            return {"CANCELLED"}
        #  The shared function, NOT bpy.ops.ht.step_particles. Calling the step
        #  fails its own poll when no session is connected, which is exactly
        #  when someone reaches for this entry.
        return _run_particles(self, context, session, self.scale,
                              self.only_emitting, self.visibility)


def draw_menu_item(layout):
    layout.operator(HT_OT_import_particles_file.bl_idname,
                    text="Session Particles",
                    **_icon_id("import_particles", "PARTICLES"))


def draw_session_entry(layout):
    """Entry 8 inside the IMPORT SESSION submenu."""
    layout.operator(HT_OT_import_particles_file.bl_idname,
                    text="7  Import DMX Session Particles",
                    **_icon_id("import_particles", "PARTICLES"))


def register(icon_id_fn=None):
    global _ht_icon_id
    _ht_icon_id = icon_id_fn
    bpy.utils.register_class(HT_OT_step_particles)
    bpy.utils.register_class(HT_OT_import_particles_file)


def unregister():
    for cls in (HT_OT_import_particles_file, HT_OT_step_particles):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
