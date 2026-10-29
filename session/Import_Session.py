"""
Import_Session.py  —  part of HoovyTools
=========================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ SFM Session

Combines:
  • SFM Session Importer (V19) — SourceIO-based, armature renamer
  • SFM Rig Fixer (V3)         — rest pose fixer using reference DMX files

PUBLIC API
──────────
    from . import Import_Session

    # Import models from a session file (one pass; already-imported models are skipped)
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
from ..core import Progress
from ..core import paths as _ht_paths
from ..core import paths as _paths
from ..core import user_paths as _user_paths
import math

from mathutils import Vector
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
    r"\game\usermod\plugins\___SFM to Blender Session Importer\_Dev\_Faulty Rigs"
)



def _get_prefs():
    """Return the HoovyTools addon preferences, or None if unavailable."""
    try:
        return _ht_paths.addon_prefs()
    except (KeyError, AttributeError):
        return None


def usermod_bases() -> list:
    """Every SFM install to search, best first. Preference, then the extras.

    ONE PATH WAS NEVER ENOUGH. People keep SFM on more than one drive - a Steam
    library that moved, an old install kept for one mod - and with a single
    value the answer to "why can it not find my model" is "because it is in the
    other install", which fixing the path does not solve: fixing it breaks the
    first one. So all of them are searched, in order.

    The preference is slot 1 and `core/user_paths.py` holds slots 2 and 3, so
    an install that never added anything has no JSON and behaves exactly as it
    did before. De-duplicated by resolved path.
    """
    out, seen = [], set()
    for p in [_pref_usermod()] + _user_paths.folders("usermod"):
        if p is None or not p.is_dir():
            continue
        try:
            r = p.resolve()
        except OSError:
            r = p
        if r in seen:
            continue
        seen.add(r)
        out.append(p)
    return out


def _pref_usermod() -> Path:
    """Slot 1: whatever the preference says, valid or not."""
    prefs = _get_prefs()
    if prefs and prefs.sfm_usermod_path.strip():
        return Path(bpy.path.abspath(prefs.sfm_usermod_path.strip()))
    return _DEFAULT_SFM_USERMOD


def get_gameinfo_base() -> Path:
    """THE usermod path - the first one that actually exists.

    Everything that only wants one install still calls this and still gets one.
    It returns the first VALID base rather than always the preference, so a
    user whose C: install is gone but whose D: install is listed gets the D:
    one instead of an error about C:.

    When NONE of them exist it returns the preference anyway, so the failure
    message names the path the user configured rather than a default they have
    never seen.
    """
    bases = usermod_bases()
    return bases[0] if bases else _pref_usermod()


def get_faulty_rigs_sfm_folder() -> Path:
    """The SFM-side Faulty Rigs folder. Priority: prefs -> default.

    Run through `data_dir_at` so `_Faulty Rigs` and `Faulty Rigs` are both
    accepted at whatever the path points AT. The underscore convention now
    reaches into the SFM plugins tree - the folder there was renamed to match
    - and a user still holding the bare-named one must not lose their
    reference rigs over a rename they did not make.
    """
    prefs = _get_prefs()
    raw = ""
    if prefs is not None:
        raw = (prefs.faulty_rigs_sfm_path or "").strip()
    p = Path(bpy.path.abspath(raw)) if raw else _DEFAULT_FAULTY_RIGS_SFM
    if p.is_dir():
        return p
    #  Pointed at the parent, or at the name that is no longer there.
    return _paths.data_dir_at(p.parent, p.name.lstrip("_"))


def get_faulty_rigs_override() -> Path | None:
    """The user's own Faulty Rigs folder from preferences, or None."""
    prefs = _get_prefs()
    if prefs is None:
        return None
    raw = (getattr(prefs, "faulty_rigs_path", "") or "").strip()
    if not raw:
        return None
    p = Path(bpy.path.abspath(raw))
    return p if p.is_dir() else None


# ──────────────────────────────────────────────────────────────────────────────
#  FOLDER HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _addon_faulty_rigs_folder() -> Path:
    """HoovyTools/Faulty Rigs/ — sits next to this .py file."""
    return _paths.faulty_rigs()


def _faulty_rigs_search_folders() -> list:
    """Folders to search for reference DMX files, in priority order:

      1. The preferences override, if one is set. FIRST on purpose - the
         whole reason to set it is to beat the shipped file for one rig.
      2. HoovyTools/_Faulty Rigs/ - what ships.
      3. The SFM-side copy in the plugins tree.

    Only folders that actually exist come back, so a blank override and a
    missing SFM tree both just shorten the list.
    """
    candidates = ([get_faulty_rigs_override()]
                  + _user_paths.folders("faulty_rigs")
                  + [_addon_faulty_rigs_folder(),
                     get_faulty_rigs_sfm_folder()]
                  #  The SFM-side copy inside EVERY install, not just the
                  #  primary - someone with two SFMs has two of these.
                  + [_paths.data_dir_at(b / "plugins"
                                        / "___SFM to Blender Session Importer"
                                        / "_Dev", "Faulty Rigs")
                     for b in usermod_bases()])
    out = []
    for f in candidates:
        if f is not None and f.is_dir() and f not in out:
            out.append(f)
    return out


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

# SourceIO is usually installed straight from its GitHub zip, which unpacks as
# "SourceIO-master" - so that, not "SourceIO", is the module name Blender knows
# it by. Enabling by the pretty name works only once something else has already
# loaded it, which is why this never showed up interactively and always did in
# a headless run: "No module named 'SourceIO'", then every model import failing
# with "operator bpy.ops.sourceio.mdl could not be found".
_SOURCEIO_MODULES = ("SourceIO", "SourceIO-master")


def _ensure_sourceio():
    for name in _SOURCEIO_MODULES:
        if addon_utils.check(name)[1]:
            return name
    for name in _SOURCEIO_MODULES:
        try:
            if addon_utils.enable(name, default_set=True) is not None:
                print(f"[SESSION]  enabled SourceIO as '{name}'")
                return name
        except Exception:
            pass
    print("[SESSION]  [WARN] SourceIO could not be enabled - model import "
          "will fail. Tried: " + ", ".join(_SOURCEIO_MODULES))
    return None


# ──────────────────────────────────────────────────────────────────────────────
#  DMX → TEX CONVERSION
# ──────────────────────────────────────────────────────────────────────────────

def _dmxconvert_folders() -> list:
    """Folders the user pointed at for dmxconvert.exe, best first."""
    out = []
    prefs = _get_prefs()
    raw = (getattr(prefs, "dmxconvert_path", "") or "").strip() if prefs else ""
    if raw:
        p = Path(bpy.path.abspath(raw))
        if p.is_dir():
            out.append(p)
    out.extend(_user_paths.folders("dmxconvert"))
    return out


def _find_dmxconvert(gameinfo_base: Path = None) -> Path:
    #  THE USER'S OWN FOLDERS FIRST. Someone with a broken SFM and a working
    #  Source SDK can point at the SDK's copy, which is the whole reason this
    #  is overridable - the exe is Valve's and identical everywhere.
    for folder in _dmxconvert_folders():
        c = folder / "dmxconvert.exe"
        if c.is_file():
            return c.resolve()

    #  ACROSS ALL INSTALLS. A second SFM added because the first one is broken
    #  is exactly the case where the first one's bin/ is the missing thing, so
    #  looking only next to the primary usermod would report "not found" while
    #  a working copy sat one slot down the list.
    bases = [gameinfo_base] if gameinfo_base else (usermod_bases()
                                                   or [_pref_usermod()])
    for base in bases:
        sfm_root = base.parent.parent
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
        # dmxconvert can fail with NOTHING on stderr. Raising an empty
        # RuntimeError made the operator's own error handler blow up on
        # err_lines[0] - a crash inside a crash, which hid the real cause.
        detail = (result.stderr or "").strip() or (result.stdout or "").strip()
        if not detail:
            detail = (f"dmxconvert exited with code {result.returncode} and "
                      f"said nothing.\n"
                      f"Command: {' '.join(str(c) for c in cmd)}\n"
                      f"Usually this means the session references a game "
                      f"path that does not resolve - check the SFM Usermod "
                      f"Path in Preferences.")
        raise RuntimeError(detail)
    return out_tex.read_text(encoding="utf-8", errors="ignore")


