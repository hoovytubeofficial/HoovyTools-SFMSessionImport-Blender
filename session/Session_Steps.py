"""
Session_Steps.py  -  part of HoovyTools
=======================================

The session, broken into the seven things a person actually asks for:

    1  Models      every model the session references
    2  Fix Rigs    each rig's rest pose, from its reference DMX
    3  Animations  bone animation onto those rigs
    4  Shape Keys  facial animation onto their meshes
    5  Cameras     the session's cameras
    6  Sounds      the session's audio
    7  Lights      the session's lights

`ht.session_one_click` runs all seven in order. Each is also its own
operator, so a step can be redone without repeating the rest.

RIG FIXING IS ITS OWN STEP
==========================
It briefly lived inside step 1, on the reasoning that a session model always
wants its reference rest pose so it should not be a decision. That reasoning
was right about the DEFAULT and wrong about the PACKAGING: folded into the
model import it could not be run, skipped or re-run on its own, and "the rig
is wrong" could not be told apart from "the model did not import". It is
step 2 again, and it is idempotent - a second and third run change nothing -
so re-running it costs only time.

WHAT IT ACTUALLY DOES, because this is easy to misread:
SourceIO builds the rig from the .mdl with bone rolls that do not match the
rig SFM animated. The reference DMX supplies the rest pose SFM expects; the
mesh and weight groups stay SourceIO's. The change is almost ENTIRELY
ROTATION - on a real TF2 rig up to 240 degrees of re-roll against about
0.03 units of movement - so judging it by bone positions reads as "nothing
happened" when it worked. The step reports both numbers for that reason.

Order still matters: pose is stored relative to the rest pose, so fixing a
rest pose after animation is on the rig bends every existing key. Step 2
warns when it finds a rig that already has an action.

EVERY OPTION IS ALWAYS AVAILABLE
================================
Developer mode changes what the PANEL shows inline, never what an operator
can do. Press any of these and its full option set is in the dialog and in
the redo panel, developer mode or not.
"""

import bpy
import os
from pathlib import Path

from bpy.types import Operator
from bpy.props import (BoolProperty, IntProperty, FloatProperty,
                       StringProperty, EnumProperty)

from ..core import DMX_Analyzer as DA
from ..core import Progress


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def session_of(context):
    from . import Session_Paths
    return Session_Paths.session_file(context.scene)




def _session_for(op, context):
    """The session THIS press should use: the picked file, or the connected
    one. Returns None when there is neither."""
    raw = (getattr(op, "filepath", "") or "").strip()
    if raw:
        p = Path(bpy.path.abspath(raw))
        return p if p.is_file() else None
    return session_of(context)


def pick_or_run(op, context, event):
    """Shared invoke: open the file browser, or just run.

    OPENS IN SFM's ELEMENTS FOLDER, from the config ladder - so somebody who
    keeps sessions on a share says so once in customizedconfig.json rather
    than navigating there on every press.
    """
    if getattr(op, "pick_session", False) and getattr(op, "reads_session", True):
        if not op.filepath:
            from . import Session_Paths
            d = Session_Paths.config_folder("elements")
            if d is not None:
                op.filepath = str(d) + os.sep
        context.window_manager.fileselect_add(op)
        return {"RUNNING_MODAL"}
    return op.execute(context)


def no_session_error(op):
    """The same sentence everywhere, and it names which case you are in."""
    if getattr(op, "pick_session", False):
        return "No session picked - choose a .dmx in the file browser"
    return "No session connected - load one on the Main tab"


def _popup(context, title, lines, icon='CHECKMARK', key=None,
           level='INFO', operator=None):
    """One step's report.

    Everything goes through Report_UI now: the console always, ONE popup that
    carries its own off switch, and a coloured bar along the bottom of the
    viewport for ten seconds. Inside a `Report_UI.quiet()` scope - which is
    what IMPORT WHOLE SESSION runs in - the popup and the bar are collected
    instead, so eight steps produce one dialog rather than eight.

    *key* names the switch in Report_UI.REPORTS. A call without one still
    reports; it just has no off switch of its own."""
    from ..core import Report_UI
    Report_UI.report(context, key, title, lines, level=level, icon=icon,
                     operator=operator, prefix="SESSION_STEP")


@Progress.jobbed("HoovyTools - Import Models")
def import_models(context, session, fix_rigs=False, **_legacy):
    """
    Step 1. Models. Nothing else.

    ONE CALL. `run_session_import` used to import a slice per invocation and
    this looped it up to `max_passes` times, which meant the passes existed
    only to be counted. Both are gone; `**_legacy` swallows a stale
    `max_passes=` from an old script rather than raising at it.

    *fix_rigs*: 1.18.0 folds the rest-pose fix back into this step. It is safe here since 1.17.2 - the session animation is laid on
    through the model rest and re-keyed onto the reference rest, so the fix
    no longer has to run on its own before the animation. The operator and
    the one-click pass True; the default stays False for scripts.
    """
    from . import Import_Session
    r = Import_Session.run_session_import(Path(session))
    out = {"imported": r.get("imported", 0), "missing": r.get("missing", 0),
           "fixed": 0, "no_reference": 0, "rig_errors": 0,
           "missing_models": r.get("missing_models", []),
           "elsewhere": r.get("elsewhere", {}), "searched": r.get("searched", 0)}

    if fix_rigs:
        rf = Import_Session.run_rig_fixer()
        out["fixed"] = rf["fixed"]
        out["kept"] = rf.get("kept", 0)
        out["no_reference"] = rf["skipped"]
        out["rig_errors"] = rf["errors"]
        out["rig_rows"] = rf["results"]
    return out


def _shot_label(context, idx, name=""):
    """The chosen shot's name, safe for a folder. "" when there is not one.

    ONE COPY. This was written twice within an hour - once to pick the extract
    folder and once to find it again - and the two had already drifted: one
    fell back to `cut{idx}` and the other to nothing, so a shot whose name the
    picker had not cached would have been written to `cut1` and looked for
    under a folder with no name at all.
    """
    from . import Session_Paths, Session_Reader
    if idx is None or int(idx) < 0:
        return ""
    label = name or ""
    if not label:
        try:
            cached, _fresh = Session_Paths.cached_shots(
                getattr(context, "scene", None) if context else None)
            if 0 <= int(idx) < len(cached):
                label = cached[int(idx)].name or ""
        except Exception:
            label = ""
    return Session_Reader.safe_name(label or f"cut{int(idx)}")


