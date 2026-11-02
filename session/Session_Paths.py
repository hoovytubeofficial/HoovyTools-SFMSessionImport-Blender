"""
Session_Paths.py  -  part of HoovyTools             [roadmap #4]
===============================================================

Where this .blend gets its DMX from.

    ANIMATIONS FOLDER    exported animation DMX files
    DMX / SESSION FOLDER the .dmx session itself, or the folder holding it

These are NOT global user preferences and they do not belong in a -paths
JSON. They are part of the CURRENT WORK, so they live on the Scene, which
means they are saved inside the .blend and come back when it is reopened.
One blend can track one SFM project and another blend a completely
different one, with no shared state to collide.

    Preferences (AddonPreferences)   where SFM itself is installed.
                                     One machine, one answer, global.

    Scene (here)                     which project this file is about.
                                     Per .blend, saved with it.

Once a folder is connected there is no hunting for it again. UPDATE
ANIMATIONS re-reads it: SFM changes, animations get re-exported, Blender
refreshes its side of the pipeline without a new file dialog.

WHY A SCENE PROPERTYGROUP AND NOT A CUSTOM PROP
===============================================
PointerProperty on Scene is saved in the .blend automatically, is typed,
and shows up in the UI with prop(). Raw ID custom properties would work
too but carry no descriptions, so the tooltips - which are the
documentation here - would have nowhere to live.
"""

import bpy
import os
from pathlib import Path
from bpy.types import Operator, PropertyGroup
from bpy.props import (StringProperty, PointerProperty, IntProperty,
                       BoolProperty, EnumProperty, CollectionProperty)


# ─────────────────────────────────────────────────────────────────────────────
# The stored project
# ─────────────────────────────────────────────────────────────────────────────

TIP = "\n\nTHIS FEATURE WAS ADDED IN VERSION 1.26.0 AND IS IN EXPERIMENTAL STAGE"

class HoovyToolsShot(PropertyGroup):
    """One cut, cached so the picker never re-reads the file.

    READING THE SESSION TO DRAW A MENU IS THE BUG THIS FIXES. The first picker
    built its enum from the file, and Blender calls an enum's item callback on
    every redraw of the dialog - so hovering across the list re-parsed a 17 MB
    DMX, and on the gothic session that means a dmxconvert round trip each
    time. The list is read ONCE, when you connect a session or press refresh,
    and lives here until the file underneath it changes.
    """
    name: StringProperty(default="")             # type: ignore
    frame_start: IntProperty(default=0)          # type: ignore
    frame_end: IntProperty(default=0)            # type: ignore
    set_count: IntProperty(default=0)            # type: ignore
    camera: StringProperty(default="")           # type: ignore
    # 3.0.0: CLIP or SLUG (a cut with no animation sets - SFM's placeholder)
    kind: StringProperty(default="CLIP")         # type: ignore


def _shot_index_changed(pr):
    i = int(pr.shot_index)
    name = pr.shots[i].name if 0 <= i < len(pr.shots) else ""
    if pr.shot_name != name:
        pr.shot_name = name


