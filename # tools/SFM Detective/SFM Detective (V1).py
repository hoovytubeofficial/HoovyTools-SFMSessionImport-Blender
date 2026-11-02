# =============================================================================
# SFM Detective (V1)
# A standalone folder finder for Source Filmmaker  (SFM Session Importer 3.0.9)
# =============================================================================
#
# WHAT IT does: finds every Source Filmmaker install on this computer - from
# the Windows registry, every Steam library Steam knows about, the usual Steam
# folders on every drive (C:, D:, E:, F: ...) and, if you ask, a deep search
# of whole drives - and checks each one: sfm.exe, dmxconvert.exe,
# usermod\gameinfo.txt, the folders SFM loads models from
#
# Give it a session (.dmx) and it also says which install the session lives
# in, every model the session uses, where each one is found (or that it's
# found NOWHERE), whether its .vvd / .vtx files are beside it, and which of
# its materials are missing. A model that isn't at its path but has the
# same file name somewhere else is pointed out - that's usually the answer.
#
# HOW (Blender): open this file in a Text Editor, set SESSION_DMX below if you
# have a session that fails, press Run Script (Alt+P). The report opens as
# the text "SFM Detective Report" and is saved as a .txt beside this script
# HOW (no Blender): python "SFM Detective (V1).py" "D:\...\my_session.dmx"
# switches: --deep  --no-names  --no-materials  --out=<folder>
#
# Needs nothing else - not the add-on, not SourceIO, not SFM running. It only
# READS: it never changes a file, a setting or the registry
#
# The report contains file paths from this computer, which include your
# Windows user name. Read it before you post it anywhere public.
#
# this feature was added in version 3.0.9 and is in experimental stage.
# =============================================================================

SESSION_DMX = r""           # a session .dmx to investigate (optional): r"D:\...\usermod\elements\x.dmx"
DEEP_SCAN = False           # also search whole drives for SFM folders (slow: up to DEEP_SECONDS)
DEEP_DEPTH = 6              # how many folders down the deep search goes
DEEP_SECONDS = 120          # the deep search stops after this long
NAME_SEARCH = True          # a missing model: look for its FILE NAME in every models folder
CHECK_MATERIALS = True      # a found model: check the .vmt files it asks for
REPORT_FOLDER = r""         # where the report goes; empty = beside this script

# -----------------------------------------------------------------------------

import json
import os
import re
import string
import struct
import sys
import tempfile
import time

VERSION = "SFM Detective (V1)"
REPORT_STEM = "SFM Detective Report"
SFM_APPID = "1840"

#Where Steam usually puts SFM, relative to a drive root. A Steam library
#Steam knows about is read from Steam itself; these catch the rest
GUESSES = (
    r"Program Files (x86)\Steam\steamapps\common\SourceFilmmaker",
    r"Program Files\Steam\steamapps\common\SourceFilmmaker",
    r"SteamLibrary\steamapps\common\SourceFilmmaker",
    r"Steam\steamapps\common\SourceFilmmaker",
    r"Games\Steam\steamapps\common\SourceFilmmaker",
    r"Games\SteamLibrary\steamapps\common\SourceFilmmaker",
    r"Steam Library\steamapps\common\SourceFilmmaker",
    r"SourceFilmmaker",
)

# never walked by the deep search - huge, and SFM is never in them
DEEP_SKIP = {"windows", "$recycle.bin", "system volume information", "programdata", "appdata",
             "node_modules", "$windows.~bt", "$windows.~ws", "windowsapps", "winsxs", ".git",
             "recovery", "msocache", "intel", "amd", "nvidia", "perflogs"}

DRIVE_TYPES = {0: "unknown", 1: "no root", 2: "removable", 3: "fixed", 4: "network", 5: "cd/dvd", 6: "ram disk"}


# ─────────────────────────────────────────────────────────────────────────────
# SMALL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def norm(p):
    """A path to compare by: absolute, case-folded, no trailing separator. No disk access."""
    return os.path.normcase(os.path.normpath(os.path.abspath(str(p))))


def isfile(p):
    try:
        return os.path.isfile(p)
    except (OSError, ValueError):
        return False


def isdir(p):
    try:
        return os.path.isdir(p)
    except (OSError, ValueError):
        return False


