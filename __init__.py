bl_info = {
    "name":        "HoovyTools",
    "description": "SFM → Blender pipeline tools",
    "author":      "HoovyTools",
    "version":     (2, 0, 0),
    "blender":     (5, 0, 1),
    "location":    "File > Import > Source Engine (HoovyTools) + 3D View sidebar (N)",
    "category":    "Import-Export",
}

import bpy
import bpy.utils.previews
from pathlib import Path
from bpy.types import AddonPreferences
from bpy.props import StringProperty
from . import SST
from . import Import_Session
from . import Import_DMX_Animation
from . import Import_DMX_Camera
from . import Import_Shape_Keys
from . import Import_Animations
from . import Import_Camera_Animations
from . import Import_Shape_Key_Animations
from . import Import_Session_Sounds
from . import Import_MDL
from . import Utils_Shape_Keys
from . import Utils_MDL
from . import Utils_Camera_Fix_Camera
from . import Utils_Misc
from . import Panel


# ──────────────────────────────────────────────────────────────────────────────
#  ADDON PREFERENCES
# ──────────────────────────────────────────────────────────────────────────────

class HoovyToolsPreferences(AddonPreferences):
    bl_idname = __name__

    sfm_usermod_path: StringProperty(
        name        = "SFM Usermod Path",
        description = "Path to SourceFilmmaker/game/usermod — must contain gameinfo.txt",
        default     = r"C:\Program Files (x86)\Steam\steamapps\common\SourceFilmmaker\game\usermod",
        subtype     = "DIR_PATH",
    )

    faulty_rigs_sfm_path: StringProperty(
        name        = "Faulty Rigs SFM Path",
        description = "Second search location for reference DMX files",
        default     = (
            r"C:\Program Files (x86)\Steam\steamapps\common\SourceFilmmaker"
            r"\game\usermod\plugins\___SFM to Blender Session Importer\_Dev\Faulty Rigs"
        ),
        subtype     = "DIR_PATH",
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="SFM Installation Paths", icon="FILE_FOLDER")
        box = layout.box()
        col = box.column()
        col.prop(self, "sfm_usermod_path")
        col.prop(self, "faulty_rigs_sfm_path")
        from . import Import_Session
        active = Import_Session.get_gameinfo_base()
        if not active.exists():
            row = col.row()
            row.alert = True
            row.label(text=f"SFM Usermod Path not found: {active}", icon="ERROR")
        else:
            col.label(text=f"Resolved: {active}", icon="CHECKMARK")


# ──────────────────────────────────────────────────────────────────────────────
#  CUSTOM ICONS
# ──────────────────────────────────────────────────────────────────────────────

_ICONS_DIR = Path(__file__).parent / "Icons"

_ICON_FILES = {
    "hoovy_logo":                   "hoovy_logo",
    "import_session":               "import_session",
    "import_session_models":        "import_session_models",
    "import_session_sounds":         "import_session_sounds",
    "rig_fixer":                    "rig_fixer",
    "import_dmx_anim":              "import_dmx_anim",
    "import_dmx_camera":            "import_dmx_camera",
    "import_shape_keys":            "import_shape_keys",
    "util_import_shape_keys":       "util_import_shape_keys",
    "import_animations":            "import_animations",
    "import_camera_animations":     "import_camera_animations",
    "import_shape_key_animations":  "import_shape_key_animations",
    "source_engine_utils":          "source_engine_utils",
    "utils_shape_keys":             "utils_shape_keys",
    "utils_camera":                 "utils_camera",
    "split_camera":                 "split_camera",
    "organize_scene":               "organize_scene",
    "utils_misc":                   "utils_misc",
    "reduce_lag":                   "reduce_lag",
    "remove_drivers":               "remove_drivers",
    "symmetrize_shapekeys":         "symmetrize_shapekeys",
    "bake_localvars":               "bake_localvars",
    "import_mdl":                   "import_mdl",
    "utils_mdl":                    "utils_mdl",
    "fix_eye_constraints":          "fix_eye_constraints",
    "fix_rig":                      "fix_rig",
}

_pcoll = None


def _load_icons():
    global _pcoll
    _pcoll = bpy.utils.previews.new()
    if not _ICONS_DIR.is_dir():
        print(f"[HoovyTools]  Icons/ not found at {_ICONS_DIR} — using Blender defaults")
        return
    for key, fname in _ICON_FILES.items():
        path = _ICONS_DIR / f"{fname}.png"
        if path.exists():
            _pcoll.load(key, str(path), "IMAGE")
            print(f"[HoovyTools]  icon loaded : {key}")
        else:
            print(f"[HoovyTools]  icon missing: {fname}.png")


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
#  MENUS
# ──────────────────────────────────────────────────────────────────────────────

