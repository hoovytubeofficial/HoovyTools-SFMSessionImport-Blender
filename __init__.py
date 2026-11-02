"""
SFM Session Importer  -  SFM sessions, models, animations and cameras into Blender

THE LAYOUT, AND WHAT THE UNDERSCORES MEAN
=========================================
    name        REQUIRED. The add-on does not start without it.
    _name       OPTIONAL. Shipped, but the add-on runs if you delete it.
    __name      DEVELOPMENT ONLY. Never shipped.

    __init__.py         this file - bl_info, menus, icons, registration
    core/               shared plumbing; knows about nothing else
    session/            the SFM session pipeline, the eight numbered steps
    importers/          one module per thing importable on its own
    tools/              utilities that act on an already-built scene
    ui/                 the sidebar panel and the in-addon roadmap
    SST/                a bundled subset of Blender Source Tools

    images/             custom panel icons, colour-coded. REQUIRED - the
                        panel is built around them
    experimental/       work in progress. NO underscore: it is imported
                        at registration, not lazily. Still wrapped in a
                        try/except, so deleting it prints a note rather
                        than raising - but the add-on does reach for it
    _config/            three JSON files, one job each:
                          _startupconfig.json   ours, rewritten every launch
                          customizedconfig.json yours, and it wins
                          user_paths.json       the wiring slots you set
                          _popupvariables.json  which reports open a dialog
    _QC Face Data/      QC files the HWM face bake reads; _Generated/ inside
                        holds the ones written from imported models (3.0.0)
    _Faulty Rigs/       reference DMX files the rig fixer reads rest poses from

THE LAYERING RULE: `core` reaches nowhere, `ui` reaches everywhere, and the
three in between only reach downwards. If a module in `core/` ever imports
from `session/`, `importers/` or `tools/`, that is the rule breaking.

    grep -rnE "from [.][.](session|importers|tools|ui)" core/

is the whole check, and it earns its keep: it caught FPS_Safety sitting in
`core` while reaching into `session` for the project paths. Matching the scene
to a session's frame rate is session knowledge, so FPS_Safety moved rather than
the rule bending.
"""

bl_info = {
    "name":        "SFM Session Importer",
    "description": "SFM sessions, models, animations, cameras, lights, sounds and particles into Blender",
    "author":      "Kajetan (HoovyTube)",
    "version":     (3, 0, 10),
    "blender":     (5, 0, 1),
    "location":    "File > Import > Source Engine (SFM Session Importer) + 3D View sidebar (N) > HoovyTools",
    "category":    "Import-Export",
}

import bpy
import bpy.utils.previews
from pathlib import Path
from bpy.types import AddonPreferences
from bpy.props import StringProperty, BoolProperty, EnumProperty
from . import SST

# one LINE PER PACKAGE. What each one is for is in its own __init__.py; the
# layering rule is that `core` knows about nothing, `ui` knows about
# everything, and the three in between only reach downwards
from .core import (Report_UI, Common_Props, DMX_Analyzer,
                   anim_compat, paths, config, user_paths, sources,
                   console_mark)
from .session import (Import_Session, Session_Paths, Session_Reader,
                      FPS_Safety,
                      Session_Steps, Session_Orchestrator, Session_Particles,
                      Import_Session_Sounds, Session_Map)
from .importers import (Import_DMX_Animation, Import_DMX_Camera,
                        Import_Shape_Keys, Import_MDL, Light_Import,
                        Import_Animations, Import_Camera_Animations,
                        Import_Shape_Key_Animations, Import_Materials)
from .tools import (Camera_Tools, ShapeKey_Proxy, Utils_Shape_Keys, Utils_MDL,
                    Utils_Camera_Fix_Camera, Utils_Misc, Layout_Builder,
                    Camera_Bone_Rig, Euler_Output, Scene_Offset,
                    Session_Visibility)
from .ui import Panel, Developer

# OPTIONAL, and THAT IS ENFORCED RATHER THAN DOCUMENTED. A folder whose name
# starts with a single underscore is one the add-on runs w/o, so deleting
# `experimental/` has to be a supported thing to do - not a traceback on
# startup. Hence the guard, not a plain import
try:
    from .experimental import Playground, Session_Locks
    _HAS_EXPERIMENTAL = True
except Exception as _exc:                                   # noqa: BLE001
    Playground = Session_Locks = None
    _HAS_EXPERIMENTAL = False
    print(f"[HoovyTools]  experimental/ not loaded ({_exc}) - "
          f"optional, everything else works")