class HoovyToolsProject(PropertyGroup):
    animations_path: StringProperty(  # type: ignore
        name="Animations Folder",
        description=(
            "Folder holding this project's exported animation DMX files.\n"
            "Saved in this .blend, so reopening the project restores it. "
            "Another .blend can point at a completely different SFM project"),
        subtype="DIR_PATH",
        default="",
    )
    session_path: StringProperty(  # type: ignore
        name="Session / DMX Folder",
        description=(
            "This project's SFM session .dmx, or the folder holding it.\n"
            "Saved in this .blend alongside the animations folder"),
        subtype="FILE_PATH",
        default="",
    )

    # filled by UPDATE ANIMATIONS so the panel can show what it found
    # w/o touching the disk on every redraw.
    anim_count: IntProperty(default=-1)          # type: ignore
    anim_fps: StringProperty(default="")         # type: ignore
    # anim_status holds a FPS_Safety status CODE and nothing else - OK,
    # MISMATCH, MIXED, UNKNOWN. The human sentence goes in anim_message
    # These were one field once, and a free-text message written into it
    # reached STATUS_ICON[status] in a draw() and took the whole panel down
    # with a KeyError. A draw-time exception also kills the console, so a
    # bad value here isn't a cosmetic bug
    anim_status: StringProperty(default="")      # type: ignore
    anim_message: StringProperty(default="")     # type: ignore
    # the session's own frame rate, cached when it is connected so the
    # panel can show SFM vs Blender without reading the file every redraw.
    session_fps: StringProperty(default="")      # type: ignore
    session_sets: IntProperty(default=-1)        # type: ignore
    # SET BY HAND, SO STOP MOVING IT. `ensure_extracted` points
    # `animations_path` at wherever it just extracted, on every run of steps
    # 3, 4 and 5 - which silently undid anybody who chose a folder. When this
    # is on, the extract goes INTO the chosen folder instead of relocating
    # the pointer, which is what "override the one from the session" means
    animations_locked: BoolProperty(default=False)   # type: ignore
    # WHICH SHOT the import steps use. -1 is the whole session, which is
    # what everything did before this existed and what a one-shot session
    # means anyway. The NAME is stored beside the index so a session
    # re-saved with a cut inserted is noticed rather than silently
    # importing a different shot - see resolve_shot()
    # 3.0.0: also the shot LIST's active row - picking a row stores its name with it
    shot_index: IntProperty(default=-1, update=lambda self, _ctx: _shot_index_changed(self))  # type: ignore
    shot_name: StringProperty(default="")        # type: ignore
    # the cut list, cached. `shots_source` is the file it was read from, so a
    # stale list announces itself instead of quietly describing another
    # session's cuts.
    shots: CollectionProperty(type=HoovyToolsShot)   # type: ignore
    shots_source: StringProperty(default="")     # type: ignore

    unpack_anims: BoolProperty(  # type: ignore
        name="Create Anims Folders",
        description=(
            "Write the extracted animation .dmx files to an anims folder "
            "BESIDE THE SESSION, where they pile up in your elements "
            "folders. Off (the default): the same files go to Blender's "
            "temp folder instead and vanish when Blender exits - the "
            "import is identical either way"),
        default=False)

    shot_timing: EnumProperty(  # type: ignore
        name="Shot Timing",
        items=[
            ("MOVIE", "SFM Movie Time",
             "Every shot lands where SFM's timeline puts it: Blender frame = "
             "SFM movie time x fps (the viewport's left number). A shot with "
             "an offset - the gothic intro's starts at shot time -10.767 - "
             "no longer falls below frame 0, and the frame range is the "
             "shot list's own numbers.\n\nTHIS FEATURE WAS ADDED IN VERSION "
             "1.17.0 AND IS IN EXPERIMENTAL STAGE"),
            ("RAW", "Raw Clip Time",
             "Where every version before 1.17.0 put a shot: on its clips' "
             "raw time, usually five seconds after movie time - and BELOW "
             "frame 0 for a shot with a negative offset, where Blender "
             "cannot play it. Only for re-importing into a .blend built "
             "before 1.17.0"),
        ],
        default="MOVIE")

    session_textures: EnumProperty(  # type: ignore
        name="Textures",
        items=[
            ("FULL", "Full", "Every texture at its full size - what every version before 1.21.0 did.\n\nTHIS FEATURE WAS ADDED IN VERSION 1.21.0 AND IS IN EXPERIMENTAL STAGE"),
            ("PROXY", "Proxy", "Each material gets a small copy of its own texture (the VTF's mip at 64 px or "
             "less) - the look survives, the import is quick and a saved .blend stays small. 1.23.0: its materials are "
             "named <vmt>_proxy_V<n>; a second copy of the model shares them. 1.25.0: a texture made with no small "
             "mip (your Glamrock textures, one 4096 px picture each) is sampled down to 64 px too, never packed at "
             "full size; one image per texture, whichever materials use it.\n\nTHIS FEATURE WAS ADDED IN VERSION 1.21.0 AND IS IN EXPERIMENTAL STAGE"),
            ("NONE", "None", "No textures at all - the quickest; for work that needs only the rigs and bodies "
             "(transposing animation to send back to SFM). 1.23.0: its materials are named <vmt>_proxy_V<n>.\n\nTHIS FEATURE WAS ADDED IN VERSION 1.21.0 AND IS IN EXPERIMENTAL STAGE"),
        ],
        default="FULL")

    skip_hidden: BoolProperty(  # type: ignore
        name="Skip Hidden Objects",
        description="Leave out what SFM hides: a model, light or camera whose eye is off in the shot - itself or a "
                    "group above it - is not imported at all (no model, no animation, no camera, no light). Off = "
                    "every set comes in and the Visibility step hides what SFM hides, as before. A whole-session "
                    "import leaves a set out only when every cut that has it hides it" + TIP,
        default=False)

    scanned: BoolProperty(default=False)         # type: ignore


def skip_hidden(scene=None):
    """1.26.0: is Skip Hidden Objects on for this scene"""
    scene = scene or getattr(bpy.context, "scene", None)
    pr = getattr(scene, "ht_project", None) if scene is not None else None
    return bool(getattr(pr, "skip_hidden", False))


