"""
Light_Import.py  -  part of HoovyTools     [roadmap #15, EXPERIMENTAL]
=====================================================================

Rebuild SFM lights in Blender. Best effort, by design.

The roadmap pins this as EXPERIMENTAL / RESEARCH and says plainly that
missing light support must never fail a Session Import. So nothing else
depends on this module, the orchestrator only ever REPORTS lights, and
every unmappable parameter is listed rather than silently dropped.

WHAT SFM ACTUALLY STORES        (probed from a real session, 2026-08-20)
=======================================================================
One element type carries essentially everything: DmeProjectedLight. It is
a spot light with a projected texture, and it has 45 attributes. The ones
that map onto a Blender light:

    intensity              500.0        -> energy, via a scale factor
    color                  255 255 255 255 (Color, 0-255 RGBA) -> color
    horizontalFOV          21.6 deg     -> spot_size
    verticalFOV            21.6 deg     (Blender's cone is round - see below)
    castsShadows           True         -> use_shadow
    radius                 0.0          -> shadow_soft_size
    maxDistance            600.0        -> cutoff_distance
    visible                True         -> hide_viewport / hide_render
    transform              DmeTransform -> location + rotation_quaternion

    constant/linear/quadraticAttenuation
                           -> the light's own ShaderNodeLightFalloff mix
    volumetric             -> whether this light scatters in the volume box

And the ones with NO honest Blender equivalent, reported and skipped:

    uberlight and its rectangle    width height edgeWidth edgeHeight
                                   roundness nearEdge farEdge
    volumetricIntensity            always 1.0 in every session measured, so
                                   nothing to test a mapping against
    texture (a gobo, e.g. effects/gobo_radial)
    ambientIntensity, ambientOcclusion, noiseStrength, jitterSeed
    shadow tuning                  shadowAtten shadowFilterSize
                                   shadowDepthBias shadowSlopeScaleDepthBias
    cutOn / cutOff, numPlanes, planeOffset, minDistance

WHY THE COLOR IS NOT A STRAIGHT DIVIDE BY 255
=============================================
SFM stores the colour as 8-bit sRGB. Blender's light colour is linear. A
plain /255 leaves every tinted light too bright and washed out, so the
channels are converted through the sRGB transfer function.

INTENSITY HAS NO PRINCIPLED CONVERSION - BUT SCALE DOES
=======================================================
Source intensity is not watts and not lumens; 500 is a normal value. There
is no correct factor for THAT, only a taste one, so `energy_scale` stays a
taste control at 1.0.

The SCALE part is not a matter of taste. Blender lights fall off with the
inverse square of distance, and a session imported at Source-unit scale is
about 52x larger than the same scene in metres (1 Hammer unit ~ 0.01905 m,
so ~52.5 units per metre). Every distance being 52x bigger divides the
irradiance by 52 SQUARED - roughly 2,700x - which is why imported lights
looked essentially black next to correctly placed geometry.

So energy is:

    energy = intensity * energy_scale * unit_scale**2 * TWEAK_BRIGHTNESS_GLOBAL

with `unit_scale` defaulting to 52.0, the scale this pipeline imports at.
Set it to 1.0 for a scene authored in metres. It is squared for you - give
it the linear scale, not the square.

TWEAK_BRIGHTNESS_GLOBAL is the last term and it is deliberately a single
module constant rather than an operator option: with the physics above
accounted for, imported lights still read about a third as bright as the SFM
render, and that residual is a property of the two renderers, not of any one
light or any one session. Set to 3.0 (2026-08-21) as a starting point
to be fine-tuned. Change the constant, re-import, compare - one number, one
place. It multiplies the ANIMATED intensity too, so a keyed light and a
static one stay in step.

THE AIM MIGHT BE WRONG
======================
Position and orientation are converted with the SAME formulas the camera
importer uses, which are verified for cameras - both are DmeTransform DAG
nodes, and a Blender spot points down -Z exactly like a Blender camera. So
this should be right. But it is untested against a lit reference render,
so `aim_offset` is exposed to spin the whole rig if it turns out otherwise.
"""

import bpy
import math
from pathlib import Path
from mathutils import Vector, Quaternion, Euler, Matrix

from bpy.types import Operator
from bpy.props import (StringProperty, FloatProperty, BoolProperty,
                       FloatVectorProperty, EnumProperty)
from bpy_extras.io_utils import ImportHelper

from ..core.anim_compat import make_action, get_channelbag, fc_find_or_new, iter_fcurves
from ..core import Progress


COLLECTION = "___HoovyTools Lights___"
COLLECTION_COLOR = "COLOR_02"     # orange

LIGHT_TYPES = ("DmeProjectedLight", "DmeLight")

