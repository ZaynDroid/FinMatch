"""
Tests for user and admin authentication, registration, password hashing, and role checks.
"""

import pytest
from backend.auth import hash_password, verify_password
from backend.service import ReconciliationService


def test_password_hashing():
    pwd = "secret_password_123"
    h1, salt1 = hash_password(pwd)
    h2, salt2 = hash_password(pwd)

    # Different salts produce different hashes
    assert salt1 != salt2
    assert h1 != h2

    # Verification succeeds with corresponding salt
    assert verify_password(pwd, h1, salt1) is True
    assert verify_password(pwd, h2, salt2) is True
    assert verify_password("wrong_password", h1, salt1) is False


def test_default_seeded_accounts(in_memory_service: ReconciliationService):
    svc = in_memory_service
    # Test default admin login
    admin = svc.login("admin@finmatch.demo", "admin123", role="admin")
    assert admin.role == "admin"
    assert admin.email == "admin@finmatch.demo"
    assert admin.business_name == "FinMatch Administration"

    # Test default user login by email
    user_email = svc.login("user@finmatch.demo", "demo123", role="user")
    assert user_email.role == "user"
    assert user_email.business_name == "Sharma Traders"

    # Test default user login by 10-digit mobile number
    user_mobile = svc.login("9876543210", "demo123", role="user")
    assert user_mobile.user_id == user_email.user_id
    assert user_mobile.mobile == "9876543210"


def test_register_new_business(in_memory_service: ReconciliationService):
    svc = in_memory_service
    new_biz = svc.register_business(
        business_name="Himalayan Organics",
        owner_name="Deepak Joshi",
        email="deepak@himalayan.com",
        mobile="9800012345",
        password="securepass999",
        role="user",
    )
    assert new_biz.user_id.startswith("USR-")
    assert new_biz.business_name == "Himalayan Organics"
    assert new_biz.status == "Active"

    # Login with new account via email
    logged_in_email = svc.login("deepak@himalayan.com", "securepass999")
    assert logged_in_email.user_id == new_biz.user_id

    # Login with new account via mobile
    logged_in_mob = svc.login("9800012345", "securepass999")
    assert logged_in_mob.user_id == new_biz.user_id


def test_register_duplicate_email_fails(in_memory_service: ReconciliationService):
    svc = in_memory_service
    with pytest.raises(ValueError, match="already registered"):
        svc.register_business(
            business_name="Another Traders",
            owner_name="Someone",
            email="user@finmatch.demo",  # Already exists
            mobile="9811199999",
            password="password123",
        )


def test_register_duplicate_mobile_fails(in_memory_service: ReconciliationService):
    svc = in_memory_service
    with pytest.raises(ValueError, match="already registered"):
        svc.register_business(
            business_name="Unique Biz",
            owner_name="Someone",
            email="unique_email@test.com",
            mobile="9876543210",  # Already used by default demo user
            password="password123",
        )


def test_invalid_registration_fields(in_memory_service: ReconciliationService):
    svc = in_memory_service
    # Invalid mobile (not 10 digits)
    with pytest.raises(ValueError, match="must be exactly 10 digits"):
        svc.register_business("Biz", "Owner", "biz@test.com", "12345", "pass123")

    # Invalid email format
    with pytest.raises(ValueError, match="Invalid email address"):
        svc.register_business("Biz", "Owner", "not-an-email", "9800011111", "pass123")

    # Password too short
    with pytest.raises(ValueError, match="at least 4 characters"):
        svc.register_business("Biz", "Owner", "biz@test.com", "9800011111", "ab")


def test_login_incorrect_password(in_memory_service: ReconciliationService):
    svc = in_memory_service
    with pytest.raises(ValueError, match="Incorrect password"):
        svc.login("user@finmatch.demo", "wrong_password")


def test_login_unauthorized_role(in_memory_service: ReconciliationService):
    svc = in_memory_service
    # User trying to log in with role='admin'
    with pytest.raises(ValueError, match="not authorized as 'admin'"):
        svc.login("user@finmatch.demo", "demo123", role="admin")


def test_disabled_account_cannot_login(in_memory_service: ReconciliationService):
    svc = in_memory_service
    # Disable user
    user = svc.repo.get_user_by_email("user@finmatch.demo")
    assert user is not None
    svc.set_business_status(user.user_id, "Disabled")

    with pytest.raises(ValueError, match="account is disabled"):
        svc.login("user@finmatch.demo", "demo123")
