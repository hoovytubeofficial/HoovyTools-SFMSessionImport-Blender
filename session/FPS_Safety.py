"""
FPS_Safety.py  -  part of HoovyTools                [roadmap #5]
================================================================

The problem this solves is simple: nobody should import a whole animation
authored at one framerate, and only discover it later.

    SOURCE FPS    what the DMX says its clip runs at
    BLENDER FPS   what this scene is set to

Both are shown side by side. Matching is green. A mismatch is raised BEFORE
any animation is imported, with three explicit ways out:

    SET BLENDER FPS TO SOURCE     change the scene, keep the keys
    RESCALE ANIMATION TO SOURCE   keep the scene, move the keys
    IMPORT ANYWAY                 you know what you are doing

No FPS change ever happens silently. Every operator here is button-driven
and says in its report exactly what it did.

WHERE SOURCE FPS COMES FROM
===========================
DMX_Analyzer reads clip.frameRate on a deep pass. Sessions never get a deep
pass (a 2.4 MB session takes ~55 s to load), so a session reports no FPS -
and that is fine, because what actually gets imported is the exported
animation files, and those are cheap to read. check_folder() samples them.

Corpus reality (5084 files): 24 and 30 both occur, sometimes inside one
project. SFM's own timeline is 24 fps, so 24 is the common case and 30 is
the one that quietly ruins a shot.

BLENDER'S FPS IS A FRACTION
===========================
scene.render.fps is an int and scene.render.fps_base a float; the real rate
is fps / fps_base. NTSC rates live entirely in fps_base (30000/1001 is
fps=30000, fps_base=1001). set_scene_fps() writes the exact pair for the
standard rates instead of rounding 29.97 to 30.
"""

import bpy
from bpy.types import Operator
from bpy.props import FloatProperty, StringProperty, BoolProperty


# Two rates count as the same if they are closer than this. Chosen so that
# 29.97 and 30 stay DIFFERENT - they are, and conflating them is the bug.
FPS_EPSILON = 0.01

# Exact (fps, fps_base) pairs, so NTSC rates round-trip.
_EXACT = {
    23.976: (24000, 1001.0),
    24.0:   (24, 1.0),
    25.0:   (25, 1.0),
    29.97:  (30000, 1001.0),
    30.0:   (30, 1.0),
    48.0:   (48, 1.0),
    50.0:   (50, 1.0),
    59.94:  (60000, 1001.0),
    60.0:   (60, 1.0),
    120.0:  (120, 1.0),
}


def scene_fps(scene=None):
    """The scene's real frame rate as a float."""
    scene = scene or bpy.context.scene
    base = scene.render.fps_base or 1.0
    return scene.render.fps / base


def matches(source_fps, blender_fps):
    if source_fps is None or blender_fps is None:
        return False
    return abs(float(source_fps) - float(blender_fps)) < FPS_EPSILON


def set_scene_fps(scene, fps):
    """
    Write an exact fps / fps_base pair. Returns (fps_int, fps_base).

    Nearest standard rate wins when the value is within FPS_EPSILON of one,
    so 29.969999 becomes the true 30000/1001 rather than a lumpy fraction.
    """
    fps = float(fps)
    for known, (i, b) in _EXACT.items():
        if abs(fps - known) < FPS_EPSILON:
            scene.render.fps = i
            scene.render.fps_base = b
            return i, b
    # Non-standard rate: keep it exactly, as a fraction over 1.
    scene.render.fps = int(round(fps))
    scene.render.fps_base = (int(round(fps))) / fps if fps else 1.0
    return scene.render.fps, scene.render.fps_base


def rescale_factor(source_fps, blender_fps):
    """
    How far every key must move to survive the rate change.

    An animation authored at 30 fps played back on a 24 fps timeline is
    running fast; its keys belong at 24/30 = 0.8 of their frame numbers.
    """
    if not source_fps or not blender_fps:
        return 1.0
    return float(blender_fps) / float(source_fps)


# ─────────────────────────────────────────────────────────────────────────────
#  Status
# ─────────────────────────────────────────────────────────────────────────────

OK = 'OK'
MISMATCH = 'MISMATCH'
UNKNOWN = 'UNKNOWN'
MIXED = 'MIXED'

