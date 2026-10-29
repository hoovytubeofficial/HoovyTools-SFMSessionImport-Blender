"""
Session_Orchestrator.py  -  part of HoovyTools      [roadmap #8]
===============================================================

The Session Importer should not own a second copy of every importer.

    ANALYZE   ask DMX_Analyzer what each file actually holds
    ROUTE     decide which module handles which file
    DELEGATE  call the standalone module, unchanged

So fixing the standalone Animation Importer automatically improves session
import, because session import IS the standalone importer, called in a
sensible order with the session's own defaults. Nothing here re-implements
a channel reader.

WHAT IT ORCHESTRATES
====================
Given a connected animations folder (Session_Paths), each .dmx is analyzed
once and dispatched:

    ANIMATION -> Import_DMX_Animation, onto the matching armature
    CAMERA    -> Import_DMX_Camera
    SHAPEKEY  -> Import_Shape_Keys; a proxy ONLY if you ask for one
    MODEL     -> skipped, it is a reference pose and has no animation
    LIGHT     -> reported, not imported          [roadmap #15 is research]

ORDER MATTERS
=============
Animation first, then shape keys, then cameras. Facial data has to land on
meshes whose armature already exists, and cameras are independent of both,
so they go last where a failure cannot strand a half-imported rig.

FAILURE IS PER FILE
===================
One unreadable DMX must not abort a session of four hundred. Every file is
tried inside its own guard and the run returns a per-file report. Missing
light support in particular never fails the run - the report says the
lights were seen and skipped, and that is all.

DRY RUN
=======
plan() does the analyze-and-route half with no importing at all, so the UI
can show what a session import WOULD do before anything touches the scene.
"""

import bpy
from pathlib import Path
from bpy.types import Operator
from bpy.props import BoolProperty, StringProperty, IntProperty

from ..core import DMX_Analyzer as DA
from ..core import Progress


# ─────────────────────────────────────────────────────────────────────────────
#  Matching files to armatures
# ─────────────────────────────────────────────────────────────────────────────

def _norm(name):
    return "".join(c for c in name.lower() if c.isalnum())


def find_armature(stem, scene=None):
    """
    The armature an animation file belongs to.

    SFM exports are named after the animation set, which is usually the
    model name with decoration around it. Exact match first, then a
    containment test both ways, so 'heavy_shot3' finds 'heavy' and
    'heavy' finds 'heavy.001'.
    """
    scene = scene or bpy.context.scene
    arms = [o for o in scene.objects if o.type == 'ARMATURE']
    if not arms:
        return None
    want = _norm(stem)
    for o in arms:
        if _norm(o.name) == want:
            return o
    best, best_len = None, 0
    for o in arms:
        n = _norm(o.name)
        if n and (n in want or want in n) and len(n) > best_len:
            best, best_len = o, len(n)
    return best


# ─────────────────────────────────────────────────────────────────────────────
#  Plan
# ─────────────────────────────────────────────────────────────────────────────

# Import order. Animation before facial, cameras last.
KIND_ORDER = (DA.ANIMATION, DA.SHAPEKEY, DA.CAMERA)


def plan(paths, scene=None, deep="auto", allow_proxy=False):
    """
    Analyze every file and say what would happen. Imports nothing.

    Returns a list of dicts: path, name, kinds, actions, armature, note.

    allow_proxy is OFF by default and that matters. Facial data with no rig
    used to fall back to a Shape Key Proxy automatically, so a session
    imported before its models produced a screenful of proxy sliders and no
    animation - the tool quietly did something else instead of saying it
    could not do the thing asked. The proxy is now opt-in, and an unmatched
    file is reported as unmatched.
    """
    scene = scene or bpy.context.scene
    out = []
    for p in paths:
        p = Path(p)
        a = DA.analyze(p, deep=deep)
        entry = {"path": p, "name": p.name, "analysis": a,
                 "kinds": DA.kinds_sorted(a), "actions": [],
                 "armature": None, "note": "", "unmatched": False}

        if not a["ok"]:
            entry["note"] = a["error"] or "unreadable"
            out.append(entry)
            continue

        if DA.MODEL in entry["kinds"] and not (
                set(entry["kinds"]) & {DA.ANIMATION, DA.SHAPEKEY, DA.CAMERA}):
            entry["note"] = "reference pose, nothing to animate"
            out.append(entry)
            continue

        if DA.ANIMATION in entry["kinds"] or DA.SHAPEKEY in entry["kinds"]:
            entry["armature"] = find_armature(p.stem, scene)

        for kind in KIND_ORDER:
            if kind not in entry["kinds"]:
                continue
            if kind in (DA.ANIMATION, DA.SHAPEKEY) and entry["armature"] is None:
                if DA.CAMERA in entry["kinds"]:
                    continue
                entry["note"] = "no matching rig in the scene"
                entry["unmatched"] = True
                if kind == DA.SHAPEKEY and allow_proxy:
                    entry["actions"].append("SHAPEKEY_PROXY")
                continue
            entry["actions"].append(kind)

        if DA.LIGHT in entry["kinds"]:
            entry["note"] = ((entry["note"] + "; ") if entry["note"] else "") \
                + "lights present, not imported (roadmap #15)"
        out.append(entry)
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  Run
# ─────────────────────────────────────────────────────────────────────────────