def listdir(p):
    try:
        return sorted(os.listdir(p))
    except (OSError, ValueError):
        return []


def drive_of(p):
    return os.path.splitdrive(str(p))[0].upper() or "?"


def say(text):
    """print() that never dies on a console that cannot show a character (cp1250 / cp1252 consoles and a
    path with Polish letters, or a garbage file's header)."""
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(enc, "replace").decode(enc, "replace"))


def read_text(p, limit=4_000_000):
    try:
        with open(p, "rb") as f:
            return f.read(limit).decode("utf-8", "replace")
    except (OSError, ValueError):
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# WHERE TO LOOK
# ─────────────────────────────────────────────────────────────────────────────

def local_drives():
    """[(letter 'D:', type name)] - every drive Windows has, network and empty CD drives marked (they are
    skipped by the scans: a disconnected network drive can hang a folder check for half a minute)."""
    out = []
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        mask = k32.GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if mask & (1 << i):
                t = k32.GetDriveTypeW(f"{letter}:\\")
                out.append((f"{letter}:", DRIVE_TYPES.get(t, str(t))))
        return out
    except Exception:                                         # noqa: BLE001 - not Windows, or no ctypes
        pass
    for letter in string.ascii_uppercase:
        if isdir(f"{letter}:\\"):
            out.append((f"{letter}:", "fixed"))
    return out


def scannable(drives):
    return [d for d, t in drives if t in ("fixed", "removable", "ram disk")]


def registry_values():
    """[(where, path)] - Steam's own install folder and SFM's uninstall entry, from the registry."""
    out = []
    try:
        import winreg
    except ImportError:
        return out
    keys = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath", "Steam (HKCU SteamPath)"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath", "Steam (HKLM InstallPath)"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath", "Steam (HKLM InstallPath)"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App " + SFM_APPID,
         "InstallLocation", "SFM uninstall entry"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Steam App " + SFM_APPID,
         "InstallLocation", "SFM uninstall entry"),
    )
    for hive, sub, name, label in keys:
        try:
            with winreg.OpenKey(hive, sub) as k:
                val, _ = winreg.QueryValueEx(k, name)
            if val:
                out.append((label, os.path.normpath(str(val))))
        except OSError:
            pass
    return out


def steam_libraries(steam_root):
    """Every library folder one Steam install lists (libraryfolders.vdf, old and new format, and the old
    config.vdf BaseInstallFolder_N lines)."""
    libs = [steam_root]
    for vdf in (os.path.join(steam_root, "steamapps", "libraryfolders.vdf"),
                os.path.join(steam_root, "config", "libraryfolders.vdf")):
        text = read_text(vdf)
        for m in re.finditer(r'"path"\s+"([^"]+)"', text):
            libs.append(m.group(1).replace("\\\\", "\\"))
        for m in re.finditer(r'^\s*"\d+"\s+"([A-Za-z]:[^"]+)"', text, re.M):     # pre-2021 format
            libs.append(m.group(1).replace("\\\\", "\\"))
    text = read_text(os.path.join(steam_root, "config", "config.vdf"))
    for m in re.finditer(r'"BaseInstallFolder_\d+"\s+"([^"]+)"', text):
        libs.append(m.group(1).replace("\\\\", "\\"))
    out, seen = [], set()
    for lib in libs:
        lib = os.path.normpath(lib)
        if norm(lib) not in seen:
            seen.add(norm(lib))
            out.append(lib)
    return out


def sfm_in_library(lib):
    """The SFM folder in one Steam library, by its app manifest (the folder name SFM was installed under)
    or the usual name. None when the library has no SFM."""
    common = os.path.join(lib, "steamapps", "common")
    acf = read_text(os.path.join(lib, "steamapps", f"appmanifest_{SFM_APPID}.acf"))
    m = re.search(r'"installdir"\s+"([^"]+)"', acf)
    for name in ([m.group(1)] if m else []) + ["SourceFilmmaker"]:
        p = os.path.join(common, name)
        if isdir(os.path.join(p, "game")):
            return p
    return None