# ──────────────────────────────────────────────────────────────────────────────
#  V12 ELEMENT SCANNER
# ──────────────────────────────────────────────────────────────────────────────

_TYPE_RE = re.compile(r'^\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*$')
_ID_RE   = re.compile(r'^\s*"id"\s+"elementid"\s+"([^"]+)"')
_STR_RE  = re.compile(r'^\s*"([^"]+)"\s+"string"\s+"([^"]*)"')
_ELEM_RE = re.compile(r'^\s*"([^"]+)"\s+"element"\s+"([^"]+)"')
#  1.16.0: DmeGameModel's "body" - every bodygroup choice packed in one int
_INT_RE  = re.compile(r'^\s*"([^"]+)"\s+"int"\s+"(-?\d+)"')
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
        elem_body = None
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
                int_m = _INT_RE.match(lines[k])
                if int_m:
                    if int_m.group(1).lower() == "body":
                        elem_body = int(int_m.group(2))
                    k += 1; continue
            k += 1
        results.append({"type": m.group(1), "id": elem_id,
                        "name": elem_name or "", "model": elem_model,
                        "gm_ref": gm_ref, "body": elem_body})
        i = k
    return results


#  (model, animset name) -> the session's `body` for it. Filled by
#  _collect_import_list; read by run_session_import. A side table rather than
#  a third tuple member, so nothing that unpacks (rel, name) has to change.
SESSION_BODIES = {}


def _collect_import_list(tex: str, keep_names=None) -> list:
    """Ordered list of (rel_mdl_path, animset_name) tuples.

    `keep_names` limits the result to one shot's animation sets, and DEDUPES.
    Both halves are needed. On a seventeen-shot film the same character has
    seventeen DmeAnimationSet elements under one name - one per cut - so
    filtering by name alone still returns seventeen `gomez` entries and
    imports the model seventeen times, which is the bug wearing a hat.

    Deduped on (model, name) rather than on name alone, so a genuine model
    swap mid-film - the same character re-pointed at a different .mdl - still
    produces both. That is rare and it is real, and silently keeping one of
    them would be a wrong scene with no error in it.
    """
    SESSION_BODIES.clear()        # never carry one session's bodies into the next
    elems       = _scan_elements(tex)
    game_models = {e["id"]: e for e in elems
                   if e["type"] in ("DmeGameModel", "CDmeGameModel") and e["id"]}
    import_list = []
    claimed     = set()

    seen_pairs  = set()

    def add(model, name):
        if keep_names is not None:
            if name not in keep_names:
                return
            pair = (model, name)
            if pair in seen_pairs:
                return
            seen_pairs.add(pair)
        import_list.append((model, name))

    for e in elems:
        if e["type"] not in ("DmeAnimationSet", "CDmeAnimationSet"):
            continue
        name = e["name"].strip()
        if not name:
            continue
        gm = game_models.get(e["gm_ref"]) if e["gm_ref"] else None
        if gm and gm["model"]:
            add(gm["model"], name)
            claimed.add(gm["id"])
            if gm.get("body") is not None:
                SESSION_BODIES[(gm["model"], name)] = gm["body"]

    for e in elems:
        if e["type"] not in ("DmeGameModel", "CDmeGameModel"):
            continue
        if e["id"] in claimed or not e["model"]:
            continue
        add(e["model"], e["name"].strip() or "unknown")
        if e.get("body") is not None:
            SESSION_BODIES[(e["model"], e["name"].strip() or "unknown")] = e["body"]

    return import_list


# ──────────────────────────────────────────────────────────────────────────────
#  SEARCH PATHS + MODEL RESOLVER
# ──────────────────────────────────────────────────────────────────────────────

def _scan_game_mounts() -> bool:
    """Preference: also search every mod folder under SourceFilmmaker/game."""
    prefs = _get_prefs()
    if prefs is None:
        return True
    return bool(getattr(prefs, "scan_game_mounts", True))


def _build_search_paths(gameinfo_base: Path = None) -> list:
    """Where a session's `models/...` path is allowed to be found, best first.

    THREE SOURCES, IN PRIORITY ORDER, AND THE ORDER IS THE WHOLE DESIGN:

      1. usermod itself.
      2. Whatever `gameinfo.txt` lists in its SearchPaths block. This is
         Valve's own priority order, so it must stay ahead of anything this
         add-on works out for itself - a mod that deliberately overrides a
         TF2 model does it by sitting higher in gameinfo, and re-sorting that
         list would silently hand back the wrong model.
      3. EVERY OTHER MOD FOLDER UNDER `game/`, alphabetically, as a fallback.

    Step 3 is the fix for the reports of Workshop content not being found.
    A stock `gameinfo.txt` does not mention `game/workshop` at all - SFM
    mounts it itself - so a Workshop model resolved to nothing and the failure
    read as "model missing from the session", which is a different problem
    from the one the user actually had. Measured on a real install: the
    gameinfo block resolves 4 paths, the folder scan finds 27 mounts.

    Being LAST is what makes step 3 safe. A path already contributed by
    gameinfo is not added twice, so the scan can only ever add a place to
    look, never re-order the places that were already being looked at.
    """
    if gameinfo_base is None:
        #  EVERY install, not only the first. An explicit override still means
        #  "just this one" - that is what an override is for, and the session
        #  dialog's per-import override depends on it.
        out = []
        for base in (usermod_bases() or [_pref_usermod()]):
            for d in _build_search_paths(base):
                if d not in out:
                    out.append(d)
        if len(out) > 1:
            print(f"[SESSION]  {len(out)} search path(s) across "
                  f"{len(usermod_bases())} SFM install(s)")
        return out
    paths = [gameinfo_base]
    ginfo = gameinfo_base / "gameinfo.txt"
    if not ginfo.exists():
        print(f"[SESSION]  WARNING: gameinfo.txt not found at '{ginfo}'")
        print(f"[SESSION]  Check your SFM Usermod Path in addon preferences.")
        return _append_game_mounts(paths, gameinfo_base)
    text  = ginfo.read_text(errors="ignore")
    block = re.search(r"SearchPaths\s*\{([^}]*)\}", text, re.S)
    if not block:
        print(f"[SESSION]  WARNING: No SearchPaths block found in '{ginfo}'")
        return _append_game_mounts(paths, gameinfo_base)
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
            rp = p.resolve()
            if rp not in paths:
                paths.append(rp)
        else:
            print(f"[SESSION]  search path not found (skipped): '{p}'")
    return _append_game_mounts(paths, gameinfo_base)


def _append_game_mounts(paths: list, gameinfo_base: Path) -> list:
    """Add the mod folders `gameinfo.txt` did not mention, and report once.

    ONE LINE, NOT TWENTY-SEVEN. The old builder printed the whole resolved
    list on every import; at 4 paths that was readable and at 31 it is a wall
    that hides the warnings above it. The names go out at a glance and the
    full list stays one `Search paths` line away for anyone who wants it.
    """
    from_gameinfo = len(paths)
    if _scan_game_mounts():
        known = {Path(p).resolve() for p in paths}
        for mount in _paths.mod_dirs(gameinfo_base):
            if mount not in known:
                paths.append(mount)
                known.add(mount)
    added = len(paths) - from_gameinfo
    names = [p.name for p in paths[from_gameinfo:]]
    shown = ", ".join(names[:8]) + (f", +{len(names) - 8} more" if len(names) > 8 else "")
    print(f"[SESSION]  Search paths: {from_gameinfo} from gameinfo"
          + (f" + {added} mod folder(s) under game/ ({shown})" if added else
             " (game/ scan off, or nothing to add)"))
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

#  Valve's convention: a model compiled with $staticprop has exactly one bone
#  and it is called "static_prop". Confirmed in a real session -
#  `models/props_badlands/barrel01.mdl` animates `static_prop_p` (82 keys) and
#  `static_prop_o` against a DAG child named `bone 0 (static_prop)`.
STATIC_PROP_BONE = "static_prop"


