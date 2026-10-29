# ═════════════════════════════════════════════════════════════════════════════
# DEPENDENCIES
# bpy                            the scene, its actions, sequencer, markers
# numpy                          ships with Blender - keys moved in bulk
# core/anim_compat.py            layered (5.x) and legacy actions alike
# Drawn by ui/Panel.py, Tools tab > Cleanup. Added in 1.17.0
# ═════════════════════════════════════════════════════════════════════════════
"""
Scene_Offset - OFFSET EVERYTHING: the whole scene moves in time, together.

WHAT MOVES, AND WHY ALL OF IT
-----------------------------
Moving only the keys is the classic half-job: the sound stays behind, the
frame range now frames nothing, the camera splitter's shot bounds point at the
old cut. So one delta goes to everything that holds a FRAME NUMBER:

    keys          every f-curve of every action the scene uses - objects,
                  their data (camera lens, light energy), shape keys,
                  materials and node trees, the world, the scene - key and
                  both handles, plus restricted-range f-modifiers. Actions
                  NOTHING uses move too (parked takes stay in step).
                  Whole File: every action in the .blend.
    NLA           each strip's placement AND its action range, so a strip
                  keeps playing the same keys it played before.
    sequencer     every top-level strip (sounds, movies) - effect strips
                  follow their inputs.
    markers       timeline markers.
    the scene     frame_start / frame_end, the playhead, the preview range.
    particles     emission frame_start / frame_end of the scene's particle
                  settings.
    shot bounds   `ht_shot_bounds` on the camera importer's root empties
                  (the camera splitter reads them).

Not moved, and reported: drivers whose expression reads `frame` (they compute
from the clock, there is nothing to shift).

FRAME 0. Blender cannot start a scene below frame 0, so a delta that would
push frame_start negative clamps the RANGE (and says so) while the keys still
move by the full amount - nothing is lost, it is just outside the range.
"""

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty

from ..core import anim_compat

try:
    import numpy as _np
except Exception:                                             # noqa: BLE001
    _np = None


# ─────────────────────────────────────────────────────────────────────────────
# What holds animation
# ─────────────────────────────────────────────────────────────────────────────

def _ad_owners(scene):
    """Every ID this scene reaches that can carry animation_data."""
    seen = set()
    out = []

    def add(idb):
        if idb is None or id(idb) in seen:
            return
        if getattr(idb, "animation_data", None) is None and \
                not hasattr(idb, "animation_data"):
            return
        seen.add(id(idb))
        out.append(idb)

    add(scene)
    world = getattr(scene, "world", None)
    add(world)
    add(getattr(world, "node_tree", None))
    for ob in scene.objects:
        add(ob)
        data = getattr(ob, "data", None)
        add(data)
        add(getattr(data, "shape_keys", None))
        add(getattr(data, "node_tree", None))          #lights' shader trees
        for slot in getattr(ob, "material_slots", []):
            mat = slot.material
            add(mat)
            add(getattr(mat, "node_tree", None))
        for ps in getattr(ob, "particle_systems", []):
            add(ps.settings)
    return out


def _actions_of(owners):
    """{action pointer: action} used by these owners - active and NLA."""
    acts = {}
    for idb in owners:
        ad = getattr(idb, "animation_data", None)
        if ad is None:
            continue
        if ad.action is not None:
            acts[ad.action.as_pointer()] = ad.action
        for tr in ad.nla_tracks:
            for st in tr.strips:
                if st.action is not None:
                    acts[st.action.as_pointer()] = st.action
    return acts


def _other_scene_actions(scene):
    out = set()
    for sc in bpy.data.scenes:
        if sc == scene:
            continue
        out.update(_actions_of(_ad_owners(sc)).keys())
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Moving
# ─────────────────────────────────────────────────────────────────────────────

def _shift_fcurve(fc, d):
    kps = fc.keyframe_points
    n = len(kps)
    if n:
        if _np is not None:
            for prop in ("co", "handle_left", "handle_right"):
                buf = _np.empty(2 * n, dtype=_np.float32)
                kps.foreach_get(prop, buf)
                buf[0::2] += d
                kps.foreach_set(prop, buf)
        else:
            for kp in kps:
                kp.co.x += d
                kp.handle_left.x += d
                kp.handle_right.x += d
    mods = 0
    for m in fc.modifiers:
        if getattr(m, "use_restricted_range", False):
            m.frame_start += d
            m.frame_end += d
            mods += 1
    fc.update()
    return n, mods