def deep_scan(drives, depth, seconds, log):
    """Walk whole drives for a `game` folder holding usermod\\gameinfo.txt - finds renamed and copied SFM
    folders the Steam data knows nothing about. Breadth first, stops at `seconds`."""
    found = []
    deadline = time.time() + seconds
    for d in drives:
        level = [d + "\\"]
        for _ in range(depth):
            nxt = []
            for folder in level:
                if time.time() > deadline:
                    log.append(f"deep search stopped after {seconds} s (at {folder})")
                    return found
                try:
                    with os.scandir(folder) as it:
                        for e in it:
                            try:
                                if not e.is_dir(follow_symlinks=False):
                                    continue
                            except OSError:
                                continue
                            low = e.name.lower()
                            if low in DEEP_SKIP:
                                continue
                            if low == "game" and isfile(os.path.join(e.path, "usermod", "gameinfo.txt")):
                                found.append(os.path.dirname(e.path))
                                continue
                            nxt.append(e.path)
                except (OSError, ValueError):
                    continue
            level = nxt
    return found


def find_installs(deep=False, log=None):
    """{norm root: install dict} - every SFM install, with how each was found."""
    log = log if log is not None else []
    installs = {}

    def add(root, how):
        root = os.path.normpath(root)
        if not isdir(os.path.join(root, "game")):
            return
        key = norm(root)
        if key not in installs:
            installs[key] = {"root": root, "found_by": []}
        if how not in installs[key]["found_by"]:
            installs[key]["found_by"].append(how)

    drives = local_drives()
    steam_roots = []
    for label, path in registry_values():
        if label.startswith("Steam"):
            steam_roots.append(path)
        else:
            add(path, label)
    for d in scannable(drives):
        for guess in (r"Program Files (x86)\Steam", r"Program Files\Steam", r"Steam"):
            if isfile(os.path.join(d + "\\", guess, "steam.exe")):
                steam_roots.append(os.path.join(d + "\\", guess))
    unique, seen = [], set()
    for root in steam_roots:
        if norm(root) not in seen and isdir(root):
            seen.add(norm(root))
            unique.append(root)
    steam_roots = unique
    for root in steam_roots:
        for lib in steam_libraries(root):
            sfm = sfm_in_library(lib)
            if sfm:
                add(sfm, f"Steam library {lib}")
    for d in scannable(drives):
        for guess in GUESSES:
            add(os.path.join(d + "\\", guess), "usual folder")
    if deep:
        for root in deep_scan(scannable(drives), DEEP_DEPTH, DEEP_SECONDS, log):
            add(root, "deep search")
    return installs, drives, steam_roots


# ─────────────────────────────────────────────────────────────────────────────
# ONE INSTALL
# ─────────────────────────────────────────────────────────────────────────────

def gameinfo_paths(mod, game):
    """The folders a mod's gameinfo.txt SearchPaths block names, in order, that exist."""
    text = read_text(os.path.join(mod, "gameinfo.txt"))
    block = re.search(r"SearchPaths\s*\{([^}]*)\}", text, re.S | re.I)
    out = []
    if not block:
        return out
    for line in block.group(1).splitlines():
        line = line.split("//", 1)[0].strip()
        if not line:
            continue
        raw = line.split()[-1].strip('"').replace("|gameinfo_path|", mod + os.sep)
        if "|" in raw:
            continue
        p = raw if os.path.isabs(raw) else os.path.join(game, raw)
        p = os.path.normpath(p)
        if isdir(p) and norm(p) not in {norm(x) for x in out}:
            out.append(p)
    return out


def inspect_install(inst):
    root = inst["root"]
    game = os.path.join(root, "game")
    usermod = os.path.join(game, "usermod")
    bin_ = os.path.join(game, "bin")
    mods = [os.path.join(game, n) for n in listdir(game)
            if isdir(os.path.join(game, n)) and n.lower() not in ("bin", "sdktools")]
    order = [usermod] if isdir(usermod) else []
    for p in gameinfo_paths(usermod, game):
        if norm(p) not in {norm(x) for x in order}:
            order.append(p)
    for p in mods:                                  # what SFM mounts beyond gameinfo (workshop etc.), last
        if norm(p) not in {norm(x) for x in order}:
            order.append(p)
    inst.update({
        "drive": drive_of(root),
        "game": game,
        "usermod": usermod,
        "sfm_exe": isfile(os.path.join(game, "sfm.exe")),
        "dmxconvert": isfile(os.path.join(bin_, "dmxconvert.exe")),
        "studiomdl": isfile(os.path.join(bin_, "studiomdl.exe")),
        "gameinfo": isfile(os.path.join(usermod, "gameinfo.txt")),
        "mods": [os.path.basename(m) for m in mods],
        "search_order": order,
    })
    return inst


