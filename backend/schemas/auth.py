from pydantic import BaseModel, EmailStr, field_validator


class SetupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) < 3 or len(v) > 80:
            raise ValueError("Username must be 3-80 characters")
        if not v.isalnum() and "_" not in v:
            raise ValueError("Username must be alphanumeric or underscore")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        # Applies to the single admin account created at setup (and to
        # password changes). Length does most of the work; the character-class
        # check rules out the trivially weak 8-char cases. Deliberately not
        # stricter than this — composition rules past a point push people to
        # predictable substitutions.
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        classes = sum(
            (
                any(c.islower() for c in v),
                any(c.isupper() for c in v),
                any(c.isdigit() for c in v),
                any(not c.isalnum() for c in v),
            )
        )
        if classes < 3:
            raise ValueError(
                "Password must include at least three of: lowercase, "
                "uppercase, digit, symbol"
            )
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    status: str
    message: str


class UserInfo(BaseModel):
    username: str
    email: str
    is_admin: bool
    broker: str | None = None
    broker_authenticated: bool = False
