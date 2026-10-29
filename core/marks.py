"""
core/marks.py  -  the coloured dot that starts a HoovyTools line

WHY A DOT AND NOT A WORD
------------------------
A console dump of an eight-step import is two hundred lines of grey text with
`[WARN]` and `[FAIL]` somewhere in it, and the eye does not find those - it
reads them, one line at a time, from the top. A coloured circle is found
before anything is read, which is the whole job: you should be able to scroll
a log and see WHERE the trouble is without parsing a word of it.

Same three colours as the panel, and that is the point. Green, orange and red
mean the same thing in the readout, on a button, in a report file and on the
console, so the vocabulary is learned once. The full legend lives in the
constitution under COLOUR.

THE FALLBACK IS NOT OPTIONAL
----------------------------
Blender's own console is UTF-8 and prints these fine - measured. Somebody
running Blender from a cmd.exe pinned to a legacy code page is not, and a
UnicodeEncodeError raised from inside a REPORT is a crash in the code whose
one job is to tell you what went wrong. So the marks are encode-tested once
against the real stdout and quietly become ASCII if they do not survive.
"""

import sys

#  The circles, and what they mean everywhere in this add-on.
_RICH = {
    "OK":      "\U0001F7E2",    # green circle  - fine
    "INFO":    "\U0001F7E2",    # green circle  - nothing wrong
    "WARNING": "\U0001F7E1",    # yellow circle - works, one thing is off
    "WARN":    "\U0001F7E1",
    "ERROR":   "\U0001F534",    # red circle    - this will not work
    "BAD":     "\U0001F534",
    #  PURPLE IS PROVENANCE - where a thing came from, not whether it worked.
    #  The other three answer "is this all right"; this one answers "which
    #  file". They are never on the same line, so a purple dot in a log means
    #  "this is a path you can go and open" and nothing else.
    #
    #  It is the same purple Developer Mode wears, and that is not an
    #  accident: both are information ABOUT the add-on rather than about the
    #  scene. The COLOUR section says so, because a colour that acquires a
    #  second meaning quietly is a colour that means nothing.
    "SOURCE":  "\U0001F7E3",    # purple circle - a file, go and look at it
}

_PLAIN = {
    "OK": "[ ok ]", "INFO": "[ ok ]",
    "WARNING": "[warn]", "WARN": "[warn]",
    "ERROR": "[FAIL]", "BAD": "[FAIL]",
    "SOURCE": "[file]",
}

_use_rich = None


def _can_encode():
    """Once, against the REAL stdout. `sys.stdout.encoding` can be None."""
    enc = getattr(sys.stdout, "encoding", None) or ""
    if not enc:
        return False
    try:
        "".join(_RICH.values()).encode(enc)
        return True
    except Exception:                                         # noqa: BLE001
        return False


def rich():
    global _use_rich
    if _use_rich is None:
        _use_rich = _can_encode()
    return _use_rich


def mark(level, pad=True):
    """The dot for a level. `pad` keeps columns lined up in a log file.

    An emoji is TWO CELLS WIDE in most terminals and one character in Python,
    so a plain `ljust` puts the ASCII and the emoji versions in different
    columns. One trailing space on the rich form is what makes a log written
    on one machine line up when read on another.
    """
    key = str(level or "INFO").upper()
    if rich():
        m = _RICH.get(key, _RICH["INFO"])
        return f"{m} " if pad else m
    m = _PLAIN.get(key, _PLAIN["INFO"])
    return m if pad else m


def legend():
    """One line naming what the colours mean, for the top of a report."""
    return (f"{mark('OK')}fine    "
            f"{mark('WARNING')}works, but one thing is off    "
            f"{mark('ERROR')}this will not work    "
            f"{mark('SOURCE')}a file you can open")