def install_of(path, installs):
    """The install a file sits inside: the longest install root that is a parent of it."""
    p = norm(path)
    best = None
    for key, inst in installs.items():
        if p.startswith(key + os.sep) and (best is None or len(key) > len(best)):
            best = key
    return installs.get(best)


def install_from_path(path):
    """An SFM root read from a file's own folders (a session inside an SFM nobody listed)."""
    cur = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.basename(cur).lower() == "game" and isfile(os.path.join(cur, "usermod", "gameinfo.txt")):
            return os.path.dirname(cur)
        up = os.path.dirname(cur)
        if up == cur:
            return None
        cur = up


# ─────────────────────────────────────────────────────────────────────────────
# the session
# ─────────────────────────────────────────────────────────────────────────────

MODEL_RX = re.compile(rb"models[\\/][^\x00\"\r\n<>|*?]{1,240}?\.mdl", re.I)
MAP_RX = re.compile(rb"maps[\\/][^\x00\"\r\n<>|*?]{1,240}?\.bsp", re.I)


def session_refs(path):
    """(header line, [model rel paths], [map rel paths]) read straight from the file's bytes - binary and
    text .dmx both keep the paths as plain text, so dmxconvert is not needed."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as exc:
        return f"(cannot read: {exc})", [], []
    head = data[:120].split(b"\n", 1)[0].decode("ascii", "replace").strip()
    head = "".join(c if 32 <= ord(c) < 127 else "?" for c in head)

    def uniq(rx):
        out, seen = [], set()
        for m in rx.finditer(data):
            rel = re.sub(r"/+", "/", m.group(0).decode("utf-8", "replace").replace("\\", "/"))
            if rel.lower() not in seen:
                seen.add(rel.lower())
                out.append(rel)
        return out
    return head, uniq(MODEL_RX), uniq(MAP_RX)


def locate(rel, inst):
    """Every folder of one install that has `rel`, in SFM's order (the first one wins)."""
    return [os.path.join(d, rel.replace("/", os.sep)) for d in inst["search_order"]
            if isfile(os.path.join(d, rel.replace("/", os.sep)))]


def mdl_companions(mdl):
    """What a .mdl needs beside it to load: the .vvd and a .vtx."""
    base = mdl[:-4]
    missing = []
    if not isfile(base + ".vvd"):
        missing.append(os.path.basename(base) + ".vvd")
    if not any(isfile(base + ext) for ext in (".dx90.vtx", ".dx80.vtx", ".sw.vtx", ".vtx")):
        missing.append(os.path.basename(base) + ".dx90.vtx")
    return missing


def mdl_materials(mdl):
    """([(texture name, [cd dirs])], problem or '') from the .mdl header - studiohdr_t v44-49:
    numtextures @204, textureindex @208, numcdtextures @212, cdtextureindex @216; 64-byte texture
    records with the name offset at +0. The header's own length (@76) must equal the file size,
    or the offsets are not trusted."""
    try:
        with open(mdl, "rb") as f:
            data = f.read()
    except OSError as exc:
        return [], f"cannot read ({exc})"
    if len(data) < 232 or data[:4] != b"IDST":
        return [], "not a Source .mdl (no IDST header)"
    version = struct.unpack_from("<i", data, 4)[0]
    if not 44 <= version <= 49:
        return [], f"MDL version {version} - only 44-49 are read"
    length = struct.unpack_from("<i", data, 76)[0]
    if length != len(data):
        return [], f"header says {length} bytes, file is {len(data)} - not trusted"
    ntex, itex, ncd, icd = struct.unpack_from("<4i", data, 204)

    def cstr(at):
        if not 0 <= at < len(data):
            return None
        end = data.find(b"\x00", at)
        return data[at:end if end >= 0 else len(data)].decode("utf-8", "replace")
    if not (0 <= ntex <= 1024 and 0 <= ncd <= 256 and 0 <= itex <= len(data) - 64 * ntex
            and 0 <= icd <= len(data) - 4 * ncd):
        return [], "texture table out of range - not trusted"
    dirs = []
    for i in range(ncd):
        s = cstr(struct.unpack_from("<i", data, icd + 4 * i)[0])
        if s is not None:
            dirs.append(s.replace("\\", "/").strip("/"))
    out = []
    for i in range(ntex):
        rec = itex + 64 * i
        name = cstr(rec + struct.unpack_from("<i", data, rec)[0])
        if name:
            out.append((name.replace("\\", "/"), dirs))
    return out, ""


