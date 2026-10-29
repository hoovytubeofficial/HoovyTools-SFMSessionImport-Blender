"""
core/config.py  -  where each KIND of asset lives, as two JSON files

TWO FILES, AND WHICH ONE IS WHOSE IS THE WHOLE DESIGN
-----------------------------------------------------
    _config/_startupconfig.json     OURS.   Rewritten on every launch.
    _config/customizedconfig.json   YOURS.  Never touched by the add-on.

`_startupconfig.json` is generated from whatever usermod path is configured
when the add-on registers. It is the FALLBACK and it is disposable - delete it
and it comes back next time Blender starts, which is exactly why nothing you
type should ever go in it. It exists so that "where does this add-on look for
animations?" has an answer you can open and read rather than one you have to
find in the source.

`customizedconfig.json` is yours. Same shape, and anything in it WINS. It is
not created for you: an empty file you did not ask for is one more thing to
wonder about, so there is a button that makes one seeded from the startup
config when you actually want one.

THE LADDER, WHICH IS WHAT "WIRE IT AUTOMATICALLY" MEANS
-------------------------------------------------------
Every kind of asset gets an ORDERED LIST, not one path, because the honest
answer to "where are the animations" is "here, and if not here then here":

    animations   usermod/animations  ->  usermod  ->  the built-in default
    elements     usermod/elements    ->  usermod  ->  ...
    models       usermod/models      ->  usermod  ->  ...
    particles    usermod/particles   ->  usermod  ->  ...
    sound        usermod/sound       ->  usermod  ->  ...
    materials    usermod/materials   ->  usermod  ->  ...
    maps         usermod/maps        ->  usermod  ->  ...

EVERY CONFIGURED INSTALL CONTRIBUTES, in slot order, so somebody with SFM on
C: and D: gets `C:/.../animations`, `D:/.../animations`, then the bare usermod
folders, then the built-in default. First one that EXISTS wins, and nothing
is invented: a folder that is not there is skipped, never created.

WHY NOT ONE FILE
----------------
`user_paths.json`, next to these two, holds the WIRING SLOTS - which SFM
installs and which extra reference folders. That is a different question
("which copies of SFM do I have") from this one ("where does a .pcf live"),
it is written by the panel rather than by hand, and merging them would mean
the add-on rewriting a file the user edits. Three files, one job each.

NOTHING HERE RAISES
-------------------
A missing, unreadable or hand-mangled config returns the built-in ladder. This
is read on the way into an import; a typo in a JSON file must cost you an
override, not the import.
"""

import json
import time
from pathlib import Path

from . import paths as _paths

STARTUP_NAME = "_startupconfig.json"
CUSTOM_NAME = "customizedconfig.json"
CONFIG_VERSION = 1

# kind -> the subfolder of usermod it normally lives in
# Order is the order they are written to the file, so the file reads as a
# list of what the add-on cares about rather than as a dict in hash order
KINDS = (
    ("animations", "animations", "extracted per-set .dmx animation files"),
    ("elements",   "elements",   "SFM session files"),
    ("models",     "models",     "compiled .mdl models"),
    ("particles",  "particles",  ".pcf particle definitions"),
    ("sound",      "sound",      ".wav files a session references"),
    ("materials",  "materials",  ".vmt / .vtf materials"),
    ("maps",       "maps",       "compiled .bsp maps"),
)

_KIND_SUB = {k: sub for k, sub, _d in KINDS}

_last_error = None


def config_dir() -> Path:
    """`HoovyTools/_config`, the same folder user_paths.json lives in."""
    return _paths.data_dir("config")


def startup_path() -> Path:
    return config_dir() / STARTUP_NAME


def custom_path() -> Path:
    return config_dir() / CUSTOM_NAME


# ─────────────────────────────────────────────────────────────────────────────
# building the ladder
# ─────────────────────────────────────────────────────────────────────────────

def build_ladders(usermod_bases, default_usermod=None) -> dict:
    """{kind: [path, ...]} - every place to try, best first.

    `usermod_bases` is the configured installs in slot order. The built-in
    default goes on the end whether or not it is one of them, so a user who
    has pointed everything somewhere else still falls back to the stock
    location rather than to nothing.
    """
    bases = [Path(b) for b in (usermod_bases or [])]
    if default_usermod is not None:
        d = Path(default_usermod)
        if d not in bases:
            bases.append(d)

    out = {}
    for kind, sub, _desc in KINDS:
        rungs = []
        # the specific folder in every install first...
        for b in bases:
            p = b / sub
            if p not in rungs:
                rungs.append(p)
        # ...then the bare usermod folders, bc a flat install keeps
        # everything loose and "usermod/animations" simply isn't there
        for b in bases:
            if b not in rungs:
                rungs.append(b)
        out[kind] = rungs
    return out


def _read(path):
    global _last_error
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:                                  # noqa: BLE001
        #ONCE PER DISTINCT FAULT. This is reached on the way into an import
        #and from the panel; a broken file must say so, not say so a
        #thousand times
        sig = f"{path}|{exc}"
        if sig != _last_error:
            _last_error = sig
            print(f"[HoovyTools]  {path.name} could not be read ({exc}) - "
                  f"using the built-in folders")
        return {}
    return raw if isinstance(raw, dict) else {}