def _animation_files(context):
    """
    The extracted animation files, wherever they actually are.

    Prefers the connected Animations folder, but falls back to the `anims`
    folder beside the session. Extraction always writes there, and the two
    used to be able to disagree: a run that extracted without connecting
    left the files on disk and every later step reporting "no animation
    files" while staring straight at them.
    """
    from . import Session_Paths, Session_Reader
    idx, nm = Session_Paths.shot_choice(context.scene)

    if idx is not None and int(idx) >= 0:
        safe = _shot_label(context, idx, nm)
        if safe:
            bases = []
            connected = Session_Paths.animations_dir(context.scene)
            if connected is not None:
                bases.append(Path(connected))
            session0 = Session_Paths.session_file(context.scene)
            if session0 is not None:
                bases.append(Session_Reader.default_out_dir(session0))
            for base in bases:
                # `base` may already BE the shot folder - it's whenever
                # ensure_extracted has just run - so try it before its child.
                for cand in ((base,) if base.name == safe else ()) + (base / safe,):
                    try:
                        hit = sorted(Path(cand).glob("*.dmx"))
                    except OSError:
                        hit = []
                    if hit:
                        return hit

    files = Session_Paths.list_animations(context.scene)

    #FALLING BACK TO A FOLDER THAT HOLDS EVERY CUT. This is what is left
    #when a shot is chosen and nothing has been extracted for it - the user
    #turned `extract_first` off, and the folder still holds a whole-session
    #extract from some earlier run. Handing all of it over is how shot 2
    #ended up importing shot 1's camera.
    #
    #Filter by the shot's OWN SET NAMES, which is what the extract names its
    #files after. Reading the session costs about 0.2 s and only happens on
    #this fallback, not on the normal path above.
    if files and idx is not None and int(idx) >= 0:
        try:
            session1 = Session_Paths.session_file(context.scene)
            info = Session_Reader.read_session(session1) if session1 else None
            shot, _note = (Session_Paths.resolve_shot(
                info["shots"], index=int(idx), name=nm or "")
                if info else (None, ""))
            if shot is not None:
                want = {Session_Reader.safe_name(a.name).lower()
                        for a in (shot.get("sets") or ())}
                keep = [f for f in files if f.stem.lower() in want]
                if keep and len(keep) != len(files):
                    print(f"[SESSION_STEP]  {len(files) - len(keep)} file(s) in "
                          f"{files[0].parent} belong to other cuts - using the "
                          f"{len(keep)} that are {shot.get('name')}'s. Run "
                          f"Extract, or leave 'Extract From Session First' on, "
                          f"to give this shot a folder of its own.")
                if keep:
                    files = keep
        except Exception as exc:                              # noqa: BLE001
            print(f"[SESSION_STEP]  could not scope files to the shot "
                  f"({exc}) - using the folder as found")

    if files:
        return files

    session = Session_Paths.session_file(context.scene)
    if session is None:
        return []
    fallback = Session_Reader.default_out_dir(session)
    if not fallback.is_dir():
        return []
    files = sorted(fallback.glob("*.dmx"))
    if files:
        #adopt it, so the panel and every later step agree from now on
        pr = Session_Paths.project(context)
        if pr is not None and not pr.animations_path:
            pr.animations_path = str(fallback)
            pr.scanned = False
        print(f"[SESSION_STEP]  using {fallback} ({len(files)} file(s))")
    return files


@Progress.jobbed("HoovyTools - Session Import")
def _routed(context, kinds, allow_proxy=False, **opts):
    """Run the orchestrator, restricted to *kinds*."""
    from . import Session_Orchestrator as SO
    files = _animation_files(context)
    if not files:
        raise RuntimeError(
            "No animation files found - neither in the connected Animations "
            "folder nor in an anims folder beside the session. Run "
            "3 Import Animations, or Extract Animations, first.")

    entries = SO.plan(files, context.scene, allow_proxy=allow_proxy)
    for e in entries:
        e["actions"] = [a for a in e["actions"]
                        if a in kinds or a == "SHAPEKEY_PROXY"]
    stats = SO.run(entries, allow_proxy=allow_proxy, **opts)
    #only count a file as "no matching rig" if this step was going to do
    #something with it. A camera extract lives in the same folder and has no
    #rig by nature, so every animation run ended on a red "1 file(s) had NO
    #MATCHING RIG - run step 1 first" that pointed at a file which was never
    #this step's business, and sent the user back to redo a step that worked.
    stats["unmatched"] = [e for e in entries
                          if e.get("unmatched") and e["actions"]]
    stats["files"] = len([e for e in entries if e["actions"]])

    # RE-ASSERT the SHOT'S RANGE, after the importers have run
    #
    # `ensure_extracted` sets it before them, and Blender Source Tools then
    # pushes `frame_end` out to cover whatever it just imported - which for a
    # session is every set's full span, not the cut's. Measured on shot1:
    # the shot ends at 312 and the range grew to 339, bc
    # `combine_rifle_ammo12` keeps keying past the cut
    #
    # Extending is right when nobody has said which cut this is. Once
    # somebody has, the cut is the answer and the leftover keys are not part
    # of it. Cheap and idempotent: four numbers and no file reading beyond
    # the session read it already does
    try:
        session2 = None
        from . import Session_Paths as _SP
        session2 = _SP.session_file(context.scene)
        if session2 is not None:
            apply_shot_frame_range(context, session2)
    except Exception as exc:                                  # noqa: BLE001
        print(f"[SESSION_STEP]  frame range not re-applied ({exc})")

    return stats