def config_folder(kind):
    """The first existing folder the config ladder gives for `kind`, or None.

    ONE CALL, AND IT NEVER RAISES. Every file browser in the add-on wants to
    open somewhere sensible and none of them should carry a try/except and a
    guess about SFM's folder layout - that knowledge is in the config now.
    """
    try:
        from ..core import config
        from . import Import_Session
        return config.folder(kind, Import_Session.usermod_bases(),
                             Import_Session._DEFAULT_SFM_USERMOD)
    except Exception:                                         # noqa: BLE001
        return None


def project(context=None):
    context = context or bpy.context
    return getattr(context.scene, "ht_project", None)


def _resolved(raw):
    if not raw:
        return None
    try:
        p = Path(bpy.path.abspath(raw))
    except Exception:
        return None
    return p


def animations_dir(scene=None):
    """The connected animations folder as a Path, or None."""
    scene = scene or bpy.context.scene
    pr = getattr(scene, "ht_project", None)
    if pr is None:
        return None
    p = _resolved(pr.animations_path)
    return p if (p and p.is_dir()) else None


def session_file(scene=None):
    """The connected session .dmx as a Path, or None."""
    scene = scene or bpy.context.scene
    pr = getattr(scene, "ht_project", None)
    if pr is None:
        return None
    p = _resolved(pr.session_path)
    if p is None:
        return None
    if p.is_file():
        return p
    return None


def session_dir(scene=None):
    """Folder holding the session, whether a file or a folder was given."""
    scene = scene or bpy.context.scene
    pr = getattr(scene, "ht_project", None)
    if pr is None:
        return None
    p = _resolved(pr.session_path)
    if p is None:
        return None
    if p.is_dir():
        return p
    if p.is_file():
        return p.parent
    return None


def list_animations(scene=None):
    """Every .dmx in the connected animations folder, sorted. Never recurses."""
    d = animations_dir(scene)
    if d is None:
        return []
    try:
        return sorted(d.glob("*.dmx"))
    except OSError:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Connect
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_connect_animations(Operator):
    """PICK folder (animation) - the folder holding this .blend's exported
        animation .dmx files. A FOLDER, not a file

        Point this .blend at the folder holding its exported animation .dmx files

Stored in the scene and saved with the file, so a .blend remembers where
its animations came from. The folder-at-a-time importers and the numbered
session steps all read it.

Connecting also lets the panel check the folder's frame rate against the
scene BEFORE anything is imported, which is the cheapest moment to catch
a mismatch.

A session extraction sets this for you, pointing at the anims folder it
just wrote"""
    bl_idname = "ht.connect_animations"
    bl_label = "Connect Animations Folder"
    bl_options = {"REGISTER", "UNDO"}

    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})  # type: ignore
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    def invoke(self, context, event):
        pr = project(context)
        if pr and pr.animations_path:
            self.directory = pr.animations_path
        else:
            d = config_folder("animations")
            if d is not None:
                self.directory = str(d)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        pr = project(context)
        if pr is None:
            self.report({"ERROR"}, "Scene project settings unavailable")
            return {"CANCELLED"}
        pr.animations_path = self.directory
        pr.animations_locked = True
        n = len(list_animations(context.scene))
        pr.scanned = False
        print(f"[HT_PATHS]  animations folder -> {self.directory} ({n} dmx)")
        self.report({"INFO"}, f"Connected animations folder - {n} DMX file(s)")
        return {"FINISHED"}



def set_world_black(scene):
    """Make the scene's world pure black. Returns True if anything changed."""
    if scene is None:
        return False
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world
    changed = False
    try:
        if tuple(world.color) != (0.0, 0.0, 0.0):
            world.color = (0.0, 0.0, 0.0)
            changed = True
    except Exception:
        pass
    try:
        if world.use_nodes and world.node_tree is not None:
            for n in world.node_tree.nodes:
                if n.bl_idname == "ShaderNodeBackground":
                    col = n.inputs.get("Color")
                    if col is not None and tuple(col.default_value)[:3] != (0.0, 0.0, 0.0):
                        col.default_value = (0.0, 0.0, 0.0, 1.0)
                        changed = True
    except Exception:
        pass
    return changed


