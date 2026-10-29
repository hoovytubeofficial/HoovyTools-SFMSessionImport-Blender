"""
Developer.py - HoovyTools developer surface
===========================================

Two things live here:

  ROADMAP     The numbered priorities list from the 2026-08-20 work report,
              as data (PRIORITIES). One flat numbering 1..N across three
              tiers so "#9" always means the same item no matter where it
              is quoted - panel, menu, console dump or a conversation.

  DEVELOPER   The workshop half of the addon. Main menu = product, this =
              machinery: every importer callable on its own, the debug
              readouts, and the roadmap itself.

Anything on the roadmap that is not built yet still gets a menu entry, wired
to ht.dev_stub. Clicking it reports which roadmap number would deliver it -
an unbuilt tool that says so beats a menu that hides what is coming.

DRAW-TIME RULES
===============
Same contract as Panel.py: draw() is read-only. Status detection introspects,
never mutates. The dump / debug operators mutate nothing either - they print.

TOOLTIPS ARE THE DOCUMENTATION
==============================
Every roadmap row carries a "?" button whose tooltip is composed by
HT_OT_priority_info.description(). Plain text only - tooltip text cannot be
coloured and emoji render as monochrome boxes.
"""

import bpy
from ..core import paths as _ht_paths
from bpy.props import (IntProperty, EnumProperty, BoolProperty,
                       StringProperty)
from ..core import user_paths
from ..core import marks as _marks
from bpy.types import Operator, Menu
from pathlib import Path
import subprocess
import sys as _sys
import time


# ─────────────────────────────────────────────────────────────────────────────
# Icon bridge (wired by __init__.register)
# ─────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None


def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}



TIER_HIGH    = "HIGH"
TIER_MEDIUM  = "MEDIUM"
TIER_BACKLOG = "BACKLOG"

TIERS = (
    (TIER_HIGH,    "High",     "Blocking work - fix these before building on top",
                   'ERROR'),
    (TIER_MEDIUM,  "Medium",   "Structural work - lands once the high tier is stable",
                   'DOT'),
    (TIER_BACKLOG, "Backlog",  "Experimental and research - must never block a release",
                   'RNDCURVE'),
)

STATUS_ICON = {
    "TODO": 'RADIOBUT_OFF',
    "WIP":  'TIME',
    "DONE": 'CHECKMARK',
}

STATUS_LABEL = {
    "TODO": "not started",
    "WIP":  "in progress",
    "DONE": "done",
}


PRIORITIES = (
    # ── high ──────────────────────────────────────────────────────────────
    dict(
        n=1, tier=TIER_HIGH, status="DONE",
        title="Animation Scale precision",
        where="Common_Props.py:scale_prop, 3 call sites",
        detail=(),
    ),
    dict(
        n=2, tier=TIER_HIGH, status="DONE",
        title="BST-like standalone defaults",
        where="Common_Props.py:PROFILE_ITEMS, Import_DMX_Animation.py",
        detail=(),
    ),
    dict(
        n=3, tier=TIER_HIGH, status="DONE",
        title="Session-aware import preset",
        where="Common_Props.py, Session_Orchestrator.py",
        detail=(),
    ),
    dict(
        n=4, tier=TIER_HIGH, status="DONE",
        title="Project-local source folders",
        where="Session_Paths.py",
        detail=(),
    ),
    dict(
        n=5, tier=TIER_HIGH, status="DONE",
        title="Source FPS vs Blender FPS safety",
        where="FPS_Safety.py",
        detail=(),
    ),
    dict(
        n=6, tier=TIER_HIGH, status="DONE",
        title="DMX Analyzer",
        where="DMX_Analyzer.py",
        detail=(),
    ),
    dict(
        n=7, tier=TIER_HIGH, status="DONE",
        title="Importers callable standalone",
        where="Import_*.py, Session_Orchestrator.py",
        detail=(),
    ),

    # ── medium ────────────────────────────────────────────────────────────
    dict(
        n=8, tier=TIER_MEDIUM, status="DONE",
        title="Session Importer as orchestrator",
        where="Session_Orchestrator.py",
        detail=(),
    ),
    dict(
        n=9, tier=TIER_MEDIUM, status="DONE",
        title="Camera Split boundary frame bug",
        where="Utils_Camera_Fix_Camera.py:_trim_action",
        detail=(),
    ),
    dict(
        n=10, tier=TIER_MEDIUM, status="DONE",
        title="Camera Splitter as standalone tool",
        where="Camera_Tools.py, Utils_Camera_Fix_Camera.py:shot_bounds_of",
        detail=(),
    ),
    dict(
        n=11, tier=TIER_MEDIUM, status="DONE",
        title="Camera pre / post handles",
        where="Camera_Tools.py:add_handles",
        detail=(),
    ),
    dict(
        n=12, tier=TIER_MEDIUM, status="DONE",
        title="Shape Key Proxy",
        where="ShapeKey_Proxy.py",
        detail=(),
    ),
    dict(
        n=13, tier=TIER_MEDIUM, status="DONE",
        title="Shape Key Proxy labels",
        where="ShapeKey_Proxy.py:_make_label, ramp_colour",
        detail=(),
    ),
    dict(
        n=14, tier=TIER_MEDIUM, status="DONE",
        title="Main menu vs Developer menu",
        where="Panel.py:draw_main, Developer.py",
        detail=(),
    ),

    dict(
        n=22, tier=TIER_HIGH, status="DONE",
        title="Bundled datamodel, never SourceIO's",
        where="SST/__init__.py:get_datamodel",
        detail=(),
    ),
    dict(
        n=23, tier=TIER_HIGH, status="DONE",
        title="One axis correction, not two",
        where="Import_DMX_Animation.py:_get_or_create_axis_empty",
        detail=(),
    ),
    dict(
        n=24, tier=TIER_HIGH, status="DONE",
        title="SFM instance numbers break every lookup",
        where="Import_Session.py:_name_candidates + 3 call sites",
        detail=(),
    ),
    dict(
        n=25, tier=TIER_HIGH, status="DONE",
        title="Camera animation out of a session",
        where="Session_Reader.py:extract_camera_set",
        detail=(),
    ),
    dict(
        n=26, tier=TIER_HIGH, status="DONE",
        title="Session shape keys must run the full pipeline",
        where="Session_Orchestrator.py",
        detail=(),
    ),
    dict(
        n=27, tier=TIER_HIGH, status="DONE",
        title="A fallback must never replace the asked-for action",
        where="Session_Orchestrator.py:plan",
        detail=(),
    ),
    dict(
        n=28, tier=TIER_HIGH, status="DONE",
        title="Main / Tools structure and one-click import",
        where="Panel.py, Session_Steps.py, Session_Orchestrator.py",
        detail=(),
    ),
    dict(
        n=15, tier=TIER_BACKLOG, status="DONE",
        title="Light reconstruction from DMX",
        where="Light_Import.py",
        detail=(),
    ),
    dict(
        n=16, tier=TIER_BACKLOG, status="DONE",
        title="MDL sequence research",
        where="Playground.py:parse_mdl, walk_model",
        detail=(),
    ),
    dict(
        n=17, tier=TIER_BACKLOG, status="DONE",
        title="Playground Tools",
        where="Playground.py",
        detail=(),
    ),
    dict(
        n=18, tier=TIER_BACKLOG, status="DONE",
        title="Better camera extrapolation",
        where="Camera_Tools.py:edge_velocity, ease_profile",
        detail=(),
    ),
    dict(
        n=20, tier=TIER_HIGH, status="DONE",
        title="Datamodel loader O(n^2) fix",
        where="SST/datamodel.py:_element_by_id",
        detail=(),
    ),
    dict(
        n=21, tier=TIER_HIGH, status="DONE",
        title="Read animation from the session",
        where="Session_Reader.py",
        detail=(),
    ),
    dict(
        n=19, tier=TIER_BACKLOG, status="DONE",
        title="Richer proxy visualization",
        where="ShapeKey_Proxy.py:build_peaks, build_activity_roll",
        detail=(),
    ),
    dict(
        n=29, tier=TIER_HIGH, status="DONE",
        title="Stepped keyframes in animation import",
        where="Import_DMX_Animation.py:fix_stepped_keys, count_stepped, "
              "resample_integer",
        detail=(),
    ),
    dict(
        n=30, tier=TIER_HIGH, status="DONE",
        title="Bone scale stopped importing",
        where="Import_DMX_Animation.py:_patch_scale_and_root, _rescale_span, "
              "_bone_for_scale",
        detail=(),
    ),
    dict(
        n=31, tier=TIER_HIGH, status="DONE",
        title="One report per operator, with an off switch",
        where="Report_UI.py (new), every module that had a popup",
        detail=(),
    ),
    dict(
        n=32, tier=TIER_HIGH, status="DONE",
        title="Particle TRANSFORM channels were never read",
        where="Session_Particles.py:_apply_transform, describe",
        detail=(),
    ),
    dict(
        n=33, tier=TIER_HIGH, status="DONE",
        title="TWEAK_BRIGHTNESS_GLOBAL for lights",
        where="Light_Import.py:TWEAK_BRIGHTNESS_GLOBAL, energy_for",
        detail=(),
    ),
    dict(
        n=34, tier=TIER_HIGH, status="DONE",
        title="The custom viewport message bar is gone",
        where="Report_UI.py",
        detail=(),
    ),
    dict(
        n=35, tier=TIER_HIGH, status="DONE",
        title="No redo panel on a heavy operator",
        where="bl_options across 16 modules",
        detail=(),
    ),
    dict(
        n=36, tier=TIER_HIGH, status="DONE",
        title="Two particles with the same name, and why they were invisible",
        where="Session_Particles.py:claim_instance_names, apply_visibility",
        detail=(),
    ),
    dict(
        n=37, tier=TIER_MEDIUM, status="DONE",
        title="The _Architecture split",
        where="HoovyToolsDeveloper/_Architecture, constitution/",
        detail=(),
    ),
    dict(
        n=38, tier=TIER_HIGH, status="DONE",
        title="A particle transform is LOCAL to its parent DAG",
        where="Session_Particles.py:dag_parents, parent_matrix, world_position",
        detail=(),
    ),
    dict(
        n=39, tier=TIER_HIGH, status="DONE",
        title="Static props get the one bone SourceIO does not build",
        where="Import_Session.py:build_static_prop_rig, _import_and_rename",
        detail=(),
    ),
    dict(
        n=40, tier=TIER_HIGH, status="DONE",
        title="Never hide a particle's control empties",
        where="Session_Particles.py:apply_visibility, _visibility_spans",
        detail=(),
    ),
    dict(
        n=41, tier=TIER_HIGH, status="DONE",
        title="Stepped shape keys loaded as a 3-frame tween",
        where="Import_Shape_Keys.py:fix_flex_stepped_keys, import_flex_dmx",
        detail=(),
    ),
    dict(
        n=42, tier=TIER_HIGH, status="DONE",
        title="Per-instance naming, done in the particle add-on this time",
        where="HoovyToolsParticleImport/api.py:build_effect(name_prefix=), "
              "op_particle_import.build_system_tree; Session_Particles.py",
        detail=(),
    ),
    dict(
        n=43, tier=TIER_HIGH, status="DONE",
        title="gman's face - and the %-sigil bug that was hurting every model",
        where="Import_Shape_Keys.py:_parse_localvar_expressions, _topo_order, "
              "parse_eyelids, split_flexpairs, bake_hwm_localvars",
        detail=(),
    ),
    dict(
        n=44, tier=TIER_BACKLOG, status="WIP",
        title="Session locks - scanner and dependency order",
        where="Session_Locks.py",
        detail=(),
    ),
    dict(
        n=45, tier=TIER_MEDIUM, status="DONE",
        title="The add-on is packages now, and the underscores mean something",
        where="the whole tree; core/paths.py, MANIFEST.txt, .gitignore",
        detail=(),
    ),
    dict(
        n=46, tier=TIER_MEDIUM, status="DONE",
        title="Tooltips are the documentation, so they say something now",
        where="every HT_OT_* class docstring",
        detail=(),
    ),
    dict(
        n=47, tier=TIER_MEDIUM, status="DONE",
        title="Cleanup - dead code out, startup console from 38 lines to 4",
        where="tools/, SST/, __init__.py, every menu class",
        detail=(),
    ),
    dict(
        n=48, tier=TIER_HIGH, status="DONE",
        title="One camera import path - the session route stops smearing cuts",
        where="Import_DMX_Camera.py, Session_Orchestrator.py, Import_Camera_Animations.py",
        detail=(),
    ),
    dict(
        n=49, tier=TIER_MEDIUM, status="DONE",
        title="Auto-split hoovy cameras: ON by default, pink icons",
        where="ui/Panel.py, ui/Developer.py, make_icons.py",
        detail=(),
    ),
    dict(
        n=50, tier=TIER_MEDIUM, status="DONE",
        title="LOGS box - per-report switches for the _Logs file, magenta",
        where="core/logvars.py, core/Report_UI.py, ui/Developer.py",
        detail=(),
    ),
    dict(
        n=51, tier=TIER_HIGH, status="DONE",
        title="Quaternion flip fix for bone animation - the camera's pass, ported",
        where="Import_DMX_Animation.py:fix_action_quat_flips",
        detail=(),
    ),
    dict(
        n=52, tier=TIER_MEDIUM, status="DONE",
        title="Register Skydome - shadows off, world lit from the dome",
        where="ui/Developer.py:HT_OT_register_skydome",
        detail=(),
    ),
    dict(
        n=53, tier=TIER_MEDIUM, status="DONE",
        title="Every panel section closable, every section its own colour",
        where="ui/Panel.py:SECTIONS + fold_section, ui/Developer.py",
        detail=(),
    ),
    dict(
        n=54, tier=TIER_MEDIUM, status="DONE",
        title="Compact rig report, Cleanup on Tools, VertexlitGeneric Fix",
        where="Session_Steps.py, ui/Panel.py, tools/Utils_Misc.py",
        detail=(),
    ),
    dict(
        n=55, tier=TIER_MEDIUM, status="DONE",
        title="Orange light collection, radius/filter mapped, skydome world rig",
        where="Light_Import.py, ui/Developer.py:_build_skydome_world",
        detail=(),
    ),
    dict(
        n=56, tier=TIER_MEDIUM, status="DONE",
        title="Auto frame rate, auto organize, anims folders off, shot icons",
        where="Session_Paths.py, Session_Orchestrator.py, ui/Panel.py",
        detail=(),
    ),
    dict(
        n=57, tier=TIER_MEDIUM, status="DONE",
        title="Shelves start closed; Anims Folder section; console into Logs",
        where="ui/Panel.py:SECTIONS, ui/Developer.py",
        detail=(),
    ),
    dict(
        n=58, tier=TIER_MEDIUM, status="DONE",
        title="Workspace layouts - Two Screen and Three Monitor, on demand",
        where="tools/Layout_Builder.py, ui/Developer.py, Session_Orchestrator.py",
        detail=(),
    ),
    dict(
        n=59, tier=TIER_MEDIUM, status="DONE",
        title="Lights axis brought home, per-project wiring rows, dome diffuse",
        where="Light_Import.py:_axis_empty, ui/Developer.py",
        detail=(),
    ),
    dict(
        n=60, tier=TIER_MEDIUM, status="DONE",
        title="Skydome world: EEVEE/Cycles parity - the Light Path split removed",
        where="ui/Developer.py:_build_skydome_world",
        detail=(),
    ),
    dict(
        n=61, tier=TIER_MEDIUM, status="DONE",
        title="Layouts rework, render presets, camera jump, Rigs onto Main",
        where="Layout_Builder.py, Session_Orchestrator.py, ui/Panel.py, Session_Steps.py",
        detail=(),
    ),
    dict(
        n=62, tier=TIER_HIGH, status="DONE",
        title="The Gomez session: codepage crash + per-clip time bases",
        where="SST/datamodel.py:get_str, Session_Reader.py:clip_base_shift",
        detail=(),
    ),
    dict(
        n=63, tier=TIER_HIGH, status="DONE",
        title="Gomez round 2: per-shot clip lookup, light parent DAGs",
        where=("Session_Reader.py:shot_clips/_clip_for_set, "
               "Light_Import.py:_chain_matrix, Panel.py:draw_main"),
        detail=(),
    ),
    dict(
        n=64, tier=TIER_HIGH, status="DONE",
        title="Round 3: volumetrics rig, engine parity, UI moves, x4 lights",
        where=("Light_Import.py:_build_volume_group, "
               "Layout_Builder.py:HT_OT_engine_preset, Panel.py, "
               "ui/Developer.py:_build_skydome_world"),
        detail=(),
    ),
    dict(
        n=65, tier=TIER_HIGH, status="DONE",
        title="Light desaturate factor, the Lights Port collection, UI trims",
        where=("Light_Import.py:desaturate/_get_collection, "
               "Session_Steps.py, ui/Panel.py, ui/Developer.py"),
        detail=(),
    ),
    dict(
        n=66, tier=TIER_HIGH, status="DONE",
        title="Volume box home, Density Scale knob, SFM Light Data node",
        where=("Light_Import.py:_light_collections/_sfm_data_group, "
               "Layout_Builder.py:HT_OT_engine_preset"),
        detail=(),
    ),
    dict(
        n=67, tier=TIER_HIGH, status="DONE",
        title="The uberlight reconstruction + density/20",
        where="Light_Import.py:_uberlight_group/apply_attenuation_nodes",
        detail=(),
    ),
    dict(
        n=68, tier=TIER_HIGH, status="DONE",
        title="Brightness x3, the particle cross-shot leak, 17-shot audit",
        where="Session_Particles.py:shot_particle_systems, Light_Import.py",
        detail=(),
    ),
    dict(
        n=69, tier=TIER_HIGH, status="DONE",
        title="The SFM variables PLUGGED IN - links and drivers",
        where=("Light_Import.py:_sfm_data_group/_build_data_node/"
               "drive_from_data"),
        detail=(),
    ),
)


_BY_N = {p["n"]: p for p in PRIORITIES}


def priority(n):
    return _BY_N.get(n)


def tier_items(tier):
    return [p for p in PRIORITIES if p["tier"] == tier]


def counts(tier=None):
    """(done, total) for a tier, or for the whole roadmap when tier is None."""
    items = PRIORITIES if tier is None else tier_items(tier)
    return sum(1 for p in items if p["status"] == "DONE"), len(items)


def roadmap_lines():
    """The whole roadmap as plain text lines - console dump and clipboard."""
    out = ["HoovyTools roadmap - work report 2026-08-20", ""]
    for key, label, _desc, _icon in TIERS:
        done, total = counts(key)
        out.append(f"{label.upper()}  ({done}/{total} done)")
        for p in tier_items(key):
            out.append(f"  {p['n']:>2}. [{STATUS_LABEL[p['status']]:<11}] {p['title']}")
            if p["where"]:
                out.append(f"      -> {p['where']}")
        out.append("")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Operators
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# render presets
# ─────────────────────────────────────────────────────────────────────────────

def _volume_materials():
    """Every material whose output actually drives a VOLUME.

    ASK THE OUTPUT SOCKET, NOT THE NODE NAMES. The first version of this
    walked the top-level nodes looking for "Volume" in a bl_idname, and it
    reported "no volume shader in this scene" for a session whose fog is a
    ShaderNodeGroup called HT Volumetrics with the Principled Volume INSIDE
    the group. The preset then switched volumetrics off, Cycles rendered
    the fog box as real participating media anyway - it is geometry with a
    volume output, not an EEVEE setting - and ten seconds of footage came
    back as a white sheet with ghosts behind it.

    `Material Output -> Volume` being linked is the definitive test: it is
    true through any depth of node group, and it is exactly what makes a
    mesh render as fog.
    """
    out = []
    for mat in bpy.data.materials:
        if not (mat.use_nodes and mat.node_tree):
            continue
        for n in mat.node_tree.nodes:
            if n.bl_idname != "ShaderNodeOutputMaterial":
                continue
            sock = n.inputs.get("Volume")
            if sock is not None and sock.is_linked:
                out.append(mat)
                break
    return out