def _auto_split_cameras(context, force=False):
    """
    Split every camera whose name matches, if the Developer tab asked for it.
    Returns report lines; never raises.

    `force` ignores the toggle - that is the manual button, where the press IS
    the consent. The match string still applies, so the button and the
    automatic pass always agree about WHICH cameras they would touch.

    MATCHED ON THE SFM NAME FIRST, then the Blender names.

    The Blender objects are named after the DMX FILE stem, not after the camera
    - deliberately, because SFM calls nearly every camera "camera" and naming
    from the element would collapse a batch onto one object. So a camera the
    user named "hoovy" in SFM arrives in Blender as
    "2026-08-06 - v1 - scene2 - v10 - rescued anim", and matching on object
    names alone finds NOTHING. Measured on a real session: 287 strings
    containing "hoovy" in the file, none of them the camera's Blender name.

    Import_DMX_Camera therefore stamps `ht_sfm_name` on all three rig objects.
    Object names are still checked, so naming the FILE hoovy works too.

    Failures here are reported, never fatal: a camera that will not split is
    still a camera that imported, and losing the import over it would be a
    worse trade than leaving it unsplit.
    """
    from ..ui.Panel import settings as _panel_settings
    st = _panel_settings(context)
    if not st:
        return []
    if not force and not getattr(st, "auto_split_hoovy_camera", False):
        return []

    needle = (getattr(st, "auto_split_match", "") or "").strip().lower()
    if not needle:
        return ["Auto-split : skipped (no match string set)"]

    from ..tools import Utils_Camera_Fix_Camera as UC

    #collect roots first: splitting mutates the scene, so iterating
    #bpy.data.objects while it changes underneath is asking for trouble
    split_col = bpy.data.collections.get(UC.SPLIT_COLLECTION)

    roots = []
    for obj in list(bpy.data.objects):
        if obj.type != "CAMERA":
            continue
        # never RE-SPLIT A SPLIT. The shots are named "<orig>_cut_01", so they
        # still contain the needle - run this twice, or call it from two
        # places, and it would split the shots into shots
        if split_col is not None and obj.name in split_col.objects:
            continue
        root = UC._resolve_root(obj)
        if root is None:
            continue
        parts = [obj, root]
        if root.parent:
            parts.append(root.parent)
        names = []
        for o in parts:
            names.append(o.name)
            names.append(str(o.get("ht_sfm_name", "")))
            names.append(str(o.get("ht_source_file", "")))
        if not any(needle in n.lower() for n in names if n):
            continue
        if root.name not in [r.name for r in roots]:
            roots.append(root)

    if not roots:
        return [f"Auto-split : no camera matching '{needle}'"]

    lines, made, failed = [], 0, 0
    for root in roots:
        name = root.name
        try:
            res = UC.split_camera_cuts(root)
            if res.get("single"):
                lines.append(f"Auto-split : '{name}' -> 1 shot, left alone")
            else:
                made += res.get("shots", 0)
                lines.append(f"Auto-split : '{name}' -> {res.get('shots')} shot(s)")
        except Exception as exc:
            failed += 1
            lines.append(f"Auto-split : '{name}' FAILED - {exc}")
            print(f"[HT_SESSION]  auto-split failed on '{name}': "
                  f"{type(exc).__name__}: {exc}")
    if made:
        lines.append(f"Auto-split : {made} camera(s) in {UC.SPLIT_COLLECTION}")
    return lines


class HT_OT_update_rig_anim(Operator):
    """NO INPUT - the rig name rides on the button that pressed this

        Re-import ONE rig's animation from whatever is wired in

The button next to each rig in the Rigs roster. It finds this rig's
animation in the connected Animations folder - or extracts the connected
session fresh when the folder is empty or missing - and re-imports bone
animation and facial animation onto just this rig, leaving every other
rig alone.

Use it after re-saving the session in SFM: one press per changed
character instead of re-running step 3 over the whole scene"""
    bl_idname = "ht.update_rig_anim"
    bl_label = "Update Rig Animation"
    bl_options = {"UNDO"}

    rig_name: StringProperty()  # type: ignore

    def execute(self, context):
        from . import Session_Orchestrator as SO
        from . import Session_Paths
        from ..core.DMX_Analyzer import ANIMATION as DA_ANIM, SHAPEKEY as DA_SK

        arm = bpy.data.objects.get(self.rig_name)
        if arm is None or arm.type != 'ARMATURE':
            self.report({"ERROR"}, f"No armature named '{self.rig_name}'")
            return {"CANCELLED"}

        # Wire in: the connected animations folder first; when it's empty
        # or gone, a fresh extract of the connected session (which also
        # covers the temp-extract workflow, where the files evaporate when
        # Blender closes).
        files = _animation_files(context)
        if not files:
            session = Session_Paths.session_file(context.scene)
            if session is None:
                self.report({"ERROR"},
                            "No animation files and no session connected - "
                            "nothing to update from")
                return {"CANCELLED"}
            try:
                ensure_extracted(context, session)
            except Exception as exc:                          # noqa: BLE001
                self.report({"ERROR"}, f"Extract failed: {exc}")
                return {"CANCELLED"}
            files = _animation_files(context)
        if not files:
            self.report({"ERROR"}, "The extract produced no files")
            return {"CANCELLED"}

        entries = SO.plan(files, context.scene)
        mine = []
        for e in entries:
            if e.get("armature") is not arm:
                continue
            e["actions"] = [a for a in e["actions"]
                            if a in (DA_ANIM, DA_SK)]
            if e["actions"]:
                mine.append(e)
        if not mine:
            self.report({"WARNING"},
                        f"No animation file matches '{arm.name}' - "
                        f"instance numbers are stripped, so check the "
                        f"file names in the animations folder")
            return {"CANCELLED"}

        stats = SO.run(mine)
        lines = [f"Rig      : {arm.name}",
                 f"Files    : {len(mine)}",
                 f"Imported : {stats['imported']}"]
        if stats["failed"]:
            lines.append(f"Failed   : {stats['failed']}")
        _popup(context, "Update Rig Animation", lines,
               icon='FILE_REFRESH', key="update_rig",
               level=("WARNING" if stats["failed"] else "INFO"),
               operator=self)
        self.report({"WARNING" if stats["failed"] else "INFO"},
                    f"{arm.name}: {stats['imported']} imported"
                    + (f", {stats['failed']} failed" if stats["failed"]
                       else ""))
        return {"FINISHED"}


class HT_OT_split_matching_cameras(Operator):
    """Split every camera matching the Developer tab's name, right now

Same pass the session import runs, on demand. Use it when the take was
imported before the toggle was on, or when you want the split repeated
after re-importing.

Cameras already inside the split collection are skipped, so pressing it
twice does not split the shots into shots."""

    bl_idname = "ht.split_matching_cameras"
    bl_label = "Split Matching Cameras Now"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(o.type == "CAMERA" for o in bpy.data.objects)

    def execute(self, context):
        lines = _auto_split_cameras(context, force=True)
        if not lines:
            self.report({"WARNING"}, "Nothing to split")
            return {"CANCELLED"}
        for line in lines:
            print(f"[HT_SESSION]  {line}")
        made = [l for l in lines if "-> " in l and "shot" in l]
        _popup(context, "Split Matching Cameras", lines, icon='CON_CAMERASOLVER',
               key="step_cameras", level="INFO", operator=self)
        self.report({"INFO"}, f"{len(made)} camera take(s) split")
        return {"FINISHED"}


def _clear_imported_cameras():
    """
    Remove cameras a previous import created, so a re-run replaces.

    Scoped to the collections the camera IMPORTER owns. A camera the user
    built themselves is never in one of those, so it survives.

    SPLITS ARE DELIBERATELY NOT CLEARED. They used to be, because the splitter
    wrote into the importer's own collection and this set named it. Splitting
    is downstream work with edits hanging off it - markers bound to shot
    cameras, handles tuned by hand - and quietly deleting it because the take
    was re-imported is the kind of loss you only notice later. Splits now live
    in Utils_Camera_Fix_Camera.SPLIT_COLLECTION, which is not in this set;
    delete that collection by hand when you want them gone.
    """
    names = {"___HoovyTools Camera___", "___HoovyTools Cameras___"}
    removed = 0
    for col_name in names:
        col = bpy.data.collections.get(col_name)
        if col is None:
            continue
        for obj in list(col.objects):
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed += 1
            except Exception:
                pass
    return removed



