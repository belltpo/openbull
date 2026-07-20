"""Run a disposable, source-accurate OpenBull documentation environment.

The helper derives its connection details from the developer's existing
configuration without printing them, but switches to a dedicated PostgreSQL
database. It refuses non-local database hosts. No real broker credential is
created: the optional seed uses a deliberately unsupported broker name so UI
guards can be documented without contacting a provider.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[2]
DOC_DATABASE = "openbull_documentation"
LOCAL_HOSTS = {None, "", "localhost", "127.0.0.1", "::1"}

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def documentation_url() -> str:
    from backend.config import get_settings

    original = make_url(get_settings().database_url)
    if original.host not in LOCAL_HOSTS:
        raise RuntimeError(
            "Documentation runtime refuses a non-local PostgreSQL host."
        )
    return original.set(database=DOC_DATABASE).render_as_string(hide_password=False)


def configure_environment() -> str:
    url = documentation_url()
    os.environ["DATABASE_URL"] = url
    os.environ["FRONTEND_URL"] = "http://127.0.0.1:5173"
    os.environ["CORS_ORIGINS"] = "http://127.0.0.1:5173,http://localhost:5173"
    os.environ["COOKIE_SECURE"] = "false"
    from backend.config import get_settings

    get_settings.cache_clear()
    return url


def maintenance_connection():
    import psycopg
    from backend.config import get_settings

    source = make_url(get_settings().database_url)
    if source.host not in LOCAL_HOSTS:
        raise RuntimeError("Refusing to create documentation database remotely.")
    maintenance = source.set(database="postgres", drivername="postgresql+psycopg")
    kwargs = {
        "host": maintenance.host or "localhost",
        "port": maintenance.port or 5432,
        "dbname": maintenance.database,
        "user": maintenance.username,
        "password": maintenance.password,
        "autocommit": True,
    }
    return psycopg.connect(**kwargs)


def create_database() -> None:
    from psycopg import sql

    with maintenance_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (DOC_DATABASE,)
        ).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DOC_DATABASE)))
        row = conn.execute(
            "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = %s",
            (DOC_DATABASE,),
        ).fetchone()
        if row and row[0] not in (None, "OpenBull documentation screenshot database"):
            raise RuntimeError("Refusing to mark an existing non-documentation database")
        if row and row[0] is None:
            conn.execute(
                sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                    sql.Identifier(DOC_DATABASE),
                    sql.Literal("OpenBull documentation screenshot database"),
                )
            )


def recreate_database() -> None:
    """Replace only a database previously marked as this tool's fixture."""
    from psycopg import sql

    with maintenance_connection() as conn:
        row = conn.execute(
            "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = %s",
            (DOC_DATABASE,),
        ).fetchone()
        if row is not None:
            if row[0] != "OpenBull documentation screenshot database":
                raise RuntimeError("Refusing to replace an unmarked database")
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (DOC_DATABASE,),
            )
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(DOC_DATABASE)))
    create_database()