def missing_materials(mdl, inst):
    """([vmt rel paths not found in the install], problem) - each texture is looked up under every cd dir."""
    textures, problem = mdl_materials(mdl)
    missing = []
    for name, dirs in textures:
        tries = [f"materials/{d}/{name}.vmt" if d else f"materials/{name}.vmt" for d in (dirs or [""])]
        if not any(locate(t, inst) for t in tries):
            missing.append(tries[0])
    return missing, problem


def name_search(rels, installs, seconds, log):
    """{rel: [full paths with the same FILE NAME]} - one walk over every models folder of every install."""
    want = {os.path.basename(r).lower(): r for r in rels}
    hits = {r: [] for r in rels}
    if not want:
        return hits
    deadline = time.time() + seconds
    roots = []
    for inst in installs.values():
        for d in inst["search_order"]:
            m = os.path.join(d, "models")
            if isdir(m) and norm(m) not in {norm(x) for x in roots}:
                roots.append(m)
    for top in roots:
        for folder, _dirs, files in os.walk(top):
            if time.time() > deadline:
                log.append(f"file-name search stopped after {seconds} s (at {folder})")
                return hits
            for f in files:
                r = want.get(f.lower())
                if r is not None:
                    hits[r].append(os.path.join(folder, f))
    return hits


# ─────────────────────────────────────────────────────────────────────────────
# BLENDER (only when this runs inside Blender)
# ─────────────────────────────────────────────────────────────────────────────

ADDON_NAMES = ("HoovyTools-SFMSessionImport-Blender-Master", "HoovyTools-SFMSessionImport-Blender-master",
               "HoovyTools-SFMSessionImport-Blender-main")


def blender_addon_paths():
    """{pref: value} of the SFM Session Importer add-on's SFM folders, read through Blender's own
    preferences (nothing of the add-on is imported). {} outside Blender or without the add-on."""
    try:
        import bpy
    except ImportError:
        return {}
    for name in ADDON_NAMES:
        a = bpy.context.preferences.addons.get(name)
        if a is not None and a.preferences is not None:
            out = {}
            for attr in ("sfm_usermod_path", "faulty_rigs_sfm_path", "dmxconvert_path"):
                v = getattr(a.preferences, attr, None)
                if v is not None:
                    out[attr] = str(v)
            return out
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# the investigation
# ─────────────────────────────────────────────────────────────────────────────