UNMAPPED = (
    "uberlight", "width", "height", "edgeWidth", "edgeHeight", "roundness",
    "nearEdge", "farEdge", "volumetricIntensity", "texture",
    "ambientIntensity", "ambientOcclusion", "noiseStrength", "jitterSeed",
    "shadowAtten", "shadowDepthBias",
    "shadowSlopeScaleDepthBias", "cutOn", "cutOff", "numPlanes",
    "planeOffset", "drawShadowFrustum", "positionJitter",
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _srgb_to_linear(c):
    """8-bit sRGB channel to Blender's linear light colour."""
    c = max(0.0, min(1.0, c / 255.0))
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


DESATURATE_DEFAULT = 0.6


def desaturate(rgb, factor):
    """Blend a linear RGB toward its own luma. 1 = untouched, 0 = grey.

    Applied in LINEAR light with Rec.709 luma weights - the same domain the
    renderer mixes in, so halving saturation cannot shift perceived
    brightness the way an sRGB-domain blend would."""
    f = max(0.0, min(1.0, float(factor)))
    r, g, b = (float(rgb[0]), float(rgb[1]), float(rgb[2]))
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return (y + (r - y) * f, y + (g - y) * f, y + (b - y) * f)


COLLECTION_PORT = "___HoovyTools Lights Port___"


def _light_collections():
    """(outer, inner): ___HoovyTools Lights___ and the nested Port."""
    outer = bpy.data.collections.get(COLLECTION)
    if outer is None:
        outer = bpy.data.collections.new(COLLECTION)
        bpy.context.scene.collection.children.link(outer)
    # UNCONDITIONALLY, not only on create - a collection surviving from an
    # import made before the colour changed would keep the old colour for
    # ever, and "the colour code updated except for my scene" reads as a
    # broken colour code. Same lesson as the camera collections.
    outer.color_tag = COLLECTION_COLOR

    inner = bpy.data.collections.get(COLLECTION_PORT)
    if inner is None:
        inner = bpy.data.collections.new(COLLECTION_PORT)
    # MEMBERSHIP ENFORCED EVERY CALL (the get-or-create rule): the inner
    # collection hangs under the outer one and nowhere else - an organizer
    # pass or an old scene may have left it at the scene root
    for parent in bpy.data.collections:
        if parent is not inner and inner.name in parent.children:
            if parent is not outer:
                parent.children.unlink(inner)
    root = bpy.context.scene.collection
    if inner.name in root.children:
        root.children.unlink(inner)
    if inner.name not in outer.children:
        outer.children.link(inner)
    inner.color_tag = COLLECTION_COLOR
    return outer, inner


def _get_collection():
    """The collection imported light objects go into (the inner Port)."""
    return _light_collections()[1]


def _axis_empty(collection):
    """
    A grouping parent for the imported lights - NOT an axis correction.

    It used to carry +90 X "exactly as the camera importer uses it", which was
    a misreading: the camera importer converts inside its own keyed values, and
    so do sfm_position()/sfm_orientation() here. The extra rotation was a
    second correction on top of a complete one, which put every light
    underground (see import_lights). It sits at identity unless the user asks
    for an aim_offset.
    """
    name = "HT_lights_axis"
    e = bpy.data.objects.get(name)
    if e is None:
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = 'ARROWS'
        e.empty_display_size = 20.0
        e.rotation_mode = 'XYZ'
    for col in list(e.users_collection):
        if col is not collection:
            col.objects.unlink(e)
    if e.name not in collection.objects:
        collection.objects.link(e)
    return e



ATTENUATION_KEYS = ("constantAttenuation", "linearAttenuation",
                    "quadraticAttenuation")


def attenuation_of(elem):
    """(constant, linear, quadratic) from an SFM light. Missing reads as 0."""
    out = []
    for k in ATTENUATION_KEYS:
        try:
            v = elem.get(k)
            out.append(float(v) if v is not None else 0.0)
        except Exception:
            out.append(0.0)
    return tuple(out)


def attenuation_weights(triple):
    """The triple as weights summing to 1, or None when it says nothing.

    A light whose three terms are all zero has no opinion about falloff, and
    inventing one for it would be worse than leaving Blender's own.
    """
    total = sum(abs(v) for v in triple)
    if total <= 0.0:
        return None
    return tuple(abs(v) / total for v in triple)



UBERLIGHT_GROUP = "HT SFM Uberlight"
#bumped whenever the group's INTERNALS change while its sockets don't.
#1  first build (caller normalized the triple)
#2  normalization moved inside; raw SFM values may be linked in
UBERLIGHT_BUILD = 2


def _group_socket(node, identifier, outputs=False):
    """Mix-node sockets BY IDENTIFIER (A_Float/B_Float/Result_Float) - the
    NAME 'A' exists once per data type and a name lookup grabs the wrong
    one. Same trap the skydome world hit with its RGBA mixes."""
    coll = node.outputs if outputs else node.inputs
    return next(s for s in coll if s.identifier == identifier)


def _uberlight_group():
    """Get-or-build the shared uberlight shaping group. Inputs are the SFM
    numbers; the one output is the emission-strength multiplier."""
    inputs = ("constantAttenuation", "linearAttenuation",
              "quadraticAttenuation", "uberlight", "cutOn", "cutOff",
              "nearEdge", "farEdge", "width", "height", "edgeWidth",
              "edgeHeight", "minDistance", "maxDistance")
    ng = bpy.data.node_groups.get(UBERLIGHT_GROUP)
    if ng is not None:
        have = sorted(s.name for s in ng.interface.items_tree
                      if getattr(s, "in_out", "") == 'INPUT')
        # A BUILD STAMP, not JUST THE SOCKET SET. The sockets did not
        # change when normalization moved INSIDE this group - so a .blend
        # holding the older build would have been reused unchanged and fed
        # raw slider values into a formula expecting normalized ones (the
        # 1500x dimming, back again, silently). Any internal change bumps
        # the stamp
        if have == sorted(inputs) and ng.get("ht_build") == UBERLIGHT_BUILD:
            return ng
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(UBERLIGHT_GROUP, "ShaderNodeTree")
    ng["ht_build"] = UBERLIGHT_BUILD
    for name in inputs:
        ng.interface.new_socket(name, in_out='INPUT',
                                socket_type='NodeSocketFloat')
    ng.interface.new_socket("Strength", in_out='OUTPUT',
                            socket_type='NodeSocketFloat')

    n, L = ng.nodes, ng.links.new
    gi = n.new("NodeGroupInput");  gi.location = (-1500, 0)
    go = n.new("NodeGroupOutput"); go.location = (900, 0)

    def math(op, x, y, label="", v0=None, v1=None, clamp=False):
        m = n.new("ShaderNodeMath")
        m.operation = op
        m.location = (x, y)
        if label:
            m.label = label
        if v0 is not None:
            m.inputs[0].default_value = v0
        if v1 is not None:
            m.inputs[1].default_value = v1
        m.use_clamp = clamp
        return m

    def smoothwin(x, y, label):
        """Map Range in smoothstep mode - the uberlight's smoothstep."""
        m = n.new("ShaderNodeMapRange")
        m.location = (x, y)
        m.label = label
        m.interpolation_type = 'SMOOTHSTEP'
        m.clamp = True
        m.inputs["To Min"].default_value = 0.0
        m.inputs["To Max"].default_value = 1.0
        return m

    # d = Constant / Linear of a strength-1 Light Falloff (measured above).
    fall = n.new("ShaderNodeLightFalloff")
    fall.location = (-1260, 320)
    fall.label = "distance source"
    fall.inputs["Strength"].default_value = 1.0
    fall.inputs["Smooth"].default_value = 0.0
    dist = math('DIVIDE', -1060, 320, "d = C/L")
    L(fall.outputs["Constant"], dist.inputs[0])
    L(fall.outputs["Linear"], dist.inputs[1])

    # light-space direction; z depth and unit-plane coordinates
    tc = n.new("ShaderNodeTexCoord"); tc.location = (-1260, 60)
    sep = n.new("ShaderNodeSeparateXYZ"); sep.location = (-1060, 60)
    L(tc.outputs["Normal"], sep.inputs[0])
    az = math('ABSOLUTE', -880, 20, "|n.z|")
    L(sep.outputs["Z"], az.inputs[0])
    azm = math('MAXIMUM', -700, 20, "", v1=1e-4)
    L(az.outputs[0], azm.inputs[0])
    zdep = math('MULTIPLY', -520, 200, "z depth")
    L(dist.outputs[0], zdep.inputs[0])
    L(azm.outputs[0], zdep.inputs[1])
    ux = math('DIVIDE', -700, 120, "u = x/|z|")
    L(sep.outputs["X"], ux.inputs[0]); L(azm.outputs[0], ux.inputs[1])
    uy = math('DIVIDE', -700, -80, "v = y/|z|")
    L(sep.outputs["Y"], uy.inputs[0]); L(azm.outputs[0], uy.inputs[1])
    aux = math('ABSOLUTE', -520, 120, "|u|")
    L(ux.outputs[0], aux.inputs[0])
    auy = math('ABSOLUTE', -520, -80, "|v|")
    L(uy.outputs[0], auy.inputs[0])

    rsum1 = math('ADD', -1060, 900, "c+l")
    L(gi.outputs["constantAttenuation"], rsum1.inputs[0])
    L(gi.outputs["linearAttenuation"], rsum1.inputs[1])
    rsum = math('ADD', -880, 900, "+q")
    L(rsum1.outputs[0], rsum.inputs[0])
    L(gi.outputs["quadraticAttenuation"], rsum.inputs[1])
    rsafe = math('MAXIMUM', -700, 900, "", v1=1e-9)
    L(rsum.outputs[0], rsafe.inputs[0])
    thas = math('GREATER_THAN', -700, 1000, "triple set?", v1=1e-6)
    L(rsum.outputs[0], thas.inputs[0])
    cn = math('DIVIDE', -520, 1000, "c norm")
    L(gi.outputs["constantAttenuation"], cn.inputs[0])
    L(rsafe.outputs[0], cn.inputs[1])
    ln = math('DIVIDE', -520, 900, "l norm")
    L(gi.outputs["linearAttenuation"], ln.inputs[0])
    L(rsafe.outputs[0], ln.inputs[1])
    qn0 = math('DIVIDE', -520, 800, "q norm")
    L(gi.outputs["quadraticAttenuation"], qn0.inputs[0])
    L(rsafe.outputs[0], qn0.inputs[1])
    # no TRIPLE AT all -> pure quadratic, so the light is untouched
    qnm = n.new("ShaderNodeMix"); qnm.data_type = 'FLOAT'
    qnm.location = (-340, 800); qnm.label = "q norm or 1"
    _group_socket(qnm, "A_Float").default_value = 1.0
    L(thas.outputs[0], _group_socket(qnm, "Factor_Float"))
    L(qn0.outputs[0], _group_socket(qnm, "B_Float"))

    # ATTENUATION  d^2 / (c + l*d + q*d^2), guarded; all-zero triple = 1.
    d2 = math('MULTIPLY', -700, 480, "d^2")
    L(dist.outputs[0], d2.inputs[0]); L(dist.outputs[0], d2.inputs[1])
    ld = math('MULTIPLY', -700, 620, "l*d")
    L(ln.outputs[0], ld.inputs[0])
    L(dist.outputs[0], ld.inputs[1])
    qd2 = math('MULTIPLY', -520, 620, "q*d^2")
    L(_group_socket(qnm, "Result_Float", True), qd2.inputs[0])
    L(d2.outputs[0], qd2.inputs[1])
    s1 = math('ADD', -340, 620, "c + l*d")
    L(cn.outputs[0], s1.inputs[0])
    L(ld.outputs[0], s1.inputs[1])
    s2 = math('ADD', -160, 620, "+ q*d^2")
    L(s1.outputs[0], s2.inputs[0]); L(qd2.outputs[0], s2.inputs[1])
    den = math('MAXIMUM', 20, 620, "", v1=1e-4)
    L(s2.outputs[0], den.inputs[0])
    att = math('DIVIDE', 200, 620, "d^2/denom")
    L(d2.outputs[0], att.inputs[0]); L(den.outputs[0], att.inputs[1])
    attm = n.new("ShaderNodeMix"); attm.data_type = 'FLOAT'
    attm.location = (380, 620); attm.label = "atten or 1"
    _group_socket(attm, "A_Float").default_value = 1.0
    L(thas.outputs[0], _group_socket(attm, "Factor_Float"))
    L(att.outputs[0], _group_socket(attm, "B_Float"))

    # UBER DISTANCE WINDOW  smoothstep(cutOn-nearEdge, cutOn, z)
    # * (1 - smoothstep(cutOff, cutOff+farEdge, z))
    on0 = math('SUBTRACT', -340, 200, "cutOn - nearEdge")
    L(gi.outputs["cutOn"], on0.inputs[0])
    L(gi.outputs["nearEdge"], on0.inputs[1])
    win_on = smoothwin(-160, 260, "fade in")
    L(zdep.outputs[0], win_on.inputs["Value"])
    L(on0.outputs[0], win_on.inputs["From Min"])
    L(gi.outputs["cutOn"], win_on.inputs["From Max"])
    # cutOn 0 = no near clip. Without this guard the Map Range gets
    # From Min == From Max == 0, a degenerate window that reads 0 and
    # BLACKED out every uber light with no near clip set (render-caught)
    on_has = math('GREATER_THAN', 20, 320, "cutOn set?", v1=1e-6)
    L(gi.outputs["cutOn"], on_has.inputs[0])
    onm = n.new("ShaderNodeMix"); onm.data_type = 'FLOAT'
    onm.location = (200, 260); onm.label = "near clip or 1"
    _group_socket(onm, "A_Float").default_value = 1.0
    L(on_has.outputs[0], _group_socket(onm, "Factor_Float"))
    L(win_on.outputs[0], _group_socket(onm, "B_Float"))
    off1 = math('ADD', -340, 60, "cutOff + farEdge")
    L(gi.outputs["cutOff"], off1.inputs[0])
    L(gi.outputs["farEdge"], off1.inputs[1])
    win_off = smoothwin(-160, 60, "fade out")
    L(zdep.outputs[0], win_off.inputs["Value"])
    L(gi.outputs["cutOff"], win_off.inputs["From Min"])
    L(off1.outputs[0], win_off.inputs["From Max"])
    off_inv = math('SUBTRACT', 20, 60, "1 -", v0=1.0)
    L(win_off.outputs[0], off_inv.inputs[1])
    # cutOff 0 = no far clip
    off_has = math('GREATER_THAN', 20, -60, "cutOff set?", v1=1e-6)
    L(gi.outputs["cutOff"], off_has.inputs[0])
    offm = n.new("ShaderNodeMix"); offm.data_type = 'FLOAT'
    offm.location = (200, 20); offm.label = "far clip or 1"
    _group_socket(offm, "A_Float").default_value = 1.0
    L(off_has.outputs[0], _group_socket(offm, "Factor_Float"))
    L(off_inv.outputs[0], _group_socket(offm, "B_Float"))
    zwin = math('MULTIPLY', 380, 200, "z window")
    L(_group_socket(onm, "Result_Float", True), zwin.inputs[0])
    L(_group_socket(offm, "Result_Float", True), zwin.inputs[1])

    # BARN DOORS  (1 - smoothstep(width, width+edgeWidth, |u|)) * same for v
    wx1 = math('ADD', -340, -160, "width + edgeWidth")
    L(gi.outputs["width"], wx1.inputs[0])
    L(gi.outputs["edgeWidth"], wx1.inputs[1])
    door_x = smoothwin(-160, -160, "door x")
    L(aux.outputs[0], door_x.inputs["Value"])
    L(gi.outputs["width"], door_x.inputs["From Min"])
    L(wx1.outputs[0], door_x.inputs["From Max"])
    dx_inv = math('SUBTRACT', 20, -160, "1 -", v0=1.0)
    L(door_x.outputs[0], dx_inv.inputs[1])
    hy1 = math('ADD', -340, -320, "height + edgeHeight")
    L(gi.outputs["height"], hy1.inputs[0])
    L(gi.outputs["edgeHeight"], hy1.inputs[1])
    door_y = smoothwin(-160, -320, "door y")
    L(auy.outputs[0], door_y.inputs["Value"])
    L(gi.outputs["height"], door_y.inputs["From Min"])
    L(hy1.outputs[0], door_y.inputs["From Max"])
    dy_inv = math('SUBTRACT', 20, -320, "1 -", v0=1.0)
    L(door_y.outputs[0], dy_inv.inputs[1])
    doors = math('MULTIPLY', 200, -240, "doors")
    L(dx_inv.outputs[0], doors.inputs[0])
    L(dy_inv.outputs[0], doors.inputs[1])
    # width or height 0 = no doors (the SFM defaults)
    wsum = math('MULTIPLY', 200, -400, "w*h")
    L(gi.outputs["width"], wsum.inputs[0])
    L(gi.outputs["height"], wsum.inputs[1])
    whas = math('GREATER_THAN', 380, -400, "doors set?", v1=1e-9)
    L(wsum.outputs[0], whas.inputs[0])
    doorm = n.new("ShaderNodeMix"); doorm.data_type = 'FLOAT'
    doorm.location = (380, -240); doorm.label = "doors or 1"
    _group_socket(doorm, "A_Float").default_value = 1.0
    L(whas.outputs[0], _group_socket(doorm, "Factor_Float"))
    L(doors.outputs[0], _group_socket(doorm, "B_Float"))

    #NON-UBER WINDOW  hard-ish min/max distance clips (tight 1-unit edges)
    mn1 = math('SUBTRACT', -340, -520, "min - 1", v1=1.0)
    L(gi.outputs["minDistance"], mn1.inputs[0])
    win_mn = smoothwin(-160, -520, "min clip")
    L(dist.outputs[0], win_mn.inputs["Value"])
    L(mn1.outputs[0], win_mn.inputs["From Min"])
    L(gi.outputs["minDistance"], win_mn.inputs["From Max"])
    mx1 = math('ADD', -340, -680, "max + 1", v1=1.0)
    L(gi.outputs["maxDistance"], mx1.inputs[0])
    win_mx = smoothwin(-160, -680, "max clip")
    L(dist.outputs[0], win_mx.inputs["Value"])
    L(gi.outputs["maxDistance"], win_mx.inputs["From Min"])
    L(mx1.outputs[0], win_mx.inputs["From Max"])
    mx_inv = math('SUBTRACT', 20, -680, "1 -", v0=1.0)
    L(win_mx.outputs[0], mx_inv.inputs[1])
    mx_has = math('GREATER_THAN', 20, -780, "max set?", v1=1e-6)
    L(gi.outputs["maxDistance"], mx_has.inputs[0])
    mxm = n.new("ShaderNodeMix"); mxm.data_type = 'FLOAT'
    mxm.location = (200, -680); mxm.label = "max clip or 1"
    _group_socket(mxm, "A_Float").default_value = 1.0
    L(mx_has.outputs[0], _group_socket(mxm, "Factor_Float"))
    L(mx_inv.outputs[0], _group_socket(mxm, "B_Float"))
    mmwin = math('MULTIPLY', 380, -560, "min/max window")
    L(win_mn.outputs[0], mmwin.inputs[0])
    L(_group_socket(mxm, "Result_Float", True), mmwin.inputs[1])

    #UBER vs NON-UBER: uber mode uses window*doors, plain uses min/max
    uber_shape = math('MULTIPLY', 560, 40, "uber shaping")
    L(zwin.outputs[0], uber_shape.inputs[0])
    L(_group_socket(doorm, "Result_Float", True), uber_shape.inputs[1])
    shape = n.new("ShaderNodeMix"); shape.data_type = 'FLOAT'
    shape.location = (560, -200); shape.label = "uber?"
    L(gi.outputs["uberlight"], _group_socket(shape, "Factor_Float"))
    L(mmwin.outputs[0], _group_socket(shape, "A_Float"))
    L(uber_shape.outputs[0], _group_socket(shape, "B_Float"))

    total = math('MULTIPLY', 740, 200, "strength")
    L(_group_socket(attm, "Result_Float", True), total.inputs[0])
    L(_group_socket(shape, "Result_Float", True), total.inputs[1])
    L(total.outputs[0], go.inputs["Strength"])
    return ng


def apply_attenuation_nodes(light_obj, elem):
    """
    Build the light's node tree as the reconstructed SFM uberlight.

    Returns a dict for the report, or None when the element carries no
    shaping information at all (attenuation triple, uberlight windows and
    min/max distances all unset).
    """
    data = getattr(light_obj, "data", None)
    if data is None or not hasattr(data, "use_nodes"):
        return None

    def num(name):
        try:
            v = elem.get(name)
            return float(v) if v is not None else 0.0
        except Exception:                                     # noqa: BLE001
            return 0.0

    triple = attenuation_of(elem)
    weights = attenuation_weights(triple)
    uber = num("uberlight")
    has_shaping = (weights is not None or uber
                   or num("maxDistance") > 0 or num("minDistance") > 0)
    if not has_shaping:
        return None

    data.use_nodes = True
    nt = data.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputLight")
    out.location = (760, 0)
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.location = (560, 0)
    emit.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)

    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = _uberlight_group()
    grp.name = grp.label = "SFM Uberlight"
    grp.location = (220, 0)
    grp.width = 220

    dgrp = _build_data_node(nt, elem)
    dgrp.location = (-260, 40)
    for name in ("constantAttenuation", "linearAttenuation",
                 "quadraticAttenuation", "uberlight", "cutOn", "cutOff",
                 "nearEdge", "farEdge", "width", "height", "edgeWidth",
                 "edgeHeight", "minDistance", "maxDistance"):
        try:
            nt.links.new(dgrp.outputs[name], grp.inputs[name])
        except Exception:                                     # noqa: BLE001
            pass

    nt.links.new(grp.outputs["Strength"], emit.inputs["Strength"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])

    f_data = nt.nodes.new("NodeFrame")
    f_data.label = "SFM · LIGHT DATA"
    dgrp.parent = f_data
    f_att = nt.nodes.new("NodeFrame")
    f_att.label = "SFM · UBERLIGHT"
    grp.parent = f_att
    f_out = nt.nodes.new("NodeFrame")
    f_out.label = "OUTPUT"
    emit.parent = f_out
    out.parent = f_out

    w = weights or (0.0, 0.0, 1.0)
    return {
        "triple": tuple(round(v, 4) for v in triple),
        "weights": tuple(round(v, 4) for v in w),
        "magnitude": round(sum(abs(v) for v in triple), 4),
        "pure_quadratic": w[2] > 0.999,
        "uberlight": bool(uber),
    }