def build_static_prop_rig(meshes, rig_name, bone_name=STATIC_PROP_BONE):
    """Give a static prop the one bone SourceIO does not build for it.

    THE PROBLEM
    -----------
    SFM animates a static prop exactly like anything else: the session carries
    `static_prop_p` / `static_prop_o` channels aimed at a DAG node named
    `bone 0 (static_prop)`. But SourceIO imports a $staticprop model as MESHES
    ONLY - no armature, because the MDL's single bone is not deform data as far
    as it is concerned. So the animation arrives with nothing to land on, the
    file is reported as "NO MATCHING RIG", and the barrel sits at the origin
    while everything around it moves.

    The fix is exactly as small as it sounds: build a one-bone armature at the
    origin with identity rest orientation, weight the meshes to it, and the
    ordinary animation path works unchanged.

    WHY tail = (0, 1, 0) AND NOT (0, 0, 1)
    --------------------------------------
    A Blender bone's local Y axis runs head -> tail. With head at the origin,
    tail on +Y and roll 0, `bone.matrix_local` is the IDENTITY - which is what
    the DMX means by an untransformed bone. Point the tail at +Z instead and
    the rest matrix carries a 90 degree rotation that every imported key then
    inherits, and the prop arrives tipped over. Length does not affect the
    matrix, only how big the bone looks.

    Returns the armature object, or None if there was nothing to rig.
    """
    meshes = [m for m in meshes if m and m.type == 'MESH']
    if not meshes:
        return None

    arm_data = bpy.data.armatures.new(rig_name)
    arm_obj = bpy.data.objects.new(rig_name, arm_data)

    #  Land it in the same collection the meshes went into, so a static prop
    #  does not end up somewhere else in the outliner from everything else the
    #  same import produced.
    colls = meshes[0].users_collection
    (colls[0] if colls else bpy.context.scene.collection).objects.link(arm_obj)

    prev = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = arm_obj
    try:
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm_data.edit_bones.new(bone_name)
        eb.head = (0.0, 0.0, 0.0)
        eb.tail = (0.0, 1.0, 0.0)      # see the docstring - identity rest
        eb.roll = 0.0
        eb.use_deform = True
        bpy.ops.object.mode_set(mode='OBJECT')
    finally:
        bpy.context.view_layer.objects.active = prev

    #  Weight every vertex to the one bone. A static prop is rigid by
    #  definition, so full weight on everything is not an approximation.
    for mesh in meshes:
        if mesh.parent is None:
            mesh.parent = arm_obj
        vg = mesh.vertex_groups.get(bone_name) or mesh.vertex_groups.new(
            name=bone_name)
        vg.add(range(len(mesh.data.vertices)), 1.0, 'REPLACE')
        if not any(m.type == 'ARMATURE' and m.object == arm_obj
                   for m in mesh.modifiers):
            mod = mesh.modifiers.new(name="Armature", type='ARMATURE')
            mod.object = arm_obj

    print(f"  Static prop: built a 1-bone rig '{rig_name}' "
          f"(bone '{bone_name}') for {len(meshes)} mesh(es)")
    return arm_obj


def _import_and_rename(abs_path: Path, animset_name: str,
                       body: int = None, textures: str = "FULL",
                       engine: str = None, search_dirs=None):
    before = {obj.name for obj in bpy.data.objects if obj.type == "ARMATURE"}
    #  ALL objects, not just armatures: a static prop produces no armature at
    #  all, and the meshes it did produce are what we need to find.
    before_all = set(bpy.data.objects)

    #  1.21.0: SourceIO or the embedded importer (core/model_engine.py - DEVELOPER > Model Importer), at the
    #  session's scale 1.0, with or without textures; the HT eye fix runs after either, so session imports get
    #  the same eye rig treatment as Source Model (.mdl) manual imports.
    from ..core import model_engine
    ok_imp, _eng, _made, note = model_engine.import_mdl(abs_path, textures, scale=1.0, eng=engine)
    if not ok_imp:
        print(f"  [WARN] {note or 'the import failed'} for {abs_path.name}")
        return False

    after        = {obj.name for obj in bpy.data.objects if obj.type == "ARMATURE"}
    new_armatures = after - before
    fresh         = [o for o in bpy.data.objects if o not in before_all]

    proxy = None
    if str(textures).upper() == "PROXY":
        #  1.21.0: a small copy of each material's own texture (core/proxy_textures.py)
        try:
            from ..core import proxy_textures
            proxy = proxy_textures.apply(fresh, abs_path, search_dirs or _build_search_paths())
        except Exception as exc:                              # noqa: BLE001
            print(f"  [WARN] proxy textures skipped for '{animset_name}': {exc}")
    elif str(textures).upper() == "NONE":
        try:
            from ..core import proxy_textures
            proxy_textures.plain(fresh)
        except Exception as exc:                              # noqa: BLE001
            print(f"  [WARN] plain materials skipped for '{animset_name}': {exc}")

    #  1.16.0: SourceIO brings in every option of every bodygroup; SFM shows
    #  one per bodygroup, chosen by the session's `body`. Hide the rest.
    if body is not None:
        try:
            from ..tools import Session_Bodygroups
            Session_Bodygroups.apply_session_bodygroups(
                fresh, abs_path, body, label=animset_name)
        except Exception as exc:                              # noqa: BLE001
            print(f"  [WARN] bodygroups skipped for '{animset_name}': {exc}")

    if not new_armatures:
        #  NO ARMATURE IS NOT AUTOMATICALLY A FAILURE.
        #
        #  A model compiled with $staticprop imports as meshes only - SourceIO
        #  does not build a rig for its single bone. This used to return False,
        #  so the model counted as failed AND its animation later reported
        #  "NO MATCHING RIG", which reads as two problems when it is one and
        #  neither of them is the model.
        #
        #  SFM animates it anyway: barrel011 carries `static_prop_p` with 82
        #  keys. Give it the bone SourceIO left out and the ordinary animation
        #  path handles it with no further special cases.
        meshes = [o for o in fresh if o.type == 'MESH']
        if meshes:
            arm_obj = build_static_prop_rig(meshes, animset_name)
            if arm_obj is not None:
                print(f"  Imported '{abs_path.name}' as a STATIC PROP "
                      f"-> '{animset_name}'")
                return proxy or True
        print(f"  [WARN] No new armature and no meshes after importing "
              f"{abs_path.name}")
        return False

    mdl_stem = abs_path.stem.lower()
    chosen   = next((n for n in new_armatures if mdl_stem in n.lower()), None) \
               or next(iter(new_armatures))

    arm_obj = bpy.data.objects[chosen]
    arm_obj.name = animset_name
    print(f"  Renamed '{chosen}' → '{animset_name}'")

    # Apply HT eye fix — same result as importing via Source Model (.mdl) manually
    #
    # apply_eye_fix REPORTS failure, it does not raise it, so the return value
    # has to be read. Ignoring it hid the case that matters: no eye empties
    # means no viewTarget bone, and no viewTarget bone means the animation
    # importer later drops the session's viewTarget channel with nothing but a
    # console line. Import_DMX_Animation.ensure_file_root_bones() now creates
    # the bone from the file as a backstop, but a model that got no eye rig at
    # all is still worth hearing about.
    try:
        from ..importers import Import_MDL
        fix = Import_MDL.apply_eye_fix(arm_obj)
        if not fix.get("ok"):
            print(f"  [WARN] Eye fix skipped for '{animset_name}': "
                  f"{fix.get('error') or 'unknown reason'}")
        else:
            print(f"  Eye fix: {fix.get('eyes_fixed', 0)} eye(s) -> viewTarget")
    except Exception as e:
        print(f"  [WARN] Eye fix failed for '{animset_name}': {e}")

    return proxy or True



# ──────────────────────────────────────────────────────────────────────────────
#  SESSION IMPORT — PUBLIC
# ──────────────────────────────────────────────────────────────────────────────