class HT_OT_connect_session(Operator):
    """PICK .dmx (session) - the file SFM saved, usually under
        usermod\\elements\\sessions

        Point this .blend at the SFM session .dmx it belongs to

Stored in the scene and saved with the file, so a .blend remembers its
session. Every numbered step reads it, which is why they are greyed out
until this is set.

One .blend, one SFM project. Connecting a session also lets the panel
report its frame rate and warn before a mismatch bends your keys"""
    bl_idname = "ht.connect_session"
    bl_label = "Connect Session DMX"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})  # type: ignore

    world_black: BoolProperty(  # type: ignore
        name="Black World",
        description=(
            "Set the World colour to pure black when the session is "
            "connected. SFM has no ambient sky: everything you see there is "
            "lit by the lights in the session. Blender ships a grey world at "
            "0.05, which lifts every shadow slightly and flattens the "
            "contrast - so a faithfully imported shot still does not look "
            "like the SFM render, for a reason that is nowhere in the "
            "import. Turn this off to keep whatever world the .blend has"),
        default=True,
    )

    def invoke(self, context, event):
        pr = project(context)
        if pr and pr.session_path:
            self.filepath = pr.session_path
        else:
            #open where SFM keeps sessions - or, 3.0.0, the folder you picked sessions from 3+ times
            #(core/start_folders.py; the config ladder's elements folder until then)
            try:
                from ..core import start_folders
                self.filepath = start_folders.start("session") or self.filepath
            except Exception:
                pass
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        from ..core import Progress, start_folders
        try:
            start_folders.remember_file("session", self.filepath)
        except Exception:                                     # noqa: BLE001
            pass
        with Progress.job("SFM Session Importer - Loading DMX Session", phase_total=3):
            return self._execute(context)

    def _execute(self, context):
        from ..core import Progress
        pr = project(context)
        if pr is None:
            self.report({"ERROR"}, "Scene project settings unavailable")
            return {"CANCELLED"}
        pr.session_path = self.filepath
        pr.session_fps = ""
        pr.session_sets = -1
        print(f"[HT_PATHS]  session -> {self.filepath}")
        # 3.0.8: the SFM this .dmx sits in becomes a searched install
        try:
            from .Import_Session import adopt_install
            adopted = adopt_install(self.filepath)
            if adopted:
                self.report({"INFO"}, adopted)
        except Exception as exc:                              # noqa: BLE001
            print(f"[HT_PATHS]  adopt install failed: {exc}")

        if self.world_black:
            blacked = set_world_black(context.scene)
            if blacked:
                print("[HT_PATHS]  world set to black - SFM has no ambient sky")

        # cheap now that the loader is O(1) - read the session's own frame
        # rate and set count so the panel has something true to show.
        try:
            from . import Session_Reader
            Progress.phase("1 Reading " + Path(self.filepath).name, number=1)
            info = Session_Reader.read_session(self.filepath)
            Progress.phase("2 Shots", number=2)
            pr.session_fps = f"{info['fps']:g}"
            pr.session_sets = len(info["sets"])

            # the CUT LIST COMES FREE FROM this READ. `read_session` already
            # built it, so caching it here is the difference between the
            # picker costing nothing and the picker re-parsing a 17 MB DMX
            # every time the mouse crosses it
            pr.shots.clear()
            pr.shots_source = ""
            for sh in info["shots"]:
                item = pr.shots.add()
                item.name = sh["name"]
                item.frame_start = int(sh["frame_start"])
                item.frame_end = int(sh["frame_end"])
                item.set_count = len(sh["sets"])
                item.camera = sh["camera"] or ""
                item.kind = "SLUG" if sh.get("slug") else "CLIP"
            pr.shots_source = str(self.filepath)
            Progress.phase("3 Frame rate", number=3)
            # a new session is not the old one's shot 4.
            set_shot_choice(context.scene, SHOT_ALL, "")

            try:
                st = getattr(context.scene, "ht_panel", None)
                if st is None or getattr(st, "auto_fps", True):
                    from . import FPS_Safety
                    cur = FPS_Safety.scene_fps(context.scene)
                    if abs(cur - float(info["fps"])) > 1e-6:
                        FPS_Safety.set_scene_fps(context.scene, info["fps"])
                        print(f"[HT_PATHS]  scene frame rate {cur:g} -> "
                              f"{info['fps']:g} (auto, from the session)")
            except Exception as exc:                          # noqa: BLE001
                print(f"[HT_PATHS]  auto frame rate failed: {exc}")

            for line in Session_Reader.report_lines(info, max_sets=8):
                print(f"[HT_PATHS]  {line}")
            self.report({"INFO"},
                        f"{len(info['sets'])} set(s), {info['fps']:g} fps, "
                        f"{len(info['shots'])} shot(s)")
        except Exception as exc:
            print(f"[HT_PATHS]  session summary unavailable: {exc}")
            self.report({"INFO"}, "Session connected")
        return {"FINISHED"}


