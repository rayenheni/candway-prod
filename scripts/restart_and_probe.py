"""
Start uvicorn in the background, wait for the server to be ready,
hit the admin /users endpoint with a freshly-issued admin token,
print the result, and exit.
"""
import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
import json

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv

load_dotenv()
SECRET = os.environ["SECRET_KEY"]

# Free port 8080 from any previous process.
subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue "
     "| ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }"],
    capture_output=True,
)
time.sleep(3)

# Spawn uvicorn.
log_out = open("server.out.log", "ab", buffering=0)
log_err = open("server.err.log", "ab", buffering=0)
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.app:app",
     "--host", "127.0.0.1", "--port", "8080", "--log-level", "info"],
    stdout=log_out,
    stderr=log_err,
    cwd=os.getcwd(),
)
print(f"spawned uvicorn pid={proc.pid}")
time.sleep(9)

# Issue admin JWT.
from backend.dependencies import create_access_token
import datetime

token = create_access_token({
    "sub": "rayenheni8@gmail.com",
    "id": 1,
    "role": "admin",
    "is_super_admin": True,
    "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
})
print(f"token issued: {token[:30]}...")

# Probe endpoint.
for path, label in [
    ("/api/v1/admin/users?role=all", "role=all"),
    ("/api/v1/admin/users?role=candidate", "role=candidate"),
    ("/api/v1/admin/users?role=recruiter", "role=recruiter"),
    ("/api/v1/admin/users?role=mentor", "role=mentor"),
    ("/api/v1/admin/users?role=admin", "role=admin"),
    ("/api/v1/admin/users", "no filter"),
]:
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:8080{path}",
            headers={"Authorization": f"Bearer {token}"},
        )
        r = urllib.request.urlopen(req, timeout=5)
        body = json.loads(r.read())
        print(f"  {r.status}  {label:15s}  total={body.get('total'):3}  users={len(body.get('users', []))}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:120]
        print(f"  {e.code}  {label:15s}  {body}")
    except Exception as e:
        print(f"  ERR  {label:15s}  {e}")

# Leave server running.
print(f"server still running pid={proc.pid}")
