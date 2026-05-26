"""Service-layer wrapper over the B2 connectivity probe.

Keeps the runtime layer free of direct repo imports.
"""

from app.repo import b2_client


def check_b2() -> bool:
    """Cheap reachability probe — never raises."""
    return b2_client.check_connectivity()