def apply_shot_frame_range(context, session, info=None):
    """Set the scene range to the chosen shot's. Returns (start, end) or None."""
    from . import Session_Paths, Session_Reader
    scene = getattr(context, "scene", None) or bpy.context.scene
    idx, nm = Session_Paths.shot_choice(scene)
    if idx is None or int(idx) < 0:
        return None
    try:
        info = info or Session_Reader.read_session(session)
        shot, _note = Session_Paths.resolve_shot(info["shots"],
                                                 index=int(idx),
                                                 name=nm or "")
        if shot is None:
            return None
        fps = float(info["fps"] or 24.0)
        # 1.17.0: thru shot_timeline_frames - SFM's movie frames by
        # default (the shot list's own numbers), extract frames in RAW mode
        # One function for the range, the extract, the lights, the sounds
        # and the particles, so they cannot disagree
        start, end = Session_Reader.shot_timeline_frames(info["model"], shot,
                                                         fps)
        if end <= start:
            return None
        if start < 0:
            # Blender clamps frame_start at 0 - which is how the gothic
            # intro lost its first 173 frames in RAW placement. Say so
            print(f"[SESSION]  [WARN] {shot.get('name')} starts at frame "
                  f"{start} - Blender cannot start a scene below 0, the "
                  f"first {-start} frame(s) are outside the range. Shot "
                  f"Timing 'SFM Movie Time' (Developer tab) places it on "
                  f"{shot['frame_start']}-{shot['frame_end']}.")
        scene.frame_start = start
        scene.frame_end = end
        # put the playhead inside the range. At frame_start a character sits
        # in bind pose on the first key, which reads as "the animation did
        # not import" - the trap already recorded under TESTING.
        if not (start <= scene.frame_current <= end):
            scene.frame_current = start
        print(f"[SESSION]  scene frame range set to {start}-{end} "
              f"for {shot.get('name')} (movie frames "
              f"{shot['frame_start']}-{shot['frame_end']})")
        return start, end
    except Exception as exc:                                  # noqa: BLE001
        print(f"[SESSION]  could not set the frame range ({exc})")
        return None


@Progress.jobbed("HoovyTools - Extract Animation")
def ensure_extracted(context, session, rebase=False):
    """
    Make sure the animations folder holds this session's animation.

    Extraction is idempotent and fast, so re-running it is cheaper than
    asking the user whether they remembered to.
    """
    from . import Session_Reader, Session_Paths
    # THE ONE PLACE STEPS 3-5 GET THEIR FILES, so the shot filter goes here
    # and every one of them obeys it w/o knowing it exists
    idx, name = Session_Paths.shot_choice(context.scene if context else None)

    # A FOLDER YOU CHOSE is where THE EXTRACT GOES. Without this the extract
    # wrote to its own default and then pointed `animations_path` at it,
    # quietly undoing the choice on every run of steps 3, 4 and 5.
    pr0 = Session_Paths.project(context)
    out_dir = None
    if pr0 is not None and getattr(pr0, "animations_locked", False):
        chosen = Session_Paths.animations_dir(context.scene)
        if chosen is not None:
            out_dir = str(chosen)

    # CREATE UNPACKED ANIMS FOLDER, off. Extract into Blender's temp folder
    # instead of beside the session, so nothing is left in the user's
    # directory. Real files either way - the importer takes a path
    #
    # A STABLE NAME UNDER tempdir, not mkdtemp(). Steps 3, 4 and 5 each call
    # this, and a fresh random folder per call would re-extract the whole
    # session three times and leave two orphans behind. Keyed on the session
    # file so two sessions in one Blender run can't overwrite each other
    #
    # A LOCKED FOLDER STILL WINS. Somebody who went and chose a folder by
    # hand has said where they want the files more loudly than a default
    # switch has, so this only applies when nothing is locked
    unpacked = True if pr0 is None else bool(getattr(pr0, "unpack_anims", True))
    if out_dir is None and not unpacked:
        import hashlib
        key = hashlib.sha1(str(Path(session).resolve()).encode(
            "utf-8", "replace")).hexdigest()[:10]
        tmp = Path(bpy.app.tempdir) / f"ht_anims_{key}"
        tmp.mkdir(parents=True, exist_ok=True)
        out_dir = str(tmp)
        print(f"[SESSION]  anims folder off - extracting to {tmp}")

    if idx is not None and int(idx) >= 0:
        base = Path(out_dir) if out_dir else Session_Reader.default_out_dir(session)
        # THE SHOT'S own NAME, not its position - `shot{idx+1}` reads as the
        # picker's numbering, where the first cut is 1, so choosing the cut
        # SFM calls `shot1` produced a folder called `shot2`. See _shot_label
        out_dir = str(base / _shot_label(context, idx, name))

    from ..tools import Session_Visibility
    hidden = Session_Visibility.hidden_set_names(session, context.scene if context else None)
    r = Session_Reader.extract_session(session, rebase=rebase, out_dir=out_dir,
                                       shot_index=idx, shot_name=name,
                                       skip_names=hidden or None)
    r["skipped_hidden"] = sorted(hidden)
    if r.get("shot_note"):
        print(f"[SESSION]  {r['shot_note']}")

    # the scene follows the shot. Here rather than in each step, because this
    # is already "the one place steps 3-5 get their files" and the range has
    # to agree with them
    r["frame_range"] = apply_shot_frame_range(context, session,
                                              info=r.get("info"))
    # connect it too - extraction writing files that nothing points at is
    # how steps 4-7 ended up reporting "no animation files"
    pr = Session_Paths.project(context)
    if pr is not None:
        # POINT AT WHERE IT ACTUALLY WENT, LOCKED or not. The lock decides
        # which FOLDER the extract goes into; it can't also mean "and then
        # read a different one back". Leaving the pointer on the parent while
        # the files went into a per-shot subfolder would hand steps 3-5 every
        # shot again, which is the whole bug this change exists to stop.
        pr.animations_path = str(r["out_dir"])
        pr.scanned = False
    return r