def _shot_set_names(session_path: Path, tex: str = None):
    """The set names of the scene's chosen shot, or None for the whole session.

    Reads the shot list off the file rather than trusting a cached one - the
    session on disk is what is about to be imported, and a stale shot list
    would silently import the wrong cut. Returns None on ANY failure, which
    means "no filter": a shot list that cannot be read must not stop an import
    that worked perfectly well before shots existed.
    """
    try:
        from . import Session_Paths
        idx, name = Session_Paths.shot_choice()
        if idx is None or int(idx) < 0:
            return None
        from . import Session_Reader
        model = Session_Reader.load_session_model(session_path)
        fps = Session_Reader.session_fps(model.root) or 24.0
        shots = Session_Reader.shots(model, fps)
        shot, note = Session_Paths.resolve_shot(shots, index=idx, name=name)
        if note:
            print(f"[SESSION]  {note}")
        if shot is None:
            return None
        names = set(shot["set_names"])
        print(f"[SESSION]  shot {shot['index'] + 1} '{shot['name']}' - "
              f"{len(names)} animation set name(s), frames "
              f"{shot['frame_start']}-{shot['frame_end']}")
        return names
    except Exception as exc:                                  # noqa: BLE001
        print(f"[SESSION]  shot filter unavailable ({exc}) - importing "
              f"the whole session")
        return None


@Progress.jobbed("HoovyTools - Import Session Models")
def run_session_import(session_path: Path,
                       gameinfo_base: Path = None, textures: str = None,
                       only=None) -> dict:
    """
    Import models from an SFM session DMX file.
    One pass, every model. See the note above the shot filter.

    gameinfo_base: optional Path override for the SFM usermod folder.
                   Defaults to addon preferences → _DEFAULT_SFM_USERMOD.
    textures:      1.21.0 - FULL / PROXY / NONE; None = the session panel's
                   Textures choice (core/model_engine.textures()).
    only:          1.21.0 - animation set names to import (others skipped),
                   for another add-on that needs a few characters of a shot.

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
    try:
        from ..core import sources
        sources.add("session", session_path.stem, session_path)
    except Exception:
        pass
    print(f"  Gameinfo base: {gameinfo_base}")

    from ..core import model_engine
    textures = (textures or model_engine.textures()).upper()
    engine = model_engine.engine()                  # 1.21.0: SourceIO is enabled here when it is the engine
    print(f"  Models       : {engine.lower()} importer, textures {textures.lower()}")
    if only is not None:
        only = {str(n) for n in only}
        print(f"  Only         : {', '.join(sorted(only))}")

    with tempfile.TemporaryDirectory() as tmp:
        print("  Converting DMX → TEX...")
        Progress.note("Converting DMX -> TEX (dmxconvert)...")
        tex = _convert_to_tex(session_path, tmp, gameinfo_base)

    print("  Parsing animation sets...")
    Progress.note("Parsing animation sets...")
    keep = _shot_set_names(session_path, tex)
    import_list = _collect_import_list(tex, keep_names=keep)
    #  1.26.0 SKIP HIDDEN OBJECTS (Developer Mode): the sets SFM hides are not imported
    from ..tools import Session_Visibility
    hidden = Session_Visibility.hidden_set_names(session_path)
    search_dirs = _build_search_paths(gameinfo_base)
    total       = len(import_list)
    print(f"  Total instances: {total}")

    ok = missing = skipped = 0

    existing = {o.name for o in bpy.data.objects if o.type == "ARMATURE"}

    proxied = grey = 0
    left_hidden = []
    for i, (rel, name) in enumerate(import_list, 1):
        if only is not None and name not in only:
            skipped += 1
            continue
        if name in hidden:
            print(f"  [{i}/{total}] SKIP  {name}  (hidden in SFM by {hidden[name]} - Skip Hidden Objects)")
            left_hidden.append(name)
            continue
        if name in existing:
            print(f"  [{i}/{total}] SKIP  {name}  (already in the scene)")
            skipped += 1
            continue
        abs_path = _resolve_model(rel, search_dirs)
        if not abs_path:
            print(f"  [{i}/{total}] MISSING  {rel}")
            missing += 1
            continue
        print(f"  [{i}/{total}] {name}  <-  {abs_path.name}")
        #  Painted BEFORE the import call: this is the label that stays on
        #  screen while a heavy model blocks everything, which is the
        #  whole answer to "frozen or keeled over".
        Progress.update(i, total, f"{name}  <-  {abs_path.name}")
        try:
            done = _import_and_rename(abs_path, name, body=SESSION_BODIES.get((rel, name)),
                                      textures=textures, engine=engine, search_dirs=search_dirs)
            if done:
                if isinstance(done, dict):
                    proxied += done.get("proxied", 0)
                    grey += done.get("grey", 0)
                ok += 1
                existing.add(name)
                #  WHICH .mdl, recorded where it was RESOLVED. The name alone
                #  is useless - three `scout.mdl` under three mods is normal -
                #  and this is the only point in the pipeline that still knows
                #  which one won the search.
                try:
                    from ..core import sources
                    sources.add("model", name, abs_path)
                except Exception:
                    pass
        except Exception as e:
            print(f"  [ERROR] {abs_path.name}: {e}")

    if missing == 0 and ok > 0:
        msg = f"All {ok} model(s) imported successfully."
    elif ok == 0 and skipped:
        msg = f"All {skipped} model(s) were already in the scene."
    elif ok == 0 and left_hidden and not missing:
        msg = "Nothing to import."
    elif ok == 0:
        msg = (f"0 of {total} models could be found on disk. "
               f"Check your SFM Usermod Path.")
    else:
        msg = f"{ok} imported, {missing} model file(s) not found on disk."

    if left_hidden:
        msg += f" {len(left_hidden)} hidden in SFM left out (Skip Hidden Objects)."
    if textures == "PROXY":
        msg += f" Proxy textures: {proxied} material(s), {grey} grey."
    print(f"\n  Done - imported:{ok}  missing:{missing}  ({engine.lower()}, textures {textures.lower()})")
    #  `remaining` and `done` are kept in the result so a caller written
    #  against the chunked version still reads sensibly; they are now always
    #  0 and True.
    return {"ok": True, "imported": ok, "skipped": skipped,
            "missing": missing, "remaining": 0, "done": True,
            "message": msg, "engine": engine, "textures": textures,
            "proxied": proxied, "grey": grey, "skipped_hidden": sorted(left_hidden)}


# ──────────────────────────────────────────────────────────────────────────────
#  RIG FIXER HELPERS
# ──────────────────────────────────────────────────────────────────────────────

_ARM_DATA_RE = re.compile(r'_arm_data.*$', re.IGNORECASE)


def _extract_base_name(data_name: str) -> str:
    return _ARM_DATA_RE.sub("", data_name).strip()


def _reference_stems():
    """{lowercase model name: Path} for every *_reference.dmx we can see."""
    out = {}
    for folder in _faulty_rigs_search_folders():
        try:
            entries = list(folder.iterdir())
        except OSError:
            continue
        for f in entries:
            if f.suffix.lower() != ".dmx":
                continue
            stem = f.stem.lower()
            if not stem.endswith("_reference"):
                continue
            out.setdefault(stem[:-len("_reference")], f)
    return out


def _name_candidates(name: str):
    """
    Progressively more forgiving forms of an armature name.

    SFM names an animation set after the model plus an INSTANCE NUMBER -
    'scout' becomes 'scout1', a second one 'scout2'. Blender then adds its
    own '.001' when a name collides. Neither belongs in a reference lookup,
    and looking for 'scout1_reference.dmx' is why the rig fixer used to
    report "No reference file" for every single rig in a real session.
    """
    seen, out = set(), []

    def add(v):
        v = (v or "").strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)

    add(name)
    add(_ARM_DATA_RE.sub("", name).strip())
    for base in list(out):
        add(re.sub(r"\.\d+$", "", base))            # Blender's .001
    for base in list(out):
        add(re.sub(r"\d+$", "", base))               # SFM's instance number
    for base in list(out):
        add(base.rstrip("_- ."))
    return out


def resolve_reference(name: str):
    """
    The reference DMX for an armature, or None.

    Exact match on any candidate form first. Only then fall back to the
    LONGEST reference stem that prefixes a candidate, so 'scout_toga' is
    never satisfied by 'scout' while a genuine 'scoutXYZ' still resolves.
    """
    refs = _reference_stems()
    if not refs:
        return None, []
    cands = _name_candidates(name)

    for c in cands:
        hit = refs.get(c.lower())
        if hit is not None:
            return hit, cands

    best, best_len = None, 0
    for c in cands:
        cl = c.lower()
        for stem, path in refs.items():
            if cl.startswith(stem) and len(stem) > best_len:
                best, best_len = path, len(stem)
    return best, cands


def _find_reference_dmx(base_name: str) -> Path | None:
    """Reference DMX for *base_name*, tolerant of SFM and Blender suffixes."""
    hit, cands = resolve_reference(base_name)
    if hit is not None:
        print(f"[RIG_FIXER]  '{base_name}' -> {hit.name}")
        return hit
    known = sorted(_reference_stems())
    print(f"[RIG_FIXER]  no reference for '{base_name}' "
          f"(tried {cands}); have: {known}")
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


def _detach_action(armature, action=None) -> int:
    """
    Take the reference animation back off the rig, and delete it.

    Detaching alone used to leave the imported reference action sitting in
    the file - and with it, a rig that still looked animated. The action
    datablock is removed outright, plus any other action left behind by the
    reference import, so a fixed rig is a CLEAN rig.

    Returns how many action datablocks were removed.
    """
    ad = armature.animation_data
    removed = 0
    if ad is not None:
        ad.action = None
        for track in list(ad.nla_tracks):
            ad.nla_tracks.remove(track)
    if action is not None:
        try:
            if action.users == 0 or action.use_fake_user:
                action.use_fake_user = False
            bpy.data.actions.remove(action)
            removed += 1
        except Exception as exc:
            print(f"[RIG_FIXER]  could not remove '{action.name}': {exc}")
    return removed


def _purge_orphan_actions(before_names) -> int:
    """Delete every action the reference import created and nobody kept."""
    removed = 0
    for act in list(bpy.data.actions):
        if act.name in before_names:
            continue
        if act.users:
            continue
        try:
            bpy.data.actions.remove(act)
            removed += 1
        except Exception:
            pass
    return removed


def _span(points) -> float:
    """Bounding-box diagonal of a set of points - a scale-free size measure."""
    pts = list(points)
    if len(pts) < 2:
        return 0.0
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return math.sqrt(sum((hi[i] - lo[i]) ** 2 for i in range(3)))


def pose_scale_ratio(armature) -> float:
    """
    How much bigger the CURRENT POSE is than the rig's own rest pose.

    A reference DMX is authored in Source units. A model imported at
    SourceIO's default 0.01905 scale is in metres - about 52x smaller. Drop
    that reference pose onto that rig and every bone is flung ~50x too far,
    which does not read as "wrong scale", it reads as the model exploding.

    Comparing bounding-box diagonals catches it without needing to know
    either unit. ~1.0 means the two agree.
    """
    rest = _span(b.head_local for b in armature.data.bones)
    posed = _span(pb.matrix.translation for pb in armature.pose.bones)
    if posed <= 1e-9 or rest <= 1e-9:
        return 1.0
    return posed / rest



#  A vertex pair three times further apart than the model was built with is
#  not a pose, it is a tear. Deliberately generous: a genuine bind-vs-rest
#  difference is a few percent, and the measured bad case is 138x.
SKIN_TEAR_RATIO = 3.0
#  One stray edge is a weight painted onto the wrong bone by the model's
#  author and is not our business. Hundreds is the skin coming off.
SKIN_TEAR_EDGES = 50


def _deforming_meshes(armature):
    out = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for m in obj.modifiers:
            if m.type == "ARMATURE" and m.object == armature:
                out.append(obj)
                break
    return out


def skin_stretch(armature):
    """
    How badly the CURRENT pose stretches the skin. (worst, bad_edges, edges).

    worst is the largest edge-length ratio against the rest mesh; 1.0 is
    undeformed. Never raises - a rig with no mesh, or a Blender that will not
    evaluate one, reports (1.0, 0, 0) and lets the caller carry on, because
    refusing a rig fix on the strength of a failed measurement would be worse
    than not measuring.
    """
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
    except Exception:
        return 1.0, 0, 0

    worst, bad, total = 1.0, 0, 0
    for obj in _deforming_meshes(armature):
        try:
            rest = [v.co.copy() for v in obj.data.vertices]
            ev = obj.evaluated_get(dg)
            me = ev.to_mesh()
            posed = [v.co.copy() for v in me.vertices]
            edges = [(e.vertices[0], e.vertices[1]) for e in me.edges]
            ev.to_mesh_clear()
        except Exception:
            continue
        if len(posed) != len(rest):
            #  A modifier that changes the vertex count sits between us and
            #  the armature; there is nothing to compare edge-wise.
            continue
        for i, j in edges:
            r = (rest[i] - rest[j]).length
            if r < 1e-6:
                continue
            total += 1
            ratio = (posed[i] - posed[j]).length / r
            if ratio > worst:
                worst = ratio
            if ratio > SKIN_TEAR_RATIO:
                bad += 1
    return worst, bad, total


def _apply_pose_as_rest(armature, bake_meshes=False) -> int:
    """
    Make the current pose the rest pose.

    NO MESH BAKING. It is tempting: `pose.armature_apply()` rewrites the rest
    matrices and does not touch mesh data, so in principle the mesh should be
    moved with the bones first. Tried it - baking the armature deformation
    into the meshes (and into every shape key) before applying - and it made
    the model WORSE, pulling the limbs off at the joints.

    The reason is that a reference DMX is a REST POSE, not an arbitrary pose.
    It is within a few percent of the bind pose the mesh was skinned to, so
    `armature_apply` alone lands the skeleton where the mesh already expects
    it. Baking adds a deformation that was never missing, and the second copy
    is what tears the mesh apart.

    What actually shredded the model was SCALE - see pose_scale_ratio(). A rig
    imported at SourceIO's 0.01905 metres default against a reference authored
    in Source units is off by ~52x, and no amount of re-binding fixes that.

    *bake_meshes* is kept as an argument so the choice is visible rather than
    implicit, but it does nothing; leave it False.
    """
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    return 0


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


def _rest_snapshot(armature) -> dict:
    """Every bone's rest matrix, so a fix can be measured instead of assumed."""
    return {b.name: b.matrix_local.copy() for b in armature.data.bones}


