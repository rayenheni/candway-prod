"""
Native production Nginx config tests.

Verifies the source-of-truth for the systemd/native production Nginx
(`deploy/nginx/candway.conf`, installed to
`/etc/nginx/sites-enabled/candway.conf`) keeps its invariants:

1. The native Candway config file exists and is not the Docker-oriented
   root `nginx.conf`.
2. Exactly two `X-Frame-Options` directives exist (landing + application).
3. Both are ``SAMEORIGIN`` (aligned with the backend's own header) and no
   ``DENY`` remains.
4. Required production directives (rate limit, upstream, server names,
   SSL, API/WebSocket/uploads/admin proxy, SPA fallback) remain intact.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NATIVE_NGINX = REPO_ROOT / "deploy" / "nginx" / "candway.conf"


def _native_config() -> str:
    assert NATIVE_NGINX.exists(), f"native config missing: {NATIVE_NGINX}"
    return NATIVE_NGINX.read_text(encoding="utf-8")


def test_native_candway_config_exists():
    assert NATIVE_NGINX.is_file()


def test_native_config_is_not_the_docker_nginx_conf():
    docker_conf = REPO_ROOT / "nginx.conf"
    assert NATIVE_NGINX.resolve() != docker_conf.resolve()


def test_exactly_two_x_frame_options_directives():
    content = _native_config()
    directives = re.findall(r'add_header\s+X-Frame-Options\s+"[^"]+"\s+always;', content)
    assert len(directives) == 2, f"expected 2 X-Frame-Options, got {len(directives)}"


def test_both_x_frame_options_are_sameorigin():
    content = _native_config()
    sameorigin = re.findall(r'add_header\s+X-Frame-Options\s+"SAMEORIGIN"\s+always;', content)
    assert len(sameorigin) == 2


def test_no_x_frame_options_deny_remains():
    content = _native_config()
    deny = re.findall(r'add_header\s+X-Frame-Options\s+"DENY"\s+always;', content)
    assert deny == []


def test_required_directives_preserved():
    content = _native_config()
    assert 'limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;' in content
    assert 'upstream candway_backend {' in content
    assert 'server 127.0.0.1:8000 max_fails=3 fail_timeout=10s;' in content
    assert 'server_name candway.com www.candway.com;' in content
    assert 'server_name app.candway.com;' in content
    assert '/etc/letsencrypt/live/candway.com/fullchain.pem' in content
    assert '/etc/letsencrypt/options-ssl-nginx.conf' in content


def test_proxy_and_websocket_directives_preserved():
    content = _native_config()
    assert 'proxy_pass http://candway_backend;' in content
    assert 'proxy_set_header Upgrade $http_upgrade;' in content
    assert 'proxy_set_header Connection "upgrade";' in content
    assert 'proxy_read_timeout 86400s;' in content
    assert 'location /api/' in content
    assert 'location /ws/' in content
    assert 'location /uploads/' in content
    assert 'location /assets/' in content
    assert 'location ~ ^/admin(?:/|$)' in content
    assert 'try_files $uri $uri/ /index.html;' in content