SFM_LIGHT_DATA_GROUP = "HT SFM Light Data"

SFM_LIGHT_ATTRS = (
    "intensity", "ambientIntensity", "horizontalFOV", "verticalFOV",
    "radius", "shadowFilterSize", "shadowAtten", "minDistance",
    "maxDistance", "constantAttenuation", "linearAttenuation",
    "quadraticAttenuation", "shadowDepthBias", "shadowSlopeScaleDepthBias",
    "farZAtten", "nearEdge", "farEdge", "cutOn", "cutOff",
    "volumetricIntensity", "noiseStrength", "width", "edgeWidth",
    "height", "edgeHeight", "uberlight",
)

SFM_LIGHT_DRIVERS = (
    # cone: SFM's FOV is the FULL angle in degrees, which is what
    # spot_size means too - a straight radians(), wider axis winning
    # (Blender's cone is round, SFM's can be oval)
    ("spot_size", "radians(min(179.0, max(1.0, max(h, v))))",
     {"h": "horizontalFOV", "v": "verticalFOV"}),
    # emitter size for soft shadows: Hammer units, times import scale
    ("shadow_soft_size", "max(0.0, r * {scale})", {"r": "radius"}),
    # EEVEE shadow blur - unitless on both sides
    ("shadow_filter_radius", "max(0.0, f)", {"f": "shadowFilterSize"}),
    #reach: SFM's maxDistance IS Blender's Custom Distance cutoff
    ("cutoff_distance", "max(0.0, m * {scale})", {"m": "maxDistance"}),
    # nothing nearer than this casts - the shadow buffer's near clip
    ("shadow_buffer_clip_start", "max(0.001, n * {scale})",
     {"n": "minDistance"}),
    # watts. The conversion chain (energy scale, world scale squared, the
    # taste tweak) is baked into the expression as one factor, so the SFM
    # intensity stays the number you read and turn
    ("energy", "i * {energy}", {"i": "intensity"}),
)


SFM_LIGHT_PANELS = (
    ("", ("intensity", "ambientIntensity", "color")),
    ("SFM · Cone", ("horizontalFOV", "verticalFOV", "radius")),
    ("SFM · Shadow", ("shadowFilterSize", "shadowAtten", "shadowDepthBias",
                      "shadowSlopeScaleDepthBias")),
    ("SFM · Attenuation", ("minDistance", "maxDistance",
                           "constantAttenuation", "linearAttenuation",
                           "quadraticAttenuation", "farZAtten")),
    ("SFM · Edges", ("uberlight", "nearEdge", "farEdge", "cutOn", "cutOff",
                     "width", "edgeWidth", "height", "edgeHeight")),
    ("SFM · Volumetric", ("volumetricIntensity", "noiseStrength")),
    ("SFM · Transform", ("transform_pos", "transform_rot (deg)")),
)


def _sock_type(name):
    return ('NodeSocketColor' if name == "color"
            else 'NodeSocketVector' if name.startswith("transform")
            else 'NodeSocketFloat')


def _sfm_data_group():
    """Get-or-build the shared data group. Rebuilt only when its socket set
    does not match (an older build), because a rebuild resets the per-light
    values every existing instance carries.

    IT HAS OUTPUTS NOW, one per input, wired straight through. That is what turns it from a read-only sticker into the
    SOURCE: the uberlight group takes its attenuation and window values
    from these outputs, and the light's own properties read the same
    sockets through drivers. One number, one place, two consumers.
    """
    want = sorted(list(SFM_LIGHT_ATTRS) + ["color", "transform_pos",
                                           "transform_rot (deg)"])
    ng = bpy.data.node_groups.get(SFM_LIGHT_DATA_GROUP)
    if ng is not None:
        have = sorted(s.name for s in ng.interface.items_tree
                      if getattr(s, "in_out", "") == 'INPUT')
        outs = sorted(s.name for s in ng.interface.items_tree
                      if getattr(s, "in_out", "") == 'OUTPUT')
        if have == want and outs == want:
            return ng
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(SFM_LIGHT_DATA_GROUP, "ShaderNodeTree")

    def sock(name, parent=None):
        stype = _sock_type(name)
        if parent is not None:
            try:
                return ng.interface.new_socket(name, in_out='INPUT',
                                               socket_type=stype,
                                               parent=parent)
            except Exception:                                 # noqa: BLE001
                pass
        return ng.interface.new_socket(name, in_out='INPUT',
                                       socket_type=stype)

    order = []
    for title, names in SFM_LIGHT_PANELS:
        panel = None
        if title:
            try:
                # closed by default - the node stays compact; SFM's main
                # three (intensity, ambient, color) sit above the panels
                panel = ng.interface.new_panel(title, default_closed=True)
            except Exception:                                 # noqa: BLE001
                panel = None
        for name in names:
            sock(name, panel)
            order.append(name)

    # OUTPUTS are FLAT, in the same order - an output panel would only
    # add clicks to a side of the node nobody reads, and the pass-through
    # wiring below matches them by NAME, not by position
    for name in order:
        ng.interface.new_socket(name, in_out='OUTPUT',
                                socket_type=_sock_type(name))

    gi = ng.nodes.new("NodeGroupInput");  gi.location = (-260, 0)
    go = ng.nodes.new("NodeGroupOutput"); go.location = (260, 0)
    for name in order:
        try:
            ng.links.new(gi.outputs[name], go.inputs[name])
        except Exception:                                     # noqa: BLE001
            pass
    return ng


DATA_NODE_NAME = "SFM Light Data"


def _build_data_node(nt, elem):
    """Get-or-create the SFM Light Data node in *nt* and stamp *elem*'s
    values onto it. Returns the node.

    GET-OR-CREATE, NOT CREATE: the uberlight builder
    makes this node and LINKS it, and a later re-stamp that removed and
    remade it would take every one of those links with it - the shader
    would keep rendering, on socket defaults, silently ignoring the data
    node it is drawn next to."""
    grp = next((n for n in nt.nodes
                if n.bl_idname == "ShaderNodeGroup"
                and n.node_tree is not None
                and n.node_tree.name == SFM_LIGHT_DATA_GROUP), None)
    if grp is None:
        grp = nt.nodes.new("ShaderNodeGroup")
        grp.location = (-460, -320)
    grp.node_tree = _sfm_data_group()
    grp.name = grp.label = DATA_NODE_NAME
    grp.width = 230

    for name in SFM_LIGHT_ATTRS:
        try:
            v = elem.get(name)
        except Exception:                                     # noqa: BLE001
            v = None
        try:
            grp.inputs[name].default_value = float(v) if v is not None else 0.0
        except Exception:                                     # noqa: BLE001
            pass

    try:
        col = elem.get("color")
        if col is not None:
            grp.inputs["color"].default_value = (
                float(col[0]) / 255.0, float(col[1]) / 255.0,
                float(col[2]) / 255.0,
                (float(col[3]) / 255.0) if len(col) > 3 else 1.0)
    except Exception:                                         # noqa: BLE001
        pass
    try:
        tr = elem.get("transform")
        if tr is not None:
            p = tr.get("position")
            q = tr.get("orientation")
            if p is not None:
                grp.inputs["transform_pos"].default_value = (
                    float(p[0]), float(p[1]), float(p[2]))
            if q is not None:
                e = Quaternion((float(q[3]), float(q[0]), float(q[1]),
                                float(q[2]))).to_euler()
                grp.inputs["transform_rot (deg)"].default_value = (
                    math.degrees(e.x), math.degrees(e.y), math.degrees(e.z))
    except Exception:                                         # noqa: BLE001
        pass
    return grp


def apply_sfm_data_node(light_obj, elem):
    """Stamp one HT SFM Light Data instance into the light's node tree.

    Values that the file does not carry read 0. Never raises; returns how
    many of the scalar attributes were present."""
    data = getattr(light_obj, "data", None)
    if data is None or not hasattr(data, "use_nodes"):
        return 0
    # enabling use_nodes on a light makes Blender build its own default
    # emission tree, which renders identically to the non-nodal light - so
    # a light apply_attenuation_nodes left alone is safe to touch here
    data.use_nodes = True
    nt = data.node_tree

    grp = _build_data_node(nt, elem)
    if grp.parent is None:
        # its own labelled frame, matching the uberlight/output frames
        frame = next((n for n in nt.nodes if n.bl_idname == "NodeFrame"
                      and n.label == "SFM · LIGHT DATA"), None)
        if frame is None:
            frame = nt.nodes.new("NodeFrame")
            frame.label = "SFM · LIGHT DATA"
        grp.parent = frame

    found = 0
    for name in SFM_LIGHT_ATTRS:
        try:
            if elem.get(name) is not None:
                found += 1
        except Exception:                                     # noqa: BLE001
            pass
    return found



def _keyed_paths(data):
    """Every data_path the light data's own action keys."""
    out = set()
    ad = getattr(data, "animation_data", None)
    action = getattr(ad, "action", None) if ad else None
    if action is None:
        return out
    try:
        from ..core.anim_compat import iter_fcurves
        for fc in iter_fcurves(action, data):
            out.add(fc.data_path)
    except Exception:                                         # noqa: BLE001
        pass
    return out


LIGHT_DRIVERS = False


def strip_light_drivers(light_obj):
    """Remove every driver on a light's data - including ones an older build
    put there. Returns how many went."""
    data = getattr(light_obj, "data", None)
    ad = getattr(data, "animation_data", None) if data is not None else None
    if ad is None:
        return 0
    n = 0
    for fc in list(ad.drivers):
        try:
            data.driver_remove(fc.data_path, fc.array_index)
            n += 1
        except Exception:                                     # noqa: BLE001
            try:
                ad.drivers.remove(fc)
                n += 1
            except Exception:                                 # noqa: BLE001
                pass
    return n