def investigate(session="", deep=False, names=True, materials=True):
    t0 = time.time()
    log = []
    installs, drives, steam_roots = find_installs(deep=deep, log=log)
    for inst in installs.values():
        inspect_install(inst)
    facts = {"tool": VERSION, "when": time.strftime("%Y-%m-%d %H:%M:%S"), "python": sys.version.split()[0],
             "drives": drives, "steam": steam_roots, "installs": list(installs.values()), "log": log}
    problems = []                                   # (level, sentence) - BREAKS / RISKY / NOTE

    if not installs:
        problems.append(("BREAKS", "no Source Filmmaker install was found on any drive"
                                   + ("" if deep else " - run again with DEEP_SCAN = True to search whole drives")))
    for inst in installs.values():
        where = inst["root"]
        if not inst["gameinfo"]:
            problems.append(("BREAKS", f"{where} has no usermod\\gameinfo.txt - SFM cannot start from it, "
                                       f"and importers cannot use it"))
        if not inst["dmxconvert"]:
            problems.append(("RISKY", f"{where} has no game\\bin\\dmxconvert.exe - sessions cannot be "
                                      f"converted with this install"))
        if not inst["sfm_exe"]:
            problems.append(("NOTE", f"{where} has no game\\sfm.exe (a copied or partial install?)"))

    sess = None
    if session:
        session = os.path.normpath(session.strip().strip('"'))
        sess = {"path": session, "exists": isfile(session)}
        if not sess["exists"]:
            problems.append(("BREAKS", f"the session file does not exist: {session}"))
        else:
            own = install_of(session, installs)
            if own is None:
                root = install_from_path(session)
                if root:
                    installs[norm(root)] = inspect_install({"root": root, "found_by": ["the session's folder"]})
                    own = installs[norm(root)]
                    facts["installs"] = list(installs.values())
            sess["install"] = own["root"] if own else None
            if own is None:
                problems.append(("NOTE", "the session is not inside any SFM install (copied out?) - its models "
                                         "are looked up in every install"))
            head, models, maps = session_refs(session)
            sess.update({"header": head, "models": [], "maps": []})
            if "dmx" not in head.lower():
                problems.append(("RISKY", f"the session does not start like a .dmx ({head[:60]!r})"))
            nowhere = []
            for rel in models:
                row = {"rel": rel, "found": {}, "companions_missing": [], "materials_missing": [],
                       "materials_problem": ""}
                for inst in installs.values():
                    hits = locate(rel, inst)
                    if hits:
                        row["found"][inst["root"]] = hits
                if not row["found"]:
                    nowhere.append(rel)
                else:
                    use = own if own and own["root"] in row["found"] else installs[norm(next(iter(row["found"])))]
                    winner = row["found"][use["root"]][0]
                    row["winner"] = winner
                    row["companions_missing"] = mdl_companions(winner)
                    if materials:
                        row["materials_missing"], row["materials_problem"] = missing_materials(winner, use)
                    if own and own["root"] not in row["found"]:
                        problems.append(("RISKY", f"{rel} is not in the session's own SFM ({own['root']}) - "
                                                  f"only in {', '.join(row['found'])}"))
                    if row["companions_missing"]:
                        gone = row["companions_missing"]
                        problems.append(("BREAKS", f"{winner} is there but {' and '.join(gone)} "
                                                   f"{'is' if len(gone) == 1 else 'are'} not beside it - "
                                                   f"the model cannot load"))
                    if row["materials_missing"]:
                        n = len(row["materials_missing"])
                        problems.append(("RISKY", f"{rel}: {n} material{'s' if n != 1 else ''} not found "
                                                  f"(pink and black in SFM): "
                                                  + ", ".join(row["materials_missing"][:4])
                                                  + (" ..." if n > 4 else "")))
                sess["models"].append(row)
            if nowhere:
                hits = name_search(nowhere, installs, 60, log) if names else {}
                for row in sess["models"]:
                    if row["rel"] in hits:
                        row["same_name_elsewhere"] = hits[row["rel"]][:10]
                for rel in nowhere:
                    alt = hits.get(rel) or []
                    problems.append(("BREAKS", f"{rel} is in no SFM install on this computer"
                                     + (f" - a file with the same name is at {alt[0]}" if alt else "")))
            for rel in maps:
                found = {i["root"]: locate(rel, i) for i in installs.values()}
                found = {k: v for k, v in found.items() if v}
                sess["maps"].append({"rel": rel, "found": found})
                if not found:
                    problems.append(("NOTE", f"the map {rel} is in no SFM install (the scene imports without it)"))
            if not models:
                problems.append(("NOTE", "no model paths were found in the session file"))
    facts["session"] = sess

    addon = blender_addon_paths()
    if addon:
        facts["addon_preferences"] = addon
        um = addon.get("sfm_usermod_path", "").strip()
        known = {norm(i["usermod"]) for i in installs.values()}
        if um and not isdir(um):
            best = next(iter(installs.values()), None)
            problems.append(("RISKY", f"the SFM Session Importer's SFM Usermod Path does not exist ({um})"
                             + (f" - your SFM is at {best['usermod']}" if best else "")))
        elif um and norm(um) not in known:
            problems.append(("NOTE", f"the SFM Session Importer's SFM Usermod Path ({um}) is not the usermod "
                                     f"of any install found"))
    order = {"BREAKS": 0, "RISKY": 1, "NOTE": 2}
    facts["problems"] = sorted(problems, key=lambda p: order[p[0]])
    facts["seconds"] = round(time.time() - t0, 2)
    return facts