class MT_HT_session_submenu(bpy.types.Menu):
    bl_idname = "MT_HT_session_submenu"
    bl_label  = "Import Session"

    def draw(self, context):
        Import_Session.draw_submenu(self.layout)
        Import_Animations.draw_session_entry(self.layout)
        Import_Camera_Animations.draw_session_entry(self.layout)
        Import_Shape_Key_Animations.draw_session_entry(self.layout)
        Import_Session_Sounds.draw_session_entry(self.layout)


class MT_HT_utils_submenu(bpy.types.Menu):
    bl_idname = "MT_HT_utils_submenu"
    bl_label  = "Source Engine Utils"

    def draw(self, context):
        Utils_Shape_Keys.draw_utils_shapekeys_entry(self.layout)
        Utils_MDL.draw_utils_mdl_entry(self.layout)
        Utils_Camera_Fix_Camera.draw_utils_camera_entry(self.layout)
        Utils_Misc.draw_utils_misc_entry(self.layout)


class MT_HT_import_submenu(bpy.types.Menu):
    bl_idname = "MT_HT_import_submenu"
    bl_label  = "Source Engine (HoovyTools)"

    def draw(self, context):
        self.layout.menu(
            MT_HT_session_submenu.bl_idname,
            **icon_id("import_session", "SCENE_DATA"),
        )
        self.layout.separator()
        Import_MDL.draw_menu_item(self.layout)
        self.layout.separator()
        Import_DMX_Animation.draw_menu_item(self.layout)
        Import_DMX_Camera.draw_menu_item(self.layout)
        Import_Shape_Keys.draw_menu_item(self.layout)
        self.layout.separator()
        self.layout.menu(
            MT_HT_utils_submenu.bl_idname,
            **icon_id("source_engine_utils", "TOOL_SETTINGS"),
        )


def _draw_ht_submenu(self, context):
    self.layout.menu(
        MT_HT_import_submenu.bl_idname,
        **icon_id("hoovy_logo", "TOOL_SETTINGS"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

def register():
    bpy.utils.register_class(HoovyToolsPreferences)

    # Ensure import_scene.smd is available — uses BST if present, SST bundle otherwise
    SST.ensure_smd_importer()

    _load_icons()
    Import_Session.register(icon_id_fn=icon_id)
    Import_DMX_Animation.register(icon_id_fn=icon_id)
    Import_DMX_Camera.register(icon_id_fn=icon_id)
    Import_Animations.register(icon_id_fn=icon_id)
    Import_Camera_Animations.register(icon_id_fn=icon_id)
    Import_Shape_Keys.register(icon_id_fn=icon_id)
    Utils_Shape_Keys.register(icon_id_fn=icon_id)
    Utils_MDL.register(icon_id_fn=icon_id)
    Utils_Camera_Fix_Camera.register(icon_id_fn=icon_id)
    Utils_Misc.register(icon_id_fn=icon_id)
    Import_MDL.register(icon_id_fn=icon_id)
    Import_Shape_Key_Animations.register(icon_id_fn=icon_id)
    Import_Session_Sounds.register(icon_id_fn=icon_id)
    Panel.register(icon_id_fn=icon_id)
    bpy.utils.register_class(MT_HT_session_submenu)
    bpy.utils.register_class(MT_HT_utils_submenu)
    bpy.utils.register_class(MT_HT_import_submenu)
    bpy.types.TOPBAR_MT_file_import.append(_draw_ht_submenu)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(_draw_ht_submenu)
    bpy.utils.unregister_class(MT_HT_import_submenu)
    bpy.utils.unregister_class(MT_HT_utils_submenu)
    bpy.utils.unregister_class(MT_HT_session_submenu)
    Panel.unregister()
    Import_Session_Sounds.unregister()
    Import_Shape_Key_Animations.unregister()
    Import_MDL.unregister()
    Import_Shape_Keys.unregister()
    Utils_Misc.unregister()
    Utils_Camera_Fix_Camera.unregister()
    Utils_MDL.unregister()
    Utils_Shape_Keys.unregister()
    Import_Camera_Animations.unregister()
    Import_Animations.unregister()
    Import_DMX_Camera.unregister()
    Import_DMX_Animation.unregister()
    Import_Session.unregister()
    _unload_icons()

    # Unregister SST's SmdImporter only if we were the ones who registered it
    SST.unregister_smd_importer()
    bpy.utils.unregister_class(HoovyToolsPreferences)
