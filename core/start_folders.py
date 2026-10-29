"""
core/start_folders.py  -  where each file browser opens  (3.0.0)

Every importer opens its browser at start(kind) and counts the folder it was given with remember_file(). A folder
picked LEARN_AFTER (3) times or more becomes that importer's folder - written to _config/start_folders.json, so it
outlives the .blend. Until then each kind opens at its usual SFM folder (the config ladder: usermod/elements for
sessions, animations, cameras and shape keys; usermod/models; usermod/materials; usermod/maps).

`browser_at(kind)` puts both on an operator class. Never fatal: a broken store or a vanished folder falls back to
the usual folder, then to wherever Blender's browser was.
"""

import json
import os
import time
from pathlib import Path

LEARN_AFTER = 3
STORE_NAME = "start_folders.json"

# kind -> the config ladder's folder kind (core/config.py KINDS)
KINDS = {
    "session": "elements",
    "animation": "elements",
    "camera": "elements",
    "shapekeys": "elements",
    "animations_folder": "elements",
    "model": "models",
    "material": "materials",
    "texture": "materials",
    "map": "maps",
}


def store_path():
    from . import paths
    return paths.addon_root() / "_config" / STORE_NAME


def _load():
    try:
        data = json.loads(store_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:                                         # noqa: BLE001
        return {}


def _save(data):
    try:
        p = store_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(p)
    except Exception as exc:                                  # noqa: BLE001
        print("[START_FOLDERS]  not saved: %s" % exc)


def remember(kind, folder):
    """Count one pick of `folder` for `kind`. Returns the count."""
    if not folder:
        return 0
    folder = str(Path(folder))
    data = _load()
    entry = data.setdefault(kind, {}).setdefault(folder, {"count": 0})
    entry["count"] = int(entry.get("count", 0)) + 1
    entry["last"] = time.time()
    _save(data)
    if entry["count"] == LEARN_AFTER:
        print("[START_FOLDERS]  %s now opens at %s (picked %d times)" % (kind, folder, LEARN_AFTER))
    return entry["count"]


def remember_file(kind, filepath):
    """Count the folder a picked file sits in (or the folder itself)."""
    if not filepath:
        return 0
    p = Path(filepath)
    return remember(kind, p if p.is_dir() else p.parent)


def learned(kind):
    """The folder picked LEARN_AFTER+ times for `kind` (most picks, then most recent), if it still exists."""
    picks = _load().get(kind) or {}
    best = None
    for folder, entry in picks.items():
        n = int(entry.get("count", 0))
        if n < LEARN_AFTER or not Path(folder).is_dir():
            continue
        key = (n, float(entry.get("last", 0)))
        if best is None or key > best[0]:
            best = (key, folder)
    return best[1] if best else None


def default(kind):
    """The usual SFM folder for `kind`, from the config ladder."""
    try:
        from ..session.Session_Paths import config_folder
        d = config_folder(KINDS.get(kind, "elements"))
        return str(d) if d is not None else None
    except Exception:                                         # noqa: BLE001
        return None


def start(kind):
    """A folder path ending in a separator for a browser's filepath, or "" (Blender's own choice)."""
    d = learned(kind) or default(kind)
    return (str(Path(d)) + os.sep) if d else ""


def browser_at(kind):
    """Class decorator for an import operator: its browser opens at start(kind), and every run counts the pick.
    Keeps the class's own invoke (ImportHelper's or its own) - only an empty filepath is filled in first."""
    def deco(cls):
        inv = getattr(cls, "invoke", None)
        exe = cls.execute

        def invoke(self, context, event):
            if not getattr(self, "filepath", ""):
                try:
                    p = start(kind)
                    if p:
                        self.filepath = p
                except Exception:                             # noqa: BLE001
                    pass
            if inv is not None:
                return inv(self, context, event)
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}

        def execute(self, context):
            try:
                remember_file(kind, getattr(self, "filepath", "") or getattr(self, "directory", ""))
            except Exception:                                 # noqa: BLE001
                pass
            return exe(self, context)

        invoke.__doc__, execute.__doc__ = getattr(inv, "__doc__", None), exe.__doc__
        cls.invoke = invoke
        cls.execute = execute
        return cls
    return deco
