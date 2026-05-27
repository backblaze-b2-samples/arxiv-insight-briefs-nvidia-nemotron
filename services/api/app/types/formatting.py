"""Shared formatting utilities used across layers."""


def humanize_bytes(size: int) -> str:
    """Render a byte count as a short human-readable string (e.g. 1.5 KB)."""
    s: float = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(s) < 1024:
            return f"{s:.1f} {unit}"
        s /= 1024
    return f"{s:.1f} PB"