# ─────────────────────────────────────────────────────────────────────────────
# the report
# ─────────────────────────────────────────────────────────────────────────────

def plain_words(f):
    inst = f["installs"]
    drives = sorted({i["drive"] for i in inst})
    if not inst:
        text = "No Source Filmmaker was found on this computer."
    else:
        text = (f"Found {len(inst)} Source Filmmaker install{'s' if len(inst) != 1 else ''} "
                f"(on {', '.join(drives)}).")
    s = f.get("session")
    if s and s.get("exists"):
        n = len(s["models"])
        nowhere = [m["rel"] for m in s["models"] if not m["found"]]
        text += f" The session uses {n} model{'s' if n != 1 else ''}"
        text += (f" and lives in {s['install']}." if s.get("install") else ".")
        if nowhere:
            text += (f" {len(nowhere)} of them {'is' if len(nowhere) == 1 else 'are'} on NO install - that is "
                     f"why an import comes out without them; whoever made the session has to send those "
                     f"models (with their materials), and they go into usermod at the same path.")
        elif n:
            text += " Every one of them is on this computer."
    serious = [p for p in f["problems"] if p[0] != "NOTE"]
    notes = len(f["problems"]) - len(serious)
    if serious:
        text += (f" {len(serious)} problem{'s' if len(serious) != 1 else ''}"
                 + (f" and {notes} note{'s' if notes != 1 else ''}" if notes else "") + " below, worst first.")
    elif inst:
        text += " Nothing wrong was found."
    return text


def wrap(text, width=96, indent="  "):
    out, line = [], indent
    for w in text.split():
        if len(line) + len(w) + 1 > width and line.strip():
            out.append(line.rstrip())
            line = indent
        line += w + " "
    if line.strip():
        out.append(line.rstrip())
    return out


def report_text(f):
    L = ["=" * 78, f"  {VERSION}  -  {f['when']}  -  Python {f['python']}  -  {f['seconds']} s", "=" * 78, "",
         "  THIS FILE CONTAINS FILE PATHS FROM THIS COMPUTER, which include your",
         "  user name. Read it before you post it anywhere public.", "",
         "-- IN PLAIN WORDS " + "-" * 60, ""]
    L += wrap(plain_words(f))
    L += ["", f"-- WHAT'S WRONG ({len(f['problems'])}) " + "-" * 56, ""]
    if not f["problems"]:
        L.append("  nothing")
    for lvl, sentence in f["problems"]:
        first = True
        for ln in wrap(sentence, indent="           "):
            L.append((f"  [{lvl}]".ljust(11) + ln.strip()) if first else ln)
            first = False
    L += ["", "-- SFM INSTALLS " + "-" * 62, ""]
    for i in f["installs"]:
        mark = lambda ok: "yes" if ok else "NO"
        L += [f"  {i['root']}",
              f"      found by       {'; '.join(i['found_by'])}",
              f"      sfm.exe {mark(i['sfm_exe'])}   dmxconvert.exe {mark(i['dmxconvert'])}   "
              f"studiomdl.exe {mark(i['studiomdl'])}   usermod\\gameinfo.txt {mark(i['gameinfo'])}",
              f"      mod folders    {', '.join(i['mods']) or '(none)'}",
              f"      models are looked up in ({len(i['search_order'])}):"]
        L += [f"        {n:>2}  {p}" for n, p in enumerate(i["search_order"], 1)]
        L.append("")
    s = f.get("session")
    if s:
        L += ["-- SESSION " + "-" * 67, "", f"  {s['path']}"]
        if s.get("exists"):
            L += [f"  {s.get('header', '')}", f"  lives in: {s.get('install') or '(no SFM install)'}", ""]
            for m in s["models"]:
                L.append(f"  {m['rel']}")
                if not m["found"]:
                    L.append("      NOT FOUND in any install")
                    for alt in m.get("same_name_elsewhere", []):
                        L.append(f"      same file name at: {alt}")
                for root, hits in m["found"].items():
                    L.append(f"      {root}: {hits[0]}" + (f"  (+{len(hits) - 1} lower)" if len(hits) > 1 else ""))
                if m["companions_missing"]:
                    L.append(f"      MISSING beside it: {', '.join(m['companions_missing'])}")
                if m["materials_problem"]:
                    L.append(f"      materials not checked: {m['materials_problem']}")
                for vmt in m["materials_missing"]:
                    L.append(f"      material missing: {vmt}")
            for mp in s["maps"]:
                L.append(f"  {mp['rel']}  -  " + (", ".join(mp["found"]) if mp["found"] else "NOT FOUND"))
        L.append("")
    if f.get("addon_preferences"):
        L += ["-- SFM SESSION IMPORTER PREFERENCES " + "-" * 42, ""]
        L += [f"  {k:<22} {v or '(blank)'}" for k, v in f["addon_preferences"].items()]
        L.append("")
    L += ["-- WHERE IT LOOKED " + "-" * 59, ""]
    L += [f"  drive {d}  {t}" for d, t in f["drives"]]
    L += [f"  Steam   {p}" for p in f["steam"]] or ["  Steam   (not found in the registry or the usual folders)"]
    L += [f"  note    {x}" for x in f["log"]]
    L += ["", "=" * 78, "  FOR THE DEVELOPER  (the same facts as JSON)", "=" * 78, "",
          json.dumps(f, indent=2, default=str), ""]
    return "\n".join(L)


