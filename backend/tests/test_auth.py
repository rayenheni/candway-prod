"""
Authentication Tests
Tests for user registration, login, and token validation
"""

from fastapi import status


class TestUserRegistration:
    """Test user registration endpoints"""

    def test_register_candidate_success(self, client):
        """Test successful candidate registration"""
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "name": "New User",
                "role": "candidate",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "candidate"

    def test_register_duplicate_email(self, client, test_user):
        """Test registration with existing email fails"""
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "test@example.com",  # Already exists
                "password": "SecurePass123!",
                "name": "Duplicate User",
                "role": "candidate",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already registered" in response.json()["detail"].lower()

    def test_register_weak_password(self, client):
        """Test registration with weak password fails"""
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "weakpass@example.com",
                "password": "123",  # Too weak
                "name": "Weak Password User",
                "role": "candidate",
            },
        )

        # Should fail validation
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    def test_register_invalid_email(self, client):
        """Test registration with invalid email format"""
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "not-an-email",
                "password": "SecurePass123!",
                "name": "Invalid Email User",
                "role": "candidate",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestUserLogin:
    """Test user login endpoints"""

    def test_login_success(self, client, test_user):
        """Test successful login"""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "testpassword123"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "candidate"

    def test_login_wrong_password(self, client, test_user):
        """Test login with incorrect password"""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent email"""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "anypassword"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_missing_credentials(self, client):
        """Test login with missing credentials"""
        response = client.post("/api/v1/auth/login", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestTokenValidation:
    """Test JWT token validation"""

    def test_access_protected_route_with_valid_token(self, client, auth_headers):
        """Test accessing protected route with valid token"""
        response = client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get("email") == "test@example.com" or data.get("profile", {}).get("email") == "test@example.com"

    def test_access_protected_route_without_token(self, client):
        """Test accessing protected route without token"""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_access_protected_route_with_invalid_token(self, client):
        """Test accessing protected route with invalid token"""
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer invalid_token_here"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_contains_user_info(self, client, auth_headers):
        """Test that token contains correct user information"""
        response = client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert "role" in data
        assert data["role"] == "candidate"


class TestRoleBasedAccess:
    """Test role-based access control"""

    def test_candidate_cannot_access_recruiter_routes(self, client, auth_headers):
        """Test that candidates cannot access recruiter-only routes"""
        response = client.get("/api/v1/recruiter/stats", headers=auth_headers)

        # Should be forbidden or unauthorized
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
        ]

    def test_recruiter_can_access_recruiter_routes(self, client, recruiter_headers):
        """Test that recruiters can access recruiter routes"""
        response = client.get("/api/v1/recruiter/stats", headers=recruiter_headers)

        # Should succeed
        assert response.status_code == status.HTTP_200_OK


class TestPasswordSecurity:
    """Test password security measures"""

    def test_password_is_hashed(self, db_session, test_user):
        """Test that passwords are stored hashed, not in plaintext"""
        # Password should not be stored in plaintext
        assert test_user.hashed_password != "testpassword123"
        # Should be a pbkdf2_sha256 hash (starts with $pbkdf2-sha256$)
        assert test_user.hashed_password.startswith(
            "$2b$"
        ) or test_user.hashed_password.startswith("$pbkdf2")

    def test_password_not_returned_in_response(self, client, auth_headers):
        """Test that password is never returned in API responses"""
        response = client.get("/api/v1/auth/me", headers=auth_headers)

        data = response.json()
        assert "password" not in data
        assert "hashed_password" not in data


class TestEmailVerification:
    """Test link-based email verification + resend (org-created members)."""

    def _create_unverified_user(self, db_session):
        from backend.database import User
        from backend.dependencies import pwd_context

        user = User(
            email="verifyme@test.tn",
            name="Verify Me",
            hashed_password=pwd_context.hash("testpassword123"),
            role="recruiter",
            email_verified=False,
        )
        db_session.add(user)
        db_session.flush()
        return user

    def _create_verification(self, db_session, user_id, token="tok123"):
        from datetime import UTC, datetime, timedelta
        from backend.database import EmailVerification

        ev = EmailVerification(
            user_id=user_id,
            token=token,
            code=None,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        db_session.add(ev)
        db_session.commit()
        return ev

    def test_verify_email_valid_token(self, client, db_session):
        user = self._create_unverified_user(db_session)
        self._create_verification(db_session, user.id)
        resp = client.get("/api/v1/auth/verify-email/tok123")
        assert resp.status_code == 200, resp.text
        assert "verified successfully" in resp.json()["message"]
        db_session.refresh(user)
        assert user.email_verified is True

    def test_verify_email_already_used(self, client, db_session):
        user = self._create_unverified_user(db_session)
        self._create_verification(db_session, user.id)
        resp1 = client.get("/api/v1/auth/verify-email/tok123")
        assert resp1.status_code == 200
        # Reusing the same token must fail (already verified).
        resp2 = client.get("/api/v1/auth/verify-email/tok123")
        assert resp2.status_code == 400

    def test_verify_email_expired(self, client, db_session):
        from datetime import UTC, datetime, timedelta
        from backend.database import EmailVerification

        user = self._create_unverified_user(db_session)
        self._create_verification(db_session, user.id)
        ev = db_session.query(EmailVerification).filter_by(token="tok123").first()
        ev.expires_at = datetime.now(UTC) - timedelta(hours=1)
        db_session.commit()
        resp = client.get("/api/v1/auth/verify-email/tok123")
        assert resp.status_code == 400
        assert "Invalid or expired" in resp.json()["detail"]

    def test_resend_verification_link(self, client, db_session):
        from datetime import UTC, datetime, timedelta
        from backend.database import EmailVerification

        user = self._create_unverified_user(db_session)
        # Old (expired) token so the 60s resend cooldown does not fire.
        db_session.add(
            EmailVerification(
                user_id=user.id,
                token="old-token",
                code=None,
                expires_at=datetime.now(UTC) - timedelta(hours=25),
            )
        )
        db_session.commit()
        resp = client.post(
            "/api/v1/auth/resend-verification", json={"email": user.email}
        )
        assert resp.status_code == 200, resp.text
        assert "Verification link sent" in resp.json()["message"]
        # A fresh token row must exist.
        evs = (
            db_session.query(EmailVerification)
            .filter_by(user_id=user.id)
            .order_by(EmailVerification.id.desc())
            .all()
        )
        assert len(evs) == 2
        assert evs[0].token != "old-token"

    def test_resend_verification_verified_user_rejected(self, client, db_session):
        user = self._create_unverified_user(db_session)
        user.email_verified = True
        db_session.commit()
        resp = client.post(
            "/api/v1/auth/resend-verification", json={"email": user.email}
        )
        assert resp.status_code == 409

    def test_resend_verification_unknown_email(self, client):
        resp = client.post(
            "/api/v1/auth/resend-verification", json={"email": "nobody@test.tn"}
        )
        assert resp.status_code == 404


class TestCorsAndDomainArchitecture:
    """Test CORS, headers, and domain architecture requirements."""

    def test_cors_preflight_candidate_origin(self, client):
        """Verify candway.com origin is allowed with credentials.

        Access-Control-Expose-Headers is only present on actual (non-preflight)
        responses per the CORS spec, so we check it on a real GET request.
        The preflight check still validates that candway.com is an allowed origin.
        """
        # 1. Check preflight allows the origin with credentials
        preflight_headers = {
            "Origin": "https://candway.com",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "Content-Type, X-CSRF-Token",
        }
        preflight = client.options("/api/v1/candidate/profile", headers=preflight_headers)
        assert preflight.status_code == 200
        assert preflight.headers.get("access-control-allow-origin") == "https://candway.com"
        assert preflight.headers.get("access-control-allow-credentials") == "true"

        # 2. Expose-headers only appears on actual responses (not preflight)
        actual = client.get(
            "/api/v1/auth/me",
            headers={"Origin": "https://candway.com"},
        )
        exposed = actual.headers.get("access-control-expose-headers", "")
        assert "x-csrf-token" in exposed.lower()

    def test_cors_preflight_app_origin(self, client):
        """Verify app.candway.com CORS preflight succeeds."""
        headers = {
            "Origin": "https://app.candway.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
        resp = client.options("/api/v1/auth/login", headers=headers)
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "https://app.candway.com"
        assert resp.headers.get("access-control-allow-credentials") == "true"

    def test_host_only_auth_cookies(self, client, test_user):
        """Verify auth cookies are set without a shared parent domain attribute."""
        # Password matches pwd_context.hash("testpassword123") in conftest test_user fixture
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "testpassword123"},
        )
        assert resp.status_code == 200
        cookie_header = resp.headers.get("set-cookie", "")
        # Must not set a parent domain cookie like domain=.candway.com
        assert "domain=.candway.com" not in cookie_header.lower()
