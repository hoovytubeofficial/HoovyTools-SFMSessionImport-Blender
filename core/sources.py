"""
core/sources.py  -  WHAT THIS SCENE WAS BUILT FROM

Every step already prints what it did. None of them prints WHICH FILE it did
it from, and that is the thing you need when something looks wrong: not "8
particle effects built" but the .pcf those definitions came out of, so you can
open it. The information exists at every import site and was thrown away the
moment the step finished.

So each importer records one line here as it resolves a file, and one report
prints the lot. It is a MANIFEST, not a log: one entry per file, no timing, no
counts, nothing that changes between two identical runs.

WHY PURPLE
==========
The constitution's COLOUR section is emphatic - a colour means one thing
everywhere or it means nothing anywhere - and purple was Developer Mode's.
This extends it, deliberately and with the user's word for it, to:

    PURPLE = PROVENANCE. Where this came from.

Developer Mode is the same idea wearing a different hat: both are information
ABOUT the add-on rather than about the scene. Nothing else may take purple,
and the COLOUR section says so now. The alternative was a fourth meaning for
green, which would have made green mean nothing.

WHY IT IS NOT A LIST OF EVERYTHING
==================================
Only files with an ANSWER in them: the session, the .mdl per model, the .pcf
per effect. Not the reference DMX the rig fixer read, not the QC the face bake
parsed - those are the add-on's own data and a user cannot act on them. The
test is "would you open this file to find out why the scene looks like that".

STATE, AND WHY IT IS CLEARED PER RUN
====================================
Held in a module global, cleared by `begin()`. A manifest that accumulated
across two imports would name files that are not in the scene any more, which
is worse than no manifest - it would send somebody to open the wrong .pcf.
The one-click calls `begin()`; a step run on its own appends to whatever is
there and says so, because a step IS an addition to the scene.
"""

import bpy
from pathlib import Path

from bpy.types import Operator

from . import marks


#  Kinds, in the order they are printed. The order is the pipeline's, so the
#  manifest reads the way the import ran.
KINDS = ("session", "model", "particle", "sound", "camera")

_KIND_LABEL = {
    "session":  "Session",
    "model":    "Models",
    "particle": "Particles",
    "sound":    "Sounds",
    "camera":   "Cameras",
}

_entries = []          # [{kind, name, path}]


def begin():
    """Start a fresh manifest. Called by whatever owns a whole import."""
    _entries.clear()


def add(kind, name, path):
    """Record one file. Silently ignores a blank path - a step that resolved
    nothing must not put an empty line in the manifest."""
    if not path:
        return
    kind = kind if kind in KINDS else "model"
    p = str(path)
    for e in _entries:
        if e["kind"] == kind and e["path"] == p and e["name"] == str(name):
            return                      # same file, same set - said once
    _entries.append({"kind": kind, "name": str(name or ""), "path": p})


def entries(kind=None):
    return [e for e in _entries if kind is None or e["kind"] == kind]


def _exists(p):
    try:
        return Path(p).exists()
    except Exception:
        return False


def lines(width=96):
    """The manifest as report lines. Empty list when nothing was recorded."""
    if not _entries:
        return []

    dot = marks.mark("SOURCE")
    out = [f"{dot}WHAT THIS SCENE WAS BUILT FROM", ""]

    for kind in KINDS:
        got = entries(kind)
        if not got:
            continue
        out.append(f"{dot}{_KIND_LABEL[kind]}  ({len(got)})")
        for e in got:
            #  THE FULL PATH, NOT THE FILE NAME. The whole point is being able
            #  to go and open it, and three `scout.mdl` under three different
            #  mods is the normal case.
            path = e["path"]
            if len(path) > width:
                path = "..." + path[-(width - 3):]
            head = f"   {e['name']}" if e["name"] else "   "
            out.append(head)
            #  A file that has since moved is worth saying, because "check
            #  this file" is the instruction and it would fail silently.
            out.append(f"      {path}" + ("" if _exists(e["path"])
                                          else "   [NOT THERE NOW]"))
        out.append("")

    while out and not out[-1]:
        out.pop()
    return out


def report(context, operator=None, title="Source Files"):
    """Print the manifest through the normal channel. No-op when empty."""
    body = lines()
    if not body:
        return False
    from . import Report_UI
    Report_UI.report(context, "sources", title, body,
                     level='INFO', operator=operator, prefix="SOURCES",
                     summary=f"{len(_entries)} source file(s) - see the console"
                             f" or _Logs")
    return True


class HT_OT_source_manifest(Operator):
    """List every file this scene was built from - session, models, particles

Each importer records the file it resolved as it runs, and this prints the
lot in one place: the session .dmx, the .mdl behind every model, and the
.pcf behind every particle effect. Full paths, because three `scout.mdl`
under three different mods is the normal case and the file name alone
tells you nothing.

Marked in PURPLE, which in this add-on means provenance - where something
came from, rather than whether it worked.

It is filled by importing. Run it on an empty scene and it says so"""
    bl_idname = "ht.source_manifest"
    bl_label = "Source Files"
    bl_options = {"REGISTER"}

    def execute(self, context):
        if not report(context, operator=self):
            self.report({"INFO"},
                        "Nothing recorded yet - import a session first.")
        return {"FINISHED"}


_CLASSES = (HT_OT_source_manifest,)


def register(icon_id_fn=None):
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