# ──────────────────────────────────────────────────────────────────────────────
# addon preferences
# ──────────────────────────────────────────────────────────────────────────────

class HoovyToolsPreferences(AddonPreferences):
    """Where SFM is, and where the two optional data sets are.

    THE DATA FOLDERS ARE OVERRIDABLE BECAUSE THEIR CONTENTS ARE THE POINT.
    `_QC Face Data` ships with twelve TF2 QCs; anyone importing a session
    built on a custom character has to add their own, and editing files
    INSIDE an installed add-on means losing them the next time the add-on is
    updated. So both folders take an override that is searched FIRST and the
    shipped set stays as the fallback - add one QC, keep the other twelve.

    A blank override is not an error and not "off". Every one of these
    resolves to a sensible default when empty, which is why none of them are
    required to import a session on a stock install.
    """

    bl_idname = __name__

    sfm_usermod_path: StringProperty(
        name        = "SFM Usermod Path",
        description = "Path to SourceFilmmaker/game/usermod - must contain gameinfo.txt",
        default     = r"C:\Program Files (x86)\Steam\steamapps\common\SourceFilmmaker\game\usermod",
        subtype     = "DIR_PATH",
    )

    find_sfm_on_all_drives: BoolProperty(
        name        = "Look for SFM on every drive",
        description = (
            "Also search the SFM installs on the other drives (C:, D:, E:, F: ...) "
            "in the usual Steam folders, after the ones set here. A session made "
            "with models from an older install on another drive then still finds "
            "them. The SFM folder a loaded .dmx sits in is picked up by itself "
            "either way. ADDED IN VERSION 3.0.8"
        ),
        default     = True,
    )

    scan_game_mounts: BoolProperty(
        name        = "Scan all mod folders under game/",
        description = (
            "Also search every mod folder next to usermod, not only the ones "
            "gameinfo.txt lists. A stock gameinfo.txt does not mention "
            "game/workshop at all, so Workshop models, sounds and particles "
            "were reported as missing when they were installed. Scanned "
            "folders are searched AFTER everything gameinfo.txt lists, so "
            "this can add a place to look but never change which copy of a "
            "model wins"
        ),
        default     = True,
    )

    dmxconvert_path: StringProperty(
        name        = "dmxconvert.exe folder",
        description = (
            "Folder holding Valve's dmxconvert.exe, used when a session is not "
            "UTF-8 and has to be converted before it can be read. Blank finds "
            "it next to whichever SFM install is configured; set it to borrow "
            "the copy from a Source SDK install instead"
        ),
        default     = "",
        subtype     = "DIR_PATH",
    )

    qc_face_data_path: StringProperty(
        name        = "QC Face Data (override)",
        description = (
            "Extra folder of .qc files for the HWM face bake, searched BEFORE "
            "the set that ships in the add-on's _QC Face Data folder. Put your "
            "own character's .qc here and the twelve shipped TF2 ones still "
            "work. Leave blank to use only the shipped set"
        ),
        default     = "",
        subtype     = "DIR_PATH",
    )

    faulty_rigs_path: StringProperty(
        name        = "Faulty Rigs (override)",
        description = (
            "Extra folder of reference .dmx files the rig fixer reads rest "
            "poses from, searched BEFORE the set that ships in the add-on's "
            "_Faulty Rigs folder. Leave blank to use only the shipped set"
        ),
        default     = "",
        subtype     = "DIR_PATH",
    )

    use_sourceio: BoolProperty(
        name        = "Use SourceIO",
        description = (
            "What imports a model - the session import's models and Import Model on Engine: Auto.\n"
            "On: SourceIO's own MDL importer, when it is installed and enabled (otherwise HoovyTools').\n"
            "Off: HoovyTools' importer, carried inside this add-on - SourceIO is never called for models"
        ),
        default     = False,
    )

    model_importer: EnumProperty(
        name        = "Model Importer",
        description = ("Which importer brings models in. Maps always go through SourceIO.\n\n"
                       "THIS FEATURE WAS ADDED IN VERSION 3.0.0 AND IS IN EXPERIMENTAL STAGE"),
        items       = [("HOOVYTOOLS", "HoovyTools", "HoovyTools' own MDL importer, carried inside this add-on - "
                                                    "SourceIO does not need to be installed", 'NONE', 0),
                       ("SOURCEIO", "SourceIO", "SourceIO's MDL importer, when it is installed and enabled",
                        'NONE', 1)],
        get         = lambda self: 1 if self.use_sourceio else 0,
        set         = lambda self, value: setattr(self, "use_sourceio", value == 1),
    )

    faulty_rigs_sfm_path: StringProperty(
        name        = "Faulty Rigs (SFM-side)",
        description = (
            "Third search location for reference DMX files - the copy that "
            "lives in the SFM plugins tree. Underscored or not, both names "
            "are accepted"
        ),
        default     = (
            r"C:\Program Files (x86)\Steam\steamapps\common\SourceFilmmaker"
            r"\game\usermod\plugins\___SFM to Blender Session Importer\_Dev\_Faulty Rigs"
        ),
        subtype     = "DIR_PATH",
    )

    def draw(self, context):
        layout = self.layout
        from . import Import_Session
        active = Import_Session.get_gameinfo_base()

        box = layout.box()
        box.label(text="Source Filmmaker", icon="FILE_FOLDER")
        col = box.column(align=True)
        col.prop(self, "sfm_usermod_path", text="")
        status = col.row()
        status.enabled = False
        status.label(text=str(active) if active.exists() else "not found - pick the usermod folder",
                     icon="CHECKMARK" if active.exists() else "ERROR")
        box.prop(self, "scan_game_mounts")
        box.prop(self, "find_sfm_on_all_drives")

        box = layout.box()
        box.label(text="Models", icon="MESH_DATA")
        row = box.row(align=True)
        row.prop(self, "model_importer", expand=True)

        box = layout.box()
        box.label(text="Data Folders", icon="FILE_CACHE")
        col = box.column()
        col.prop(self, "qc_face_data_path")
        col.prop(self, "faulty_rigs_path")
        col.prop(self, "faulty_rigs_sfm_path")


