import httpx, json, time

c = httpx.Client(follow_redirects=True, timeout=120)
r = c.post("http://127.0.0.1:8003/api/v1/auth/login", json={"email": "rayenteck8@gmail.com", "password": "Test@2026!"})
token = r.json()["access_token"]
c.get("http://127.0.0.1:8003/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
csrf = None
for k, v in c.cookies.items():
    if k == "csrf_token":
        csrf = v
h = {"Authorization": "Bearer " + token}
if csrf:
    h["X-CSRF-Token"] = csrf

t0 = time.time()
r = c.post("http://127.0.0.1:8003/api/v1/ai/interview/chat",
           headers=h,
           json={"candidate_id": 121, "message": "ready", "language": "English", "current_score": 0},
           timeout=120)
print(f"Status: {r.status_code} ({time.time()-t0:.1f}s)")
print(json.dumps(r.json(), indent=2)[:2000] if r.status_code == 200 else r.text[:1000])