def _armature_meshes(arm):
    return [o for o in bpy.data.objects
            if o.type == 'MESH' and o.parent == arm
            and o.data and o.data.shape_keys]


def run(entries, anim_scale=1.0, add_root_helpers=True, camera_scale=1.0,
        allow_proxy=False, up_axis='FILE', bake_hwm=True,
        remove_drivers=True, stepped_keys='AUTO', report=print,
        rot_mode='QUATERNION'):
    """
    Execute a plan. Every file is guarded on its own.

    Returns {imported, failed, skipped, rows} where rows carry one line per
    file per action, so the caller can print or popup whatever it likes.
    """
    from ..importers import Import_DMX_Animation, Import_DMX_Camera, Import_Shape_Keys

    stats = {"imported": 0, "failed": 0, "skipped": 0, "rows": []}

    for e_idx, e in enumerate(entries, 1):
        Progress.update(e_idx, len(entries), e["name"])
        if not e["actions"]:
            stats["skipped"] += 1
            stats["rows"].append((e["name"], "skip", e["note"] or "nothing to do"))
            continue

        for action in e["actions"]:
            try:
                if action == DA.ANIMATION:
                    def _do(e=e):
                        Import_DMX_Animation.import_dmx_animation(
                            e["path"], e["armature"],
                            add_root_helpers=add_root_helpers,
                            anim_scale=anim_scale, up_axis=up_axis,
                            stepped_keys=stepped_keys,
                            rot_mode=rot_mode)
                    #  1.17.2: a SESSION extract onto a rig Fix All has fixed lands through the model's rest and is
                    #  re-keyed onto Fix All's - on that rest directly its legs crossed in an X (x140). An SFM
                    #  export (no session stamp) goes straight on: Fix All's rest is its own basis.
                    from . import Import_Session
                    arm_ = e["armature"]
                    if Import_Session.has_two_rests(arm_) and Import_Session.is_session_extract(e["path"]):
                        Import_Session.import_on_model_basis(arm_, _do, log=report)
                        how = "%s (session -> Fix All's rest)" % arm_.name
                    else:
                        _do()
                        how = arm_.name
                    stats["imported"] += 1
                    stats["rows"].append((e["name"], "anim", how))

                elif action == DA.CAMERA:
                    #  fix_quat_flips=False EXPLICITLY, not by default.
                    #  This call used to inherit the function's old default of
                    #  True - the "smooth" path - while the standalone DMX
                    #  Camera operator shipped False - the raw/stepped path.
                    #  Same file, two behaviours: a session import smeared
                    #  every hard cut into a slow spin and keyed off-frame,
                    #  while a hand import of the SAME extracted data was
                    #  clean. The extraction was never wrong (measured
                    #  identical to an SFM export of the same take); the
                    #  entry point was.
                    Import_DMX_Camera.import_dmx_camera(
                        str(e["path"]), scale=camera_scale,
                        fix_quat_flips=False)
                    stats["imported"] += 1
                    stats["rows"].append((e["name"], "camera", "imported"))

                elif action == DA.SHAPEKEY:
                    meshes = _armature_meshes(e["armature"])
                    if not meshes:
                        if allow_proxy:
                            from ..tools import ShapeKey_Proxy
                            r = ShapeKey_Proxy.build_proxy_from_dmx(e["path"])
                            stats["imported"] += 1
                            stats["rows"].append(
                                (e["name"], "proxy",
                                 f"{r['shape_keys']} key(s), no target mesh"))
                        else:
                            stats["skipped"] += 1
                            stats["rows"].append(
                                (e["name"], "skip", "no mesh with shape keys"))
                        continue
                    # The FULL pipeline, not import_flex_dmx: that one
                    # only lays down the flex animation and skips the HWM
                    # localvar bake, so a session import produced faces
                    # whose combination controls never fired. A standalone
                    # Import Shape Keys always baked; this now matches it.
                    done = baked = 0
                    try:
                        for m in meshes:
                            r = Import_Shape_Keys.import_shape_keys(
                                e["path"], m,
                                do_remove_drivers=remove_drivers,
                                do_stereo_split=False,
                                do_import_flex=True,
                                do_bake_hwm=bake_hwm)
                            done += 1
                            # import_shape_keys returns bake_result, not
                            # "bake" - reading the wrong key made every run
                            # report "bake found no QC" while the console
                            # showed [HWM_BAKE] baked:140.
                            if isinstance(r, dict) and r.get("bake_result"):
                                baked += 1
                    except ValueError as exc:
                        if "No flexWeight channels" not in str(exc):
                            raise
                        stats["skipped"] += 1
                        stats["rows"].append(
                            (e["name"], "skip", "no facial keys in this set"))
                        continue
                    stats["imported"] += 1
                    stats["rows"].append(
                        (e["name"], "flex",
                         f"{done} mesh(es)"
                         + (f", {baked} baked" if baked else
                            (", bake found no QC" if bake_hwm else
                             ", bake off"))))

                elif action == "SHAPEKEY_PROXY":
                    if not allow_proxy:
                        stats["skipped"] += 1
                        stats["rows"].append(
                            (e["name"], "skip", "no armature, proxy disabled"))
                        continue
                    from ..tools import ShapeKey_Proxy
                    r = ShapeKey_Proxy.build_proxy_from_dmx(e["path"])
                    stats["imported"] += 1
                    stats["rows"].append(
                        (e["name"], "proxy",
                         f"{r['shape_keys']} key(s), no character"))

            except Exception as exc:
                stats["failed"] += 1
                stats["rows"].append(
                    (e["name"], "FAIL", f"{action}: {type(exc).__name__}: {exc}"))
                report(f"[ORCHESTRATOR]  {e['name']} {action} FAILED: {exc}")
                # Print the stack. A per-file guard that swallows WHERE it
                # broke turns a five minute fix into an afternoon - the
                # summary line alone told us a camera raised IndexError and
                # nothing about which line.
                import traceback
                traceback.print_exc()

    #  AUTO-SPLIT BELONGS HERE, NOT ONLY ON THE STEP OPERATOR.
    #  This orchestrator calls Import_DMX_Camera directly, so the one-click and
    #  Import All paths never reach HT_OT_step_cameras.execute - hooking the
    #  step alone meant the toggle did nothing for anyone importing a whole
    #  session, which is the case it exists for. The helper skips anything
    #  already inside the split collection, so being called from both paths
    #  cannot split a shot into shots.
    if any(DA.CAMERA in (e.get("actions") or ()) for e in entries):
        try:
            from .Session_Steps import _auto_split_cameras
            for line in _auto_split_cameras(bpy.context):
                stats["rows"].append(("auto-split", "camera", line))
                report(f"[ORCHESTRATOR]  {line}")
        except Exception as exc:
            report(f"[ORCHESTRATOR]  auto-split failed: "
                   f"{type(exc).__name__}: {exc}")
            import traceback
            traceback.print_exc()

        try:
            from ..tools import Camera_Bone_Rig
            for r in Camera_Bone_Rig.rig_all_cameras():
                if r["status"] == "skipped":
                    continue
                line = (f"{r['camera']}: {r['status']}"
                        + (f" ({r['curves']} curve(s), drift {r['drift']:.1e})"
                           if r["status"] == "rigged" else
                           f" - {r.get('reason') or r.get('drift')}"))
                stats["rows"].append(("camera rig", "camera", line))
                report(f"[ORCHESTRATOR]  camera rig: {line}")
        except Exception as exc:
            report(f"[ORCHESTRATOR]  camera rig failed: "
                   f"{type(exc).__name__}: {exc}")
            import traceback
            traceback.print_exc()

    return stats


