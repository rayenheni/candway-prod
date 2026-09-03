
import requests
import sys
import os

BASE_URL = "http://localhost:8002/api/v1"

def test_privacy():
    admin_email = os.getenv("TEST_ADMIN_EMAIL", "admin@candway.io")
    admin_password = os.getenv("TEST_ADMIN_PASSWORD")
    if not admin_password:
        print("TEST_ADMIN_PASSWORD is required.")
        sys.exit(1)

    # 1. Login
    print("Logging in...")
    resp = requests.post(f"{BASE_URL}/user/login", data={
        "username": admin_email,
        "password": admin_password
    })
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        sys.exit(1)
        
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful.")

    # 2. Update Consent
    print("Testing POST /privacy/consent...")
    consent_data = {"marketing_consent": True, "data_processing_consent": True}
    resp = requests.post(f"{BASE_URL}/privacy/consent", json=consent_data, headers=headers)
    print(f"Update Consent Status: {resp.status_code}")
    print(resp.text)
    
    # 3. Export Data
    print("Testing GET /privacy/export-data...")
    resp = requests.get(f"{BASE_URL}/privacy/export-data", headers=headers)
    print(f"Export Data Status: {resp.status_code}")
    if resp.status_code == 200:
        print("Export successful (Preview first 100 chars):")
        print(resp.text[:100])
    else:
        print(resp.text)

if __name__ == "__main__":
    test_privacy()
