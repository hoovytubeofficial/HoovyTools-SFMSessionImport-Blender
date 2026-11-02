"""
core/usage.py  -  what you import, counted  (3.0.3)

_config/usage.json:
    "models":      {model path: {"count", "last"}}                  every Import Model (Easy Import's too) +1
    "animations":  {animation .dmx: {model path: {"count", "last"}}}  every Import Animation onto a rig with a known
                                                                      model +1
The folders each importer opens are counted in _config/start_folders.json (core/start_folders.py, since 3.0.0) - a
folder picked 3+ times becomes where that importer's browser opens.

Never fatal: a broken file reads as empty, a failed write prints one line.
"""

import json
import os
import time
from pathlib import Path

STORE_NAME = "usage.json"


def store_path():
    from . import paths
    return paths.addon_root() / "_config" / STORE_NAME


def _load():
    try:
        d = json.loads(store_path().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:                                         # noqa: BLE001
        return {}


def _save(d):
    try:
        p = store_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, indent=1), encoding="utf-8")
        tmp.replace(p)
    except Exception as exc:                                  # noqa: BLE001
        print("[USAGE]  not saved: %s" % exc)


def key(path):
    return os.path.normcase(os.path.abspath(str(path)))


def _bump(entry, by=1):
    entry["count"] = int(entry.get("count", 0)) + by
    entry["last"] = time.time()
    return entry


def model_imported(path):
    """+1 for a model imported"""
    d = _load()
    _bump(d.setdefault("models", {}).setdefault(key(path), {"count": 0}))
    _save(d)


def model_added(path):
    """a model put on the list by hand: there with 0 imports until it is used (the newest stays on the list)"""
    d = _load()
    e = d.setdefault("models", {}).setdefault(key(path), {"count": 0})
    e["last"] = time.time()
    _save(d)


def animation_on(dmx, model):
    """+1 for an animation imported onto a model"""
    if not dmx or not model:
        return
    d = _load()
    _bump(d.setdefault("animations", {}).setdefault(key(dmx), {}).setdefault(key(model), {"count": 0}))
    _save(d)


def _ranked(table, n):
    rows = [(k, int(e.get("count", 0)), float(e.get("last", 0))) for k, e in table.items() if os.path.isfile(k)]
    rows.sort(key=lambda r: (-r[1], -r[2]))
    out = rows[:n]
    newest = max(rows, key=lambda r: r[2]) if rows else None
    if newest is not None and newest not in out and out:       # one just added (0 imports) is always on the list
        out[-1] = newest
    return [(k, c) for k, c, _l in out]


def top_models(n=10):
    """[(model path, count)] - the most imported first"""
    return _ranked(_load().get("models") or {}, n)


def models_for(dmx, n=5):
    """[(model path, count)] - the models this animation was imported onto, most first"""
    if not dmx:
        return []
    return _ranked((_load().get("animations") or {}).get(key(dmx)) or {}, n)