# ─────────────────────────────────────────────────────────────────────────────
#  Operators
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_session_plan(Operator):
    """Dry run: say what a session import WOULD do, and change nothing

Analyses every file in the connected animations folder, decides what each
one is - bone animation, camera, shape keys - and which rig in the scene
it would land on.

Read this before a long import. It is the cheapest way to catch the two
failures that waste the most time: a file that matches no rig (import the
models first) and a folder that is not the one you meant"""
    bl_idname = "ht.session_plan"
    bl_label = "Plan Session Import"
    bl_options = {"REGISTER"}

    limit: IntProperty(  # type: ignore
        name="Limit",
        description="Analyze at most this many files. 0 for all of them",
        default=0, min=0, max=100000,
    )

    def execute(self, context):
        from . import Session_Paths
        files = Session_Paths.list_animations(context.scene)
        if not files:
            self.report({"WARNING"},
                        "No animations folder connected, or it holds no DMX")
            return {"CANCELLED"}
        if self.limit:
            files = files[:self.limit]

        entries = plan(files, context.scene)

        by_action = {}
        no_rig = []
        for e in entries:
            for a in e["actions"]:
                by_action[a] = by_action.get(a, 0) + 1
            if not e["actions"]:
                no_rig.append(e)

        print(f"\n[ORCHESTRATOR]  plan for {len(entries)} file(s)")
        for e in entries:
            arm = e["armature"].name if e["armature"] else "-"
            acts = "+".join(e["actions"]) or "skip"
            print(f"[ORCHESTRATOR]  {acts:<22} {arm:<22} {e['name']}"
                  + (f"   ({e['note']})" if e["note"] else ""))

        lines = [f"Files   : {len(entries)}"]
        for a, n in sorted(by_action.items()):
            lines.append(f"{a:<8}: {n}")
        if no_rig:
            lines.append(f"Skipped : {len(no_rig)}")
        lines.append("Full routing is in the system console.")
        for line in lines:
            print(f"[ORCHESTRATOR]  {line}")

        from ..core import Report_UI
        Report_UI.report(
            context, "session_plan", "Session Plan", lines, level='INFO',
            icon='VIEWZOOM', operator=self, prefix="ORCHESTRATOR",
            summary=(f"Session Plan - {len(entries)} file(s): "
                     + ", ".join(f"{a} {n}"
                                 for a, n in sorted(by_action.items()))
                     or "nothing to do"))
        return {"FINISHED"}


