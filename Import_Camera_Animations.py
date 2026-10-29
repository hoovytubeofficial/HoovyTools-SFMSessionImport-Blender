"""
Import_Camera_Animations.py  —  part of HoovyTools
====================================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Camera Animations (Folder)

Scans a folder of exported SFM DMX camera animations, imports each one via
Import_DMX_Camera.import_dmx_camera(), and organises all resulting objects
into a single scene collection called  __Hoovy Camera Import__  (blue).

Each imported camera produces the standard HoovyTools hierarchy:
    {cam}_axis   — static axis-correction empty
    {cam}_root   — animated empty  (position + rotation)
    {cam}        — camera object   (lens / FOV only)

All three objects are moved into the  __Hoovy Camera Import__  collection.

NAMING CONVENTION
─────────────────
    {shot}_camera*.dmx        →   shot1_camera_main.dmx
    {shot}_cam*.dmx           →   shot1_cam01.dmx
    Any DMX whose root element contains a "camera" key is accepted regardless
    of filename when IGNORE_SHOT_NUMBER is True.

DETECTION
─────────
A DMX file is treated as a camera file when its filename contains "camera"
or "cam" (case-insensitive) after the shot prefix is stripped.
When IGNORE_SHOT_NUMBER is True every .dmx in the folder is probed.
"""