# ─────────────────────────────────────────────────────────────────────────────
# 1  Models
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_step_models(Operator):
    """NO INPUT - runs on the session connected on the Main tab.

        Step 1 - import every model the session references

Reads the session, resolves each animation set's .mdl against the SFM
search paths, and brings it in through SourceIO. A model already in the
scene is skipped, so a second run does not double it, and
repeated until it is done, so a large session cannot hang the UI.

Armatures are renamed to the session's set name (scout1, not scout_ARM),
which is what every later step matches against. Each rig then gets the
rest pose SFM animated it in, from its reference .dmx in the Faulty Rigs
folder, and its eyes are wired to viewTarget.

STATIC PROPS get a bone built for them. A $staticprop model has exactly
one bone and SourceIO imports it as meshes only, so its animation would
have nothing to land on - a one-bone rig is created and the meshes
weighted to it. A static prop is rigid, so full weight is exact.
    """
    # BELOW the TOOLTIP CAP. Blender truncates an operator description
    # at 1023 characters, without a warning, mid-word. These paragraphs
    # were part of the docstring and were already being cut off before
    # anyone could read them, so they live here instead - kept, but out
    # of the tooltip's budget
    # Missing models are counted and named; they usually mean the .mdl isn't
    # under the configured usermod path. Nothing else in the pipeline works
    # until this has run
    #

    bl_idname = "ht.step_models"
    bl_label = "1  Import Models"
    # NO "REGISTER" - see the note in Report_UI/the constitution
    # REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    # touching any field in it RE-RUNS this operator. Re-running an
    # import re-reads the DMX and rebuilds every f-curve; nudging Scale
    # there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    # with the value you wanted is the safe way to change your mind
    bl_options = {"UNDO"}

    reads_session = True

    # PICKED, NOT CONNECTED. Set by the Tools drawer; empty everywhere else,
    # and empty means "use the session this .blend is wired to".
    pick_session: BoolProperty(default=False, options={"HIDDEN"})  # type: ignore
    filepath:    StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})  # type: ignore
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    def invoke(self, context, event):
        from .Session_Steps import pick_or_run
        return pick_or_run(self, context, event)

    fix_rigs: BoolProperty(  # type: ignore
        name="Fix Rig Rest Poses",
        description=("Give every imported rig the rest pose SFM animated it in, "
                     "from its reference .dmx in the Faulty Rigs folder - the "
                     "same as Source IO Help > Fix All Rig Rest Poses. Off: "
                     "SourceIO's own rest stays"),
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return True

    @Progress.jobbed_execute("SFM Session Importer - 1  Import Models")
    def execute(self, context):
        session = _session_for(self, context)
        if session is None:
            self.report({"ERROR"}, no_session_error(self))
            return {"CANCELLED"}
        try:
            r = import_models(context, session,
                              fix_rigs=self.fix_rigs)
        except Exception as exc:
            self.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}

        lines = [f"Models   : {r['imported']} imported "
                 ]
        if r["missing"]:
            lines.append(f"Missing  : {r['missing']} model file(s)")
            from .Import_Session import missing_lines
            lines += ["           " + ln for ln in missing_lines(
                r.get("missing_models", []), r.get("elsewhere", {}), r.get("searched", 0))]
        if self.fix_rigs:
            lines.append(f"Rigs     : {r['fixed']} rest pose(s) fixed")
            if r["no_reference"]:
                lines.append(f"           {r['no_reference']} had no "
                             f"reference DMX")
            if r["rig_errors"]:
                lines.append(f"           {r['rig_errors']} error(s)")
        lines.append("")
        lines.append("Next: 2 Import Animations.")
        _popup(context, "Import Models", lines, key="step_models",
               level=("WARNING" if r["missing"] else "INFO"), operator=self)
        self.report({"INFO"}, f"{r['imported']} model(s) imported")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# 3  Animations
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_step_animations(Operator):
    """NO INPUT - runs on the session connected on the Main tab.

        Step 2 - put the session's bone animation onto the rigs

Routes every extracted animation file to the armature it belongs to,
matching by name with SFM's instance numbers stripped.

Root motion is ON by default, so characters stand where the session puts
them rather than all at the origin.

Stepped keys are resampled onto whole frames: SFM writes a HOLD as two
keys a thousandth of a frame apart, and Blender evaluates only whole
frames, so a step otherwise lands between its own two keys and reads as
a soft ramp.

Run steps 1 and 2 first. A file that finds no rig is REPORTED, not
skipped quietly - "N file(s) had NO MATCHING RIG" means the models are
not in the scene yet, not that the animation is broken
        """
    bl_idname = "ht.step_animations"
    bl_label = "2  Import Animations"
    # NO "REGISTER" - see the note in Report_UI/the constitution
    # REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    # touching any field in it RE-RUNS this operator. Re-running an
    # import re-reads the DMX and rebuilds every f-curve; nudging Scale
    # there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    # with the value you wanted is the safe way to change your mind
    bl_options = {"UNDO"}

    reads_session = True

    # PICKED, NOT CONNECTED. Set by the Tools drawer; empty everywhere else,
    # and empty means "use the session this .blend is wired to".
    pick_session: BoolProperty(default=False, options={"HIDDEN"})  # type: ignore
    filepath:    StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})  # type: ignore
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    def invoke(self, context, event):
        from .Session_Steps import pick_or_run
        return pick_or_run(self, context, event)

    extract_first: BoolProperty(  # type: ignore
        name="Extract From Session First",
        description=("Pull the animation out of the session before "
                     "importing. Idempotent and fast, so leave it on"),
        default=True,
    )
    root_motion: BoolProperty(  # type: ignore
        name="Root Motion",
        description=("Key the game model's own transform onto a root empty "
                     "and parent the rig to it. This is what places a "
                     "character where the session puts it. Off imports bone "
                     "channels only, which is what a clean SMD export wants"),
        default=True,
    )
    anim_scale: FloatProperty(  # type: ignore
        name="Animation Scale",
        description="Multiply every location key. Full precision is kept",
        default=1.0, min=1e-6, soft_min=0.0001, soft_max=100.0,
        precision=6, step=1,
    )
    up_axis: StringProperty(  # type: ignore
        name="Up Axis",
        description=(
            "Which axis the source treats as up. FILE reads it out of the "
            "DMX, which SFM always sets to Y. Blender Source Tools would "
            "otherwise use a scene default of Z, and Z means no correction "
            "at all - the usual reason an import comes in rotated"),
        default='FILE',
    )
    stepped_keys: StringProperty(  # type: ignore
        name="Stepped Keys",
        description=(
            "AUTO / ALL / OFF. SFM keys off whole frames and writes a hold as "
            "two keys a thousandth of a frame apart, which Blender - which "
            "only evaluates whole frames - samples right between. AUTO snaps "
            "near-integer keys and resamples the curves that contain a step"),
        default='AUTO',
    )
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

    rebase: BoolProperty(  # type: ignore
        name="Rebase To Frame 0",
        description=("Start each animation at frame 0 instead of where it "
                     "sits on the session timeline. OFF keeps every set in "
                     "sync with the others, which is usually what you want"),
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return True

    @Progress.jobbed_execute("SFM Session Importer - 2  Import Animations")
    def execute(self, context):
        session = _session_for(self, context)
        lines = []
        if self.extract_first and session is not None:
            try:
                r = ensure_extracted(context, session, rebase=self.rebase)
                lines.append(f"Extracted: {len(r['written'])} file(s) -> "
                             f"{r['out_dir'].name}/")
            except Exception as exc:
                self.report({"ERROR"}, f"Extract failed: {exc}")
                return {"CANCELLED"}
        try:
            stats = _routed(context, {DA.ANIMATION},
                            add_root_helpers=self.root_motion,
                            anim_scale=self.anim_scale,
                            up_axis=self.up_axis,
                            stepped_keys=self.stepped_keys,
                            rot_mode=self.rot_mode)
        except Exception as exc:
            self.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}

        lines += [
            f"Files    : {stats['files']}",
            f"Imported : {stats['imported']}",
            f"Root     : {'on' if self.root_motion else 'OFF'}",
            f"Up axis  : {self.up_axis}",
            f"Stepped  : {self.stepped_keys}",
        ]
        if stats["failed"]:
            lines.append(f"Failed   : {stats['failed']}")
        if stats["unmatched"]:
            lines.append("")
            lines.append(f"{len(stats['unmatched'])} file(s) had NO MATCHING "
                         f"RIG.")
            lines.append("Run step 1 first.")
        _popup(context, "Import Animations", lines, key="step_animations",
               level=("WARNING" if (stats["failed"] or stats["unmatched"])
                      else "INFO"), operator=self)

        if stats["unmatched"] and not stats["imported"]:
            self.report({"ERROR"},
                        "Nothing imported - no rigs matched. Run 1 Import "
                        "Models first.")
            return {"FINISHED"}
        self.report({"INFO"}, f"{stats['imported']} animation(s) imported")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# 3  Shape Keys
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_step_shapekeys(Operator):
    """NO INPUT - runs on the session connected on the Main tab.

        Step 3 - put the session's facial animation onto the characters

Routes each flex file to its rig's meshes and runs the full shape key
pipeline, including the HWM localvar bake - the part that makes
combination controls fire. Without it a face barely moves.

Needs the model's .qc. Twelve TF2 ones ship in _QC Face Data; for any
other character set "QC Face Data (override)" in add-on preferences to a
folder of your own - it is searched first and the shipped twelve still
work. Without a QC the flex curves still import and only the bake is
skipped, with a line saying so.
    """
    # BELOW the TOOLTIP CAP. Blender truncates an operator description
    # at 1023 characters, without a warning, mid-word. These paragraphs
    # were part of the docstring and were already being cut off before
    # anyone could read them, so they live here instead - kept, but out
    # of the tooltip's budget
    # Run step 1 first. Facial data that finds no character is reported rather
    # than turned into a proxy: a screenful of proxy sliders and no animation
    # looks like the importer misfiring, when the real answer is that the rigs
    # are not there yet. The proxy is opt-in
    #

    bl_idname = "ht.step_shapekeys"
    bl_label = "3  Import Shape Keys"
    # NO "REGISTER" - see the note in Report_UI/the constitution
    # REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    # touching any field in it RE-RUNS this operator. Re-running an
    # import re-reads the DMX and rebuilds every f-curve; nudging Scale
    # there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    # with the value you wanted is the safe way to change your mind
    bl_options = {"UNDO"}

    reads_session = True

    # PICKED, NOT CONNECTED. Set by the Tools drawer; empty everywhere else,
    # and empty means "use the session this .blend is wired to".
    pick_session: BoolProperty(default=False, options={"HIDDEN"})  # type: ignore
    filepath:    StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})  # type: ignore
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    def invoke(self, context, event):
        from .Session_Steps import pick_or_run
        return pick_or_run(self, context, event)

    extract_first: BoolProperty(  # type: ignore
        name="Extract From Session First",
        description="Pull facial animation out of the session before importing",
        default=True,
    )
    bake_hwm: BoolProperty(  # type: ignore
        name="Bake HWM Localvars",
        description=(
            "Run the HWM localvar bake after importing the flex animation, "
            "the way a standalone Shape Keys import does. Without it the "
            "combination controls on an HWM face never fire, so the "
            "animation is there but the face barely moves"),
        default=True,
    )
    remove_drivers: BoolProperty(  # type: ignore
        name="Remove Existing Drivers",
        description="Strip shape key drivers before importing",
        default=True,
    )
    allow_proxy: BoolProperty(  # type: ignore
        name="Proxy If No Character",
        description=("Build a Shape Key Proxy for facial data that has no "
                     "mesh to land on. OFF by default: otherwise importing "
                     "before the models are in fills the scene with proxy "
                     "sliders and no animation"),
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return True

    @Progress.jobbed_execute("SFM Session Importer - 3  Import Shape Keys")
    def execute(self, context):
        session = _session_for(self, context)
        lines = []
        if self.extract_first and session is not None:
            try:
                r = ensure_extracted(context, session)
                lines.append(f"Extracted: {len(r['written'])} file(s)")
            except Exception as exc:
                self.report({"ERROR"}, f"Extract failed: {exc}")
                return {"CANCELLED"}
        try:
            stats = _routed(context, {DA.SHAPEKEY},
                            allow_proxy=self.allow_proxy,
                            bake_hwm=self.bake_hwm,
                            remove_drivers=self.remove_drivers)
        except Exception as exc:
            self.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}

        lines += [f"Files    : {stats['files']}",
                  f"Imported : {stats['imported']}",
                  f"HWM bake : {'on' if self.bake_hwm else 'OFF'}"]
        for name, kind, detail in stats["rows"]:
            if kind == "flex":
                lines.append(f"  {name[:26]:<28}{detail}")
        if stats["failed"]:
            lines.append(f"Failed   : {stats['failed']}")
        if stats["unmatched"]:
            lines.append("")
            lines.append(f"{len(stats['unmatched'])} had no character.")
            lines.append("Run step 1, or tick Proxy If No Character.")
        _popup(context, "Import Shape Keys", lines, icon='SHAPEKEY_DATA',
               key="step_shapekeys",
               level=("WARNING" if (stats["failed"] or stats["unmatched"])
                      else "INFO"), operator=self)
        self.report({"INFO"}, f"{stats['imported']} facial import(s)")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# 4  Cameras
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_step_cameras(Operator):
    """NO INPUT - runs on the session connected on the Main tab.

        Step 4 - build the session's cameras

Every camera set in the session becomes a Blender camera with its own
root and axis empties, in the camera collection.

The conversion is verified against 363 real SFM camera exports - median
roll 0.16 degrees, none near 90 - so if a shot looks wrong, check the
ROOT MOTION of what it is pointing at before suspecting the camera.

Focal length is deliberately about 5.8 degrees wider than SFM's stated
field of view; that is an old, kept fudge exposed as Lens Offset (mm).
Set it to 0 to match SFM exactly.

Camera sets carry no game model, so they are correctly skipped by the
animation step rather than reported as rigless
        """
    bl_idname = "ht.step_cameras"
    bl_label = "4  Import Cameras"
    # NO "REGISTER" - see the note in Report_UI/the constitution
    # REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    # touching any field in it RE-RUNS this operator. Re-running an
    # import re-reads the DMX and rebuilds every f-curve; nudging Scale
    # there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    # with the value you wanted is the safe way to change your mind
    bl_options = {"UNDO"}

    reads_session = True

    # PICKED, NOT CONNECTED. Set by the Tools drawer; empty everywhere else,
    # and empty means "use the session this .blend is wired to".
    pick_session: BoolProperty(default=False, options={"HIDDEN"})  # type: ignore
    filepath:    StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})  # type: ignore
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    def invoke(self, context, event):
        from .Session_Steps import pick_or_run
        return pick_or_run(self, context, event)

    extract_first: BoolProperty(  # type: ignore
        name="Extract From Session First",
        description="Pull camera animation out of the session before importing",
        default=True,
    )
    scale: FloatProperty(  # type: ignore
        name="Scale",
        description="World scale - match your model import scale",
        default=1.0, min=1e-6, soft_min=0.0001, soft_max=100.0,
        precision=6, step=1,
    )
    replace: BoolProperty(  # type: ignore
        name="Replace Existing Cameras",
        description=(
            "Delete the cameras a previous run imported before importing "
            "again, so running this twice REPLACES rather than piling up a "
            "second set. Only touches HoovyTools' own camera collections - "
            "cameras you made yourself are left alone"),
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return True

    @Progress.jobbed_execute("SFM Session Importer - 4  Import Cameras")
    def execute(self, context):
        session = _session_for(self, context)
        lines = []
        removed = 0
        if self.replace:
            removed = _clear_imported_cameras()
            if removed:
                lines.append(f"Replaced : {removed} existing camera object(s)")
        if self.extract_first and session is not None:
            try:
                ensure_extracted(context, session)
            except Exception as exc:
                self.report({"ERROR"}, f"Extract failed: {exc}")
                return {"CANCELLED"}
        try:
            stats = _routed(context, {DA.CAMERA}, camera_scale=self.scale)
        except Exception as exc:
            self.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}
        lines += [f"Files   : {stats['files']}",
                  f"Cameras : {stats['imported']}"]
        if stats["failed"]:
            lines.append(f"Failed  : {stats['failed']}")

        #developer tab > Session Automation. Off by default; when on, any
        #camera whose name matches is split the moment it lands, so a session
        #that always needs splitting stops being a two-step job
        lines += _auto_split_cameras(context)

        if session is not None and stats["imported"]:
            try:
                from ..tools import Session_Visibility, Layout_Builder
                from . import Session_Paths
                idx, nm = Session_Paths.shot_choice(context.scene)
                r = Session_Visibility.set_shot_camera(context, session,
                                                       shot_index=idx, shot_name=nm)
                lines += [ln for ln in Session_Visibility.report_lines(r)
                          if not ln.startswith(("Hidden", "Shown", "Not found"))]
                Layout_Builder.jump_to_session_camera(context)
            except Exception as exc:                          # noqa: BLE001
                lines.append(f"Camera  : could not pick the shot's camera ({exc})")

        _popup(context, "Import Cameras", lines, icon='CAMERA_DATA',
               key="step_cameras",
               level=("WARNING" if stats["failed"] else "INFO"),
               operator=self)
        self.report({"INFO"}, f"{stats['imported']} camera(s)")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# 6  Lights
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_step_lights(Operator):
    """NO INPUT - runs on the session connected on the Main tab.

        Step 6 - rebuild the session's lights as Blender spots

SFM stores every light as a DmeProjectedLight - 45 attributes,
essentially a spot. Intensity, colour, cone, shadows and the light's
KEYED MOVEMENT all come across; that movement lives on the light's own
transform rather than on the light element and is easy to miss (one
light here carries over 4,000 transform keys).

About 29 Source parameters have no honest Blender equivalent -
uberlight, attenuation, volumetrics, gobo textures - and are reported,
never silently dropped.

Brightness carries the SQUARE of the world scale, because a session at
Source scale is ~52x larger than the same scene in metres and Blender
falls off with the inverse square. Light aim is confirmed correct
        """
    bl_idname = "ht.step_lights"
    bl_label = "6  Import Lights"
    # NO "REGISTER" - see the note in Report_UI/the constitution
    # REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    # touching any field in it RE-RUNS this operator. Re-running an
    # import re-reads the DMX and rebuilds every f-curve; nudging Scale
    # there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    # with the value you wanted is the safe way to change your mind
    bl_options = {"UNDO"}

    reads_session = True

    # PICKED, NOT CONNECTED. Set by the Tools drawer; empty everywhere else,
    # and empty means "use the session this .blend is wired to".
    pick_session: BoolProperty(default=False, options={"HIDDEN"})  # type: ignore
    filepath:    StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})  # type: ignore
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    def invoke(self, context, event):
        from .Session_Steps import pick_or_run
        return pick_or_run(self, context, event)

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
    energy_scale: FloatProperty(  # type: ignore
        name="Energy Scale",
        description=("Source intensity is neither watts nor lumens, so there "
                     "is no correct conversion - this is a taste control"),
        default=1.0, min=0.0, soft_max=100.0, precision=4,
    )
    scale: FloatProperty(  # type: ignore
        name="Scale", description="World scale",
        default=1.0, min=1e-6, soft_min=0.0001, soft_max=100.0,
        precision=6, step=1,
    )
    do_animation: BoolProperty(  # type: ignore
        name="Import Animation",
        description="Key intensity, colour and cone where the session animates them",
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
    desaturate: FloatProperty(  # type: ignore
        name="Desaturate Factor",
        description=("How much of each light's colour saturation to keep. "
                     "1.0 = the session's exact colours; 0.6 default - "
                     "Source's lighting model washes colour out on the way "
                     "to the screen, so faithful colours read MORE saturated "
                     "in Blender than the same shot in SFM. Applied to the "
                     "static colour and every colour animation key alike"),
        # lock-step with Light_Import.DESATURATE_DEFAULT.
        default=0.6, min=0.0, max=1.0, precision=3,
    )
    volume_density: FloatProperty(  # type: ignore
        name="Volume Density",
        description=("Principled Volume density. The box is thousands of "
                     "units across and optical depth is density x distance, "
                     "so a little goes a very long way - 0.000015 matches "
                     "SFM's look, 0.005 was white soup"),
        # kept in lock-step with Light_Import.VOLUME_DENSITY - two entry
        # points, one look (the fix_quat_flips lesson: with two entry
        # points, the defaults are part of the interface)
        default=0.000015, min=0.0, soft_max=1.0, precision=6, step=0.1,
    )
    volume_anisotropy: FloatProperty(  # type: ignore
        name="Volume Anisotropy",
        description=("How much light scatters FORWARD. 0 is even fog; "
                     "0.28 keeps a beam readable without the starburst "
                     "0.745 used to paint around every light"),
        default=0.281364, min=-1.0, max=1.0, precision=3,
    )

    @classmethod
    def poll(cls, context):
        return True

    @Progress.jobbed_execute("SFM Session Importer - 6  Import Lights")
    def execute(self, context):
        from ..importers import Light_Import
        from . import Session_Paths
        session = _session_for(self, context)
        if session is None:
            self.report({"ERROR"}, no_session_error(self))
            return {"CANCELLED"}
        try:
            # the SHOT PICKER REACHES STEP 7 NOW. It never did: steps 3-5
            # get their filter from `ensure_extracted` and this step doesn't
            # go thru it, so every light in the file was imported whatever
            # cut was selected
            idx, nm = Session_Paths.shot_choice(context.scene)
            from ..tools import Session_Visibility
            hidden = Session_Visibility.hidden_set_names(session, context.scene)
            r = Light_Import.import_lights(
                session, scale=self.scale,
                energy_scale=self.energy_scale,
                unit_scale=self.unit_scale,
                do_animation=self.do_animation,
                volume_box=self.volume_box,
                volume_lights=self.volume_lights,
                volume_density=self.volume_density,
                volume_anisotropy=self.volume_anisotropy,
                shot_index=idx, shot_name=nm,
                desaturate_factor=self.desaturate,
                skip_names=hidden or None)
        except Exception as exc:
            if "No light elements" in str(exc):           # 3.0.9: nothing to import isn't a failure
                self.report({"INFO"}, "The session has no lights")
                return {"FINISHED"}
            self.report({"WARNING"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}
        lines = [f"Lights   : {r['count']}"
                 + (f"  of {r['in_file']} in the file"
                    if r.get('skipped_other_shots') else ""),
                 f"Keys     : {r['keyed']}",
                 f"Unmapped : {len(r['unmapped'])} Source parameter(s)"]
        if r.get("skipped_hidden"):
            lines.append(f"Hidden   : {len(r['skipped_hidden'])} light(s) SFM hides left out "
                         f"(Skip Hidden Objects): {', '.join(r['skipped_hidden'])}")
        if r.get("shot"):
            lines.append(f"Shot     : {r['shot']}"
                         + (f"  ({r['skipped_other_shots']} light(s) from "
                            f"other cuts left out)"
                            if r.get("skipped_other_shots") else ""))
        elif r.get("shot_note"):
            lines.append(f"Shot     : {r['shot_note']}")

        # SAY WHICH PROPERTIES THE SFM VALUES DRIVE, AND WHICH THEY DO NOT.
        # A property skipped because it's ANIMATED is the right outcome -
        # but silence would make it look like the driver simply failed
        skips = r.get("driver_skips") or {}
        if skips:
            kinds = {}
            for props in skips.values():
                for prop, why in props.items():
                    kinds.setdefault(why, set()).add(prop)
            for why, props in sorted(kinds.items()):
                lines.append(f"Drivers  : {', '.join(sorted(props))} "
                             f"- {why}")

        # SAY WHAT THE BOX DID, INCLUDING WHEN IT DID nothing. A volume that
        # silently failed to build looks exactly like a volume that built and
        # is too thin to see, and the two want opposite next moves.
        vol = r.get("volume") or {}
        if vol.get("object") is not None:
            lines.append("-" * 42)
            lines.append(f"Volume   : {vol['name']}  {vol['size'][0]:.0f} x "
                         f"{vol['size'][1]:.0f} x {vol['size'][2]:.0f}")
            lines.append(f"           density {vol['density']:g}, "
                         f"anisotropy {vol['anisotropy']:g}")
            if vol.get("eevee_end"):
                lines.append(f"           EEVEE volumetric range -> "
                             f"{vol['eevee_end']:.0f}")
            lines.append(f"Scatter  : {r['volume_on']} light(s) in, "
                         f"{r['volume_off']} out  ({r['volume_lights']})")
            if r.get("volume_lights") == "SFM" and not r.get("volume_on"):
                lines.append("           NOTHING will scatter - the session "
                             "marks no light volumetric.")
                lines.append("           Switch Lights In Volume to All.")
        elif self.volume_box:
            lines.append(f"Volume   : not built - {vol.get('reason')}")

        #ATTENUATION. The magnitudes are the interesting part and they are
        #not applied - see the note in Light_Import. Printed per distinct
        #value rather than per light, because ten lights with two values
        #between them is two facts, not ten
        at = r.get("attenuation") or {}
        if at:
            lines.append("-" * 42)
            pure = sum(1 for v in at.values() if v["pure_quadratic"])
            lines.append(f"Falloff  : {len(at)} light(s) got a Light Falloff "
                         f"node ({pure} pure quadratic)")
            mags = {}
            for nm, v in at.items():
                mags.setdefault(v["magnitude"], []).append(nm)
            for mag in sorted(mags):
                lines.append(f"           magnitude {mag:g} x{len(mags[mag])}")
            if len(mags) > 1:
                lines.append("           magnitudes differ between lights and")
                lines.append("           are NOT applied to energy - see the")
                lines.append("           note in Light_Import before changing")
            lines.append("           Cycles only; EEVEE ignores light nodes")
        _popup(context, "Import Lights", lines, icon='LIGHT_POINT',
               key="step_lights",
               level=("INFO" if r["count"] else "WARNING"), operator=self)
        self.report({"INFO"}, f"{r['count']} light(s)")
        return {"FINISHED"}


_CLASSES = (
    HT_OT_step_models,
    HT_OT_step_animations,
    HT_OT_step_shapekeys,
    HT_OT_step_cameras,
    HT_OT_split_matching_cameras,
    HT_OT_update_rig_anim,
    HT_OT_step_lights,
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