def _pref_folder_row(col, prefs, prop_name, shipped, pattern):
    """One override field plus what each of the two folders actually holds.

    A COUNT, NOT A TICK. "Folder exists" is not the question anyone has -
    they have just pointed this at a folder and want to know whether the
    add-on can see the files in it. An override that resolves to an empty
    folder looks identical to a working one unless the count is on screen.
    """
    col.separator()
    col.prop(prefs, prop_name)
    info = col.column(align=True)
    info.scale_y = 0.8

    raw = getattr(prefs, prop_name, "").strip()
    if raw:
        override = Path(bpy.path.abspath(raw))
        if override.is_dir():
            n = len(list(override.glob(pattern)))
            info.label(text=f"override: {n} {pattern} file(s)",
                       icon="CHECKMARK" if n else "ERROR")
        else:
            row = info.row()
            row.alert = True
            row.label(text=f"override folder not found: {override}", icon="ERROR")

    if shipped.is_dir():
        info.label(text=f"shipped ({shipped.name}): "
                        f"{len(list(shipped.glob(pattern)))} {pattern} file(s)",
                   icon="CHECKMARK")
    else:
        info.label(text=f"shipped folder absent: {shipped.name}", icon="INFO")


# ──────────────────────────────────────────────────────────────────────────────
# custom icons
# ──────────────────────────────────────────────────────────────────────────────

# `images` is optional: every lookup falls back to a stock Blender icon, so
# a build without the folder looks plainer and works identically.
# core/paths.py knows where it's, and accepts the old `_Icons` name too
_ICONS_DIR = paths.icons()