def _volume_objects(scene):
    """Mesh objects carrying one of those materials."""
    vol_mats = {m.name for m in _volume_materials()}
    if not vol_mats:
        return []
    return [o for o in scene.objects
            if o.type == 'MESH'
            and any(ms.material and ms.material.name in vol_mats
                    for ms in o.material_slots)]


def _scene_has_volume(scene):
    """Does anything in this scene actually use a volume shader?

    VOLUMETRICS ARE NOT FREE - measured on the Gothic scene2 session,
    0.317 s/frame with EEVEE's volumetrics on against 0.276 with them off.
    Worth switching off when nothing uses them, and worth leaving alone
    when something does.
    """
    if _volume_materials():
        return True
    w = getattr(scene, "world", None)
    if w is not None and w.use_nodes and w.node_tree:
        for n in w.node_tree.nodes:
            if n.bl_idname == "ShaderNodeOutputWorld":
                sock = n.inputs.get("Volume")
                if sock is not None and sock.is_linked:
                    return True
    return False


def _cycles_device():
    """Point Cycles at the fastest backend the machine has. Returns a label.

    MEASURED, AND IT IS THE WHOLE BALLGAME FOR CYCLES: this workstation has
    an RTX 4070 SUPER visible under both CUDA and OPTIX, and Blender shipped
    with `compute_device_type = NONE` - meaning every Cycles render would
    have run on the CPU. A preset that sets samples but leaves the device
    alone is tuning the wrong number by two orders of magnitude.
    """
    addon = bpy.context.preferences.addons.get("cycles")
    if addon is None:
        try:
            bpy.ops.preferences.addon_enable(module="cycles")
        except Exception:                                     # noqa: BLE001
            return "CPU"
        addon = bpy.context.preferences.addons.get("cycles")
    if addon is None:
        return "CPU"
    cp = addon.preferences
    # OPTIX before CUDA: same card, RT cores used.
    for want in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            cp.compute_device_type = want
        except Exception:                                     # noqa: BLE001
            continue
        try:
            cp.get_devices()
        except Exception:                                     # noqa: BLE001
            pass
        if any(dv.type == want for dv in cp.devices):
            for dv in cp.devices:
                dv.use = (dv.type == want)
            return want
    return "CPU"


def _set(obj, attr, value):
    """Set it if this Blender has it. EEVEE renames properties between
    releases and a preset must not die on the one it does not recognise."""
    if obj is not None and hasattr(obj, attr):
        try:
            setattr(obj, attr, value)
            return True
        except Exception:                                     # noqa: BLE001
            return False
    return False


def apply_render_preset(scene, preset):
    """Set every knob for one preset. Returns a list of report lines."""
    r = scene.render
    lines = []
    volume = _scene_has_volume(scene)

    # PERSISTENT DATA is always ON. It keeps the evaluated scene between
    # frames, which is what an animation render wants and what a single
    # still does not care about.
    _set(r, "use_persistent_data", True)
    r.resolution_x, r.resolution_y = 1920, 1080

    if preset in ("CHEAP_EEVEE", "EXPENSIVE_EEVEE"):
        for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                r.engine = eng
                break
            except Exception:                                 # noqa: BLE001
                continue
        ee = getattr(scene, "eevee", None)
        cheap = (preset == "CHEAP_EEVEE")
        r.resolution_percentage = 50 if cheap else 100
        _set(ee, "taa_render_samples", 8 if cheap else 64)
        _set(ee, "use_raytracing", not cheap)
        _set(ee, "use_shadows", True)
        _set(ee, "shadow_ray_count", 1 if cheap else 3)
        _set(ee, "shadow_step_count", 3 if cheap else 6)
        _set(ee, "use_volumetric_shadows", volume)
        _set(ee, "volumetric_samples", 4 if not volume else (
            32 if cheap else 128))
        lines.append("Engine        : %s" % r.engine)
        lines.append("Resolution    : %dx%d  (%d%%)"
                     % (r.resolution_x * r.resolution_percentage // 100,
                        r.resolution_y * r.resolution_percentage // 100,
                        r.resolution_percentage))
        lines.append("Samples       : %s" % getattr(ee, "taa_render_samples",
                                                    "?"))
        lines.append("Raytracing    : %s" % getattr(ee, "use_raytracing", "?"))
    else:
        r.engine = "CYCLES"
        dev = _cycles_device()
        cy = getattr(scene, "cycles", None)
        cheap = (preset == "CHEAP_CYCLES")
        _set(cy, "device", "GPU" if dev != "CPU" else "CPU")
        r.resolution_percentage = 50 if cheap else 100
        _set(cy, "use_adaptive_sampling", True)
        _set(cy, "samples", 32 if cheap else 512)
        _set(cy, "adaptive_threshold", 0.10 if cheap else 0.01)
        _set(cy, "use_denoising", True)
        _set(cy, "max_bounces", 4 if cheap else 12)
        _set(cy, "diffuse_bounces", 2 if cheap else 4)
        _set(cy, "glossy_bounces", 2 if cheap else 4)
        _set(cy, "transmission_bounces", 2 if cheap else 8)
        _set(cy, "transparent_max_bounces", 4 if cheap else 12)
        #─── VOLUMETRICS ARE A RENDER SETTING TOO ────────────────────
        #
        #MEASURED on the Gothic fog box (1,440,000 units across, smooth
        #density), one frame, ten settings:
        #
        #step rate 1.0 ... a single foggy frame cost 104 s
        #step rate 8.0 ... the same frame cost 38-68 s
        #
        #A huge box of SMOOTH fog gains nothing from fine steps - the
        #integrator is just sampling the same value repeatedly. Coarse
        #steps are the single biggest volumetric saving here.
        #
        #NOISE DEFEATS IT. A density modulated by a noise texture needs
        #the fine steps back: the same frame went to 205 s with noise at
        #0.5. If the fog is patchy, expect to pay for it
        _set(cy, "volume_bounces", 0 if not volume else (1 if cheap else 2))
        _set(cy, "volume_step_rate", 16.0 if cheap else 8.0)
        _set(cy, "volume_preview_step_rate", 16.0 if cheap else 8.0)
        _set(cy, "volume_max_steps", 128 if cheap else 256)
        _set(cy, "caustics_reflective", not cheap)
        _set(cy, "caustics_refractive", not cheap)
        lines.append("Engine        : CYCLES")
        lines.append("Device        : %s (%s)"
                     % (getattr(cy, "device", "?"), dev))
        lines.append("Resolution    : %dx%d  (%d%%)"
                     % (r.resolution_x * r.resolution_percentage // 100,
                        r.resolution_y * r.resolution_percentage // 100,
                        r.resolution_percentage))
        lines.append("Samples       : %s  (adaptive %.2f)"
                     % (getattr(cy, "samples", "?"),
                        getattr(cy, "adaptive_threshold", 0.0)))
        lines.append("Denoise       : %s" % getattr(cy, "use_denoising", "?"))

    lines.append("Volumetrics   : %s"
                 % ("ON - the scene has volume shaders" if volume
                    else "OFF - no volume shader in this scene"))
    if volume and r.engine == "CYCLES":
        cy2 = getattr(scene, "cycles", None)
        lines.append("Volume steps  : rate %s, max %s, bounces %s"
                     % (getattr(cy2, "volume_step_rate", "?"),
                        getattr(cy2, "volume_max_steps", "?"),
                        getattr(cy2, "volume_bounces", "?")))
    lines.append("Persistent    : %s" % getattr(r, "use_persistent_data", "?"))
    return lines


class HT_OT_render_preset(Operator):
    """Set every render knob at once, for one of four ways to shoot

CHEAP EEVEE - 960x540, 8 samples, no raytracing. The look-see pass:
0.32 s a frame on a 291-object session.
EXPENSIVE EEVEE - 1920x1080, 64 samples, raytracing on. Minutes, not hours.
CHEAP CYCLES - 960x540, 32 adaptive samples, denoised, four bounces. What
real light does, before committing.
EXPENSIVE CYCLES - 1920x1080, 512 samples, twelve bounces, caustics. 49 s
a still and ~90 s an animated frame on an RTX 4070 SUPER. The hero shot.

Volumetrics go on only when a volume shader exists, Cycles is pointed at
the GPU first, and output format and path are never touched"""
    # BELOW the TOOLTIP CAP. Blender truncates an operator description at
    # 1023 characters, mid-word and without a warning, and this one had
    # reached exactly 1023. The measurements live here instead:
    #
    # EXPENSIVE CYCLES - ten secs of footage is ~7 hours. and THE
    # THRESHOLD IS the EXPENSIVE KNOB, not the sample cap - at 1080p:
    # 512 spp / 0.01 threshold   48.9 s
    # 64 spp / 0.01 threshold   27.8 s
    # 128 spp / 0.05 threshold   25.8 s
    # Dropping the cap by 8x saved 43%; loosening the threshold by 5x saved
    # as much again for a quarter of the sample budget. Adaptive sampling
    # stops when the noise floor is met, so the threshold decides the time
    #
    # VOLUMES: volumetrics cost about 13% of a frame and this scene had
    # none - three full renders paid for them anyway - so a preset counts
    # volume shaders first. GPU: Blender shipped this machine with
    # compute_device_type NONE, so Cycles rendered on the CPU whatever the
    # sample count said; the Cycles presets pick OPTIX, then CUDA, then
    # whatever else is there, before touching a single quality knob
    # Resolution, samples, bounces, shadows and persistent data are set;
    # container, codec and file path are yours
    bl_idname = "ht.render_preset"
    bl_label = "Render Preset"
    bl_options = {"REGISTER", "UNDO"}

    preset: EnumProperty(  # type: ignore
        name="Preset",
        items=(
            ("CHEAP_EEVEE", "Cheap EEVEE",
             "960x540, 8 samples, no raytracing - the look-see pass"),
            ("EXPENSIVE_EEVEE", "Expensive EEVEE",
             "1920x1080, 64 samples, raytracing on"),
            ("CHEAP_CYCLES", "Cheap Cycles",
             "960x540, 32 adaptive samples, denoised, 4 bounces"),
            ("EXPENSIVE_CYCLES", "Expensive Cycles",
             "1920x1080, 512 adaptive samples, 12 bounces, caustics"),
        ),
        default="CHEAP_EEVEE",
    )

    def execute(self, context):
        label = self.preset.replace("_", " ").title()
        lines = apply_render_preset(context.scene, self.preset)
        for ln in lines:
            print("[PRESET]  %s" % ln)
        from ..core import Report_UI
        Report_UI.report(
            context, "render_preset", "Render Preset - %s" % label, lines,
            level='INFO', operator=self, prefix="PRESET",
            summary="Render preset applied - %s" % label)
        return {"FINISHED"}


class HT_OT_priority_info(Operator):
    """Show the full text of this roadmap item in a popup and the console

Every item carries what was done, why, what it cost to find out, and the
numbers it was verified against. The one-line title is only the label"""
    bl_idname = "ht.priority_info"
    bl_label = "Priority Info"
    bl_options = {"INTERNAL"}

    index: IntProperty(default=0)  # type: ignore

    @classmethod
    def description(cls, context, properties):
        p = priority(properties.index)
        if p is None:
            return "Unknown roadmap item"
        head = f"#{p['n']}  {p['title']}   [{p['tier']} - {STATUS_LABEL[p['status']]}]"
        body = "\n".join(p["detail"])
        tail = f"\n\nCode: {p['where']}" if p["where"] else "\n\nNothing built yet."
        return f"{head}\n\n{body}{tail}"

    def execute(self, context):
        p = priority(self.index)
        if p is not None:
            print(f"\n[HT_ROADMAP]  #{p['n']}  {p['title']}  "
                  f"[{p['tier']} - {STATUS_LABEL[p['status']]}]")
            for line in p["detail"]:
                print(f"[HT_ROADMAP]    {line}")
            if p["where"]:
                print(f"[HT_ROADMAP]    Code: {p['where']}")
        return {"FINISHED"}


class HT_OT_dev_stub(Operator):
    """Not built yet - this button is a placeholder

It marks a roadmap item that has a place in the UI but no implementation.
Pressing it does nothing except say so"""
    bl_idname = "ht.dev_stub"
    bl_label = "Not Implemented"

    index: IntProperty(default=0)  # type: ignore

    @classmethod
    def description(cls, context, properties):
        p = priority(properties.index)
        if p is None:
            return "Not implemented yet"
        return (f"NOT BUILT YET\n\n"
                f"Delivered by roadmap #{p['n']}  {p['title']}\n"
                f"Tier: {p['tier']}   Status: {STATUS_LABEL[p['status']]}\n\n"
                + "\n".join(p["detail"]))

    def execute(self, context):
        p = priority(self.index)
        if p is None:
            self.report({"INFO"}, "Not implemented yet.")
        else:
            self.report({"INFO"},
                        f"Not built yet - roadmap #{p['n']}: {p['title']} "
                        f"({p['tier']}, {STATUS_LABEL[p['status']]})")
        return {"FINISHED"}


class HT_OT_dev_console_success(Operator):
    """Print a SUCCESS block to the system console and report INFO

Use it to prove the console is actually reachable and scrolling before
chasing a bug through it - if this line does not appear, the problem is the
console, not the addon.

Window > Toggle System Console opens it on Windows"""
    bl_idname = "ht.dev_console_success"
    bl_label = "Print Success Message"

    def execute(self, context):
        bar = "=" * 58
        print()
        print(bar)
        print("[HOOVYTOOLS]  CONSOLE TEST - SUCCESS")
        print(f"[HOOVYTOOLS]  Blender {bpy.app.version_string}")
        print(f"[HOOVYTOOLS]  addon registered, print() reaches this console")
        print(f"[HOOVYTOOLS]  blend: {bpy.data.filepath or '(unsaved)'}")
        print(bar)
        print()
        self.report({"INFO"},
                    "HoovyTools console test: SUCCESS - check the system "
                    "console")
        return {"FINISHED"}


class HT_OT_dev_console_error(Operator):
    """Print an ERROR block to the system console and report ERROR

The counterpart to the success test: shows what a failure looks like in
both the console and the status bar, so you can tell a real error apart
from a missing message.

Nothing is changed in the scene"""
    bl_idname = "ht.dev_console_error"
    bl_label = "Print Error Message"

    def execute(self, context):
        bar = "!" * 58
        print()
        print(bar)
        print("[HOOVYTOOLS]  CONSOLE TEST - ERROR")
        print("[HOOVYTOOLS]  This is a DELIBERATE test message.")
        print("[HOOVYTOOLS]  Nothing has gone wrong and nothing was changed.")
        print("[HOOVYTOOLS]  A real failure prints a Python stack here,")
        print("[HOOVYTOOLS]  naming the file and line that raised.")
        # deliberately does NOT print a real stack dump, and deliberately
        # avoids the word a log search looks for. A realistic-looking
        # failure sitting in the log is the kind of thing that costs
        # someone an hour six months later, and it breaks any tooling
        # that greps logs for genuine errors
        print(bar)
        print()
        self.report({"ERROR"},
                    "HoovyTools console test: ERROR (deliberate - nothing "
                    "is broken)")
        return {"FINISHED"}


class HT_OT_dev_dump_roadmap(Operator):
    """Print the whole numbered roadmap to the system console

Every item with its tier, status, what was done and why. Numbers are
stable references - a shipped item is never renumbered - so #29 means the
same thing in a work report a month later.

Useful for pasting into a report, or for reading the reasoning behind a
decision without hunting through the source"""
    bl_idname = "ht.dev_dump_roadmap"
    bl_label = "Dump Roadmap"

    def execute(self, context):
        lines = roadmap_lines()
        text = "\n".join(lines)
        print()
        for line in lines:
            print(f"[HT_ROADMAP]  {line}")
        try:
            context.window_manager.clipboard = text
            self.report({"INFO"}, f"Roadmap printed and copied ({len(PRIORITIES)} items)")
        except Exception as exc:
            self.report({"WARNING"}, f"Printed, clipboard failed: {exc}")
        return {"FINISHED"}


class HT_OT_dev_debug_paths(Operator):
    """Print every path HoovyTools resolves right now to the system console

The usermod path, the reference-rig folder, the QC folder, the connected
session and animations folder, and whether each one exists.

First thing to check when something reports "not found" - it separates
"the file is missing" from "we are looking in the wrong place", which
otherwise read identically"""
    bl_idname = "ht.dev_debug_paths"
    bl_label = "Debug Paths"

    def execute(self, context):
        from pathlib import Path
        lines = []

        prefs = None
        try:
            prefs = context.preferences.addons[__package__].preferences
        except Exception as exc:
            lines.append(f"preferences unavailable: {exc}")

        if prefs is not None:
            for attr in ("sfm_usermod_path", "faulty_rigs_sfm_path"):
                raw = getattr(prefs, attr, "")
                ok = Path(bpy.path.abspath(raw)).exists() if raw else False
                lines.append(f"{attr:<22} {'OK ' if ok else 'MISSING'}  {raw}")

        try:
            from ..session import Import_Session
            base = Import_Session.get_gameinfo_base()
            lines.append(f"{'gameinfo base':<22} "
                         f"{'OK ' if base.exists() else 'MISSING'}  {base}")
        except Exception as exc:
            lines.append(f"gameinfo base failed: {exc}")

        blend = bpy.data.filepath or "(unsaved)"
        lines.append(f"{'current .blend':<22}         {blend}")
        lines.append(f"{'scene fps':<22}         "
                     f"{context.scene.render.fps / context.scene.render.fps_base:g}")

        print()
        for line in lines:
            print(f"[HT_PATHS]  {line}")
        self.report({"INFO"}, "Paths printed to the system console")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# The wiring readout
# ─────────────────────────────────────────────────────────────────────────────
#
# WHAT IT IS FOR. Nine things have to be in place before a session imports,
# and when one is missing the error you get names the SYMPTOM: "model failed",
# "no reference file for this rig", "baker skipped". None of those say
# "SourceIO isn't installed" or "your usermod path has a typo in it", which
# is what was actually wrong. This is the one screen that says which
#
# DRAW() MUST NOT TOUCH THE DISK. It runs on every redraw - every mouse move
# over the panel - and `mod_dirs()` alone stats every child of `game/`. So the
# results are cached, and the cache key is built ONLY from things that are
# free to read: the preference strings, the toggle, how many icons loaded, and
# the connected session's path. Change any of those and the next draw
# recomputes; change something on disk behind the add-on's back and the
# Re-check button is there for exactly that.
#
# THREE STATES, NOT TWO. A red X means the pipeline is broken and an import
# will fail. Orange means a FEATURE is unavailable but everything else still
# runs - no QC means the face bake is skipped and the flex curves still
# import, which is not the same kind of problem and must not look like one.

_WIRING_CACHE = None
_WIRING_KEY = None

OK, WARN, BAD = 'OK', 'WARN', 'BAD'

_STATUS_ICON = {
    OK:   ("status_ok",   'CHECKMARK'),
    WARN: ("status_warn", 'ERROR'),
    BAD:  ("status_bad",  'X'),
}