class HT_OT_session_import_all(Operator):
    """Import every animation in the connected folder, routing each to its own rig

The batch version of the numbered steps: it plans, then runs bone
animation, cameras and facial animation in one pass, matching each file
to a rig by name.

Import the session's models first. Anything that finds no rig is reported
rather than dropped - and a camera file, which has no rig by nature, is
correctly not counted against you.

For a whole session prefer Import Whole Session; this one is for a folder
you have curated by hand"""
    bl_idname = "ht.session_import_all"
    bl_label = "Import Session Animations"
    #  NO "REGISTER" - see the note in Report_UI/the constitution.
    #  REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    #  touching any field in it RE-RUNS this operator. Re-running an
    #  import re-reads the DMX and rebuilds every f-curve; nudging Scale
    #  there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    #  with the value you wanted is the safe way to change your mind.
    bl_options = {"UNDO"}

    allow_proxy: BoolProperty(  # type: ignore
        name="Proxy For Orphan Facial Data",
        description=(
            "Build a Shape Key Proxy when facial animation has no character "
            "to land on. OFF by default: a session imported before its "
            "models would otherwise fill the scene with proxy sliders and "
            "no animation, which looks like the importer misfiring rather "
            "than like the rigs being missing. Turn it on when you WANT to "
            "inspect facial data without a character"),
        default=False,
    )
    add_root_helpers: BoolProperty(  # type: ignore
        name="Root Transform",
        description=("Session-aware default: keep the root transform. The "
                     "session knows its own game-model motion, so unlike a "
                     "lone file this can assume it is wanted"),
        default=True,
    )
    check_fps: BoolProperty(  # type: ignore
        name="Check Frame Rate First",
        description=("Refuse to start when the folder's frame rate does not "
                     "match the scene. Turn off to import anyway"),
        default=True,
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=340)

    def draw(self, context):
        from . import Session_Paths
        from ..session import FPS_Safety
        col = self.layout.column()
        folder = Session_Paths.animations_dir(context.scene)
        if folder is None:
            box = col.box()
            box.alert = True
            box.label(text="No animations folder connected", icon='ERROR')
            return
        n = len(Session_Paths.list_animations(context.scene))
        col.label(text=f"{n} DMX file(s) in the connected folder",
                  icon='FILE_TICK')
        col.separator()
        col.prop(self, "check_fps")
        col.prop(self, "add_root_helpers")
        col.prop(self, "allow_proxy")

    def execute(self, context):
        from . import Session_Paths
        from ..session import FPS_Safety
        files = Session_Paths.list_animations(context.scene)
        if not files:
            self.report({"WARNING"},
                        "No animations folder connected, or it holds no DMX")
            return {"CANCELLED"}

        if self.check_fps:
            folder = Session_Paths.animations_dir(context.scene)
            r = FPS_Safety.check_folder(folder, context.scene)
            if r["status"] in (FPS_Safety.MISMATCH, FPS_Safety.MIXED):
                self.report({"ERROR"},
                            f"Frame rate {r['status']}: {r['message']}. "
                            f"Fix it in the Main tab, or untick "
                            f"Check Frame Rate First.")
                return {"CANCELLED"}

        entries = plan(files, context.scene, allow_proxy=self.allow_proxy)
        stats = run(entries, add_root_helpers=self.add_root_helpers,
                    allow_proxy=self.allow_proxy)

        unmatched = [e for e in entries if e.get("unmatched")]

        print(f"\n[ORCHESTRATOR]  imported {stats['imported']}, "
              f"failed {stats['failed']}, skipped {stats['skipped']}")
        for name, kind, detail in stats["rows"]:
            print(f"[ORCHESTRATOR]  {kind:<7} {name:<44} {detail}")

        lines = [
            f"Files    : {len(entries)}",
            f"Imported : {stats['imported']}",
            f"Skipped  : {stats['skipped']}",
            f"Failed   : {stats['failed']}",
        ]
        if unmatched:
            lines.append("")
            lines.append(f"{len(unmatched)} file(s) had NO MATCHING RIG:")
            for e in unmatched[:5]:
                lines.append(f"  {e['name']}")
            if len(unmatched) > 5:
                lines.append(f"  ... and {len(unmatched) - 5} more")
            lines.append("")
            lines.append("Import the session models first (step 1),")
            lines.append("then run this again.")
        fails = [r for r in stats["rows"] if r[1] == "FAIL"]
        if fails:
            lines.append("")
            for name, _k, detail in fails[:4]:
                lines.append(f"{name}: {detail[:48]}")
            if len(fails) > 4:
                lines.append(f"... and {len(fails) - 4} more (console)")

        from ..core import Report_UI
        Report_UI.report(
            context, "session_import_all", "Session Import", lines,
            level=('WARNING' if (stats["failed"] or unmatched) else 'INFO'),
            prefix="ORCHESTRATOR", operator=self,
            summary=f"Session Import - {stats['imported']} imported, "
                    f"{stats['skipped']} skipped, {stats['failed']} failed"
                    + (f", {len(unmatched)} with no rig" if unmatched else ""))

        if unmatched and not stats["imported"]:
            self.report({"ERROR"},
                        f"Nothing imported - none of the {len(entries)} "
                        f"file(s) matched a rig in the scene. Import the "
                        f"session models first.")
            return {"FINISHED"}
        level = "WARNING" if (stats["failed"] or unmatched) else "INFO"
        self.report({level},
                    f"Imported {stats['imported']}, skipped "
                    f"{stats['skipped']}, failed {stats['failed']}"
                    + (f", {len(unmatched)} with no rig" if unmatched else ""))
        return {"FINISHED"}