def drive_from_data(light_obj, scale=1.0, energy_scale=1.0, unit_scale=52.0):
    """Drive the light's own properties from its SFM Light Data node.

    Returns {property: reason} for what was NOT driven, so the report can
    say so instead of leaving it a mystery."""
    data = getattr(light_obj, "data", None)
    if data is None or not getattr(data, "use_nodes", False):
        return {}
    nt = getattr(data, "node_tree", None)
    if nt is None or DATA_NODE_NAME not in nt.nodes:
        return {}

    keyed = _keyed_paths(data)
    energy_factor = (float(energy_scale) * (float(unit_scale) ** 2)
                     * TWEAK_BRIGHTNESS_GLOBAL)
    skipped = {}
    for prop, expr, var_map in SFM_LIGHT_DRIVERS:
        if not hasattr(data, prop):
            skipped[prop] = "not on this Blender build"
            continue
        if prop in keyed:
            skipped[prop] = "animated - keyframes kept"
            continue
        try:
            data.driver_remove(prop)
        except Exception:                                     # noqa: BLE001
            pass
        try:
            fcu = data.driver_add(prop)
        except Exception as exc:                              # noqa: BLE001
            skipped[prop] = f"{type(exc).__name__}"
            continue
        drv = fcu.driver
        drv.type = 'SCRIPTED'
        drv.expression = expr.format(scale=repr(float(scale)),
                                     energy=repr(energy_factor))
        for var_name, socket in var_map.items():
            var = drv.variables.new()
            var.name = var_name
            var.type = 'SINGLE_PROP'
            tgt = var.targets[0]
            # the LIGHT DATA IS the ID, and the path walks into its own
            # node tree. Targeting the node GROUP instead would make every
            # light read one shared value - the group is shared, the NODE
            # is per light
            tgt.id_type = 'LIGHT'
            tgt.id = data
            tgt.data_path = (f'node_tree.nodes["{DATA_NODE_NAME}"]'
                             f'.inputs["{socket}"].default_value')
    return skipped



VOLUME_OBJECT = "HT_Volumetrics"
VOLUME_MATERIAL = "HT_Volumetrics"

VOLUME_BOUNDS_MULTIPLIER = 10.0

VOLUME_DENSITY = 0.000015
VOLUME_ANISOTROPY = 0.281364

VOLUME_COLOR = (1.0, 1.0, 1.0, 1.0)

#A box whose thinnest axis is under this fraction of its thickest is opened
#out. See the degenerate-axis note above
VOLUME_MIN_AXIS_RATIO = 0.1

# Blender's own default for `Light.volume_factor` is 1.0
VOLUME_FACTOR_ON = 1.0
VOLUME_FACTOR_OFF = 0.0

VOLUME_MODES = ("ALL", "SFM", "NONE")


def volume_bounds(objects, multiplier=None, min_ratio=None):
    """(centre, size) in Blender space for a box wrapping *objects*.

    (None, None) when there is nothing to wrap. Positions come from
    `matrix_world`, so a light parented to the grouping empty is measured
    where it actually is rather than where its local offset says.
    """
    mult = VOLUME_BOUNDS_MULTIPLIER if multiplier is None else float(multiplier)
    ratio = VOLUME_MIN_AXIS_RATIO if min_ratio is None else float(min_ratio)

    pts = []
    for o in objects or ():
        try:
            pts.append(o.matrix_world.translation.copy())
        except Exception:
            continue
    if not pts:
        return None, None

    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    centre = Vector(((lo[i] + hi[i]) * 0.5 for i in range(3)))
    size = [(hi[i] - lo[i]) * mult for i in range(3)]

    # one light, or several at one point, has no extent in any axis. Fall
    # back to something a person can see rather than a zero-volume box
    biggest = max(size)
    if biggest <= 0.0:
        biggest = 100.0 * mult
        size = [biggest, biggest, biggest]
    floor = biggest * ratio
    size = [max(v, floor) for v in size]

    return centre, Vector(size)


VOLUME_GROUP = "HT Volumetrics"


def _build_volume_group():
    """The HT Volumetrics node group, rebuilt fresh - one node, seven knobs.

    Same doctrine as the HT Skydome World rig: the material tree holds ONE
    group node, and every artistic decision is a group input:

    Height uses the box's own Generated coordinates (0..1 inside the mesh
    bounds), the noise a Noise Texture on the same coordinates - both
    evaluate identically in EEVEE and Cycles; nothing here is ray-type
    dependent (the skydome parity rule, applied to volumes).
    """
    old = bpy.data.node_groups.get(VOLUME_GROUP)
    if old is not None:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(VOLUME_GROUP, "ShaderNodeTree")

    def add_in(name, stype, default=None, mn=None, mx=None):
        s = ng.interface.new_socket(name, in_out='INPUT', socket_type=stype)
        if default is not None:
            s.default_value = default
        if mn is not None and hasattr(s, "min_value"):
            s.min_value = mn
        if mx is not None and hasattr(s, "max_value"):
            s.max_value = mx
        return s

    add_in("Density Scale", 'NodeSocketFloat', 5.0, 0.0, None)
    add_in("Anisotropy", 'NodeSocketFloat', VOLUME_ANISOTROPY, -1.0, 1.0)
    add_in("Color", 'NodeSocketColor', VOLUME_COLOR)
    add_in("Height Fade", 'NodeSocketFloat', 0.0, 0.0, 1.0)
    add_in("Noise Strength", 'NodeSocketFloat', 0.0, 0.0, 1.0)
    add_in("Noise Scale", 'NodeSocketFloat', 2.0, 0.0, 100.0)
    add_in("Density", 'NodeSocketFloat', VOLUME_DENSITY, 0.0, 1.0)
    ng.interface.new_socket("Volume", in_out='OUTPUT',
                            socket_type='NodeSocketShader')

    n = ng.nodes
    gi = n.new("NodeGroupInput");  gi.location = (-900, 0)
    go = n.new("NodeGroupOutput"); go.location = (500, 0)
    texco = n.new("ShaderNodeTexCoord"); texco.location = (-900, 320)

    # height factor = 1 - HeightFade * Z   (Generated Z is 0 at the box
    # floor, 1 at its ceiling)
    sep = n.new("ShaderNodeSeparateXYZ"); sep.location = (-700, 320)
    hmul = n.new("ShaderNodeMath"); hmul.operation = 'MULTIPLY'
    hmul.location = (-520, 320)
    hsub = n.new("ShaderNodeMath"); hsub.operation = 'SUBTRACT'
    hsub.inputs[0].default_value = 1.0
    hsub.use_clamp = True
    hsub.location = (-340, 320)

    # noise factor = 1 + NoiseStrength * (2*Fac - 1): mean stays ~1, so
    # turning the knob changes the TEXTURE of the fog, not its exposure
    noise = n.new("ShaderNodeTexNoise"); noise.location = (-700, 120)
    nmad = n.new("ShaderNodeMath"); nmad.operation = 'MULTIPLY_ADD'
    nmad.inputs[1].default_value = 2.0
    nmad.inputs[2].default_value = -1.0
    nmad.location = (-520, 120)
    nmul = n.new("ShaderNodeMath"); nmul.operation = 'MULTIPLY'
    nmul.location = (-340, 120)
    nadd = n.new("ShaderNodeMath"); nadd.operation = 'ADD'
    nadd.inputs[1].default_value = 1.0
    nadd.location = (-160, 120)

    dmul0 = n.new("ShaderNodeMath"); dmul0.operation = 'MULTIPLY'
    dmul0.label = "density x scale"
    dmul0.location = (-340, 420)
    dmul1 = n.new("ShaderNodeMath"); dmul1.operation = 'MULTIPLY'
    dmul1.location = (-160, 320)
    dmul2 = n.new("ShaderNodeMath"); dmul2.operation = 'MULTIPLY'
    dmul2.use_clamp = False
    dmul2.location = (20, 220)
    dmax = n.new("ShaderNodeMath"); dmax.operation = 'MAXIMUM'
    dmax.inputs[1].default_value = 0.0
    dmax.location = (180, 220)

    vol = n.new("ShaderNodeVolumePrincipled")
    vol.location = (320, -40)
    vol.name = "HT Principled Volume"

    L = ng.links.new
    L(texco.outputs["Object"], noise.inputs["Vector"])
    L(gi.outputs["Noise Scale"], noise.inputs["Scale"])
    L(texco.outputs["Generated"], sep.inputs["Vector"])
    L(sep.outputs["Z"], hmul.inputs[0])
    L(gi.outputs["Height Fade"], hmul.inputs[1])
    L(hmul.outputs[0], hsub.inputs[1])
    L(noise.outputs["Fac"], nmad.inputs[0])
    L(nmad.outputs[0], nmul.inputs[0])
    L(gi.outputs["Noise Strength"], nmul.inputs[1])
    L(nmul.outputs[0], nadd.inputs[0])
    L(gi.outputs["Density"], dmul0.inputs[0])
    L(gi.outputs["Density Scale"], dmul0.inputs[1])
    L(dmul0.outputs[0], dmul1.inputs[0])
    L(hsub.outputs[0], dmul1.inputs[1])
    L(dmul1.outputs[0], dmul2.inputs[0])
    L(nadd.outputs[0], dmul2.inputs[1])
    L(dmul2.outputs[0], dmax.inputs[0])
    # BY NAME, NOT BY INDEX. Principled Volume has thirteen inputs and
    # Blender has reordered shader sockets between releases before; an index
    # that silently became "Emission Strength" would fill the scene with
    # light and look nothing like a density problem
    L(dmax.outputs[0], vol.inputs["Density"])
    L(gi.outputs["Anisotropy"], vol.inputs["Anisotropy"])
    L(gi.outputs["Color"], vol.inputs["Color"])
    L(vol.outputs["Volume"], go.inputs["Volume"])
    return ng


def _volume_material(density=None, anisotropy=None):
    """The HT Volumetrics material - one group node, knobs on the group."""
    density = VOLUME_DENSITY if density is None else float(density)
    anisotropy = VOLUME_ANISOTROPY if anisotropy is None else float(anisotropy)

    ng = _build_volume_group()

    mat = bpy.data.materials.get(VOLUME_MATERIAL)
    if mat is None:
        mat = bpy.data.materials.new(VOLUME_MATERIAL)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = ng
    grp.location = (0, 0)
    grp.width = 190
    grp.inputs["Density"].default_value = density
    grp.inputs["Anisotropy"].default_value = anisotropy
    # See VOLUME_COLOR: the default is grey and it dims the whole scene.
    grp.inputs["Color"].default_value = VOLUME_COLOR

    # VOLUME, not SURFACE. A box wired to Surface is an opaque cube around
    # the whole scene - a much louder failure than no volume at all, and an
    # easy one to cause, bc Surface is the socket everything else in
    # Blender connects to
    nt.links.new(grp.outputs["Volume"], out.inputs["Volume"])
    return mat


def _fit_eevee_volumetrics(scene, centre, size):
    """Open EEVEE's volumetric range far enough to contain the box.

    ONLY EVER OUTWARDS. Somebody who has tuned this for their own scene must
    not have it quietly reduced by an import.
    """
    ev = getattr(scene, "eevee", None)
    if ev is None or centre is None:
        return None
    # far corner measured from the origin, which is where an unmoved camera
    # sits and is a safe over-estimate for one that has moved into the box.
    reach = Vector(centre).length + Vector(size).length * 0.5
    try:
        if float(getattr(ev, "volumetric_end", 0.0)) < reach:
            ev.volumetric_end = float(reach)
        return float(ev.volumetric_end)
    except Exception:
        return None


