import httpx, json

c = httpx.Client(follow_redirects=True, timeout=120)

r = c.post("http://127.0.0.1:8003/api/v1/auth/login", json={"email":"test@candway.tn","password":"Test@2026!"})
print("login:", r.status_code)
token = r.json()["access_token"]

c.get("http://127.0.0.1:8003/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
csrf = None
for k, v in c.cookies.items():
    if k == "csrf_token":
        csrf = v

h = {"Authorization": "Bearer " + token}
if csrf:
    h["X-CSRF-Token"] = csrf

print("\nSending ready to app 114 (status=interviewing)...")
r2 = c.post("http://127.0.0.1:8003/api/v1/ai/interview/chat",
            headers=h,
            json={"candidate_id": 114, "message": "ready", "language": "English", "current_score": 0},
            timeout=120)
print("chat:", r2.status_code)
try:
    print(json.dumps(r2.json(), indent=2)[:3000])
except:
    print(r2.text[:3000])
