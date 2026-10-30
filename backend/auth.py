"""
Authentication and User Account Management for FinMatch.
Provides salted password hashing, user/admin authentication, and registration.
"""

from __future__ import annotations
import hashlib
import hmac
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

EMAIL_RE = re.compile(r"^[\w\.\+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\.\-]+$")
MOBILE_RE = re.compile(r"^\d{10}$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Produce a secure salted SHA-256 hash using PBKDF2 with 100,000 iterations.
    Returns (hex_hash, salt_hex).
    """
    if not salt:
        salt = os.urandom(16).hex()
    pwd_bytes = password.encode("utf-8")
    salt_bytes = salt.encode("utf-8")
    derived = hashlib.pbkdf2_hmac("sha256", pwd_bytes, salt_bytes, iterations=100_000)
    return derived.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Safely verify password against stored PBKDF2 hash using constant-time comparison."""
    computed_hash, _ = hash_password(password, salt=salt)
    return hmac.compare_digest(computed_hash, stored_hash)


@dataclass
class UserAccount:
    user_id: str
    email: str
    mobile: str
    business_name: str
    owner_name: str
    password_hash: str
    password_salt: str
    role: str = "user"  # 'user' or 'admin'
    status: str = "Active"  # 'Active' or 'Disabled'
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        data = {
            "user_id": self.user_id,
            "email": self.email,
            "mobile": self.mobile,
            "business_name": self.business_name,
            "owner_name": self.owner_name,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_sensitive:
            data["password_hash"] = self.password_hash
            data["password_salt"] = self.password_salt
        return data


class AuthManager:
    """Manages user registration, credential validation, and login authentication."""

    @staticmethod
    def validate_registration_inputs(
        business_name: str,
        owner_name: str,
        email: str,
        mobile: str,
        password: str,
    ) -> None:
        """Validate all required registration fields."""
        if not business_name or not business_name.strip():
            raise ValueError("Business name is required.")
        if not owner_name or not owner_name.strip():
            raise ValueError("Owner name is required.")
        if not email or not email.strip():
            raise ValueError("Email address is required.")
        if not EMAIL_RE.match(email.strip()):
            raise ValueError(f"Invalid email address format: '{email}'.")
        if not mobile or not mobile.strip():
            raise ValueError("Mobile number is required.")
        
        clean_mobile = mobile.strip().replace(" ", "").replace("-", "")
        if not MOBILE_RE.match(clean_mobile):
            raise ValueError(f"Mobile number must be exactly 10 digits, got '{mobile}'.")
        
        if not password or len(password) < 4:
            raise ValueError("Password must be at least 4 characters long.")

    @staticmethod
    def create_user_account(
        business_name: str,
        owner_name: str,
        email: str,
        mobile: str,
        password: str,
        role: str = "user",
        user_id: Optional[str] = None,
    ) -> UserAccount:
        """Construct a new UserAccount with salted password hash."""
        AuthManager.validate_registration_inputs(
            business_name=business_name,
            owner_name=owner_name,
            email=email,
            mobile=mobile,
            password=password,
        )

        clean_email = email.strip().lower()
        clean_mobile = mobile.strip().replace(" ", "").replace("-", "")
        pwd_hash, salt = hash_password(password)

        uid = user_id or f"{'ADM' if role == 'admin' else 'USR'}-{uuid.uuid4().hex[:8].upper()}"

        return UserAccount(
            user_id=uid,
            email=clean_email,
            mobile=clean_mobile,
            business_name=business_name.strip(),
            owner_name=owner_name.strip(),
            password_hash=pwd_hash,
            password_salt=salt,
            role=role.lower(),
            status="Active",
            created_at=_utc_now(),
        )
