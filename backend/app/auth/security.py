"""Password hashing (scrypt, stdlib), opaque session tokens, and TOTP
two-factor codes (RFC 6238, stdlib only — compatible with Google
Authenticator / Authy / 1Password).
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 16384, 8, 1

TOKEN_TTL_DAYS = 7


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex),
            n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(48)


# --- TOTP (RFC 6238, SHA-1, 6 digits, 30 s) --------------------------------

def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def totp_uri(secret: str, username: str) -> str:
    return (
        f"otpauth://totp/Codnixy%20AI%20Trade:{username}"
        f"?secret={secret}&issuer=Codnixy%20AI%20Trade&digits=6&period=30"
    )


def _totp_at(secret: str, counter: int) -> str:
    key = base64.b32decode(secret)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def verify_totp(secret: str, code: str, step: int = 30) -> bool:
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6 or not secret:
        return False
    counter = int(time.time() // step)
    return any(
        hmac.compare_digest(_totp_at(secret, counter + drift), code)
        for drift in (-1, 0, 1)  # tolerate ±30 s clock skew
    )