class HT_OT_clear_project_paths(Operator):
    """Forget the session and animations folder this .blend is connected to

Clears the stored paths only. Nothing in the scene is touched - no
objects, no animation, no imported data. Use it when a .blend has been
copied to a new project and should not keep pointing at the old one"""
    bl_idname = "ht.clear_project_paths"
    bl_label = "Disconnect Sources"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        pr = project(context)
        if pr is None:
            return {"CANCELLED"}
        pr.animations_path = ""
        pr.animations_locked = False
        pr.session_path = ""
        pr.anim_count = -1
        pr.anim_fps = ""
        pr.anim_status = ""
        pr.anim_message = ""
        pr.session_fps = ""
        pr.session_sets = -1
        pr.scanned = False
        # the cut list belonged to the session that just got disconnected
        pr.shots.clear()
        pr.shots_source = ""
        set_shot_choice(context.scene, SHOT_ALL, "")
        self.report({"INFO"}, "Sources disconnected")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# Update
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_update_animations(Operator):
    """Re-read the connected animations folder and report what changed

Rescans the folder, re-counts the files and re-checks their frame rate
against the scene without importing anything.

Use it after extracting a session, after adding files by hand, or when
the panel's counts look stale. It is the read-only half of the import:
nothing in the scene is touched"""
    bl_idname = "ht.update_animations"
    bl_label = "Update Animations"
    bl_options = {"REGISTER"}

    def execute(self, context):
        pr = project(context)
        if pr is None:
            self.report({"ERROR"}, "Scene project settings unavailable")
            return {"CANCELLED"}

        from ..session import FPS_Safety
        folder = animations_dir(context.scene)
        if folder is None:
            pr.scanned = True
            pr.anim_count = -1
            pr.anim_status = FPS_Safety.UNKNOWN
            pr.anim_message = "no folder connected"
            pr.anim_fps = ""
            self.report({"WARNING"}, "No animations folder connected")
            return {"CANCELLED"}

        files = list_animations(context.scene)
        pr.anim_count = len(files)

        r = FPS_Safety.check_folder(folder, context.scene)
        pr.anim_status = r["status"]
        pr.anim_message = r["message"]
        pr.anim_fps = f"{r['source_fps']:g}" if r["source_fps"] else ""
        pr.scanned = True

        print(f"\n[HT_UPDATE]  {folder}")
        print(f"[HT_UPDATE]  {len(files)} DMX file(s)")
        print(f"[HT_UPDATE]  fps {r['status']}: {r['message']}")

        level = "WARNING" if r["status"] in ("MISMATCH", "MIXED") else "INFO"
        self.report({level},
                    f"{len(files)} animation(s) - {r['message']}")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# Draw
# ─────────────────────────────────────────────────────────────────────────────

def _path_row(col, pr, attr, connect_op, label, icon, resolved):
    row = col.row(align=True)
    row.label(text=label, icon=icon)
    ok = resolved is not None
    tick = row.row(align=True)
    tick.alignment = 'RIGHT'
    tick.label(text="", icon='CHECKMARK' if ok else 'X')

    value = getattr(pr, attr, "")
    body = col.column(align=True)
    body.scale_y = 0.85
    if value:
        s = str(resolved) if resolved else bpy.path.abspath(value)
        body.label(text=s if len(s) <= 44 else "..." + s[-41:])
        if not ok:
            warn = body.row()
            warn.alert = True
            warn.label(text="path no longer exists", icon='ERROR')
    else:
        body.label(text="not connected")
    col.operator(connect_op, text="Change" if value else "Connect",
                 icon='FILE_FOLDER')


def draw_sources(layout, context, compact=False):
    """The SOURCE CONNECTIONS block. Read-only - every change is an operator."""
    pr = project(context)
    box = layout.box()
    if pr is None:
        box.alert = True
        box.label(text="Scene project settings unavailable", icon='ERROR')
        return

    box.label(text="Source Connections", icon='LINKED')

    col = box.column(align=True)
    _path_row(col, pr, "animations_path", "ht.connect_animations",
              "Animations", 'ANIM', animations_dir(context.scene))
    col.separator()
    _path_row(col, pr, "session_path", "ht.connect_session",
              "Session DMX", 'SCENE_DATA', session_file(context.scene))

    if not compact:
        info = box.column(align=True)
        info.scale_y = 0.8
        if pr.scanned and pr.anim_count >= 0:
            info.label(text=f"{pr.anim_count} animation file(s) found",
                       icon='FILE_TICK')
        else:
            info.label(text="Run Update Animations to scan", icon='INFO')

    row = box.row(align=True)
    row.scale_y = 1.1
    row.operator("ht.update_animations", text="Update Animations",
                 icon='FILE_REFRESH')
    if pr.animations_path or pr.session_path:
        row.operator("ht.clear_project_paths", text="", icon='X')


