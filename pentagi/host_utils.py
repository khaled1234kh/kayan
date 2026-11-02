"""Helper to extract host from a URL for TrustGate target matching."""

import re


def extract_host(target: str) -> str:
    """Extract hostname/IP from a URL or return as-is if already a host."""
    target = target.strip()
    # Remove protocol
    if "://" in target:
        target = target.split("://", 1)[1]
    # Remove path
    target = target.split("/", 1)[0]
    # Remove port
    if ":" in target:
        target = target.split(":")[0]
    return target
