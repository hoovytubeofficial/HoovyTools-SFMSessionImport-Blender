"""
core/popups.py  -  which reports open a dialog, as a file you can edit

WHY THIS LEFT THE DEVELOPER TAB
-------------------------------
It was a box of eighteen checkboxes on the screen people open when an import
has just failed. Nobody who is stuck needs to change which dialogs appear;
they need to know where SFM is. So the box is gone from the panel and the
setting lives here, in `_config/_popupvariables.json`, next to the other
config files - editable, greppable, and out of the way.

THE POPUPS STILL WORK EXACTLY AS THEY DID. Every one of them still draws its
own checkbox inside itself, which is where turning one off has always made
sense - you switch a dialog off at the moment it annoys you, not from a list
of eighteen names you have to match to reports you half remember.

THE SCENE PROPERTIES ARE STILL THE LIVE VALUE
---------------------------------------------
`scene.ht_reports` is what `popup_enabled()` reads and what the in-popup
checkbox writes, because that is what Blender's UI can bind to. This file is
the part that SURVIVES: loaded into the scene block when the add-on
registers, written back whenever a switch changes.

GLOBAL, NOT PER-SCENE, AND THAT IS THE FIX. Being a scene property meant "I
turned that dialog off" lasted until you opened a different .blend, which
made it look like the setting did not work. It follows the add-on now.

NOTHING HERE RAISES. A missing or mangled file means every popup is ON, which
is the same as a fresh install and the safe direction: a report you did not
want is a nuisance, a report you needed and never saw is a bug hunt.
"""

import json
from pathlib import Path

from . import paths as _paths

STORE_NAME = "_popupvariables.json"
STORE_VERSION = 1

_last_error = None


def store_dir() -> Path:
    return _paths.data_dir("config")


def store_path() -> Path:
    return store_dir() / STORE_NAME


def load() -> dict:
    """{key: bool}. Missing, unreadable or partial all mean 'everything on'."""
    global _last_error
    p = store_path()
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:                                  # noqa: BLE001
        sig = f"{p}|{exc}"
        if sig != _last_error:
            _last_error = sig
            print(f"[HoovyTools]  {p.name} could not be read ({exc}) - "
                  f"every popup is on")
        return {}
    _last_error = None
    got = raw.get("popups") if isinstance(raw, dict) else None
    if not isinstance(got, dict):
        return {}
    return {k: bool(v) for k, v in got.items() if isinstance(k, str)}


def save(values: dict, keys=None) -> Path:
    """Write the switches. `keys` fixes the order so diffs stay readable."""
    d = store_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / STORE_NAME
    order = list(keys) if keys else sorted(values)
    payload = {
        "version": STORE_VERSION,
        "note": ("Which HoovyTools reports open a dialog. false = no dialog; "
                 "the report still prints to the console and still shows in "
                 "the status bar. Every popup also has this checkbox inside "
                 "itself, which is the easy way to change one."),
        "popups": {k: bool(values.get(k, True)) for k in order},
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def apply_to(block, keys):
    """Copy the file onto a scene's switch block. Returns how many were set."""
    if block is None:
        return 0
    stored = load()
    n = 0
    for k in keys:
        if k in stored and hasattr(block, k):
            try:
                setattr(block, k, stored[k])
                n += 1
            except Exception:                                 # noqa: BLE001
                pass
    return n


def capture_from(block, keys):
    """Write a scene's switch block out to the file."""
    if block is None:
        return None
    return save({k: bool(getattr(block, k, True)) for k in keys}, keys)