# ──────────────────────────────────────────────────────────────────────────────
# the chosen shot
# ──────────────────────────────────────────────────────────────────────────────
#
# ONE CHOICE, ON the SCENE, READ BY EVERY STEP. Not a property on each import
# operator: there are five of them and they would each have to be told again,
# and the failure mode of getting it wrong - models from shot 3 with animation
# from shot 7 - is silent and looks like a broken importer rather than like a
# mismatched setting
#
# STORED AS INDEX and NAME, and both ARE CHECKED. The index is what the shot
# list is ordered by and the name is what the user actually chose. If the
# session is re-saved with a shot inserted, the index now points at a
# different cut - so `resolve_shot()` prefers the index only when the name
# still matches there, falls back to finding the name, and says so
#
# -1 MEANS the whole SESSION, which is what everything did before this
# existed and what a one-shot session means anyway

SHOT_ALL = -1


def shot_choice(scene=None):
    """(index, name) of the chosen shot. index -1 means the whole session."""
    scene = scene or bpy.context.scene
    pr = getattr(scene, "ht_project", None)
    if pr is None:
        return SHOT_ALL, ""
    return int(getattr(pr, "shot_index", SHOT_ALL)), \
        getattr(pr, "shot_name", "") or ""


def set_shot_choice(scene, index, name=""):
    pr = getattr(scene, "ht_project", None)
    if pr is None:
        return
    pr.shot_index = int(index)
    pr.shot_name = name or ""


def resolve_shot(shot_list, index=None, name=None, scene=None):
    """The chosen shot out of `shot_list`, or None for the whole session.

    Returns (shot_or_None, note). `note` is empty when the choice resolved
    cleanly and says what happened when it did not - a shot list that has
    changed under the choice is worth a line in the report, not a silent
    substitution.
    """
    if index is None or name is None:
        i, n = shot_choice(scene)
        index = i if index is None else index
        name = n if name is None else name

    if index is None or int(index) < 0:
        return None, ""
    index = int(index)
    if not shot_list:
        return None, "no shots in this session - importing all of it"

    if 0 <= index < len(shot_list):
        s = shot_list[index]
        if not name or s["name"] == name:
            return s, ""
        # index still valid but it's a different cut now
        for other in shot_list:
            if other["name"] == name:
                return other, (f"shot {index + 1} is now '{s['name']}' - used "
                               f"'{name}' at {other['index'] + 1} instead")
        return s, (f"shot '{name}' is gone - used shot {index + 1} "
                   f"'{s['name']}' instead")

    for other in shot_list:
        if other["name"] == name:
            return other, (f"shot {index + 1} no longer exists - used "
                           f"'{name}' at {other['index'] + 1}")
    return None, (f"shot {index + 1} '{name}' is not in this session any more "
                  f"- importing the whole thing")


def shot_set_names(shot):
    """The animation set names in a shot, or None meaning 'no filter'."""
    if shot is None:
        return None
    return set(shot.get("set_names") or ())


def _shot_items(self, context):
    """Enum items for the picker, built from the session on the disk."""
    items = [("-1", "Whole session", "Import every shot, as before", 'SEQUENCE', 0)]
    for s in _PICKER_CACHE.get("shots", []):
        span = s["frame_end"] - s["frame_start"]
        items.append((
            str(s["index"]),
            f"{s['index'] + 1}. {s['name']}",
            f"frames {s['frame_start']}-{s['frame_end']} ({span}) - "
            f"{len(s['sets'])} animation set(s)"
            + (f", camera {s['camera']}" if s["camera"] else ""),
            'SEQUENCE',
            s["index"] + 1,
        ))
    return items


# the enum callback can't read the file - Blender calls it on every redraw of
# the dialog, and the gothic session takes a dmxconvert round trip. So the
# operator reads once in invoke() and the callback serves that
_PICKER_CACHE = {"path": None, "shots": []}


def cached_shots(scene=None):
    """The cached cut list, and whether it matches the connected session."""
    scene = scene or bpy.context.scene
    pr = getattr(scene, "ht_project", None)
    if pr is None:
        return [], False
    sess = session_file(scene)
    fresh = bool(sess) and pr.shots_source == str(sess)
    return list(pr.shots), fresh


def refresh_shots(context, quiet=False):
    """Read the session once and cache its cuts. Returns (count, error)."""
    scene = context.scene
    pr = getattr(scene, "ht_project", None)
    if pr is None:
        return 0, "no project on this scene"
    path = session_file(scene)
    pr.shots.clear()
    pr.shots_source = ""
    if path is None:
        return 0, "no session connected"
    try:
        from . import Session_Reader
        model = Session_Reader.load_session_model(path)
        fps = Session_Reader.session_fps(model.root) or 24.0
        shots = Session_Reader.shots(model, fps)
    except Exception as exc:                                  # noqa: BLE001
        if not quiet:
            print(f"[SESSION]  could not read shots: {exc}")
        return 0, str(exc)
    for s in shots:
        item = pr.shots.add()
        item.name = s["name"]
        item.frame_start = int(s["frame_start"])
        item.frame_end = int(s["frame_end"])
        item.set_count = len(s["sets"])
        item.camera = s["camera"] or ""
        item.kind = "SLUG" if s.get("slug") else "CLIP"
    pr.shots_source = str(path)

    # A CHOICE that no LONGER POINTS ANYWHERE is DROPPED HERE, not silently
    # carried into an import. resolve_shot() would catch it later and say so,
    # but the panel should not be showing "Shot 12" for a file with 4 cuts
    idx, name = shot_choice(scene)
    if idx >= 0 and not (0 <= idx < len(shots) and shots[idx]["name"] == name):
        match = next((s for s in shots if s["name"] == name), None)
        set_shot_choice(scene, match["index"] if match else SHOT_ALL,
                        match["name"] if match else "")
    return len(shots), None


