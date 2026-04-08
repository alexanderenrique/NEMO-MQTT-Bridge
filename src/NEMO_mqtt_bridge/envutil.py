"""Small environment-variable helpers shared across bridge entrypoints."""

from __future__ import annotations

import os


def env_truthy(name: str) -> bool:
    """True if ``name`` is set to a common affirmative string (1, true, yes, on)."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")