def _rest_delta(before: dict, after: dict) -> tuple:
    """
    How far the rest pose actually moved: (max_move, max_rotation_degrees).

    BOTH numbers matter, and the ROTATION one is why this function exists.
    Re-rolling bones is the transposer's entire job: on a real TF2 rig it
    turns them by up to 240 degrees while moving the heads about 0.03 units.
    Measure translation alone and the answer reads "nothing happened", which
    is the opposite of the truth - that misreading cost a long detour once
    already. Never judge this fix by bone positions.
    """
    move = rot = 0.0
    for name, m0 in before.items():
        m1 = after.get(name)
        if m1 is None:
            continue
        move = max(move, (m0.translation - m1.translation).length)
        try:
            ang = m0.to_quaternion().rotation_difference(
                m1.to_quaternion()).angle
        except Exception:
            ang = 0.0
        rot = max(rot, math.degrees(ang))
    return move, rot


#  A deforming bone whose AXIS turns this far while its head stays put is
#  being re-framed, not repositioned. Every TF2 reference measures exactly
#  90 deg on hip/knee/upperArm/lowerArm both sides with heads within 0.03u.
REFRAME_SWING_DEG = 30.0
REFRAME_STILL_UNITS = 0.5


def _reframe_signature(armature) -> dict:
    """
    What the CURRENT pose would do to the rest pose if it were applied,
    per deforming bone: {"reframed": [names], "moved": [names],
    "worst_swing": deg}. Needs the depsgraph current (view_layer.update()).

    "reframed" = the bone's Y axis swings past REFRAME_SWING_DEG while its
    head moves less than REFRAME_STILL_UNITS. A rest-pose CORRECTION moves
    joints; a reference that only turns limb axes 90 deg is carrying SFM's
    per-joint EXPORT frame, which is right for animations exported from SFM
    and wrong for channels read out of a session - see the note in
    _process_armature_rig_fix, 2026-09-19.
    """
    deforming = set()
    for obj in _deforming_meshes(armature):
        for vg in obj.vertex_groups:
            deforming.add(vg.name)
    y_axis = Vector((0.0, 1.0, 0.0))
    reframed, moved, worst = [], [], 0.0
    for bone in armature.data.bones:
        if bone.name not in deforming:
            continue
        pb = armature.pose.bones.get(bone.name)
        if pb is None:
            continue
        rest, posed = bone.matrix_local, pb.matrix
        y0 = (rest.to_3x3() @ y_axis).normalized()
        y1 = (posed.to_3x3() @ y_axis).normalized()
        try:
            swing = math.degrees(y0.angle(y1))
        except ValueError:
            swing = 0.0
        move = (posed.translation - rest.translation).length
        worst = max(worst, swing)
        if move >= REFRAME_STILL_UNITS:
            moved.append(bone.name)
        elif swing >= REFRAME_SWING_DEG:
            reframed.append(bone.name)
    return {"reframed": reframed, "moved": moved, "worst_swing": worst}



