"""
HoovyTools/SST/  —  Bundled Source Tools subset
=================================================
Bundles the minimum files from Blender Source Tools needed for
HoovyTools to import SMD/DMX animations without requiring BST
to be installed as a separate Blender addon.

Bundled files (copy from BST source into this folder):
  datamodel.py      — DMX parsing                (already present)
  import_smd.py     — SmdImporter operator
  utils.py          — shared BST utilities
  ordered_set.py    — ordered set data structure
  flex.py           — flex/shape key helpers
  translations.py   — UI string table

  Copyright (c) 2014 Tom Edwards  contact@steamreview.org
  Licensed under GPL v2 or later.
  Source: https://github.com/Artfunkel/BlenderSourceTools

Usage from HoovyTools:
  from .SST import get_datamodel, ensure_smd_importer, unregister_smd_importer
"""

import sys
import bpy
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
#  DATAMODEL  (existing logic, unchanged)
# ──────────────────────────────────────────────────────────────────────────────

_datamodel_cache = None


def get_datamodel():
    """
    Return the datamodel module.

    Priority:
      1. Already loaded in sys.modules (BST is present) — free reuse.
      2. Previously cached load of our bundled copy.
      3. Load our bundled HoovyTools/SST/datamodel.py fresh.
    """
    global _datamodel_cache

    # 1. BST already loaded — reuse it at no cost
    for name, mod in sys.modules.items():
        if name.endswith(".datamodel") and hasattr(mod, "DataModel") and hasattr(mod, "Time"):
            return mod

    # 2. Previously loaded bundled copy
    if _datamodel_cache is not None:
        return _datamodel_cache

    # 3. Load our bundled copy
    bundled = Path(__file__).parent / "datamodel.py"
    if not bundled.exists():
        raise ImportError(
            f"[HoovyTools/SST]  datamodel.py not found at:\n  {bundled}\n"
            f"Copy datamodel.py from Blender Source Tools into HoovyTools/SST/"
        )

    import importlib.util
    spec = importlib.util.spec_from_file_location("_ht_sst_datamodel", str(bundled))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules["_ht_sst_datamodel"] = mod
    _datamodel_cache = mod
    print("[HoovyTools/SST]  bundled datamodel.py loaded")
    return _datamodel_cache


# ──────────────────────────────────────────────────────────────────────────────
#  SMD IMPORTER
# ──────────────────────────────────────────────────────────────────────────────

_sst_importer_registered  = False   # True if WE registered SmdImporter
_sst_props_registered     = False   # True if WE registered the .vs props


def _bst_is_active() -> bool:
    """True when BST is enabled in Blender's addon registry."""
    return "io_scene_valvesource" in bpy.context.preferences.addons


def ensure_smd_importer():
    """
    Guarantee that bpy.ops.import_scene.smd exists.

    Always attempts to register SmdImporter from the bundled SST copy.
    If BST already registered it, Blender raises RuntimeError — we catch
    it silently and move on. Either way the operator is available.

    Safe to call multiple times.
    """
    global _sst_importer_registered, _sst_props_registered

    if _sst_importer_registered:
        return   # already done by us in a previous call

    # ── Check all required files are present ──────────────────────────────────
    sst_dir  = Path(__file__).parent
    required = ("import_smd.py", "utils.py", "ordered_set.py",
                "flex.py", "translations.py", "datamodel.py")
    missing  = [f for f in required if not (sst_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"[HoovyTools/SST]  Missing bundled BST files: {missing}\n"
            f"Copy them from Blender Source Tools into:\n  {sst_dir}"
        )

    # ── Register .vs property groups first (import_smd reads them) ────────────
    from . import sst_props
    try:
        sst_props.register_props()
        _sst_props_registered = True
    except Exception:
        # BST already registered .vs props — that's fine
        print("[HoovyTools/SST]  .vs props already registered (BST present) — skipping")

    # ── Register SmdImporter ───────────────────────────────────────────────────
    from . import import_smd as _import_smd_mod

    # Patch out BST-specific post-import scene management — HoovyTools doesn't
    # use BST's export list or scene update hooks, and they require property
    # groups we deliberately don't register.
    from . import utils as _sst_utils
    _sst_utils.State.update_scene = classmethod(lambda cls, scene=None: None)
    _sst_utils.State.hook_events  = classmethod(lambda cls: None)
    _sst_utils.State.unhook_events = classmethod(lambda cls: None)

    try:
        bpy.utils.register_class(_import_smd_mod.SmdImporter)
        _sst_importer_registered = True
        print("[HoovyTools/SST]  SmdImporter registered as 'ht.import_smd'")
    except Exception as exc:
        print(f"[HoovyTools/SST]  Failed to register SmdImporter: {exc}")
        raise


def unregister_smd_importer():
    """
    Unregister SmdImporter and .vs props only if WE registered them.
    If BST was providing them, we leave BST's registrations alone.
    """
    global _sst_importer_registered, _sst_props_registered

    if _sst_importer_registered:
        from . import import_smd as _import_smd_mod
        try:
            bpy.utils.unregister_class(_import_smd_mod.SmdImporter)
            print("[HoovyTools/SST]  SmdImporter unregistered")
        except Exception:
            pass
        _sst_importer_registered = False

    if _sst_props_registered:
        from . import sst_props
        sst_props.unregister_props()
        _sst_props_registered = False