#SOURCE-STYLE ICONS: foreground colour identifies the file/utility type
#Models: crowbar green; lights: muted yellow; animation: muted blue;
#cameras: cyan; shape keys: orange; sounds: violet; particles: red;
#complete DMX sessions: saturated orange. Miscellaneous types retain
#the add-on's associations in a muted Source-inspired palette
#
#Background shape identifies input scope: folder inputs use a folder;
#DMX-session operations use a solid-centre gear; other tools use circles
#Circle colours further distinguish single-file, selected-data, batch,
#configuration, report and navigation contexts. Status variants retain
#their subject colour and add a green check, amber warning or red cross
#
#Every key resolves to images/<key>.png. Generated art, prompts, colour
#legend and usage map live in images/source-style; originals in images/old
_ICON_KEYS = (
    'hoovy_logo', 'session_load', 'import_session',
    'import_session_models', 'import_animations', 'import_camera_animations',
    'import_shape_key_animations', 'import_session_sounds', 'import_lights',
    'import_particles', 'rig_fixer', 'fix_rig',
    'fix_eye_constraints', 'remove_drivers', 'symmetrize_shapekeys',
    'util_import_shape_keys', 'bake_localvars', 'import_mdl',
    'import_dmx_anim', 'import_dmx_camera', 'import_shape_keys',
    'import_lights_one', 'analyze_dmx', 'split_camera',
    'utils_camera', 'camera_handles', 'camera_shot_report',
    'source_engine_utils', 'utils_shape_keys', 'utils_mdl',
    'utils_misc', 'organize_scene', 'reduce_lag',
    'session_report', 'rescan_animations', 'fps_report',
    'experimental', 'shapekey_proxy', 'mdl_sequences',
    'print_success', 'print_error', 'print_paths',
    'print_roadmap', 'print_behavior', 'purge_model_only',
    'strip_all_animation', 'delete_euler_spins', 'vertexlit_fix',
    'developer_mode', 'dev_folders', 'dev_config',
    'dev_console', 'auto_split_camera', 'auto_split_run',
    'logs_section', 'log_on', 'log_off',
    'log_folder', 'skydome_section', 'register_skydome',
    'sec_elements', 'sec_framerate', 'sec_scene',
    'sec_batch', 'sec_utils', 'sec_organizers',
    'sec_rigs', 'sec_cleanup', 'sec_wiring',
    'sec_popups', 'shots', 'anims_folder',
    'layout_default', 'layout_two', 'layout_three',
    'engine_default', 'engine_eevee', 'engine_cycles',
    'sec_sourceio', 'sio_rig_fixer', 'sio_fix_rig',
    'sio_fix_eyes', 'status_ok', 'status_warn',
    'status_bad', 'session_animations', 'session_camera_animations',
    'session_shape_key_animations', 'import_pcf', 'offset_everything',
    'match_sfm_visibility', 'render_presets', 'shot_timing',
    # 3.0.0: the tabs, Main Tools, HoovyTools Importers (MDL / VMT / VTF), the slug shots
    'tab_main', 'tab_tools', 'tab_dev', 'sec_main_tools', 'sec_hoovy_importers',
    'import_vmt', 'import_vtf', 'shot_slug',
    'import_map',
)


_pcoll = None


def _load_icons():
    global _pcoll
    _pcoll = bpy.utils.previews.new()
    if not _ICONS_DIR.is_dir():
        print(f"[HoovyTools]  images/ not found at {_ICONS_DIR} - using Blender defaults")
        return
    # ONE LINE, not ONE PER ICON. Twenty-five "icon loaded" lines and three
    # "icon missing" lines on every startup buried anything that mattered
    # A missing icon isn't an error - every lookup falls back to a stock
    # Blender one - so it's worth a mention, not a paragraph
    loaded, missing = [], []
    for key in _ICON_KEYS:
        path = _ICONS_DIR / f"{key}.png"
        if path.exists():
            _pcoll.load(key, str(path), "IMAGE")
            loaded.append(key)
        else:
            missing.append(f"{key}.png")
    print(f"[HoovyTools]  icons: {len(loaded)} loaded"
          + (f", {len(missing)} missing ({', '.join(missing)}) - "
             f"stock icons used instead" if missing else ""))


def _unload_icons():
    global _pcoll
    if _pcoll is not None:
        bpy.utils.previews.remove(_pcoll)
        _pcoll = None


def icon_id(key: str, fallback: str = "NONE") -> dict:
    if _pcoll is not None and key in _pcoll:
        return {"icon_value": _pcoll[key].icon_id}
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
# MENUS
# ──────────────────────────────────────────────────────────────────────────────

class HT_MT_session_submenu(bpy.types.Menu):
    bl_idname = "HT_MT_session_submenu"
    bl_label  = "Import Session"

    def draw(self, context):
        # THE WHOLE WORKFLOW, 1 TO 7, NUMBERED THE SAME AS THE MAIN TAB.
        # Sounds and particles used to sit in the standalone block one level
        # up, next to Import MDL - which put two SESSION importers among the
        # one-file importers and left this submenu stopping at 5. Everything
        # in here takes a session .dmx; that is what makes it a submenu.
        Import_Session.draw_submenu(self.layout)
        Import_Animations.draw_session_entry(self.layout)
        Import_Camera_Animations.draw_session_entry(self.layout)
        Import_Shape_Key_Animations.draw_session_entry(self.layout)
        Import_Session_Sounds.draw_session_entry(self.layout)
        Light_Import.draw_session_entry(self.layout)
        Session_Particles.draw_session_entry(self.layout)


