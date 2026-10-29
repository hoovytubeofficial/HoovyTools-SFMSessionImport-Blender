"""
Import_Session.py  —  part of HoovyTools
=========================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ SFM Session

Combines:
  • SFM Session Importer (V19) — SourceIO-based, chunked, armature renamer
  • SFM Rig Fixer (V3)         — rest pose fixer using reference DMX files

PUBLIC API
──────────
    from . import Import_Session

    # Import models from a session file (chunked, picks up where it left off)
    Import_Session.run_session_import(Path("my_session.dmx"))

    # Fix rest poses for all armatures in the scene
    Import_Session.run_rig_fixer()

FAULTY RIGS SEARCH ORDER
─────────────────────────
  1. HoovyTools/Faulty Rigs/    (next to this file — always checked first)
  2. SFM usermod path           (hardcoded as FAULTY_RIGS_SFM_FOLDER below)
"""

bl_info = {
    "name":        "HoovyTools: Import SFM Session",
    "description": "Import SFM session models via SourceIO + fix rest poses",
    "author":      "HoovyTools",
    "version":     (1, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > SFM Session",
    "category":    "Import-Export",
}

import bpy
import addon_utils
import subprocess
import tempfile
import re
import os
import json
from pathlib import Path
from bpy.types import Operator
from bpy.props import StringProperty


# ──────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────────────────────────────────────

# Default paths — used as fallback when addon preferences are not set.
_DEFAULT_SFM_USERMOD = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\SourceFilmmaker\game\usermod"
)
_DEFAULT_FAULTY_RIGS_SFM = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\SourceFilmmaker"
    r"\game\usermod\plugins\___SFM to Blender Session Importer\_Dev\Faulty Rigs"
)

# Chunked import — imports CHUNK_SIZE models per operator invocation.
# Progress is saved on bpy.context.scene["sfm_import_state"].
IMPORT_IN_CHUNKS = True
CHUNK_SIZE       = 55


def _get_prefs():
    """Return the HoovyTools addon preferences, or None if unavailable."""
    try:
        return bpy.context.preferences.addons["HoovyTools"].preferences
    except (KeyError, AttributeError):
        return None


def get_gameinfo_base() -> Path:
    """Return the SFM usermod path. Priority: prefs → default."""
    prefs = _get_prefs()
    if prefs and prefs.sfm_usermod_path.strip():
        return Path(prefs.sfm_usermod_path.strip())
    return _DEFAULT_SFM_USERMOD


def get_faulty_rigs_sfm_folder() -> Path:
    """Return the SFM-side Faulty Rigs folder. Priority: prefs → default."""
    prefs = _get_prefs()
    if prefs and prefs.faulty_rigs_sfm_path.strip():
        return Path(prefs.faulty_rigs_sfm_path.strip())
    return _DEFAULT_FAULTY_RIGS_SFM


# ──────────────────────────────────────────────────────────────────────────────
#  FOLDER HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _addon_faulty_rigs_folder() -> Path:
    """HoovyTools/Faulty Rigs/ — sits next to this .py file."""
    return Path(__file__).parent / "Faulty Rigs"


def _faulty_rigs_search_folders() -> list:
    """
    Returns folders to search for reference DMX files, in priority order:
      1. HoovyTools/Faulty Rigs/
      2. SFM usermod Faulty Rigs folder
    Only returns folders that actually exist.
    """
    return [f for f in [_addon_faulty_rigs_folder(), get_faulty_rigs_sfm_folder()] if f.is_dir()]


# ──────────────────────────────────────────────────────────────────────────────
#  ICON HELPER
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None   # injected by __init__.py via register(icon_id_fn=...)

def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
#  SOURCEIO ENABLE
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_sourceio():
    if not addon_utils.check("SourceIO")[1]:
        addon_utils.enable("SourceIO", default_set=True)


# ──────────────────────────────────────────────────────────────────────────────
#  DMX → TEX CONVERSION
# ──────────────────────────────────────────────────────────────────────────────