class HT_OT_session_one_click(Operator):
    """Take the connected session all the way in - the whole scene

Runs the whole pipeline in order, reporting each step:

  1  import the session's models, rest poses fixed, eyes wired
  2  pull the animation straight out of the session
  3  match the scene frame rate to the session
  4  import the animation onto the rigs, facial included
  5  import the session's sounds onto the sequencer
  6  import the session's lights
  7  build its particle effects
  11 import the shot's map (through SourceIO), in one collection

Developer Mode: the button asks first, with every step as a switch.

Root transform is on, so characters stand where the session puts them.

Every step is optional and every step reports what it did. If the models
cannot be found the run stops there and says so, rather than carrying on
and importing animation onto nothing"""
    bl_idname = "ht.session_one_click"
    bl_label = "Import Whole Session"
    #  NO "REGISTER" - see the note in Report_UI/the constitution.
    #  REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    #  touching any field in it RE-RUNS this operator. Re-running an
    #  import re-reads the DMX and rebuilds every f-curve; nudging Scale
    #  there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    #  with the value you wanted is the safe way to change your mind.
    bl_options = {"UNDO"}

    do_models: BoolProperty(  # type: ignore
        name="1  Import Models",
        description=("Import every model the session references, give each rig "
                     "the rest pose from its reference .dmx (Faulty Rigs) and "
                     "wire its eyes. Models already in the scene are skipped, so "
                     "a second press does not double the scene"),
        default=True,
    )
    do_extract: BoolProperty(  # type: ignore
        name="2  Extract Animation",
        description=("Pull the animation out of the session and WRITE IT TO "
                     "DISK, in an `anims` folder beside the session .dmx. "
                     "Those files are ordinary export-shaped DMX animations: "
                     "you can import any of them by hand with the standalone "
                     "DMX Animation importer, which is the way to tell an "
                     "extraction problem apart from a session-import problem. "
                     "Turn this off to reuse whatever is already in the "
                     "folder instead of rewriting it"),
        default=True,
    )
    do_fps: BoolProperty(  # type: ignore
        name="3  Match Frame Rate",
        description=("Set the scene to the session's frame rate before any "
                     "animation lands, so nothing has to be rescaled later"),
        default=True,
    )
    do_animation: BoolProperty(  # type: ignore
        name="4  Import Animation",
        description="Route each extracted file onto its rig",
        default=True,
    )
    do_sounds: BoolProperty(  # type: ignore
        name="5  Import Sounds",
        description=("Lay the session's sounds onto the sequencer at the "
                     "times SFM plays them"),
        default=True,
    )
    do_particles: BoolProperty(  # type: ignore
        name="7  Import Particles",
        description=("Build the particle effects the session names, through "
                     "the HoovyTools Particle Import add-on. That add-on must "
                     "be enabled; a session only names an effect, the "
                     "definition lives in a .pcf"),
        default=True,
    )
    do_lights: BoolProperty(  # type: ignore
        name="6  Import Lights",
        description=("Bring in the session's DmeProjectedLights as Blender "
                     "spots, with their SFM colour and placement"),
        default=True,
    )
    do_euler: BoolProperty(  # type: ignore
        name="9  End on Euler Rotations",
        description=("Convert every animated rotation from quaternion to "
                     "Euler (XYZ) as the last step, so Blender's "
                     "Discontinuity (Euler) Filter and the graph editor work "
                     "on the result. Sign flips cannot survive the "
                     "conversion.\n\nTHIS FEATURE WAS ADDED IN VERSION 1.16.0 "
                     "AND IS IN EXPERIMENTAL STAGE"),
        default=True,
    )
    do_visibility: BoolProperty(  # type: ignore
        name="10  SFM Visibility + Shot Camera",
        description=("Hide every model and light SFM hides in this shot - "
                     "hidden itself or inside a hidden group - and look "
                     "through the camera SFM looks through (the shot's own "
                     "camera, not the alphabetically first one).\n\nTHIS "
                     "FEATURE WAS ADDED IN VERSION 1.17.0 AND IS IN "
                     "EXPERIMENTAL STAGE"),
        default=True,
    )
    do_map: BoolProperty(  # type: ignore
        name="11  Import Map",
        description=("Import the map the shot plays on, LAST - through SourceIO, at the session's scale - and "
                     "put all of it into ONE collection, 'Map - <name>'. A map already imported is left alone; "
                     "a stock map that only lives inside a VPK is reported, not imported. Without SourceIO the "
                     "map is left out and everything else still imports.\n\nTHIS FEATURE WAS "
                     "ADDED IN VERSION 3.0.0 AND IS IN EXPERIMENTAL STAGE"),
        default=True,
    )
    do_organize: BoolProperty(  # type: ignore
        name="8  Sort Into Collections",
        description=("Run the scene organizer at the end, so everything the "
                     "import made is filed into character and model "
                     "collections instead of lying flat in the scene root. "
                     "The same pass as Tools > Scene Organizers, run "
                     "automatically"),
        default=True,
    )

    def invoke(self, context, event):
        try:
            from ..ui.Panel import settings as _panel_settings
            st = _panel_settings(context)
            dev = bool(getattr(st, "developer_mode", False))
        except Exception:                                     # noqa: BLE001
            dev = False
        if not dev:
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        from . import Session_Paths
        col = self.layout.column()
        p = Session_Paths.session_file(context.scene)
        if p is None:
            box = col.box()
            box.alert = True
            box.label(text="No session connected", icon='ERROR')
            box.label(text="Connect one above first.")
            return
        col.label(text=p.name, icon='SCENE_DATA')
        col.separator()
        col.prop(self, "do_models")
        col.prop(self, "do_extract")
        col.prop(self, "do_fps")
        col.prop(self, "do_animation")
        col.prop(self, "do_sounds")
        col.prop(self, "do_lights")
        col.prop(self, "do_particles")
        col.prop(self, "do_organize")
        col.prop(self, "do_euler")
        col.prop(self, "do_visibility")
        col.prop(self, "do_map")
        col.separator()

    def execute(self, context):
        #  NOT the @jobbed decorator: register_class inspects execute's
        #  own argument count and a (*args, **kwargs) wrapper reads as 0
        #  [MEASURED: ValueError at registration]. A two-line trampoline
        #  keeps the signature Blender checks.
        with Progress.job("SFM Session Importer - Import Whole Session",
                          phase_total=11):
            return self._execute(context)

    def _execute(self, context):
        from . import Session_Paths, Session_Reader, Import_Session
        from ..session import FPS_Safety

        session = Session_Paths.session_file(context.scene)
        if session is None:
            self.report({"ERROR"}, "No session connected")
            return {"CANCELLED"}

        #  ONE REPORT FOR THE WHOLE RUN.
        #
        #  Every step below is an operator or a function that reports for
        #  itself, and each of those reports used to open its own dialog. A
        #  whole-session import therefore ended in a stack of popups that had
        #  to be clicked through one at a time - and because a popup blocks,
        #  the next step did not even start until the previous dialog was
        #  dismissed. One click was not one click.
        #
        #  Inside this quiet scope every nested report still prints its full
        #  text to the console and is collected; nothing opens and nothing
        #  blocks. The single summary at the bottom is the only dialog, and it
        #  carries its own off switch like every other report in the addon.
        from ..core import Report_UI
        with Report_UI.quiet():
            steps = []
            fatal = None

            def step(label, fn):
                """Run one stage, record what it said, never let it kill the run."""
                nonlocal fatal
                if fatal:
                    steps.append((label, "skipped", "an earlier step failed"))
                    return None
                #  The overlay names the stage: '5 Animation' advances the
                #  10-phase bar to position 5 whatever was switched off.
                head = label.split()
                Progress.phase(label, number=(int(head[0])
                                              if head and head[0].isdigit()
                                              else None))
                try:
                    detail = fn()
                    steps.append((label, "ok", detail))
                    return detail
                except Exception as exc:
                    steps.append((label, "FAILED", f"{type(exc).__name__}: {exc}"))
                    return None

            #  ONE IMPORT, ONE MANIFEST. Cleared here rather than appended
            #  to, because a list naming files from a previous import would
            #  send somebody to open the wrong .pcf - worse than no list.
            try:
                from ..core import sources
                sources.begin()
            except Exception:
                pass

            # 1 ── models ────────────────────────────────────────────────────
            from . import Session_Steps
            if self.do_models:
                def _models():
                    r = Session_Steps.import_models(
                        context, session, fix_rigs=True)
                    bits = [f"{r['imported']} model(s)"]
                    if r["missing"]:
                        bits.append(f"{r['missing']} missing")
                    bits.append(f"{r['fixed']} rest pose(s) fixed")
                    if r.get("no_reference"):
                        bits.append(f"{r['no_reference']} without a reference")
                    if r.get("rig_errors"):
                        bits.append(f"{r['rig_errors']} rig error(s)")
                    return ", ".join(bits)
                step("1 Models", _models)

            arms = [o for o in context.scene.objects if o.type == 'ARMATURE']
            if self.do_animation and not arms and self.do_models:
                fatal = ("No armatures in the scene after importing models. "
                         "Animation would have nothing to land on - check that "
                         "SourceIO is enabled and the .mdl files are findable.")

            # 3 ── extract ───────────────────────────────────────────────────
            out_dir = None

            if self.do_extract:
                def _extract():
                    nonlocal out_dir
                    r = Session_Steps.ensure_extracted(context, session,
                                                       rebase=False)
                    out_dir = r["out_dir"]
                    # Print the FULL path, not just the folder name. These files
                    # are the thing to hand to the standalone importer when the
                    # question is "is the extraction wrong or is the session
                    # import wrong", and a bare "anims/" is not something you can
                    # paste into a file browser.
                    print(f"[ONE_CLICK]  anims folder: {out_dir}")
                    for w in r["written"]:
                        print(f"[ONE_CLICK]     {Path(w['path']).name}")
                    return (f"{len(r['written'])} animation(s) -> "
                            f"{out_dir}  ({len(r['skipped'])} skipped)")
                step("2 Extract", _extract)

            # 4 ── frame rate ────────────────────────────────────────────────
            if self.do_fps:
                def _fps():
                    info_fps = Session_Reader.read_session(session)["fps"]
                    before = FPS_Safety.scene_fps(context.scene)
                    if FPS_Safety.matches(info_fps, before):
                        return f"already {before:g} fps"
                    FPS_Safety.set_scene_fps(context.scene, info_fps)
                    return (f"{before:g} -> "
                            f"{FPS_Safety.scene_fps(context.scene):g} fps")
                step("3 Frame rate", _fps)

            # 5 ── animation ─────────────────────────────────────────────────
            if self.do_animation:
                def _anim():
                    files = Session_Paths.list_animations(context.scene)
                    if not files:
                        raise RuntimeError("no animation files to import")
                    entries = plan(files, context.scene, allow_proxy=False)
                    stats = run(entries, add_root_helpers=True, allow_proxy=False)
                    unmatched = [e for e in entries if e.get("unmatched")]
                    detail = (f"{stats['imported']} imported, "
                              f"{stats['skipped']} skipped, "
                              f"{stats['failed']} failed")
                    if unmatched:
                        detail += f", {len(unmatched)} with NO MATCHING RIG"
                    return detail
                step("4 Animation", _anim)

            # 6 ── sounds ────────────────────────────────────────────────────
            #
            #  Sounds and lights were reachable only as separate buttons, so
            #  "Import Whole Session" quietly imported most of a session and the
            #  rest had to be remembered. A whole session means the whole scene.
            if self.do_sounds:
                def _sounds():
                    # Count sound DATABLOCKS, not sequencer strips. Blender 5.x
                    # renamed sequence_editor.sequences_all to strips_all, and
                    # reaching for the old name here would turn a working import
                    # into a reported failure on exactly the versions this addon
                    # targets. bpy.data.sounds is stable across both.
                    before = {s.name for s in bpy.data.sounds}
                    r = bpy.ops.ht.import_session_sounds(filepath=str(session))
                    if "FINISHED" not in r:
                        raise RuntimeError(f"sound importer returned {r}")
                    added = {s.name for s in bpy.data.sounds} - before
                    return f"{len(added)} sound(s) loaded"
                step("5 Sounds", _sounds)

            # 7 ── lights ────────────────────────────────────────────────────
            if self.do_lights:
                def _lights():
                    before = {o.name for o in bpy.data.objects if o.type == 'LIGHT'}
                    r = bpy.ops.ht.step_lights()
                    if "FINISHED" not in r:
                        raise RuntimeError(f"light importer returned {r}")
                    after = {o.name for o in bpy.data.objects if o.type == 'LIGHT'}
                    return f"{len(after - before)} light(s) imported"
                step("6 Lights", _lights)

            # 8 ── particles ─────────────────────────────────────────────────
            #
            #  Handed to the Particle Import add-on through its api module. It is
            #  a separate add-on and may not be enabled, so a failure here reports
            #  and never takes the session down with it.
            if self.do_particles:
                def _particles():
                    from . import Session_Particles, Session_Paths
                    #  The shot filter, in BOTH import paths (the lesson
                    #  auto-split taught: a per-step hook wired into the
                    #  step operator alone does nothing for one-click).
                    idx, nm = Session_Paths.shot_choice(context.scene)
                    r = Session_Particles.import_session_particles(
                        session, shot_index=idx, shot_name=nm)
                    bits = [f"{len(r['made'])} effect(s) built"]
                    if r["skipped"]:
                        bits.append(f"{len(r['skipped'])} skipped")
                    if r["failed"]:
                        bits.append(f"{len(r['failed'])} failed")
                    if not r["wanted"]:
                        return "none in this cut"
                    return ", ".join(bits)
                step("7 Particles", _particles)

            if self.do_organize:
                def _organize():
                    from ..tools import Utils_Misc
                    r = Utils_Misc.organize_scene()
                    bits = [f"{len(r['characters'])} character(s)",
                            f"{len(r['models'])} model(s) filed",
                            f"{len(r.get('props', []))} prop(s)"]
                    if r["skipped"]:
                        bits.append(f"{len(r['skipped'])} left as-is")
                    return ", ".join(bits)
                step("8 Organize", _organize)

            if self.do_euler:
                def _euler():
                    from ..tools import Euler_Output
                    r = Euler_Output.convert_scene()
                    return (f"{r['rotations']} rotation(s) on {r['objects']} "
                            f"object(s) now Euler XYZ")
                step("9 Euler", _euler)

            if self.do_visibility:
                def _visibility():
                    from ..tools import Session_Visibility
                    idx, nm = Session_Paths.shot_choice(context.scene)
                    r = Session_Visibility.apply(context, session,
                                                 shot_index=idx, shot_name=nm)
                    for line in Session_Visibility.report_lines(r):
                        print(f"[VISIBILITY]  {line}")
                    bits = [f"{len(r['hidden'])} hidden as in SFM"]
                    if r.get("camera"):
                        bits.append(f"camera {r['camera']}")
                    elif r.get("camera_element"):
                        bits.append(f"SFM camera {r['camera_element']!r} "
                                    f"not imported")
                    if r["missing"]:
                        bits.append(f"{len(r['missing'])} hidden set(s) not "
                                    f"in the scene")
                    return ", ".join(bits)
                step("10 Visibility", _visibility)

            if self.do_map:
                def _map():
                    from . import Session_Map
                    idx, nm = Session_Paths.shot_choice(context.scene)
                    r = Session_Map.import_map(context, session, shot_index=idx, shot_name=nm)
                    if not r.get("map"):
                        return r.get("note", "no map")
                    return "%s - %s" % (Path(r["map"]).name, r.get("note", ""))
                step("11 Map", _map)

        #  THE MANIFEST, LAST, so it lists what this run actually brought
        #  in. Purple = provenance; see core/sources.py.
        try:
            from ..core import sources
            sources.report(context)
        except Exception as exc:                              # noqa: BLE001
            print(f"[SOURCES]  manifest unavailable ({exc})")

        #  THE SHOT OWNS THE FRAME RANGE, AND IT GETS THE LAST WORD.
        #
        #  Every importer between here and the extract may push `frame_end`
        #  out to cover what it just brought in - Blender Source Tools does it
        #  per model, the shape-key importer does it per face, the sound
        #  importer does it per strip. That is right when nobody has said
        #  which cut this is. Once somebody has, the cut is the answer, and
        #  the keys that run past it are not part of it.
        #
        #  Measured on shot1: the shot ends at 312 and the range had grown to
        #  339, because `combine_rifle_ammo12` keeps keying past the cut.
        rng = Session_Steps.apply_shot_frame_range(context, session)
        if rng:
            steps.append(("Frame range", "ok", f"{rng[0]}-{rng[1]}"))

        try:
            from ..tools import Layout_Builder
            cam_line = Layout_Builder.jump_to_session_camera(context)
            if cam_line:
                steps.append(("Camera view", "ok",
                              cam_line.split(": ", 1)[-1]))
        except Exception as exc:                              # noqa: BLE001
            print(f"[ONE_CLICK]  camera jump failed: {exc}")

        #  BUILD THE CHOSEN WORKSPACE LAYOUT, if the Developer tab's Layouts
        #  box picked one for "after session import" (default Off). The
        #  rebuild runs on a UI timer AFTER this operator returns, so it can
        #  never slow or break the import - a background run refuses cleanly.
        #  Its 3D views also open in camera view, because the jump above
        #  already set scene.camera and the builder honours it at DONE.
        try:
            from ..tools import Layout_Builder
            ll = Layout_Builder.launch_after_import(context)
            if ll:
                steps.append(("Layout", "ok", ll.split(": ", 1)[-1]))
        except Exception as exc:                              # noqa: BLE001
            print(f"[ONE_CLICK]  layout launch failed: {exc}")

        try:
            from ..tools import Layout_Builder
            rl = Layout_Builder.apply_render_after_import(context)
            if rl:
                steps.append(("Engine", "ok", rl.split(": ", 1)[-1]))
        except Exception as exc:                              # noqa: BLE001
            print(f"[ONE_CLICK]  render preset failed: {exc}")

        lines = [f"Session: {session.name}", ""]
        for label, status, detail in steps:
            mark = {"ok": "", "FAILED": "FAILED - ",
                    "skipped": "skipped - "}[status]
            lines.append(f"{label}: {mark}{detail or ''}")
        if fatal:
            lines.append("")
            lines.append(fatal)

        print()

        failed = [s for s in steps if s[1] == "FAILED"]
        if fatal:
            level = 'ERROR'
        elif failed:
            level = 'WARNING'
        else:
            level = 'INFO'

        #  report_collected folds everything the quiet scope caught into this
        #  one dialog, under the per-step summary built above. The level it
        #  would have chosen on its own is overridden here: a step that
        #  reported INFO can still have FAILED as far as the pipeline is
        #  concerned, and `steps` is what knows that.
        Report_UI.report_collected(
            context, "session_one_click", "Session Import",
            header_lines=lines, level=level, operator=self,
            prefix="ONE_CLICK")
        return {"FINISHED"}


_CLASSES = (
    HT_OT_session_plan,
    HT_OT_session_import_all,
    HT_OT_session_one_click,
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