SESSION_TAG = b"HoovyTools session extract"
MODEL_REST = "ht_rest_model"
REF_REST = "ht_rest_reference"


def is_session_extract(path) -> bool:
    """Session_Reader.extract_set stamps tags.app = 'HoovyTools session extract' - an SFM export never has it."""
    try:
        with open(str(path), "rb") as fh:
            return SESSION_TAG in fh.read()
    except OSError:
        return False


def has_two_rests(armature) -> bool:
    d = getattr(armature, "data", None)
    return d is not None and MODEL_REST in d and REF_REST in d


def _rest_read(armature) -> dict:
    """{bone: [head xyz, tail xyz, roll]} of the rest, armature space - no edit mode needed"""
    out = {}
    for b in armature.data.bones:
        roll = bpy.types.Bone.AxisRollFromMatrix(b.matrix_local.to_3x3())[1]
        out[b.name] = list(b.head_local) + list(b.tail_local) + [float(roll)]
    return out


def _parents_first(armature):
    out, seen = [], set()

    def walk(b):
        out.append(b.name)
        for c in b.children:
            walk(c)
    for b in armature.data.bones:
        if b.parent is None:
            walk(b)
    return out


def _set_rest(armature, rest: dict):
    """Put a stored rest back on (edit mode, parents first, then OBJECT mode again)."""
    view = bpy.context.view_layer
    keep_active = view.objects.active
    keep_sel = [o for o in bpy.context.selected_objects]
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for o in view.objects:
        o.select_set(False)
    armature.select_set(True)
    view.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    eb = armature.data.edit_bones
    for name in _parents_first(armature):
        r = rest.get(name)
        e = eb.get(name)
        if r is None or e is None:
            continue
        e.head = r[0:3]
        e.tail = r[3:6]
        e.roll = r[6]
    bpy.ops.object.mode_set(mode="OBJECT")
    view.update()
    for o in view.objects:
        if o is not None:
            o.select_set(o in keep_sel)
    if keep_active is not None:
        view.objects.active = keep_active


def _capture_pose(armature, frames) -> dict:
    """every bone's pose matrix (armature space) on every frame, and the rest it is on"""
    sc = bpy.context.scene
    keep = sc.frame_current
    out = {"frames": list(frames), "M": {},
           "R": {b.name: b.matrix_local.copy() for b in armature.data.bones}}
    for f in out["frames"]:
        sc.frame_set(f)
        out["M"][f] = {pb.name: pb.matrix.copy() for pb in armature.pose.bones}
    sc.frame_set(keep)
    return out


def _action_frames(action):
    lo, hi = action.frame_range
    return range(int(math.floor(lo)), int(math.ceil(hi)) + 1)


def _rekey_keep_skin(armature, action, cap) -> int:
    """The rest changed under `cap`: re-key `action` so every bone deforms the mesh exactly as it did - its pose
    becomes (old pose x old rest^-1) x new rest. Returns how many bones were re-keyed (0 = the rest had not moved)."""
    from ..core import anim_compat as AC
    from mathutils import Quaternion
    R_new = {b.name: b.matrix_local.copy() for b in armature.data.bones}
    R_old = cap["R"]

    def moved(a, b):
        return max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4))
    changed = {n for n in R_new if n in R_old and moved(R_new[n], R_old[n]) > 1e-6}
    if not changed:
        return 0
    keyed = set()
    for fc in AC.iter_fcurves(action):
        if fc.data_path.startswith('pose.bones["'):
            keyed.add(fc.data_path.split('"')[1])
    todo = (changed | keyed) & set(R_new)
    order = _parents_first(armature)
    bag = AC.get_channelbag(action, armature)
    props = (".location", ".rotation_quaternion", ".rotation_euler", ".rotation_axis_angle", ".scale")
    for fc in list(bag.fcurves):
        dp = fc.data_path
        if dp.startswith('pose.bones["') and dp.split('"')[1] in todo and dp.endswith(props):
            bag.fcurves.remove(fc)
    rows = {n: ([], [], []) for n in todo}
    last_q = {}
    for f in cap["frames"]:
        M = cap["M"][f]
        new = {}
        for n in order:
            if n not in M:
                continue
            Mn = M[n] @ R_old[n].inverted() @ R_new[n]
            new[n] = Mn
            if n not in todo:
                continue
            p = armature.data.bones[n].parent
            if p is None or p.name not in new:
                basis = R_new[n].inverted() @ Mn
            else:
                basis = (R_new[p.name].inverted() @ R_new[n]).inverted() @ new[p.name].inverted() @ Mn
            loc, rot, scl = basis.decompose()
            q = Quaternion(rot)
            if n in last_q and last_q[n].dot(q) < 0:
                q.negate()
            last_q[n] = q
            rows[n][0].append((f, loc))
            rows[n][1].append((f, q))
            rows[n][2].append((f, scl))
    for n, (locs, rots, scls) in rows.items():
        armature.pose.bones[n].rotation_mode = "QUATERNION"
        for prop, series, width in (("location", locs, 3), ("rotation_quaternion", rots, 4), ("scale", scls, 3)):
            for i in range(width):
                fc = AC.fc_find_or_new(bag, 'pose.bones["%s"].%s' % (n, prop), i, group_name=n)
                fc.keyframe_points.clear()
                fc.keyframe_points.add(len(series))
                co = []
                for f, v in series:
                    co += [float(f), float(v[i])]
                fc.keyframe_points.foreach_set("co", co)
                for k in fc.keyframe_points:
                    k.interpolation = "LINEAR"
                fc.update()
    return len(todo)


def import_on_model_basis(armature, do_import, log=print):
    """A SESSION extract onto a rig Fix All has fixed: the model's rest under it while it lands (the clean scout),
    then the reference rest back on with every frame re-keyed - the same mesh, Fix All's rest. Returns the bones."""
    model = json.loads(armature.data[MODEL_REST])
    ref = json.loads(armature.data[REF_REST])
    _set_rest(armature, model)
    try:
        do_import()
    finally:
        act = armature.animation_data.action if armature.animation_data else None
        if act is None:
            _set_rest(armature, ref)
    cap = _capture_pose(armature, _action_frames(act))
    _set_rest(armature, ref)
    n = _rekey_keep_skin(armature, act, cap)
    log(f"[RIG_FIXER]  '{armature.name}': session animation laid on through the model rest, "
        f"{n} bone(s) re-keyed onto Fix All's rest ({len(cap['frames'])} frames)")
    return n