def _shift_nla(owners, d):
    """Move every strip and its action range by d; returns strips moved."""
    moved = 0
    for idb in owners:
        ad = getattr(idb, "animation_data", None)
        if ad is None:
            continue
        for tr in ad.nla_tracks:
            # later strips first when moving later (and earlier first when
            # moving earlier), so no strip is ever pushed into its neighbour
            strips = sorted(tr.strips, key=lambda s: s.frame_start, reverse=d > 0)
            for st in strips:
                length = st.frame_end - st.frame_start
                # frame_start_ui MOVES a strip (3.3+); frame_start alone
                # would resize it.
                if hasattr(st, "frame_start_ui"):
                    st.frame_start_ui = st.frame_start_ui + d
                elif d > 0:
                    st.frame_end = st.frame_end + d
                    st.frame_start = st.frame_start + d
                else:
                    st.frame_start = st.frame_start + d
                    st.frame_end = st.frame_end + d
                if st.action is not None:
                    #the keys inside moved by d as well - keep the window on
                    #the same keys (end first when moving later, so the
                    #window never turns inside out).
                    if d > 0:
                        st.action_frame_end = st.action_frame_end + d
                        st.action_frame_start = st.action_frame_start + d
                    else:
                        st.action_frame_start = st.action_frame_start + d
                        st.action_frame_end = st.action_frame_end + d
                if abs((st.frame_end - st.frame_start) - length) > 1e-3:
                    st.frame_end = st.frame_start + length
                moved += 1
    return moved


def _top_strips(scene):
    se = scene.sequence_editor
    if se is None:
        return []
    # 5.x renamed `sequences` to `strips`; an EMPTY collection is falsy, so
    # pick by attribute, never with `or`
    return list(se.strips if hasattr(se, "strips") else getattr(se, "sequences", []))


def _shift_sequencer(scene, d):
    moved = 0
    strips = [s for s in _top_strips(scene) if getattr(s, "input_1", None) is None]
    strips.sort(key=lambda s: s.frame_start, reverse=d > 0)
    for st in strips:
        try:
            st.frame_start = st.frame_start + d
            moved += 1
        except Exception:                                     # noqa: BLE001
            pass
    return moved


def offset_everything(scene, delta, whole_file=False):
    """Move everything in `scene` that holds a frame number by `delta` frames.
    Returns a report dict."""
    d = int(delta)
    r = {"delta": d, "actions": 0, "fcurves": 0, "keys": 0, "fmodifiers": 0,
         "nla_strips": 0, "sequencer_strips": 0, "markers": 0, "particles": 0,
         "shot_bounds": 0, "frame_drivers": [], "range_before": (scene.frame_start, scene.frame_end),
         "range_after": None, "clamped": False}
    if d == 0:
        r["range_after"] = r["range_before"]
        return r

    owners = _ad_owners(scene)
    acts = _actions_of(owners)
    if whole_file:
        for a in bpy.data.actions:
            acts.setdefault(a.as_pointer(), a)
    else:
        # Parked takes - actions nothing (or only their fake user) holds -
        # travel with the scene; an action another SCENE uses does not
        others = _other_scene_actions(scene)
        for a in bpy.data.actions:
            if a.as_pointer() in acts or a.as_pointer() in others:
                continue
            if a.users <= (1 if a.use_fake_user else 0):
                acts[a.as_pointer()] = a

    for a in acts.values():
        r["actions"] += 1
        for fc in anim_compat.iter_fcurves(a):
            n, mods = _shift_fcurve(fc, d)
            r["fcurves"] += 1
            r["keys"] += n
            r["fmodifiers"] += mods

    r["nla_strips"] = _shift_nla(owners, d)
    r["sequencer_strips"] = _shift_sequencer(scene, d)

    for m in scene.timeline_markers:
        m.frame = m.frame + d
        r["markers"] += 1

    for idb in owners:
        if isinstance(idb, bpy.types.ParticleSettings):
            idb.frame_end = idb.frame_end + d
            idb.frame_start = idb.frame_start + d
            r["particles"] += 1
        ad = getattr(idb, "animation_data", None)
        if ad is not None:
            for drv in ad.drivers:
                expr = getattr(drv.driver, "expression", "") or ""
                if "frame" in expr:
                    r["frame_drivers"].append(f"{idb.name}: {drv.data_path}")

    for ob in scene.objects:
        if "ht_shot_bounds" in ob.keys():
            try:
                ob["ht_shot_bounds"] = [float(v) + d for v in ob["ht_shot_bounds"]]
                r["shot_bounds"] += 1
            except Exception:                                 # noqa: BLE001
                pass

    # THE RANGE last, and in the safe order: Blender refuses an end before
    # the start, and clamps a start below 0
    s0, e0 = scene.frame_start, scene.frame_end
    want_s, want_e = s0 + d, e0 + d
    if d > 0:
        scene.frame_end = want_e
        scene.frame_start = want_s
    else:
        scene.frame_start = max(0, want_s)
        scene.frame_end = max(scene.frame_start + 1, want_e)
    r["clamped"] = scene.frame_start != want_s
    if getattr(scene, "use_preview_range", False):
        if d > 0:
            scene.frame_preview_end = scene.frame_preview_end + d
            scene.frame_preview_start = scene.frame_preview_start + d
        else:
            scene.frame_preview_start = max(0, scene.frame_preview_start + d)
            scene.frame_preview_end = max(scene.frame_preview_start + 1,
                                          scene.frame_preview_end + d)
    try:
        scene.frame_set(max(0, scene.frame_current + d))
    except Exception:                                         # noqa: BLE001
        pass
    r["range_after"] = (scene.frame_start, scene.frame_end)
    return r


