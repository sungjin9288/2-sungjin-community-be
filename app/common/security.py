
import hashlib
import hmac
import os

_ITERATIONS = 200_000
_ALGO = "sha256"
_SALT_BYTES = 16


def hash_password(password: str) -> str:

    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, password_hash: str) -> bool:

    try:
        scheme, iters, salt_hex, hash_hex = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False

        iterations = int(iters)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)

        dk = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False