def _find_dmxconvert(gameinfo_base: Path = None) -> Path:
    sfm_root = (gameinfo_base if gameinfo_base else get_gameinfo_base()).parent.parent
    for c in [sfm_root / "game/bin/dmxconvert.exe",
              sfm_root / "bin/dmxconvert.exe"]:
        if c.exists():
            return c.resolve()
    raise RuntimeError(
        "dmxconvert.exe not found.\n"
        "\n"
        "HoovyTools needs dmxconvert.exe to convert SFM session files.\n"
        "\n"
        "── OPTION A  (SFM installed) ────────────────────────────────\n"
        "  1. Open Edit > Preferences > Add-ons > HoovyTools\n"
        "  2. Set 'SFM Usermod Path' to your SFM usermod folder, e.g.:\n"
        "       C:\\Program Files (x86)\\Steam\\steamapps\\common\\SourceFilmmaker\\game\\usermod\n"
        "  dmxconvert.exe will be found automatically at SFM/game/bin/\n"
        "\n"
        "── OPTION B  (SFM not installed / path override) ────────────\n"
        "  1. Find dmxconvert.exe on any machine that has SFM installed\n"
        "     (it lives at SFM/game/bin/dmxconvert.exe)\n"
        "  2. Copy it anywhere on this machine\n"
        "  3. In the import dialog, set 'SFM Usermod Path Override' so that\n"
        "     going two folders up (..\\..) leads to the folder containing dmxconvert.exe\n"
        "     Example: if dmxconvert.exe is at D:\\tools\\game\\bin\\dmxconvert.exe\n"
        "              set override to   D:\\tools\\game\\usermod\n"
        "\n"
        f"Currently searched: {sfm_root / 'game/bin/dmxconvert.exe'}\n"
        f"                    {sfm_root / 'bin/dmxconvert.exe'}"
    )