STATUS_ICON = {
    OK:       'CHECKMARK',
    MISMATCH: 'ERROR',
    UNKNOWN:  'QUESTION',
    MIXED:    'ERROR',
}


def check_file(path, scene=None):
    """
    {status, source_fps, blender_fps, message} for one DMX.

    Deep-reads the file, because FPS is the whole point of asking.
    """
    from ..core import DMX_Analyzer
    scene = scene or bpy.context.scene
    bfps = scene_fps(scene)
    a = DMX_Analyzer.analyze(path, deep="auto")
    sfps = a["fps"]

    if not a["ok"]:
        return {"status": UNKNOWN, "source_fps": None, "blender_fps": bfps,
                "message": a["error"] or "unreadable", "analysis": a}
    if sfps is None:
        why = a["deep_skipped"] or "no frame rate in this file"
        return {"status": UNKNOWN, "source_fps": None, "blender_fps": bfps,
                "message": why, "analysis": a}
    if matches(sfps, bfps):
        return {"status": OK, "source_fps": sfps, "blender_fps": bfps,
                "message": f"both {sfps:g} fps", "analysis": a}
    return {"status": MISMATCH, "source_fps": sfps, "blender_fps": bfps,
            "message": f"source {sfps:g} fps, scene {bfps:g} fps",
            "analysis": a}


def check_folder(folder, scene=None, limit=40):
    """
    Sample a folder of exported animations and report the rate they share.

    MIXED means the folder itself disagrees - that is worth surfacing
    loudly, because no single scene rate can be right for all of it.
    """
    from pathlib import Path
    from ..core import DMX_Analyzer
    scene = scene or bpy.context.scene
    bfps = scene_fps(scene)

    folder = Path(folder) if folder else None
    if not folder or not folder.is_dir():
        return {"status": UNKNOWN, "source_fps": None, "blender_fps": bfps,
                "message": "no animations folder connected", "files": 0,
                "rates": {}}

    rates = {}
    n = 0
    for p in sorted(folder.glob("*.dmx"))[:limit]:
        a = DMX_Analyzer.analyze(p, deep="auto")
        n += 1
        if a["fps"]:
            rates[a["fps"]] = rates.get(a["fps"], 0) + 1

    if not rates:
        return {"status": UNKNOWN, "source_fps": None, "blender_fps": bfps,
                "message": f"no frame rate found in {n} file(s)",
                "files": n, "rates": {}}
    if len(rates) > 1:
        listed = ", ".join(f"{k:g} fps x{v}" for k, v in sorted(rates.items()))
        return {"status": MIXED, "source_fps": None, "blender_fps": bfps,
                "message": f"folder mixes rates: {listed}",
                "files": n, "rates": rates}

    sfps = next(iter(rates))
    if matches(sfps, bfps):
        return {"status": OK, "source_fps": sfps, "blender_fps": bfps,
                "message": f"both {sfps:g} fps", "files": n, "rates": rates}
    return {"status": MISMATCH, "source_fps": sfps, "blender_fps": bfps,
            "message": f"source {sfps:g} fps, scene {bfps:g} fps",
            "files": n, "rates": rates}


# ─────────────────────────────────────────────────────────────────────────────
#  Actions
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_set_scene_fps(Operator):
    """Set this scene's frame rate to the rate the source files were authored at

The cheapest fix for a frame-rate mismatch, and the right one to apply
BEFORE any animation lands - nothing then has to be rescaled afterwards.

A DMX stores key times in seconds and converts them to frames at its own
rate, so matching the scene to the source means every key lands on the
frame SFM meant.

If animation is already imported at the wrong rate, use Rescale Animation
To Scene FPS instead - that moves existing keys rather than changing what
future ones will mean"""
    bl_idname = "ht.set_scene_fps"
    bl_label = "Set Blender FPS To Source"
    bl_options = {"REGISTER", "UNDO"}

    fps: FloatProperty(name="Source FPS", default=24.0, min=1.0, max=1000.0,
                       precision=3)  # type: ignore

    def execute(self, context):
        before = scene_fps(context.scene)
        i, b = set_scene_fps(context.scene, self.fps)
        after = scene_fps(context.scene)
        print(f"[HT_FPS]  scene {before:g} -> {after:g} fps  (fps={i} base={b:g})")
        self.report({"INFO"},
                    f"Scene frame rate {before:g} -> {after:g} fps")
        return {"FINISHED"}


