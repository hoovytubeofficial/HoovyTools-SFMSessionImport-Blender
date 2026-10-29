"""
core/paths.py  -  where things are on disk

THE ONE PLACE THAT KNOWS THE FOLDER LAYOUT.

Before the packages existed, six modules each did

    Path(__file__).parent / "Faulty Rigs"

which was correct only while every module sat in the add-on root. The moment
anything moved a level down, every one of them silently pointed at a folder
that does not exist - and the failure would have read as "no reference file
for this rig", not as "the path is wrong". So they all come through here now.

THE UNDERSCORE CONVENTION, which this function implements:

    name      required. The add-on does not start without it.
    _name     OPTIONAL. Shipped, but the add-on runs if you delete it.
    __name    development only. Never shipped.

Data folders are optional by that rule - a missing `_Faulty Rigs` means the rig
fixer reports "no reference file" and everything else carries on - so they are
looked up under the underscored name first and the bare name second. The
fallback is not politeness: a user who unzipped an older build has the bare
names, and silently finding nothing would be worse than finding the old folder.

THE SAME TOLERANCE APPLIES OFF-DISK-LAYOUT TOO. `data_dir_at()` runs the
underscored-then-bare ladder against ANY parent, which is what lets the SFM-side
`_Dev` copies of `_Faulty Rigs` and `_QC Face Data` be renamed to match the
convention without breaking anyone still holding the bare-named ones.
"""

from pathlib import Path

#  A folder under SourceFilmmaker/game is a MOUNT if it holds one of these.
#  Signature, not a whitelist: `workshop` is the folder people report missing,
#  and no fixed list of mod names can know what someone called theirs.
_MOD_MARKERS = ("gameinfo.txt", "models", "materials", "particles",
                "sound", "maps", "scripts")

#  Not mounts, and cheap to say so by name: `bin` is the engine's DLLs and
#  `reports` is SFM's crash dumps. Both would otherwise match on `scripts`
#  or on sheer coincidence and add a pointless branch to every model lookup.
_NOT_MODS = {"bin", "reports", "screencast"}


def addon_root() -> Path:
    """The HoovyTools folder itself, from two levels down."""
    return Path(__file__).resolve().parent.parent


def data_dir_at(parent: Path, name: str) -> Path:
    """`parent/_name` if it exists, else `parent/name` if it does, else the
    underscored one - so a caller printing it names what to create."""
    parent = Path(parent)
    for candidate in (parent / ("_" + name), parent / name):
        if candidate.is_dir():
            return candidate
    return parent / ("_" + name)


def data_dir(name: str) -> Path:
    """An optional data folder inside the add-on, underscored or not."""
    return data_dir_at(addon_root(), name)


#  WHERE THE REPORTS ARE WRITTEN
#  -----------------------------
#  `_Logs`, one underscore: optional, and the add-on runs without it.
#
#  THIS FOLDER IS THE ONE EXCEPTION TO THE UNDERSCORE CONVENTION, so it is
#  written down here rather than remembered. The convention is `name`
#  required, `_name` optional but SHIPPED, `__name` development only and
#  never shipped. A log is runtime output and is not content, so by that
#  reading it belongs under two underscores, where `__*/` in `.gitignore`
#  excludes it automatically and nobody has to think about it.
#
#  It is `_Logs` anyway, because a log the user is meant to find has to sit
#  somewhere they will look. That costs the automatic exclusion: `_name` is
#  a SHIPPED tier, so nothing in `.gitignore` covers this folder by pattern
#  and it needs its own explicit `_Logs/` line. That line is load-bearing -
#  delete it and every report this add-on writes starts getting committed.
#
#  CREATED ON DEMAND, AND NEVER FATAL. An add-on folder can be read-only -
#  installed by an admin, or sitting on a share - and that is a reason to skip
#  a log file, not a reason to break every report in the add-on. Returns None
#  and the caller carries on printing to the console exactly as before.

LOGS_DIR_NAME = "_Logs"