class HT_MT_utils_submenu(bpy.types.Menu):
    bl_idname = "HT_MT_utils_submenu"
    bl_label  = "Source Engine Utils"

    def draw(self, context):
        Utils_Shape_Keys.draw_utils_shapekeys_entry(self.layout)
        Utils_MDL.draw_utils_mdl_entry(self.layout)
        Utils_Camera_Fix_Camera.draw_utils_camera_entry(self.layout)
        self.layout.operator("ht.rig_cameras_on_bones", icon='BONE_DATA')
        self.layout.operator("ht.rotations_to_euler", icon='ORIENTATION_GIMBAL')
        Utils_Misc.draw_utils_misc_entry(self.layout)


class HT_MT_hoovytools_utils(bpy.types.Menu):
    """Everything in File > Import that is not one of the five main importers."""
    bl_idname = "HT_MT_hoovytools_utils"
    bl_label  = "SFM Session Importer (Utils)"

    def draw(self, context):
        self.layout.menu(
            HT_MT_session_submenu.bl_idname,
            **icon_id("import_session", "SCENE_DATA"),
        )
        self.layout.menu(
            HT_MT_utils_submenu.bl_idname,
            **icon_id("source_engine_utils", "TOOL_SETTINGS"),
        )
        self.layout.separator()
        if _HAS_EXPERIMENTAL:
            Playground.draw_menu_item(self.layout)
        Developer.draw_developer_entry(self.layout)


class HT_MT_import_submenu(bpy.types.Menu):
    bl_idname = "HT_MT_import_submenu"
    bl_label  = "Source Engine (SFM Session Importer)"

    def draw(self, context):
        Panel.draw_main_tool_buttons(self.layout)
        self.layout.separator()
        self.layout.menu(
            HT_MT_hoovytools_utils.bl_idname,
            **icon_id("hoovy_logo", "TOOL_SETTINGS"),
        )