def _process_armature_rig_fix(armature, allow_reframe=True,
                               reference=None) -> dict:
    result = {"name": armature.name, "base": "", "status": "",
              "marked_col": "", "cleared": 0,
              "moved": 0.0, "rotated": 0.0, "had_action": False,
              "baked": 0, "scale_ratio": 1.0,
              "skin_stretch": 1.0, "skin_bad_edges": 0}
    # Match on the OBJECT name too. Session imports name the object after
    # the animation set while the armature DATA can keep the model name, or
    # the other way round - whichever resolves is the right answer.
    base_name = _extract_base_name(armature.data.name)
    if resolve_reference(base_name)[0] is None:
        alt = _extract_base_name(armature.name)
        if resolve_reference(alt)[0] is not None:
            base_name = alt
    result["base"]  = base_name
    #  1.18.0: a reference CHOSEN by hand (Fix Rig From Reference DMX) goes
    #  through exactly this procedure - two rests stored, the existing
    #  animation kept and re-keyed - instead of the older path that button
    #  used to have of its own.
    ref_dmx         = (Path(reference) if reference
                       else _find_reference_dmx(base_name))

    if ref_dmx is None:
        result["status"] = "— No reference file"
        return result

    print(f"[RIG_FIXER]  fixing '{armature.name}'  ref: '{ref_dmx.name}'")
    before = {a.name for a in bpy.data.actions}

    # An action already on the rig is about to be invalidated: pose data is
    # stored relative to the rest pose, so replacing the rest pose silently
    # bends every existing keyframe. Blender warns about this on the console
    # and nowhere the user looks - so record it and put it in the report.
    result["had_action"] = bool(armature.animation_data
                                and armature.animation_data.action)

    rest_before = _rest_snapshot(armature)
    #  1.17.2: an animation already on the rig is KEPT - captured here, re-keyed onto the new rest below (it used to
    #  be taken off with the reference and lost). And the model's rest is remembered the first time, for session
    #  extracts (import_on_model_basis).
    ad0 = armature.animation_data
    own_action = ad0.action if ad0 is not None else None
    own_slot = ad0.action_slot if ad0 is not None and own_action is not None else None
    own_pose = _capture_pose(armature, _action_frames(own_action)) if own_action is not None else None
    if own_action is not None:
        own_action.use_fake_user = True                 # it is off the rig while the reference poses it
    if MODEL_REST not in armature.data:
        armature.data[MODEL_REST] = json.dumps(_rest_read(armature))
    action = None
    try:
        action = _import_reference_dmx(ref_dmx, armature)
        if action is None:
            result["status"] = "✗  Import OK but no action created"
            return result

        # REFUSE A SCALE MISMATCH RATHER THAN SHREDDING THE MODEL.
        # The reference is in Source units; a model imported at SourceIO's
        # 0.01905 default is in metres. Applying one to the other flings every
        # bone ~52x too far and the mesh comes apart. That looked like "the rig
        # fixer is broken" when the rig fixer was doing exactly as told.
        bpy.context.view_layer.update()
        ratio = pose_scale_ratio(armature)
        result["scale_ratio"] = ratio
        if not (0.5 < ratio < 2.0):
            _detach_action(armature, action)
            _purge_orphan_actions(before)
            result["status"] = f"✗  Scale mismatch x{ratio:.1f} - not applied"
            print(f"[RIG_FIXER]  '{armature.name}': reference pose is "
                  f"{ratio:.2f}x the rig's own size. Re-import the model at "
                  f"World Scale 1.0 (Source units); SourceIO's 0.01905 "
                  f"default is metres and does not match the reference DMX.")
            return result
        sig = _reframe_signature(armature)
        result["reframed"] = len(sig["reframed"])
        result["joints_moved"] = len(sig["moved"])
        if not allow_reframe and sig["reframed"]:
            _detach_action(armature, action)
            _purge_orphan_actions(before)
            names = ", ".join(sig["reframed"][:8])
            result["status"] = (f"○  Kept SourceIO rest - reference re-frames "
                                f"{len(sig['reframed'])} limb axes (SFM export "
                                f"frames; session channels are model-basis)")
            print(f"[RIG_FIXER]  '{armature.name}': reference turns the axis "
                  f"of {len(sig['reframed'])} deforming bone(s) by up to "
                  f"{sig['worst_swing']:.0f} deg with the heads still "
                  f"({names}). That is SFM's export frame, not a rest-pose "
                  f"correction; a session's channels are in the model's own "
                  f"basis, so SourceIO's rest is kept. Use this reference "
                  f"with Import DMX Animation on files EXPORTED from SFM.")
            return result
        stretch, bad, edges = skin_stretch(armature)
        result["skin_stretch_before"] = stretch
        result["skin_bad_edges"] = bad
        if bad > SKIN_TEAR_EDGES and stretch > SKIN_TEAR_RATIO:
            print(f"[RIG_FIXER]  '{armature.name}': the reference differs "
                  f"from the current rest by enough to stretch {bad} of "
                  f"{edges} edges (worst x{stretch:.1f}). That IS the "
                  f"mismatch being corrected, not a reason to stop.")

        # Rest pose FIRST, while the reference action is still driving the
        # pose - that pose is the whole point. Only then take it away.
        _apply_pose_as_rest(armature)
        gone = _detach_action(armature, action)
        gone += _purge_orphan_actions(before)
        result["cleared"] = gone
        result["marked_col"] = _mark_collection_yellow(armature)
        armature.data[REF_REST] = json.dumps(_rest_read(armature))

        # THE POST-CONDITION, which is the one that can actually fail.
        # With the action detached and the rest replaced, the rig is in its
        # own rest pose and the mesh should be undeformed: stretch ~1.0.
        # Anything else means the reference really did not belong to this
        # model, and now it is observed rather than predicted.
        after, bad_after, _ = skin_stretch(armature)
        result["skin_stretch"] = after
        result["skin_stretch_after"] = after

        move, rot = _rest_delta(rest_before, _rest_snapshot(armature))
        result["moved"], result["rotated"] = move, rot
        # Say what CHANGED, not just that something ran. A bare tick next to a
        # rig that looks wrong is unfalsifiable; a number is not.
        if move < 1e-4 and rot < 0.5:
            result["status"] = "=  Already matched (no change)"
        else:
            result["status"] = f"✓  Applied  {rot:.0f}° / {move:.2f}u"
        #  LAST WORD TO THE POST-CONDITION. Written after the tick above, so
        #  a rig that still tears cannot report a clean tick - which is the
        #  unfalsifiable thing the line above warns about.
        if bad_after > SKIN_TEAR_EDGES and after > SKIN_TEAR_RATIO:
            result["status"] = f"⚠  Applied, skin still x{after:.0f}"
            print(f"[RIG_FIXER]  '{armature.name}': WARNING - with the rest "
                  f"replaced the mesh is STILL stretched x{after:.1f} across "
                  f"{bad_after} edge(s). This reference does not belong to "
                  f"this model. Ctrl+Z and check which .dmx was used.")
        print(f"[RIG_FIXER]  '{armature.name}' rest moved {move:.3f}u, "
              f"rotated {rot:.1f} deg, skin x{stretch:.1f} -> x{after:.1f}")
        if gone:
            print(f"[RIG_FIXER]  removed {gone} leftover action(s)")
    except Exception as exc:
        print(f"[RIG_FIXER]  ERROR on '{armature.name}': {exc}")
        result["status"] = f"✗  {exc}"
        #  Never leave the reference posing the rig: the animation step
        #  would key on top of it.
        if action is not None:
            try:
                _detach_action(armature, action)
                _purge_orphan_actions(before)
            except Exception:
                pass
    finally:
        _give_back(armature, own_action, own_slot, own_pose, result)

    return result


