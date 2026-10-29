"""
core/console_mark.py  -  every console line this add-on prints starts with its name

WHY
---
Blender's console is shared by every enabled add-on, and this one's lines used
to start with tags only it knew - [DMX_CAM], [SESSION], [HT_PATHS]. In a pasted
console nobody could tell which add-on said what. Now every line printed from
this package carries the add-on's name first:

    [SFM Session Importer] [DMX_CAM]  camera5: 240 keys

HOW
---
builtins.print is wrapped ONCE, at register. The wrapper looks at who called
print - the first frame outside any print wrapper - and marks the line only
when that caller's module belongs to this package. Another add-on's prints pass
through untouched. Wrappers chain: Source Particle Import wraps print the same
way, every wrapper module carries `__print_wrapper__ = True` so the others step
over its frames, and each one only ever marks its own lines.

Output written to a FILE (print(..., file=fh)) is never marked. Anything that
goes wrong inside the wrapper falls back to the plain print - the console must
keep working whatever happens here.
"""

import builtins
import sys

MARK = "[SFM Session Importer]"
PACKAGE = (__package__ or "").split(".")[0]

# read by every print wrapper in the family: a frame whose module says this is
# skipped while looking for the real caller
__print_wrapper__ = True

_prev = None        # the print this wrapper hands on to
_on = False         # off = a plain pass-through (unregistered, still chained)
_CONSOLE = None


def _consoles():
    global _CONSOLE
    if _CONSOLE is None:
        _CONSOLE = {id(s) for s in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__)
                    if s is not None}
    return _CONSOLE


def _caller_is_mine():
    f = sys._getframe(1)
    while f is not None and f.f_globals.get("__print_wrapper__"):
        f = f.f_back
    name = f.f_globals.get("__name__", "") if f is not None else ""
    return name == PACKAGE or name.startswith(PACKAGE + ".")


def mark_text(text):
    """MARK in front of every line that has something on it."""
    return "\n".join((MARK + " " + ln) if ln.strip() else ln
                     for ln in str(text).split("\n"))


def _print(*args, **kwargs):
    prev = _prev or builtins.__dict__.get("print")
    try:
        target = kwargs.get("file")
        if _on and (target is None or id(target) in _consoles()) and _caller_is_mine():
            sep = kwargs.get("sep")
            text = (" " if sep is None else str(sep)).join(str(a) for a in args)
            rest = {k: v for k, v in kwargs.items() if k != "sep"}
            return prev(mark_text(text), **rest)
    except Exception:                                         # noqa: BLE001
        pass
    return prev(*args, **kwargs)


def install():
    """Wrap print (once) and switch marking on."""
    global _prev, _on
    if _prev is None:
        _prev = builtins.print
        builtins.print = _print
    _on = True


def uninstall():
    """Switch marking off. Unwraps when nothing wrapped print after us -
    otherwise stays in the chain as a pass-through, so the wrapper above keeps
    a working print to hand on to."""
    global _prev, _on
    _on = False
    if _prev is not None and builtins.print is _print:
        builtins.print = _prev
        _prev = None