def logs_dir(create=True):
    """The add-on's log folder, or None if it cannot be had."""
    try:
        d = addon_root() / LOGS_DIR_NAME
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d if d.is_dir() else None
    except Exception:
        return None


def faulty_rigs() -> Path:
    """Reference DMX files the rig fixer reads rest poses from."""
    return data_dir("Faulty Rigs")


def qc_face_data() -> Path:
    """QC files the HWM localvar bake needs."""
    return data_dir("QC Face Data")


QC_GENERATED_NAME = "_Generated"


def qc_generated(create=False):
    """3.0.0: where the QCs written from imported models go - `_QC Face Data/_Generated` inside the add-on, or
    Blender's config folder when the add-on folder is read-only. None when neither can be had.

    Runtime output, like `_Logs`: `.gitignore` names it, and the next import writes a deleted file again."""
    for d in (qc_face_data() / QC_GENERATED_NAME, _config_qc_dir()):
        if d is None:
            continue
        try:
            if create:
                d.mkdir(parents=True, exist_ok=True)
                probe = d / ".write_test"
                probe.write_text("", encoding="utf-8")
                probe.unlink()
            if d.is_dir():
                return d
        except Exception:                                     # noqa: BLE001
            continue
    return None


def _config_qc_dir():
    try:
        import bpy
        return Path(bpy.utils.user_resource('CONFIG', path="SFM Session Importer")) / "QC Face Data"
    except Exception:                                         # noqa: BLE001
        return None


ADDON_MODULE = (__package__ or "").split(".")[0]


def addon_prefs():
    """This add-on's own AddonPreferences, or None when it is not enabled.

    Returns None instead of raising: a caller that only wants a usermod
    path should degrade, not take the import down with it.
    """
    import bpy
    entry = bpy.context.preferences.addons.get(ADDON_MODULE)
    return entry.preferences if entry else None


def icons() -> Path:
    """Custom panel icons. Stock Blender icons are used when absent.

    `images` is the current, colour-coded set and is REQUIRED - the panel is
    built around it. `images` and `_Icons` were earlier names and are still
    looked for, newest first, so an install carrying an old folder keeps
    working and one carrying both prefers the new."""
    root = addon_root()
    for candidate in (root / "images", root / "images",
                      root / "_Icons", root / "Icons"):
        if candidate.is_dir():
            return candidate
    return root / "images"


def is_mod_dir(path: Path) -> bool:
    """Does this folder look like a Source mod mount?"""
    path = Path(path)
    if not path.is_dir() or path.name.lower() in _NOT_MODS:
        return False
    for marker in _MOD_MARKERS:
        if (path / marker).exists():
            return True
    #  A VPK-only mount has no loose folders at all. `next()` on the glob
    #  rather than a list: one hit is the whole answer and some of these
    #  folders hold thousands of files.
    return next(path.glob("*.vpk"), None) is not None


def mod_dirs(usermod: Path) -> list:
    """Every mod mount under SourceFilmmaker/game, usermod first.

    WHY THIS EXISTS. `gameinfo.txt` only lists what VALVE shipped plus what a
    user hand-edited into it, and SFM itself mounts more than that - Workshop
    content in particular lands in `game/workshop`, which no stock gameinfo
    mentions. People kept reporting "it cannot find my Workshop model" and the
    honest answer was that the add-on had never looked there.

    Reading the folder rather than a list of names is the point: `tf`,
    `tf_movies`, `hl2` and `workshop` were hardcoded in three separate modules,
    each with a different subset, and none of them knew about the half-dozen
    other mods a real install accumulates.

    Returns [] rather than raising if the path is wrong - every caller treats
    search paths as best-effort and reports what it could not find.
    """
    usermod = Path(usermod)
    game = usermod.parent
    if not game.is_dir():
        return []
    out = []
    if usermod.is_dir():
        out.append(usermod.resolve())
    try:
        children = sorted(game.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return out
    for child in children:
        if not is_mod_dir(child):
            continue
        rp = child.resolve()
        if rp not in out:
            out.append(rp)
    return out
