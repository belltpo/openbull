from pydantic import model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Core secrets
    app_secret_key: str
    encryption_pepper: str
    # Optional dedicated key material for Fernet (broker tokens, API keys,
    # api_secret). When empty, the Fernet key is derived from
    # ENCRYPTION_PEPPER exactly as before, so existing installs are
    # unaffected. Setting it stops one leaked value from compromising both
    # the password pepper and all stored broker credentials — see
    # backend.security for the MultiFernet migration path.
    encryption_secret: str = ""

    # Database. No credentials in the default: a guessable fallback password
    # is a real credential the moment someone deploys without setting
    # DATABASE_URL. Missing/invalid values now fail loudly at startup
    # instead of silently trying postgres/123456.
    database_url: str = ""

    # Server
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    frontend_url: str = "http://127.0.0.1:5173"
    # flask_debug was dead config — there is no Flask in this project and
    # nothing read the value, so a stray FLASK_DEBUG=true in a .env looked
    # like a live debug switch while doing nothing. Removed; `extra: ignore`
    # means an existing .env that still sets it keeps loading fine.

    # CORS
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    # Brokers
    valid_brokers: str = "upstox,zerodha"

    # Logging
    log_level: str = "INFO"
    log_to_file: bool = True
    log_dir: str = "logs"
    log_colors: bool = True
    # File rotation. Total on-disk footprint per log file is bounded by
    # (backup_count + 1) * max_mb. Defaults give a 100 MB hard cap per file
    # (openbull.log and openbull-error.log each), 200 MB total on disk.
    log_file_max_mb: int = 10
    log_file_backup_count: int = 9
    # DB-backed error sink. Worker trims the `error_logs` table down to this
    # many rows after every batch of inserts, bounding table growth.
    error_log_db_max_rows: int = 50000
    # DB-backed API request log. Stores one row per *authenticated* request;
    # worker trims to this row count so attacker floods cannot blow up the
    # table (they also get skipped at the middleware because they never pass
    # auth). At ~2 KB/row this caps the table around 200 MB.
    api_log_db_max_rows: int = 100000

    # Rate limits
    login_rate_limit_min: str = "5 per minute"
    login_rate_limit_hour: str = "25 per hour"
    api_rate_limit: str = "50 per second"
    order_rate_limit: str = "10 per second"

    # Session
    session_expiry_time: str = "03:00"
    # Secure flag on the session cookie. Defaults to True so a production
    # install that never sets COOKIE_SECURE is safe by default; local
    # http://127.0.0.1 dev must set COOKIE_SECURE=false explicitly (see
    # .env.example), otherwise the browser will not send the cookie over
    # plain HTTP.
    cookie_secure: bool = True

    # Reverse-proxy trust. X-Forwarded-For / X-Real-IP are only honoured when
    # the immediate peer is one of these, because a client can put anything
    # in those headers and nginx's $proxy_add_x_forwarded_for *appends* to
    # whatever arrived. Without this check the leftmost XFF entry — fully
    # attacker-controlled — was used for the webhook IP allow-list and for
    # the client_ip recorded in api_logs. Empty disables XFF entirely.
    trusted_proxy_ips: str = "127.0.0.1,::1"

    # Host header allow-list for TrustedHostMiddleware. Empty = allow any
    # (dev). Production installs should set this to the serving domain so a
    # forged Host cannot be reflected into absolute URLs.
    allowed_hosts: str = ""

    # Retention for sm_webhook_event. The webhook endpoint is unauthenticated
    # by design (the URL token is the credential) and records one row per
    # request including rejections, so without a cap an anonymous flood grows
    # the table without bound.
    webhook_event_max_rows: int = 50000

    # WebSocket Proxy
    websocket_host: str = "127.0.0.1"
    websocket_port: int = 8765
    websocket_url: str = "ws://127.0.0.1:8765"
    zmq_host: str = "127.0.0.1"
    zmq_port: int = 5555

    # Redis (cache backend)
    redis_url: str = "redis://127.0.0.1:6379/0"

    # WebSocket Connection Pooling
    max_symbols_per_websocket: int = 1000
    max_websocket_connections: int = 3
    enable_connection_pooling: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_proxy_ip_list(self) -> list[str]:
        return [p.strip() for p in self.trusted_proxy_ips.split(",") if p.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def valid_broker_list(self) -> list[str]:
        return [b.strip() for b in self.valid_brokers.split(",") if b.strip()]

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg")

    @model_validator(mode="after")
    def _require_database_url(self) -> "Settings":
        if not self.database_url.strip():
            raise ValueError(
                "DATABASE_URL is not set. Add it to .env, e.g.\n"
                "  DATABASE_URL = "
                '"postgresql+asyncpg://openbull:<password>@127.0.0.1:5432/openbull"\n'
                "There is deliberately no built-in default — the old fallback "
                "shipped a guessable password."
            )
        return self

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
