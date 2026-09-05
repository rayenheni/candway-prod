# Native production Nginx config

`candway.conf` is the source-of-truth for the **native** Nginx deployment
(Linux systemd host, not Docker).

Install it to the production host exactly as:

```bash
sudo cp deploy/nginx/candway.conf /etc/nginx/sites-enabled/candway.conf
sudo nginx -t
sudo systemctl reload nginx
```

Notes:

- The Docker-oriented root `nginx.conf` is a separate artifact for the
  containerized stack only and is NOT used by the native deployment.
- No credentials or private keys are stored in this file — SSL material is
  referenced from `/etc/letsencrypt/live/candway.com/…`.
- Backend FastAPI already emits `X-Frame-Options: SAMEORIGIN`; Nginx is
  aligned to the same value. Any duplicate-header behavior after deploy is
  handled separately, not by editing either layer silently.