def _draw_ht_submenu(self, context):
    self.layout.menu(
        HT_MT_import_submenu.bl_idname,
        **icon_id("hoovy_logo", "TOOL_SETTINGS"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# register / unregister
# ──────────────────────────────────────────────────────────────────────────────

def _write_startup_config():
    """Rewrite `_config/_startupconfig.json` from the configured installs.

    ON EVERY LAUNCH, AND IT OVERWRITES. That is only safe because nothing the
    user types is ever in that file - theirs is `customizedconfig.json` beside
    it, and the generated one says so in its own first line. Regenerating it
    is the point: change the usermod path and the file that documents where
    the add-on looks is correct again without anyone having to remember.

    Never fatal. An add-on folder can be read-only - installed by an admin, or
    on a share - and that is a reason to skip a documentation file, not a
    reason to leave someone with no add-on.
    """
    try:
        from .session import Import_Session
        bases = Import_Session.usermod_bases()
        default = Import_Session._DEFAULT_SFM_USERMOD
        p = config.write_startup(bases, default)
        if p is not None:
            print(f"[HoovyTools]  {p.name}: {len(bases) or 1} install(s), "
                  f"{len(config.KINDS)} folder kinds"
                  + ("  (+ customizedconfig.json)"
                     if config.custom_path().is_file() else ""))
    except Exception as exc:                                  # noqa: BLE001
        print(f"[HoovyTools]  startup config skipped ({exc})")


def register():
    # first: every line printed from here on starts with [SFM Session Importer] (3.0.0)
    console_mark.install()
    bpy.utils.register_class(HoovyToolsPreferences)

    # ensure import_scene.smd is available — uses BST if present, SST bundle otherwise
    SST.ensure_smd_importer()

    _load_icons()
    Report_UI.register(icon_id_fn=icon_id)
    sources.register(icon_id_fn=icon_id)
    Import_Session.register(icon_id_fn=icon_id)
    Import_DMX_Animation.register(icon_id_fn=icon_id)
    Import_DMX_Camera.register(icon_id_fn=icon_id)
    Import_Animations.register(icon_id_fn=icon_id)
    Import_Camera_Animations.register(icon_id_fn=icon_id)
    Import_Shape_Keys.register(icon_id_fn=icon_id)
    Utils_Shape_Keys.register(icon_id_fn=icon_id)
    Utils_MDL.register(icon_id_fn=icon_id)
    Utils_Camera_Fix_Camera.register(icon_id_fn=icon_id)
    Camera_Bone_Rig.register()
    Euler_Output.register()
    Scene_Offset.register()
    Session_Visibility.register()
    Utils_Misc.register(icon_id_fn=icon_id)
    Layout_Builder.register(icon_id_fn=icon_id)
    Import_MDL.register(icon_id_fn=icon_id)
    Import_Materials.register(icon_id_fn=icon_id)                     #3.0.0: Import VMT / Import VTF
    Import_Shape_Key_Animations.register(icon_id_fn=icon_id)
    Import_Session_Sounds.register(icon_id_fn=icon_id)
    DMX_Analyzer.register(icon_id_fn=icon_id)
    Session_Paths.register(icon_id_fn=icon_id)
    FPS_Safety.register(icon_id_fn=icon_id)
    Camera_Tools.register(icon_id_fn=icon_id)
    ShapeKey_Proxy.register(icon_id_fn=icon_id)
    Session_Orchestrator.register(icon_id_fn=icon_id)
    Light_Import.register(icon_id_fn=icon_id)
    Session_Reader.register(icon_id_fn=icon_id)
    Session_Steps.register(icon_id_fn=icon_id)
    Session_Particles.register(icon_id_fn=icon_id)
    Session_Map.register()                                            #3.0.0: 8 Import Map
    if _HAS_EXPERIMENTAL:
        Playground.register(icon_id_fn=icon_id)
        Session_Locks.register(icon_id_fn=icon_id)
    Developer.register(icon_id_fn=icon_id)
    Panel.register(icon_id_fn=icon_id)
    # after Panel: ht_panel exists only now, so the stored layout choice
    # could not land during Layout_Builder.register above.
    try:
        Layout_Builder.ensure_synced(bpy.context.scene)
    except Exception:                                         # noqa: BLE001
        pass
    bpy.utils.register_class(HT_MT_session_submenu)
    bpy.utils.register_class(HT_MT_utils_submenu)
    bpy.utils.register_class(HT_MT_hoovytools_utils)
    bpy.utils.register_class(HT_MT_import_submenu)
    bpy.types.TOPBAR_MT_file_import.append(_draw_ht_submenu)

    # LAST, bc it asks Import_Session where the installs are and that
    # reads the preferences, which only exist once the class above is
    # registered.
    _write_startup_config()


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(_draw_ht_submenu)
    bpy.utils.unregister_class(HT_MT_import_submenu)
    bpy.utils.unregister_class(HT_MT_hoovytools_utils)
    bpy.utils.unregister_class(HT_MT_utils_submenu)
    bpy.utils.unregister_class(HT_MT_session_submenu)
    Panel.unregister()
    Developer.unregister()
    if _HAS_EXPERIMENTAL:
        Session_Locks.unregister()
        Playground.unregister()
    Session_Map.unregister()
    Session_Particles.unregister()
    Session_Steps.unregister()
    Session_Reader.unregister()
    Light_Import.unregister()
    Session_Orchestrator.unregister()
    ShapeKey_Proxy.unregister()
    Camera_Tools.unregister()
    FPS_Safety.unregister()
    Session_Paths.unregister()
    DMX_Analyzer.unregister()
    Import_Session_Sounds.unregister()
    Import_Shape_Key_Animations.unregister()
    Import_Materials.unregister()
    Import_MDL.unregister()
    Import_Shape_Keys.unregister()
    Utils_Misc.unregister()
    Layout_Builder.unregister()
    Utils_Camera_Fix_Camera.unregister()
    Camera_Bone_Rig.unregister()
    Session_Visibility.unregister()
    Scene_Offset.unregister()
    Euler_Output.unregister()
    Utils_MDL.unregister()
    Utils_Shape_Keys.unregister()
    Import_Camera_Animations.unregister()
    Import_Animations.unregister()
    Import_DMX_Camera.unregister()
    Import_DMX_Animation.unregister()
    Import_Session.unregister()
    sources.unregister()
    Report_UI.unregister()
    _unload_icons()

    # Unregister SST's SmdImporter only if we were the ones who registered it
    SST.unregister_smd_importer()
    bpy.utils.unregister_class(HoovyToolsPreferences)
    console_mark.uninstall()