def set_lights_volume_influence(lights, mode="ALL", elements=None):
    """
    Decide which lights scatter in the volume. Returns (on, off).

    `Light.volume_factor` is the control - measured as the only per-light
    volume property Blender 5.2 exposes.

    MODES
        ALL   every light scatters. THE DEFAULT, and it has to be.
        SFM   honour `DmeProjectedLight.volumetric`, the session's own
              per-light flag, which until now sat in UNMAPPED and was dropped.
        NONE  no light scatters; the box is lit by world light only.

    WHY `SFM` IS NOT THE DEFAULT THOUGH IT IS THE FAITHFUL ANSWER: measured on
    a real test session, ALL TEN lights carry `volumetric = False` -
    including the one the user named `volumetricLight2`. Faithful here means
    an empty box and a user reporting that volumetrics do not work, which is
    the exact complaint this feature exists to stop. So faithfulness is on the
    menu and it is not what a first import gets.
    """
    mode = (mode or "ALL").upper()
    if mode not in VOLUME_MODES:
        mode = "ALL"
    on = off = 0
    for i, obj in enumerate(lights or ()):
        data = getattr(obj, "data", None)
        if data is None or not hasattr(data, "volume_factor"):
            continue
        want = True
        if mode == "NONE":
            want = False
        elif mode == "SFM":
            elem = elements[i] if (elements and i < len(elements)) else None
            flag = None
            if elem is not None:
                try:
                    flag = elem.get("volumetric")
                except Exception:
                    flag = None
            want = bool(flag)
        data.volume_factor = VOLUME_FACTOR_ON if want else VOLUME_FACTOR_OFF
        on += 1 if want else 0
        off += 0 if want else 1
    return on, off


