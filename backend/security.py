import hashlib
import base64
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import (
    Argon2Error,
    InvalidHashError,
    VerifyMismatchError,
)
from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import jwt
from jwt import PyJWTError

from backend.config import get_settings

settings = get_settings()

# -- Argon2 password hashing --

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    peppered = password + settings.encryption_pepper
    return _ph.hash(peppered)


def verify_password(password: str, password_hash: str) -> bool:
    peppered = password + settings.encryption_pepper
    try:
        return _ph.verify(password_hash, peppered)
    except VerifyMismatchError:
        return False
    except (Argon2Error, InvalidHashError):
        # Malformed / truncated stored hash. Note InvalidHashError subclasses
        # ValueError, not Argon2Error, so it must be named explicitly.
        # Treat as "does not match" instead of letting it surface as a 500 —
        # a corrupt row must not turn login into a server error.
        return False


def check_needs_rehash(password_hash: str) -> bool:
    return _ph.check_needs_rehash(password_hash)


# -- Fernet encryption (for tokens, broker secrets) --

def _derive_fernet_key(secret: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    key = kdf.derive(secret.encode())
    return base64.urlsafe_b64encode(key)


# Legacy key: derived from ENCRYPTION_PEPPER with the original salt and
# iteration count. It MUST stay exactly as it was — every broker token,
# API key and api_secret already in the database was encrypted with it, and
# changing any KDF input here would make all of that ciphertext
# undecryptable.
_LEGACY_SALT = b"openbull_static_salt"
_LEGACY_ITERATIONS = 100_000
_legacy_fernet = Fernet(
    _derive_fernet_key(settings.encryption_pepper, _LEGACY_SALT, _LEGACY_ITERATIONS)
)

# Optional dedicated encryption secret. ENCRYPTION_PEPPER is mixed into every
# Argon2 password/API-key hash, so using it as the Fernet key material too
# means one leaked value compromises both the password pepper and all stored
# broker credentials. Setting ENCRYPTION_SECRET splits those two roles.
#
# MultiFernet encrypts with the first key and decrypts with any of them, so
# turning this on is backwards compatible: existing rows still decrypt under
# the legacy key and are re-encrypted under the new one the next time they
# are written. Leaving it unset keeps the previous behaviour exactly.
if settings.encryption_secret:
    _fernet = MultiFernet([
        Fernet(_derive_fernet_key(settings.encryption_secret, b"openbull_fernet_v2", 600_000)),
        _legacy_fernet,
    ])
else:
    _fernet = _legacy_fernet


def encrypt_value(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()


# -- API key hashing (Argon2 for verification) --

def hash_api_key(api_key: str) -> str:
    peppered = api_key + settings.encryption_pepper
    return _ph.hash(peppered)


def verify_api_key(api_key: str, api_key_hash: str) -> bool:
    peppered = api_key + settings.encryption_pepper
    try:
        return _ph.verify(api_key_hash, peppered)
    except VerifyMismatchError:
        return False
    except (Argon2Error, InvalidHashError):
        return False


def api_key_lookup(api_key: str) -> str:
    """Cheap, indexable fingerprint of an API key.

    Argon2 is deliberately expensive (~64 MB and tens of ms per call), which
    made every *unauthenticated* request carrying a bogus key cost a full
    Argon2 verification. Callers now SELECT on this fingerprint first and
    only run Argon2 against the single row it returns, so a random key is
    rejected by an indexed lookup instead of a KDF.

    SHA-256 with no salt is deliberate and safe here: the input is
    ``secrets.token_hex(32)`` — 256 bits of entropy, not a guessable
    password — so there is nothing for a slow KDF to protect. The identical
    digest is already used as the Redis cache key, so this introduces no new
    exposure. Argon2 remains the authority on whether the key is correct.
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_api_key() -> str:
    return secrets.token_hex(32)


# -- JWT --

ALGORITHM = "HS256"


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default: expire at 3:00 AM IST next day
        now_utc = datetime.now(timezone.utc)
        ist_offset = timedelta(hours=5, minutes=30)
        now_ist = now_utc + ist_offset

        parts = settings.session_expiry_time.split(":")
        expiry_hour, expiry_min = int(parts[0]), int(parts[1])

        expiry_ist = now_ist.replace(hour=expiry_hour, minute=expiry_min, second=0, microsecond=0)
        if expiry_ist <= now_ist:
            expiry_ist += timedelta(days=1)

        expire = expiry_ist - ist_offset  # convert back to UTC

    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.app_secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM])
        return payload
    except PyJWTError:
        return None