class HT_OT_refresh_shots(Operator):
    """Read the connected session's cut list again

The list is cached so that picking a shot costs nothing - the first picker
rebuilt its menu from the file and Blender calls that on every redraw, so
hovering across the shots re-parsed the whole DMX each time.

Press this when the session has been re-saved in SFM behind Blender's back.
Connecting a session reads it automatically"""
    bl_idname = "ht.refresh_shots"
    bl_label = "Read Shots"

    @classmethod
    def poll(cls, context):
        return session_file(context.scene) is not None

    def execute(self, context):
        n, err = refresh_shots(context)
        if err:
            self.report({"ERROR"}, f"Could not read shots: {err}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{n} shot(s)")
        return {"FINISHED"}


class HT_OT_set_shot(Operator):
    """Import this shot only"""
    bl_idname = "ht.set_shot"
    bl_label = "Set Shot"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)               # type: ignore

    @classmethod
    def description(cls, context, properties):
        """THE TOOLTIP IS THE LABEL. A grid of numbers is compact enough to
        hold fifty cuts and tells you nothing about any of them, so the name,
        the frame range and the set count arrive on hover - which is where
        you were already pointing."""
        i = properties.index
        if i < 0:
            return ("Import every shot, as before.\n\n"
                    "On a multi-shot film that means every cut is loaded on "
                    "top of every other one")
        shots, _fresh = cached_shots(context.scene)
        if not (0 <= i < len(shots)):
            return "This shot is not in the cached list - press Read Shots"
        s = shots[i]
        span = s.frame_end - s.frame_start
        out = (f"{i + 1}.  {s.name}\n\n"
               f"frames {s.frame_start} - {s.frame_end}  ({span} frames)\n"
               f"{s.set_count} animation set(s)")
        if s.camera:
            out += f"\ncamera: {s.camera}"
        if not s.set_count:
            out += "\n\nNo animation sets - a slug or a title card"
        return out

    def execute(self, context):
        shots, _fresh = cached_shots(context.scene)
        if self.index < 0 or not (0 <= self.index < len(shots)):
            set_shot_choice(context.scene, SHOT_ALL, "")
            self.report({"INFO"}, "Importing the whole session")
            return {"FINISHED"}
        s = shots[self.index]
        set_shot_choice(context.scene, self.index, s.name)
        self.report({"INFO"},
                    f"Shot {self.index + 1} '{s.name}' - frames "
                    f"{s.frame_start}-{s.frame_end}, {s.set_count} set(s)")
        return {"FINISHED"}


def draw_shot_grid(layout, context, icon_id=None):
    """EVERY SHOT, BY NAME, ALL OF THEM. No scrolling list:
    one button per cut - its number, its name, slug or frame count beside it - Whole Session above them, and the
    pressed one is what IMPORT imports. Hover a shot for its frames, sets and camera."""
    ico = icon_id or (lambda _key, fallback: {"icon": fallback})
    shots, fresh = cached_shots(context.scene)
    idx, _name = shot_choice(context.scene)
    if not shots:
        layout.operator("ht.refresh_shots", text="Read Shots", icon='FILE_REFRESH')
        return

    col = layout.column(align=True)
    head = col.row(align=True)
    head.operator("ht.set_shot", text="Whole Session", depress=(idx < 0),
                  **ico("shots", 'SEQ_SEQUENCER')).index = -1
    again = head.row(align=True)
    again.alert = not fresh                       # the list was read from another session file
    again.operator("ht.refresh_shots", text="", icon='FILE_REFRESH')
    col.separator(factor=0.4)
    for i, s in enumerate(shots):
        slug = s.kind == "SLUG"
        row = col.row(align=True)
        row.operator("ht.set_shot", text="%d  %s" % (i + 1, s.name), depress=(i == idx),
                     **ico(*(("shot_slug", 'SEQ_STRIP_META') if slug else ("shots", 'SEQUENCE')))).index = i
        tag = row.row(align=True)
        tag.ui_units_x = 2.4
        tag.enabled = False
        tag.label(text="slug" if slug else "%d f" % max(0, s.frame_end - s.frame_start))