def _unit_cube(mesh):
    """Rewrite *mesh* as a cube from -1 to +1 on every axis."""
    verts = [(-1, -1, -1), (-1, -1, 1), (-1, 1, -1), (-1, 1, 1),
             (1, -1, -1), (1, -1, 1), (1, 1, -1), (1, 1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
             (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh.clear_geometry()
    mesh.from_pydata(verts, [], faces)
    mesh.update()



FILL_OBJECT = "HT_Fill (global)"
FILL_STRENGTH = 0.5
FILL_ANGLE_DEG = 180.0     #fully open: a sky, not a sun
FILL_HEIGHT_FACTOR = 1.5   #above the top of the lights' bounding box


def fill_colour(lights):
    """Energy-weighted mean colour of *lights*, brightest channel = 1."""
    acc = [0.0, 0.0, 0.0]
    weight = 0.0
    for ob in lights:
        d = getattr(ob, "data", None)
        if d is None or getattr(ob, "type", "") != "LIGHT":
            continue
        if ob.name == FILL_OBJECT:
            continue
        w = max(0.0, float(getattr(d, "energy", 0.0)))
        if w <= 0.0:
            continue
        for c in range(3):
            acc[c] += float(d.color[c]) * w
        weight += w
    if weight <= 0.0:
        return (1.0, 1.0, 1.0), 0
    col = [v / weight for v in acc]
    peak = max(col) or 1.0
    return tuple(v / peak for v in col), sum(
        1 for ob in lights if getattr(ob, "type", "") == "LIGHT"
        and ob.name != FILL_OBJECT)


def build_fill_light(lights, collection=None, strength=None):
    """Create - or recolour and move - the global fill. Returns a dict."""
    import math
    lights = [ob for ob in lights if getattr(ob, "type", "") == "LIGHT"]
    if not lights:
        return {"object": None, "reason": "no lights to average"}
    colour, n = fill_colour(lights)

    try:
        bpy.context.view_layer.update()
    except Exception:                                         # noqa: BLE001
        pass
    xs = [ob.matrix_world.translation for ob in lights]
    centre = [sum(v[i] for v in xs) / len(xs) for i in range(3)]
    top = max(v[2] for v in xs)
    span = max(1.0, max(max(v[i] for v in xs) - min(v[i] for v in xs)
                        for i in range(3)))

    col = collection or _light_collections()[0]
    obj = bpy.data.objects.get(FILL_OBJECT)
    if obj is None or obj.type != 'LIGHT' or obj.data.type != 'SUN':
        data = bpy.data.lights.new(FILL_OBJECT, type='SUN')
        obj = bpy.data.objects.new(FILL_OBJECT, data)
        col.objects.link(obj)
    else:
        for c in list(obj.users_collection):
            if c is not col:
                c.objects.unlink(obj)
        if obj.name not in col.objects:
            col.objects.link(obj)
    d = obj.data
    d.color = colour
    d.energy = FILL_STRENGTH if strength is None else float(strength)
    d.angle = math.radians(FILL_ANGLE_DEG)
    for prop, val in (("volume_factor", 0.0), ("use_shadow", False)):
        if hasattr(d, prop):
            setattr(d, prop, val)
    obj.location = (centre[0], centre[1],
                    top + span * (FILL_HEIGHT_FACTOR - 1.0) + 1.0)
    obj.rotation_mode = 'XYZ'
    obj.rotation_euler = (0.0, 0.0, 0.0)          # a sun points down -Z
    obj["ht_fill"] = ("global fill, not from SFM: energy-weighted mean colour "
                      "of %d light(s)" % n)
    print(f"[LIGHTS]  fill: '{FILL_OBJECT}' colour "
          f"({colour[0]:.2f} {colour[1]:.2f} {colour[2]:.2f}) from {n} "
          f"light(s), strength {d.energy:g}")
    return {"object": obj, "colour": colour, "from": n,
            "strength": d.energy}


def build_volume_box(lights, collection=None, density=None, anisotropy=None,
                     multiplier=None, scene=None):
    """
    Create - or resize - the volumetric box around *lights*. Returns a dict.

    Re-running reshapes the SAME object rather than adding a second box. Two
    nested boxes double the density of the world, which looks like the shader
    being wrong rather than like the import having run twice.
    """
    scene = scene or bpy.context.scene

    # RULE 20, in A NEW PLACE. `matrix_world` is not valid until the
    # depsgraph has run, and these lights were created moments ago - so
    # every one of them read as (0, 0, 0) and the box came out a 1000-unit
    # cube at the origin instead of the 2778 x 3677 x 1356 the session
    # actually spans. It looked like a plausible box, which is why it would
    # have shipped. Measured both ways before and after this line.
    try:
        bpy.context.view_layer.update()
    except Exception:
        pass

    centre, size = volume_bounds(lights, multiplier=multiplier)
    if centre is None:
        return {"object": None, "reason": "no lights to measure"}

    col = collection or _light_collections()[0]

    obj = bpy.data.objects.get(VOLUME_OBJECT)
    if obj is None or obj.type != 'MESH':
        mesh = bpy.data.meshes.new(VOLUME_OBJECT)
        obj = bpy.data.objects.new(VOLUME_OBJECT, mesh)
        col.objects.link(obj)
    else:
        # membership enforced every call - a box surviving from an import
        # that filed it in the Port comes home to the outer collection
        for c in list(obj.users_collection):
            if c is not col:
                c.objects.unlink(obj)
        if obj.name not in col.objects:
            try:
                col.objects.link(obj)
            except Exception:
                pass

    #A UNIT CUBE PLUS SCALE, not vertices at the final size. The box is
    #thousands of units across and somebody will want to nudge it; a scale
    #is a thing you can read and type into, and eight vertices at +/-1838
    #are not
    _unit_cube(obj.data)
    obj.location = centre
    obj.scale = (size[0] * 0.5, size[1] * 0.5, size[2] * 0.5)
    obj.rotation_euler = (0.0, 0.0, 0.0)

    # DISPLAY AS WIRE. Solid, it hides the entire scene in the viewport the
    # instant it appears, and the first thing anybody would do is delete it.
    obj.display_type = 'WIRE'
    obj.show_in_front = False
    # It must not cast a shadow of its own six faces over everything.
    if hasattr(obj, "visible_shadow"):
        obj.visible_shadow = False

    mat = _volume_material(density=density, anisotropy=anisotropy)
    obj.data.materials.clear()
    obj.data.materials.append(mat)

    far = _fit_eevee_volumetrics(scene, centre, size)

    return {
        "object": obj,
        "name": obj.name,
        "centre": tuple(round(v, 2) for v in centre),
        "size": tuple(round(v, 1) for v in size),
        "density": VOLUME_DENSITY if density is None else float(density),
        "anisotropy": (VOLUME_ANISOTROPY if anisotropy is None
                       else float(anisotropy)),
        "eevee_end": far,
        "reason": None,
    }


def sfm_position(v, scale=1.0):
    """SFM (x, y, z) -> Blender (y, -x, z). Same as the camera importer."""
    return Vector((float(v[1]), -float(v[0]), float(v[2]))) * scale


def sfm_orientation(v):
    """DMX (x,y,z,w) -> Quaternion(y, w, x, z), then the camera's fixup."""
    q = Quaternion((float(v[1]), float(v[3]), float(v[0]), float(v[2])))
    q.rotate(Euler((-math.pi / 2, 0.0, -math.pi)))
    return q



def _dag_parent_map(model):
    """{id(child element): parent DmeDag}, over every DAG in the file."""
    parent = {}
    for e in model.elements:
        if (e.type or "") != "DmeDag":
            continue
        for kid in (e.get("children") or []):
            parent.setdefault(id(kid), e)
    return parent


def _parent_chain(elem, parent_map):
    """The DmeDags above *elem*, root LAST -> reversed to root-first."""
    chain = []
    seen = {id(elem)}
    node = parent_map.get(id(elem))
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        chain.append(node)
        node = parent_map.get(id(node))
    chain.reverse()
    return chain


def _chain_matrix(chain):
    """One SFM-space matrix for a static DAG chain (root first)."""
    m = Matrix.Identity(4)
    for dag in chain:
        tr = dag.get("transform")
        if tr is None:
            continue
        p = tr.get("position")
        q = tr.get("orientation")
        loc = (Vector((float(p[0]), float(p[1]), float(p[2])))
               if p is not None else Vector((0.0, 0.0, 0.0)))
        rot = (Quaternion((float(q[3]), float(q[0]), float(q[1]),
                           float(q[2])))
               if q is not None else Quaternion())
        m = m @ Matrix.Translation(loc) @ rot.to_matrix().to_4x4()
    return m


def _lift_position(v, chain_m):
    """Local SFM position -> world SFM position, still in SFM axes."""
    return chain_m @ Vector((float(v[0]), float(v[1]), float(v[2])))


def _lift_orientation(v, chain_q):
    """Local DMX (x,y,z,w) -> world, returned in DMX order for
    sfm_orientation() - zero new conversion math on the way out."""
    q = chain_q @ Quaternion((float(v[3]), float(v[0]), float(v[1]),
                              float(v[2])))
    return (q.x, q.y, q.z, q.w)


def find_lights(model):
    """EVERY light element in the file, from every shot. See shot_lights()."""
    return [e for e in model.elements if (e.type or "") in LIGHT_TYPES]




def light_set_names(model):
    """{id(light element): animation set name} for every light set in a file."""
    out = {}
    for aset in model.elements:
        if (aset.type or "") != "DmeAnimationSet":
            continue
        try:
            elem = aset.get("light")
        except Exception:
            continue
        if elem is None or (getattr(elem, "type", "") or "") not in LIGHT_TYPES:
            continue
        out.setdefault(id(elem), aset.name or "")
    return out


def shot_lights(shot):
    """The light elements THIS shot's animation sets own, in file order.

    `shot` is a dict from `Session_Reader.shots()`. Returns [] for a shot with
    no light sets - a slug - which is correct and is not an error.
    """
    out = []
    seen = set()
    for aset in (shot.get("sets") or ()):
        try:
            elem = aset.get("light")
        except Exception:
            elem = None
        if elem is None or (getattr(elem, "type", "") or "") not in LIGHT_TYPES:
            continue
        if id(elem) in seen:
            continue
        seen.add(id(elem))
        out.append(elem)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# One light
# ─────────────────────────────────────────────────────────────────────────────

TWEAK_BRIGHTNESS_GLOBAL = 16.0


def energy_for(intensity, energy_scale, unit_scale,
               tweak=None):
    """
    Source intensity -> Blender watts, corrected for world scale.

    The scale term is the inverse square law, not a fudge: at ~52 Blender
    units per metre every distance in the scene is 52x what it would be in
    metres, so the light arriving at a surface is 52**2 - about 2,700x -
    weaker. Compensating there is the difference between a lit scene and a
    black one.

    TWEAK_BRIGHTNESS_GLOBAL is the taste term on top of that - see its
    comment. *tweak* overrides it, which exists so a test can pin the value
    rather than track whatever the constant currently is.
    """
    t = TWEAK_BRIGHTNESS_GLOBAL if tweak is None else float(tweak)
    return (float(intensity) * float(energy_scale)
            * (float(unit_scale) ** 2) * t)


def _apply_static(light_obj, elem, energy_scale, spot_blend, unit_scale=1.0,
                  scale=1.0, desaturate_factor=1.0):
    """Map the SFM attributes onto the Blender light. Returns notes.

    MEASURED 2026-08-27, because the user reported radius and the cone
    angle as "not read": they ARE - on the Gothic session, spot 80.3 deg vs
    horizontalFOV 80.3, shadow_soft_size 22.43 vs radius 22.43, use_shadow
    False where castsShadows is False. A scene imported before 2026-08-22,
    when these were still on the UNMAPPED list, keeps the old values until
    step 7 is re-run - that is what "not read" looks like from the outside.
    """
    data = light_obj.data
    notes = []

    intensity = elem.get("intensity")
    if intensity is not None:
        data.energy = energy_for(intensity, energy_scale, unit_scale)

    col = elem.get("color")
    if col is not None:
        try:
            data.color = desaturate((_srgb_to_linear(col[0]),
                                     _srgb_to_linear(col[1]),
                                     _srgb_to_linear(col[2])),
                                    desaturate_factor)
            if len(col) > 3 and int(col[3]) != 255:
                notes.append(f"colour alpha {col[3]} ignored")
        except Exception:
            notes.append("colour unreadable")

    h = elem.get("horizontalFOV")
    v = elem.get("verticalFOV")
    if h is not None:
        # Blender's spot cone is circular. SFM can be elliptical, so take the
        # wider axis and say so rather than silently cropping the beam.
        fov = float(h)
        if v is not None and abs(float(v) - fov) > 0.5:
            fov = max(fov, float(v))
            notes.append(f"elliptical cone {float(h):g}x{float(v):g} deg "
                         f"flattened to {fov:g}")
        data.spot_size = math.radians(min(179.0, max(1.0, fov)))
        data.spot_blend = spot_blend

    shadows = elem.get("castsShadows")
    if shadows is not None:
        try:
            data.use_shadow = bool(shadows)
        except Exception:
            pass

    max_d = elem.get("maxDistance")
    try:
        if max_d is not None and float(max_d) > 0.0 and \
                hasattr(data, "use_custom_distance"):
            data.use_custom_distance = True
            data.cutoff_distance = float(max_d) * scale
    except Exception:
        pass

    radius = elem.get("radius")
    if radius is not None:
        # TIMES THE IMPORT SCALE. radius is in Hammer units like everything
        # else in the file; at the default scale 1.0 this changes nothing,
        # but a 0.01905 metric import used to keep a HU-sized soft shadow.
        data.shadow_soft_size = max(0.0, float(radius) * scale)

    # shadowFilterSize -> EEVEE's shadow filter radius. Same job on both
    # sides: how much the shadow map is blurred, independent of the
    # emitter's physical size (which radius already carries for Cycles)
    # Measured range in real sessions: 0.35..0.76, comfortably inside
    # Blender's scale for the property. hasattr-guarded - the property is
    # EEVEE's and builds differ
    filt = elem.get("shadowFilterSize")
    if filt is not None and hasattr(data, "shadow_filter_radius"):
        try:
            data.shadow_filter_radius = max(0.0, float(filt))
        except Exception:
            pass

    # minDistance -> shadow clip start, where the build has one. SFM uses
    # it as "nothing nearer than this casts", which is exactly what the
    # shadow buffer clip start means.
    near = elem.get("minDistance")
    if near is not None and float(near) > 0.0:
        for prop in ("shadow_buffer_clip_start",):
            if hasattr(data, prop):
                try:
                    setattr(data, prop, float(near) * scale)
                except Exception:
                    pass
                break

    far = elem.get("maxDistance")
    if far is not None and float(far) > 0.0:
        try:
            data.use_custom_distance = True
            data.cutoff_distance = float(far) * scale
        except Exception:
            notes.append("cutoff distance unsupported on this build")

    visible = elem.get("visible")
    if visible is not None and not bool(visible):
        light_obj.hide_viewport = True
        light_obj.hide_render = True
        notes.append("light is hidden in the session")

    tex = elem.get("texture")
    if tex:
        notes.append(f"gobo '{tex}' not applied")
    if elem.get("volumetric"):
        notes.append("volumetric not applied")
    if elem.get("uberlight"):
        notes.append("uberlight rectangle not applied")

    return notes


def _rescale_of(channel):
    """
    The (lo, hi) a light channel's value is lerped through, or None.

    Same trick SFM plays with cameras (see Session_Reader._rescale_of): the
    session stores a NORMALISED 0..1 slider and routes it through a
    DmeExpressionOperator whose expr is `lerp(value, lo, hi)`. The
    `scaled_<attr>_channel` sitting on the light element itself carries ZERO
    keys - it is only a mirror - so reading that and stopping is why an
    animated light arrived with no keyframes at all.
    """
    to = channel.get("toElement")
    if to is None or (to.type or "") != "DmeExpressionOperator":
        return None
    try:
        expr = str(to.get("expr") or "")
        if "lerp" not in expr:
            return None
        lo, hi = to.get("lo"), to.get("hi")
        if lo is None or hi is None:
            return None
        return float(lo), float(hi)
    except Exception:
        return None


def _log_of(ch):
    """(times, values) for a channel, or (None, None)."""
    log = ch.get("log")
    if log is None:
        return None, None
    layers = log.get("layers")
    if not layers:
        return None, None
    times = layers[0].get("times")
    values = layers[0].get("values")
    if not times or not values or len(times) != len(values):
        return None, None
    return times, values


def _animate_transform(light_obj, elem, by_target, frame_rate, start, scale,
                       chain_m=None, chain_q=None):
    """
    Key the light's MOVEMENT.

    A light that moves in SFM is animated on its DmeTransform, not on the
    DmeProjectedLight - `transform_pos` and `transform_rot`, exactly like a
    camera. The old code only looked at channels whose toElement was the
    light element itself, so it never saw these and every light came in
    nailed to its first frame. On `new session.dmx` that is 649 position and
    543 orientation keys per light, silently dropped.

    The keyed values are LOCAL to the light's parent DAG, exactly like the
    static ones - so they take the same chain lift before the world map.
    """
    tr = elem.get("transform")
    if tr is None:
        return 0
    if chain_m is None:
        chain_m = Matrix.Identity(4)
    if chain_q is None:
        chain_q = Quaternion()

    action, bag = make_action(f"{light_obj.name}_xform", light_obj)
    light_obj.rotation_mode = 'QUATERNION'
    keyed = 0

    for ch in by_target.get(id(tr), []):
        attr = ch.get("toAttribute") or ""
        times, values = _log_of(ch)
        if times is None:
            continue
        if attr == "position":
            for t, v in zip(times, values):
                f = (float(t) + start) * frame_rate
                loc = sfm_position(_lift_position(v, chain_m), scale)
                for i in range(3):
                    fc = fc_find_or_new(bag, "location", i, "light")
                    fc.keyframe_points.insert(f, loc[i], options={"FAST"})
                    keyed += 1
        elif attr == "orientation":
            # 1.17.3: walked onto one hemisphere before keying. The camera's
            # formula (sfm_orientation) puts a light facing SFM yaw 0 on the
            # sign boundary, so neighbouring samples came out q and -q and the
            # keys in between spun the long way round (only the final Euler
            # step, when it ran, cleaned that up)
            from ..core import camera_resample as _CR
            rows = sorted((((float(t) + start) * frame_rate,
                            sfm_orientation(_lift_orientation(v, chain_q)))
                           for t, v in zip(times, values)), key=lambda r: r[0])
            rows, _walked = _CR.hemisphere_walk(rows)
            for f, q in rows:
                for i in range(4):
                    fc = fc_find_or_new(bag, "rotation_quaternion", i, "light")
                    fc.keyframe_points.insert(f, q[i], options={"FAST"})
                    keyed += 1

    if keyed:
        for fc in iter_fcurves(action, light_obj):
            fc.update()
    else:
        try:
            bpy.data.actions.remove(action)
        except Exception:
            pass
    return keyed


def _channels_by_target(model):
    """{id(target element): [DmeChannel, ...]} for the whole file. Built ONCE
    per import - it used to be rebuilt per light, a full element scan each."""
    by_target = {}
    for e in model.elements:
        if (e.type or "") != "DmeChannel":
            continue
        to = e.get("toElement")
        if to is not None:
            by_target.setdefault(id(to), []).append(e)
    return by_target


def _animate(light_obj, elem, model, energy_scale, frame_rate, start,
             unit_scale=1.0, scale=1.0, by_target=None,
             chain_m=None, chain_q=None, desaturate_factor=1.0):
    """
    Key whatever the session animated: movement first, then the light values.

    Two things used to stop this finding anything. The MOVEMENT lives on the
    light's DmeTransform, not on the light element. And the VALUE channels on
    the light element are `scaled_<attr>_channel` mirrors holding zero keys -
    the real curve sits behind a lerp operator, the same normalised-slider
    arrangement the camera importer already knew about.
    """
    if by_target is None:
        by_target = _channels_by_target(model)

    keyed = _animate_transform(light_obj, elem, by_target, frame_rate, start,
                               scale, chain_m=chain_m, chain_q=chain_q)

    channels = by_target.get(id(elem), [])

    data = light_obj.data
    action = None
    bag = None

    def _frame(t):
        return (float(t) + start) * frame_rate

    for ch in channels:
        attr = ch.get("toAttribute") or ""
        if attr not in ("intensity", "horizontalFOV", "verticalFOV", "color"):
            continue
        log = ch.get("log")
        if log is None:
            continue
        layers = log.get("layers")
        if not layers:
            continue
        times = layers[0].get("times")
        values = layers[0].get("values")
        if not times or not values or len(times) != len(values):
            continue

        if action is None:
            action, bag = make_action(f"{light_obj.name}_light", data)

        for t, val in zip(times, values):
            f = _frame(t)
            if attr == "intensity":
                fc = fc_find_or_new(bag, "energy", 0, "light")
                fc.keyframe_points.insert(
                    f, energy_for(val, energy_scale, unit_scale),
                    options={"FAST"})
                keyed += 1
            elif attr in ("horizontalFOV", "verticalFOV"):
                fc = fc_find_or_new(bag, "spot_size", 0, "light")
                fc.keyframe_points.insert(
                    f, math.radians(min(179.0, max(1.0, float(val)))),
                    options={"FAST"})
                keyed += 1
            elif attr == "color":
                # reached only by a channel that writes the light's `color`
                # DIRECTLY. In every session measured those carry ZERO keys -
                # the real animation arrives thru a pack operator, handled
                # by _animate_color() below. Kept because a hand-built or
                # future session could key it here, and dropping the branch
                # would make that silently do nothing
                lin = desaturate((_srgb_to_linear(val[0]),
                                  _srgb_to_linear(val[1]),
                                  _srgb_to_linear(val[2])),
                                 desaturate_factor)
                for i in range(3):
                    fc = fc_find_or_new(bag, "color", i, "light")
                    fc.keyframe_points.insert(f, lin[i], options={"FAST"})
                    keyed += 1

    if action is not None:
        for fc in iter_fcurves(action, data):
            fc.update()
    return keyed


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def _pack_for_light(elem, model):
    """The DmePackColorOperator driving this light's colour, or None."""
    for ch in model.elements:
        if (ch.type or "") != "DmeChannel":
            continue
        try:
            if ch.get("toAttribute") != "color":
                continue
            if ch.get("toElement") is not elem:
                continue
            src = ch.get("fromElement")
        except Exception:
            continue
        if src is not None and (src.type or "") == "DmePackColorOperator":
            return src
    return None


def _animate_color(light_obj, elem, model, frame_rate, start,
                   desaturate_factor=1.0):
    """Key the light's colour from its pack operator. Returns keys written.

    THE DESATURATE FACTOR NEEDS ALL THREE CHANNELS AT ONCE - luma is a
    property of the triple, and the pack operator keys red, green and blue
    on INDEPENDENT times (327/340/98 keys on the user's colour-animated
    light). So each key's missing channels are linearly interpolated from
    their own curves (static colour as the fallback for a channel with no
    curve at all), the luma is taken of that instant's real triple, and
    only then is the keyed channel pulled toward it. Desaturating each
    channel against the STATIC colour's luma instead would visibly pump
    brightness whenever the animation moves away from the static hue."""
    pack = _pack_for_light(elem, model)
    if pack is None:
        return 0

    #{channel index: [(frame, linear value)]} - r, g, b. Alpha is read and
    #dropped: a Blender light has no alpha and inventing one would be a
    #fourth curve nobody asked for.
    per_channel = {}
    for ch in model.elements:
        if (ch.type or "") != "DmeChannel":
            continue
        try:
            if ch.get("toElement") is not pack:
                continue
            attr = ch.get("toAttribute")
        except Exception:
            continue
        idx = {"red": 0, "green": 1, "blue": 2}.get(attr)
        if idx is None:
            continue
        log = ch.get("log")
        layers = log.get("layers") if log is not None else None
        if not layers:
            continue
        times = layers[0].get("times")
        values = layers[0].get("values")
        if not times or not values or len(times) != len(values):
            continue
        per_channel[idx] = [
            ((float(t) + start) * frame_rate, _srgb_to_linear(float(v) * 255.0))
            for t, v in zip(times, values)
        ]

    if not per_channel:
        return 0

    if desaturate_factor < 1.0 - 1e-6:
        # static linear colour = the fallback for a channel with no curve
        static_lin = (1.0, 1.0, 1.0)
        col = elem.get("color")
        if col is not None:
            try:
                static_lin = (_srgb_to_linear(col[0]),
                              _srgb_to_linear(col[1]),
                              _srgb_to_linear(col[2]))
            except Exception:                                 # noqa: BLE001
                pass

        srt = {i: sorted(p) for i, p in per_channel.items()}

        def _at(idx, f):
            pairs = srt.get(idx)
            if not pairs:
                return static_lin[idx]
            if f <= pairs[0][0]:
                return pairs[0][1]
            if f >= pairs[-1][0]:
                return pairs[-1][1]
            import bisect
            k = bisect.bisect_left(pairs, (f, float("-inf")))
            (f0, v0), (f1, v1) = pairs[k - 1], pairs[k]
            w = (f - f0) / (f1 - f0) if f1 > f0 else 0.0
            return v0 + (v1 - v0) * w

        for idx, pairs in per_channel.items():
            out = []
            for f, v in pairs:
                triple = [_at(0, f), _at(1, f), _at(2, f)]
                triple[idx] = v
                out.append((f, desaturate(triple, desaturate_factor)[idx]))
            per_channel[idx] = out

    data = light_obj.data
    # REUSE the ACTION `_animate` JUST MADE. `make_action` always creates a
    # NEW one and assigns it, so calling it here would throw away the
    # intensity and cone curves written moments ago - the colour would work
    # and everything else would silently vanish
    ad = getattr(data, "animation_data", None)
    action = ad.action if (ad is not None and ad.action is not None) else None
    if action is None:
        action, bag = make_action(f"{light_obj.name}_light", data)
    else:
        bag = get_channelbag(action, data)
    keyed = 0
    for idx, pairs in per_channel.items():
        fc = fc_find_or_new(bag, "color", idx, "light")
        for f, v in pairs:
            fc.keyframe_points.insert(f, v, options={"FAST"})
            keyed += 1
    for fc in iter_fcurves(action, data):
        fc.update()
    return keyed


def import_lights(dmx_path, scale=1.0, energy_scale=1.0, spot_blend=0.15,
                  aim_offset=(0.0, 0.0, 0.0), do_animation=True,
                  unit_scale=52.0, volume_box=True, fill_light=True,
                  volume_lights='SFM', volume_density=None,
                  volume_anisotropy=None, attenuation_nodes=True,
                  shot_index=None, shot_name=None,
                  desaturate_factor=DESATURATE_DEFAULT, skip_names=None):
    """
    Rebuild every light in *dmx_path*. 1.26.0: `skip_names` - set names to
    leave out (Skip Hidden Objects, the lights SFM hides). Never raises for a light it cannot
    map - it records the reason and moves on.

    Returns a summary dict, including `unmapped`, a sorted list of the SFM
    attributes that were present and had nowhere to go.
    """
    from ..SST import get_datamodel
    from ..core import DMX_Analyzer

    dmx_path = Path(dmx_path)
    dm = get_datamodel()
    model = dm.load(DMX_Analyzer.long_path(dmx_path))

    lights = find_lights(model)
    total_in_file = len(lights)
    shot_used = None
    shot_note = ""
    shot_ref = None          # the shot's reference timeFrame triple, if known
    time_shot = None         # 1.17.0: the chosen shot, for its timeline shift

    # NARROW TO one CUT. Only when a shot was actually chosen: with no choice
    # the whole session is the job, which is what every earlier version did
    # and what a one-shot session means anyway
    if shot_index is not None and int(shot_index) >= 0:
        try:
            from ..session import Session_Reader as _SR, Session_Paths as _SP
            shot_list = _SR.shots(model)
            shot, shot_note = _SP.resolve_shot(shot_list, index=int(shot_index),
                                               name=shot_name or "")
            if shot is not None:
                picked = shot_lights(shot)
                #A SHOT WITH NO LIGHT SETS KEEPS the WHOLE FILE rather than
                #importing nothing. Returning [] here would turn "this cut
                #has no lights of its own" into "the light importer is
                #broken", and the two look identical from the outside
                if picked:
                    lights = picked
                    shot_used = shot.get("name")
                else:
                    shot_note = (f"{shot.get('name')} has no light sets - "
                                 f"importing every light in the file")
                # the shot's elected time base - light keys must land on
                # the same timeline the extracted animation lands on, and
                # that timeline is per clip, not per file (Gomez: clip
                # bases in one film differ by up to 55.6 s)
                try:
                    shot_ref = _SR.shot_time_base(model, shot)["clip_tf"]
                    time_shot = shot
                except Exception:                             # noqa: BLE001
                    shot_ref = None
        except Exception as exc:                              # noqa: BLE001
            print(f"[LIGHTS]  shot filter unavailable ({exc}) - "
                  f"importing every light")

    if not lights:
        raise RuntimeError(f"No light elements in {dmx_path.name}")

    # frame rate for any animation, from wherever this file keeps its clip
    frame_rate, start = 0.0, 0.0
    clip = DMX_Analyzer.find_clip(model.root)
    if clip is not None:
        frame_rate = float(clip.get("frameRate") or 0.0)
        tf = clip.get("timeFrame")
        if tf is not None:
            start = float(tf.get("start") or 0.0)
    # 1.17.0: A SESSION'S CLIPS CARRY no frameRate (Session_Reader's module
    # notes: "clip has none") - the rate lives in settings.renderSettings
    # This read 24 for every session, so on the 30 fps gothic intro every
    # light key landed at 24/30 of its time: light2 at -258 instead of -323,
    # the skydome lights at -988 instead of -1235. The animation importer
    # reads the session rate; the lights now read the same one.
    if not frame_rate:
        try:
            from ..session import Session_Reader as _SRf
            frame_rate = float(_SRf.session_fps(model.root) or 24.0)
        except Exception:                                     # noqa: BLE001
            frame_rate = 24.0

    col = _get_collection()
    axis = _axis_empty(col)
    # no +90 X HERE. sfm_position()/sfm_orientation() already map SFM into
    # Blender - they are the camera importer's conversion, world map included -
    # so a rotation on this parent applies it a SECOND time. Measured on
    # `new session.dmx`: light1 sits at (262.19, 14.46, 171.28) in the session,
    # sfm_position gives the correct (14.5, -262.2, 171.3), and the +90 X then
    # dragged it to (14.5, -171.3, -262.2) - underground, with the whole rig
    # tipped over. The empty stays as a grouping parent; aim_offset is still
    # honoured bc that is a deliberate user nudge.
    axis.rotation_euler = tuple(aim_offset)

    made, failed, keyed_total = [], [], 0
    # kept alongside `made` and in the same order, so `volume_lights='SFM'`
    # can ask each light's own element for its `volumetric` flag without
    # re-finding it by name - which is the lookup that goes wrong the moment
    # two shots both contain a light called `light1`.
    made_elems = []
    atten = {}
    colour_keyed = {}
    # {light: {property: why it was not driven}} - a driver skipped for a
    # good reason (the property is animated) must not look like one that
    # failed silently
    driven_skips = {}
    notes = {}
    unmapped_seen = set()

    label_of = light_set_names(model)
    skipped_hidden = []
    if skip_names:
        keep = []
        for elem in lights:
            nm = label_of.get(id(elem)) or elem.name or "light"
            (skipped_hidden if nm in skip_names else keep).append(elem)
        skipped_hidden = sorted(label_of.get(id(e)) or e.name or "light" for e in skipped_hidden)
        lights = keep
    parent_map = _dag_parent_map(model)
    by_target = _channels_by_target(model)
    #which channels clip holds each channel - a light's own clip carries
    #its time base, and on a multi-shot film that base is per clip.
    clip_of_channel = {}
    for _cl in model.elements:
        if (_cl.type or "") == "DmeChannelsClip":
            for _ch in (_cl.get("channels") or []):
                clip_of_channel[id(_ch)] = _cl

    #1.17.0: the shot each light is timed through. A chosen shot is the
    #answer; with none, MOVIE timing times each light through its own
    #shot (Session_Reader.element_shots) - the old global start would put
    #a whole film's lights on extract time while the rigs sit on movie
    #time
    from ..session import Session_Reader as _SRt
    _mode = _SRt.timing_mode()
    _own_shot = {}
    if time_shot is None and _mode == _SRt.TIMING_MOVIE:
        try:
            _own_shot = _SRt.element_shots(_SRt.shots(model))
        except Exception:                                     # noqa: BLE001
            _own_shot = {}
    _bases = {}

    def _base(sh):
        if id(sh) not in _bases:
            _bases[id(sh)] = _SRt.shot_time_base(model, sh)
        return _bases[id(sh)]

    def _start_for(elem):
        """The seconds added to this light's raw key times so they land on
        the Blender timeline: the rebase onto its shot's reference clip -
        the same one clip_base_shift() gives the extracted animation - plus
        the shot's placement on SFM's movie clock (1.17.0,
        Session_Reader.clip_timeline_shift). Without any shot, the old
        global start stands."""
        sh = time_shot if time_shot is not None else _own_shot.get(id(elem))
        if sh is None:
            return start
        tr = elem.get("transform")
        chans = (by_target.get(id(tr), []) if tr is not None else []) \
            + by_target.get(id(elem), [])
        for ch in chans:
            cl = clip_of_channel.get(id(ch))
            if cl is None:
                continue
            return _SRt.clip_timeline_shift(model, sh, cl, mode=_mode,
                                            base=_base(sh), fps=frame_rate)
        return _SRt.place_shift(model, sh, mode=_mode, base=_base(sh))

    for _n_light, elem in enumerate(lights, 1):
        # the set's name first - see light_set_names(). The element name is
        # the fallback for a light no set points at, which a hand-edited
        # session can produce.
        name = label_of.get(id(elem)) or elem.name or "light"
        Progress.update(_n_light, len(lights), name)
        try:
            data = bpy.data.lights.new(f"{name}_data", type='SPOT')
            obj = bpy.data.objects.new(name, data)
            col.objects.link(obj)
            obj.parent = axis
            obj.rotation_mode = 'QUATERNION'

            # the wrapper DAGs above this light, composed - identity for
            # a light whose parents all sit at the origin, which is every
            # session before Gomez.
            chain = _parent_chain(elem, parent_map)
            chain_m = _chain_matrix(chain)
            chain_q = chain_m.to_quaternion()
            for d in chain:
                d_tr = d.get("transform")
                if d_tr is not None and by_target.get(id(d_tr)):
                    print(f"[LIGHTS]  {name}: parent DAG {d.name!r} is "
                          f"ANIMATED - only its static transform is applied")

            lstart = _start_for(elem)
            if abs(lstart - start) > 1e-6:
                print(f"[LIGHTS]  {name}: keys shifted {lstart:+.4f}s onto "
                      f"the Blender timeline (clip rebase + shot placement)")

            tr = elem.get("transform")
            if tr is not None:
                pos = tr.get("position")
                ori = tr.get("orientation")
                if pos is not None:
                    obj.location = sfm_position(
                        _lift_position(pos, chain_m), scale)
                if ori is not None:
                    obj.rotation_quaternion = sfm_orientation(
                        _lift_orientation(ori, chain_q))

            n = _apply_static(obj, elem, energy_scale, spot_blend,
                              unit_scale=unit_scale, scale=scale,
                              desaturate_factor=desaturate_factor)
            if n:
                notes[name] = n

            for a in UNMAPPED:
                if elem.get(a) is not None:
                    unmapped_seen.add(a)

            if attenuation_nodes:
                a = apply_attenuation_nodes(obj, elem)
                if a is not None:
                    atten[obj.name] = a
                # the full SFM attribute panel on the shader. The uberlight
                # builder already made and LINKED this node when the light
                # had shaping; this is get-or-create, so a light w/o
                # shaping still gets its panel and nothing is unwired
                try:
                    apply_sfm_data_node(obj, elem)
                except Exception as exc:                      # noqa: BLE001
                    print(f"[LIGHTS]  {name}: SFM data node failed ({exc})")

            if do_animation:
                keyed_total += _animate(obj, elem, model, energy_scale,
                                        frame_rate, lstart,
                                        unit_scale=unit_scale, scale=scale,
                                        by_target=by_target,
                                        chain_m=chain_m, chain_q=chain_q,
                                        desaturate_factor=desaturate_factor)
                n_col = _animate_color(obj, elem, model, frame_rate, lstart,
                                       desaturate_factor=desaturate_factor)
                keyed_total += n_col
                if n_col:
                    colour_keyed[obj.name] = n_col

            #last, and that ordering is the whole safety argument: the
            #drivers are added only to properties the animation above did
            #NOT key, and it has to have run to know which those are
            if attenuation_nodes and LIGHT_DRIVERS:
                try:
                    sk = drive_from_data(obj, scale=scale,
                                         energy_scale=energy_scale,
                                         unit_scale=unit_scale)
                    if sk:
                        driven_skips[obj.name] = sk
                except Exception as exc:                      # noqa: BLE001
                    print(f"[LIGHTS]  {name}: drivers failed ({exc})")
            else:
                # 1.16.0: no drivers - and none left over from an older
                # import of the same light either
                gone = strip_light_drivers(obj)
                if gone:
                    print(f"[LIGHTS]  {name}: removed {gone} old driver(s)")
            made.append(obj)
            made_elems.append(elem)
        except Exception as exc:
            failed.append((name, f"{type(exc).__name__}: {exc}"))

    # after the loop, because the box is sized from where the lights ENDED
    # UP - a light that failed to build must not stretch the world, and one
    # that was keyed into motion is still measured at its rest position,
    # which is the honest answer for a static box.
    vol_on, vol_off = set_lights_volume_influence(
        made, mode=volume_lights, elements=made_elems)
    volume = {"object": None, "reason": "not requested"}
    if volume_box and made:
        try:
            volume = build_volume_box(made,
                                      density=volume_density,
                                      anisotropy=volume_anisotropy)
        except Exception as exc:
            volume = {"object": None,
                      "reason": f"{type(exc).__name__}: {exc}"}

    fill = {"object": None, "reason": "not requested"}
    if fill_light and made:
        try:
            fill = build_fill_light(made)
        except Exception as exc:                              # noqa: BLE001
            fill = {"object": None,
                    "reason": f"{type(exc).__name__}: {exc}"}

    return {
        "fill": fill,
        "lights": made,
        "count": len(made),
        "failed": failed,
        "volume": volume,
        "volume_lights": (volume_lights or "SFM").upper(),
        "attenuation": atten,
        "colour_keyed": colour_keyed,
        "driver_skips": driven_skips,
        "volume_on": vol_on,
        "volume_off": vol_off,
        "keyed": keyed_total,
        "collection": col.name,
        "notes": notes,
        "unmapped": sorted(unmapped_seen),
        "frame_rate": frame_rate,
        "shot": shot_used,
        "shot_note": shot_note,
        "in_file": total_in_file,
        "skipped_other_shots": total_in_file - len(lights) - len(skipped_hidden),
        "skipped_hidden": skipped_hidden,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Operator
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_import_lights(Operator, ImportHelper):
    """PICK .dmx (session) - the lights live inside the session; there is no
        separate light file

        Rebuild the session's SFM lights as Blender spot lights

SFM stores every light as one element type - DmeProjectedLight, 45
attributes, essentially a Blender spot.

WHAT MAPS: intensity, colour, cone angle, shadows, cutoff distance, and
the light's keyed MOVEMENT - which lives on the light's own transform
rather than on the light element and is easy to miss entirely. One light
in the test session carries over 4,000 transform keys.

WHAT DOES NOT: about 29 Source parameters have no honest Blender
equivalent - uberlight, the attenuation triple, volumetrics, the gobo
texture, shadow tuning. They are REPORTED, never silently dropped and
never guessed at.
    """

    bl_idname = "ht.import_lights"
    bl_label = "Import Lights (Experimental)"
    # NO "REGISTER" - see the note in Report_UI/the constitution
    # REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    # touching any field in it RE-RUNS this operator. Re-running an
    # import re-reads the DMX and rebuilds every f-curve; nudging Scale
    # there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    # with the value you wanted is the safe way to change your mind
    bl_options = {"UNDO"}

    filename_ext = ".dmx"
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    scale: FloatProperty(  # type: ignore
        name="Scale",
        description="World scale - match your session import scale",
        default=1.0, min=1e-6, soft_min=0.0001, soft_max=100.0,
        precision=6, step=1,
    )
    energy_scale: FloatProperty(  # type: ignore
        name="Energy Scale",
        description=("Multiplier from Source intensity to Blender watts. "
                     "There is no correct value - Source intensity is "
                     "neither watts nor lumens, and 500 is an ordinary "
                     "reading - so this is a taste control, not a "
                     "conversion. Start at 1.0 and judge by eye"),
        default=1.0, min=0.0, soft_max=100.0, precision=4,
    )
    unit_scale: FloatProperty(  # type: ignore
        name="Units Per Metre",
        description=("How many Blender units make a metre in this scene. "
                     "Source imports at about 52 (1 Hammer unit ~ 0.019 m). "
                     "Blender light falls off with the SQUARE of distance, so "
                     "a 52x bigger world needs 52*52 - about 2700x - more "
                     "energy to look the same. This is squared for you: give "
                     "the linear scale. Use 1.0 for a scene built in metres"),
        default=52.0, min=0.0001, soft_max=1000.0, precision=3,
    )
    spot_blend: FloatProperty(  # type: ignore
        name="Cone Softness",
        description=("Blender spot_blend for every imported light. SFM's "
                     "edge controls belong to the uberlight rectangle and "
                     "do not map onto a round cone, so this is a flat "
                     "default rather than a translation"),
        default=0.15, min=0.0, max=1.0,
    )
    desaturate: FloatProperty(  # type: ignore
        name="Desaturate Factor",
        description=("How much of each light's colour saturation to keep. "
                     "1.0 = the session's exact colours; 0.6 default - "
                     "Source's lighting model washes colour out on the way "
                     "to the screen, so faithful colours read MORE saturated "
                     "in Blender than the same shot in SFM. Applied to the "
                     "static colour and every colour animation key alike"),
        default=DESATURATE_DEFAULT, min=0.0, max=1.0, precision=3,
    )
    aim_offset: FloatVectorProperty(  # type: ignore
        name="Aim Offset",
        description=("Extra rotation on the parent axis empty, in case the "
                     "beams point the wrong way. Position and orientation "
                     "use the camera importer's verified formulas, so this "
                     "should stay at zero"),
        default=(0.0, 0.0, 0.0), subtype='EULER',
    )
    do_animation: BoolProperty(  # type: ignore
        name="Import Animation",
        description=("Key intensity, colour and cone angle where the "
                     "session animated them"),
        default=True,
    )

    # ── the volumetric box ───────────────────────────────────────────────
    # ON BY DEFAULT, and that's the feature. A spot light in empty space
    # looks identical with volumetrics on and off, so an import w/o a
    # volume to scatter in reads as "Blender doesn't do volumetrics".
    volume_box: BoolProperty(  # type: ignore
        name="Volumetric Box",
        description=("Build a large Principled Volume box around the lights "
                     "so their beams are actually visible. Blender needs "
                     "something for light to scatter IN - without it a spot "
                     "in empty air looks the same whether volumetrics are on "
                     "or not, which is why people think Blender has none. "
                     "Sized from the lights' own bounding box, blown up 10x, "
                     "and EEVEE's volumetric range is opened to match. Wire "
                     "display, so it does not hide the scene. Re-running "
                     "resizes the same box rather than nesting a second one"),
        default=True,
    )
    volume_lights: EnumProperty(  # type: ignore
        name="Lights In Volume",
        description=("Which lights scatter in the box, via each light's "
                     "Volume Factor"),
        items=[
            ('ALL', "All Lights",
             "Every imported light scatters in the box. The default"),
            ('SFM', "Only SFM Volumetric",
             "Honour each light's own `volumetric` flag from the session. "
             "FAITHFUL, AND USUALLY EMPTY - measured on a real session all "
             "ten lights carry volumetric=False, so expect nothing to "
             "scatter unless you set the flag in SFM"),
            ('NONE', "No Lights",
             "The box exists but no light scatters in it - world light only"),
        ],
        default='SFM',
    )
    volume_density: FloatProperty(  # type: ignore
        name="Volume Density",
        description=("Principled Volume density. The box is thousands of "
                     "units across and optical depth is density x distance, "
                     "so a little goes a very long way - 0.000015 matches "
                     "SFM's look, 0.005 was white soup"),
        default=VOLUME_DENSITY, min=0.0, soft_max=1.0, precision=6, step=0.1,
    )
    volume_anisotropy: FloatProperty(  # type: ignore
        name="Volume Anisotropy",
        description=("How much light scatters FORWARD. 0 is even fog; "
                     "0.28 keeps a beam readable without the starburst "
                     "0.745 used to paint around every light"),
        default=VOLUME_ANISOTROPY, min=-1.0, max=1.0, precision=3,
    )

    def draw(self, context):
        col = self.layout.column()
        box = col.box()
        box.label(text="Experimental - roadmap #15", icon='ERROR')
        sub = box.column(align=True)
        sub.scale_y = 0.8
        sub.label(text="Best effort. Unmappable Source")
        sub.label(text="parameters are listed, not applied.")
        col.separator()
        col.prop(self, "scale")
        col.prop(self, "energy_scale")
        col.prop(self, "unit_scale")
        col.prop(self, "spot_blend")
        col.separator()
        col.prop(self, "do_animation")
        col.prop(self, "aim_offset")

    def execute(self, context):
        try:
            r = import_lights(self.filepath, scale=self.scale,
                              energy_scale=self.energy_scale,
                              unit_scale=self.unit_scale,
                              spot_blend=self.spot_blend,
                              aim_offset=tuple(self.aim_offset),
                              do_animation=self.do_animation,
                              desaturate_factor=self.desaturate)
        except Exception as exc:
            self.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}

        lines = [
            f"File     : {Path(self.filepath).name}",
            f"Lights   : {r['count']}",
        ]
        if r["keyed"]:
            lines.append(f"Keys     : {r['keyed']} (at {r['frame_rate']:g} fps)")
        if r["failed"]:
            lines.append(f"Failed   : {len(r['failed'])}")
        lines.append(f"Collection: {r['collection']}")
        if r["unmapped"]:
            lines.append("")
            lines.append("Present in SFM, no Blender equivalent:")
            row = ", ".join(r["unmapped"])
            while row:
                lines.append("  " + row[:46])
                row = row[46:]

        print()
        for line in lines:
            print(f"[LIGHTS]  {line}")
        for name, notes in r["notes"].items():
            for n in notes:
                print(f"[LIGHTS]  {name}: {n}")
        for name, err in r["failed"]:
            print(f"[LIGHTS]  {name} FAILED: {err}")

        level = "WARNING" if r["failed"] else "INFO"
        from ..core import Report_UI
        Report_UI.report(context, "import_lights", "Lights", lines,
                         level=level, icon='LIGHT_POINT', operator=self,
                         prefix="LIGHTS",
                         summary=f"Lights - {r['count']} imported, "
                                 f"{r['keyed']} key(s), "
                                 f"{len(r['unmapped'])} parameter(s) unmapped")
        return {"FINISHED"}


_CLASSES = (HT_OT_import_lights,)


_ht_icon_id = None


def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


def draw_session_entry(layout):
    """Entry 7 inside the IMPORT SESSION submenu.

    The submenu numbers ITS entries the same as the Main tab numbers its
    steps, so 7 has to be lights whether or not anyone uses it. A menu that
    runs 1-6 then 8 is a menu that makes you look for the missing one."""
    layout.operator(HT_OT_import_lights.bl_idname,
                    text="6  Import DMX Session Lights",
                    **_icon_id("import_lights", "LIGHT_POINT"))


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