def _give_back(armature, own_action, own_slot, own_pose, result):
    """1.17.2: the rig's own animation goes back on - re-keyed so the mesh moves exactly as before when the rest
    changed under it. Every exit of the fixer comes through here (refusals and errors too)."""
    if own_action is None or own_action.name not in bpy.data.actions:
        return
    ad = armature.animation_data_create()
    if ad.action is not own_action:
        ad.action = own_action
        if own_slot is not None:
            try:
                tgt = next((s for s in own_action.slots if s.identifier == own_slot.identifier), None)
                if tgt is not None:
                    ad.action_slot = tgt
            except Exception:
                pass
    if own_pose is not None:
        try:
            n = _rekey_keep_skin(armature, own_action, own_pose)
            result["kept_animation"] = n
            if n:
                print(f"[RIG_FIXER]  '{armature.name}': its animation '{own_action.name}' kept - {n} bone(s) "
                      f"re-keyed onto the new rest, the mesh moves as before")
        except Exception as exc:
            print(f"[RIG_FIXER]  '{armature.name}': could not re-key its animation: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
#  RIG FIXER — PUBLIC
# ──────────────────────────────────────────────────────────────────────────────

@Progress.jobbed("HoovyTools - Fix Rig Rest Poses")
def reference_choices(armature=None):
    """[(path, label)] - every .dmx in the Faulty Rigs folders, the best match
    for *armature* first (the one Fix All would pick for it)."""
    best = None
    if armature is not None:
        for nm in (_extract_base_name(armature.data.name),
                   _extract_base_name(armature.name)):
            best = resolve_reference(nm)[0]
            if best is not None:
                break
    seen, out = set(), []
    for folder in _faulty_rigs_search_folders():
        try:
            files = sorted(f for f in folder.iterdir()
                           if f.suffix.lower() == ".dmx")
        except OSError:
            continue
        for f in files:
            key = str(f).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append((f, f.stem))
    if best is not None:
        out.sort(key=lambda pl: 0 if pl[0] == best else 1)
    return out


def fix_one_rig(armature, reference=None) -> dict:
    """Fix All Rig Rest Poses, for ONE armature - with *reference* when given,
    otherwise the reference Fix All would find by name."""
    if not hasattr(bpy.ops.ht, "import_smd"):
        raise RuntimeError(
            "No SMD/DMX importer available. The bundled SST failed to "
            "register - re-enable HoovyTools.")
    r = _process_armature_rig_fix(armature, True, reference)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    return r


def run_rig_fixer(allow_reframe=True) -> dict:
    """
    Scan every armature in the scene and apply rest pose fixes.

    *allow_reframe* False is the SESSION pipeline: a reference that would
    only turn limb axes (SFM's export frame) is not applied and the rig
    keeps SourceIO's rest, which is the basis session channels are in.
    True is the manual flow for animations EXPORTED from SFM.

    Returns:
    {
        "fixed":   int,
        "skipped": int,   no reference file
        "kept":    int,   reference refused as an export frame (session mode)
        "errors":  int,
        "results": list[dict],
    }
    """
    # The bundled SST registers the importer as ht.import_smd; a separately
    # installed Blender Source Tools registers import_scene.smd. Either is
    # fine - _import_reference_dmx uses ht.import_smd, which SST guarantees.
    if not hasattr(bpy.ops.ht, "import_smd"):
        raise RuntimeError(
            "No SMD/DMX importer available. The bundled SST failed to "
            "register - re-enable HoovyTools.")

    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        return {"fixed": 0, "skipped": 0, "errors": 0, "results": []}

    results = []
    for a_idx, arm in enumerate(armatures, 1):
        Progress.update(a_idx, len(armatures), f"rest pose  {arm.name}")
        results.append(_process_armature_rig_fix(arm, allow_reframe))

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    fixed   = sum(1 for r in results if r["status"].startswith("✓"))
    skipped = sum(1 for r in results if r["status"].startswith("—"))
    kept    = sum(1 for r in results if r["status"].startswith("○"))
    errors  = sum(1 for r in results if r["status"].startswith("✗"))

    cleared = sum(r.get("cleared", 0) for r in results)
    print(f"[RIG_FIXER]  done — fixed:{fixed}  kept:{kept}  skipped:{skipped}  "
          f"errors:{errors}  leftover actions removed:{cleared}")
    return {"fixed": fixed, "skipped": skipped, "kept": kept, "errors": errors,
            "cleared": cleared, "results": results}


# ──────────────────────────────────────────────────────────────────────────────
#  OPERATORS
# ──────────────────────────────────────────────────────────────────────────────

class HT_OT_ImportSession(Operator):
    """PICK .dmx (session) - the file SFM saved, usually under
        usermod\\elements\\sessions

        Import every model an SFM session references

Reads the session, resolves each animation set's .mdl against the SFM
search paths, and imports it through SourceIO. A model already in the
scene is skipped, so running this twice does not double it.
Blender stays responsive and a huge session cannot hang the UI in one
call. Press it again to continue - it reports how many are left.

Armatures are renamed to the session's animation set name (scout1, not
scout_ARM) because that is what every later step matches against.

STATIC PROPS get a bone built for them. A model compiled with $staticprop
has exactly one bone and SourceIO imports it as meshes only, so its
animation would have nothing to land on. A one-bone rig is created and
the meshes weighted to it - a static prop is rigid, so full weight is
exact, not an approximation.
    """
    #  BELOW THE TOOLTIP CAP. Blender truncates an operator description
    #  at 1023 characters, without a warning, mid-word. These paragraphs
    #  were part of the docstring and were already being cut off before
    #  anyone could read them, so they live here instead - kept, but out
    #  of the tooltip's budget.
    #  Missing models are counted and named. They usually mean the .mdl is not
    #  under the configured usermod path
    #

    bl_idname  = "ht.import_session"
    bl_label   = "SFM Session"
    #  NO "REGISTER" - see the note in Report_UI/the constitution.
    #  REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    #  touching any field in it RE-RUNS this operator. Re-running an
    #  import re-reads the DMX and rebuilds every f-curve; nudging Scale
    #  there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    #  with the value you wanted is the safe way to change your mind.
    bl_options = {"UNDO"}

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
            # Show a proper popup so the error is impossible to miss.
            # NEVER index into this blind: an exception with an empty message
            # is exactly what used to turn a failed import into an
            # IndexError inside the handler.
            err_lines = [l for l in str(exc).splitlines() if l.strip()]
            if not err_lines:
                err_lines = [f"{type(exc).__name__} with no message "
                             f"(see the system console)"]
            from ..core import Report_UI
            Report_UI.report(context, "session_models",
                             "Session Import Failed", err_lines,
                             level='ERROR', prefix="SESSION",
                             operator=self,
                             summary=f"Session import FAILED - {err_lines[0]}")
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
        from ..core import Report_UI
        Report_UI.report(context, "session_models", "SFM Session Import",
                         lines, icon=icon, prefix="SESSION", operator=self,
                         level=('WARNING' if result["missing"] else 'INFO'),
                         summary=result["message"])
        return {"FINISHED"}


class HT_OT_RigFixer(Operator):
    """Give every rig in the scene the rest pose SFM animated it in

SourceIO builds a rig from the .mdl with bone rolls that do not match the
rig SFM used. The reference DMX supplies the rest pose SFM expects; the
mesh and its weight groups stay SourceIO's.

JUDGE THIS BY ROTATION, NOT BY POSITION. On a real TF2 rig it re-rolls
bones by up to 240 degrees while moving bone heads about 0.03 units.
Measuring translation alone reads as "nothing happened" and is the
opposite of the truth - so the report gives both numbers.

ORDER MATTERS. Pose is stored relative to the rest pose, so fixing a rest
pose AFTER animation is on the rig bends every existing key. Run this
before importing animation; it warns when it finds a rig that already has
an action.

Idempotent - a second and third run change nothing.

Reference files live in _Faulty Rigs as <model>_reference.dmx. SFM's
instance numbers are stripped when matching, so scout1 finds scout"""
    bl_idname  = "ht.rig_fixer"
    bl_label   = "Fix Rig Rest Poses"
    #  NO "REGISTER" - see the note in Report_UI/the constitution.
    #  REGISTER makes Blender draw the "Adjust Last Operation" panel, and
    #  touching any field in it RE-RUNS this operator. Re-running an
    #  import re-reads the DMX and rebuilds every f-curve; nudging Scale
    #  there froze and then killed Blender. Undo (Ctrl+Z) plus a fresh run
    #  with the value you wanted is the safe way to change your mind.
    bl_options = {"UNDO"}

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
        from ..core import Report_UI
        Report_UI.report(context, "rig_fixer", "Rig Fixer", lines, icon=icon,
                         prefix="RIG_FIXER", operator=self,
                         level=('ERROR' if result["errors"] else 'INFO'),
                         summary=f"Rig Fixer - {result['fixed']} fixed, "
                                 f"{result['skipped']} without a reference")
        return {"FINISHED"}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU ITEMS  (called directly from HT_MT_import_submenu.draw in __init__.py)
# ──────────────────────────────────────────────────────────────────────────────

def draw_submenu(layout):
    """
    Draw the three numbered IMPORT SESSION entries.
    Called from HT_MT_session_submenu.draw() in __init__.py.
    """
    layout.operator(
        HT_OT_ImportSession.bl_idname,
        text="1  Import DMX Session Models",
        **_icon_id("import_session_models", "SCENE_DATA"),
    )


def draw_menu_item(layout):
    """
    Top-level menu entry for HT_MT_import_submenu in __init__.py.
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