bl_info = {
    "name":        "HoovyTools: Import Camera Animations (Folder)",
    "description": "Batch import SFM DMX camera animations from a folder",
    "author":      "HoovyTools",
    "version":     (1, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > Camera Animations (Folder)",
    "category":    "Import-Export",
}

import bpy
from pathlib import Path
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, FloatProperty


# ──────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────────────────────────────────────

SHOT_FILTER        = "shot1"
IGNORE_SHOT_NUMBER = False

CAMERA_COLLECTION  = "__Hoovy Camera Import__"
COLOR_CAMERA_COL   = "COLOR_05"   # blue  — camera collection
COLOR_OK           = "COLOR_04"   # green — camera successfully imported
COLOR_FAIL         = "COLOR_06"   # red   — import failed

# Keywords used to identify camera DMX files by stem (after shot prefix stripped)
_CAM_KEYWORDS = ("camera", "cam")


# ──────────────────────────────────────────────────────────────────────────────
#  ICON HELPER
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
#  COLLECTION HELPER
# ──────────────────────────────────────────────────────────────────────────────

def _get_or_create_camera_collection() -> bpy.types.Collection:
    """
    Return the  __Hoovy Camera Import__  collection, creating it if needed.
    Always a direct child of the Scene Collection, colored blue.
    """
    col = bpy.data.collections.get(CAMERA_COLLECTION)
    if col is None:
        col = bpy.data.collections.new(CAMERA_COLLECTION)
        bpy.context.scene.collection.children.link(col)
        print(f"[CAM_HARVEST]  created collection '{CAMERA_COLLECTION}'")
    col.color_tag = COLOR_CAMERA_COL
    return col


def _move_object_to_collection(obj: bpy.types.Object,
                                target: bpy.types.Collection) -> None:
    """Unlink *obj* from every collection it currently lives in, then link to *target*."""
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    if obj.name not in target.objects:
        target.objects.link(obj)


# ──────────────────────────────────────────────────────────────────────────────
#  FILE DETECTION
# ──────────────────────────────────────────────────────────────────────────────

def _strip_shot_prefix(stem: str, shot_filter: str, ignore_shot: bool) -> str:
    s = stem.lower()
    if not ignore_shot:
        prefix = shot_filter.lower().rstrip("_") + "_"
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s


def _is_camera_file(stem: str, shot_filter: str, ignore_shot: bool) -> bool:
    """True when the stem (after shot prefix) contains a camera keyword."""
    s = _strip_shot_prefix(stem, shot_filter, ignore_shot)
    return any(kw in s for kw in _CAM_KEYWORDS)


def _collect_camera_dmx_files(folder: Path, shot_filter: str,
                               ignore_shot: bool) -> list:
    if not folder.exists():
        raise FileNotFoundError(f"Animation folder not found:\n  {folder}")
    all_dmx = sorted(folder.glob("*.dmx"))
    if not all_dmx:
        raise FileNotFoundError(f"No .dmx files found in:\n  {folder}")

    if ignore_shot:
        candidates = all_dmx
    else:
        prefix     = shot_filter.lower().rstrip("_") + "_"
        candidates = [f for f in all_dmx if f.name.lower().startswith(prefix)]

    cam_files = [f for f in candidates
                 if _is_camera_file(f.stem, shot_filter, ignore_shot)]

    print(f"[CAM_HARVEST]  shot filter '{shot_filter}': "
          f"{len(cam_files)} camera file(s) from {len(all_dmx)} total")
    return cam_files


# ──────────────────────────────────────────────────────────────────────────────
#  PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def run_camera_harvester(folder: Path,
                         shot_filter: str  = SHOT_FILTER,
                         ignore_shot: bool = IGNORE_SHOT_NUMBER,
                         scale: float      = 1.0,
                         fix_quat_flips: bool = True) -> dict:
    """
    Import all camera DMX files from *folder*.
    All imported objects are collected into  __Hoovy Camera Import__  (blue).

    Returns:
    {
        "ok":      int,
        "warned":  int,
        "failed":  int,
        "results": list[dict],
    }
    """
    from . import Import_DMX_Camera

    print(f"\n[CAM_HARVEST]  {'='*50}")
    print(f"[CAM_HARVEST]  Folder : {folder}")
    print(f"[CAM_HARVEST]  Shot   : {shot_filter}  ignore={ignore_shot}  scale={scale}")

    cam_col   = _get_or_create_camera_collection()
    cam_files = _collect_camera_dmx_files(folder, shot_filter, ignore_shot)

    if not cam_files:
        print("[CAM_HARVEST]  No camera files matched — done.")
        return {"ok": 0, "warned": 0, "failed": 0, "results": []}

    results = []

    for dmx in cam_files:
        entry = {"file": dmx.name, "camera": None, "status": ""}
        print(f"[CAM_HARVEST]  importing '{dmx.name}'")

        try:
            result = Import_DMX_Camera.import_dmx_camera(dmx, scale=scale,
                                                            fix_quat_flips=fix_quat_flips)

            cam_obj    = result["camera_obj"]
            root_empty = result["root_empty"]
            axis_empty = result["axis_empty"]

            # Move all three hierarchy objects into the camera collection
            for obj in (axis_empty, root_empty, cam_obj):
                _move_object_to_collection(obj, cam_col)

            from .anim_compat import count_fcurves
            root_fc = count_fcurves(result["root_action"], root_empty)
            lens_fc = count_fcurves(result["cam_action"], cam_obj.data) if result["cam_action"] else 0

            entry["camera"] = cam_obj.name
            flips = result.get("quat_flips", 0)
            entry["status"] = (
                f"✓  {cam_obj.name}"
                f"  root:{root_fc} fc"
                + (f"  lens:{lens_fc} fc" if lens_fc else "")
                + (f"  flips:{flips}" if flips else "")
            )
            print(f"[CAM_HARVEST]  ✓ '{cam_obj.name}'")

        except Exception as exc:
            print(f"[CAM_HARVEST]  ERROR: {exc}")
            entry["status"] = f"✗  {exc}"

        results.append(entry)

    ok      = sum(1 for r in results if r["status"].startswith("✓"))
    warned  = sum(1 for r in results if r["status"].startswith("⚠"))
    failed  = sum(1 for r in results if r["status"].startswith("✗"))

    print(f"[CAM_HARVEST]  done — ok:{ok}  warned:{warned}  failed:{failed}")
    return {"ok": ok, "warned": warned, "failed": failed, "results": results}


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_ImportCameraAnimations(Operator):
    """Import SFM DMX camera animations from a folder"""
    bl_idname  = "ht.import_camera_animations"
    bl_label   = "Camera Animations (Folder)"
    bl_options = {"REGISTER", "UNDO"}

    filepath:    StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})

    shot_filter:  StringProperty(name="Shot Filter",        default=SHOT_FILTER)
    ignore_shot:  BoolProperty(  name="Ignore Shot Number", default=IGNORE_SHOT_NUMBER)
    scale:        FloatProperty( name="Scale",
                                 description="World scale — match your session import",
                                 default=1.0, min=0.001)
    fix_quat_flips: BoolProperty(name="Fix Quaternion Flips",
                                 description="Negate quaternion keyframes where dot(prev,curr) < 0 to prevent 180° spin artifacts from SFM",
                                 default=True)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        self.layout.prop(self, "shot_filter")
        self.layout.prop(self, "ignore_shot")
        self.layout.prop(self, "scale")
        self.layout.prop(self, "fix_quat_flips")

    def execute(self, context):
        folder = Path(self.filepath)
        if folder.suffix or not folder.is_dir():
            folder = folder.parent

        try:
            result = run_camera_harvester(folder,
                                          shot_filter=self.shot_filter,
                                          ignore_shot=self.ignore_shot,
                                          scale=self.scale,
                                          fix_quat_flips=self.fix_quat_flips)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        total = result["ok"] + result["warned"] + result["failed"]
        lines = [
            f"Folder     : {folder.name}",
            f"Shot       : {self.shot_filter}" if not self.ignore_shot else "Shot       : (all)",
            f"Imported   : {result['ok']} / {total}",
            f"Collection : {CAMERA_COLLECTION}",
        ]
        if result["warned"]:
            lines.append(f"Warned   : {result['warned']}")
        if result["failed"]:
            lines.append(f"Failed   : {result['failed']}")
        lines.append("─" * 44)
        for r in result["results"]:
            lines.append(r["file"])
            lines.append(f"    {r['status']}")

        _lines = list(lines)
        def draw_popup(self, context):
            for line in _lines:
                self.layout.label(text=line)
        context.window_manager.popup_menu(
            draw_popup,
            title=f"Camera Animations — {result['ok']}/{total} imported",
            icon="CHECKMARK" if not result["warned"] and not result["failed"] else "INFO",
        )
        self.report({"INFO"}, f"Imported {result['ok']} camera animation(s)")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU ITEMS
# ──────────────────────────────────────────────────────────────────────────────

def draw_menu_item(layout):
    """Standalone entry in the top-level HoovyTools submenu (currently unused)."""
    layout.operator(
        HT_OT_ImportCameraAnimations.bl_idname,
        text="Camera Animations (Folder)",
        **_icon_id("import_camera_animations", "CAMERA_DATA"),
    )


def draw_session_entry(layout):
    """Entry 4 inside the IMPORT SESSION submenu."""
    layout.operator(
        HT_OT_ImportCameraAnimations.bl_idname,
        text="4  Import DMX Session Cameras",
        **_icon_id("import_camera_animations", "CAMERA_DATA"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (HT_OT_ImportCameraAnimations,)


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


if __name__ == "__main__":
    register()
    bpy.ops.ht.import_camera_animations("INVOKE_DEFAULT")
