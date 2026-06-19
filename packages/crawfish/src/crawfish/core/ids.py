"""ID generation. Kept isolated so everything can import it without cycles."""

from __future__ import annotations

import uuid


def new_id() -> str:
    """A fresh opaque identifier for any framework object."""
    return str(uuid.uuid4())
