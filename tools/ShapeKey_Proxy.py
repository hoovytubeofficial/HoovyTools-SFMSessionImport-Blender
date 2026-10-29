"""
ShapeKey_Proxy.py  -  part of HoovyTools       [roadmap #12, #13]
================================================================

A missing target mesh is not the end of the operation.

Import facial animation with no compatible character selected and this
builds a procedural stand-in instead: one mesh, one segment per shape key,
each segment driven by a real shape key of the same name.

    value 0.0    the segment sits at its base height
    value 1.0    the segment is visibly extruded

So the animation becomes watchable without owning the final face. Scrub the
timeline and you can see, immediately:

    whether any flex data was found at all
    which shape keys exist
    which of them are animated
    when they are animated
    what values they reach

WHY REAL SHAPE KEYS AND NOT DRIVERS OR GEOMETRY NODES
=====================================================
Because then the proxy is debugging the same machinery the real character
uses. The keys carry the flex names verbatim, the animation lands on
key_blocks[name].value exactly as it would on a face, and an f-curve that
misbehaves here misbehaves there. A geometry-node bar chart would look the
same and prove nothing.

LOOKS                                                    [roadmap #13]
======================================================================
It should look good, not merely work. So:

    a colour ramp across the set, written as a point colour attribute,
      so neighbouring bars are readable apart at a glance
    a procedural text label under every segment, naming its shape key
    a dark backdrop plate, so bright bars have something to read against
    ACTIVE bars (those with animation) are full height and saturated;
      bars with no animation are shorter and dimmed, so a face with 60
      flexes and 6 animated ones says so instantly
    a PEAK marker on each rail at the highest value that flex reaches,
      so a bar resting at 0 still tells you what it is capable of
    an ACTIVITY ROLL below the chart - one lane per flex, a bar wherever
      it fires. The chart says what value right now; the roll says when,
      across the whole take, and makes the shape of a performance obvious

Materials are EMISSION. A lit BSDF is invisible in an unlit scene, which
a debug proxy usually lands in. `diffuse_color` is set to match so Solid
viewport shading shows the same colours as Material Preview.
"""

import bpy
import colorsys
import math
from pathlib import Path

from bpy.types import Operator

# ──────────────────────────────────────────────────────────────────────────────
# Icon bridge (wired by __init__.register)
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None


def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}

from bpy.props import (StringProperty, FloatProperty, BoolProperty,
                       IntProperty)
from bpy_extras.io_utils import ImportHelper


COLLECTION = "___HoovyTools ShapeKey Proxy___"
COLLECTION_COLOR = "COLOR_05"      #blue

# LAYOUT
# ------
# Everything lives in the XZ plane and is read head-on, like an equaliser
# The first attempt wrapped rows backwards in -Y and it was unreadable: from
# the front the rows receded into perspective and hid each other. Rows now
# stack DOWNWARD in -Z, each one its own little chart, and Y is used only
# for a shallow depth that keeps the bars from looking like flat decals.
BAR_W = 0.8          # X width of one segment
BAR_D = 0.55         # Y depth - just enough to read as a solid
BAR_GAP = 0.3
BAR_BASE_H = 0.14    # height at value 0.0
BAR_FULL_H = 2.2     # height added at value 1.0
LABEL_SIZE = 0.34    # big enough to read at a glance, not just to exist
LABEL_BAND = 2.7     # Z space under each row for its labels, hanging
                     # vertically - sized for a ~15 character flex name
ROW_HEIGHT = BAR_BASE_H + BAR_FULL_H + LABEL_BAND
TRACK_INSET = 0.12   # how much narrower the dim 0..1 track is than the bar
GLYPH_ADVANCE = 0.52 # average character advance, in em, for the default font

# Richer visualization                                       [roadmap #19]
PEAK_H = 0.05        # thickness of the peak-value marker on a track
ACTIVE_EPS = 0.02    # a flex counts as firing above this value
#The roll is sized RELATIVE to the bar chart so the two read as one figure.
#The first attempt used absolute lane heights and a 57-flex file produced a
#roll three times taller than the chart it belonged to
ROLL_H = 0.15        # height of one lane
ROLL_GAP = 0.035
ROLL_MARGIN = 1.6    # gap between the bar chart and the roll
ROLL_RAIL = 0.03     # dim full-width rail per lane, so empty lanes show