def _wiring_key(context):
    """Everything that could invalidate the readout, all free to read."""
    try:
        prefs = _ht_paths.addon_prefs()
        pref_bits = (prefs.sfm_usermod_path, prefs.qc_face_data_path,
                     prefs.faulty_rigs_path, prefs.faulty_rigs_sfm_path,
                     prefs.scan_game_mounts)
    except Exception:
        pref_bits = ("<no prefs>",)
    try:
        from .. import _pcoll, _ICON_KEYS
        icon_bits = (len(_pcoll) if _pcoll is not None else -1, len(_ICON_KEYS))
    except Exception:
        icon_bits = (-1, -1)
    try:
        from ..session import Session_Paths
        sess = Session_Paths.session_file(context.scene)
        sess_bit = str(sess) if sess else ""
    except Exception:
        sess_bit = "?"
    try:
        from ..session import Session_Paths
        anim = Session_Paths.animations_dir(context.scene)
        anim_bit = str(anim) if anim else ""
    except Exception:
        anim_bit = "?"
    # The JSON store, by mtime and size - free to read, and the only thing
    # that changes when a user adds a folder from the wiring section
    try:
        store_bit = user_paths.fingerprint()
    except Exception:
        store_bit = (0, 0)
    return pref_bits + icon_bits + (sess_bit, anim_bit) + store_bit


def _module_dir(name):
    """Where an installed add-on lives on disk, or None.

    `addon_utils.check` answers whether a module is enabled and nothing about
    where it is - and "where is SourceIO actually installed" is the next
    question every time the answer is "the wrong one is enabled"."""
    import sys
    from pathlib import Path as _P
    mod = sys.modules.get(name)
    f = getattr(mod, "__file__", None) if mod else None
    if not f:
        try:
            import importlib.util
            spec = importlib.util.find_spec(name)
            f = getattr(spec, "origin", None) if spec else None
        except Exception:
            f = None
    if not f:
        return None
    d = _P(f).parent
    return d if d.is_dir() else None


def _check_usermod():
    """All three slots at once - the row is about whether ANY install works."""
    from ..session import Import_Session
    bases = Import_Session.usermod_bases()
    if not bases:
        # Say which way each configured slot failed, not just that none
        # worked. "D: not connected" and "you typed it wrong" want different
        # actions and the row is the only place that difference is cheap
        why = []
        for i, raw in enumerate(_configured_usermods()):
            st, short, _long = diagnose_path(raw, want_gameinfo=True)
            if st is not None:
                why.append(f"slot {i + 1}: {short}")
        return BAD, "none connected", (
            "  |  ".join(why) if why
            else "No usermod folder is set at all. Add one below"), None
    bad = [b for b in bases if not (b / "gameinfo.txt").is_file()]
    detail = "  |  ".join(str(b) for b in bases)

    #HOW MANY OF HOW MANY. "usermod" told you the folder's name, which you
    #knew; what you want when one of two drives is unplugged is that one of
    #two is unplugged. Counted against the slots that are SET, not against
    #the three that exist - two empty slots are not two failures
    configured = [r for r in _configured_usermods() if r.strip()]
    total = max(len(configured), len(bases))

    if len(bad) == len(bases):
        return WARN, f"{len(bases)}, no gameinfo.txt", detail, bases[0]
    if bad:
        return (WARN, f"{len(bases)} set, {len(bad)} without gameinfo.txt",
                detail, bases[0])
    if total > len(bases):
        return (WARN, f"{len(bases)} of {total} connected",
                f"{total - len(bases)} configured install(s) are not "
                f"reachable - see Where is SFM.  |  {detail}", bases[0])
    return (OK, "connected" if total == 1 else f"all {total} connected",
            detail, bases[0])


def _check_mounts():
    from ..core import paths
    from ..session import Import_Session
    mounts = []
    for base in Import_Session.usermod_bases():
        for m in paths.mod_dirs(base):
            if m not in mounts:
                mounts.append(m)
    if not mounts:
        return (BAD, "none found",
                "Nothing under game/ looks like a mod folder", None)
    has_ws = any(m.name.lower() == "workshop" for m in mounts)
    names = [m.name for m in mounts]
    #the game/ folder itself, not one mount - the row is about all of them.
    #The NAMES come back as extras so the row can print which ones got
    #connected without scanning the disk again from inside draw()
    return (OK, f"{len(mounts)} found",
            ", ".join(names)
            + ("" if has_ws else "  (no 'workshop' folder - Workshop content "
                                 "will not resolve)"),
            mounts[0].parent, {"names": names})


def _check_dmxconvert():
    from ..session import Import_Session
    try:
        exe = Import_Session._find_dmxconvert()
    except Exception:
        return BAD, "not found", ("Valve's dmxconvert.exe, expected in "
                                  "SourceFilmmaker/game/bin. Sessions cannot "
                                  "be read without it"), None
    return OK, exe.name, str(exe), exe.parent


def _check_sourceio():
    import addon_utils
    from ..session import Import_Session
    for name in Import_Session._SOURCEIO_MODULES:
        loaded, enabled = addon_utils.check(name)
        if enabled:
            return OK, name, "enabled", _module_dir(name)
    installed = {m.__name__ for m in addon_utils.modules()}
    for name in Import_Session._SOURCEIO_MODULES:
        if name in installed:
            return WARN, "installed, off", (
                f"Found '{name}' but it is not enabled. The session import "
                f"enables it itself, so this usually turns green on first "
                f"run"), _module_dir(name)
    return WARN, "not installed", (
        "Only the map step needs SourceIO - maps import through it, so without it the map is left out. Models "
        "import with HoovyTools' own importer. Tried: " + ", ".join(Import_Session._SOURCEIO_MODULES)), None


def _check_smd():
    from ..core import paths
    sst = paths.addon_root() / "SST"
    if hasattr(bpy.ops.import_scene, "smd"):
        return OK, "import_scene.smd", "bundled SST, or Blender Source Tools", sst
    return BAD, "missing", ("bpy.ops.import_scene.smd is not registered - "
                            "the bundled SST/ folder is incomplete"), sst


def _check_folder(label, folders, pattern, empty_level, empty_note):
    total = 0
    where = []
    for f in folders:
        n = len(list(f.glob(pattern)))
        total += n
        # PARENT/NAME, because the add-on's `_Faulty Rigs` and the SFM tree's
        # `_Faulty Rigs` have the same basename by design - and a detail line
        # reading "_Faulty Rigs: 15 | _Faulty Rigs: 13" names neither of them
        where.append(f"{f.parent.name}/{f.name}: {n}")
    if not folders:
        return empty_level, "no folder", empty_note, None
    if not total:
        return empty_level, f"0 {pattern}", empty_note, folders[0]
    return OK, f"{total} {pattern}", "  |  ".join(where), folders[0]


def _check_faulty_rigs():
    from ..session import Import_Session
    return _check_folder(
        "Faulty Rigs", Import_Session._faulty_rigs_search_folders(), "*.dmx",
        WARN, "The rig fixer reports 'no reference file' and rest poses are "
              "left as imported. Everything else still works")


def _check_qc():
    from ..importers import Import_Shape_Keys
    return _check_folder(
        "QC Face Data", Import_Shape_Keys._qc_search_folders(), "*.qc",
        WARN, "The HWM face bake is skipped. Flex curves still import, so "
              "faces move - just not the combination controls")


def _check_icons():
    from .. import _pcoll, _ICON_KEYS
    have = len(_pcoll) if _pcoll is not None else 0
    want = len(_ICON_KEYS)
    from ..core import paths
    where = paths.icons()
    if have >= want:
        return OK, f"{have}/{want}", str(where), where
    if not have:
        return WARN, "0 loaded", ("No images folder - stock Blender icons "
                                  "are used and everything works, "
                                  "plainer"), None
    return (WARN, f"{have}/{want}", "Some icon files are missing from images",
            where)


def _check_particles():
    """Is the .PCF importer MOUNTED - not merely present on disk.

    THREE DIFFERENT ANSWERS THAT ALL LOOK THE SAME FROM OUTSIDE. The add-on can
    be absent, present but disabled, or enabled but broken in a way that only
    shows when its `api` module is imported. Particles are built by calling
    `HoovyToolsParticleImport.api.build_effect()`, so `api` importing is the
    only test that means anything - the package importing proves nothing, and
    that is what this used to check.
    """
    import addon_utils
    from ..core import siblings
    # Every name it has shipped under, newest first - see core/siblings
    NAMES = siblings.names("particles")

    found = None
    installed = {m.__name__ for m in addon_utils.modules()}
    for name in NAMES:
        _loaded, enabled = addon_utils.check(name)
        if enabled:
            found = (name, True)
            break
        if name in installed and found is None:
            found = (name, False)
    if found is None:
        try:
            # A hyphenated module name cannot be reached with `import X`,
            # so this goes through importlib like everything else now
            _name, _pi = siblings.find("particles")
            if _pi is None:
                raise ImportError("no particle add-on under any known name")
            found = (_name, True)
        except Exception:
            return WARN, "not installed", (
                "Step 7 (Import Particles) and Particles (Session File) do "
                "nothing without the .PCF importer add-on. Every other step "
                "works - this one cannot, because nothing here reads a "
                ".pcf"), None

    name, enabled = found
    if not enabled:
        return WARN, "installed, off", (
            f"'{name}' is installed but not enabled. Turn it on in "
            f"Preferences > Add-ons; nothing here can enable it for "
            f"you"), _module_dir(name)

    # the version, and whether the entry point actually imports
    ver = ""
    try:
        mod = __import__(name)
        v = getattr(mod, "bl_info", {}).get("version")
        if v:
            ver = "v" + ".".join(str(x) for x in v)
    except Exception:
        pass
    try:
        __import__(f"{name}.api")
    except Exception as exc:                                # noqa: BLE001
        return BAD, f"{ver or 'mounted'}, api broken".strip(), (
            f"The add-on is enabled but `{name}.api` will not import "
            f"({exc}). That is the module the particle build "
            f"calls"), _module_dir(name)
    return (OK, f"mounted {ver}".strip(), f"{name} - api reachable",
            _module_dir(name))


def _check_session(context):
    from ..session import Session_Paths
    sess = Session_Paths.session_file(context.scene)
    if sess is None:
        return WARN, "not loaded", "Load one on the Main tab", None
    if not sess.exists():
        return BAD, "file is gone", str(sess), sess.parent
    return OK, sess.name, str(sess), sess.parent


def _check_anims(context):
    """The connected animations folder - a PER-PROJECT choice, like the
    session. RED only when a folder that WAS connected has vanished
    from disk, which really is broken."""
    from ..session import Session_Paths
    anim = Session_Paths.animations_dir(context.scene)
    if anim is None:
        sess = Session_Paths.session_file(context.scene)
        return OK, ("from the session" if sess is not None else "optional"), (
            "No animations folder is needed - a session import extracts what "
            "it needs by itself. Connect one only to reuse a folder of "
            "exported animations"), None
    if not anim.is_dir():
        return BAD, "folder is gone", str(anim), anim.parent
    try:
        n = len(list(anim.glob("*.dmx")))
    except Exception:                                         # noqa: BLE001
        n = -1
    return OK, f"{anim.name} ({n} dmx)", str(anim), anim


# order is the order things fail in. Everything above the line has to work
# before a session imports at all; everything below it costs you one feature.
_CHECKS = (
    #key            label              check              fixable as
    ("usermod",    "SFM usermod",    _check_usermod,    ("slot", "usermod")),
    ("mods",       "Mod folders",    _check_mounts,     ("slot", "usermod")),
    ("dmxconvert", "dmxconvert.exe", _check_dmxconvert, ("slot", "dmxconvert")),
    ("sourceio",   "SourceIO",       _check_sourceio,   ("enable", "sourceio")),
    ("rigs",       "Faulty Rigs",    _check_faulty_rigs, ("slot", "faulty_rigs")),
    ("qc",         "QC Face Data",   _check_qc,         ("slot", "qc_face_data")),
    ("particles",  ".PCF importer",  _check_particles,  ("enable", "particles")),
)

# CHECKED, REPORTED, NOT DRAWN. These two are facts about the add-on's own
# files - the bundled SST folder and the images folder - and there's nothing
# a user can do about either from a panel. They earned a row when the readout
# was a completeness list; they cost one when it became a repair screen, so
# they live in Print Addon Behavior where a completeness list belongs
_REPORT_ONLY = (
    ("smd",    "SMD importer", _check_smd),
    ("icons",  "Panel icons",  _check_icons),
)


def _row(key, label, status, value, detail, path, fix):
    return {"key": key, "label": label, "status": status, "value": value,
            "detail": detail, "path": path, "fix": fix}


def _run_check(key, label, fn, fix, context=None):
    extras = {}
    try:
        got = fn(context) if key in ("session", "anims") else fn()
        # A check may return a fifth item: whatever else its row wants to
        # show. Only `mods` uses it today - for the list of mount NAMES,
        # which the row prints and which would otherwise mean scanning the
        # disk a second time from inside draw().
        if len(got) == 5:
            status, value, detail, path, extras = got
        else:
            status, value, detail, path = got
    except Exception as exc:                                  # noqa: BLE001
        # A check that raises is a red row, never a traceback in draw(). This
        # runs inside the panel; an exception here takes the whole sidebar
        # with it and the user loses the tab that would have told them what
        # was wrong.
        status, value, detail, path = BAD, "check failed", str(exc), None
    # A row that's FINE offers no fix. The button is the answer to a
    # problem, so it appears with the problem and not before it - except an
    # OPTIONAL folder nobody connected (1.18.0, Animations): fine as it's,
    # and LOAD is still the one thing you could do with that row
    keep = status != OK or (key in ("anims", "session") and not path)
    row = _row(key, label, status, value, detail, path, fix if keep else None)
    row.update(extras or {})
    return row


def wiring(context, force=False, include_hidden=False):
    """The readout, cached against a key that is free to read.

    Rows are dicts, not tuples. They grew a path and then a fix and then a
    key, and a five-then-six-field tuple unpacked in four places is a rename
    away from silently shifting everything along by one.
    """
    global _WIRING_CACHE, _WIRING_KEY
    ckey = _wiring_key(context)
    if not force and _WIRING_CACHE is not None and _WIRING_KEY == ckey:
        rows = _WIRING_CACHE
    else:
        rows = [_run_check(k, lbl, fn, fix) for k, lbl, fn, fix in _CHECKS]
        rows.append(_run_check("session", "DMX Session", _check_session,
                               ("connect", None), context))
        rows.append(_run_check("anims", "Animations", _check_anims,
                               ("connect_anims", None), context))
        _WIRING_CACHE, _WIRING_KEY = rows, ckey

    if include_hidden:
        rows = list(rows) + [_run_check(k, lbl, fn, None)
                             for k, lbl, fn in _REPORT_ONLY]
    return rows


def wiring_summary(rows):
    """(ok, warn, bad) counts."""
    return (sum(1 for r in rows if r["status"] == OK),
            sum(1 for r in rows if r["status"] == WARN),
            sum(1 for r in rows if r["status"] == BAD))


class HT_OT_dev_recheck_wiring(Operator):
    """Re-run the wiring checks against the disk right now

The readout is cached, because draw() runs on every mouse move over the
panel and scanning the SFM folder that often would make the sidebar
stutter. The cache clears itself whenever a preference path, the mod-folder
toggle, the folder store or the connected session changes - so the only
time you need this button is when something changed OUTSIDE Blender: you
installed SourceIO, created the folder it was complaining about, or fixed a
path in Explorer"""
    bl_idname = "ht.dev_recheck_wiring"
    bl_label = "Re-check Wiring"

    def execute(self, context):
        rows = wiring(context, force=True, include_hidden=True)
        ok, warn, bad = wiring_summary(rows)
        print()
        print(f"[HT_WIRING]  {_marks.legend()}")
        for r in rows:
            print(f"[HT_WIRING]  {_marks.mark(r['status'])}{r['label']:<16} "
                  f"{r['value']:<22} {r['detail']}")
        level = "INFO" if not bad else "WARNING"
        self.report({level}, f"Wiring: {ok} ok, {warn} warning(s), {bad} broken")
        return {"FINISHED"}


class HT_OT_enable_addon(Operator):
    """Turn this add-on on, from here

The readout can see that SourceIO or the .PCF importer is installed and
switched off, and switching it on is one call - so it is one button rather
than a sentence telling you to go and find Preferences > Add-ons.

Only ever ENABLES something already installed. It cannot download or
install anything, and if the add-on is not there it says so"""
    bl_idname = "ht.enable_addon"
    bl_label = "Enable Add-on"

    which: EnumProperty(  # type: ignore
        name="Add-on",
        items=[("sourceio", "SourceIO", "The model importer"),
               ("particles", ".PCF importer", "Source Particle Import")],
        default="sourceio",
        options={'HIDDEN'},
    )

    def execute(self, context):
        import addon_utils
        from ..core import siblings
        names = {"sourceio": ("SourceIO", "SourceIO-master"),
                 "particles": siblings.names("particles")}[self.which]

        present = {m.__name__ for m in addon_utils.modules()}
        installed = [n for n in names if n in present]
        if not installed:
            self.report({"ERROR"},
                        f"Not installed - tried {', '.join(names)}. "
                        f"Install it first; this only switches one on")
            return {"CANCELLED"}

        last = None
        for n in installed:
            try:
                if addon_utils.enable(n, default_set=True) is not None:
                    wiring(context, force=True)
                    self.report({"INFO"}, f"'{n}' enabled")
                    return {"FINISHED"}
            except Exception as exc:                          # noqa: BLE001
                last = exc
        self.report({"ERROR"}, f"Could not enable {installed[0]}: {last}")
        return {"CANCELLED"}


def _draw_fix(row_layout, row):
    """The ONE button that repairs this row, or nothing.

    THIS IS WHY THE READOUT EXISTS. Ten rows telling you what is wrong leave
    you to work out which of ten different actions fixes each one - and the
    action is never the same twice: browse for a folder, enable an add-on,
    connect a session. The row already knows which; it may as well offer it.
    """
    fix = row.get("fix")
    if not fix:
        return
    kind, arg = fix
    if kind == "slot":
        # slot 1, always. Slot 0 is the folder WE assign, and a broken row is
        # the moment to add yours rather than to overwrite the default you
        # may still want back.
        op = row_layout.operator("ht.set_search_folder", text="Fix",
                                 icon='FILEBROWSER')
        op.slot_key, op.slot_index = arg, 1
    elif kind == "enable":
        row_layout.operator("ht.enable_addon", text="Enable",
                            icon='CHECKBOX_HLT').which = arg
    elif kind == "connect":
        row_layout.operator("ht.connect_session", text="Load",
                            icon='FILE_FOLDER')
    elif kind == "connect_anims":
        row_layout.operator("ht.connect_animations", text="Load",
                            icon='FILE_FOLDER')