def report_lines(r):
    L = [f"Offset   : {r['delta']:+d} frame(s)",
         f"Range    : {r['range_before'][0]}-{r['range_before'][1]} -> "
         f"{r['range_after'][0]}-{r['range_after'][1]}"
         + ("  (clamped at 0 - Blender cannot start below frame 0)" if r["clamped"] else ""),
         f"Keys     : {r['keys']} on {r['fcurves']} f-curve(s) in {r['actions']} action(s)"]
    if r["nla_strips"]:
        L.append(f"NLA      : {r['nla_strips']} strip(s)")
    L.append(f"Sequencer: {r['sequencer_strips']} strip(s)")
    L.append(f"Markers  : {r['markers']}")
    if r["particles"]:
        L.append(f"Particles: {r['particles']} emission range(s)")
    if r["shot_bounds"]:
        L.append(f"Shot bounds: {r['shot_bounds']} camera(s)")
    if r["frame_drivers"]:
        L.append(f"NOT moved: {len(r['frame_drivers'])} driver(s) reading `frame` - "
                 + ", ".join(r["frame_drivers"][:4]))
    return L


# ─────────────────────────────────────────────────────────────────────────────
# The operator
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_offset_everything(bpy.types.Operator):
    """Move the whole scene in time - every key, sound, marker and the frame range together

Start At Frame: the scene's range starts on the frame you type (0 puts the shot at the start of the timeline).
By Frames: everything moves that many frames (negative = earlier).

Keys of every action the scene uses (objects, their data, shape keys, materials, node trees, the world) move,
and so do the NLA strips playing them, the sequencer strips (sounds), the timeline markers, the frame range and
playhead, particle emission ranges and the camera importer's shot bounds - so nothing drifts apart. Actions
nothing uses move too; Whole File moves every action in the .blend.

HOW: Tools > Cleanup > Offset Everything, pick a mode, type the frame, OK. Ctrl+Z undoes it.

THIS FEATURE WAS ADDED IN VERSION 1.17.0 AND IS IN EXPERIMENTAL STAGE"""
    bl_idname = "ht.offset_everything"
    bl_label = "Offset Everything"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(  # type: ignore
        name="Mode",
        items=[("TO", "Start At Frame", "Move everything so the scene's frame range starts on this frame"),
               ("BY", "By Frames", "Move everything by this many frames (negative = earlier)")],
        default="TO")
    to_frame: IntProperty(  # type: ignore
        name="Start At Frame", default=0, min=0,
        description="The frame the scene's range starts on afterwards")
    by_frames: IntProperty(  # type: ignore
        name="By Frames", default=0,
        description="How many frames everything moves - negative moves it earlier")
    whole_file: BoolProperty(  # type: ignore
        name="Whole File", default=False,
        description="Move EVERY action in the .blend, including ones another scene uses. Off: this scene's "
                    "actions and the ones nothing uses")

    def invoke(self, context, event):
        self.to_frame = 0
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        col = self.layout.column()
        col.row(align=True).prop(self, "mode", expand=True)
        if self.mode == "TO":
            col.prop(self, "to_frame")
            d = self.to_frame - context.scene.frame_start
        else:
            col.prop(self, "by_frames")
            d = self.by_frames
        col.prop(self, "whole_file")
        sc = context.scene
        hint = col.row()
        hint.enabled = False
        hint.label(text=f"{sc.frame_start}-{sc.frame_end} -> {sc.frame_start + d}-{sc.frame_end + d}  "
                        f"({d:+d})")

    def execute(self, context):
        sc = context.scene
        d = (self.to_frame - sc.frame_start) if self.mode == "TO" else self.by_frames
        r = offset_everything(sc, d, whole_file=self.whole_file)
        for line in report_lines(r):
            print(f"[OFFSET]  {line}")
        self.report({"WARNING"} if r["clamped"] else {"INFO"},
                    f"Moved {d:+d}: {r['keys']} keys, {r['sequencer_strips']} strip(s), {r['markers']} marker(s); "
                    f"range {r['range_after'][0]}-{r['range_after'][1]}"
                    + (" (clamped at 0)" if r["clamped"] else ""))
        return {"FINISHED"}


def register():
    bpy.utils.register_class(HT_OT_offset_everything)


def unregister():
    bpy.utils.unregister_class(HT_OT_offset_everything)