def report_folder(override=""):
    """Beside this script, else the Desktop, else the temp folder - the first one that can be written."""
    here = ""
    try:
        import bpy
        for t in bpy.data.texts:
            if t.name.startswith("SFM Detective") and t.filepath:
                here = os.path.dirname(bpy.path.abspath(t.filepath))
                break
    except ImportError:
        pass
    if not here and "__file__" in globals() and os.path.isabs(__file__):
        here = os.path.dirname(__file__)
    for folder in (override, here, os.path.join(os.path.expanduser("~"), "Desktop"), tempfile.gettempdir()):
        if folder and isdir(folder) and os.access(folder, os.W_OK):
            return folder
    return tempfile.gettempdir()


def next_report_path(folder):
    top = 0
    rx = re.compile(re.escape(REPORT_STEM) + r" \(V(\d+)\)\.txt$")
    for n in listdir(folder):
        m = rx.match(n)
        if m:
            top = max(top, int(m.group(1)))
    return os.path.join(folder, f"{REPORT_STEM} (V{top + 1}).txt")


def main(argv=None):
    session, deep, names, materials, out = SESSION_DMX, DEEP_SCAN, NAME_SEARCH, CHECK_MATERIALS, REPORT_FOLDER
    for a in argv or []:
        if a in ("-h", "--help"):
            print('SFM Detective: python "SFM Detective (V1).py" [session.dmx] [--deep] [--no-names] '
                  '[--no-materials] [--out=<folder>]')
            return None
        if a == "--deep":
            deep = True
        elif a == "--no-names":
            names = False
        elif a == "--no-materials":
            materials = False
        elif a.startswith("--out="):
            out = a[6:]
        elif not a.startswith("--"):
            session = a
    facts = investigate(session, deep=deep, names=names, materials=materials)
    text = report_text(facts)
    path = next_report_path(report_folder(out))
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as exc:
        path = f"(not saved: {exc})"
    say(text.split("-- SFM INSTALLS")[0])
    say(f"[SFM Detective]  full report: {path}")
    try:
        import bpy
        t = bpy.data.texts.get("SFM Detective Report") or bpy.data.texts.new("SFM Detective Report")
        t.clear()
        t.write(text)
        for area in bpy.context.screen.areas if bpy.context.screen else ():
            if area.type == "TEXT_EDITOR":
                area.spaces.active.text = t
                break
    except Exception:                                         # noqa: BLE001 - not in Blender, or no screen
        pass
    facts["report_path"] = path
    return facts


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--" in sys.argv:                           # blender -b --python "SFM Detective (V1).py" -- <args>
        args = sys.argv[sys.argv.index("--") + 1:]
    elif "bpy" in sys.modules:
        args = []
    main(args)