def _draw_usermod_slots(col, context):
    """The three usermod slots, at the top of the wiring box.

    FIRST, BECAUSE THIS IS THE ONE THAT GOES WRONG. Everything else can be
    perfect and nothing will import if the folder it is pointed at is not
    there - and the usual way it is not there is a second drive that is
    unplugged. It is not a separate section, though: it IS the first wiring
    row, expanded, and two boxes both called "is it connected" read as one
    thing broken in half.
    """
    raws = _configured_usermods()
    states = [diagnose_path(r, want_gameinfo=True) for r in raws]

    #1.18.0: only the SLOTS that ARE SET. Two "SFM 2 / SFM 3 - not set -
    #LOAD" rows on every install were two buttons for a question nobody
    #asked; adding a second install is what Where It Looks (folded in below)
    #is for. Nothing set at all: one row, one LOAD.
    if not any(r for r in raws):
        line = col.row(align=True)
        line.label(text="", icon='DOT')
        line.label(text="SFM usermod")
        tail = line.row(align=True)
        tail.alignment = 'RIGHT'
        tail.enabled = False
        tail.label(text="not set")
        draw_row_button(line, False, "", slot_key="usermod", slot_index=0)
        return states

    first = True
    for i, (raw, (st, short, _long)) in enumerate(zip(raws, states)):
        if not raw:
            continue
        if not first:
            _line(col)
        first = False
        line = col.row(align=True)
        if st in _STATUS_ICON:
            line.label(text="", **_icon_id(*_STATUS_ICON[st]))
        else:
            line.label(text="", icon='DOT')

        name = line.row()
        name.enabled = bool(raw)
        name.alert = (st == BAD)
        name.label(text=_shorten(raw, 32) if raw else f"SFM {i + 1}")

        tail = line.row(align=True)
        tail.alignment = 'RIGHT'
        tail.enabled = st == OK
        tail.label(text=short)

        draw_row_button(line, st == OK, raw, slot_key="usermod", slot_index=i)

    return states


def _wrap(text, width):
    """Break a sentence for a panel, on spaces, without a dependency."""
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def _line(col):
    """A thin rule between two wiring rows."""
    try:
        col.separator(factor=0.6, type='LINE')
    except TypeError:
        col.separator(factor=0.6)


def draw_wiring(layout, context, st=None):
    """ONE box. The usermod slots, then everything else that has to be true.

    MINIMAL TEXT. A row is an icon, a name, a state and one button; the
    explanation is the tooltip on the button you are already pointing at.
    The only prose left is a single line for a row that is RED, because
    "D: is not connected, do not change this path" is the difference between
    fixing it and breaking something that was right.

    CLOSABLE (sec_wiring), and the header still carries the verdict either
    way - a folded wiring box that hid "3 broken" would be a trap. The
    section icon is GRAPHITE, the status glyph rides beside the text.
    """
    from .Panel import fold_section
    dev = bool(getattr(st, "developer_mode", False))
    rows = wiring(context)
    ok, warn, bad = wiring_summary(rows)

    if bad:
        title, sicon = f"Wiring - {bad} broken", _STATUS_ICON[BAD]
    else:
        title, sicon = ("Wiring - ready" if warn else "Wiring - all connected"), _STATUS_ICON[OK]

    box, head = fold_section(layout, st, "sec_wiring", title,
                             _icon_id("sec_wiring", 'PLUGIN'))
    right = head.row(align=True)
    right.alignment = 'RIGHT'
    right.label(text="", **_icon_id(*sicon))
    right.operator("ht.dev_recheck_wiring", text="",
                   **_icon_id("rescan_animations", 'FILE_REFRESH'))
    if box is None:
        return

    col = box.column()
    um_states = _draw_usermod_slots(col, context)

    _divider_drawn = False
    for r in rows:
        if r["key"] == "usermod":
            continue                      #drawn above, as three slots
        if r["key"] in ("session", "anims") and not _divider_drawn:
            _divider_drawn = True
            col.separator(factor=1.4)
        else:
            _line(col)
        row = col.row(align=True)
        row.label(text=r["label"], **_icon_id(*_STATUS_ICON[r["status"]]))
        val = row.row(align=True)
        val.alignment = 'RIGHT'
        val.enabled = r["status"] == OK
        val.label(text=r["value"])

        fix = r.get("fix") or (None, None)
        draw_row_button(row, r["status"] == OK and bool(r["path"]), r["path"],
                        slot_key=fix[1] if fix[0] == "slot" else None,
                        slot_index=1,
                        fallback_op=fix[0], fallback_arg=fix[1])

    # which MOD FOLDERS GOT CONNECTED. Names, not a count - the count is
    # already in the row and it's the names you check a missing model
    # against
    mods = next((r for r in rows if r["key"] == "mods"), None)
    names = (mods or {}).get("names") or []
    if names and dev:
        sub = box.row()
        sub.scale_y = 0.7
        sub.enabled = False
        sub.label(text=", ".join(names[:8])
                       + (f"  +{len(names) - 8}" if len(names) > 8 else ""))

    # ONE LINE, ONLY FOR RED. An orange row already says its state in its own
    # value column; a red one is somebody about to change the wrong thing
    reds = [(f"SFM {i + 1}", long)
            for i, (st, _s, long) in enumerate(um_states) if st == BAD]
    reds += [(r["label"], r["detail"]) for r in rows if r["status"] == BAD]
    for label, long in reds:
        note = box.row()
        note.scale_y = 0.75
        note.alert = True
        note.label(text=f"{label}: {_wrap(long, 54)[0]}")

    draw_search_folders(box, context, st)

    box.separator(factor=0.4)
    box.operator("ht.open_my_config", text="Open Config", **_icon_id("dev_config", 'FILE_TEXT'))



def _configured_usermods():
    """The raw string in every usermod slot, in order. Blanks included."""
    out = []
    try:
        prefs = _ht_paths.addon_prefs()
        out.append((prefs.sfm_usermod_path or "").strip())
    except Exception:                                         # noqa: BLE001
        out.append("")
    try:
        out.extend(user_paths.slots("usermod")[1:])
    except Exception:                                         # noqa: BLE001
        pass
    return out


def diagnose_path(raw, want_gameinfo=False):
    """(status, short, long) for a configured folder. Names the REAL cause.

    THREE WAYS A PATH FAILS AND THEY NEED DIFFERENT SENTENCES. This is the
    single most common thing that goes wrong with this add-on - somebody keeps
    SFM on a second drive, the drive is not plugged in or the network share is
    down, and every import fails with "model missing from the session". The
    error names the symptom and the user goes looking at their session.

        drive not mounted   the D: drive is not there AT ALL. Plug it in.
                            Nothing about the configuration is wrong and
                            changing it would be the wrong fix.
        folder missing      the drive is fine, the folder is not. Moved,
                            renamed, or the path was typed wrong.
        no gameinfo.txt     the folder is there but it is not a usermod - the
                            classic is pointing one level too high, at
                            `game` instead of `game/usermod`.

    A generic "folder does not exist" covers all three and helps with none.
    """
    raw = (raw or "").strip()
    if not raw:
        return None, "not set", ""

    p = Path(bpy.path.abspath(raw))

    # the DRIVE, first. `p.is_dir()` on an unplugged D: is False for the
    # same reason a typo is False, and telling somebody their path is wrong
    # when their drive is unplugged sends them to edit a setting that was
    # correct all along
    anchor = p.anchor
    if anchor and not Path(anchor).exists():
        return BAD, f"{anchor.rstrip(chr(92))} not connected", (
            f"The drive {anchor} is not available. Plug it in, or reconnect "
            f"the network share, and press Re-check. Nothing here is "
            f"misconfigured - do not change this path.")

    if not p.is_dir():
        # Walk up to the deepest parent that is there. "this much of the path
        # is real" turns a wrong path into an obvious one.
        deepest = p
        while deepest.parent != deepest and not deepest.is_dir():
            deepest = deepest.parent
        return BAD, "folder is missing", (
            f"{p} is not there. The deepest part that does exist is "
            f"{deepest} - the rest was moved, renamed, or mistyped.")

    if want_gameinfo and not (p / "gameinfo.txt").is_file():
        kids = []
        try:
            kids = [c.name for c in p.iterdir() if c.is_dir()][:6]
        except OSError:
            pass
        hint = ""
        if "usermod" in [k.lower() for k in kids]:
            # the single most common mistake, and it is one click to fix
            hint = (f"  There IS a 'usermod' folder inside it - you are one "
                    f"level too high. Point this at {p / 'usermod'}.")
        return WARN, "no gameinfo.txt", (
            f"{p} exists but has no gameinfo.txt, so it is not a usermod "
            f"folder.{hint}")

    return OK, "connected", str(p)


# what a slot should CONTAIN, and what it's for. `None` means "a usermod",
# which is checked by gameinfo.txt rather than by a glob.
_SLOT_PATTERN = {"usermod": None, "dmxconvert": "dmxconvert.exe",
                 "faulty_rigs": "*.dmx", "qc_face_data": "*.qc"}

_SLOT_HELP = {
    "usermod":      "SourceFilmmaker/game/usermod",
    "dmxconvert":   "folder holding dmxconvert.exe",
    "faulty_rigs":  "reference .dmx for the rig fixer",
    "qc_face_data": ".qc for the HWM face bake",
}


def _slot_default(key):
    """The folder WE assign for this row when the user has set nothing.

    Every row has one. The old panel left slot 1 of Faulty Rigs and QC Face
    Data blank because the preference behind them defaults to empty - so the
    readout said "28 *.dmx found" and the slot underneath it said "(not set)",
    two true statements that together read as a bug. The shipped folder was
    always being used; it just was not on screen.
    """
    try:
        from ..core import paths
        if key == "usermod":
            from ..session import Import_Session
            return Import_Session._DEFAULT_SFM_USERMOD
        if key == "faulty_rigs":
            return paths.faulty_rigs()
        if key == "qc_face_data":
            return paths.qc_face_data()
        if key == "dmxconvert":
            from ..session import Import_Session
            try:
                return Import_Session._find_dmxconvert().parent
            except Exception:
                return None
    except Exception:                                         # noqa: BLE001
        return None
    return None


def _pref_attr(key):
    """The preference backing slot 1 of `key`, or None if there isn't one."""
    return {"usermod": "sfm_usermod_path",
            "dmxconvert": "dmxconvert_path",
            "faulty_rigs": "faulty_rigs_path",
            "qc_face_data": "qc_face_data_path"}.get(key)


def slot_value(context, key, index):
    """The raw string in one slot, wherever it is actually stored."""
    if index == 0:
        attr = _pref_attr(key)
        try:
            prefs = _ht_paths.addon_prefs()
            return (getattr(prefs, attr, "") or "").strip()
        except Exception:
            return ""
    return user_paths.slots(key)[index]


def set_slot_value(context, key, index, value):
    """Write one slot to whichever store owns it. Returns a note for the user."""
    value = (value or "").strip()
    if index == 0:
        attr = _pref_attr(key)
        prefs = _ht_paths.addon_prefs()
        setattr(prefs, attr, value)
        return "saved to add-on preferences"
    p = user_paths.set_slot(key, index, value)
    return f"saved to {p.parent.name}/{p.name}"


def slot_status(key, raw):
    """(status, what it says) for one slot's current value."""
    if not raw:
        return None, "not set"
    p = Path(bpy.path.abspath(raw))
    if not p.is_dir():
        return BAD, "folder does not exist"
    pattern = _SLOT_PATTERN[key]
    if pattern is None:
        if not (p / "gameinfo.txt").is_file():
            return WARN, "no gameinfo.txt in it"
        return OK, "gameinfo.txt found"
    n = len(list(p.glob(pattern)))
    if not n:
        return WARN, f"0 {pattern} in it"
    return OK, f"{n} {pattern}"


class HT_OT_set_search_folder(Operator):
    """PICK folder (search path) - a usermod folder, or any folder the add-on
        should search. A FOLDER, not a file

        Pick a folder for the add-on to search, and remember it

Slot 1 is saved in the add-on preferences, where it has always been. Slots 2
and 3 are saved to HoovyTools/_config/user_paths.json - plain readable JSON
with absolute paths in it.

THREE USERMOD SLOTS BECAUSE PEOPLE HAVE MORE THAN ONE SFM. A Steam library
that moved, an old install kept for one mod: with a single path the answer to
"why can it not find my model" is "it is in the other install", and fixing
the path just breaks the first one. All three are searched, in order.

The JSON lives inside the add-on folder, so an update that replaces that
folder takes it with it. Print Addon Behavior includes the whole file, so any
log report you have kept still has your paths in it"""
    bl_idname = "ht.set_search_folder"
    bl_label = "Set Search Folder"
    bl_options = {"REGISTER", "UNDO"}

    slot_key: StringProperty(options={'HIDDEN'})
    slot_index: IntProperty(default=0, options={'HIDDEN'})

    # `directory` plus `fileselect_add` is how Blender gives you a FOLDER
    # browser. `filter_folder` hides the files so the dialog can't be
    # confusing about what it wants.
    directory: StringProperty(subtype='DIR_PATH')
    filter_folder: BoolProperty(default=True, options={'HIDDEN'})

    def invoke(self, context, event):
        current = slot_value(context, self.slot_key, self.slot_index)
        if current:
            # Open ON the folder already set. Re-pointing a path is far more
            # common than setting one from nothing, and starting at the last
            # place Blender happened to browse means finding it again by hand.
            self.directory = current
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        key, i = self.slot_key, self.slot_index
        if key not in _SLOT_PATTERN:
            self.report({"ERROR"}, f"Unknown folder slot '{key}'")
            return {"CANCELLED"}
        chosen = (self.directory or "").strip()
        if not chosen:
            self.report({"WARNING"}, "No folder picked.")
            return {"CANCELLED"}

        try:
            where = set_slot_value(context, key, i, chosen)
        except Exception as exc:                              # noqa: BLE001
            self.report({"ERROR"}, f"Could not save the folder: {exc}")
            return {"CANCELLED"}

        status, note = slot_status(key, chosen)
        wiring(context, force=True)          # the tick updates immediately

        level = "WARNING" if status in (WARN, BAD) else "INFO"
        self.report({level}, f"{_SLOT_LABEL[key]} {i + 1}: {note} - {where}")
        return {"FINISHED"}


class HT_OT_clear_search_folder(Operator):
    """Forget this folder. Nothing on disk is touched, only the path

Clearing slot 1 puts it back to the built-in default; clearing any other slot
empties it"""
    bl_idname = "ht.clear_search_folder"
    bl_label = "Clear Search Folder"
    bl_options = {"REGISTER", "UNDO"}

    slot_key: StringProperty(options={'HIDDEN'})
    slot_index: IntProperty(default=0, options={'HIDDEN'})

    def execute(self, context):
        try:
            set_slot_value(context, self.slot_key, self.slot_index, "")
        except Exception as exc:                              # noqa: BLE001
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        wiring(context, force=True)
        self.report({"INFO"},
                    f"{_SLOT_LABEL.get(self.slot_key, self.slot_key)} "
                    f"{self.slot_index + 1} cleared")
        return {"FINISHED"}


class HT_OT_paste_search_folder(Operator):
    """TYPE OR PASTE a folder path - into the box that opens, then confirm

        Type or paste a path straight into this slot

BECAUSE THE PATH IS USUALLY ALREADY IN YOUR CLIPBOARD. You copied it out of
Explorer's address bar, or somebody sent it to you in Discord - and browsing
to a folder you can already name is four clicks to arrive somewhere you were
holding the address of.

Opens with your clipboard already in the box when it looks like a path, so
the common case is press, look, OK. Quotes around it are stripped - copying
a path in Explorer with Ctrl+Shift+C includes them - and a file gets turned
into the folder holding it, since every slot here wants a folder"""
    bl_idname = "ht.paste_search_folder"
    bl_label = "Paste Folder Path"
    bl_options = {"REGISTER", "UNDO"}

    slot_key: StringProperty(options={'HIDDEN'})  # type: ignore
    slot_index: IntProperty(default=0, options={'HIDDEN'})  # type: ignore
    path: StringProperty(name="Path", description="Paste it here")  # type: ignore

    @staticmethod
    def _clean(raw):
        raw = (raw or "").strip().strip('"').strip("'").strip()
        if not raw:
            return ""
        p = Path(bpy.path.abspath(raw))
        # A FILE MEANS THE FOLDER HOLDING IT. Pointing at dmxconvert.exe
        # itself is the obvious thing to do and every slot here wants the
        # folder, so accept it and do the right thing rather than refuse
        if p.is_file():
            p = p.parent
        return str(p)

    def invoke(self, context, event):
        current = slot_value(context, self.slot_key, self.slot_index)
        clip = self._clean(getattr(context.window_manager, "clipboard", ""))
        # only prefill from the clipboard when it actually is a folder -
        # dropping whatever text you last copied into a path field is worse
        # than an empty box
        self.path = current or (clip if clip and Path(clip).is_dir() else "")
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "path", text="")
        cleaned = self._clean(self.path)
        info = col.column(align=True)
        info.scale_y = 0.8
        if not cleaned:
            info.label(text="Paste a folder path.", icon='INFO')
            return
        status, note = slot_status(self.slot_key, cleaned)
        if status == BAD:
            row = info.row()
            row.alert = True
            row.label(text=note, icon='ERROR')
        else:
            info.label(text=note,
                       icon='CHECKMARK' if status == OK else 'ERROR')
        if cleaned != (self.path or "").strip():
            info.label(text=f"will save: {cleaned}")

    def execute(self, context):
        cleaned = self._clean(self.path)
        if not cleaned:
            self.report({"WARNING"}, "Nothing pasted.")
            return {"CANCELLED"}
        try:
            where = set_slot_value(context, self.slot_key, self.slot_index,
                                   cleaned)
        except Exception as exc:                              # noqa: BLE001
            self.report({"ERROR"}, f"Could not save the folder: {exc}")
            return {"CANCELLED"}
        status, note = slot_status(self.slot_key, cleaned)
        wiring(context, force=True)
        level = "WARNING" if status in (WARN, BAD) else "INFO"
        self.report({level},
                    f"{_SLOT_LABEL.get(self.slot_key, self.slot_key)} "
                    f"{self.slot_index + 1}: {note} - {where}")
        return {"FINISHED"}


class HT_OT_make_custom_config(Operator):
    """Create customizedconfig.json, seeded with the folders in use now

WHERE EACH KIND OF ASSET LIVES, as a file you own. `_startupconfig.json`
beside it is generated on every launch from your usermod path and is the
FALLBACK; anything you put in yours wins and is never overwritten.

SEEDED, NOT EMPTY. A blank file with the right keys still means looking up
what a key is called and what shape its value takes. A copy of the working
answer means deleting the lines you do not care about - the same edit,
backwards, and impossible to get wrong. A missing key just means "use the
default", and a single path is accepted anywhere a list is shown.

Refuses to overwrite one that already exists"""
    bl_idname = "ht.make_custom_config"
    bl_label = "Create My Config"

    def execute(self, context):
        from ..core import config
        from ..session import Import_Session
        try:
            path, made = config.write_custom_template(
                Import_Session.usermod_bases(),
                Import_Session._DEFAULT_SFM_USERMOD)
        except Exception as exc:                              # noqa: BLE001
            self.report({"ERROR"}, f"Could not write it: {exc}")
            return {"CANCELLED"}
        if not made:
            self.report({"WARNING"},
                        f"{path.name} already exists - opening it instead")
        try:
            bpy.ops.wm.path_open(filepath=str(path))
        except Exception:                                     # noqa: BLE001
            pass
        self.report({"INFO"}, str(path))
        return {"FINISHED"}


