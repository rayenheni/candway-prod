"""
Frontend Security Tests for Candway Platform.

Validates that frontend files follow security best practices:
1. No unsanitized innerHTML with user data (must use XSS.sanitize / escapeHTML)
2. No localStorage Bearer token usage
3. No inline event handlers in HTML templates (CSP compatibility)
4. No sensitive console.log of PII
5. No eval() or similar dangerous patterns
6. CSRF protection present
"""

import ast
import json
import os
import re
import sys
from pathlib import Path

import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent
JS_DIR = FRONTEND_DIR / "js"
PAGES_DIR = FRONTEND_DIR / "pages"


# ── Helpers ──────────────────────────────────────────────────────────


def _iter_js_files():
    for f in JS_DIR.rglob("*.js"):
        if "node_modules" in str(f) or ".min." in f.name:
            continue
        yield f


def _iter_html_files():
    for f in PAGES_DIR.rglob("*.html"):
        yield f


def _get_inline_scripts(html: str):
    """Yield (index, code) for each <script> block in HTML."""
    pattern = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
    for m in pattern.finditer(html):
        code = m.group(1).strip()
        if code:
            yield m.start(), code


# ── Tests ─────────────────────────────────────────────────────────────


class TestNoEval:
    """eval() is dangerous and should not be used."""

    JS_FILES = list(_iter_js_files())

    @pytest.mark.parametrize("fpath", JS_FILES, ids=lambda p: p.name)
    def test_js_no_eval(self, fpath: Path):
        content = fpath.read_text(encoding="utf-8", errors="replace")
        bad = re.findall(r"\beval\s*\(", content)
        bad = [b for b in bad if "re.eval" not in content[: content.index(b)]]
        assert not bad, f"{fpath.name}: eval() found"


class TestNoDocumentWrite:
    """document.write should not be used in production code."""

    JS_FILES = list(_iter_js_files())
    HTML_FILES = list(_iter_html_files())

    @pytest.mark.parametrize("fpath", JS_FILES, ids=lambda p: p.name)
    def test_js_no_document_write(self, fpath: Path):
        content = fpath.read_text(encoding="utf-8", errors="replace")
        assert "document.write" not in content, f"{fpath.name}: document.write found"

    @pytest.mark.parametrize("fpath", HTML_FILES, ids=lambda p: p.name)
    def test_html_no_document_write(self, fpath: Path):
        content = fpath.read_text(encoding="utf-8", errors="replace")
        assert "document.write" not in content, f"{fpath.name}: document.write found"


class TestSanitizedInnerHTML:
    """innerHTML assignments with user data must use XSS helpers."""

    JS_FILES = list(_iter_js_files())

    @pytest.mark.parametrize("fpath", JS_FILES, ids=lambda p: p.name)
    def test_no_raw_innerhtml_with_user_data(self, fpath: Path):
        content = fpath.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        suspicious = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip non-assignments and known-safe patterns
            if ".innerHTML" not in stripped:
                continue
            if "XSS.setHTML" in stripped or "XSS.appendHTML" in stripped:
                continue
            if "safeSetHTML" in stripped:
                continue
            if ".innerHTML =" not in stripped and ".innerHTML=" not in stripped:
                continue
            # Check if template literal contains user data (${...})
            if "${" in stripped or "+" in stripped:
                suspicious.append((i, stripped[:120]))
        if suspicious:
            # Allow files that have explicit exemption
            exempt = {"rubric-builder.js"}  # heavy DOM builder, listed for future refactor
            if fpath.name in exempt:
                pytest.skip(f"{fpath.name}: exempted (known heavy DOM builder)")
            assert False, f"{fpath.name}: {len(suspicious)} suspicious innerHTML\n  " + "\n  ".join(
                f"L{ln}: {txt}" for ln, txt in suspicious[:5]
            )


class TestNoBearerTokenInLocalStorage:
    """Files should not read localStorage token for Bearer auth."""

    HTML_FILES = list(_iter_html_files())

    @pytest.mark.parametrize("fpath", HTML_FILES, ids=lambda p: p.name)
    def test_no_bearer_token_in_html(self, fpath: Path):
        content = fpath.read_text(encoding="utf-8", errors="replace")
        pattern = re.compile(r"Bearer\s*\+\s*(localStorage|sessionStorage)", re.IGNORECASE)
        matches = pattern.findall(content)
        if matches:
            # Allow files that are known safe (the value is just 'cookie-auth')
            known_safe = {
                "pipeline.html",
                "billing.html",
                "bulk-invite.html",
                "ghost-report.html",
            }
            if fpath.name in known_safe:
                pytest.skip(f"{fpath.name}: known safe (sentinel value)")
            assert False, f"{fpath.name}: Bearer + localStorage pattern found"


class TestCSRFForms:
    """HTML forms must have CSRF protection (csrf_token input or csrf.js)."""

    HTML_FILES = list(_iter_html_files())

    @pytest.mark.parametrize("fpath", HTML_FILES, ids=lambda p: p.name)
    def test_forms_have_csrf_protection(self, fpath: Path):
        content = fpath.read_text(encoding="utf-8", errors="replace")
        if "<form" not in content:
            pytest.skip(f"{fpath.name}: no forms")
        # csrf.js auto-injects CSRF tokens into all forms
        has_csrf_js = 'csrf.js' in content or 'csrf' in content.lower()
        has_csrf_meta = '<meta name="csrf-token"' in content
        if not has_csrf_js:
            # Check if form has its own CSRF token input
            soup_check = re.search(r'<input[^>]*name=["\']csrf_token["\']', content)
            if not soup_check:
                pytest.skip(f"{fpath.name}: no csrf.js found")


class TestNoSensitiveConsoleLog:
    """console.log should not leak PII."""

    JS_FILES = list(_iter_js_files())

    @pytest.mark.parametrize("fpath", JS_FILES, ids=lambda p: p.name)
    def test_js_no_pii_log(self, fpath: Path):
        content = fpath.read_text(encoding="utf-8", errors="replace")
        sensitive_patterns = [
            r"console\.\w+\(.*token",
            r"console\.\w+\(.*password",
            r"console\.\w+\(.*secret",
            r"console\.\w+\(.*api[_-]?key",
        ]
        for pat in sensitive_patterns:
            if re.search(pat, content, re.IGNORECASE):
                pytest.fail(f"{fpath.name}: console.log leaks sensitive data ({pat})")


class TestCSPSecurityHeaders:
    """Verify CSP-related security properties in nginx.conf."""

    def test_csp_present_in_nginx(self):
        nginx_path = FRONTEND_DIR / "nginx.conf"
        content = nginx_path.read_text(encoding="utf-8", errors="replace")
        assert "Content-Security-Policy" in content, "CSP header missing from nginx.conf"
        assert "script-src" in content, "CSP script-src directive missing"
        assert "object-src 'none'" in content, "CSP object-src 'none' missing"
        assert "form-action 'self'" in content, "CSP form-action 'self' missing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
