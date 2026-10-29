"""
core/logvars.py  -  which reports are WRITTEN TO THE LOG FILE, as a file

THE SIBLING OF core/popups.py, FOR THE OTHER SURFACE
----------------------------------------------------
popups.py decides which reports open a DIALOG. This file decides which
reports land in `_Logs/HoovyTools_<stamp>.log`. Same shape on purpose - one
JSON in `_config/`, loaded onto a scene block at register, written back
whenever a switch changes - because the popup store already solved the only
hard part (a scene property does not survive opening another .blend, a
config file does).

WHAT A SWITCH BEING OFF MEANS
-----------------------------
The report still prints to the console, still reaches the status bar and
the Info editor, and still lands in the in-memory history that PRINT ADDON
BEHAVIOR reads. It only stops being appended to the log FILE. So switching
things off here shapes the file you hand to somebody, it never loses the
live output.

The switches are drawn in the Developer tab's LOGS box (magenta), one per
report key from Report_UI.REPORTS.

NOTHING HERE RAISES. A missing or mangled file means every report is
logged, which matches a fresh install and is the safe direction: a fat log
is a nuisance, a missing line in the one log that mattered is a bug hunt.
"""

import json
from pathlib import Path

from . import paths as _paths

STORE_NAME = "_logvariables.json"
STORE_VERSION = 1

_last_error = None


def store_dir() -> Path:
    return _paths.data_dir("config")


def store_path() -> Path:
    return store_dir() / STORE_NAME


def load() -> dict:
    """{key: bool}. Missing, unreadable or partial all mean 'log everything'."""
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
                  f"every report is logged")
        return {}
    _last_error = None
    got = raw.get("logs") if isinstance(raw, dict) else None
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
        "note": ("Which HoovyTools reports are written to the _Logs file. "
                 "false = that report is left out of the log; it still "
                 "prints to the console and still shows in the status bar. "
                 "The switches are in the Developer tab's LOGS box."),
        "logs": {k: bool(values.get(k, True)) for k in order},
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