class HT_OT_rescale_action_fps(Operator):
    """Move every keyframe of the selected objects to a different frame rate

For animation that has ALREADY been imported at the wrong rate. It scales
key times so the motion keeps its real-world duration - a 2 second action
stays 2 seconds.

Prefer Set Blender FPS To Source and a re-import when you can: rescaling
moves keys onto fractional frames, and Blender evaluates only whole ones.

Bezier handles move with their keys, so eases survive. Shape key and bone
actions are both handled"""
    bl_idname = "ht.rescale_action_fps"
    bl_label = "Rescale Animation To Scene FPS"
    bl_options = {"REGISTER", "UNDO"}

    source_fps: FloatProperty(name="Source FPS", default=30.0, min=1.0,
                              max=1000.0, precision=3)  # type: ignore
    include_children: BoolProperty(  # type: ignore
        name="Include Children",
        description="Also rescale objects parented under the selection, so a "
                    "camera or rig keeps its root and axis empties in step",
        default=True,
    )

    def execute(self, context):
        from .anim_compat import iter_fcurves
        target = scene_fps(context.scene)
        factor = rescale_factor(self.source_fps, target)
        if abs(factor - 1.0) < 1e-9:
            self.report({"INFO"}, "Rates already match - nothing to rescale")
            return {"CANCELLED"}

        objs = list(context.selected_objects)
        if self.include_children:
            seen = {o.name for o in objs}
            queue = list(objs)
            while queue:
                o = queue.pop()
                for c in o.children:
                    if c.name not in seen:
                        seen.add(c.name)
                        objs.append(c)
                        queue.append(c)
        if not objs:
            self.report({"ERROR"}, "Select something to rescale")
            return {"CANCELLED"}

        actions, curves, keys = set(), 0, 0
        for obj in objs:
            owners = [(obj, obj.animation_data)]
            if obj.type == 'CAMERA' and obj.data:
                owners.append((obj.data, obj.data.animation_data))
            for owner, ad in owners:
                if ad is None or ad.action is None:
                    continue
                act = ad.action
                if act.name in actions:
                    continue
                actions.add(act.name)
                for fc in iter_fcurves(act, owner):
                    for kp in fc.keyframe_points:
                        # Handles move WITH the key, or the curve shape is
                        # destroyed - the same mistake the camera splitter
                        # used to make. [roadmap #9]
                        kp.co[0] *= factor
                        kp.handle_left[0] *= factor
                        kp.handle_right[0] *= factor
                        keys += 1
                    fc.update()
                    curves += 1

        print(f"[HT_FPS]  rescaled x{factor:.6g}: {len(actions)} action(s), "
              f"{curves} curve(s), {keys} key(s)")
        self.report({"INFO"},
                    f"Rescaled x{factor:.6g} - {len(actions)} action(s), "
                    f"{curves} curve(s)")
        return {"FINISHED"}


