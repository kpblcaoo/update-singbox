try:
    from importlib.metadata import version as _version
    __version__ = _version("sboxmgr")
except Exception:
    __version__ = "unknown" 