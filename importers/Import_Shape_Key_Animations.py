"""
Import_Shape_Key_Animations.py  —  part of HoovyTools
=======================================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Import Session ▸
           5  Import DMX Session Shape Keys

Scans a folder of exported SFM flex DMX files, matches each file to an
armature already in the scene by name (same token-matching logic as
Import_Animations), then imports shape key animation onto every MESH child
of that armature via Import_Shape_Keys.import_shape_keys().

After processing, colors each armature's top-level collection:
  Green  — at least one mesh successfully imported
  Red    — armature found but no mesh imported / error
Nothing is moved.

NAMING CONVENTION
─────────────────
    {shot}_{armature_name}_*.dmx   →   shot1_scout_flex.dmx
    {shot}_{armature_name}.dmx     →   shot1_scout3.dmx

MESH MATCHING
─────────────
Rather than matching DMX filenames to mesh names directly, the harvester:
  1. Matches the DMX stem to an armature name (same as Import_Animations).
  2. Collects all MESH children of that armature.
  3. Runs import_shape_keys() on each mesh child in turn.
     The first mesh that succeeds is treated as the primary result.
     Remaining meshes receive the same flex animation (shared shapes).
"""

bl_info = {
    "name":        "HoovyTools: Import Shape Key Animations (Folder)",
    "description": "Batch import SFM flex DMX shape key animations from a folder",
    "author":      "HoovyTools",
    "version":     (1, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > Import Session",
    "category":    "Import-Export",
}

import bpy
from pathlib import Path
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty


# ──────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────────────────────────────────────

SHOT_FILTER        = "shot1"
IGNORE_SHOT_NUMBER = False

COLOR_OK   = "COLOR_04"   # green — shape keys imported
COLOR_FAIL = "COLOR_06"   # red   — no mesh imported / error

# Stems containing these keywords are skipped — they are rig / bone animations,
# not flex animations.  Extend as needed.
_SKIP_KEYWORDS = ("_anim", "_camera", "_cam", "_rig")


# ──────────────────────────────────────────────────────────────────────────────
#  ICON HELPER
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _build_armature_map() -> dict:
    """Lower-case name → armature object for every ARMATURE in the scene."""
    return {obj.name.lower(): obj
            for obj in bpy.data.objects if obj.type == "ARMATURE"}


def _mesh_children(armature) -> list:
    """
    Return all MESH objects that are children of *armature* or have it
    as an ARMATURE modifier target.
    """
    direct = [o for o in armature.children if o.type == "MESH"]
    modifier_linked = [
        o for o in bpy.data.objects
        if o.type == "MESH" and o not in direct
        and any(m.type == "ARMATURE" and m.object == armature
                for m in o.modifiers)
    ]
    return direct + modifier_linked


def _armature_name_from_stem(stem: str, shot_filter: str,
                              ignore_shot: bool, arm_map: dict) -> str:
    """
    Strip shot prefix, then find the longest token sequence that matches
    an armature name.  Mirrors Import_Animations._armature_name_from_stem().
    """
    s = stem.lower()
    if not ignore_shot:
        prefix = shot_filter.lower().rstrip("_") + "_"
        if s.startswith(prefix):
            s = s[len(prefix):]
    tokens = s.split("_")
    for i in range(len(tokens), 0, -1):
        candidate = "_".join(tokens[:i])
        if candidate in arm_map:
            return candidate
    return s


def _collect_flex_dmx_files(folder: Path, shot_filter: str,
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

    # Filter out files that look like bone animations or cameras
    flex_files = [
        f for f in candidates
        if not any(kw in f.stem.lower() for kw in _SKIP_KEYWORDS)
    ]

    print(f"[SK_HARVEST]  shot filter '{shot_filter}': "
          f"{len(flex_files)} flex file(s) from {len(all_dmx)} total")
    return flex_files


def _find_top_collection(armature) -> bpy.types.Collection | None:
    """Return the direct child of Scene Collection that contains armature."""
    scene_root = bpy.context.scene.collection

    def search(col, obj, path):
        if obj.name in col.objects:
            return path + [col]
        for child in col.children:
            result = search(child, obj, path + [col])
            if result:
                return result
        return None

    path = search(scene_root, armature, [])
    if not path or len(path) < 2:
        return None
    return path[1]


def _color_top_collection(armature, color: str) -> str:
    col = _find_top_collection(armature)
    if col is None:
        return ""
    col.color_tag = color
    return col.name


# ──────────────────────────────────────────────────────────────────────────────
#  PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def run_shape_key_harvester(folder: Path,
                             shot_filter: str  = SHOT_FILTER,
                             ignore_shot: bool = IGNORE_SHOT_NUMBER) -> dict:
    """
    Import all matching flex DMX animations from *folder* onto scene armature
    mesh children.  Top-level collections colored green (ok) or red (fail).

    Returns:
    {
        "ok":      int,
        "warned":  int,
        "skipped": int,
        "results": list[dict],
    }
    """
    from . import Import_Shape_Keys

    print(f"\n[SK_HARVEST]  {'='*50}")
    print(f"[SK_HARVEST]  Folder : {folder}")
    print(f"[SK_HARVEST]  Shot   : {shot_filter}  ignore={ignore_shot}")

    arm_map   = _build_armature_map()
    dmx_files = _collect_flex_dmx_files(folder, shot_filter, ignore_shot)

    # Pre-color armatures with no matching flex DMX red
    targeted_keys = set()
    for dmx in dmx_files:
        key = _armature_name_from_stem(dmx.stem, shot_filter, ignore_shot, arm_map)
        if key in arm_map:
            targeted_keys.add(key)

    for key, arm in arm_map.items():
        if key not in targeted_keys:
            col_name = _color_top_collection(arm, COLOR_FAIL)
            print(f"[SK_HARVEST]  NO MATCH: '{arm.name}' → '{col_name}' colored red")

    # Main import loop
    results = []
    for dmx in dmx_files:
        arm_key  = _armature_name_from_stem(dmx.stem, shot_filter, ignore_shot, arm_map)
        entry    = {"file": dmx.name, "target_key": arm_key,
                    "armature": None, "meshes": [], "status": ""}

        if arm_key not in arm_map:
            print(f"[SK_HARVEST]  SKIP: no armature '{arm_key}'")
            entry["status"] = f"✗  No matching armature '{arm_key}'"
            results.append(entry)
            continue

        armature = arm_map[arm_key]
        entry["armature"] = armature.name
        meshes   = _mesh_children(armature)

        if not meshes:
            print(f"[SK_HARVEST]  SKIP: '{armature.name}' has no mesh children")
            entry["status"] = f"✗  No mesh children on '{armature.name}'"
            _color_top_collection(armature, COLOR_FAIL)
            results.append(entry)
            continue

        print(f"[SK_HARVEST]  {dmx.name}  →  '{armature.name}'  "
              f"({len(meshes)} mesh(es))")

        mesh_results = []
        any_ok       = False

        for mesh_obj in meshes:
            try:
                sk_result = Import_Shape_Keys.import_shape_keys(dmx, mesh_obj)
                ch        = sk_result["channels"]
                fr        = sk_result["frame_rate"]
                mf        = sk_result["max_frame"]
                bake      = sk_result["bake_result"]

                summary = f"{mesh_obj.name}: {ch} ch  {fr}fps  0–{int(mf)}fr"
                if bake and bake.get("ok"):
                    summary += f"  bake:{bake['baked']}lv"
                mesh_results.append(f"    ✓ {summary}")
                any_ok = True

            except Exception as exc:
                print(f"[SK_HARVEST]  ERROR on '{mesh_obj.name}': {exc}")
                mesh_results.append(f"    ✗ {mesh_obj.name}: {exc}")

        entry["meshes"] = mesh_results
        if any_ok:
            entry["status"] = f"✓  {len([r for r in mesh_results if r.strip().startswith('✓')])} mesh(es) imported"
            _color_top_collection(armature, COLOR_OK)
        else:
            entry["status"] = "✗  All meshes failed"
            _color_top_collection(armature, COLOR_FAIL)

        results.append(entry)

    ok      = sum(1 for r in results if r["status"].startswith("✓"))
    warned  = sum(1 for r in results if r["status"].startswith("⚠"))
    skipped = sum(1 for r in results if r["status"].startswith("✗"))

    print(f"[SK_HARVEST]  done — ok:{ok}  warned:{warned}  skipped:{skipped}")
    return {"ok": ok, "warned": warned, "skipped": skipped, "results": results}


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATOR
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_ImportShapeKeyAnimations(Operator):
    """PICK .dmx (face / flex - multiple) - click any ONE file and EVERY flex
        file in that folder is imported

        Import a FOLDER of flex .dmx files onto the meshes of the rigs in the scene

Each file is matched to an armature by name and then to that rig's
meshes, so import the models first.

This is the folder-at-a-time version of the shape key importer and it
runs the same HWM localvar bake, which is the part that makes a face
actually move. A file whose rig is not in the scene is reported rather
than dropped quietly"""
    bl_idname  = "ht.import_shape_key_animations"
    bl_label   = "Shape Key Animations (Folder)"
    #  NO "REGISTER" - see the note in Report_UI/the constitution.
    #  REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    #  touching any field in it RE-RUNS this operator. Re-running an
    #  import re-reads the DMX and rebuilds every f-curve; nudging Scale
    #  there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    #  with the value you wanted is the safe way to change your mind.
    bl_options = {"UNDO"}

    filepath:    StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})

    shot_filter: StringProperty(name="Shot Filter",        default=SHOT_FILTER)
    ignore_shot: BoolProperty(  name="Ignore Shot Number", default=IGNORE_SHOT_NUMBER)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        self.layout.prop(self, "shot_filter")
        self.layout.prop(self, "ignore_shot")

    def execute(self, context):
        folder = Path(self.filepath)
        if folder.suffix or not folder.is_dir():
            folder = folder.parent

        try:
            result = run_shape_key_harvester(folder,
                                             shot_filter=self.shot_filter,
                                             ignore_shot=self.ignore_shot)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        total = result["ok"] + result["warned"] + result["skipped"]
        lines = [
            f"Folder   : {folder.name}",
            f"Shot     : {self.shot_filter}" if not self.ignore_shot else "Shot     : (all)",
            f"Imported : {result['ok']} / {total}",
        ]
        if result["warned"]:
            lines.append(f"Warned   : {result['warned']}")
        if result["skipped"]:
            lines.append(f"Skipped  : {result['skipped']} (no armature / no mesh)")
        lines.append("─" * 44)
        for r in result["results"]:
            arm_label = (f"→ {r['armature']}" if r["armature"]
                         else f"→ ('{r['target_key']}' not found)")
            lines.append(r["file"])
            lines.append(f"    {arm_label}  {r['status']}")
            for mesh_line in r.get("meshes", []):
                lines.append(mesh_line)

        from ..core import Report_UI
        Report_UI.report(
            context, "import_shapekey_anims",
            f"Shape Keys - {result['ok']}/{total} imported", lines,
            level=('WARNING' if (result["warned"] or result["skipped"])
                   else 'INFO'),
            operator=self, prefix="SHAPEKEY_ANIMS",
            summary=f"Shape Key Animations - {result['ok']}/{total} imported"
                    + (f", {result['skipped']} skipped"
                       if result["skipped"] else ""))
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU ITEMS
# ──────────────────────────────────────────────────────────────────────────────

def draw_menu_item(layout):
    """Standalone top-level entry (reserved, not currently shown in main menu)."""
    layout.operator(
        HT_OT_ImportShapeKeyAnimations.bl_idname,
        text="Shape Key Animations (Folder)",
        **_icon_id("import_shape_key_animations", "SHAPEKEY_DATA"),
    )


def draw_session_entry(layout):
    """Entry 5 inside the IMPORT SESSION submenu."""
    layout.operator(
        HT_OT_ImportShapeKeyAnimations.bl_idname,
        text="4  Import DMX Session Shape Keys",
        **_icon_id("import_shape_key_animations", "SHAPEKEY_DATA"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (HT_OT_ImportShapeKeyAnimations,)


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
    bpy.ops.ht.import_shape_key_animations("INVOKE_DEFAULT")