class HT_OT_pick_shot(Operator):
    """Choose which SHOT of the session the import steps use

An SFM session is a film and a film is a list of cuts. Each shot carries
its OWN animation sets - the same character appears once per shot, as a
separate element with its own channels - so importing the whole session
loads every cut on top of every other one. Measured on a real 17-shot
film: 706 animation set elements in the file, 21 to 31 per shot.

Pick a shot and every step obeys it: models, rig fixes, animation, shape
keys, cameras, sounds and particles. Pick "Whole session" for the old
behaviour, which is also what a one-shot session means.

Reads the session when you press it, so the list is what is in the file
right now"""
    bl_idname = "ht.pick_shot"
    bl_label = "Choose Shot"
    bl_options = {"REGISTER", "UNDO"}

    shot: EnumProperty(name="Shot", items=_shot_items)  # type: ignore

    @classmethod
    def poll(cls, context):
        return session_file(context.scene) is not None

    def invoke(self, context, event):
        path = session_file(context.scene)
        try:
            from . import Session_Reader
            model = Session_Reader.load_session_model(path)
            fps = Session_Reader.session_fps(model.root) or 24.0
            _PICKER_CACHE["shots"] = Session_Reader.shots(model, fps)
            _PICKER_CACHE["path"] = str(path)
        except Exception as exc:                              # noqa: BLE001
            self.report({"ERROR"}, f"Could not read the session: {exc}")
            return {"CANCELLED"}

        shots = _PICKER_CACHE["shots"]
        if len(shots) <= 1:
            # nothing to choose. Say so rather than opening a dialog with one
            # option in it - a session with one shot is the whole session
            set_shot_choice(context.scene, SHOT_ALL, "")
            self.report({"INFO"},
                        f"'{path.name}' has one shot - nothing to pick, "
                        f"importing it imports that shot")
            return {"FINISHED"}

        index, _name = shot_choice(context.scene)
        self.shot = str(index if -1 <= index < len(shots) else -1)
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "shot")
        shots = _PICKER_CACHE["shots"]
        try:
            i = int(self.shot)
        except ValueError:
            i = -1
        info = col.column(align=True)
        info.scale_y = 0.85
        if i < 0:
            total = sum(len(s["sets"]) for s in shots)
            info.label(text=f"{len(shots)} shot(s), {total} animation set(s) "
                            f"in total.", icon='INFO')
            info.label(text="Every cut is imported on top of every other one.")
        elif 0 <= i < len(shots):
            s = shots[i]
            info.label(text=f"frames {s['frame_start']} - {s['frame_end']}  "
                            f"({s['frame_end'] - s['frame_start']} frames)",
                       icon='TIME')
            info.label(text=f"{len(s['sets'])} animation set(s)"
                            + (f", camera {s['camera']}" if s["camera"] else ""))
            if not s["sets"]:
                warn = col.row()
                warn.alert = True
                warn.label(text="This shot has no animation sets - a slug or "
                                "a title card.", icon='ERROR')

    def execute(self, context):
        shots = _PICKER_CACHE["shots"]
        try:
            i = int(self.shot)
        except ValueError:
            i = SHOT_ALL
        if i < 0 or not (0 <= i < len(shots)):
            set_shot_choice(context.scene, SHOT_ALL, "")
            self.report({"INFO"}, "Importing the whole session")
            return {"FINISHED"}
        s = shots[i]
        set_shot_choice(context.scene, s["index"], s["name"])
        self.report({"INFO"},
                    f"Shot {s['index'] + 1} '{s['name']}' - frames "
                    f"{s['frame_start']}-{s['frame_end']}, "
                    f"{len(s['sets'])} set(s)")
        return {"FINISHED"}


class HT_OT_clear_shot(Operator):
    """Go back to importing the whole session"""
    bl_idname = "ht.clear_shot"
    bl_label = "Whole Session"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        set_shot_choice(context.scene, SHOT_ALL, "")
        self.report({"INFO"}, "Importing the whole session")
        return {"FINISHED"}


_CLASSES = (
    HoovyToolsShot,
    HoovyToolsProject,
    HT_OT_refresh_shots,
    HT_OT_set_shot,
    HT_OT_pick_shot,
    HT_OT_clear_shot,
    HT_OT_connect_animations,
    HT_OT_connect_session,
    HT_OT_clear_project_paths,
    HT_OT_update_animations,
)


def register(icon_id_fn=None):
    for cls in _CLASSES:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)
    bpy.types.Scene.ht_project = PointerProperty(type=HoovyToolsProject)


def unregister():
    try:
        del bpy.types.Scene.ht_project
    except Exception:
        pass
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