# ─────────────────────────────────────────────────────────────────────────────
# Collection
# ─────────────────────────────────────────────────────────────────────────────

def _get_collection():
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        col.color_tag = COLLECTION_COLOR
        bpy.context.scene.collection.children.link(col)
    return col


def _link(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


# ─────────────────────────────────────────────────────────────────────────────
# Colour
# ─────────────────────────────────────────────────────────────────────────────

def ramp_colour(i, n, active=True):
    """
    A readable spread of hues across the set.

    The hue sweep stops at 0.82 rather than wrapping to 1.0, so the last bar
    never comes back round to the same red as the first. Inactive bars keep
    their hue but lose most of their saturation, which reads as "present but
    doing nothing" instead of as a different flex.

    Saturation is high and value is pushed past 1.0 for active bars: these
    are EMISSION shaders on a near-black backdrop, and anything gentler
    renders as the washed-out pastel the first version produced.
    """
    hue = (i / max(1, n - 1)) * 0.82 if n > 1 else 0.55
    if active:
        r, g, b = colorsys.hsv_to_rgb(hue, 0.95, 1.0)
        return (r * 1.55, g * 1.55, b * 1.55, 1.0)
    r, g, b = colorsys.hsv_to_rgb(hue, 0.35, 0.30)
    return (r, g, b, 1.0)


def track_colour(i, n):
    """The dim 0..1 rail a bar climbs, so you can see how far it has to go."""
    hue = (i / max(1, n - 1)) * 0.82 if n > 1 else 0.55
    r, g, b = colorsys.hsv_to_rgb(hue, 0.55, 0.10)
    return (r, g, b, 1.0)


def peak_colour(i, n):
    """The high-water mark. Brighter than the rail, dimmer than the bar."""
    hue = (i / max(1, n - 1)) * 0.82 if n > 1 else 0.55
    r, g, b = colorsys.hsv_to_rgb(hue, 0.65, 0.85)
    return (r, g, b, 1.0)


def channel_stats(ch):
    """(peak, active_spans) for one parsed flex channel.   [roadmap #19]

    A span is a stretch of frames where the value stays above ACTIVE_EPS.
    Spans are what answer the report's "WHEN are they animated" - a peak
    alone says a flex fires, not where.
    """
    vals = [float(v) for v in ch["values"]]
    times = [float(t) for t in ch["times"]]
    peak = max(vals) if vals else 0.0
    spans, open_at = [], None
    for t, v in zip(times, vals):
        if v > ACTIVE_EPS and open_at is None:
            open_at = t
        elif v <= ACTIVE_EPS and open_at is not None:
            spans.append((open_at, t))
            open_at = None
    if open_at is not None and times:
        spans.append((open_at, times[-1]))
    return peak, spans


def _emission_material(name, colour, use_attribute=True):
    """
    Emission, because a lit BSDF is invisible in the unlit scene a debug
    proxy usually lands in.

    use_attribute drives the colour from the per-point ht_proxy_colour
    attribute - right for the bars and the tracks, where every segment
    needs its own hue from one material. Labels want one flat colour, so
    they pass False and get a constant.
    """
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (240, 0)
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.location = (0, 0)
    if use_attribute:
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.location = (-240, 0)
        attr.attribute_name = "ht_proxy_colour"
        nt.links.new(attr.outputs["Color"], emit.inputs["Color"])
    else:
        emit.inputs["Color"].default_value = colour
    emit.inputs["Strength"].default_value = 1.0
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    # solid shading reads diffuse_color, which no node touches
    mat.diffuse_color = colour
    return mat


# ─────────────────────────────────────────────────────────────────────────────
# Geometry
# ─────────────────────────────────────────────────────────────────────────────

def _box(x0, y0, z0, w, d, h):
    """8 verts, 6 quads. Returns (verts, faces) with faces indexed from 0."""
    x1, y1, z1 = x0 + w, y0 + d, z0 + h
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
         (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    return v, f


def cell(i, per_row):
    """Where segment *i* sits. Columns run +X, rows stack -Z."""
    x = (i % per_row) * (BAR_W + BAR_GAP)
    z = -(i // per_row) * ROW_HEIGHT
    return x, z


def build_proxy_mesh(names, active_flags, per_row=12):
    """
    One mesh, one box per shape key, plus a shape key that raises each box.

    The Basis holds every box at BAR_BASE_H. Shape key *i* moves only box
    *i*'s top four verts up by BAR_FULL_H, so key i at value 1.0 extrudes
    exactly one segment and nothing else - which is what makes the proxy
    readable when several flexes fire at once.
    """
    n = len(names)
    verts, faces, colours = [], [], []
    positions = []

    for i, name in enumerate(names):
        x0, z0 = cell(i, per_row)
        v, f = _box(x0, 0.0, z0, BAR_W, BAR_D, BAR_BASE_H)
        base = len(verts)
        verts.extend(v)
        faces.extend(tuple(idx + base for idx in face) for face in f)
        colours.extend([ramp_colour(i, n, active_flags[i])] * 8)
        positions.append((x0, z0, base))

    mesh = bpy.data.meshes.new("HT_ShapeKeyProxy")
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    attr = mesh.color_attributes.new(name="ht_proxy_colour", type='FLOAT_COLOR',
                                     domain='POINT')
    for i, c in enumerate(colours):
        attr.data[i].color = c

    obj = bpy.data.objects.new("HT_ShapeKeyProxy", mesh)

    obj.shape_key_add(name="Basis", from_mix=False)
    for i, name in enumerate(names):
        kb = obj.shape_key_add(name=name, from_mix=False)
        _x0, _z0, base = positions[i]
        # top four verts of box i are base+4 .. base+7.
        for vi in range(base + 4, base + 8):
            co = kb.data[vi].co
            kb.data[vi].co = (co[0], co[1], co[2] + BAR_FULL_H)
        kb.slider_min = 0.0
        kb.slider_max = 1.0
        kb.value = 0.0

    return obj, positions


def build_peaks(names, peaks, per_row=12):
    """
    A bright sliver on each rail at the highest value that flex ever reaches.

    Makes a resting bar informative: you can see a flex peaks at 0.3 and
    never goes further, which is invisible when it happens to be at 0 on
    the frame you are parked on.
    """
    n = len(names)
    verts, faces, colours = [], [], []
    made = 0
    for i in range(n):
        peak = max(0.0, min(1.0, float(peaks[i])))
        if peak <= ACTIVE_EPS:
            continue
        x0, z0 = cell(i, per_row)
        z = z0 + BAR_BASE_H + BAR_FULL_H * peak
        v, f = _box(x0 + TRACK_INSET, BAR_D * 0.5,
                    z, BAR_W - TRACK_INSET * 2, BAR_D * 0.45, PEAK_H)
        base = len(verts)
        verts.extend(v)
        faces.extend(tuple(idx + base for idx in face) for face in f)
        colours.extend([peak_colour(i, n)] * 8)
        made += 1
    if not made:
        return None
    mesh = bpy.data.meshes.new("HT_ProxyPeaks")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    attr = mesh.color_attributes.new(name="ht_proxy_colour",
                                     type='FLOAT_COLOR', domain='POINT')
    for i, c in enumerate(colours):
        attr.data[i].color = c
    return bpy.data.objects.new("HT_ProxyPeaks", mesh)


def build_activity_roll(names, spans_list, per_row=12, frame_lo=0.0,
                        frame_hi=1.0, width=None):
    """
    A piano roll under the chart: one lane per flex, a bar where it fires.

    The bar chart answers "what value, right now". This answers "when, over
    the whole take" - which of sixty flexes carry animation, whether they
    fire together or in sequence, and where the quiet stretches are. Scrub
    the timeline against it and the shape of the performance is obvious.

    Time is normalised into ROLL_W so a 40-frame test and a 4000-frame take
    both fit the same plate.
    """
    n = len(names)
    span = max(1e-6, frame_hi - frame_lo)
    roll_w = width if width else (per_row * (BAR_W + BAR_GAP) - BAR_GAP)
    verts, faces, colours = [], [], []
    lanes = 0
    for i in range(n):
        z = -(i * (ROLL_H + ROLL_GAP))
        # A dim rail for every lane, so a flex that never fires still has a
        # visible row - otherwise the roll silently omits it and you cannot
        # tell "quiet" from "not present"
        v, f = _box(0.0, BAR_D * 0.55, z + (ROLL_H - ROLL_RAIL) * 0.5,
                    roll_w, BAR_D * 0.3, ROLL_RAIL)
        base = len(verts)
        verts.extend(v)
        faces.extend(tuple(idx + base for idx in face) for face in f)
        colours.extend([track_colour(i, n)] * 8)

        for (f0, f1) in spans_list[i]:
            x0 = (f0 - frame_lo) / span * roll_w
            x1 = (f1 - frame_lo) / span * roll_w
            w = max(0.05, x1 - x0)          # a one-frame blip stays visible
            v, f = _box(x0, 0.0, z, w, BAR_D * 0.5, ROLL_H)
            base = len(verts)
            verts.extend(v)
            faces.extend(tuple(idx + base for idx in face) for face in f)
            colours.extend([ramp_colour(i, n, True)] * 8)
            lanes += 1
    if not lanes:
        return None, []      # nothing fires anywhere - skip the roll entirely
    mesh = bpy.data.meshes.new("HT_ProxyRoll")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    attr = mesh.color_attributes.new(name="ht_proxy_colour",
                                     type='FLOAT_COLOR', domain='POINT')
    for i, c in enumerate(colours):
        attr.data[i].color = c
    obj = bpy.data.objects.new("HT_ProxyRoll", mesh)
    # sit the roll below the bar chart, clear of the deepest label band
    rows = math.ceil(n / per_row) if per_row else 1
    obj.location = (0.0, 0.0,
                    -(rows - 1) * ROW_HEIGHT - LABEL_BAND - ROLL_MARGIN)
    return obj, [(-(i * (ROLL_H + ROLL_GAP)), names[i]) for i in range(n)]


def build_tracks(names, per_row=12):
    """
    A dim full-height rail behind every bar.

    Without it a half-raised bar is ambiguous - you cannot tell 0.5 from a
    flex whose range simply is small. The rail is exactly the height of a
    1.0 extrusion, so every bar is read against its own maximum.
    """
    n = len(names)
    verts, faces, colours = [], [], []
    inset = TRACK_INSET
    for i in range(n):
        x0, z0 = cell(i, per_row)
        v, f = _box(x0 + inset, BAR_D * 0.55, z0,
                    BAR_W - inset * 2, BAR_D * 0.35,
                    BAR_BASE_H + BAR_FULL_H)
        base = len(verts)
        verts.extend(v)
        faces.extend(tuple(idx + base for idx in face) for face in f)
        colours.extend([track_colour(i, n)] * 8)

    mesh = bpy.data.meshes.new("HT_ProxyTracks")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    attr = mesh.color_attributes.new(name="ht_proxy_colour", type='FLOAT_COLOR',
                                     domain='POINT')
    for i, c in enumerate(colours):
        attr.data[i].color = c
    return bpy.data.objects.new("HT_ProxyTracks", mesh)


def _make_label(text, x, z, size=LABEL_SIZE):
    """
    The flex name, hanging under its bar.

    Rotated to face -Y so it reads from the front, and turned 90 degrees in
    the plane so a long name runs DOWNWARD in its row's label band instead
    of overlapping the neighbouring column. align_x RIGHT anchors the end of
    the text at the bar, so every label starts at the same line.
    """
    curve = bpy.data.curves.new(f"HT_lbl_{text}", type='FONT')
    curve.body = text
    # fit the name to the label band instead of letting it run into the row
    # below. Blender only knows a text's real length after evaluation, which
    # is too late here, so estimate from the glyph count: the bundled font
    # averages about 0.52 em of advance per character. A long flex name like
    # BreastsNippleOutwards simply gets set smaller rather than colliding.
    est = len(text) * size * GLYPH_ADVANCE
    budget = LABEL_BAND - 0.25
    curve.size = size * (budget / est) if est > budget else size
    # LEFT so the name starts at the bar and runs away from it; CENTER so it
    # sits on the column's centre line
    curve.align_x = 'LEFT'
    curve.align_y = 'CENTER'
    obj = bpy.data.objects.new(f"HT_lbl_{text}", curve)
    # text is authored reading +X with its face along +Z. Two rotations get
    # it reading DOWNWARD (-Z) while still facing the front (-Y):
    #
    # Rx(90)  reading +X, face +Z -> -Y      now vertical, faces front
    # Ry(90)  reading +X -> -Z, face -Y      now runs down the label band
    #
    # Blender composes XYZ euler as Rz @ Ry @ Rx, so (90, 90, 0) is exactly
    # that pair in that order. The first attempt used (90, 0, 90); its Rz
    # turned the text about the WORLD z instead, which swung the reading
    # direction into +Y and rendered every label edge-on and mirrored
    obj.rotation_euler = (math.pi / 2, math.pi / 2, 0.0)
    obj.location = (x, -BAR_D * 0.05, z - 0.14)
    return obj


def _make_backdrop(n, per_row):
    """A single dark quad in the XZ plane, sitting just behind the bars."""
    cols = min(n, per_row)
    rows = math.ceil(n / per_row)
    x0 = -BAR_GAP
    x1 = cols * (BAR_W + BAR_GAP)
    z1 = BAR_BASE_H + BAR_FULL_H + 0.5
    z0 = -(rows - 1) * ROW_HEIGHT - LABEL_BAND - 0.2
    y = BAR_D * 1.05
    mesh = bpy.data.meshes.new("HT_ProxyBackdrop")
    mesh.from_pydata([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)],
                     [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new("HT_ProxyBackdrop", mesh)
    mat = bpy.data.materials.get("HT_ProxyBackdrop")
    if mat is None:
        mat = bpy.data.materials.new("HT_ProxyBackdrop")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (0.018, 0.019, 0.026, 1.0)
    emit.inputs["Strength"].default_value = 1.0
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    mat.diffuse_color = (0.018, 0.019, 0.026, 1.0)
    obj.data.materials.append(mat)
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def build_proxy(channels, frame_rate=30, start=0.0, per_row=16,
                add_labels=True, add_backdrop=True, name_filter="",
                add_peaks=True, add_roll=False):
    """
    Build the proxy and key it from parsed flex channels.

    *channels* is what Import_Shape_Keys._parse_flex_channels returns -
    a list of {flex_name, times, values}. Reusing that parser is the point:
    the proxy debugs the same read path the real importer uses.

    Returns a summary dict.
    """
    if name_filter:
        needle = name_filter.lower()
        channels = [c for c in channels if needle in c["flex_name"].lower()]
    if not channels:
        raise RuntimeError("No flexWeight channels to build a proxy from")

    # A channel is "active" when its values actually move. A flat channel
    # is data that exists but never fires, and the proxy says so visually
    names, active, peaks, spans_list = [], [], [], []
    for ch in channels:
        vals = [float(v) for v in ch["values"]]
        moves = bool(vals) and (max(vals) - min(vals)) > 1e-6
        names.append(str(ch["flex_name"]))
        active.append(moves)
        peak, spans = channel_stats(ch)
        peaks.append(peak)
        spans_list.append(spans)

    col = _get_collection()

    # clear any previous proxy so re-running is idempotent
    for old in list(col.objects):
        data = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        try:
            if data and data.users == 0:
                if isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
                elif isinstance(data, bpy.types.Curve):
                    bpy.data.curves.remove(data)
        except Exception:
            pass

    obj, positions = build_proxy_mesh(names, active, per_row=per_row)
    obj.data.materials.append(_emission_material("HT_ProxyBars",
                                                 (0.8, 0.8, 0.8, 1.0)))
    _link(obj, col)

    if add_backdrop:
        _link(_make_backdrop(len(names), per_row), col)

    tracks = build_tracks(names, per_row=per_row)
    tracks.data.materials.append(_emission_material("HT_ProxyTracks",
                                                    (0.1, 0.1, 0.12, 1.0)))
    tracks.parent = obj
    _link(tracks, col)

    # [roadmap #19] high-water marks on the rails
    if add_peaks:
        peaks_obj = build_peaks(names, peaks, per_row=per_row)
        if peaks_obj is not None:
            peaks_obj.data.materials.append(
                _emission_material("HT_ProxyPeaks", (0.6, 0.6, 0.7, 1.0)))
            peaks_obj.parent = obj
            _link(peaks_obj, col)

    if add_labels:
        lbl_active = _emission_material("HT_ProxyLabelActive",
                                        (0.95, 0.95, 1.0, 1.0),
                                        use_attribute=False)
        lbl_idle = _emission_material("HT_ProxyLabelIdle",
                                      (0.30, 0.30, 0.34, 1.0),
                                      use_attribute=False)
        for i, name in enumerate(names):
            x0, z0, _base = positions[i]
            lbl = _make_label(name, x0 + BAR_W * 0.5, z0)
            lbl.parent = obj
            lbl.data.materials.append(lbl_active if active[i] else lbl_idle)
            lbl.color = ramp_colour(i, len(names), active[i])
            _link(lbl, col)

    # ── Activity roll ─────────────────────────────────────────────────────
    # [roadmap #19] built before the keys so it can use the same frame range
    lo_f = hi_f = None
    for ch in channels:
        for t in ch["times"]:
            f = (float(t) + start) * frame_rate
            lo_f = f if lo_f is None else min(lo_f, f)
            hi_f = f if hi_f is None else max(hi_f, f)
    roll_obj = None
    if add_roll and lo_f is not None:
        frame_spans = [[((float(a) + start) * frame_rate,
                         (float(b) + start) * frame_rate) for a, b in sp]
                       for sp in spans_list]
        roll_obj, _lanes = build_activity_roll(
            names, frame_spans, per_row=per_row,
            frame_lo=lo_f, frame_hi=hi_f)
        if roll_obj is not None:
            roll_obj.data.materials.append(
                _emission_material("HT_ProxyBars", (0.8, 0.8, 0.8, 1.0)))
            roll_obj.parent = obj
            _link(roll_obj, col)

    # ── Animate ───────────────────────────────────────────────────────────
    key_data = obj.data.shape_keys
    action = bpy.data.actions.new("HT_ShapeKeyProxy_action")
    key_data.animation_data_create().action = action

    from ..core.anim_compat import get_channelbag, fc_find_or_new
    bag = get_channelbag(action, key_data)

    lo = hi = None
    keyed = 0
    for i, ch in enumerate(channels):
        name = names[i]
        path = f'key_blocks["{name}"].value'
        fc = fc_find_or_new(bag, path, index=0, group_name="flex")
        for t, v in zip(ch["times"], ch["values"]):
            frame = (float(t) + start) * frame_rate
            kp = fc.keyframe_points.insert(frame, float(v), options={"FAST"})
            kp.interpolation = 'LINEAR'
            lo = frame if lo is None else min(lo, frame)
            hi = frame if hi is None else max(hi, frame)
            keyed += 1
        fc.update()

    return {
        "object": obj,
        "collection": col.name,
        "shape_keys": len(names),
        "animated": sum(1 for a in active if a),
        "keys": keyed,
        "frame_start": lo,
        "frame_end": hi,
        "names": names,
        "peaks": peaks,
        "spans": spans_list,
        "firing": sum(1 for sp in spans_list if sp),
        "roll": roll_obj,
    }


def build_proxy_from_dmx(dmx_path, per_row=16, add_labels=True,
                         add_backdrop=True, name_filter="",
                         add_peaks=True, add_roll=False):
    """Parse a DMX and build the proxy. Reuses the real importer's parser."""
    from ..importers.Import_Shape_Keys import _parse_flex_channels
    frame_rate, start, channels = _parse_flex_channels(Path(dmx_path))
    if not channels:
        raise RuntimeError(
            f"No flexWeight channels found in {Path(dmx_path).name}")
    return build_proxy(channels, frame_rate=frame_rate, start=start,
                       per_row=per_row, add_labels=add_labels,
                       add_backdrop=add_backdrop, name_filter=name_filter,
                       add_peaks=add_peaks, add_roll=add_roll)


# ─────────────────────────────────────────────────────────────────────────────
# Operator
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_shapekey_proxy(Operator, ImportHelper):
    """PICK .dmx (face / flex) - ONE file; the stand-in plays it with no
        character in the scene

        Build a procedural stand-in that plays a DMX's facial animation with no character

One segment per shape key, each driven by a real shape key of the same
name: 0.0 sits at the base, 1.0 extrudes it. Scrub the timeline to see
which flexes exist, which are animated, when, and how far they go.

Bars that carry no animation are drawn short and dimmed, so a file with
sixty flexes and six live ones says so at a glance. Every segment is
labelled with its flex name.

Use it when you have facial data but not the face"""
    bl_idname = "ht.shapekey_proxy"
    bl_label = "Generate Shape Key Proxy"
    # NO "REGISTER" - see the note in Report_UI/the constitution
    # REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    # touching any field in it RE-RUNS this operator. Re-running an
    # import re-reads the DMX and rebuilds every f-curve; nudging Scale
    # there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    # with the value you wanted is the safe way to change your mind
    bl_options = {"UNDO"}

    filename_ext = ".dmx"
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    per_row: IntProperty(  # type: ignore
        name="Per Row",
        description="Segments before the layout wraps to a new row",
        default=16, min=1, max=64,
    )
    add_labels: BoolProperty(  # type: ignore
        name="Name Labels",
        description="Procedural text under each segment naming its shape key",
        default=True,
    )
    add_backdrop: BoolProperty(  # type: ignore
        name="Backdrop",
        description="A dark plate behind the bars so the colours read",
        default=True,
    )
    name_filter: StringProperty(  # type: ignore
        name="Filter",
        description=("Only build segments whose flex name contains this "
                     "text. Leave empty for all of them"),
        default="",
    )
    add_peaks: BoolProperty(  # type: ignore
        name="Peak Markers",
        description=("Mark each rail at the highest value that flex ever "
                     "reaches. Lets a resting bar still tell you it peaks "
                     "at 0.3 and never goes further"),
        default=True,
    )
    add_roll: BoolProperty(  # type: ignore
        name="Activity Roll",
        description=("A piano roll under the chart: one lane per flex, a bar "
                     "wherever it fires. The bars say what value right now; "
                     "this says WHEN, across the whole take. Off by default - "
                     "the bar chart carries the day-to-day job on its own"),
        default=False,
    )
    set_frame_range: BoolProperty(  # type: ignore
        name="Set Frame Range",
        description="Set the scene's start and end frames to the animation",
        default=True,
    )

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "per_row")
        col.prop(self, "name_filter")
        col.separator()
        col.prop(self, "add_labels")
        col.prop(self, "add_backdrop")
        col.prop(self, "add_peaks")
        col.prop(self, "add_roll")
        col.prop(self, "set_frame_range")

    def execute(self, context):
        try:
            r = build_proxy_from_dmx(self.filepath, per_row=self.per_row,
                                     add_labels=self.add_labels,
                                     add_backdrop=self.add_backdrop,
                                     name_filter=self.name_filter,
                                     add_peaks=self.add_peaks,
                                     add_roll=self.add_roll)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if self.set_frame_range and r["frame_start"] is not None:
            context.scene.frame_start = int(math.floor(r["frame_start"]))
            context.scene.frame_end = max(context.scene.frame_start + 1,
                                          int(math.ceil(r["frame_end"])))

        lines = [
            f"File    : {Path(self.filepath).name}",
            f"Shape keys: {r['shape_keys']}",
            f"Animated  : {r['animated']}  (the rest are dimmed)",
            f"Firing    : {r['firing']}  (reach a usable value)",
            f"Keys      : {r['keys']}",
        ]
        if r["frame_start"] is not None:
            lines.append(f"Frames    : {r['frame_start']:.0f} .. "
                         f"{r['frame_end']:.0f}")
        lines.append(f"Collection: {r['collection']}")
        for line in lines:
            print(f"[SK_PROXY]  {line}")

        from ..core import Report_UI
        Report_UI.report(
            context, "shapekey_proxy", "Shape Key Proxy", lines, level='INFO',
            icon='SHAPEKEY_DATA', operator=self, prefix="SK_PROXY",
            summary=f"Shape Key Proxy - {r['shape_keys']} shape key(s), "
                    f"{r['animated']} animated")
        return {"FINISHED"}


def draw_menu_item(layout):
    layout.operator(HT_OT_shapekey_proxy.bl_idname,
                    text="Generate Shape Key Proxy",
                    **_icon_id("shapekey_proxy", 'MESH_CUBE'))


_CLASSES = (HT_OT_shapekey_proxy,)


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
