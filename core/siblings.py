"""
siblings.py  -  finding the other HoovyTools add-ons

WHY THIS EXISTS
---------------
A FOLDER NAME IS A MODULE NAME, and on 2026-08-24 the family moved onto one
scheme with hyphens in it:

    HoovyTools-ParticleImport-Blender-Master

which the `import` statement CANNOT SPELL. `from HoovyTools-... import api`
is a syntax error, not a lookup failure. Blender itself loads these fine -
addon_utils goes through importlib, which takes any string - so the add-ons
work; it is only code naming a SIBLING that breaks.

Every such lookup now comes through here.

AND THE NAME IS NOT ONE NAME
----------------------------
The particle add-on has been installed under at least three:

    HoovyTools-ParticleImport-Blender-Master    the current scheme
    HoovyToolsParticleImport                    what it was called before
    HoovyToolsParticleImport-main               what GitHub's zip unpacks to

A user who downloaded the zip and dropped it in has the third. That is not
a mistake to correct, it is a fact to cope with, so `find()` tries all of
them and reports WHICH ONE it found - the Developer tab prints that, because
"the particle add-on is installed under a name I did not expect" is a
different problem from "it is not installed".

ONLY EVER CALLED INSIDE A FUNCTION
----------------------------------
A cross-add-on import at module scope turns an OPTIONAL dependency into a
required one: the module fails to import, and the add-on that merely wanted
to offer a feature fails to load at all. Import late, catch, degrade.
"""

import importlib
import sys

# kind -> candidate module names, best first
CANDIDATES = {
    "particles": (
        "HoovyTools-ParticleImport-Blender-Master",
        #3.0.0: what the GitHub repository's "Download ZIP" unpacks to
        "HoovyTools-ParticleImport-Blender-master",
        "HoovyTools-ParticleImport-Blender-main",
        "HoovyToolsParticleImport",
        "HoovyToolsParticleImport-main",
    ),
    # 3.0.10: only what this add-on USES - it's public, and nothing here needs the others
}


def names(kind):
    """Every name this sibling might be installed under."""
    return CANDIDATES.get(kind, ())


def find(kind):
    """(module_name, module) for the first candidate that imports, else
    (None, None).

    Already-imported modules are preferred, so an add-on Blender has enabled
    is found without importing anything a second time.
    """
    for name in names(kind):
        mod = sys.modules.get(name)
        if mod is not None:
            return name, mod
    for name in names(kind):
        try:
            return name, importlib.import_module(name)
        except Exception:
            continue
    return None, None


def module(kind):
    """The sibling's top-level module, or None."""
    return find(kind)[1]


def submodule(kind, sub):
    """`<sibling>.<sub>`, or None.

    The replacement for `from HoovyToolsParticleImport import api`:

        api = siblings.submodule("particles", "api")
        if api is None:
            ...degrade...
    """
    name, _mod = find(kind)
    if name is None:
        return None
    try:
        return importlib.import_module("%s.%s" % (name, sub))
    except Exception:
        return None


def installed_as(kind):
    """The name it was actually found under, or None. For reports - so a
    wiring readout can say WHICH name matched instead of just 'yes'."""
    return find(kind)[0]