def _folders_of(data):
    got = data.get("folders")
    return got if isinstance(got, dict) else {}


def custom_ladder(kind) -> list:
    """What customizedconfig.json says for one kind, in order. May be empty.

    A single string is accepted as well as a list - somebody hand-editing this
    will write one path far more often than a list of them, and refusing that
    would be pedantry with a traceback attached.
    """
    got = _folders_of(_read(custom_path())).get(kind)
    if isinstance(got, str):
        got = [got]
    if not isinstance(got, (list, tuple)):
        return []
    return [Path(v) for v in got if isinstance(v, str) and v.strip()]


def startup_ladder(kind) -> list:
    got = _folders_of(_read(startup_path())).get(kind)
    if isinstance(got, str):
        got = [got]
    if not isinstance(got, (list, tuple)):
        return []
    return [Path(v) for v in got if isinstance(v, str) and v.strip()]


def ladder(kind, live_bases=None, default_usermod=None) -> list:
    """The full ordered list for one kind: yours, then ours, then computed.

    The computed rungs go on the end even though `_startupconfig.json` already
    holds them, because that file is a snapshot of the last launch and the
    usermod preference can be changed without restarting Blender. Belt and
    braces, de-duplicated.
    """
    out, seen = [], set()

    def add(p):
        p = Path(p)
        key = str(p).rstrip("\\/").lower()
        if key not in seen:
            seen.add(key)
            out.append(p)

    for p in custom_ladder(kind):
        add(p)
    for p in startup_ladder(kind):
        add(p)
    if live_bases is not None:
        for p in build_ladders(live_bases, default_usermod).get(kind, []):
            add(p)
    return out


def folders(kind, live_bases=None, default_usermod=None) -> list:
    """Every rung of the ladder that EXISTS, in order."""
    return [p for p in ladder(kind, live_bases, default_usermod) if p.is_dir()]


def folder(kind, live_bases=None, default_usermod=None):
    """The first rung that exists, or None. Nothing is ever created."""
    got = folders(kind, live_bases, default_usermod)
    return got[0] if got else None


# ─────────────────────────────────────────────────────────────────────────────
# writing
# ─────────────────────────────────────────────────────────────────────────────

def _payload(ladders, usermod_bases, note):
    return {
        "version": CONFIG_VERSION,
        "note": note,
        "written": time.strftime("%Y-%m-%d %H:%M:%S"),
        "usermod": [str(b) for b in usermod_bases],
        "folders": {kind: [str(p) for p in ladders.get(kind, [])]
                    for kind, _sub, _d in KINDS},
        "what_each_one_is": {kind: desc for kind, _sub, desc in KINDS},
    }


def write_startup(usermod_bases, default_usermod=None):
    """Rewrite `_startupconfig.json`. Returns the path, or None if it failed.

    CALLED ON EVERY REGISTER, and it overwrites without asking - which is only
    safe because nothing the user types is ever in this file. The note at the
    top of it says so, in the file, where somebody about to edit it will be
    looking.
    """
    try:
        d = config_dir()
        d.mkdir(parents=True, exist_ok=True)
        ladders = build_ladders(usermod_bases, default_usermod)
        note = (f"GENERATED - rewritten every time the add-on loads. Do not "
                f"edit; your changes will be gone next launch. Put your own "
                f"paths in {CUSTOM_NAME} beside this file, same shape, and "
                f"they win.")
        p = d / STARTUP_NAME
        p.write_text(json.dumps(_payload(ladders, usermod_bases, note),
                                indent=2), encoding="utf-8")
        return p
    except Exception as exc:                                  # noqa: BLE001
        #an add-on folder can be read-only - installed by an admin, or on a
        #share. That is a reason to skip the file, never a reason to fail
        #registration and leave the user with no add-on at all
        print(f"[HoovyTools]  could not write {STARTUP_NAME} ({exc}) - "
              f"the built-in folders still work")
        return None


def write_custom_template(usermod_bases, default_usermod=None,
                          overwrite=False):
    """Create `customizedconfig.json`, seeded from the startup ladder.

    SEEDED, NOT EMPTY. A blank file with the right keys still means looking up
    what a key is called and what shape its value takes; a copy of the working
    answer means deleting the lines you do not care about, which is the same
    edit but backwards and impossible to get wrong.

    Refuses to overwrite an existing one unless asked - it is the only file
    here with anything of yours in it.
    """
    p = custom_path()
    if p.is_file() and not overwrite:
        return p, False
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    ladders = build_ladders(usermod_bases, default_usermod)
    note = (f"YOURS. Anything here beats {STARTUP_NAME}. Delete any line you "
            f"do not care about - a missing key just means 'use the default'. "
            f"A single path is fine where a list is shown.")
    p.write_text(json.dumps(_payload(ladders, usermod_bases, note), indent=2),
                 encoding="utf-8")
    return p, True


def fingerprint() -> tuple:
    """Cheap value that changes when either file changes."""
    out = []
    for p in (startup_path(), custom_path()):
        try:
            st = p.stat()
            out.append((st.st_mtime_ns, st.st_size))
        except OSError:
            out.append((0, 0))
    return tuple(out)