class HT_OT_open_config(Operator):
    """Open one of the two folder-config files"""
    bl_idname = "ht.open_config"
    bl_label = "Open Config"

    which: EnumProperty(  # type: ignore
        name="File",
        items=[("startup", "_startupconfig.json", "Generated, the fallback"),
               ("custom", "customizedconfig.json", "Yours, and it wins")],
        default="startup",
        options={'HIDDEN'},
    )

    def execute(self, context):
        from ..core import config
        path = (config.startup_path() if self.which == "startup"
                else config.custom_path())
        if not path.is_file():
            self.report({"INFO"}, f"{path.name} does not exist yet")
            return {"CANCELLED"}
        try:
            bpy.ops.wm.path_open(filepath=str(path))
        except Exception as exc:                              # noqa: BLE001
            self.report({"ERROR"}, f"Could not open {path}: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, str(path))
        return {"FINISHED"}


class HT_OT_open_my_config(Operator):
    """Open your config file to write it by hand: customizedconfig.json - where each kind of file lives
(animations, elements, models, particles ...). The first press creates it from the folders in use now; what you
write there wins over the generated _startupconfig.json, and a key you delete just means "use the default".

THIS FEATURE WAS ADDED IN VERSION 3.0.0 AND IS IN EXPERIMENTAL STAGE"""
    bl_idname = "ht.open_my_config"
    bl_label = "Open Config"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from ..core import config
        from ..session import Import_Session
        try:
            path, _made = config.write_custom_template(
                Import_Session.usermod_bases(),
                Import_Session._DEFAULT_SFM_USERMOD)
        except Exception as exc:                              # noqa: BLE001
            self.report({"ERROR"}, f"Could not write it: {exc}")
            return {"CANCELLED"}
        if bpy.app.background:
            print(f"[CONFIG]  {path}")
        else:
            bpy.ops.wm.path_open(filepath=str(path))
        self.report({"INFO"}, str(path))
        return {"FINISHED"}


class HT_OT_open_user_paths_json(Operator):
    """Open user_paths.json in whatever opens .json on this computer

It is a small, plain, hand-editable file - three lists of absolute paths -
so editing it by hand is a supported way to work, not a hack. That is also
why it is JSON and not a binary preference blob.

It appears the first time you add a folder; before that there is nothing to
open"""
    bl_idname = "ht.open_user_paths_json"
    bl_label = "Open user_paths.json"

    def execute(self, context):
        store = user_paths.store_path()
        if not store.is_file():
            self.report({"INFO"},
                        "No folders added yet - nothing has been written")
            return {"CANCELLED"}
        try:
            bpy.ops.wm.path_open(filepath=str(store))
        except Exception as exc:                              # noqa: BLE001
            self.report({"ERROR"}, f"Could not open {store}: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, str(store))
        return {"FINISHED"}


class HT_OT_open_search_folder(Operator):
    """NO INPUT - opens the folder already in this slot in your file browser

        Open this folder in the file browser"""
    bl_idname = "ht.open_search_folder"
    bl_label = "Open Folder"

    path: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        target = Path(bpy.path.abspath(self.path or ""))
        if not target.is_dir():
            self.report({"WARNING"}, f"Not a folder: {target}")
            return {"CANCELLED"}
        try:
            bpy.ops.wm.path_open(filepath=str(target))
        except Exception as exc:                              # noqa: BLE001
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


_SLOT_LABEL = {k: label for k, _n, label in user_paths.SLOTS}


def draw_row_button(row, connected, path, slot_key=None, slot_index=0,
                    fallback_op=None, fallback_arg=None):
    """THE ONE BUTTON A ROW GETS. Two states, never both.

        not connected  ->  LOAD      the only thing you can usefully do
        connected      ->  folder    the only thing you would want to do

    FOUR BUTTONS ON A ROW IS A DECISION NOBODY ASKED FOR. Browse, paste, open,
    clear - across ten rows that is forty controls on a screen somebody opened
    because something is broken, and thirty-nine of them are wrong for
    whatever is in front of them. A row that is fine has exactly one sensible
    action; a row that is not has exactly one too, and it is never the same
    one. So the row shows that one.

    Blender's own file browser has a path field at the top, so LOAD is also
    how you paste a path - `ht.paste_search_folder` stays registered and
    reachable from F3 search for anyone who wants the dialog on its own.
    """
    btn = row.row(align=True)
    btn.scale_x = 1.15
    if connected:
        btn.operator("ht.open_search_folder", text="",
                     icon='FILE_FOLDER').path = str(path or "")
        return
    if slot_key is not None:
        op = btn.operator("ht.set_search_folder", text="LOAD",
                          icon='FILEBROWSER')
        op.slot_key, op.slot_index = slot_key, slot_index
    elif fallback_op == "enable":
        btn.operator("ht.enable_addon", text="ENABLE",
                     icon='CHECKBOX_HLT').which = fallback_arg
    elif fallback_op == "connect":
        btn.operator("ht.connect_session", text="LOAD", icon='FILEBROWSER')
    elif fallback_op == "connect_anims":
        btn.operator("ht.connect_animations", text="LOAD", icon='FILEBROWSER')
    else:
        # nothing to offer, but the column still needs its width or the rows
        # above and below stop lining up
        dead = btn.row()
        dead.enabled = False
        dead.label(text="")


def _shorten(text, width=40):
    """Keep the TAIL of a path.

    Every one of these starts with the same forty characters of Program Files,
    and the part that differs - which drive, which install - is at the END,
    which is exactly what a middle-truncated label eats.
    """
    text = str(text)
    return text if len(text) <= width else "..." + text[-(width - 3):]


def _draw_slot_row(col, context, key, index, is_default):
    """One folder line: a tick, the path, what is in it, and the buttons."""
    raw = slot_value(context, key, index)
    if is_default and not raw:
        # nothing set, so show what the add-on is ACTUALLY using. A blank row
        # under a readout saying "28 *.dmx" is two true statements that
        # together read as a bug - and the shipped folder was always being
        # used, it just was never on screen
        d = _slot_default(key)
        if d is not None:
            raw = str(d)

    status, note = slot_status(key, raw)

    row = col.row(align=True)
    if status is None:
        row.label(text="", icon='DOT')
    else:
        ikey, fb = _STATUS_ICON[status]
        row.label(text="", **_icon_id(ikey, fb))

    name = row.row()
    name.enabled = bool(raw)
    name.label(text=_shorten(raw) if raw else "(not set)")

    tail = row.row(align=True)
    tail.alignment = 'RIGHT'
    tail.enabled = status == OK
    tail.label(text=note)

    draw_row_button(row, status == OK, raw, slot_key=key, slot_index=index)


def draw_search_folders(layout, context, st=None):
    """The editable half of the wiring section.

    ONE BOX PER THING IT LOOKS FOR. These used to be four columns of rows
    separated by a blank line inside one box, and at panel width a blank line
    between two rows of the same height is not a separator - the groups read
    as one long list and the only way to tell which folder belonged to which
    heading was to count. A box has an edge; a blank line does not.

    EVERY GROUP READS THE SAME WAY: the first row is the folder WE assign, the
    rest are yours, and the boundary is labelled where it actually falls. Same
    shape everywhere, so the pattern is learned once and then just recognised.
    """
    from .Panel import fold_section
    box, head = fold_section(layout, st, "sec_folders", "Where It Looks",
                             _icon_id("dev_folders", 'FILE_FOLDER'))

    # THE JSON is A FILE YOU CAN OPEN and EDIT, so there is a button that
    # opens it - rather than a sentence naming a path you then go and find
    store = user_paths.store_path()
    ops = head.row(align=True)
    ops.enabled = store.is_file()
    ops.operator("ht.open_user_paths_json", text="",
                 **_icon_id("print_paths", 'TEXT'))
    head.operator("ht.open_search_folder", text="",
                  icon='FILE_FOLDER').path = str(store.parent)
    if box is None:
        return

    for key, count, label in user_paths.SLOTS:
        group = box.box()
        title = group.row(align=True)
        title.label(text=label, **_icon_id("session_load", 'FILE_FOLDER'))
        hint = title.row()
        hint.alignment = 'RIGHT'
        hint.enabled = False
        hint.label(text=_SLOT_HELP[key])

        col = group.column(align=True)
        for i in range(count):
            _draw_slot_row(col, context, key, i, is_default=(i == 0))

    _draw_config_files(box, context)


def _draw_config_files(box, context):
    """The two files that say where each KIND of asset lives.

    A DIFFERENT QUESTION FROM THE SLOTS ABOVE. The slots answer "which copies
    of SFM do I have"; these answer "where does a .pcf live". They are next to
    each other because both are about folders, and separated because mixing
    them is how a settings screen becomes a pile.
    """
    from ..core import config
    grp = box.box()
    head = grp.row(align=True)
    head.label(text="Folder kinds", **_icon_id("dev_config", 'FILE_TEXT'))
    hint = head.row()
    hint.alignment = 'RIGHT'
    hint.enabled = False
    hint.label(text="animations, elements, models, particles, ...")

    col = grp.column(align=True)

    start = config.startup_path()
    row = col.row(align=True)
    row.label(text="_startupconfig.json",
              **_icon_id("status_ok" if start.is_file() else "status_warn",
                         'FILE_TEXT'))
    tail = row.row(align=True)
    tail.alignment = 'RIGHT'
    tail.enabled = False
    tail.label(text="generated each launch")
    opn = row.row(align=True)
    opn.enabled = start.is_file()
    opn.operator("ht.open_config", text="",
                 icon='FILE_FOLDER').which = 'startup'

    custom = config.custom_path()
    row = col.row(align=True)
    if custom.is_file():
        row.label(text="customizedconfig.json",
                  **_icon_id("status_ok", 'FILE_TEXT'))
        tail = row.row(align=True)
        tail.alignment = 'RIGHT'
        tail.enabled = False
        tail.label(text="yours - this one wins")
        row.operator("ht.open_config", text="",
                     icon='FILE_FOLDER').which = 'custom'
    else:
        row.label(text="customizedconfig.json", icon='DOT')
        tail = row.row(align=True)
        tail.alignment = 'RIGHT'
        tail.enabled = False
        tail.label(text="not created")
        row.operator("ht.make_custom_config", text="Create",
                     icon='FILE_NEW')






# ─────────────────────────────────────────────────────────────────────────────
# Print Addon Behavior  -  the file you send someone
# ─────────────────────────────────────────────────────────────────────────────
#
# why A FILE and not THE CONSOLE. Every other diagnostic here prints, and
# printing is fine when the person reading it's the person at the keyboard
# It stops working the moment the answer has to travel: "open Window > Toggle
# System Console, scroll up, select the right part, don't miss the traceback
# above it" is four instructions before the useful one, and the screenshot
# that comes back is always cropped one line too low
#
# A .txt drops into Discord in one drag. So this writes the whole state of the
# add-on to a timestamped file and OPENS the FOLDER, which turns "send me your
# logs" into "press the button, drag the file".
#
# what GOES IN IT is CHOSEN BY one TEST: could someone who can't see this
# machine work out what went wrong? That means the configuration and the
# history - what is installed answers "what have you got", and the question is
# always "what happened". Report_UI keeps the last 80 reports for exactly this
#
# IT CONTAINS PATHS FROM THIS MACHINE, and THEREFORE A USER NAME. That is
# unavoidable - "the path is wrong" is the single most common fault and cannot
# be diagnosed from a redacted path - so the file says so in its own header,
# at the top, before anything worth reading. Nobody should learn what they
# shared after they shared it

LOG_FOLDER_NAME = "HoovyTools Logs"


def _log_folder():
    """Where behavior reports are written. Created on demand, never on
    startup.

    THE ADD-ON'S OWN _Logs FOLDER, not Blender's config dir. Reports used to land in `config/HoovyTools Logs`, which
    put the run logs and the behavior reports in two different places and
    made "open the log folder" ambiguous. Everything lives in
    HoovyTools-SFMSessionImport-Blender-Master/_Logs now (an older folder before 1.20.0); the
    config folder is only the
    fallback for a read-only add-on install, and old reports written there
    are left where they are."""
    d = _ht_paths.logs_dir()
    if d is not None:
        return d
    return Path(bpy.utils.user_resource('CONFIG', path=LOG_FOLDER_NAME,
                                        create=True))


def _sec(title):
    return ["", f"-- {title} " + "-" * max(4, 58 - len(title)), ""]


def _fmt(label, value, width=22):
    return f"  {label:<{width}} {value}"


def _collect_report(context):
    """The whole report, as lines. Pure - it reads state and returns text."""
    import platform
    import sys as _sys
    import addon_utils

    L = []
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")

    L += ["=" * 66,
          "  SFM SESSION IMPORTER  -  ADDON BEHAVIOR REPORT",
          f"  generated {stamp}",
          "=" * 66,
          "",
          "  THIS FILE CONTAINS FILE PATHS FROM THIS COMPUTER, which include",
          "  your Windows user name. That is deliberate - a wrong path is the",
          "  most common fault and cannot be diagnosed without seeing it - but",
          "  read the file before you post it anywhere public.",
          ""]

    # ── versions ─────────────────────────────────────────────────────────
    L += _sec("VERSIONS")
    try:
        from .. import bl_info
        L.append(_fmt("SFM Session Importer",
                      ".".join(str(v) for v in bl_info["version"])))
    except Exception as exc:
        L.append(_fmt("SFM Session Importer", f"(unreadable: {exc})"))
    L += [_fmt("Blender", bpy.app.version_string),
          _fmt("Build", f"{bpy.app.build_branch.decode(errors='ignore')} "
                        f"{bpy.app.build_hash.decode(errors='ignore')}"),
          _fmt("Python", _sys.version.split()[0]),
          _fmt("Platform", platform.platform())]

    # ── wiring ───────────────────────────────────────────────────────────
    L += _sec("WIRING")
    L.append(f"  {_marks.legend()}")
    L.append("")
    try:
        # include_hidden: the report is a completeness list, which is exactly
        # what the SMD importer and the icon count stopped being useful for
        # on the panel. They belong here
        rows = wiring(context, force=True, include_hidden=True)
        ok, warn, bad = wiring_summary(rows)
        L.append(_fmt("summary", f"{ok} ok, {warn} warning(s), {bad} broken"))
        L.append("")
        for r in rows:
            L.append(f"  {_marks.mark(r['status'])} {r['label']:<16} "
                     f"{r['value']}")
            if r["detail"]:
                L.append(f"          {r['detail']}")
            if r.get("path"):
                L.append(f"          {r['path']}")
            # every MOUNT, one PER LINE. "27 found" is a number you have to
            # trust; the names are what somebody compares their missing model
            # against, and a comma-joined line of 27 of them wraps into mush
            for nm in (r.get("names") or []):
                L.append(f"            - {nm}")
    except Exception as exc:                                # noqa: BLE001
        L.append(f"  wiring check failed: {exc}")

    # ── preferences ──────────────────────────────────────────────────────
    L += _sec("PREFERENCES")
    try:
        prefs = _ht_paths.addon_prefs()
        for attr in ("sfm_usermod_path", "scan_game_mounts",
                     "qc_face_data_path", "faulty_rigs_path",
                     "faulty_rigs_sfm_path"):
            raw = getattr(prefs, attr, "<missing>")
            shown = raw if raw not in ("", None) else "(blank - using default)"
            L.append(_fmt(attr, shown))
    except Exception as exc:                                # noqa: BLE001
        L.append(f"  preferences unavailable: {exc}")

    # the JSON, VERBATIM. It lives inside the add-on folder, so an update that
    # replaces that folder takes it with it - and a log report written before
    # the update is then the only copy of those paths that still exists
    try:
        store = user_paths.store_path()
        L += ["", _fmt("user_paths.json",
                       str(store) if store.is_file() else "(none written yet)")]
        if store.is_file():
            for ln in store.read_text(encoding="utf-8").splitlines():
                L.append(f"    {ln}")
    except Exception as exc:                                # noqa: BLE001
        L.append(f"  user_paths.json unreadable: {exc}")

    # ── search paths ─────────────────────────────────────────────────────
    # in FULL, not TRUNCATED. This is the list a missing model was looked up
    # in, so "and 19 more" is exactly where the answer would have been
    try:
        from ..session import Import_Session
        dirs = Import_Session._build_search_paths()
        L += _sec(f"SEARCH PATHS ({len(dirs)})")
        for i, d in enumerate(dirs, 1):
            L.append(f"  {i:>3}  {d}")
    except Exception as exc:                                # noqa: BLE001
        L += _sec("SEARCH PATHS")
        L.append(f"  failed: {exc}")

    # ── data folders ─────────────────────────────────────────────────────
    L += _sec("DATA FOLDERS")
    try:
        from ..core import paths as _paths
        from ..importers import Import_Shape_Keys
        from ..session import Import_Session as _IS
        L.append(_fmt("icons", _paths.icons()))
        for name, folders, pattern in (
                ("faulty rigs", _IS._faulty_rigs_search_folders(), "*.dmx"),
                ("qc face data", Import_Shape_Keys._qc_search_folders(), "*.qc")):
            if not folders:
                L.append(_fmt(name, "(no folder found)"))
            for f in folders:
                L.append(_fmt(name, f"{len(list(f.glob(pattern))):>4} {pattern}"
                                    f"   {f}"))
    except Exception as exc:                                # noqa: BLE001
        L.append(f"  failed: {exc}")

    # ── add-ons ──────────────────────────────────────────────────────────
    L += _sec("ADD-ONS")
    try:
        # every NAME EACH one HAS SHIPPED UNDER. This is a readout, so
        # listing the old names too is correct - it's how somebody with an
        # older install sees "loaded" instead of "not installed"
        from ..core import siblings
        _addon_names = (("SourceIO", "SourceIO-master")
                        + siblings.names("particles")
                        + ("HoovyTools-SFMSessionImport-Blender-Master",
                           "HoovyTools",
                           "io_scene_valvesource"))
        for name in _addon_names:
            loaded, enabled = addon_utils.check(name)
            if loaded or enabled:
                L.append(_fmt(name, f"loaded={bool(loaded)} enabled={bool(enabled)}"))
            else:
                L.append(_fmt(name, "not installed"))
        L.append(_fmt("import_scene.smd",
                      "registered" if hasattr(bpy.ops.import_scene, "smd")
                      else "MISSING"))
        L.append(_fmt("ht.* operators", len([m for m in dir(bpy.ops.ht)
                                             if not m.startswith("_")])))
        from .. import _pcoll, _ICON_KEYS
        L.append(_fmt("panel icons",
                      f"{len(_pcoll) if _pcoll else 0}/{len(_ICON_KEYS)}"))
    except Exception as exc:                                # noqa: BLE001
        L.append(f"  failed: {exc}")

    # ── scene ────────────────────────────────────────────────────────────
    L += _sec("SCENE")
    try:
        sc = context.scene
        objs = list(sc.objects)
        kinds = {}
        for o in objs:
            kinds[o.type] = kinds.get(o.type, 0) + 1
        from .Panel import armature_status
        arms = [o for o in objs if o.type == 'ARMATURE']
        stat = {}
        for a in arms:
            try:
                s = armature_status(a)
            except Exception:
                s = "?"
            stat[s] = stat.get(s, 0) + 1
        L += [_fmt("blend file", bpy.data.filepath or "(unsaved)"),
              _fmt("frames", f"{sc.frame_start} - {sc.frame_end}  @ "
                             f"{sc.render.fps / sc.render.fps_base:g} fps"),
              _fmt("objects", f"{len(objs)}  ("
                              + ", ".join(f"{k.lower()} {v}"
                                          for k, v in sorted(kinds.items()))
                              + ")"),
              _fmt("rig status", ", ".join(f"{k} {v}" for k, v in sorted(stat.items()))
                                 or "(no armatures)"),
              _fmt("actions", len(bpy.data.actions)),
              _fmt("collections", len(bpy.data.collections))]
    except Exception as exc:                                # noqa: BLE001
        L.append(f"  failed: {exc}")

    # ── session ──────────────────────────────────────────────────────────
    L += _sec("SESSION")
    try:
        from ..session import Session_Paths
        sess = Session_Paths.session_file(context.scene)
        pr = Session_Paths.project(context)
        L.append(_fmt("connected", sess if sess else "(none)"))
        if pr is not None:
            for attr in ("session_sets", "session_fps", "anim_folder"):
                if hasattr(pr, attr):
                    L.append(_fmt(attr, getattr(pr, attr)))
    except Exception as exc:                                # noqa: BLE001
        L.append(f"  failed: {exc}")

    # ── what actually happened ───────────────────────────────────────────
    try:
        from ..core import Report_UI
        hist = Report_UI.history()
        L += _sec(f"WHAT HAPPENED THIS SESSION ({len(hist)} report(s))")
        if not hist:
            L.append("  Nothing has been run yet since the add-on loaded.")
            L.append("  Reproduce the problem, THEN press Print Addon "
                     "Behavior - this")
            L.append("  section is the one that usually holds the answer.")
        for item in hist:
            mark = {'INFO': "     ", 'WARNING': "WARN ", 'ERROR': "FAIL "}.get(
                item["level"], "     ")
            L.append(f"  {item['t']}  {mark} {item['summary']}")
        # the last few in FULL. A one-line summary says a step ran; the body
        # says what it did, and the thing that went wrong is almost always in
        # the most recent one
        for item in hist[-3:]:
            L += ["", f"  --- {item['t']}  {item['title']}  "
                      f"({item['level']}) ---"]
            L += [f"      {ln}" for ln in item["lines"][:60]]
            if len(item["lines"]) > 60:
                L.append(f"      ... {len(item['lines']) - 60} more line(s)")
    except Exception as exc:                                # noqa: BLE001
        L.append(f"  history unavailable: {exc}")

    L += ["", "=" * 66, "  end of report", "=" * 66]
    return L


def _reveal(path):
    """Open the folder, selecting the file when the OS can. (ok, note)."""
    folder = path.parent
    if _sys.platform == "win32":
        try:
            #/select, highlights the new file among however many are already
            #in there. The comma is part of the flag, not a typo, and the
            #path must be a separate argument or Explorer ignores it
            subprocess.Popen(["explorer", "/select,", str(path)])
            return True, "folder opened, file selected"
        except Exception:
            pass
    try:
        bpy.ops.wm.path_open(filepath=str(folder))
        return True, "folder opened"
    except Exception as exc:                                # noqa: BLE001
        return False, f"could not open the folder ({exc})"


class HT_OT_dev_log_report(Operator):
    """Write everything about this add-on to a .txt and open the folder

FOR SENDING TO SOMEONE ELSE. It writes a timestamped
"<date> <time> Log report.txt" and opens the folder with it selected, so
troubleshooting is "press the button, drag the file into Discord" instead
of "open the system console, scroll up, screenshot the right part".

It contains the versions, the wiring readout, your preferences, every
search path in full, the data folders and their file counts, which add-ons
are loaded, a scene summary, and WHAT THE ADD-ON HAS ACTUALLY DONE since it
loaded - the last 80 reports, with the most recent three in full.

REPRODUCE THE PROBLEM FIRST, THEN PRESS THIS. Pressing it on a fresh
Blender records a healthy add-on that has not done anything, which is the
one thing nobody needs to see.

The file has file paths from this computer in it, including your user name.
It says so at the top. Read it before posting it somewhere public"""
    bl_idname = "ht.dev_log_report"
    bl_label = "Print Addon Behavior"

    open_folder: BoolProperty(
        name="Open the folder afterwards",
        description="Show the file in Explorer as soon as it is written. Turn "
                    "this off if you only want the file on disk",
        default=True,
    )

    def execute(self, context):
        try:
            lines = _collect_report(context)
        except Exception as exc:                            # noqa: BLE001
            # A report about what is broken must not need everything to work
            # If collection itself dies, write the traceback out - that is
            # the report at that point
            import traceback
            lines = ["HOOVYTOOLS LOG REPORT - COLLECTION FAILED",
                     "", f"{exc}", ""] + traceback.format_exc().splitlines()

        name = time.strftime("%Y-%m-%d %H-%M") + " Log report.txt"
        try:
            folder = _log_folder()
            path = folder / name
            # same minute twice gets a suffix rather than an overwrite - two
            # runs a few seconds apart is exactly the before/after pair
            # someone is trying to compare.
            n = 2
            while path.exists():
                path = folder / (name[:-4] + f" ({n}).txt")
                n += 1
            path.write_text("\n".join(lines), encoding="utf-8")
        except Exception as exc:                            # noqa: BLE001
            self.report({"ERROR"}, f"Could not write the log: {exc}")
            return {"CANCELLED"}

        note = "not opened"
        if self.open_folder:
            _ok, note = _reveal(path)

        print()
        for ln in lines:
            print(ln)
        print()

        self.report({"INFO"}, f"{path.name} written - {note}")
        return {"FINISHED"}


class HT_OT_dev_open_log_folder(Operator):
    """Open the folder the behavior reports are written to

Every report ever written is still in there, oldest first by name. Delete
them whenever you like - nothing reads them back"""
    bl_idname = "ht.dev_open_log_folder"
    bl_label = "Open Log Folder"

    def execute(self, context):
        folder = _log_folder()
        try:
            bpy.ops.wm.path_open(filepath=str(folder))
        except Exception as exc:                            # noqa: BLE001
            self.report({"ERROR"}, f"Could not open {folder}: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, str(folder))
        return {"FINISHED"}



HELP_STEM = "__SFM Session Importer Log Report Data__"     # 3.0.0 (was __HoovyTools ...)
HELP_POINTS = 10          # the paragraph names this many problems, then points at the list
HELP_LOG_FULL = 6000      # lines of THIS Blender session's log kept in full
HELP_LOG_TAIL = 800       # lines kept from the end of each older log
_HELP_ORDINALS = ("First of all", "Second of all", "Third", "Fourth", "Fifth",
                  "Sixth", "Seventh", "Eighth", "Ninth", "Tenth")
_HELP_LEVELS = ("BREAKS", "RISKY", "NOTE")


def _pl(n, one, many):
    return one if n == 1 else many


def help_path(folder):
    """(path, version) - the next free __HoovyTools Log Report Data__ (V#).txt"""
    import re as _re
    rx = _re.compile(_re.escape(HELP_STEM) + r" \(V(\d+)\)\.txt$")
    top = 0
    for f in folder.glob(HELP_STEM + " (V*).txt"):
        m = rx.match(f.name)
        if m:
            top = max(top, int(m.group(1)))
    return folder / f"{HELP_STEM} (V{top + 1}).txt", top + 1


def _wiring_flag(r):
    """(level, sentence) for one wiring row that is not OK, or None. The
    sentence finishes "First of all, ..." - so it starts lower case."""
    key, val, det = r["key"], (r.get("value") or "").strip(), (r.get("detail") or "").strip()
    bad = r["status"] == BAD
    if key == "usermod":
        return ("BREAKS" if bad else "RISKY",
                f"SFM Session Importer cannot find Source Filmmaker ({val}) - {det}" if bad
                else f"one of your SFM folders is not right ({val}) - {det}")
    if key == "mods":
        return ("RISKY", f"the mod folders SFM loads were not found ({val}), so "
                         f"models that live in them will come out missing")
    if key == "dmxconvert":
        return ("RISKY", f"dmxconvert.exe was not found ({val}), so a .dmx the "
                         f"built-in reader cannot open will fail")
    if key == "sourceio":
        return ("NOTE", f"SourceIO is {val}, so the shot's map is left out - "
                        f"the models import with HoovyTools' own importer")
    if key == "rigs":
        return ("NOTE", f"the Faulty Rigs folder has {val}, so rigs keep "
                        f"SourceIO's rest pose")
    if key == "qc":
        return ("NOTE", f"the QC Face Data folder has {val}, so the HWM face "
                        f"bake has nothing to read")
    if key == "particles":
        return ("RISKY", f"the Source Particle Import add-on is {val}, so "
                         f"particles will not import")
    if key == "session":
        # a session that's simply not loaded yet is not a problem to report - only one that vanished is
        return ("BREAKS", f"the session this .blend was connected to is gone "
                          f"({det})") if bad else None
    if key == "anims":
        return ("RISKY", f"the animations folder this .blend was connected to "
                         f"is gone ({det})") if bad else None
    return ("BREAKS" if bad else "RISKY",
            f"{r.get('label', key)} is {val}" + (f" - {det}" if det else ""))


def help_flags(context):
    """[(level, sentence)] - what is wrong, worst first. Never raises."""
    flags = []
    try:
        for r in wiring(context, force=True):
            if r["status"] in (WARN, BAD):
                f = _wiring_flag(r)
                if f:
                    flags.append(f)
    except Exception as exc:                                  # noqa: BLE001
        flags.append(("RISKY", f"the wiring check itself failed ({exc})"))

    # the frame rate - the quiet way an import goes wrong
    try:
        from ..session import Session_Paths, FPS_Safety
        pr = Session_Paths.project(context)
        sfm = (pr.session_fps or pr.anim_fps) if pr is not None else ""
        blender = f"{FPS_Safety.scene_fps(context.scene):g}"
        if sfm and sfm != blender:
            flags.append(("RISKY", f"the scene runs at {blender} fps but the "
                                   f"session is {sfm} fps, so the animation "
                                   f"lands at the wrong speed"))
    except Exception:                                         # noqa: BLE001
        pass

    # what happened - the latest report of each kind that did not end well
    try:
        from ..core import Report_UI
        seen = set()
        for item in reversed(Report_UI.history()):
            if item["level"] not in ("ERROR", "WARNING") or item["title"] in seen:
                continue
            seen.add(item["title"])
            first = next((ln.strip() for ln in item["lines"] if ln.strip()), "")
            if item["level"] == "ERROR":
                flags.append(("BREAKS", f"'{item['title']}' failed at "
                                        f"{item['t']}" + (f": {first}" if first else "")))
            else:
                flags.append(("RISKY", f"'{item['title']}' ended with a warning "
                                       f"at {item['t']}" + (f": {first}" if first else "")))
    except Exception:                                         # noqa: BLE001
        pass

    # Python errors in this session's log - the thing nobody sees in a popup.
    try:
        from ..core import Report_UI
        lp = Report_UI.log_path()
        if lp is not None and lp.is_file():
            n = lp.read_text(encoding="utf-8", errors="replace").count("Traceback")
            if n:
                flags.append(("RISKY", f"this Blender session's log has {n} Python "
                                       f"error{_pl(n, '', 's')} (tracebacks) - "
                                       f"they are in the LOGS part of this file"))
    except Exception:                                         # noqa: BLE001
        pass
    order = {k: i for i, k in enumerate(_HELP_LEVELS)}
    return sorted(flags, key=lambda f: order.get(f[0], 9))


def help_paragraph(flags):
    """IN PLAIN WORDS - the paragraph a person reads first."""
    serious = [f for f in flags if f[0] in ("BREAKS", "RISKY")]
    notes = [f for f in flags if f[0] == "NOTE"]
    if not serious:
        text = ("The checks below found no known problem: SFM Session Importer finds Source Filmmaker and "
                "everything it uses, and nothing it reported has failed since Blender started. The checks only "
                "know the problems already seen.")
        if notes:
            text += (" There %s %d small note%s at the bottom of the list."
                     % (_pl(len(notes), "is", "are"), len(notes), _pl(len(notes), "", "s")))
        return text + (" If something still went wrong, do it again and press "
                       "PRINT HELP right after - this file then shows what "
                       "happened.")
    if any(f[0] == "BREAKS" for f in serious):
        parts = ["Look, SFM Session Importer is going to have a hard time on this computer, "
                 "but fear not!"]
    else:
        parts = ["Look, SFM Session Importer will mostly work here, but a few things are "
                 "off - fear not!"]
    told = serious[:HELP_POINTS]
    rest = len(serious) - len(told)
    for i, (_lvl, sentence) in enumerate(told):
        lead = _HELP_ORDINALS[i] if i < len(_HELP_ORDINALS) else "On top of that"
        if i == len(told) - 1 and i > 0 and not rest:
            lead = "And last but not least"
        parts.append(f"{lead}, {sentence.rstrip('.')}.")
    if rest:
        parts.append(f"And that's not all: {rest} more problem{_pl(rest, '', 's')} "
                     f"{_pl(rest, 'is', 'are')} waiting in the list below.")
    if notes:
        parts.append(f"There {_pl(len(notes), 'is', 'are')} also {len(notes)} "
                     f"small note{_pl(len(notes), '', 's')} at the bottom of the list.")
    parts.append("Fix the BREAKS first, then the RISKY ones, and press PRINT "
                 "HELP again.")
    return " ".join(parts)


def _collect_logs():
    """Every HoovyTools log on this computer, this session's first."""
    out = []
    try:
        from ..core import Report_UI
        d = _ht_paths.logs_dir()
        if d is None or not d.is_dir():
            return ["  (no log folder)"]
        current = Report_UI.log_path()
        logs = sorted(d.glob("HoovyTools_*.log"), key=lambda f: f.stat().st_mtime,
                      reverse=True)
        if current is not None and current in logs:
            logs.remove(current)
            logs.insert(0, current)
        if not logs:
            return ["  (no logs written yet)"]
        for i, f in enumerate(logs):
            text = f.read_text(encoding="utf-8", errors="replace").splitlines()
            keep = HELP_LOG_FULL if i == 0 else HELP_LOG_TAIL
            tag = "this Blender session" if i == 0 and f == current else "an earlier session"
            out += ["", f"--- {f.name}  ({tag}, {len(text)} line(s)) ---"]
            if len(text) > keep:
                out.append(f"    ... the first {len(text) - keep} line(s) left out ...")
                text = text[-keep:]
            out += text
    except Exception as exc:                                  # noqa: BLE001
        out.append(f"  logs unavailable: {exc}")
    return out


def collect_help(context, version=1):
    """(lines, flags) - the whole PRINT HELP file. Pure: reads, never writes."""
    import json as _json
    import textwrap
    flags = help_flags(context)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        from .. import bl_info
        ver = ".".join(str(v) for v in bl_info["version"])
    except Exception:                                         # noqa: BLE001
        ver = "?"
    L = ["=" * 78,
         f"  {HELP_STEM} (V{version})",
         f"  SFM Session Importer {ver}  -  Blender {bpy.app.version_string}  -  {stamp}",
         "=" * 78,
         "",
         "  THIS FILE CONTAINS FILE PATHS FROM THIS COMPUTER, which include your",
         "  user name. Read it before you post it anywhere public.",
         "",
         "-- IN PLAIN WORDS " + "-" * 60, ""]
    L += ["  " + ln for ln in textwrap.wrap(help_paragraph(flags), 74)]
    L += ["", f"-- WHAT'S WRONG ({len(flags)}) " + "-" * 56, ""]
    if not flags:
        L.append("  The checks found nothing - but they only know the problems already seen. If something went")
        L.append("  wrong, write what you did and what happened when you send this file.")
    for lvl, sentence in flags:
        wrapped = textwrap.wrap(sentence[:1].upper() + sentence[1:], 66)
        L.append(f"  [{lvl:<6}] {wrapped[0] if wrapped else ''}")
        L += [f"           {w}" for w in wrapped[1:]]
    L += ["", "", "=" * 78, "  ADDON BEHAVIOR  (what PRINT ADDON BEHAVIOR writes)", "=" * 78]
    try:
        L += _collect_report(context)
    except Exception as exc:                                  # noqa: BLE001
        import traceback
        L += [f"  addon behavior failed: {exc}"] + traceback.format_exc().splitlines()
    L += ["", "", "=" * 78, "  LOGS  (every SFM Session Importer log, this Blender session first)", "=" * 78]
    L += _collect_logs()

    data = {"tool": "SFM Session Importer", "version": ver, "blender": bpy.app.version_string,
            "generated": stamp, "report": f"{HELP_STEM} (V{version})",
            "flags": [{"level": a, "what": b} for a, b in flags]}
    try:
        data["wiring"] = [{k: r.get(k) for k in ("key", "label", "status", "value", "detail")}
                          for r in wiring(context, force=True, include_hidden=True)]
    except Exception as exc:                                  # noqa: BLE001
        data["wiring"] = f"failed: {exc}"
    try:
        from ..core import Report_UI
        data["reports"] = [{"t": h["t"], "key": h["key"], "level": h["level"],
                            "title": h["title"], "lines": h["lines"][:40]}
                           for h in Report_UI.history()[-30:]]
    except Exception:                                         # noqa: BLE001
        data["reports"] = []
    try:
        from ..session import Session_Paths
        sess = Session_Paths.session_file(context.scene)
        data["session"] = str(sess) if sess else None
        sc = context.scene
        data["scene"] = {"fps": sc.render.fps / sc.render.fps_base,
                         "frames": [sc.frame_start, sc.frame_end],
                         "objects": len(sc.objects),
                         "armatures": sum(1 for o in sc.objects if o.type == 'ARMATURE')}
    except Exception:                                         # noqa: BLE001
        pass
    L += ["", "", "=" * 78, "  FOR THE DEVELOPER  (the same facts as JSON)", "=" * 78, ""]
    L += _json.dumps(data, indent=2, default=str).splitlines()
    L += ["", "=" * 78, "  end of report", "=" * 78]
    return L, flags


class HT_OT_print_help(Operator):
    """Write ONE file to send when something goes wrong - it says what is wrong first

Writes "__HoovyTools Log Report Data__ (V#).txt" into the log folder (a new
version every press) and opens the folder. At the top, IN PLAIN WORDS: what
is broken on this computer and what to fix first. Under it: everything
PRINT ADDON BEHAVIOR collects, then every HoovyTools log on this computer,
then the same facts as data for the developer.

REPRODUCE THE PROBLEM FIRST, THEN PRESS THIS - the file then shows what
happened.

It holds file paths from this computer, including your user name. Read it
before you post it anywhere public.
THIS FEATURE WAS ADDED IN VERSION 1.18.0 AND IS IN EXPERIMENTAL STAGE"""
    bl_idname = "ht.print_help"
    bl_label = "Print Help"

    open_folder: BoolProperty(  # type: ignore
        name="Open the folder afterwards",
        description="Show the file in Explorer as soon as it is written",
        default=True,
    )

    def execute(self, context):
        folder = _log_folder()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path, version = help_path(folder)
        except Exception as exc:                            # noqa: BLE001
            self.report({"ERROR"}, f"No log folder: {exc}")
            return {"CANCELLED"}
        try:
            lines, flags = collect_help(context, version)
        except Exception as exc:                            # noqa: BLE001
            import traceback
            lines = [f"{HELP_STEM} (V{version}) - COLLECTION FAILED", "", str(exc), ""] \
                + traceback.format_exc().splitlines()
            flags = []
        try:
            path.write_text("\n".join(lines), encoding="utf-8")
        except Exception as exc:                            # noqa: BLE001
            self.report({"ERROR"}, f"Could not write the help file: {exc}")
            return {"CANCELLED"}
        note = "not opened"
        if self.open_folder:
            _ok, note = _reveal(path)
        print()
        for ln in lines[:40]:
            print(ln)
        print(f"[HELP]  ... {path}")
        worst = next((f[0] for f in flags), None)
        self.report({"WARNING" if worst == "BREAKS" else "INFO"},
                    f"{path.name} written - {len(flags)} problem(s) listed - {note}")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# Register Skydome
# ─────────────────────────────────────────────────────────────────────────────

def _skydome_armatures(match):
    needle = (match or "").strip().lower()
    if not needle:
        return []
    return sorted((o for o in bpy.data.objects
                   if o.type == "ARMATURE" and needle in o.name.lower()),
                  key=lambda o: o.name)


def _skydome_meshes(arm):
    """Every mesh CONNECTED to *arm*: parented under it, or deformed by an
    armature modifier that targets it. Both routes, because a session import
    parents the meshes while a hand-built scene may only wire the modifier."""
    out = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        p = o.parent
        while p is not None:
            if p == arm:
                out.append(o)
                break
            p = p.parent
        else:
            for m in o.modifiers:
                if m.type == "ARMATURE" and m.object == arm:
                    out.append(o)
                    break
    return sorted(out, key=lambda o: o.name)


def _first_image_of(mesh):
    """The first image any of *mesh*'s materials samples, or None."""
    for slot in mesh.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes or not mat.node_tree:
            continue
        for node in mat.node_tree.nodes:
            if node.bl_idname == "ShaderNodeTexImage" and node.image:
                return node.image
    return None


# PRIORITY: 4/10
# (Viewport/render taste. The skydome WORLD RIG below lights the scene from
# the dome's own texture; nothing downstream depends on its numbers.)

SKYDOME_GROUP = "HT Skydome World"


def _skydome_average_color(image):
    """The image's mean RGB, sampled fast. The rig mixes DIFFUSE rays toward
    this flat colour, which is the poor man's blurred-HDRI: bounce lighting
    stops flickering with every bright pixel while the camera keeps the
    sharp sky. Never raises - a grey 0.5 is the safe answer."""
    try:
        import numpy as np
        n = image.size[0] * image.size[1]
        if not n:
            return (0.5, 0.5, 0.5)
        buf = np.empty(n * image.channels, dtype=np.float32)
        image.pixels.foreach_get(buf)
        px = buf.reshape(-1, image.channels)
        step = max(1, n // 65536)          #~65k samples is plenty for a mean
        rgb = px[::step, :3].mean(axis=0)
        return tuple(float(c) for c in rgb)
    except Exception:                                         # noqa: BLE001
        return (0.5, 0.5, 0.5)


def _group_socket(node, identifier, outputs=False):
    coll = node.outputs if outputs else node.inputs
    return next(s for s in coll if s.identifier == identifier)


def _build_skydome_world(scene, image):
    """Rebuild the world as the HT Skydome World node group.

    Not a flat Background - a rig, with every knob a group input on ONE
    node in the world tree:

      Strength          how hard the sky lights the scene
      Rotation          spins the sky around Z - art-direct where the light
                        comes from without touching the dome mesh
      Tint              multiplied over the sky colour
      Saturation /      an HSV stage on the texture, because a game skybox
      Brightness        is usually either washed out or radioactive
      Ground Fade       dims the BELOW-HORIZON half, so the missing ground
                        does not bounce sky-blue up at everyone's chin
      Diffuse Softness  blends the sky toward its average colour (baked at
                        build time) - stable bounce light from a busy
                        texture, no blur pass needed

    NO LIGHT PATH NODE, AND THAT IS THE POINT. The first version split
    camera rays from lighting rays through Is Camera Ray - Cycles
    evaluates that per actual ray, while EEVEE bakes the world into a
    probe where the ray flags are not typed the same way, so the two
    engines picked DIFFERENT branches and the same scene lit differently.
    Every node left in this rig - env texture on Generated coordinates,
    HSV, mixes, math on the view direction - evaluates identically in
    both engines. The cost is the separate Camera Strength knob; the
    backdrop belongs to the DOME MESH anyway (camera rays stay on it),
    so the world's own camera appearance hardly shows.

    Re-running rebuilds the group from scratch - knob values reset to
    defaults, which is what a "register" button should do.
    """
    # fresh group every run. Rebuilding in place would preserve knob values
    # but also preserve any half-broken state from an older build.
    old = bpy.data.node_groups.get(SKYDOME_GROUP)
    if old is not None:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(SKYDOME_GROUP, "ShaderNodeTree")

    def add_in(name, stype, default=None, mn=None, mx=None, subtype=None):
        s = ng.interface.new_socket(name, in_out='INPUT', socket_type=stype)
        if default is not None:
            s.default_value = default
        if mn is not None and hasattr(s, "min_value"):
            s.min_value = mn
        if mx is not None and hasattr(s, "max_value"):
            s.max_value = mx
        if subtype and hasattr(s, "subtype"):
            try:
                s.subtype = subtype
            except Exception:
                pass
        return s

    add_in("Strength", 'NodeSocketFloat', 0.1, 0.0, 100.0)
    add_in("Rotation", 'NodeSocketFloat', 0.0, subtype='ANGLE')
    add_in("Tint", 'NodeSocketColor', (1.0, 1.0, 1.0, 1.0))
    add_in("Saturation", 'NodeSocketFloat', 1.0, 0.0, 2.0)
    add_in("Brightness", 'NodeSocketFloat', 1.0, 0.0, 4.0)
    add_in("Ground Fade", 'NodeSocketFloat', 0.5, 0.0, 1.0)
    add_in("Diffuse Softness", 'NodeSocketFloat', 0.35, 0.0, 1.0)
    if image is None:
        add_in("Sky Color", 'NodeSocketColor', (0.35, 0.48, 0.70, 1.0))
    ng.interface.new_socket("Background", in_out='OUTPUT',
                            socket_type='NodeSocketShader')

    n = ng.nodes
    gi = n.new("NodeGroupInput");        gi.location = (-1180, 0)
    go = n.new("NodeGroupOutput");       go.location = (560, 0)
    texco = n.new("ShaderNodeTexCoord"); texco.location = (-1180, 260)
    vrot = n.new("ShaderNodeVectorRotate")
    vrot.rotation_type = 'Z_AXIS'
    vrot.location = (-960, 260)
    env = None
    if image is not None:
        env = n.new("ShaderNodeTexEnvironment")
        env.image = image
        env.location = (-760, 260)
    hsv = n.new("ShaderNodeHueSaturation"); hsv.location = (-480, 260)
    tint = n.new("ShaderNodeMix")
    tint.data_type = 'RGBA'
    tint.blend_type = 'MULTIPLY'
    tint.inputs["Factor"].default_value = 1.0
    tint.location = (-300, 260)
    avg = n.new("ShaderNodeRGB"); avg.location = (-300, 40)
    avg.outputs[0].default_value = ((*_skydome_average_color(image), 1.0)
                                    if image is not None
                                    else (0.35, 0.48, 0.70, 1.0))
    avg.label = "sky average (baked)"
    soft = n.new("ShaderNodeMix"); soft.data_type = 'RGBA'
    soft.location = (-100, 200)
    soft.label = "toward average"

    # ground fade: factor = 1 - GroundFade * max(0, -Z) of the view
    # direction. Above the horizon it's exactly 1. Direction-dependent,
    # but ENGINE-INDEPENDENT: both engines evaluate the world per
    # direction, unlike per-ray-type
    sep = n.new("ShaderNodeSeparateXYZ"); sep.location = (-960, -40)
    mneg = n.new("ShaderNodeMath"); mneg.operation = 'MULTIPLY'
    mneg.inputs[1].default_value = -1.0
    mneg.location = (-760, -40)
    mmax = n.new("ShaderNodeMath"); mmax.operation = 'MAXIMUM'
    mmax.inputs[1].default_value = 0.0
    mmax.location = (-580, -40)
    mfade = n.new("ShaderNodeMath"); mfade.operation = 'MULTIPLY'
    mfade.location = (-400, -40)
    msub = n.new("ShaderNodeMath"); msub.operation = 'SUBTRACT'
    msub.inputs[0].default_value = 1.0
    msub.location = (-220, -40)
    msub.use_clamp = True
    mstr = n.new("ShaderNodeMath"); mstr.operation = 'MULTIPLY'
    mstr.location = (-40, -60)
    mstr.label = "strength x ground"
    bg = n.new("ShaderNodeBackground"); bg.location = (300, 60)

    L = ng.links.new
    L(texco.outputs["Generated"], vrot.inputs["Vector"])
    L(gi.outputs["Rotation"], vrot.inputs["Angle"])
    if env is not None:
        L(vrot.outputs["Vector"], env.inputs["Vector"])
        L(env.outputs["Color"], hsv.inputs["Color"])
    else:
        L(gi.outputs["Sky Color"], hsv.inputs["Color"])
    L(gi.outputs["Saturation"], hsv.inputs["Saturation"])
    L(gi.outputs["Brightness"], hsv.inputs["Value"])
    L(hsv.outputs["Color"], _group_socket(tint, "A_Color"))
    L(gi.outputs["Tint"], _group_socket(tint, "B_Color"))
    L(_group_socket(tint, "Result_Color", True), _group_socket(soft, "A_Color"))
    L(avg.outputs[0], _group_socket(soft, "B_Color"))
    L(gi.outputs["Diffuse Softness"], soft.inputs["Factor"])
    L(texco.outputs["Generated"], sep.inputs["Vector"])
    L(sep.outputs["Z"], mneg.inputs[0])
    L(mneg.outputs[0], mmax.inputs[0])
    L(mmax.outputs[0], mfade.inputs[0])
    L(gi.outputs["Ground Fade"], mfade.inputs[1])
    L(mfade.outputs[0], msub.inputs[1])
    L(gi.outputs["Strength"], mstr.inputs[0])
    L(msub.outputs[0], mstr.inputs[1])
    L(_group_socket(soft, "Result_Color", True), bg.inputs["Color"])
    L(mstr.outputs[0], bg.inputs["Strength"])
    L(bg.outputs["Background"], go.inputs["Background"])

    # the world tree itself: one group node and the output.
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("HT Skydome World")
        scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = ng
    grp.location = (-220, 0)
    grp.width = 200
    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (60, 0)
    nt.links.new(grp.outputs["Background"], out.inputs["Surface"])
    return world


class HT_OT_register_skydome(Operator):
    """NO INPUT - acts on every armature whose name contains the match string

        Make the scene's skydome light the world instead of shadowing it

Two things happen, both idempotent:

1  Every mesh connected to a skydome armature stops casting shadows
   AND stops receiving diffuse rays (Ray Visibility > Shadow and
   Diffuse off) - the world rig owns the lighting, and the camera
   still sees the dome.

2  The world is rebuilt as the HT Skydome World node group, lit from
   the dome's own texture. One node, seven knobs: Strength, Rotation
   (spin the sky), Tint / Saturation / Brightness, Ground Fade (the
   missing floor stops bouncing sky-blue upward) and Diffuse Softness
   (blend toward the sky's average colour). NO ray-type tricks, so
   EEVEE and Cycles light the scene IDENTICALLY.

No dome in the scene: the world is still built, with a flat Sky Color
knob standing in for the texture.

Re-running rebuilds the group fresh, knobs back at their defaults"""
    bl_idname = "ht.register_skydome"
    bl_label = "Register Skydome"
    bl_options = {"REGISTER", "UNDO"}

    match: StringProperty(  # type: ignore
        name="Armature name contains",
        description="Case-insensitive substring an armature must carry to "
                    "count as a skydome",
        default="skydome",
    )
    override_world: BoolProperty(  # type: ignore
        name="Override World Shader",
        description="Rebuild the world's node tree from the skydome texture. "
                    "Off: only the shadow visibility is touched",
        default=True,
    )

    def execute(self, context):
        arms = _skydome_armatures(self.match)
        if not arms and not self.override_world:
            self.report({"WARNING"},
                        f"No armature name contains '{self.match}' and "
                        f"Override World is off - nothing to do")
            return {"CANCELLED"}
        if not arms:
            world = _build_skydome_world(context.scene, None)
            from ..core import Report_UI
            Report_UI.report(
                context, "register_skydome", "Register Skydome",
                [f"No armature name contains '{self.match}'.",
                 f"World : '{world.name}' built WITHOUT a dome texture -",
                 f"        the {SKYDOME_GROUP} group carries a Sky Color",
                 "        knob in its place; all other knobs identical",
                 "        (identical in EEVEE and Cycles)"],
                level='INFO', operator=self, prefix="SKYDOME",
                summary="Skydome - no dome found, flat-color world built")
            return {"FINISHED"}

        lines = []
        shadowed = 0
        first_image = None
        first_mesh = None
        for arm in arms:
            meshes = _skydome_meshes(arm)
            for m in meshes:
                if getattr(m, "visible_shadow", True):
                    m.visible_shadow = False
                    shadowed += 1
                if getattr(m, "visible_diffuse", True):
                    m.visible_diffuse = False
            lines.append(f"{arm.name} : {len(meshes)} mesh(es), "
                         f"shadow + diffuse rays off")
            if first_image is None:
                for m in meshes:
                    img = _first_image_of(m)
                    if img is not None:
                        first_image, first_mesh = img, m
                        break

        if self.override_world:
            if first_image is None:
                # dome meshes w/o a texture: same flat-colour fallback
                # as no dome at all - the rig is the point, not the image
                world = _build_skydome_world(context.scene, None)
                lines.append(f"World : '{world.name}' built WITHOUT a dome "
                             f"texture (none found on any skydome mesh) -")
                lines.append(f"        the {SKYDOME_GROUP} group carries a")
                lines.append("        Sky Color knob in its place")
            else:
                world = _build_skydome_world(context.scene, first_image)
                lines.append(f"World : '{world.name}' rebuilt from "
                             f"'{first_image.name}' (via {first_mesh.name})")
                lines.append(f"        {SKYDOME_GROUP} node group - open the")
                lines.append("        World shader for the knobs: Strength,")
                lines.append("        Rotation, Tint, Sat/Brightness,")
                lines.append("        Ground Fade, Diffuse Softness")
                lines.append("        (identical in EEVEE and Cycles)")

        from ..core import Report_UI
        Report_UI.report(
            context, "register_skydome", "Register Skydome", lines,
            level=('WARNING' if (self.override_world and first_image is None)
                   else 'INFO'),
            operator=self, prefix="SKYDOME",
            summary=f"Skydome - {len(arms)} armature(s), "
                    f"{shadowed} mesh(es) stopped casting shadows")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar: Developer tab
# ─────────────────────────────────────────────────────────────────────────────

def _draw_priority_row(col, p):
    row = col.row(align=True)
    row.label(text="", icon=STATUS_ICON[p["status"]])
    sub = row.row(align=True)
    sub.alignment = 'LEFT'
    if p["status"] == "DONE":
        sub.active = False
    sub.label(text=f"{p['n']}.  {p['title']}")
    info = row.row(align=True)
    info.alignment = 'RIGHT'
    info.operator("ht.priority_info", text="", icon='QUESTION',
                  emboss=False).index = p["n"]


def draw_priorities(layout, st):
    done, total = counts()
    box = layout.box()
    head = box.row(align=True)
    head.label(text=f"Priorities  {done}/{total}", icon='PRESET')
    head.operator("ht.dev_dump_roadmap", text="",
                  **_icon_id("print_roadmap", 'COPYDOWN'))

    try:  #UILayout.progress is 4.0+; never let a draw call kill the panel
        bar = box.row()
        bar.scale_y = 0.4
        bar.progress(factor=(done / total if total else 0.0), type='BAR', text=" ")
    except Exception:
        pass

    row = box.row(align=True)
    row.prop(st, "dev_tier", expand=True)

    wanted = st.dev_tier
    for key, label, _desc, icon in TIERS:
        if wanted != 'ALL' and wanted != key:
            continue
        items = tier_items(key)
        if not items:
            continue
        d, t = counts(key)
        sec = box.column(align=True)
        sec.separator()
        title = sec.row(align=True)
        title.label(text=f"{label}   {d}/{t}", icon=icon)
        rows = sec.column(align=True)
        rows.scale_y = 0.9
        for p in items:
            if st.dev_hide_done and p["status"] == "DONE":
                continue
            _draw_priority_row(rows, p)

    foot = box.column(align=True)
    foot.separator()
    foot.scale_y = 0.8
    foot.label(text="Hover ? for the full item.")
    foot.prop(st, "dev_hide_done")


def draw_developer(layout, context, st):
    """The Dev tab - called from Panel.HT_PT_sidebar.draw(). 3.0.0 layout, top to bottom - the same order as Source Particle
    Import's:

        WIRING            is everything found - Where It Looks folded inside,
                          Open Config at the very bottom
        BEHAVIOR REPORT   the version, PRINT HELP, Print Addon Behavior - Logs
                          inside
        CONFIGURE         Layouts first, Popups, Anims Folder, Shot Timing,
                          Frame Rate, Session Automation
        IMPORTED SESSION  the scene readout and the rig roster
        MODEL IMPORTER    HoovyTools or SourceIO, Textures, Skip Hidden
        CREDITS           who made what, the links, and the license
        DEVELOPER MODE    the switch, last

    ALL OF IT IS THERE WITH DEVELOPER MODE OFF. The switch adds detail - the
    console tools, the mod folder names - and the extra options on the Main
    and Tools tabs; it never hides a setting somebody needs.

    THE ROADMAP LIST IS NOT DRAWN HERE. Still `draw_priorities()`, still on
    the roadmap submenu, still dumped by Print Roadmap and every report.
    """
    from .Panel import draw_imported_session

    draw_wiring(layout, context, st)
    draw_behavior(layout, context, st)
    draw_configure(layout, context, st)
    draw_imported_session(layout, context, st)
    draw_model_engine(layout, context, st)
    draw_credits(layout, context, st)
    draw_developer_mode(layout, st)


def draw_developer_mode(layout, st):
    """The DEVELOPER MODE switch, the last thing on the Dev tab - the same in both add-ons."""
    dev = bool(getattr(st, "developer_mode", False))
    layout.separator(factor=0.5)
    row = layout.row(align=True)
    row.scale_y = 1.4
    row.prop(st, "developer_mode", toggle=True, text="DEVELOPER MODE",
             **_icon_id("developer_mode", 'CHECKBOX_HLT' if dev
                        else 'CHECKBOX_DEHLT'))


def draw_model_engine(layout, context, st):
    """MODEL IMPORTER. The switch is a preference (it outlives the .blend); the session's Textures choice is drawn
    here too, beside the switch it works with."""
    from .Panel import fold_section
    from ..core import model_engine, paths as _p
    box, _head = fold_section(layout, st, "sec_model_engine", "Model Importer",
                              _icon_id("import_mdl", 'MESH_DATA'))
    if box is None:
        return
    prefs = _p.addon_prefs()
    col = box.column(align=True)
    if prefs is not None:
        #3.0.0: HoovyTools is the default - SourceIO only when you pick it here (maps still go through SourceIO)
        row = col.row(align=True)
        row.scale_y = 1.2
        row.prop(prefs, "model_importer", expand=True)
    else:
        col.label(text="(the add-on's preferences are not reachable here)", icon='ERROR')
    pr = getattr(context.scene, "ht_project", None)
    if pr is not None:
        row = box.row(align=True)
        row.label(text="Textures")
        row.prop(pr, "session_textures", expand=True)
        box.prop(pr, "skip_hidden", icon='HIDE_ON')                     #1.26.0


def draw_misc(layout, context, st):
    """MISC. MDL IMPORT (STANDALONE): the
    embedded importer on its own - with textures, or without them (quick)."""
    from .Panel import fold_section
    box, _head = fold_section(layout, st, "sec_misc", "Misc",
                              _icon_id("utils_misc", 'TOOL_SETTINGS'))
    if box is None:
        return
    sub, _h = fold_section(box, st, "sec_mdl_embedded", "MDL Import (Standalone)",
                           _icon_id("import_mdl", 'MESH_DATA'))
    if sub is None:
        return
    from ..importers import Import_MDL as _imdl
    have = _imdl.sourceio_ready()
    note = sub.column(align=True)
    note.enabled = False
    note.label(text="SourceIO: installed - Import Model uses it" if have
               else "SourceIO: not installed - Import Model uses this")
    note.label(text="SourceIO's own code, carried inside SFM Session Importer")
    col = sub.column(align=True)
    op = col.operator("ht.import_mdl_embedded", text="Import MDL",
                      **_icon_id("import_mdl", 'MESH_DATA'))
    op.import_textures = True
    op = col.operator("ht.import_mdl_embedded", text="Import MDL - No Textures (Quick)",
                      icon='MESH_MONKEY')
    op.import_textures = False


def draw_behavior(layout, context, st):
    """BEHAVIOR REPORT - below Wiring. PRINT HELP is the
    button to press; Logs is folded inside it."""
    from .Panel import fold_section
    from ..core import Report_UI as _RUI
    dev = bool(getattr(st, "developer_mode", False))
    box, _head = fold_section(layout, st, "sec_behavior", "Behavior Report",
                              _icon_id("print_behavior", 'FILE_TEXT'))
    if box is None:
        return
    from .. import bl_info
    ver = box.row()
    ver.alignment = 'CENTER'
    ver.label(text="SFM Session Importer %s" % ".".join(str(v) for v in bl_info["version"]),
              **_icon_id("hoovy_logo", 'INFO'))
    run = box.column(align=True)
    run.scale_y = 1.6
    run.operator("ht.print_help", text="PRINT HELP",
                 **_icon_id("print_behavior", 'HELP'))
    row = box.row(align=True)
    row.operator("ht.dev_log_report", text="Print Addon Behavior",
                 **_icon_id("print_paths", 'FILE_TEXT'))
    row.operator("ht.dev_open_log_folder", text="",
                 **_icon_id("log_folder", 'FILE_FOLDER'))

    lp = _RUI.log_prefs(context)
    lbox, lhead = fold_section(box, st, "sec_logs", "Logs",
                               _icon_id("logs_section", 'TEXT'))
    if lbox is None:
        return
    row = lbox.row(align=True)
    row.operator("ht.logs_all", text="All On",
                 **_icon_id("log_on", 'CHECKMARK')).value = True
    row.operator("ht.logs_all", text="All Off",
                 **_icon_id("log_off", 'X')).value = False
    if lp is None:
        lbox.label(text="Unavailable - re-enable the addon.", icon='ERROR')
    else:
        grid = lbox.grid_flow(row_major=True, columns=2, even_columns=True,
                              align=True)
        for key, label, _desc in _RUI.REPORTS:
            grid.prop(lp, key, text=label)
    if dev:
        sub = lbox.column(align=True)
        sub.scale_y = 0.85
        row = sub.row(align=True)
        row.operator("ht.dev_debug_paths", text="Print Paths",
                     **_icon_id("dev_folders", 'FILE_FOLDER'))
        row.operator("ht.dev_dump_roadmap", text="Print Roadmap",
                     **_icon_id("dev_config", 'COPYDOWN'))
        row = sub.row(align=True)
        row.operator("ht.dev_console_success", text="Success",
                     **_icon_id("print_success", 'CHECKMARK'))
        row.operator("ht.dev_console_error", text="Error",
                     **_icon_id("print_error", 'ERROR'))


def draw_popups(layout, context, st):
    """POPUPS - DISABLE ALL, and every popup's own switch folded below it. The master switch keeps the individual choices."""
    from .Panel import fold_section
    from ..core import Report_UI as _RUI
    from ..core import popups as _popups
    p = _RUI.prefs(context)
    box, head = fold_section(layout, st, "sec_popups", "Popups",
                             _icon_id("sec_popups", 'INFO'))
    if head is not None:
        state = head.row()
        state.alignment = 'RIGHT'
        state.enabled = False
        if p is not None and getattr(p, _RUI.MASTER_KEY, False):
            state.label(text="all off")
        elif p is not None:
            n_off = sum(1 for k in _RUI._KEYS if not getattr(p, k, True))
            state.label(text=(f"{n_off} off" if n_off else "all on"))
    if box is None:
        return
    if p is None:
        box.label(text="Unavailable - re-enable the addon.", icon='ERROR')
        return
    off = bool(getattr(p, _RUI.MASTER_KEY, False))
    row = box.row(align=True)
    row.scale_y = 1.2
    row.prop(p, _RUI.MASTER_KEY, text="Disable All Popups", toggle=True,
             icon=('HIDE_ON' if off else 'HIDE_OFF'))
    store = _popups.store_path()
    draw_row_button(row, store.is_file(), store.parent)
    lst, _h = fold_section(box, st, "sec_popup_list", "Individual Popups",
                           _icon_id("sec_popups", 'INFO'))
    if lst is None:
        return
    lst.enabled = not off
    row = lst.row(align=True)
    row.operator("ht.reports_all", text="All On",
                 **_icon_id("log_on", 'CHECKMARK')).value = True
    row.operator("ht.reports_all", text="All Off",
                 **_icon_id("log_off", 'X')).value = False
    grid = lst.grid_flow(row_major=True, columns=2, even_columns=True,
                         align=True)
    for key, label, _desc in _RUI.REPORTS:
        grid.prop(p, key, text=label)


def draw_framerate_section(layout, context, st):
    """The Frame Rate box - inside Configure since 1.18.0, and drawn nowhere
    else, so it lives here rather than in Panel.py. The rate matches
    AUTOMATICALLY when a session connects, so this is the readout, the off
    switch, the manual fix for the day the switch is off, and the report."""
    from .Panel import fold_section
    from ..session import FPS_Safety as _FPS
    from ..session import Session_Paths as _SP
    pr = _SP.project(context)
    box, _head = fold_section(layout, st, "sec_framerate", "Frame Rate",
                              _icon_id("sec_framerate", 'TIME'))
    if box is None:
        return
    box.prop(st, "auto_fps")
    grid = box.column(align=True)
    grid.scale_y = 0.95
    sfm = (pr.session_fps if (pr is not None and pr.session_fps)
           else (pr.anim_fps if (pr is not None and pr.anim_fps) else None))
    blender = f"{_FPS.scene_fps(context.scene):g}"
    row = grid.row(align=True)
    row.label(text="FPS SFM:")
    row.label(text=sfm or "unknown")
    row = grid.row(align=True)
    row.label(text="FPS BLENDER:")
    row.label(text=blender)
    if sfm and sfm != blender:
        warn = box.column(align=True)
        warn.alert = True
        warn.label(text="Rates differ - fix before importing.", icon='ERROR')
        try:
            box.operator("ht.set_scene_fps", text=f"Set Blender to {sfm} fps",
                         icon='TIME').fps = float(sfm)
        except ValueError:
            pass
    box.operator("ht.fps_report", text="Frame Rate Report",
                 **_icon_id("fps_report", 'TIME'))


def draw_configure(layout, context, st):
    """CONFIGURE - how the add-on behaves."""
    from .Panel import fold_section
    box, _head = fold_section(layout, st, "sec_configure", "Configure",
                              _icon_id("dev_config", 'PREFERENCES'))
    if box is None:
        return
    try:
        from ..session import Session_Paths as _SP
        pr = _SP.project(context)
    except Exception:                                         # noqa: BLE001
        pr = None

    # ── LAYOUTS, the first thing ─────────────────────────────────────────
    sub, _h = fold_section(box, st, "sec_layouts", "Layouts",
                           _icon_id("layout_two", 'WORKSPACE'))
    if sub is not None:
        col = sub.column(align=True)
        col.scale_y = 1.2
        row = col.row(align=True)
        for key, text, ikey in (('DEFAULT', "Default", "layout_default"),
                                ('TWO', "Two Screen", "layout_two"),
                                ('THREE', "Three Screen", "layout_three")):
            row.operator("ht.build_layout", text=text,
                         **_icon_id(ikey, 'WORKSPACE')).layout_key = key
        row = col.row(align=True)
        for key, text, ikey in (('DEFAULT', "Default", "engine_default"),
                                ('EEVEE', "EEVEE", "engine_eevee"),
                                ('CYCLES', "Cycles", "engine_cycles")):
            row.operator("ht.engine_preset", text=text,
                         **_icon_id(ikey, 'SHADING_RENDERED')).preset = key
        sub.prop(st, "layout_after_import")
        sub.prop(st, "render_after_import")
        rp, _h2 = fold_section(sub, st, "sec_render_presets", "Render Presets",
                               _icon_id("render_presets", 'OUTPUT'))
        if rp is not None:
            c = rp.column(align=True)
            row = c.row(align=True)
            row.operator("ht.render_preset", text="Cheap EEVEE",
                         icon='RESTRICT_RENDER_OFF').preset = "CHEAP_EEVEE"
            row.operator("ht.render_preset", text="Expensive EEVEE",
                         icon='SHADING_RENDERED').preset = "EXPENSIVE_EEVEE"
            row = c.row(align=True)
            row.operator("ht.render_preset", text="Cheap Cycles",
                         icon='RESTRICT_RENDER_OFF').preset = "CHEAP_CYCLES"
            row.operator("ht.render_preset", text="Expensive Cycles",
                         icon='SHADING_RENDERED').preset = "EXPENSIVE_CYCLES"

    # ── POPUPS ───────────────────────────────────────────────────────────
    draw_popups(box, context, st)

    # ── anims folder ─────────────────────────────────────────────────────
    sub, _h = fold_section(box, st, "sec_anims_folder", "Anims Folder",
                           _icon_id("anims_folder", 'FILE_FOLDER'))
    if sub is not None:
        if pr is None:
            sub.label(text="Unavailable - re-enable the addon.", icon='ERROR')
        else:
            on = bool(getattr(pr, "unpack_anims", False))
            row = sub.row(align=True)
            row.scale_y = 1.2
            row.prop(pr, "unpack_anims", text="Create Anims Folders",
                     icon=('FILE_FOLDER' if on else 'TRASH'), toggle=True)

    # ── shot timing ──────────────────────────────────────────────────────
    sub, _h = fold_section(box, st, "sec_shot_timing", "Shot Timing",
                           _icon_id("shot_timing", 'TIME'))
    if sub is not None:
        if pr is None:
            sub.label(text="Unavailable - re-enable the addon.", icon='ERROR')
        else:
            row = sub.row(align=True)
            row.scale_y = 1.2
            row.prop(pr, "shot_timing", expand=True)

    #── frame rate ───────────────────────────────────────────────────────
    draw_framerate_section(box, context, st)

    # ── SESSION AUTOMATION ───────────────────────────────────────────────
    sub, _h = fold_section(box, st, "sec_autosplit", "Session Automation",
                           _icon_id("auto_split_camera", 'CON_CAMERASOLVER'))
    if sub is not None:
        col = sub.column(align=True)
        col.prop(st, "auto_split_hoovy_camera",
                 **_icon_id("auto_split_camera", 'CON_CAMERASOLVER'))
        col.prop(st, "auto_split_match", text="Name contains")
        run = sub.column(align=True)
        run.scale_y = 1.2
        run.operator("ht.split_matching_cameras",
                     text="Split Matching Cameras Now",
                     **_icon_id("auto_split_run", 'CON_CAMERASOLVER'))


_CREDITS = (
    # (name, license, url, lines under it) - short lines, the sidebar is narrow
    ("Blender Source Tools", "GPL v2+",
     "https://github.com/Artfunkel/BlenderSourceTools",
     ("Artfunkel (Tom Edwards)", "with lasa01 (Lassi Säike), suXinjke",
      "bundled as SST - the DMX reader")),
    ("datamodel.py", "MIT",
     "https://github.com/Artfunkel/BlenderSourceTools/blob/master/"
     "io_scene_valvesource/datamodel.py",
     ("Artfunkel (Tom Edwards)",)),
    ("SourceIO", "MIT", "https://github.com/REDxEYE/SourceIO",
     ("REDxEYE",)),
)

LINKS = {
    "patreon": ("Patreon", 'FUND', "https://www.patreon.com/HoovyTube",
                "HoovyTube on Patreon"),
    "website": ("Website", 'WORLD', "https://hoovytube.com",
                "HoovyTube's website"),
    "github": ("GitHub", 'URL', "https://github.com/hoovytubeofficial/HoovyTools-SFMSessionImport-Blender",
               "The source of truth: the newest version of SFM Session Importer, its code and its changes"),
}


def license_path():
    """The add-on's LICENSE.txt."""
    return Path(__file__).resolve().parent.parent / "LICENSE.txt"


class HT_OT_open_link(Operator):
    """Open HoovyTube's page"""
    bl_idname = "ht.open_link"
    bl_label = "Open Link"
    bl_options = {'INTERNAL'}

    which: EnumProperty(  # type: ignore
        items=[(k, v[0], v[3]) for k, v in LINKS.items()], options={'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        name, _icon, url, desc = LINKS[properties.which]
        return "%s\n%s\n\nTHIS FEATURE WAS ADDED IN VERSION 3.0.0 AND IS IN EXPERIMENTAL STAGE" % (desc, url)

    def execute(self, context):
        bpy.ops.wm.url_open(url=LINKS[self.which][2])
        return {"FINISHED"}


def draw_credits(layout, context, st):
    """CREDITS - who made it, where to find them, the license, and the work it stands on."""
    from .Panel import fold_section
    box, _head = fold_section(layout, st, "sec_credits", "Credits",
                              _icon_id("hoovy_logo", 'HEART'))
    if box is None:
        return
    box.label(text="Made by HoovyTube", **_icon_id("hoovy_logo", 'HEART'))
    links = box.row(align=True)
    for key, (text, icon, _url, _desc) in LINKS.items():
        links.operator("ht.open_link", text=text, icon=icon).which = key
    row = box.row(align=True)
    note = row.row()
    note.enabled = False
    note.label(text="Free for everyone")
    lic = license_path()
    btn = row.row(align=True)
    btn.ui_units_x = 4.5
    btn.enabled = lic.is_file()
    btn.operator("wm.path_open", text="License", icon='TEXT').filepath = str(lic)
    for name, kind, url, under in _CREDITS:
        col = box.column(align=True)
        row = col.row(align=True)
        row.label(text=f"{name}  ({kind})")
        row.operator("wm.url_open", text="", icon='URL').url = url
        for ln in under:
            sub = col.row()
            sub.enabled = False
            sub.label(text=ln)


# ─────────────────────────────────────────────────────────────────────────────
# Menus
# ─────────────────────────────────────────────────────────────────────────────

class HT_MT_roadmap_submenu(Menu):
    """The numbered priorities list, hoverable"""
    bl_idname = "HT_MT_roadmap_submenu"
    bl_label = "Roadmap / Priorities"

    def draw(self, context):
        layout = self.layout
        for key, label, _desc, icon in TIERS:
            d, t = counts(key)
            layout.separator()
            layout.label(text=f"{label}   {d}/{t}", icon=icon)
            for p in tier_items(key):
                layout.operator("ht.priority_info",
                                text=f"{p['n']}.  {p['title']}",
                                icon=STATUS_ICON[p["status"]]).index = p["n"]
        layout.separator()
        layout.operator("ht.dev_dump_roadmap", text="Print Roadmap",
                        **_icon_id("print_roadmap", 'COPYDOWN'))


class HT_MT_developer_submenu(Menu):
    """The workshop - every component on its own, plus diagnostics"""
    bl_idname = "HT_MT_developer_submenu"
    bl_label = "Developer"

    def draw(self, context):
        layout = self.layout

        layout.menu(HT_MT_roadmap_submenu.bl_idname, icon='PRESET')
        layout.separator()

        layout.operator("ht.analyze_dmx", text="Analyze DMX",
                        **_icon_id("analyze_dmx", 'VIEWZOOM'))
        layout.separator()

        layout.operator("ht.session_one_click", text="Import Whole Session",
                        **_icon_id("import_session", 'PLAY'))
        layout.operator("ht.session_report", text="Read Session",
                        **_icon_id("session_report", 'VIEWZOOM'))
        layout.operator("ht.session_shots", text="List Shots",
                        **_icon_id("shots", 'SEQUENCE'))
        layout.operator("ht.session_extract",
                        text="Extract Animations From Session",
                        **_icon_id("session_animations", 'ANIM'))
        layout.operator("ht.session_plan", text="Plan Session Import",
                        icon='VIEWZOOM')
        layout.operator("ht.session_import_all",
                        text="Import Session Animations",
                        **_icon_id("session_animations", 'ANIM'))
        layout.separator()

        layout.operator("ht.import_dmx_animation", text="Import Animation",
                        **_icon_id("import_dmx_anim", 'ACTION'))
        layout.operator("ht.import_dmx_camera", text="Import Camera",
                        **_icon_id("import_dmx_camera", 'CAMERA_DATA'))
        layout.operator("ht.import_shape_keys", text="Import Shape Keys",
                        **_icon_id("import_shape_keys", 'SHAPEKEY_DATA'))
        layout.separator()

        layout.operator("ht.split_camera_cuts", text="Split Camera",
                        **_icon_id("split_camera", 'SEQUENCE'))
        layout.operator("ht.camera_handles",
                        text="Camera Pre / Post Handles", icon='IPO_BEZIER')
        layout.operator("ht.camera_shot_report", text="Camera Shot Report",
                        icon='INFO')
        layout.operator("ht.shapekey_proxy",
                        text="Generate Shape Key Proxy",
                        **_icon_id("shapekey_proxy", 'MESH_CUBE'))
        layout.operator("ht.register_skydome", text="Register Skydome",
                        **_icon_id("register_skydome", 'WORLD'))
        layout.separator()

        layout.operator("ht.import_lights",
                        text="Experimental Light Import",
                        **_icon_id("import_lights_one", 'LIGHT_POINT'))
        layout.operator("ht.mdl_sequences", text="MDL Sequence Report",
                        **_icon_id("mdl_sequences", 'ACTION'))
        layout.separator()

        layout.operator("ht.dev_log_report", text="Print Addon Behavior",
                        **_icon_id("print_behavior", 'FILE_TEXT'))
        layout.operator("ht.dev_open_log_folder", text="Open Log Folder",
                        icon='FILE_FOLDER')
        layout.separator()
        layout.operator("ht.dev_console_success",
                        text="Print Success Message",
                        **_icon_id("print_success", 'CHECKMARK'))
        layout.operator("ht.dev_console_error",
                        text="Print Error Message",
                        **_icon_id("print_error", 'ERROR'))
        layout.separator()
        layout.operator("ht.fps_report", text="FPS Report",
                        **_icon_id("fps_report", 'TIME'))
        layout.operator("ht.dev_debug_paths", text="Print Resolved Paths",
                        **_icon_id("print_paths", 'FILE_FOLDER'))
        layout.operator("ht.dev_dump_roadmap", text="Print Roadmap",
                        **_icon_id("print_roadmap", 'COPYDOWN'))


def draw_developer_entry(layout):
    """Called from HT_MT_import_submenu."""
    layout.menu(HT_MT_developer_submenu.bl_idname, **_icon_id("utils_misc", 'CONSOLE'))


# ─────────────────────────────────────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────────────────────────────────────

_CLASSES = (
    HT_OT_register_skydome,
    HT_OT_render_preset,
    HT_OT_priority_info,
    HT_OT_dev_stub,
    HT_OT_dev_console_success,
    HT_OT_dev_console_error,
    HT_OT_dev_dump_roadmap,
    HT_OT_dev_debug_paths,
    HT_MT_roadmap_submenu,
    HT_MT_developer_submenu,
    HT_OT_dev_recheck_wiring,
    HT_OT_dev_log_report,
    HT_OT_print_help,
    HT_OT_dev_open_log_folder,
    HT_OT_set_search_folder,
    HT_OT_clear_search_folder,
    HT_OT_open_search_folder,
    HT_OT_open_user_paths_json,
    HT_OT_enable_addon,
    HT_OT_paste_search_folder,
    HT_OT_make_custom_config,
    HT_OT_open_config,
    HT_OT_open_my_config,
    HT_OT_open_link,
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