def seed_documentation_fixture(username: str) -> None:
    """Create a sandbox-only UI fixture without contacting an external provider."""
    url = make_url(configure_environment()).set(drivername="postgresql+psycopg")
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from backend.models.auth import BrokerAuth
    from backend.models.broker_config import BrokerConfig
    from backend.models.settings import AppSettings, TRADING_MODE_KEY, TRADING_MODE_SANDBOX
    from backend.models.sandbox import (
        SandboxFund, SandboxHolding, SandboxOrder, SandboxPosition, SandboxTrade,
    )
    from backend.models.strategies import Strategy
    from backend.models.strategy_module import SmStrategy
    from backend.models.user import User
    from backend.security import encrypt_value

    engine = create_engine(url)
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.username == username))
        if user is None:
            raise RuntimeError(f"Documentation user {username!r} does not exist")
        broker_name = "documentation"
        cfg = session.scalar(
            select(BrokerConfig).where(
                BrokerConfig.user_id == user.id,
                BrokerConfig.broker_name == broker_name,
            )
        )
        if cfg is None:
            cfg = BrokerConfig(
                user_id=user.id,
                broker_name=broker_name,
                api_key=encrypt_value("documentation-only"),
                api_secret=encrypt_value("documentation-only"),
                redirect_url="http://127.0.0.1/documentation-only",
                is_active=True,
            )
            session.add(cfg)
        else:
            cfg.is_active = True
        auth = session.scalar(
            select(BrokerAuth).where(
                BrokerAuth.user_id == user.id,
                BrokerAuth.broker_name == broker_name,
            )
        )
        if auth is None:
            session.add(
                BrokerAuth(
                    user_id=user.id,
                    broker_name=broker_name,
                    access_token=encrypt_value("documentation-only"),
                    broker_user_id="documentation-only",
                    is_revoked=False,
                )
            )
        else:
            auth.is_revoked = False

        mode = session.scalar(select(AppSettings).where(AppSettings.key == TRADING_MODE_KEY))
        if mode is None:
            session.add(AppSettings(key=TRADING_MODE_KEY, value=TRADING_MODE_SANDBOX))
        else:
            mode.value = TRADING_MODE_SANDBOX

        strategy = session.scalar(
            select(SmStrategy).where(
                SmStrategy.user_id == user.id,
                SmStrategy.name == "Documentation NIFTY Spread",
            )
        )
        if strategy is None:
            token = "documentation-strategy-token"
            session.add(
                SmStrategy(
                    user_id=user.id,
                    name="Documentation NIFTY Spread",
                    strategy_kind="batch",
                    direction="both",
                    universe_tab="weekly_monthly",
                    underlying="NIFTY",
                    underlying_exchange="NSE_INDEX",
                    strategy_type="positional",
                    product="NRML",
                    pricetype="MARKET",
                    legs=[
                        {
                            "id": 1,
                            "segment": "options",
                            "expiry": "current_week",
                            "lots": 1,
                            "position": "B",
                            "option_type": "CE",
                            "strike_mode": "atm",
                            "atm_offset": "ATM",
                            "target_pts": 20,
                            "sl_pts": 10,
                            "trail": {"x": 0, "y": 0},
                            "momentum": None,
                        }
                    ],
                    overall_sl_mtm=1000,
                    overall_target_mtm=2000,
                    trail_sl_to_entry=False,
                    live_enabled=False,
                    webhook_token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    webhook_locked=False,
                    status="stopped",
                )
            )

        if session.scalar(select(SandboxOrder).where(SandboxOrder.orderid == "DOC-ORDER-001")) is None:
            session.add(
                SandboxOrder(
                    user_id=user.id, orderid="DOC-ORDER-001", symbol="NIFTY28JUL26FUT",
                    exchange="NFO", action="BUY", quantity=65, filled_quantity=0,
                    pricetype="LIMIT", product="MIS", price=24000.0, trigger_price=0.0,
                    average_price=0.0, status="open", strategy="Documentation fixture",
                    margin_blocked=0.0,
                )
            )
        if session.scalar(select(SandboxTrade).where(SandboxTrade.tradeid == "DOC-TRADE-001")) is None:
            session.add(
                SandboxTrade(
                    user_id=user.id, orderid="DOC-FILLED-001", tradeid="DOC-TRADE-001",
                    symbol="NIFTY28JUL26FUT", exchange="NFO", action="BUY", quantity=65,
                    average_price=24000.0, product="MIS", strategy="Documentation fixture",
                )
            )
        if session.scalar(
            select(SandboxPosition).where(
                SandboxPosition.user_id == user.id,
                SandboxPosition.symbol == "NIFTY28JUL26FUT",
                SandboxPosition.exchange == "NFO",
                SandboxPosition.product == "MIS",
            )
        ) is None:
            session.add(
                SandboxPosition(
                    user_id=user.id, symbol="NIFTY28JUL26FUT", exchange="NFO", product="MIS",
                    net_quantity=65, average_price=24000.0, ltp=24025.0, pnl=1625.0,
                    realized_pnl=0.0, today_realized_pnl=0.0, unrealized_pnl=1625.0,
                    margin_blocked=50000.0, day_buy_quantity=65, day_buy_value=1560000.0,
                    day_sell_quantity=0, day_sell_value=0.0,
                )
            )
        if session.scalar(
            select(SandboxHolding).where(
                SandboxHolding.user_id == user.id, SandboxHolding.symbol == "INFY",
                SandboxHolding.exchange == "NSE",
            )
        ) is None:
            session.add(
                SandboxHolding(
                    user_id=user.id, symbol="INFY", exchange="NSE", quantity=10,
                    average_price=1500.0, ltp=1510.0, pnl=100.0, pnlpercent=0.67,
                )
            )
        if session.scalar(select(SandboxFund).where(SandboxFund.user_id == user.id)) is None:
            session.add(
                SandboxFund(
                    user_id=user.id, starting_capital=10_000_000.0, available=9_950_000.0,
                    used_margin=50_000.0, realized_pnl=0.0, today_realized_pnl=0.0,
                    unrealized_pnl=1625.0,
                )
            )
        if session.scalar(
            select(Strategy).where(
                Strategy.user_id == user.id,
                Strategy.name == "Documentation Bull Call Spread",
            )
        ) is None:
            session.add(
                Strategy(
                    user_id=user.id, name="Documentation Bull Call Spread", underlying="NIFTY",
                    exchange="NFO", expiry_date="28JUL26", mode="sandbox", status="active",
                    legs=[
                        {"id": "doc-leg-1", "action": "BUY", "option_type": "CE", "strike": 24000.0,
                         "lots": 1, "lot_size": 65, "expiry_date": "28JUL26",
                         "symbol": "NIFTY28JUL2624000CE", "entry_price": 120.0,
                         "exit_price": None, "status": "open", "entry_time": None, "exit_time": None},
                        {"id": "doc-leg-2", "action": "SELL", "option_type": "CE", "strike": 24200.0,
                         "lots": 1, "lot_size": 65, "expiry_date": "28JUL26",
                         "symbol": "NIFTY28JUL2624200CE", "entry_price": 55.0,
                         "exit_price": None, "status": "open", "entry_time": None, "exit_time": None},
                    ],
                    notes="Documentation-only sandbox fixture; no provider order was sent.",
                )
            )
        session.commit()
    engine.dispose()


def serve(port: int) -> None:
    create_database()
    configure_environment()
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, log_level="warning")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("create")
    sub.add_parser("recreate")
    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--port", type=int, default=8000)
    seed_parser = sub.add_parser("seed-broker")
    seed_parser.add_argument("--username", required=True)
    args = parser.parse_args()

    if args.command == "create":
        create_database()
    elif args.command == "recreate":
        recreate_database()
    elif args.command == "serve":
        serve(args.port)
    elif args.command == "seed-broker":
        seed_documentation_fixture(args.username)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