def _convert_to_tex(dmx: Path, tmp_dir: str, gameinfo_base: Path = None) -> str:
    exe     = _find_dmxconvert(gameinfo_base)
    out_tex = Path(tmp_dir) / "session.tex"
    cmd     = [str(exe), "-i", str(dmx), "-ie", "binary",
               "-o", str(out_tex), "-of", "tex"]
    result  = subprocess.run(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return out_tex.read_text(encoding="utf-8", errors="ignore")


# ──────────────────────────────────────────────────────────────────────────────
#  V12 ELEMENT SCANNER
# ──────────────────────────────────────────────────────────────────────────────

_TYPE_RE = re.compile(r'^\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*$')
_ID_RE   = re.compile(r'^\s*"id"\s+"elementid"\s+"([^"]+)"')
_STR_RE  = re.compile(r'^\s*"([^"]+)"\s+"string"\s+"([^"]*)"')
_ELEM_RE = re.compile(r'^\s*"([^"]+)"\s+"element"\s+"([^"]+)"')
_MDL_KEYS = {"modelname", "modelfilename", "modelfile", "modelpath"}
_WANTED   = {"DmeAnimationSet", "CDmeAnimationSet",
             "DmeGameModel",    "CDmeGameModel"}


def _scan_elements(tex: str) -> list:
    lines = tex.splitlines()
    n = len(lines)
    results = []
    i = 0
    while i < n:
        m = _TYPE_RE.match(lines[i])
        if not m or m.group(1) not in _WANTED:
            i += 1
            continue
        j = i + 1
        while j < n and not lines[j].strip():
            j += 1
        if j >= n or not lines[j].strip().startswith("{"):
            i += 1
            continue
        depth = 1
        k = j + 1
        elem_id = elem_name = elem_model = gm_ref = None
        while k < n and depth > 0:
            s = lines[k].strip()
            if s in ("{", "["):
                depth += 1; k += 1; continue
            if s.startswith("}") or s.startswith("]"):
                depth -= 1; k += 1; continue
            if depth == 1:
                id_m = _ID_RE.match(lines[k])
                if id_m:
                    elem_id = id_m.group(1); k += 1; continue
                str_m = _STR_RE.match(lines[k])
                if str_m:
                    key = str_m.group(1).lower()
                    val = str_m.group(2)
                    if key == "name":
                        elem_name = val
                    elif key in _MDL_KEYS and val.lower().endswith(".mdl"):
                        mdl = val.replace("\\", "/").lstrip("/")
                        if mdl.lower().startswith("models/"):
                            elem_model = mdl
                    k += 1; continue
                ref_m = _ELEM_RE.match(lines[k])
                if ref_m:
                    if ref_m.group(1).lower() == "gamemodel":
                        gm_ref = ref_m.group(2)
                    k += 1; continue
            k += 1
        results.append({"type": m.group(1), "id": elem_id,
                        "name": elem_name or "", "model": elem_model,
                        "gm_ref": gm_ref})
        i = k
    return results


def _collect_import_list(tex: str) -> list:
    """Returns ordered list of (rel_mdl_path, animset_name) tuples."""
    elems       = _scan_elements(tex)
    game_models = {e["id"]: e for e in elems
                   if e["type"] in ("DmeGameModel", "CDmeGameModel") and e["id"]}
    import_list = []
    claimed     = set()

    for e in elems:
        if e["type"] not in ("DmeAnimationSet", "CDmeAnimationSet"):
            continue
        name = e["name"].strip()
        if not name:
            continue
        gm = game_models.get(e["gm_ref"]) if e["gm_ref"] else None
        if gm and gm["model"]:
            import_list.append((gm["model"], name))
            claimed.add(gm["id"])

    for e in elems:
        if e["type"] not in ("DmeGameModel", "CDmeGameModel"):
            continue
        if e["id"] in claimed or not e["model"]:
            continue
        import_list.append((e["model"], e["name"].strip() or "unknown"))

    return import_list


# ──────────────────────────────────────────────────────────────────────────────
#  SEARCH PATHS + MODEL RESOLVER
# ──────────────────────────────────────────────────────────────────────────────

def _build_search_paths(gameinfo_base: Path = None) -> list:
    if gameinfo_base is None:
        gameinfo_base = get_gameinfo_base()
    paths = [gameinfo_base]
    ginfo = gameinfo_base / "gameinfo.txt"
    if not ginfo.exists():
        print(f"[SESSION]  WARNING: gameinfo.txt not found at '{ginfo}'")
        print(f"[SESSION]  Check your SFM Usermod Path in addon preferences.")
        print(f"[SESSION]  Search paths: {paths}")
        return paths
    text  = ginfo.read_text(errors="ignore")
    block = re.search(r"SearchPaths\s*\{([^}]*)\}", text, re.S)
    if not block:
        print(f"[SESSION]  WARNING: No SearchPaths block found in '{ginfo}'")
        print(f"[SESSION]  Search paths: {paths}")
        return paths
    root = gameinfo_base.parent
    for line in block.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        raw = line.split()[-1].replace("|gameinfo_path|", str(gameinfo_base)).strip('"')
        # Skip lines with unresolved tokens (e.g. |all_source_engine_paths|)
        if "|" in raw:
            continue
        p = Path(raw)
        if not p.is_absolute():
            p = root / raw
        if p.exists():
            paths.append(p.resolve())
        else:
            print(f"[SESSION]  search path not found (skipped): '{p}'")
    print(f"[SESSION]  Search paths resolved ({len(paths)}): {[str(p) for p in paths]}")
    return paths


def _resolve_model(rel: str, search_dirs: list) -> Path | None:
    for d in search_dirs:
        test = d / rel
        if test.is_file():
            return test.resolve()
    return None


# ──────────────────────────────────────────────────────────────────────────────
#  SOURCEIO IMPORT + ARMATURE RENAME
# ──────────────────────────────────────────────────────────────────────────────

def _import_and_rename(abs_path: Path, animset_name: str) -> bool:
    before = {obj.name for obj in bpy.data.objects if obj.type == "ARMATURE"}

    # Call SourceIO directly (reliable in batch context), then apply the HT
    # eye fix via Import_MDL.apply_eye_fix() so session imports get the same
    # eye rig treatment as Source Model (.mdl) manual imports.
    # directory is only a registered property on Blender 4.1+.
    # On older versions get_directory() derives it from filepath automatically.
    _mdl_kwargs = dict(
        filepath          = str(abs_path),
        files             = [{"name": abs_path.name}],
        discover_resources= True,
        import_textures   = True,
        import_physics    = False,
        import_animations = False,
        scale             = 1.0,
    )
    if bpy.app.version >= (4, 1, 0):
        _mdl_kwargs["directory"] = str(abs_path.parent)
    result = bpy.ops.sourceio.mdl(**_mdl_kwargs)

    if "FINISHED" not in result:
        print(f"  [WARN] SourceIO returned {result} for {abs_path.name}")
        return False

    after        = {obj.name for obj in bpy.data.objects if obj.type == "ARMATURE"}
    new_armatures = after - before

    if not new_armatures:
        print(f"  [WARN] No new armature after importing {abs_path.name}")
        return False

    mdl_stem = abs_path.stem.lower()
    chosen   = next((n for n in new_armatures if mdl_stem in n.lower()), None) \
               or next(iter(new_armatures))

    arm_obj = bpy.data.objects[chosen]
    arm_obj.name = animset_name
    print(f"  Renamed '{chosen}' → '{animset_name}'")

    # Apply HT eye fix — same result as importing via Source Model (.mdl) manually
    try:
        from . import Import_MDL
        Import_MDL.apply_eye_fix(arm_obj)
    except Exception as e:
        print(f"  [WARN] Eye fix failed for '{animset_name}': {e}")

    return True


# ──────────────────────────────────────────────────────────────────────────────
#  CHUNK STATE
# ──────────────────────────────────────────────────────────────────────────────

_STATE_KEY = "sfm_import_state"


def _load_state() -> dict | None:
    raw = bpy.context.scene.get(_STATE_KEY)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _save_state(state: dict) -> None:
    bpy.context.scene[_STATE_KEY] = json.dumps(state)


def _clear_state() -> None:
    if _STATE_KEY in bpy.context.scene:
        del bpy.context.scene[_STATE_KEY]


# ──────────────────────────────────────────────────────────────────────────────
#  SESSION IMPORT — PUBLIC
# ──────────────────────────────────────────────────────────────────────────────

def run_session_import(session_path: Path,
                       gameinfo_base: Path = None) -> dict:
    """
    Import models from an SFM session DMX file.
    Chunked when IMPORT_IN_CHUNKS=True — call repeatedly to continue.

    gameinfo_base: optional Path override for the SFM usermod folder.
                   Defaults to addon preferences → _DEFAULT_SFM_USERMOD.

    Returns:
    {
        "ok":        bool,
        "imported":  int,
        "skipped":   int,
        "missing":   int,
        "remaining": int,
        "done":      bool,
        "message":   str,
    }
    """
    if gameinfo_base is None:
        gameinfo_base = get_gameinfo_base()

    print("\n" + "=" * 56)
    print("  SFM SESSION IMPORT  (HoovyTools)")
    print("=" * 56)
    print(f"  Session      : {session_path.name}")
    print(f"  Gameinfo base: {gameinfo_base}")

    _ensure_sourceio()

    with tempfile.TemporaryDirectory() as tmp:
        print("  Converting DMX → TEX...")
        tex = _convert_to_tex(session_path, tmp, gameinfo_base)

    print("  Parsing animation sets...")
    import_list = _collect_import_list(tex)
    search_dirs = _build_search_paths(gameinfo_base)
    total       = len(import_list)
    print(f"  Total instances: {total}")

    # ── Non-chunked ───────────────────────────────────────────
    if not IMPORT_IN_CHUNKS:
        ok = missing = 0
        for i, (rel, name) in enumerate(import_list, 1):
            abs_path = _resolve_model(rel, search_dirs)
            if not abs_path:
                print(f"  [{i}/{total}] MISSING  {rel}")
                missing += 1
                continue
            print(f"  [{i}/{total}] {name}  ←  {abs_path.name}")
            try:
                if _import_and_rename(abs_path, name):
                    ok += 1
            except Exception as e:
                print(f"  [ERROR] {abs_path.name}: {e}")
        return {"ok": True, "imported": ok, "skipped": 0,
                "missing": missing, "remaining": 0, "done": True,
                "message": f"Imported {ok} of {total} models."}

    # ── Chunked ───────────────────────────────────────────────
    session_key = str(session_path.resolve()) + "|" + str(gameinfo_base.resolve())
    state       = _load_state()

    if state is None or state.get("session") != session_key:
        state = {"session": session_key, "next_idx": 0, "total": total, "done": False}

    if state.get("done") or state.get("next_idx", 0) >= total:
        _clear_state()
        return {"ok": True, "imported": 0, "skipped": 0, "missing": 0,
                "remaining": 0, "done": True,
                "message": f"All {total} models already imported."}

    state["total"] = total
    next_idx       = state["next_idx"]
    chunk_end      = min(next_idx + CHUNK_SIZE, total)
    chunk          = import_list[next_idx:chunk_end]
    existing_names = {obj.name for obj in bpy.data.objects if obj.type == "ARMATURE"}

    print(f"\n  Chunk : {next_idx + 1}–{chunk_end} of {total}")
    ok = missing = skipped = 0

    for i, (rel, name) in enumerate(chunk, start=next_idx + 1):
        if name in existing_names:
            print(f"  [{i}/{total}] SKIP  {name}")
            skipped += 1
            continue
        abs_path = _resolve_model(rel, search_dirs)
        if not abs_path:
            print(f"  [{i}/{total}] MISSING  {rel}")
            missing += 1
            continue
        print(f"  [{i}/{total}] {name}  ←  {abs_path.name}")
        try:
            if _import_and_rename(abs_path, name):
                ok += 1
                existing_names.add(name)
        except Exception as e:
            print(f"  [ERROR] {abs_path.name}: {e}")

    state["next_idx"] = chunk_end
    state["done"]     = chunk_end >= total
    _save_state(state)

    remaining = total - chunk_end
    done      = state["done"]
    if done:
        if missing == 0 and ok > 0:
            msg = f"All {ok} model(s) imported successfully."
        elif ok == 0:
            msg = f"Done — but 0 of {total} models could be found on disk. Check your SFM Usermod Path."
        else:
            msg = f"Done — {ok} imported, {missing} model file(s) not found on disk."
    else:
        msg = f"Chunk done. {remaining} model(s) remaining — run again to continue."

    print(f"\n  Chunk done — imported:{ok}  skipped:{skipped}  missing:{missing}")
    return {"ok": True, "imported": ok, "skipped": skipped,
            "missing": missing, "remaining": remaining, "done": done,
            "message": msg}


# ──────────────────────────────────────────────────────────────────────────────
#  RIG FIXER HELPERS
# ──────────────────────────────────────────────────────────────────────────────

_ARM_DATA_RE = re.compile(r'_arm_data.*$', re.IGNORECASE)


def _extract_base_name(data_name: str) -> str:
    return _ARM_DATA_RE.sub("", data_name).strip()


def _find_reference_dmx(base_name: str) -> Path | None:
    """
    Search all Faulty Rigs folders for {base_name}_reference.dmx.
    HoovyTools/Faulty Rigs/ is checked before the SFM fallback folder.
    """
    target = f"{base_name}_reference.dmx".lower()
    for folder in _faulty_rigs_search_folders():
        for f in folder.iterdir():
            if f.suffix.lower() == ".dmx" and f.name.lower() == target:
                print(f"[RIG_FIXER]  reference found in: {folder.name}/")
                return f
    folders_str = ", ".join(f.name for f in _faulty_rigs_search_folders()) or "(none exist)"
    print(f"[RIG_FIXER]  '{target}' not found. Searched: {folders_str}")
    return None


def _import_reference_dmx(dmx_path: Path, armature) -> object:
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    before = {a.name for a in bpy.data.actions}
    result = bpy.ops.ht.import_smd(filepath=str(dmx_path))

    if "FINISHED" not in result:
        raise RuntimeError(f"SMD importer returned {result} for {dmx_path}")

    new_names = {a.name for a in bpy.data.actions} - before
    if not new_names:
        return None

    stem   = dmx_path.stem.lower()
    scored = sorted(new_names, key=lambda n: stem in n.lower(), reverse=True)
    action = bpy.data.actions[scored[0]]
    anim_data = armature.animation_data or armature.animation_data_create()
    anim_data.action = action
    return action


def _detach_action(armature) -> None:
    ad = armature.animation_data
    if ad is None:
        return
    ad.action = None
    for track in list(ad.nla_tracks):
        ad.nla_tracks.remove(track)


def _apply_pose_as_rest(armature) -> None:
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def _find_top_level_collection(armature):
    scene_root = bpy.context.scene.collection

    def find_in(col, obj, path):
        if obj.name in col.objects:
            return path + [col]
        for child in col.children:
            result = find_in(child, obj, path + [col])
            if result:
                return result
        return None

    path = find_in(scene_root, armature, [])
    if not path or len(path) < 2:
        return None
    return path[1]


def _mark_collection_yellow(armature) -> str:
    col = _find_top_level_collection(armature)
    if col is None:
        return ""
    col.color_tag = "COLOR_03"
    return col.name


def _process_armature_rig_fix(armature) -> dict:
    result = {"name": armature.name, "base": "", "status": "", "marked_col": ""}
    base_name       = _extract_base_name(armature.data.name)
    result["base"]  = base_name
    ref_dmx         = _find_reference_dmx(base_name)

    if ref_dmx is None:
        result["status"] = "— No reference file"
        return result

    print(f"[RIG_FIXER]  fixing '{armature.name}'  ref: '{ref_dmx.name}'")
    try:
        action = _import_reference_dmx(ref_dmx, armature)
        if action is None:
            result["status"] = "✗  Import OK but no action created"
            return result
        _detach_action(armature)
        _apply_pose_as_rest(armature)
        result["marked_col"] = _mark_collection_yellow(armature)
        result["status"]     = "✓  Rest pose applied"
    except Exception as exc:
        print(f"[RIG_FIXER]  ERROR on '{armature.name}': {exc}")
        result["status"] = f"✗  {exc}"

    return result


# ──────────────────────────────────────────────────────────────────────────────
#  RIG FIXER — PUBLIC
# ──────────────────────────────────────────────────────────────────────────────

def run_rig_fixer() -> dict:
    """
    Scan every armature in the scene and apply rest pose fixes.

    Returns:
    {
        "fixed":   int,
        "skipped": int,
        "errors":  int,
        "results": list[dict],
    }
    """
    if not hasattr(bpy.ops, "import_scene") or not hasattr(bpy.ops.import_scene, "smd"):
        raise RuntimeError("Blender Source Tools not enabled.")

    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        return {"fixed": 0, "skipped": 0, "errors": 0, "results": []}

    results = [_process_armature_rig_fix(arm) for arm in armatures]

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    fixed   = sum(1 for r in results if r["status"].startswith("✓"))
    skipped = sum(1 for r in results if r["status"].startswith("—"))
    errors  = sum(1 for r in results if r["status"].startswith("✗"))

    print(f"[RIG_FIXER]  done — fixed:{fixed}  skipped:{skipped}  errors:{errors}")
    return {"fixed": fixed, "skipped": skipped, "errors": errors, "results": results}


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATORS
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_ImportSession(Operator):
    """Import all models from an SFM session DMX file (chunked)"""
    bl_idname  = "ht.import_session"
    bl_label   = "SFM Session"
    bl_options = {"REGISTER", "UNDO"}

    filepath:    StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.dmx", options={"HIDDEN"})

    # Plain text field — no subtype="DIR_PATH" so it never opens a second
    # file browser while the session DMX picker is already open.
    gameinfo_override: StringProperty(
        name        = "SFM Usermod Path Override",
        description = "Override the SFM usermod path for this import only. "
                      "Leave blank to use the path from addon preferences.",
        default     = "",
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        layout = self.layout
        active = (Path(self.gameinfo_override.strip())
                  if self.gameinfo_override.strip()
                  else get_gameinfo_base())
        box = layout.box()
        box.label(text="SFM Usermod Path", icon="FILE_FOLDER")
        box.prop(self, "gameinfo_override", text="Override (blank = use prefs)")
        if not active.exists():
            row = box.row()
            row.alert = True
            row.label(text=f"Not found: {active}", icon="ERROR")
        else:
            box.label(text=f"Active: {active}", icon="CHECKMARK")

    def execute(self, context):
        override = (Path(self.gameinfo_override.strip())
                    if self.gameinfo_override.strip() else None)
        try:
            result = run_session_import(Path(self.filepath), gameinfo_base=override)
        except Exception as exc:
            # Show a proper popup so the error is impossible to miss
            err_lines = str(exc).splitlines()
            _err = list(err_lines)
            def draw_err(self, context):
                for line in _err:
                    self.layout.label(text=line, icon="NONE")
            context.window_manager.popup_menu(
                draw_err,
                title="Session Import Failed",
                icon="ERROR",
            )
            self.report({"ERROR"}, err_lines[0])
            return {"CANCELLED"}

        lines = [
            f"Session  : {Path(self.filepath).name}",
            f"Imported : {result['imported']}",
        ]
        if result["skipped"]:
            lines.append(f"Skipped  : {result['skipped']} (already in scene)")
        if result["missing"]:
            lines.append(f"Missing  : {result['missing']} model files")
        lines.append(f"Remaining: {result['remaining']}")
        lines.append(result["message"])

        icon = "CHECKMARK" if result["done"] else "TIME"
        _lines = list(lines)
        def draw(self, context):
            for line in _lines:
                self.layout.label(text=line)
        context.window_manager.popup_menu(draw, title="SFM Session Import", icon=icon)
        self.report({"INFO"}, result["message"])
        return {"FINISHED"}


class HT_OT_RigFixer(Operator):
    """Fix rest poses for all armatures using reference DMX files"""
    bl_idname  = "ht.rig_fixer"
    bl_label   = "Fix Rig Rest Poses"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            result = run_rig_fixer()
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        lines = [
            f"Scanned : {result['fixed'] + result['skipped'] + result['errors']}",
            f"Fixed   : {result['fixed']}",
            f"Skipped : {result['skipped']} (no reference file)",
        ]
        if result["errors"]:
            lines.append(f"Errors  : {result['errors']}")

        icon  = "CHECKMARK" if not result["errors"] else "ERROR"
        _lines = list(lines)
        def draw(self, context):
            for line in _lines:
                self.layout.label(text=line)
        context.window_manager.popup_menu(draw, title="Rig Fixer", icon=icon)
        self.report({"INFO"}, f"Rig Fixer: {result['fixed']} fixed, {result['skipped']} skipped")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU ITEMS  (called directly from MT_HT_import_submenu.draw in __init__.py)
# ──────────────────────────────────────────────────────────────────────────────

def draw_submenu(layout):
    """
    Draw the three numbered IMPORT SESSION entries.
    Called from MT_HT_session_submenu.draw() in __init__.py.
    """
    layout.operator(
        HT_OT_ImportSession.bl_idname,
        text="1  Import DMX Session Models",
        **_icon_id("import_session_models", "SCENE_DATA"),
    )
    layout.operator(
        HT_OT_RigFixer.bl_idname,
        text="2  Import DMX Session Fixed Rigs",
        **_icon_id("rig_fixer", "ARMATURE_DATA"),
    )
    # Entry 3 is drawn by Import_Animations via __init__.py


def draw_menu_item(layout):
    """
    Top-level menu entry for MT_HT_import_submenu in __init__.py.
    Draws all Import Session operators (session import + rig fixer).
    """
    draw_submenu(layout)


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (HT_OT_ImportSession, HT_OT_RigFixer)


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
    bpy.ops.ht.import_session("INVOKE_DEFAULT")
