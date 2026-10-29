"""
core/user_paths.py  -  the folders the USER added, on disk as JSON

WHY THIS EXISTS AND THE PREFERENCES DO NOT COVER IT
---------------------------------------------------
An add-on preference is one value. That is the right shape for "where is SFM",
right up until somebody has SFM on C: AND on D: AND on E: - which is normal for
anyone who has ever moved a Steam library or kept an old install for one mod.
With one value the answer to "why can it not find my model" is "because it is
in the other install", and no amount of fixing the path helps: fixing it breaks
the first one.

So the searchable folders are a LIST, and the list lives here:

    usermod        3 slots   whole SFM installs, all searched
    faulty_rigs    2 slots   extra reference-DMX folders
    qc_face_data   2 slots   extra .qc folders

SLOT 1 OF EACH IS STILL THE PREFERENCE, AND THAT IS DELIBERATE. Blender already
persists preferences, already gives them a UI, and everything in the add-on
already reads them. This file holds only what the user ADDED on top - so an
install that never adds anything has no JSON at all and behaves exactly as it
did before, and the two systems can never disagree about the primary path
because only one of them stores it.

WHERE THE FILE GOES, AND THE ONE THING TO KNOW ABOUT IT
-------------------------------------------------------
`HoovyTools/_config/user_paths.json` - an underscored folder, so the underscore
convention already says it is optional and the add-on runs without it.

BEING INSIDE THE ADD-ON MEANS AN UPDATE THAT REPLACES THE FOLDER TAKES IT WITH
IT. That is a real cost and it is written down rather than hidden: the file is
plain readable JSON with absolute paths in it, so copying it out before an
update and back after is a drag-and-drop, and `Print Addon Behavior` includes
its full contents so the paths survive in any log report ever written.

EVERY READ IS FORGIVING, ON PURPOSE
-----------------------------------
A corrupt or hand-edited JSON returns empty defaults instead of raising. This
is read from `draw()` by way of the wiring readout, and a malformed file must
cost the user their extra folders - not their sidebar.
"""

import json
from pathlib import Path

from . import paths as _paths

STORE_NAME = "user_paths.json"
STORE_VERSION = 1

#  key -> (how many slots, human label). The counts are the whole spec: three
#  installs because that is what people have, two extras each for the data
#  folders because a folder of your own plus a shared one off a network drive
#  is the case that came up.
SLOTS = (
    ("usermod",      3, "SFM usermod"),
    ("dmxconvert",   2, "dmxconvert.exe"),
    ("faulty_rigs",  2, "Faulty Rigs"),
    ("qc_face_data", 2, "QC Face Data"),
)

#  WHY THE OTHER WIRING ROWS HAVE NO SLOT, and it is not an oversight.
#  SourceIO, the SMD importer and the .PCF add-on are ADD-ONS. Blender decides
#  where add-ons live and loads them from its own script paths; pointing
#  HoovyTools at a folder would not make Blender load one from there, so a
#  slot on those rows would be a control that does nothing. The rows above are
#  the ones this add-on actually goes looking in.

_COUNT = {k: n for k, n, _ in SLOTS}

#  Last read failure, so a broken file is reported once and not per redraw.
_last_load_error = None


def store_dir() -> Path:
    """`HoovyTools/_config`, underscored or not. Not created by reading."""
    return _paths.data_dir("config")


def store_path() -> Path:
    return store_dir() / STORE_NAME


def _blank() -> dict:
    return {"version": STORE_VERSION,
            **{k: [""] * n for k, n, _ in SLOTS}}


def load() -> dict:
    """The store, always shaped correctly. Never raises."""
    data = _blank()
    p = store_path()
    if not p.is_file():
        return data
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:                                  # noqa: BLE001
        #  ONCE PER DISTINCT FAULT, NOT ONCE PER READ. `load()` is called from
        #  the wiring readout, which is called from draw(), which runs on every
        #  mouse move - a broken file printed nine times in one test run here
        #  and would print thousands of times in a session. The message is
        #  worth saying; saying it again on the next redraw is not, so the
        #  signature is remembered and only a CHANGED fault speaks up again.
        global _last_load_error
        sig = f"{p}|{exc}"
        if sig != _last_load_error:
            _last_load_error = sig
            print(f"[HoovyTools]  {p.name} could not be read ({exc}) - "
                  f"extra folders ignored, nothing else affected")
        return data
    _last_load_error = None
    if not isinstance(raw, dict):
        return data
    for key, n, _ in SLOTS:
        got = raw.get(key)
        if not isinstance(got, (list, tuple)):
            continue
        #  Pad or trim to the slot count rather than trusting the file. A JSON
        #  written by an older build with two usermod slots must not make
        #  `slots("usermod")[2]` an IndexError three call sites away.
        for i in range(min(n, len(got))):
            v = got[i]
            data[key][i] = v.strip() if isinstance(v, str) else ""
    return data


def save(data: dict) -> Path:
    """Write the store, creating `_config` if this is the first added folder."""
    folder = store_dir()
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / STORE_NAME
    clean = {"version": STORE_VERSION}
    for key, n, _ in SLOTS:
        vals = list(data.get(key) or [])
        clean[key] = [(vals[i].strip() if i < len(vals)
                       and isinstance(vals[i], str) else "")
                      for i in range(n)]
    p.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    return p


def slots(key: str) -> list:
    """The raw strings for one key, always `_COUNT[key]` long."""
    return load().get(key, [""] * _COUNT.get(key, 0))


def set_slot(key: str, index: int, value: str) -> Path:
    """Set one slot and write. `value=""` clears it."""
    if key not in _COUNT:
        raise KeyError(key)
    if not 0 <= index < _COUNT[key]:
        raise IndexError(f"{key} slot {index}")
    data = load()
    data[key][index] = (value or "").strip()
    return save(data)


def folders(key: str) -> list:
    """The slots for one key that are set AND exist, as Paths, in slot order.

    De-duplicated by RESOLVED path, because the same folder reached two ways -
    `D:\\SFM\\game\\usermod` and a junction pointing at it - would otherwise be
    searched twice and reported twice.
    """
    out, seen = [], set()
    for raw in slots(key):
        if not raw:
            continue
        p = Path(raw)
        if not p.is_dir():
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


def fingerprint() -> tuple:
    """Cheap value that changes when the store changes.

    The wiring readout is cached against things that are free to read, and this
    has to be one of them - so it is the file's size and mtime, not its
    contents. Two different files of the same length written in the same
    hundredth of a second would collide; nothing writes this file but the
    user pressing a button.
    """
    p = store_path()
    try:
        st = p.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return (0, 0)
