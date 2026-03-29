"""
Backward-compatible re-export.

The canonical directory provider interface now lives in
``global_utils.directory.provider``.  This module re-exports it under the
legacy name so existing backend code keeps working unchanged.
"""
from global_utils.directory.provider import DirectoryProvider as TeamDirectoryProvider

__all__ = ["TeamDirectoryProvider"]
