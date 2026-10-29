"""
Import_DMX_Animation.py  —  part of HoovyTools
===============================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ DMX Animation

PUBLIC API  (call from other HoovyTools scripts)
────────────────────────────────────────────────
    from . import Import_DMX_Animation

    result = Import_DMX_Animation.import_dmx_animation(
        dmx_path = Path("my_anim.dmx"),
        armature = bpy.data.objects["MyArm"],
    )
    # returns:
    # {
    #   "action"      : bpy.types.Action,        # bone pos/rot (from BST)
    #   "root_action" : bpy.types.Action | None, # root-empty action
    #   "root_empty"  : bpy.types.Object | None, # root Empty
    #   "scale_bones" : int,
    #   "root_curves" : int,
    # }
"""

bl_info = {
    "name":        "HoovyTools: Import DMX Animation",
    "description": "Import SFM DMX animation — bones, scale, root transform",
    "author":      "HoovyTools",
    "version":     (1, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > DMX Animation",
    "category":    "Import-Export",
}

import bpy
from math import pi
from pathlib import Path
from mathutils import Matrix, Quaternion, Vector
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty
from ..core import Common_Props
from bpy_extras.io_utils import ImportHelper

from ..core import start_folders
from ..core.anim_compat import make_action, get_channelbag, fc_find_or_new, iter_fcurves, count_fcurves


# ──────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _get_datamodel():
    """Return the datamodel module via SST's bundled copy."""
    from ..SST import get_datamodel
    return get_datamodel()


def _fc(bag, data_path, index, group):
    return fc_find_or_new(bag, data_path, index=index, group_name=group)


def _key(bag, data_path, index, group, frame, value):
    kp = _fc(bag, data_path, index, group).keyframe_points.insert(
        float(frame), float(value), options={"FAST"}
    )
    kp.interpolation = "LINEAR"


# The SFM -> Blender WORLD MAP, and the only answer either source may land on
#
# (x, y, z)  ->  (y, -x, z)        which is Rz(-90)
#
# Import_DMX_Camera has always used it for camera position. Everything else has
# to agree with it or the camera will not be looking at what it looked at in
# SFM. Confirmed w/o assuming any convention, by the angle two objects
# subtend at the camera - a quantity no rigid mapping can change:
#
# session truth                        39.966 deg
# (y,-x,z)  Rz(-90)                    39.966 deg   <-- the answer
# (y, z, x) raw session keys           33.851 deg
# (x, y, z) identity                   79.708 deg
# (x,-z, y) Rx(+90)                    77.590 deg
#
# The two SOURCES reach it from different places, which is the whole subtlety:
#
# SFM EXPORT   model data is Y-up (SFM's exporter converted it), so the axis
# empty is Rx(+90) and the root keys carry the permutation
# (v1, v2, v0).  Rx(+90) @ (v1,v2,v0) == (y,-x,z)
# SESSION      model data is live Source Z-up (nothing converted it), so the
# axis empty is Rz(-90) and the root keys go in RAW.
# Rz(-90) @ (v0,v1,v2) == (y,-x,z).
#
# Same destination, different route. Mixing the routes up is what put half a
# scene on its side and left the other half facing the wrong way
AXIS_EMPTY_EULER = {
    'Y': (pi / 2, 0.0, 0.0),      #Y-up model data  (SFM export)
    'Z': (0.0, 0.0, -pi / 2),     #Z-up model data  (session extract)
}


def _get_or_create_axis_empty(armature, source_axis='Y'):
    """
    The static parent the animated root empty hangs from, and the ONE place
    the SFM -> Blender world map is applied.

    EXACTLY ONE PLACE MAY APPLY THE MAP - AND IT IS THIS ONE
    ========================================================
    It looks like the Y-up part of this could be handed to Blender Source
    Tools instead, by telling it the file's up axis. It cannot.

    BST CANNOT DO IT HERE. getUpAxisMat() only reaches `smd.a.matrix_world` on
    the NEW_ARMATURE path, where BST builds the rig itself. This pipeline
    always animates an armature that ALREADY EXISTS - SourceIO built it from
    the .mdl - so that line never runs. On an existing rig, `upAxis='Y'` does
    nothing but seed the ROOT bone's keyframe with getUpAxisMat('Y').inverted(),
    which tips the character onto its side instead of standing it up.

    Measured on a real SourceIO scout rig, pelvis -> head:

        BST told 'Z', this empty at +90 X : (-0.038,  0.030,  0.999)  upright
        BST told 'Y', this empty at 0,0,0 : (-0.038,  0.999, -0.030)  on its side

    So BST is always run at its 'Z' no-op default and this empty does the work.

    *source_axis* is the up axis of the MODEL DATA in the file - 'Y' for an SFM
    export, 'Z' for a session extract - and picks the rotation from
    AXIS_EMPTY_EULER above. It is not a preference; it is a fact about the file,
    and Session_Reader now declares it honestly.

    The rotation is written EVERY time, not only on creation: re-importing
    onto a rig that already has an axis empty must converge on the right
    value rather than inheriting whatever the last run left behind.
    """
    euler = AXIS_EMPTY_EULER.get(source_axis, AXIS_EMPTY_EULER['Y'])
    label = "+90 X (Y-up source)" if source_axis != 'Z' else "-90 Z (Z-up source)"

    name  = f"{armature.name}_axis"
    empty = bpy.data.objects.get(name)
    created = False
    if empty is None:
        empty = bpy.data.objects.new(name, None)
        empty.empty_display_type = "ARROWS"
        empty.empty_display_size = 15.0
        empty.location           = (0.0, 0.0, 0.0)
        for col in armature.users_collection:
            col.objects.link(empty)
        created = True

    empty.rotation_mode  = "XYZ"
    empty.rotation_euler = euler
    print(f"[DMX_ANIM]  {'created' if created else 'set'} axis empty "
          f"'{name}'  rotation {label}")
    return empty


def _get_or_create_root_empty(armature, source_axis='Y'):
    """
    Animated empty that receives root transform keyframes.
    Parented to the axis empty so the world map is inherited.
    The armature is then parented to this empty.
    """
    axis_empty = _get_or_create_axis_empty(armature, source_axis)

    name  = f"{armature.name}_root"
    empty = bpy.data.objects.get(name)
    if empty is None:
        empty = bpy.data.objects.new(name, None)
        empty.empty_display_type = "ARROWS"
        empty.empty_display_size = 10.0
        for col in armature.users_collection:
            col.objects.link(empty)
        print(f"[DMX_ANIM]  created root empty '{name}'")

    # Parent root → axis (static correction layer)
    if empty.parent != axis_empty:
        empty.parent                = axis_empty
        empty.matrix_parent_inverse = Matrix.Identity(4)
        print(f"[DMX_ANIM]  '{name}' parented to '{axis_empty.name}'")

    # Parent armature → root (animated layer)
    if armature.parent != empty:
        armature.parent                = empty
        armature.matrix_parent_inverse = Matrix.Identity(4)
        print(f"[DMX_ANIM]  '{armature.name}' parented to '{name}'")

    return empty


def read_file_up_axis(dmx_path):
    """
    The up axis the DMX itself declares, or None.

    WHY THIS MATTERS
    ----------------
    BST takes its up axis from a SCENE property (import_smd.py:116,
    `scene.ht_vs.up_axis`) whose default is 'Z'. Every SFM export declares
    `skeleton.upAxis = 'Y'` in the file, and getUpAxisMat('Z') is the
    IDENTITY - so with the default, a Y-up file gets no axis correction at
    all and the result comes in rotated.

    The file knows better than a scene default, so read it.
    """
    try:
        dm = _get_datamodel()
        model = dm.load(str(dmx_path))
        skeleton = model.root.get("skeleton")
        if skeleton is None:
            return None
        axis = skeleton.get("upAxis")
        if axis and str(axis).upper() in ("X", "Y", "Z"):
            return str(axis).upper()
    except Exception as exc:
        print(f"[DMX_ANIM]  up axis unreadable ({exc}) - leaving it to BST")
    return None


def ensure_file_root_bones(dmx_path, armature, up_axis=None):
    """
    Give the armature any ROOT-LEVEL bone the file animates but the rig lacks.

    WHY THIS EXISTS - THE viewTarget CASE
    =====================================
    SFM rigs carry a `viewTarget`: the thing the eyes look at. It is a
    root-level DmeDag under the game model, with position and orientation
    channels like any bone, and it is the only reason an imported character
    looks where they looked in SFM.

    Blender Source Tools will not create it. Its bone-append mode is
    APPEND, but ensureAnimationBonesValidated() downgrades that to VALIDATE
    the moment the job is an animation onto an existing armature
    (import_smd.py: "Appending bones from animations is destructive"), and
    VALIDATE only matches names that are already there. The channel is then
    dropped with one line on the console - "Animation refers to
    unrecognised bone" - and the eyes never move. Nothing in the UI says
    so, which is what makes it read as "viewTarget is not animated".

    The rig normally gets that bone from Import_MDL.apply_eye_fix(), but
    that needs eye empties to average a position from, so a model whose
    eyes SourceIO did not produce silently arrives without one.

    Only root-level DAG children are considered - in practice the model
    root, which always exists, and viewTarget, which is the point. Bones
    deeper in the tree are the model's own skeleton and a missing one there
    means the wrong rig, not a missing control; creating those would paper
    over a mismatch worth seeing.

    Rest position comes from the file, corrected by *up_axis* the same way
    BST corrects the skeleton. It only affects where the bone sits before
    the first key - applyFrames writes pose matrices, so the animated
    result is the file's either way - but a sane rest keeps the bone from
    sitting at the origin looking broken.

    Returns the list of bone names created (usually empty).
    """
    from ..SST.utils import getUpAxisMat

    dm = _get_datamodel()
    try:
        model = dm.load(str(dmx_path))
    except Exception as exc:
        print(f"[DMX_ANIM]  root-bone check skipped: {exc}")
        return []

    skeleton = model.root.get("skeleton")
    if skeleton is None:
        return []

    existing = {b.name.lower() for b in armature.data.bones}
    wanted   = []
    for child in (skeleton.get("children") or []):
        if getattr(child, "type", None) not in ("DmeDag", "DmeJoint"):
            continue
        name = getattr(child, "name", None)
        if not name or name.lower() in existing:
            continue
        #A Dag that only wraps a mesh is not a bone - same test BST uses
        shape = child.get("shape")
        if shape is not None and shape.get("currentState") is not None:
            continue
        wanted.append((name, child))

    if not wanted:
        return []

    correction = getUpAxisMat(up_axis) if up_axis in ("X", "Y", "Z") else Matrix.Identity(4)

    linked_here = armature.name not in bpy.context.scene.collection.objects
    if linked_here:
        bpy.context.scene.collection.objects.link(armature)
    prev_active = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    created = []
    try:
        for name, node in wanted:
            head = Vector((0.0, 0.0, 0.0))
            trfm = node.get("transform")
            if trfm is not None and trfm.get("position") is not None:
                pos  = trfm["position"]
                head = correction.to_3x3() @ Vector((float(pos[0]),
                                                     float(pos[1]),
                                                     float(pos[2])))
            bone = armature.data.edit_bones.new(name)
            bone.head       = head
            bone.tail       = head + Vector((0.0, 0.0, 5.0))
            bone.use_deform = False
            created.append(bone.name)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        if linked_here:
            bpy.context.scene.collection.objects.unlink(armature)
        if prev_active is not None:
            bpy.context.view_layer.objects.active = prev_active

    if created:
        print(f"[DMX_ANIM]  added root bone(s) the file animates but "
              f"'{armature.name}' lacked: {', '.join(created)}")
    return created


ROT_MODE_DEFAULT = 'QUATERNION'


def _run_bst_import(dmx_path: Path, armature, up_axis=None,
                    rot_mode=ROT_MODE_DEFAULT):
    """Run the SMD importer. Uses SST's bundled ht.import_smd operator."""
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    rot_mode = rot_mode if rot_mode in ('XYZ', 'QUATERNION') else ROT_MODE_DEFAULT
    kw = {"rotMode": rot_mode}
    before = {a.name for a in bpy.data.actions}
    if up_axis in ("X", "Y", "Z"):
        print(f"[DMX_ANIM]  up axis: {up_axis}")
        kw["upAxis"] = up_axis
    print(f"[DMX_ANIM]  bone rotation: {rot_mode}")
    result = bpy.ops.ht.import_smd(filepath=str(dmx_path), **kw)

    if "FINISHED" not in result:
        raise RuntimeError(f"SMD importer returned {result}")

    new_names = {a.name for a in bpy.data.actions} - before
    if not new_names:
        raise RuntimeError("SMD importer finished but created no new action")

    stem   = dmx_path.stem.lower()
    scored = sorted(new_names, key=lambda n: stem in n.lower(), reverse=True)
    action = bpy.data.actions[scored[0]]

    anim_data = armature.animation_data or armature.animation_data_create()
    anim_data.action = action
    return action


def _no_patch():
    """The shape _patch_scale_and_root returns when there is nothing to patch."""
    return {"scale_bones": 0, "scale_keys": 0, "scale_unresolved": [],
            "root_curves": 0, "root_action": None, "root_empty": None}


# Root-transform channel names. A session names the game model's own
# placement rootTransform_*; an SFM export names it unnamed_*. Session_Reader
# renames the first two on extraction, but not the scale one - so both spellings
# have to be recognised here, and both have to be kept OFF the bone path
# Exception (1.16.1): "root_scale" on a rig with a bone named "root" is that
# bone's own scale channel - see the bone-scale guard in _patch_scale_and_root.
ROOT_SCALE_CHANNELS = ("rootTransform_scale", "root_scale")
ROOT_TRANSFORM_CHANNELS = ("unnamed_p", "unnamed_o") + ROOT_SCALE_CHANNELS


def _rescale_span(channel):
    """(lo, hi) if this channel feeds a `lerp(value, lo, hi)` operator.

    Shared shape with Session_Reader._rescale_of, which does the same job for
    camera settings. Kept separate rather than imported so the animation
    importer stays usable on a hand-made DMX with no session behind it."""
    to = channel.get("toElement")
    if to is None or (to.type or "") != "DmeExpressionOperator":
        return None
    try:
        if "lerp" not in str(to.get("expr") or ""):
            return None
        lo, hi = to.get("lo"), to.get("hi")
        if lo is None or hi is None:
            return None
        return float(lo), float(hi)
    except Exception:
        return None


def _patch_scale_and_root(dmx_path: Path, armature, action,
                          add_root_helpers: bool = True,
                          source_axis: str = 'Y'):
    """
    Second pass: add scale + root-transform keys that BST skips.

    SCALE  -  THREE SHAPES, AND THE ONE THAT ACTUALLY OCCURS
      Measured against `new session.dmx`, 2026-08-21. Bone scale in a real
      SFM session is NONE of the obvious things:

        a) toAttribute == "scale" on a bone's DmeTransform. Handled, and it
           does appear as the wiring between the operator below and the
           transform - but those channels carry NO KEYS.
        b) a channel named "<bone>_scale" whose toElement is the bone. Never
           seen; this was what the old code assumed.
        c) WHAT SFM ACTUALLY WRITES: a channel named "<bone>_scale" with
           toAttribute == "value", pointing at a DmeExpressionOperator called
           "<bone>_scale_rescale" whose expr is `lerp(value, lo, hi)`.

      (c) is the same normalised-slider-behind-a-rescale-operator trick the
      CAMERA uses for fieldOfView, and it has the same trap: the raw value is
      NOT the scale. gman's neck keys 0.1000..0.1229 through lo=0, hi=10, so
      the real scale runs 1.000..1.229. Import the raw number and the bone
      collapses to a tenth of its size.

      This is why scale stopped importing. The old code matched the channel
      NAME correctly and then took the bone name from `toElement.name` - which
      is "ValveBiped.Bip01_Neck1_scale_rescale", the operator, not the bone.
      No bone matched, so the channel was skipped and the run reported
      "scale: 0 bone(s)" on a file with 4 animated scale bones.

      All three shapes are read now, and the channel NAME is trusted over the
      target element's name.

    ROOT TRANSFORM
      Channels "unnamed_p" / "unnamed_o" → location / rotation_quaternion
      on a root Empty named {armature.name}_root. Armature is parented to it.

    FRAME OFFSET
      timeFrame["start"] is added to every raw time before frame conversion,
      matching BST's own behaviour (import_smd.py line 1685).

    AXIS CONVERSION  (SFM Y-up → Blender Z-up)
      position:    (x, y, z) → (x,  z, -y)
      orientation: mirrors BST's getUpAxisMat('Y').inverted() matrix chain

      Those two lines describe the keys as written into the ROOT EMPTY's
      own local space, which is only half the transform: the axis empty
      above it supplies a +90 X and the world result is (y, -x, z).
      When BST has already corrected the bones from the file's upAxis the
      axis empty sits at identity (see _get_or_create_axis_empty), so that
      +90 X has to be baked into these keys instead - otherwise the bones
      come in upright while root motion lands on the wrong axes.
    """
    dm    = _get_datamodel()
    model = dm.load(str(dmx_path))

    anim_list = model.root.get("animationList")
    if not anim_list:
        return _no_patch()
    anims = anim_list.get("animations")
    if not anims:
        return _no_patch()

    animation  = anims[0]
    frame_rate = animation.get("frameRate", 30)
    channels   = animation.get("channels") or []

    time_frame = animation.get("timeFrame")
    start = float(time_frame.get("start", 0)) if time_frame is not None else 0.0

    def frame_for(t):
        return (float(t) + start) * frame_rate

    bone_lower  = {pb.name.lower(): pb for pb in armature.pose.bones}
    scale_bones = 0
    scale_keys  = 0
    unresolved_scale = []

    #the root branches below write HALF a transform: the keys live in the axis
    #empty's own space and are finished by its rotation. Which half depends on
    #where the file came from - see AXIS_EMPTY_EULER. Both halves must multiply
    #out to the same world map, (x, y, z) -> (y, -x, z), or the characters and
    #the camera watching them end up in different coordinate systems.
    #Verified against session truth: rootTransform_p (-381.51, -10.48, 0)
    #reaches world (-10.48, 381.51, 0)
    session_source = (source_axis == 'Z')

    # create axis + root empty hierarchy so the armature gets the +90 X
    # correction even if this DMX has no unnamed_p/unnamed_o channels (e.g
    # models whose root motion lives on a bone instead of the game model).
    # When add_root_helpers is False (SMD-clean), skip it entirely: no empty,
    # no parenting, bone + scale channels only
    if add_root_helpers:
        root_empty = _get_or_create_root_empty(armature, source_axis)
    else:
        root_empty = None
        print("[DMX_ANIM]  add_root_helpers=False — skipping root empty "
              "(SMD-clean: bone channels only)")
    root_action = None
    root_bag    = None

    # Get the channelbag for the main armature action (for bone scale keys)
    action_bag = get_channelbag(action, armature)

    def _add_scale_keys(bag, path, group_name, frame, val, span=None):
        """Unpack Vector3 or uniform float -> 3 scale keys.

        *span* is the (lo, hi) of a rescale operator standing in front of this
        channel. When there is one the stored number is a normalised slider
        position, not a scale, and has to be lerped back."""
        try:
            sv = [float(val[0]), float(val[1]), float(val[2])]    # Vector3
        except TypeError:
            sv = [float(val)] * 3                                # uniform float
        if span is not None:
            lo, hi = span
            sv = [lo + (hi - lo) * v for v in sv]
        for i in range(3):
            _key(bag, path, i, group_name, frame, sv[i])

    def _bone_for_scale(ch_name, to_elem):
        """The pose bone a scale channel belongs to, or None.

        THE CHANNEL NAME IS THE AUTHORITY, not the target element. SFM points
        a scale channel at a `<bone>_scale_rescale` operator, so trusting
        `toElement.name` looks for a bone that cannot exist. The target is
        only consulted when it does name a real bone - which is the (a) shape,
        a channel wired straight onto the bone's DmeTransform."""
        stem = ch_name.removesuffix("_scale").removesuffix("_s")
        for cand in (stem, getattr(to_elem, "name", None) or ""):
            bone = bone_lower.get(cand.lower())
            if bone is not None:
                return bone
        return None

    for ch in channels:
        ch_name = ch.name or ""
        to_elem = ch.get("toElement")
        to_attr = ch.get("toAttribute", "") or ""

        try:
            log_elem = ch.get("log")
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
            print(f"[DMX_ANIM]  ch '{ch_name}' log read failed: {e}")
            continue

        # ── Bone scale ────────────────────────────────────────────────────────
        # Guard: rootTransform_scale / root_scale belong to the root empty,
        # not to a bone - UNLESS the rig has a bone literally named "root".
        # 1.16.1: SFM names a bone's scale channel "<bone>_scale", so a prop
        # whose only bone is "root" writes "root_scale" for it (its wiring
        # channel, scaled_root_scale_channel, targets "bone 0 (root)").
        # Measured on the CSdeals Scene 2 session: 26 props - streetlamps,
        # skydomes, skyboxes - had their scale put on <prop>_root and 0 keys
        # on the bone. The rig decides: a "root" bone takes it
        is_scale_ch = (to_attr == "scale") or ch_name.endswith("_scale")
        is_root_scale = (ch_name in ROOT_SCALE_CHANNELS
                         and not (ch_name == "root_scale"
                                  and "root" in bone_lower))
        if not is_root_scale and is_scale_ch:
            bone = _bone_for_scale(ch_name, to_elem)
            if not bone:
                # worth one line each: a scale channel that resolves to no
                # bone is exactly the failure that made scale silently vanish,
                # and silence is how it stayed unnoticed
                unresolved_scale.append(ch_name)
                continue
            span = _rescale_span(ch)
            path = f'pose.bones["{bone.name}"].scale'
            for t, v in zip(times, values):
                _add_scale_keys(action_bag, path, bone.name, frame_for(t), v,
                                span=span)
            scale_bones += 1
            scale_keys += len(times)
            print(f"[DMX_ANIM]  scale -> {bone.name}: {len(times)} key(s)"
                  + (f"  via lerp({span[0]:g}, {span[1]:g})" if span else ""))
            continue

        # ── Root transform ─────────────────────────────────────────────────────
        if ch_name not in ROOT_TRANSFORM_CHANNELS:
            continue

        # SMD-clean: no root empty was created, so skip root motion entirely
        if root_empty is None:
            continue

        if root_action is None:
            root_action, root_bag = make_action(f"{action.name}_root", root_empty)
            root_empty.rotation_mode = "QUATERNION"

        group = "root_transform"
        for t, v in zip(times, values):
            fr = frame_for(t)
            if ch_name == "unnamed_p":
                if session_source:
                    # Session: the axis empty above is Rz(-90), which IS the
                    # world map, so the placement goes in exactly as the
                    # session states it. Rz(-90) @ (x,y,z) == (y,-x,z)
                    loc = Vector((float(v[0]), float(v[1]), float(v[2])))
                else:
                    # export: the axis empty is Rx(+90), so the key carries the
                    # permutation that turns it into the same world map.
                    # Rx(+90) @ (v1,v2,v0) == (y,-x,z).
                    loc = Vector((float(v[1]), float(v[2]), float(v[0])))
                for i in range(3):
                    _key(root_bag, "location", i, group, fr, loc[i])
            elif ch_name == "unnamed_o":
                if session_source:
                    # session: the empty sits above the root and the bones, and
                    # the bones are raw session space too, so the whole stack is
                    # mapped once by the empty. The root's own rotation is then
                    # just the session's quaternion, DMX (x,y,z,w) reordered to
                    # mathutils (w,x,y,z). No remap, no conjugation - adding one
                    # here would rotate a character that SFM left unrotated.
                    q = Quaternion((float(v[3]), float(v[0]),
                                    float(v[1]), float(v[2])))
                else:
                    # export: root quat needs conjugation + axis remap vs
                    # per-bone quats (Evan Purr fix - world-space root vs BST
                    # bone-space pipeline)
                    q_bst    = Quaternion((-float(v[3]), -float(v[1]), float(v[0]), -float(v[2])))
                    axis_mat = Matrix.Rotation(-pi / 2, 4, 'X')
                    q        = (axis_mat @ q_bst.to_matrix().to_4x4() @ axis_mat.inverted()).to_quaternion()
                for i in range(4):
                    _key(root_bag, "rotation_quaternion", i, group, fr, q[i])
            elif ch_name in ROOT_SCALE_CHANNELS:
                _add_scale_keys(root_bag, "scale", group, fr, v,
                                span=_rescale_span(ch))

    for fc in iter_fcurves(action, armature):
        fc.update()
    root_curves = 0
    if root_action:
        for fc in iter_fcurves(root_action, root_empty):
            fc.update()
        root_curves = count_fcurves(root_action, root_empty)

    if unresolved_scale:
        print(f"[DMX_ANIM]  {len(unresolved_scale)} scale channel(s) matched "
              f"no bone on this rig: "
              + ", ".join(unresolved_scale[:6])
              + (" ..." if len(unresolved_scale) > 6 else ""))

    return {
        "scale_bones": scale_bones,
        "scale_keys":  scale_keys,
        "scale_unresolved": unresolved_scale,
        "root_curves": root_curves,
        "root_action": root_action,
        "root_empty":  root_empty,
    }


# ──────────────────────────────────────────────────────────────────────────────
# stepped keys
# ──────────────────────────────────────────────────────────────────────────────
#
# SFM DOES NOT KEY ON WHOLE FRAMES, AND IT WRITES A HOLD AS A PAIR.
#
# Measured on `new session.dmx` at 24 fps. One bone channel's key times, in
# frames:  123.1992  126.9984  127.0008  127.2000  127.9992 ...
# Two things are going on there and both hurt:
#
# 1  almost nothing lands on a whole frame. 267 of that channel's 719 keys
# are more than 0.01 of a frame off one
# 2  126.9984 and 127.0008 are 0.0024 of a frame apart. That pair IS the
# step - it's how SFM writes "hold, then jump". Blender only ever
# EVALUATES whole frames, so frame 127 lands exactly between the two
# keys and returns the halfway value. The step is not just softened, it
# is sampled at the one instant that belongs to neither side of it.
#
# Import_DMX_Camera has always dealt with this, in its raw/stepped path:
# resample onto every integer frame by linear interpolation between the
# bracketing SFM samples, and key LINEAR. The animation importer never did -
# it took whatever fractional key times BST wrote. Same data, same problem,
# and the fix is the same one, so it is the same shape of code here
#
# WHY LINEAR and not CONSTANT. A hold-previous resample turns every smooth
# pan into a staircase, because SFM's data is a mix of smooth motion and hard
# cuts with nothing marking which is which. Linear between the surrounding
# samples keeps a smooth move smooth, while a step still reads as a
# near-vertical one-frame jump - its two samples are 0.0024 frames apart, so
# the ramp between them is invisible
#
# AUTO only touches curves that actually contain a step, so an ordinary
# smooth take keeps its original keys and its original key count

STEP_GAP_FRAMES = 0.5      # two keys closer than this are a step, not motion
SNAP_EPS_FRAMES = 0.01     # SFM's own jitter is about +/-0.0008 of a frame
MAX_RESAMPLE_FRAMES = 20000


def _curve_samples(fc):
    """[(frame, value)] sorted by frame."""
    return sorted(((kp.co[0], kp.co[1]) for kp in fc.keyframe_points),
                  key=lambda s: s[0])


def count_stepped(fc, gap=STEP_GAP_FRAMES):
    """How many adjacent key pairs in *fc* are a step rather than motion.

    A step is two keys almost on top of each other in TIME carrying a value
    change that is real against this curve's own amplitude. The amplitude test
    matters: floating-point noise between two 0.002-frame-apart keys is not a
    step, and calling it one would resample the whole file for nothing."""
    kps = fc.keyframe_points
    if len(kps) < 2:
        return 0
    vals = [kp.co[1] for kp in kps]
    amp = max(vals) - min(vals)
    thresh = max(1e-6, amp * 0.01)
    steps = 0
    for i in range(1, len(kps)):
        dx = kps[i].co[0] - kps[i - 1].co[0]
        if dx <= 0.0:
            steps += 1                      #duplicate or out-of-order time
        elif dx < gap and abs(kps[i].co[1] - kps[i - 1].co[1]) > thresh:
            steps += 1
    return steps


def snap_near_integer(fc, eps=SNAP_EPS_FRAMES):
    """Move keys that sit within *eps* of a whole frame onto it.

    SFM keys a 24 fps take at 4.0008 / 4.9992 / 6.0000 - about a thousandth of
    a frame out. That is not intent, it is the timeline's own resolution, and
    leaving it means no key is ever exactly where Blender evaluates. Any
    epsilon near 1e-6 in a frame comparison is wrong for this data; 0.01 is
    what the camera importer settled on."""
    moved = 0
    for kp in fc.keyframe_points:
        f = kp.co[0]
        r = round(f)
        if f != r and abs(f - r) <= eps:
            dx = r - f
            kp.co[0] = r
            kp.handle_left[0] += dx
            kp.handle_right[0] += dx
            moved += 1
    return moved


def resample_integer(fc):
    """Rewrite *fc* with one LINEAR key on every whole frame it spans.

    Values come from linear interpolation between the bracketing ORIGINAL
    samples, so the curve's shape is preserved and a step stays a step.
    Returns the number of keys written, or 0 if nothing was done."""
    import math
    samples = _curve_samples(fc)
    if len(samples) < 2:
        return 0
    f_lo = int(math.floor(samples[0][0]))
    f_hi = int(math.ceil(samples[-1][0]))
    span = f_hi - f_lo + 1
    if span < 2 or span > MAX_RESAMPLE_FRAMES:
        # A curve spanning more frames than this is not an SFM take; it's a
        # bad time conversion. Resampling it would hang Blender, so say so
        # and leave the original keys alone
        if span > MAX_RESAMPLE_FRAMES:
            print(f"[DMX_ANIM]  resample SKIPPED for {fc.data_path}[{fc.array_index}]"
                  f" - {span} frames is beyond MAX_RESAMPLE_FRAMES")
        return 0

    out = []
    n = len(samples)
    si = 0
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
            v = v1 if f1 == f0 else v0 + (v1 - v0) * ((frame - f0) / (f1 - f0))
        out.append((float(frame), float(v)))

    fc.keyframe_points.clear()
    fc.keyframe_points.add(len(out))
    for kp, (f, v) in zip(fc.keyframe_points, out):
        kp.co = (f, v)
        kp.interpolation = 'LINEAR'
        kp.handle_left = (f - 0.333, v)
        kp.handle_right = (f + 0.333, v)
    fc.update()
    return len(out)


def fix_action_quat_flips(action, owner):
    """Negate quaternion keyframes where dot(prev, curr) < 0, per bone.

    THE CAMERA IMPORTER HAS ALWAYS HAD THIS; the animation importer never
    did, and the gap is measurable on real files: bezi2.dmx imports with 70
    sign flips across 5 bones, and a flipped pair makes Blender interpolate
    the LONG way round - the left thigh swings 177 degrees in one frame.
    That is the classic "euler spins / jerky animation" complaint on BONES,
    and the red Delete Euler Spins repair operator existed largely to clean
    it up after the fact. Fix it at import, like the camera does.

    q and -q are the SAME rotation, so negating a key never changes any
    posed frame - only the interpolation between keys, always to the short
    way. That also makes this safe to run before the stepped-key resample:
    resample_integer lerps components, and lerping across a sign flip goes
    through zero and bakes garbage onto every integer frame in the gap, so
    this MUST run first.

    Works on any action: bone curves (pose.bones["X"].rotation_quaternion)
    and the root empty's rotation_quaternion alike, grouped by data_path.
    A group with unequal key counts across its four components is skipped
    with a console line, same policy as the camera's fixer.

    Returns {"groups": n, "flipped_keys": m, "skipped": k}.
    """
    out = {"groups": 0, "flipped_keys": 0, "skipped": 0}
    if action is None:
        return out

    by_path = {}
    for fc in iter_fcurves(action, owner):
        if fc.data_path.endswith("rotation_quaternion") and 0 <= fc.array_index <= 3:
            by_path.setdefault(fc.data_path, [None] * 4)[fc.array_index] = fc

    for path, fcs in by_path.items():
        if not all(fcs):
            continue
        n = len(fcs[0].keyframe_points)
        if any(len(fc.keyframe_points) != n for fc in fcs[1:]):
            print(f"[DMX_ANIM]  quat flip fix SKIPPED for {path} - "
                  f"mismatched key counts across components")
            out["skipped"] += 1
            continue
        if n < 2:
            continue
        out["groups"] += 1
        prev = [fcs[c].keyframe_points[0].co[1] for c in range(4)]
        for i in range(1, n):
            curr = [fcs[c].keyframe_points[i].co[1] for c in range(4)]
            if sum(a * b for a, b in zip(prev, curr)) < 0.0:
                for c in range(4):
                    kp = fcs[c].keyframe_points[i]
                    kp.co[1]           = -curr[c]
                    kp.handle_left[1]  = -kp.handle_left[1]
                    kp.handle_right[1] = -kp.handle_right[1]
                curr = [-v for v in curr]
                out["flipped_keys"] += 1
            prev = curr
    return out


def fix_stepped_keys(action, owner, mode='AUTO'):
    """Apply the stepped-key treatment to every curve of one action.

    mode  AUTO  snap near-integer keys everywhere, resample only the curves
                that contain a detected step
          ALL   resample every curve onto integer frames
          OFF   do nothing

    Returns a dict of counts - what to print, and what a test asserts on."""
    out = {"curves": 0, "stepped_curves": 0, "resampled_curves": 0,
           "keys_before": 0, "keys_after": 0, "snapped": 0, "steps": 0}
    if action is None or mode == 'OFF':
        return out

    quat_groups = {}
    curves = list(iter_fcurves(action, owner))
    stepped = {}
    for fc in curves:
        stepped[fc] = count_stepped(fc)
        if fc.data_path.endswith("rotation_quaternion") and 0 <= fc.array_index <= 3:
            quat_groups.setdefault(fc.data_path, [None] * 4)[fc.array_index] = fc
    force = set()
    for path, fcs in quat_groups.items():
        if all(fcs) and (mode == 'ALL' or any(stepped[fc] for fc in fcs)):
            force.update(fcs)
    out["quat_groups_resampled"] = 0

    for fc in curves:
        out["curves"] += 1
        before = len(fc.keyframe_points)
        out["keys_before"] += before

        steps = stepped[fc]
        if steps:
            out["stepped_curves"] += 1
            out["steps"] += steps

        if mode == 'AUTO':
            out["snapped"] += snap_near_integer(fc)

        if mode == 'ALL' or steps or fc in force:
            written = resample_integer(fc)
            if written:
                out["resampled_curves"] += 1
                out["keys_after"] += written
                continue
        out["keys_after"] += len(fc.keyframe_points)

    for path, fcs in quat_groups.items():
        if all(fcs) and fcs[0] in force:
            if _normalise_quat_group(fcs):
                out["quat_groups_resampled"] += 1
    return out


def _normalise_quat_group(fcs):
    """After a coherent resample: unit length on every key, and each key in
    the same hemisphere as the one before it. Returns False (and leaves the
    curves alone) if the four do not line up key for key."""
    n = len(fcs[0].keyframe_points)
    if n < 1 or any(len(fc.keyframe_points) != n for fc in fcs[1:]):
        print(f"[DMX_ANIM]  quat normalise SKIPPED for {fcs[0].data_path} - "
              f"key counts {[len(fc.keyframe_points) for fc in fcs]}")
        return False
    prev = None
    for i in range(n):
        q = [fcs[c].keyframe_points[i].co[1] for c in range(4)]
        length = sum(v * v for v in q) ** 0.5
        if length < 1e-9:
            q = list(prev) if prev else [1.0, 0.0, 0.0, 0.0]
        else:
            q = [v / length for v in q]
        if prev is not None and sum(a * b for a, b in zip(prev, q)) < 0.0:
            q = [-v for v in q]
        for c in range(4):
            kp = fcs[c].keyframe_points[i]
            f = kp.co[0]
            kp.co = (f, q[c])
            kp.handle_left = (f - 0.333, q[c])
            kp.handle_right = (f + 0.333, q[c])
        prev = q
    for fc in fcs:
        fc.update()
    return True


# ──────────────────────────────────────────────────────────────────────────────
# public api
# ──────────────────────────────────────────────────────────────────────────────

def _apply_anim_scale(action, root_action, factor: float) -> int:
    """Multiply every location key (bones + root) by *factor*, handles too.
    Rotation and scale channels are left alone. Returns curves touched."""
    from ..core import anim_compat
    touched = 0
    for act in (action, root_action):
        if act is None:
            continue
        for fc in anim_compat.iter_fcurves(act):
            dp = fc.data_path
            if not (dp == "location" or dp.endswith(".location")):
                continue
            for kp in fc.keyframe_points:
                kp.co[1]           *= factor
                kp.handle_left[1]  *= factor
                kp.handle_right[1] *= factor
            fc.update()
            touched += 1
    return touched



_BUILD_DEFAULT_BONE = 2.0     # leaf bones, in DMX units
_BUILD_MIN_BONE = 0.02        # Blender deletes any bone shorter than this
_NOT_A_BONE = {"unnamed"}
_UP_MATS = {"Y": Matrix.Rotation(pi / 2, 4, "X"), "Z": Matrix(),
            "X": Matrix.Rotation(-pi / 2, 4, "Y")}


def _dmx_quat(q):
    """DMX stores quaternions (x, y, z, w); Blender wants (w, x, y, z)."""
    return Quaternion([q[3], q[0], q[1], q[2]])


def _joint_local_matrix(joint):
    """One joint's bind transform in its parent's space - translation, then
    rotation, the order the animation channels are set in too."""
    transform = joint.get("transform")
    if transform is None:
        return Matrix()
    mat = Matrix()
    pos = transform.get("position")
    if pos is not None:
        mat = Matrix.Translation(Vector((float(pos[0]), float(pos[1]),
                                         float(pos[2]))))
    ori = transform.get("orientation")
    if ori is not None:
        mat = mat @ _dmx_quat(ori).to_matrix().to_4x4()
    return mat


def read_skeleton(model):
    """[name, joint, parent index] PARENT-FIRST; -1 at the top. A skipped joint
    hands its parent down, so dropping one never orphans its branch."""
    skeleton = model.root.get("skeleton")
    if skeleton is None:
        return []
    out = []

    def walk(element, parent_index):
        name = (element.name or "").strip()
        if not name or name.lower() in _NOT_A_BONE:
            index = parent_index
        else:
            out.append([name, element, parent_index])
            index = len(out) - 1
        for kid in (element.get("children") or []):
            walk(kid, index)

    for top in (skeleton.get("children") or []):
        walk(top, -1)
    return out


def animated_bone_names(model):
    """Lowercased names of every element the animation keys."""
    root = model.root
    anim_list = root.get("animationList")
    anims = anim_list.get("animations") if anim_list is not None else None
    if not anims and "channelsClip" in root:
        anims = [root["channelsClip"]]
    if not anims:
        return set()
    names = set()
    for channel in (anims[0].get("channels") or []):
        to_elem = channel.get("toElement")
        if to_elem is None or channel.get("toAttribute", "") not in (
                "position", "orientation"):
            continue
        name = (to_elem.name or "").strip().lower()
        if name and name not in _NOT_A_BONE:
            names.add(name)
    return names


def build_armature_from_dmx(model, name, collection=None):
    """A Blender armature matching the .dmx's own skeleton, at its bind pose.
    Returns the armature object."""
    import collections as _collections
    joints = read_skeleton(model)
    if not joints:
        raise RuntimeError(
            "This .dmx has no skeleton in it, so there is no rig to build. "
            "Select the model's armature and import again.")
    world = []
    for _name, element, parent in joints:
        local = _joint_local_matrix(element)
        world.append(local if parent < 0 else world[parent] @ local)

    #length is cosmetic - poses go thru matrices - but a rig you cannot
    #see is a rig you cannot check: reach to the nearest child, else half
    #the parent
    children_of = _collections.defaultdict(list)
    for index, (_n, _e, parent) in enumerate(joints):
        if parent >= 0:
            children_of[parent].append(index)
    lengths = [0.0] * len(joints)
    for index in range(len(joints)):
        head = world[index].translation
        reach = [(world[k].translation - head).length
                 for k in children_of.get(index, [])]
        reach = [d for d in reach if d > _BUILD_MIN_BONE]
        if reach:
            lengths[index] = min(reach)
        else:
            parent = joints[index][2]
            plen = lengths[parent] if parent >= 0 else 0.0
            lengths[index] = (plen * 0.5) if plen else _BUILD_DEFAULT_BONE
        lengths[index] = max(lengths[index], _BUILD_MIN_BONE)

    arm_data = bpy.data.armatures.new(name)
    armature = bpy.data.objects.new(name, arm_data)
    (collection or bpy.context.scene.collection).objects.link(armature)
    prev = bpy.context.view_layer.objects.active
    if prev is not None and prev.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:                                     # noqa: BLE001
            pass
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = []
    for index, (bone_name, _e, _p) in enumerate(joints):
        eb = arm_data.edit_bones.new(bone_name)
        #Length first: EditBone.matrix keeps the length it finds, and a
        #zero-length bone is dropped on the way out of edit mode
        eb.tail = (0.0, lengths[index], 0.0)
        eb.matrix = world[index]
        edit_bones.append(eb)
    for index, (_n, _e, parent) in enumerate(joints):
        if parent >= 0:
            edit_bones[index].parent = edit_bones[parent]
            edit_bones[index].use_connect = False
    final = [eb.name for eb in edit_bones]
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = armature
    renamed = [(joints[i][0], final[i]) for i in range(len(joints))
               if final[i] != joints[i][0]]
    if renamed:
        print(f"[DMX_ANIM]  WARNING: Blender renamed {len(renamed)} bone(s): "
              + ", ".join(f"{a} -> {b}" for a, b in renamed[:6]))
    animated = animated_bone_names(model)
    covered = len(animated & {n.lower() for n in final})
    print(f"[DMX_ANIM]  built rig '{armature.name}': {len(final)} bone(s) from "
          f"the file's skeleton, {covered}/{len(animated)} animated bone(s)")
    armature["ht_built_from_dmx"] = True
    return armature


def resolve_armature(armature, model, rig_mode, fallback_name, collection=None):
    """What the animation lands on: (armature, was_built).

    AUTO uses the selected rig when it has bones this file animates, and builds
    one otherwise - and says so, because quietly ignoring the selection would be
    worse. SELECTED never builds; BUILD always does."""
    animated = animated_bone_names(model)
    if armature is not None and armature.type != "ARMATURE":
        armature = None
    if rig_mode == "BUILD":
        return build_armature_from_dmx(model, fallback_name, collection), True
    if armature is not None:
        have = {pb.name.lower() for pb in armature.pose.bones}
        matched = len(animated & have)
        if matched or rig_mode == "SELECTED":
            if rig_mode == "SELECTED" and not matched:
                raise RuntimeError(
                    f"'{armature.name}' has none of the {len(animated)} bones "
                    "this animation keys. Select the right rig, or set Rig to "
                    "Auto and let the file's own skeleton be built.")
            return armature, False
        print(f"[DMX_ANIM]  '{armature.name}' matches 0 of {len(animated)} "
              f"animated bone(s) - building a rig from the file instead")
    elif rig_mode == "SELECTED":
        raise RuntimeError("No armature selected - select the model's "
                           "armature, or set Rig to Auto.")
    return build_armature_from_dmx(model, fallback_name, collection), True


def import_dmx_animation(dmx_path, armature, add_root_helpers: bool = True,
                         anim_scale: float = 1.0, up_axis: str = 'FILE',
                         stepped_keys: str = 'AUTO',
                         rot_mode: str = ROT_MODE_DEFAULT,
                         fix_quat_flips: bool = True):
    """
    Import an SFM DMX animation onto *armature*.

    Parameters
    ──────────
    dmx_path         : str | Path          path to the .dmx file
    armature         : bpy.types.Object    must be type 'ARMATURE'
    add_root_helpers : bool
        True  — create the axis + root empty hierarchy (the +90° X correction
                and unnamed_p/unnamed_o root motion). Default; correct for
                normal SFM-to-Blender work.
        False — skip the root empty entirely and import bone (+ scale) channels
                only. Use for clean SMD export, where the extra root transform
                breaks the hierarchy Source expects.

    Returns
    ───────
    {
        "action"      : bpy.types.Action,
        "root_action" : bpy.types.Action | None,
        "root_empty"  : bpy.types.Object | None,
        "scale_bones" : int,
        "root_curves" : int,
    }

    Raises FileNotFoundError, TypeError, RuntimeError on hard failures.
    """
    dmx_path = Path(dmx_path)
    if not dmx_path.exists():
        raise FileNotFoundError(f"DMX file not found: {dmx_path}")
    if armature.type != "ARMATURE":
        raise TypeError(f"Expected ARMATURE, got '{armature.type}'")

    resolved_axis = None
    if up_axis == 'FILE':
        resolved_axis = read_file_up_axis(dmx_path)
    elif up_axis in ("X", "Y", "Z"):
        resolved_axis = up_axis

    # what THE FILE SAYS vs WHO ACTS ON IT - two different questions
    #
    # resolved_axis is the file's answer ('Y' for every SFM DMX). It decides
    # whether a correction is NEEDED. It must not be handed to BST: on an
    # existing armature BST cannot apply it and only seeds the root bone with
    # the inverse, laying the character down (see _get_or_create_axis_empty for
    # the measurement). So BST is always run at its 'Z' no-op default and the
    # axis empty performs the correction
    # 'Y' = SFM export (model data converted to Y-up by SFM's exporter)
    # 'Z' = session extract (raw Source Z-up, declared honestly by
    # Session_Reader.extract_set)
    # Anything unstated is treated as an export, which is what every file
    # predating session extraction actually is
    source_axis = 'Z' if resolved_axis == 'Z' else 'Y'

    # Before BST runs: BST cannot add bones during an animation job, so any
    # root-level control the file animates - viewTarget above all - has to
    # exist on the rig first or its channel is dropped with a console line
    # and nothing else
    try:
        added_bones = ensure_file_root_bones(dmx_path, armature,
                                             up_axis=resolved_axis)
    except Exception as exc:
        print(f"[DMX_ANIM]  root-bone check WARNING: {exc}")
        added_bones = []

    action = _run_bst_import(dmx_path, armature, up_axis=None, rot_mode=rot_mode)
    print(f"[DMX_ANIM]  BST imported action '{action.name}'  "
          f"(file up axis {resolved_axis or 'unstated'}; correction on the "
          f"axis empty, not BST)")

    try:
        patch = _patch_scale_and_root(dmx_path, armature, action,
                                      source_axis=source_axis,
                                      add_root_helpers=add_root_helpers)
    except Exception as exc:
        print(f"[DMX_ANIM]  patch WARNING: {exc}")
        patch = _no_patch()

    # Quaternion sign flips. Must run BEFORE the stepped-key pass:
    # resample_integer lerps components, and lerping across a sign flip
    # passes through zero and bakes the artifact onto every integer frame
    # in the gap. Negating a key never changes a posed frame (q == -q as a
    # rotation), so this is safe on every file; unlike the camera's raw
    # path there's nothing here for it to destroy
    flips = {"groups": 0, "flipped_keys": 0, "skipped": 0}
    if fix_quat_flips:
        try:
            for act, owner in ((action, armature),
                               (patch["root_action"], patch["root_empty"])):
                if act is None:
                    continue
                r = fix_action_quat_flips(act, owner)
                for k in flips:
                    flips[k] += r[k]
            if flips["flipped_keys"]:
                print(f"[DMX_ANIM]  quat flip fix: {flips['flipped_keys']} "
                      f"key(s) negated across {flips['groups']} rotation "
                      f"group(s) - interpolation forced to the short way")
        except Exception as exc:
            print(f"[DMX_ANIM]  quat flip WARNING: {exc}")

    # Stepped keys. Must run AFTER the patch pass, so the scale and root
    # curves it writes get the same treatment as BST's bone curves - a root
    # transform cut on a fractional frame is exactly as invisible as a bone
    # one. Runs before _apply_anim_scale, which only multiplies values and
    # does not care how many keys there are
    stepped = {"curves": 0, "stepped_curves": 0, "resampled_curves": 0,
               "keys_before": 0, "keys_after": 0, "snapped": 0, "steps": 0, "quat_groups_resampled": 0}
    if stepped_keys != 'OFF':
        try:
            for act, owner in ((action, armature),
                               (patch["root_action"], patch["root_empty"])):
                if act is None:
                    continue
                r = fix_stepped_keys(act, owner, mode=stepped_keys)
                for k in stepped:
                    stepped[k] += r[k]
            if stepped["stepped_curves"] or stepped["resampled_curves"]:
                print(f"[DMX_ANIM]  stepped: {stepped['steps']} step(s) across "
                      f"{stepped['stepped_curves']} curve(s); resampled "
                      f"{stepped['resampled_curves']}/{stepped['curves']} onto "
                      f"whole frames ({stepped['keys_before']} -> "
                      f"{stepped['keys_after']} keys); "
                      f"{stepped['snapped']} key(s) snapped; "
                      f"{stepped['quat_groups_resampled']} rotation(s) "
                      f"resampled as whole quaternions")
            else:
                print(f"[DMX_ANIM]  stepped: none detected in "
                      f"{stepped['curves']} curve(s); "
                      f"{stepped['snapped']} key(s) snapped to whole frames")
        except Exception as exc:
            print(f"[DMX_ANIM]  stepped-key WARNING: {exc}")

    #1.16.0: the first flip pass ran on the keys as BST wrote them; the
    #stepped pass may then have rewritten some groups. One more walk on the
    #result costs nothing on a clean file and guarantees nothing leaves this
    #function going the long way round
    if fix_quat_flips:
        try:
            late = 0
            for act, owner in ((action, armature),
                               (patch["root_action"], patch["root_empty"])):
                if act is not None:
                    late += fix_action_quat_flips(act, owner)["flipped_keys"]
            if late:
                print(f"[DMX_ANIM]  quat flip fix after stepped pass: {late} "
                      f"key(s) negated")
        except Exception as exc:                              # noqa: BLE001
            print(f"[DMX_ANIM]  late quat flip WARNING: {exc}")

    scaled_curves = 0
    if anim_scale != 1.0:
        try:
            scaled_curves = _apply_anim_scale(action, patch["root_action"], anim_scale)
            print(f"[DMX_ANIM]  anim scale ×{anim_scale:g} on {scaled_curves} curve(s)")
        except Exception as exc:
            print(f"[DMX_ANIM]  anim scale WARNING: {exc}")

    print(f"[DMX_ANIM]  done — scale: {patch['scale_bones']} bone(s) / "
          f"{patch['scale_keys']} key(s), "
          f"root: {patch['root_curves']} F-curve(s)"
          + ("" if add_root_helpers else "  (root helpers disabled — SMD-clean)"))

    return {
        "action":        action,
        "root_action":   patch["root_action"],
        "root_empty":    patch["root_empty"],
        "scale_bones":   patch["scale_bones"],
        "scale_keys":    patch["scale_keys"],
        "scale_unresolved": patch["scale_unresolved"],
        "root_curves":   patch["root_curves"],
        "added_bones":   added_bones,
        "anim_scale":    anim_scale,
        "scaled_curves": scaled_curves,
        "stepped":       stepped,
        "quat_flips":    flips,
    }


# ──────────────────────────────────────────────────────────────────────────────
# operator
# ──────────────────────────────────────────────────────────────────────────────

@start_folders.browser_at("animation")          #3.0.0: opens where you work, learns your folder
class HT_OT_ImportDmxAnimation(Operator, ImportHelper):
    """PICK .dmx (animation) - ONE file. Onto the SELECTED ARMATURE, or onto a
        rig built from the file's own skeleton when nothing matching is selected

        Put SFM bone animation from one .dmx onto a rig

Rig = Auto (default): the selected armature when it has bones this file
animates, otherwise an armature is built from the skeleton the .dmx carries
- no model needed.

WHAT COMES ACROSS
  bones  every position/orientation channel, via Blender Source Tools
  scale  SFM stores bone scale as a normalised slider behind a lerp()
         operator, not as a scale - read raw it shrinks a bone to a
         tenth of its size
  root   the game model's own placement, onto a root empty the rig is
         parented to, so the character stands where SFM put it
  eyes   a viewTarget the file animates is pre-created if the rig lacks
         it, because BST cannot add bones mid-animation
    """
    # BELOW the TOOLTIP CAP. Blender truncates an operator description
    # at 1023 characters, without a warning, mid-word. These paragraphs
    # were part of the docstring and were already being cut off before
    # anyone could read them, so they live here instead - kept, but out
    # of the tooltip's budget
    # STEPPED KEYS: SFM writes a HOLD as two keys a thousandth of a frame
    # apart and Blender evaluates only whole frames, so a step lands between
    # its own two keys and reads as a ramp. Stepped Keys resamples them
    #
    # Options live in the file browser sidebar; there's no redo panel
    #

    bl_idname  = "ht.import_dmx_animation"
    bl_label   = "DMX Animation"
    # NO "REGISTER" - see the note in Report_UI/the constitution
    # REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    # touching any field in it RE-RUNS this operator. Re-running an
    # import re-reads the DMX and rebuilds every f-curve; nudging Scale
    # there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    # with the value you wanted is the safe way to change your mind
    bl_options = {"UNDO"}

    filename_ext = ".dmx"
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})

    add_root_helpers: BoolProperty(
        name="Add Root Transform",
        description=(
            "Create the axis + root empty hierarchy and key the root "
            "game-model motion (unnamed_p/unnamed_o) onto it. KEEP ON for "
            "normal SFM-to-Blender work. Turn OFF for clean SMD export later — "
            "the extra root transform breaks the bone hierarchy Source expects, "
            "so disabling it imports bone channels only"
        ),
        default=True,
    )

    # [roadmap #1] precision 6 / step 1 / min 1e-6 - see Common_Props.
    anim_scale: FloatProperty(**Common_Props.scale_prop(
        name="Animation Scale",
        description=(
            "Multiply every location key (bone locations + root motion) by "
            "this factor after import. 1.0 imports the animation untouched. "
            "Use when the target model was resized: a model at 0.5x scale "
            "needs its animation at 0.5 too, or the rig walks in place while "
            "the root flies off. Rotations are never touched. "
            "Full precision is kept - Hammer Unit conversion needs far more "
            "than three decimals"
        ),
    ))

    scale_preset: EnumProperty(**Common_Props.scale_preset_prop())

    rot_mode: EnumProperty(  # type: ignore
        name="Bone Rotation",
        description=("How bone rotation is stored on the rig.\n\nQUATERNION is what the file already holds - a DmeQuaternionLog - and what SFM interpolates. It cannot gimbal-lock, so a bone passing through a pole stays smooth.\n\nXYZ EULER is Blender Source Tools' own default and converts every frame independently, with no memory of the frame before. Measured on gman's pelvis: as Y crossed 90 degrees at frame 151 the X and Z channels swung a hundred degrees in three frames while the actual orientation moved under two - a violent curve on a correct pose. Choose it only if you intend to hand-animate in euler on top"),
        items=[
            ('QUATERNION', "Quaternion",
             "As the file stores it. Cannot gimbal-lock. The default"),
            ('XYZ', "XYZ Euler",
             "Blender Source Tools' default. Can flip at a pole"),
        ],
        default='QUATERNION',
    )

    stepped_keys: EnumProperty(  # type: ignore
        name="Stepped Keys",
        description=(
            "SFM does not key on whole frames, and it writes a HOLD as two "
            "keys about a thousandth of a frame apart. Blender only ever "
            "evaluates whole frames, so a step that falls between two of them "
            "is sampled at the one instant belonging to neither side - the "
            "cut is not just softened, it is missed.\n\n"
            "AUTO snaps near-integer keys onto whole frames everywhere, and "
            "rewrites only the curves that actually contain a step so they "
            "carry one LINEAR key per frame. This is what the camera importer "
            "has always done.\n\n"
            "ALL rewrites every curve that way - bigger actions, and no "
            "reason to unless something still looks soft.\n\n"
            "OFF keeps the raw fractional key times Blender Source Tools "
            "wrote"),
        items=[
            ('AUTO', "Auto",
             "Snap near-integer keys; resample only curves with a step"),
            ('ALL', "All Curves",
             "Resample every curve onto whole frames"),
            ('OFF', "Off",
             "Keep the raw fractional key times from the file"),
        ],
        default='AUTO',
    )

    fix_quat_flips: BoolProperty(  # type: ignore
        name="Fix Quaternion Flips",
        description=(
            "Negate rotation keys where dot(prev, curr) goes negative, per "
            "bone, so interpolation always takes the short way round. A "
            "flipped pair otherwise makes a limb swing up to 180 degrees "
            "between two frames - measured 70 flips on one real character, "
            "left thigh snapping 177 degrees in one frame.\n\n"
            "q and -q are the same rotation, so no posed frame ever changes "
            "- only the path between keys. The camera importer has always "
            "done this; leave it on unless you are diffing raw curves "
            "against the file"),
        default=True,
    )

    up_axis: EnumProperty(  # type: ignore
        name="Up Axis",
        description=(
            "Which axis the source file treats as up.\n\n"
            "FROM FILE reads skeleton.upAxis out of the DMX, which every SFM "
            "export sets to Y. Blender Source Tools otherwise takes this "
            "from a scene setting that defaults to Z, and a Z up axis "
            "applies NO correction at all - which is what leaves a Y-up "
            "file rotated.\n\n"
            "Pick an axis explicitly only to override what the file says"),
        items=[
            ('FILE', "From File", "Read skeleton.upAxis out of the DMX"),
            ('SCENE', "Scene Default",
             "Leave it to Blender Source Tools' scene setting"),
            ('Y', "Y", "Force Y up - SFM's own convention"),
            ('Z', "Z", "Force Z up - no correction"),
            ('X', "X", "Force X up"),
        ],
        default='FILE',
    )

    rig_mode: EnumProperty(  # type: ignore
        name="Rig",
        description=("What the animation lands on.\n"
                     "THIS FEATURE WAS ADDED IN VERSION 1.18.0 AND IS IN "
                     "EXPERIMENTAL STAGE"),
        items=[('AUTO', "Auto",
                "The selected armature if it has bones this file animates, "
                "otherwise build one from the file's own skeleton"),
               ('SELECTED', "Selected Armature",
                "Only the selected armature - never build"),
               ('BUILD', "Build From File",
                "Always build a new armature from the file's skeleton")],
        default='AUTO',
    )

    # [roadmap #2] standalone defaults to BST-like behaviour
    import_profile: EnumProperty(
        **Common_Props.profile_prop(default=Common_Props.PROFILE_BST))

    def invoke(self, context, event):
        # [roadmap #2] Make the panel honest from the first draw: the profile
        # says BST-like, so the settings under it must already BE BST-like
        # Without this the enum would advertise one thing and the checkbox
        # below it would show another until the user touched the enum.
        for attr, value in Common_Props.profile_defaults(
                self.import_profile).items():
            if hasattr(self, attr):
                setattr(self, attr, value)
        return super().invoke(context, event)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "rig_mode")
        col.separator()
        col.prop(self, "import_profile")
        if self.import_profile == Common_Props.PROFILE_BST:
            note = col.box().column(align=True)
            note.scale_y = 0.85
            note.label(text="BST-like: bone channels only.", icon='INFO')
            note.label(text="Root motion in the file is skipped.")
            note.label(text="Session-aware keeps it.")
        col.separator()
        col.prop(self, "add_root_helpers")
        if not self.add_root_helpers:
            box = col.box()
            box.label(text="SMD-clean: no root transform", icon="INFO")
            box.label(text="bone channels only")
        col.separator()
        col.prop(self, "up_axis")
        col.separator()
        col.prop(self, "stepped_keys")
        col.prop(self, "fix_quat_flips")
        col.separator()
        Common_Props.draw_scale(col, self, "anim_scale")

    def execute(self, context):
        selected = context.active_object
        built = False
        try:
            model = _get_datamodel().load(str(self.filepath))
            armature, built = resolve_armature(
                selected, model, self.rig_mode, Path(self.filepath).stem)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        if built and not self.add_root_helpers:
            # no axis empty is coming to carry the up-axis turn, so it goes on
            # the armature itself (BST's own new-armature behaviour). With Add
            # Root Transform on, the axis empty carries it - not twice.
            ax = read_file_up_axis(self.filepath) if self.up_axis in ('FILE', 'SCENE') \
                else self.up_axis
            armature.matrix_basis = _UP_MATS.get((ax or "Y").upper(), _UP_MATS["Y"])

        try:
            axis = None if self.up_axis == 'SCENE' else self.up_axis
            result = import_dmx_animation(
                self.filepath, armature,
                add_root_helpers=self.add_root_helpers,
                anim_scale=self.anim_scale,
                up_axis=(axis or 'SCENE'),
                stepped_keys=self.stepped_keys,
                rot_mode=self.rot_mode,
                fix_quat_flips=self.fix_quat_flips)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        action = result["action"]
        lines  = [
            f"File   : {Path(self.filepath).name}",
            (f"Rig    : built from the file's skeleton - '{armature.name}', "
             f"{len(armature.data.bones)} bone(s)" if built
             else f"Rig    : {armature.name}"),
            f"Action : {action.name}",
            f"Frames : {action.frame_range[0]:.0f} – {action.frame_range[1]:.0f}",
        ]
        if result["scale_bones"]:
            lines.append(f"Scale  : {result['scale_bones']} bone(s), "
                         f"{result['scale_keys']} key(s)")
        st = result.get("stepped") or {}
        if st.get("resampled_curves"):
            lines.append(f"Stepped: {st['steps']} step(s) in "
                         f"{st['stepped_curves']} curve(s) - resampled "
                         f"{st['resampled_curves']} curve(s) onto whole frames")
        elif st.get("snapped"):
            lines.append(f"Stepped: none; {st['snapped']} key(s) snapped "
                         f"to whole frames")
        qf = result.get("quat_flips") or {}
        if qf.get("flipped_keys"):
            lines.append(f"Flips  : {qf['flipped_keys']} rotation key(s) "
                         f"negated to force short-way interpolation")
        if self.anim_scale != 1.0:
            lines.append(f"Factor : x{self.anim_scale:.6g} on "
                         f"{result.get('scaled_curves', 0)} curve(s)")
        if result.get("added_bones"):
            #say it out loud. A rig that arrives without viewTarget looks
            #exactly like a rig whose viewTarget simply is not animated
            lines.append(f"Bones  : added {', '.join(result['added_bones'])} "
                         f"(root control(s) the file animates, missing from "
                         f"the rig)")
        if result.get("root_curves"):
            lines.append(f"Root   : {result['root_curves']} F-curve(s) on {armature.name}_root")
        elif not self.add_root_helpers:
            lines.append("Root   : skipped (SMD-clean — bone channels only)")

        # [roadmap #2] Root motion must never disappear quietly. If the file
        # carried unnamed_p/unnamed_o and the chosen profile dropped it, say
        # so out loud - a silently missing root is exactly the surprise the
        # BST-like default could otherwise spring on someone.
        skipped_root = False
        if not self.add_root_helpers:
            try:
                from ..core import DMX_Analyzer
                tags = DMX_Analyzer.scan_markers(self.filepath)
                skipped_root = bool({"root_pos", "root_rot"} & tags)
            except Exception:
                pass
        if skipped_root:
            lines.append("")
            lines.append("This file HAS root motion and it was not imported.")
            lines.append("Re-run with the Session-aware profile to keep it.")

        from ..core import Report_UI
        Report_UI.report(
            context, "import_dmx_animation", "DMX Animation Imported", lines,
            level=('WARNING' if skipped_root else 'INFO'),
            prefix="DMX_ANIM", operator=self,
            summary=(f"DMX Animation - {Path(self.filepath).name}"
                     + (" - ROOT MOTION SKIPPED" if skipped_root else "")))

        if skipped_root:
            self.report({"WARNING"},
                        f"Imported '{action.name}' - root motion SKIPPED "
                        f"(BST-like profile)")
        else:
            self.report({"INFO"}, f"Imported '{action.name}'")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
# MENU ITEM  (called directly by HT_MT_import_submenu.draw in __init__.py)
# ──────────────────────────────────────────────────────────────────────────────

#Set by __init__.py during register() — direct reference to icon_id()
_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


def draw_menu_item(layout):
    """Draw this module's entry. Called from HT_MT_import_submenu.draw()."""
    layout.operator(
        HT_OT_ImportDmxAnimation.bl_idname,
        text="DMX Animation",
        **_icon_id("import_dmx_anim", "ACTION"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# register / unregister
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (HT_OT_ImportDmxAnimation,)


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


# Standalone launch (run as a script, not imported as a module)
if __name__ == "__main__":
    register()
    bpy.ops.ht.import_dmx_animation("INVOKE_DEFAULT")