"""
Import_Animations.py  —  part of HoovyTools
============================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Animations (Folder)

Scans a folder of exported SFM DMX animations, matches each file to an
armature already in the scene by name, and imports the animation.

Uses Import_DMX_Animation.import_dmx_animation() per file so scale channels
and root transform / axis empties are created automatically.

After processing, colors each armature's top-level collection:
  Green  — animation successfully imported
  Red    — armature found but no matching DMX / import failed
Nothing is moved.

NAMING CONVENTION
─────────────────
    {shot}_{armature_name}_*.dmx   →   shot1_scout_main_anim.dmx
    {shot}_{armature_name}.dmx     →   shot1_scout3.dmx
"""

bl_info = {
    "name":        "HoovyTools: Import Animations (Folder)",
    "description": "Batch import SFM DMX animations from a folder onto scene armatures",
    "author":      "HoovyTools",
    "version":     (1, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > Animations (Folder)",
    "category":    "Import-Export",
}

import bpy
from pathlib import Path
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty
from ..core import Common_Props


# ──────────────────────────────────────────────────────────────────────────────
# config
# ──────────────────────────────────────────────────────────────────────────────

SHOT_FILTER        = "shot1"
IGNORE_SHOT_NUMBER = False

COLOR_OK  = "COLOR_04"   # green — animation imported
COLOR_FAIL = "COLOR_06"  # red   — no animation found / error


# ──────────────────────────────────────────────────────────────────────────────
# icon helper
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _build_armature_map() -> dict:
    return {obj.name.lower(): obj
            for obj in bpy.data.objects if obj.type == "ARMATURE"}


def _armature_name_from_stem(stem: str, shot_filter: str,
                              ignore_shot: bool, arm_map: dict) -> str:
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


def _collect_dmx_files(folder: Path, shot_filter: str, ignore_shot: bool) -> list:
    if not folder.exists():
        raise FileNotFoundError(f"Animation folder not found:\n  {folder}")
    all_dmx = sorted(folder.glob("*.dmx"))
    if not all_dmx:
        raise FileNotFoundError(f"No .dmx files found in:\n  {folder}")
    if ignore_shot:
        return all_dmx
    prefix   = shot_filter.lower().rstrip("_") + "_"
    filtered = [f for f in all_dmx if f.name.lower().startswith(prefix)]
    print(f"[HARVESTER]  shot filter '{shot_filter}': {len(filtered)}/{len(all_dmx)} files")
    return filtered


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
    return path[1]   # path[0] = scene_root, path[1] = top-level


def _color_top_collection(armature, color: str) -> str:
    col = _find_top_collection(armature)
    if col is None:
        return ""
    col.color_tag = color
    return col.name


# ──────────────────────────────────────────────────────────────────────────────
# public api
# ──────────────────────────────────────────────────────────────────────────────

def run_harvester(folder: Path,
                  shot_filter: str  = SHOT_FILTER,
                  ignore_shot: bool = IGNORE_SHOT_NUMBER,
                  anim_scale:  float = 1.0) -> dict:
    """
    Import all matching DMX animations from *folder* onto scene armatures.
    Nothing is moved. Top-level collections are colored green (ok) or red (fail).

    Returns:
    {
        "ok":      int,
        "warned":  int,
        "skipped": int,
        "results": list[dict],
    }
    """
    from . import Import_DMX_Animation

    print(f"\n[HARVESTER]  {'='*50}")
    print(f"[HARVESTER]  Folder : {folder}")
    print(f"[HARVESTER]  Shot   : {shot_filter}  ignore={ignore_shot}")

    if not hasattr(bpy.ops.ht, "import_smd"):
        raise RuntimeError("HoovyTools SST importer not registered — reload the addon.")

    arm_map   = _build_armature_map()
    dmx_files = _collect_dmx_files(folder, shot_filter, ignore_shot)

    #track which armature keys are targeted so we can color untouched ones red
    targeted_keys = set()
    for dmx in dmx_files:
        key = _armature_name_from_stem(dmx.stem, shot_filter, ignore_shot, arm_map)
        if key in arm_map:
            targeted_keys.add(key)

    # color armatures with no matching DMX red up front
    for key, arm in arm_map.items():
        if key not in targeted_keys:
            col_name = _color_top_collection(arm, COLOR_FAIL)
            print(f"[HARVESTER]  NO MATCH: '{arm.name}' → '{col_name}' colored red")

    #main import loop
    results = []
    for dmx in dmx_files:
        arm_key = _armature_name_from_stem(dmx.stem, shot_filter, ignore_shot, arm_map)
        entry   = {"file": dmx.name, "target_key": arm_key,
                   "armature": None, "action": None, "status": ""}

        if arm_key not in arm_map:
            print(f"[HARVESTER]  SKIP: no armature '{arm_key}'")
            entry["status"] = f"✗  No matching armature '{arm_key}'"
            results.append(entry)
            continue

        armature = arm_map[arm_key]
        entry["armature"] = armature.name
        print(f"[HARVESTER]  {dmx.name}  →  '{armature.name}'")

        try:
            anim_result = Import_DMX_Animation.import_dmx_animation(dmx, armature,
                                                                    anim_scale=anim_scale)
            action      = anim_result["action"]

            if action:
                fr = action.frame_range
                entry["action"] = action.name
                entry["status"] = f"✓  {action.name}  ({fr[0]:.0f}–{fr[1]:.0f} fr)"
                if anim_result["scale_bones"]:
                    entry["status"] += f"  scale:{anim_result['scale_bones']}"
                if anim_result["root_curves"]:
                    entry["status"] += f"  root:{anim_result['root_curves']}"
                _color_top_collection(armature, COLOR_OK)
            else:
                entry["status"] = "⚠  Imported but no action created"
                _color_top_collection(armature, COLOR_FAIL)

        except Exception as exc:
            print(f"[HARVESTER]  ERROR: {exc}")
            entry["status"] = f"✗  {exc}"
            _color_top_collection(armature, COLOR_FAIL)

        results.append(entry)

    ok      = sum(1 for r in results if r["status"].startswith("✓"))
    warned  = sum(1 for r in results if r["status"].startswith("⚠"))
    skipped = sum(1 for r in results if r["status"].startswith("✗"))

    print(f"[HARVESTER]  done — ok:{ok}  warned:{warned}  skipped:{skipped}")
    return {"ok": ok, "warned": warned, "skipped": skipped, "results": results}


# ──────────────────────────────────────────────────────────────────────────────
# operator
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_ImportAnimations(Operator):
    """PICK .dmx (animation - multiple) - click any ONE file and EVERY
        animation in that folder is imported, matched to rigs by name

        Import a whole FOLDER of SFM animation .dmx files onto the rigs in the scene

Each file is matched to an armature by name, so import the models first.
Anything that finds no rig is reported rather than skipped silently -
"N file(s) had NO MATCHING RIG" means the models step has not been run,
not that the animation is broken.

Same conversion as the single-file DMX Animation importer: bones, scale,
root motion, stepped-key resampling.

Use the Shot filter to take one shot out of a folder that holds several.
For a session, prefer the numbered session steps - they extract and route
for you"""
    bl_idname  = "ht.import_animations"
    bl_label   = "Animations (Folder)"
    # NO "REGISTER" - see the note in Report_UI/the constitution
    # REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    # touching any field in it RE-RUNS this operator. Re-running an
    # import re-reads the DMX and rebuilds every f-curve; nudging Scale
    # there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    # with the value you wanted is the safe way to change your mind
    bl_options = {"UNDO"}

    filepath:    StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})

    shot_filter:  StringProperty(name="Shot Filter", default=SHOT_FILTER)
    ignore_shot:  BoolProperty(name="Ignore Shot Number", default=IGNORE_SHOT_NUMBER)
    # [roadmap #1] precision 6 / step 1 / min 1e-6 - see Common_Props.
    anim_scale:   FloatProperty(**Common_Props.scale_prop(
        name="Animation Scale",
        description=(
            "Multiply every location key (bone locations + root motion) of "
            "every imported animation by this factor. 1.0 = untouched. Use "
            "when the session models were resized and the animations need "
            "to match. Rotations are never touched. Full precision is kept - "
            "Hammer Unit conversion needs far more than three decimals"
        ),
    ))

    scale_preset: EnumProperty(**Common_Props.scale_preset_prop())

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        self.layout.prop(self, "shot_filter")
        self.layout.prop(self, "ignore_shot")
        self.layout.separator()
        Common_Props.draw_scale(self.layout, self, "anim_scale")

    def execute(self, context):
        folder = Path(self.filepath)
        if folder.suffix or not folder.is_dir():
            folder = folder.parent

        try:
            result = run_harvester(folder,
                                   shot_filter=self.shot_filter,
                                   ignore_shot=self.ignore_shot,
                                   anim_scale=self.anim_scale)
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
            lines.append(f"Skipped  : {result['skipped']} (no matching armature)")
        lines.append("─" * 44)
        for r in result["results"]:
            arm_label = (f"→ {r['armature']}" if r["armature"]
                         else f"→ ('{r['target_key']}' not found)")
            lines.append(r["file"])
            lines.append(f"    {arm_label}  {r['status']}")

        from ..core import Report_UI
        Report_UI.report(
            context, "import_animations",
            f"Animations - {result['ok']}/{total} imported", lines,
            level=('WARNING' if (result["warned"] or result["skipped"])
                   else 'INFO'),
            operator=self, prefix="IMPORT_ANIMS",
            summary=f"Animations - {result['ok']}/{total} imported"
                    + (f", {result['skipped']} without a rig"
                       if result["skipped"] else ""))
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
# menu item
# ──────────────────────────────────────────────────────────────────────────────

def draw_menu_item(layout):
    """Standalone entry — used when NOT inside the IMPORT SESSION submenu."""
    layout.operator(
        HT_OT_ImportAnimations.bl_idname,
        text="Animations (Folder)",
        **_icon_id("import_animations", "ANIM"),
    )


def draw_session_entry(layout):
    """Entry 3 inside the IMPORT SESSION submenu."""
    layout.operator(
        HT_OT_ImportAnimations.bl_idname,
        text="2  Import DMX Session Animations",
        **_icon_id("import_animations", "ANIM"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# register / unregister
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (HT_OT_ImportAnimations,)


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
    bpy.ops.ht.import_animations("INVOKE_DEFAULT")
