"""``python -m watermark`` — the module entry point.

Mirrors the ``watermark`` console script (``watermark.cli:app``) so in-process callers that
only hold an interpreter — notably ``watermark catalog run`` spawning producer subprocesses
via ``sys.executable -m watermark`` (#1021) — reach the same CLI without needing the script
on ``PATH``.
"""

from __future__ import annotations

from watermark.cli import app

if __name__ == "__main__":
    app()