class HT_OT_fps_report(Operator):
    """Compare the source frame rate against this scene and say what will happen

Reads the connected animations folder when one is set, otherwise reports
the scene rate alone.

WHY IT MATTERS: a DMX's key times are in seconds, converted to frames at
the file's OWN rate. Import a 24 fps take into a 30 fps scene and every
key lands at the wrong frame - the motion still plays, just at the wrong
speed, which is easy to miss until a shot is cut against audio.

a real corpus genuinely MIXES rates - 2,391 files at 24 and 1,915
at 30, sometimes in the same folder - so MIXED is a real answer, not a
fault. When it says MIXED, split the folder or import in two passes"""
    bl_idname = "ht.fps_report"
    bl_label = "FPS Report"

    def execute(self, context):
        try:
            from . import Session_Paths
            folder = Session_Paths.animations_dir(context.scene)
        except Exception:
            folder = None

        if folder:
            r = check_folder(folder, context.scene)
        else:
            r = {"status": UNKNOWN, "source_fps": None,
                 "blender_fps": scene_fps(context.scene),
                 "message": "no session or animations folder connected",
                 "files": 0, "rates": {}}
            try:
                from . import Session_Paths, Session_Reader
                sess = Session_Paths.session_file(context.scene)
                if sess is not None:
                    sfps = float(Session_Reader.read_session(sess)["fps"])
                    bfps = scene_fps(context.scene)
                    same = matches(sfps, bfps)
                    r = {"status": "OK" if same else "MISMATCH",
                         "source_fps": sfps, "blender_fps": bfps,
                         "message": (f"session {sfps:g} fps, scene {bfps:g} fps"
                                     + ("" if same else " - set the scene to "
                                        "the session's rate")),
                         "files": 1, "rates": {sfps: 1}}
            except Exception as exc:                          # noqa: BLE001
                r["message"] = f"session rate unreadable ({exc})"

        print(f"\n[HT_FPS]  status  : {r['status']}")
        print(f"[HT_FPS]  scene   : {r['blender_fps']:g} fps")
        print(f"[HT_FPS]  source  : "
              f"{r['source_fps'] if r['source_fps'] else 'unknown'}")
        print(f"[HT_FPS]  {r['message']}")
        for rate, count in sorted((r.get("rates") or {}).items()):
            print(f"[HT_FPS]    {rate:g} fps in {count} file(s)")

        level = {"OK": "INFO", "MISMATCH": "WARNING",
                 "MIXED": "WARNING", "UNKNOWN": "INFO"}[r["status"]]
        self.report({level}, f"FPS {r['status']}: {r['message']}")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
#  Draw helper - the status block reused by Main and Dev tabs
# ─────────────────────────────────────────────────────────────────────────────

def draw_fps_status(layout, context, result, compact=False):
    """
    SOURCE FPS and BLENDER FPS side by side, then the way out of a mismatch.

    Never mutates. The three actions are operators the user presses.

    DEFENSIVE ON PURPOSE. An exception raised inside a panel draw() does not
    just blank that panel - it takes the console with it, which is exactly
    what an unexpected status string did here once via STATUS_ICON[status].
    So every lookup below tolerates a value it does not recognise and
    degrades to UNKNOWN rather than raising.
    """
    box = layout.box()
    status = result.get("status") or UNKNOWN
    if status not in STATUS_ICON:
        status = UNKNOWN
    head = box.row(align=True)
    head.label(text="Frame Rate", icon=STATUS_ICON.get(status, 'QUESTION'))

    grid = box.row(align=True)
    left = grid.column(align=True)
    right = grid.column(align=True)
    left.scale_y = right.scale_y = 0.9
    left.label(text="Source")
    src = result.get("source_fps")
    left.label(text=f"{src:g} fps" if src else "unknown")
    right.label(text="Blender")
    bfps = result.get("blender_fps") or scene_fps(context.scene)
    right.label(text=f"{bfps:g} fps")

    message = result.get("message") or ""

    if status == OK:
        row = box.row()
        row.scale_y = 0.85
        row.label(text=message or "rates match", icon='CHECKMARK')
        return

    msg = box.column(align=True)
    msg.scale_y = 0.85
    if status == MISMATCH:
        msg.alert = True
    if message:
        msg.label(text=message)

    if compact or status not in (MISMATCH, MIXED):
        return

    if status == MIXED:
        note = box.column(align=True)
        note.scale_y = 0.85
        note.label(text="No single scene rate fits this folder.", icon='INFO')
        note.label(text="Split it, or import per rate.")
        return

    col = box.column(align=True)
    col.scale_y = 1.05
    col.operator("ht.set_scene_fps", text="Set Blender FPS To Source",
                 icon='TIME').fps = src or 24.0
    op = col.operator("ht.rescale_action_fps",
                      text="Rescale Animation To Scene", icon='MOD_TIME')
    op.source_fps = src or 24.0
    row = col.row()
    row.scale_y = 0.8
    row.label(text="Or import anyway - it is your call.", icon='INFO')


_CLASSES = (
    HT_OT_set_scene_fps,
    HT_OT_rescale_action_fps,
    HT_OT_fps_report,
)


def register(icon_id_fn=None):
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
