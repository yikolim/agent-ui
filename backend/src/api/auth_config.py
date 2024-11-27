# Create or update auth_config.py
from passlib.context import CryptContext
from typing import Optional, Dict
import hashlib
import os

class SimpleHash:
    @staticmethod
    def hash(password: str) -> str:
        salt = os.urandom(16).hex()
        hashed = hashlib.sha256((salt + password).encode()).hexdigest()
        return f"{salt}:{hashed}"
    
    @staticmethod
    def verify(password: str, hash_string: str) -> bool:
        try:
            salt, stored_hash = hash_string.split(':')
            computed_hash = hashlib.sha256((salt + password).encode()).hexdigest()
            return computed_hash == stored_hash
        except:
            return False

USERS = {
    "admin": {
        "password": SimpleHash.hash("Yiko0816!"),
        "permissions": ["read", "write", "execute"]
    },
    "user": {
        "password": SimpleHash.hash("Yiko0816!"),
        "permissions": ["read", "execute"]
    }
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return SimpleHash.verify(plain_password, hashed_password)

def get_user(username: str) -> dict:
    return USERS.get(username)

# # Create empty __init__.py
# touch src/api/__init__.py

# # Verify files exist
# ls -la src/api/