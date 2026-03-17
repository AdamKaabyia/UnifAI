"""Convenience shortcut — same as ``mas worker``."""
from bootstrap.cli import app
import sys

sys.argv = ["mas", "worker"] + sys.argv[1:]
app()
