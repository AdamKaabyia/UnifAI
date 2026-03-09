"""Document converters."""

__all__ = [
    "LocalDoclingAdapter",
    "RemoteDoclingAdapter",
]

# converters classes are loaded on demand rather than at import time.
# This prevents heavy optional dependencies (e.g. docling) from being
# imported when only the remote adapter is needed (and docling is not installed).
_ADAPTER_MAP = {
    "LocalDoclingAdapter": (
        "infrastructure.sources.document.converters.local_docling_adapter",
        "LocalDoclingAdapter",
    ),
    "RemoteDoclingAdapter": (
        "infrastructure.sources.document.converters.remote_docling_adapter",
        "RemoteDoclingAdapter",
    ),
}


def __getattr__(name: str):
    if name in _ADAPTER_MAP:
        module_path, attr = _ADAPTER_MAP[name]
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
