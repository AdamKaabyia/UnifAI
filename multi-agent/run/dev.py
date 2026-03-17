"""Convenience shortcut — same as ``mas api --dev``."""
if __name__ == "__main__":
    from bootstrap.cli import app
    import sys
    sys.argv = ["mas", "api", "--dev"]
    app()
