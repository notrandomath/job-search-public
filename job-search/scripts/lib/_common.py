"""Shared helpers so every script behaves the same on macOS, Linux, and Windows.

- setup_stdio(): force UTF-8 stdout/stderr (Windows consoles default to a legacy codepage
  and crash on non-ASCII job titles or symbols).
- open_url(): urlopen with certificate verification ON. If the local certificate store is
  broken (common with python.org builds on macOS), retry once without verification and warn.
  Responses are public job pages; no credentials are ever sent.
"""
import ssl
import sys
import urllib.error
import urllib.request

_warned = False


def setup_stdio():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_ctx_cache = {}


def _verified_context():
    if "v" not in _ctx_cache:
        _ctx_cache["v"] = _build_verified_context()
    return _ctx_cache["v"]


def _build_verified_context():
    try:
        import certifi  # optional
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _unverified_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def open_url(req, timeout=15):
    """urlopen(req) with verified TLS first, unverified fallback only on certificate errors."""
    global _warned
    try:
        return urllib.request.urlopen(req, context=_verified_context(), timeout=timeout)
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(e):
            if not _warned:
                sys.stderr.write("warning: TLS certificate store unavailable; retrying without verification "
                                 "(public pages only). Install certifi to fix.\n")
                _warned = True
            return urllib.request.urlopen(req, context=_unverified_context(), timeout=timeout)
        raise
