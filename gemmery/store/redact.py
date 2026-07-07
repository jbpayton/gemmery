"""Secrets never enter the store: high-precision credential patterns are
redacted at the capture boundary, before any blob is written.

Precision over recall by design — a memory system that redacts real prose is
worse than one that occasionally lets a low-entropy password through; the
patterns here are formats that are unambiguously credentials.
"""
from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern[bytes]]] = [
    ("aws-access-key", re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("private-key-block", re.compile(
        rb"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.S)),
    ("github-token", re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("anthropic-key", re.compile(rb"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("openai-key", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b")),
    ("slack-token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google-api-key", re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("jwt", re.compile(rb"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("bearer-header", re.compile(rb"(?i)\bauthorization:\s*bearer\s+[A-Za-z0-9._~+/-]{16,}={0,2}")),
]


def redact(data: bytes) -> tuple[bytes, list[str]]:
    """Return (clean_bytes, [pattern names hit]). Idempotent on clean input."""
    hits: list[str] = []
    for name, pat in _PATTERNS:
        if pat.search(data):
            hits.append(name)
            data = pat.sub(b"[REDACTED:" + name.encode() + b"]", data)
    return data, hits
