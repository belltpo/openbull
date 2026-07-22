# Generated Database Schema Inventory

SQLAlchemy metadata tables: **31**.

> This is the ORM metadata view. Read it together with the Alembic and startup-migration guide for existing installations.

## `api_logs`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `BIGINT` | no | PK | `—` |
| `created_at` | `DATETIME` | no | server default | `—` |
| `user_id` | `INTEGER` | yes | — | `—` |
| `auth_method` | `VARCHAR(20)` | yes | — | `—` |
| `mode` | `VARCHAR(10)` | yes | — | `—` |
| `method` | `VARCHAR(8)` | no | — | `—` |
| `path` | `VARCHAR(500)` | no | — | `—` |
| `status_code` | `INTEGER` | no | — | `—` |
| `duration_ms` | `FLOAT` | no | — | `—` |
| `client_ip` | `VARCHAR(64)` | yes | — | `—` |
| `user_agent` | `VARCHAR(500)` | yes | — | `—` |
| `request_id` | `VARCHAR(50)` | yes | — | `—` |
| `request_body` | `TEXT` | yes | — | `—` |
| `response_body` | `TEXT` | yes | — | `—` |
| `error` | `VARCHAR(500)` | yes | — | `—` |

Named constraints: —
Indexes: `idx_api_logs_created_at`, `idx_api_logs_mode_created`, `idx_api_logs_path`, `idx_api_logs_status_code`, `idx_api_logs_user_created`

## `app_settings`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `key` | `VARCHAR(100)` | no | unique, index | `—` |
| `value` | `TEXT` | no | — | `—` |

Named constraints: —
Indexes: `ix_app_settings_key`

## `error_logs`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `created_at` | `DATETIME` | yes | index, server default | `—` |
| `level` | `VARCHAR(20)` | no | index | `—` |
| `logger` | `VARCHAR(200)` | yes | — | `—` |
| `message` | `TEXT` | yes | — | `—` |
| `module` | `VARCHAR(200)` | yes | — | `—` |
| `func_name` | `VARCHAR(200)` | yes | — | `—` |
| `lineno` | `INTEGER` | yes | — | `—` |
| `request_id` | `VARCHAR(50)` | yes | index | `—` |
| `exc_text` | `TEXT` | yes | — | `—` |

Named constraints: —
Indexes: `ix_error_logs_created_at`, `ix_error_logs_level`, `ix_error_logs_request_id`

## `fr_config`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `key` | `VARCHAR(100)` | no | unique, index | `—` |
| `value` | `TEXT` | no | — | `—` |
| `description` | `VARCHAR(500)` | yes | — | `—` |
| `is_editable` | `BOOLEAN` | no | default `True` | `—` |
| `updated_at` | `DATETIME` | no | server default | `—` |

Named constraints: —
Indexes: `ix_fr_config_key`

## `fr_symbol_map`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `underlying` | `VARCHAR(50)` | no | unique, index | `—` |
| `underlying_exchange` | `VARCHAR(20)` | no | default `NSE_INDEX` | `—` |
| `futures_symbol` | `VARCHAR(100)` | yes | — | `—` |
| `futures_exchange` | `VARCHAR(20)` | no | default `NFO` | `—` |
| `lot_size` | `INTEGER` | no | default `0` | `—` |
| `auto_resolve` | `BOOLEAN` | no | default `True` | `—` |
| `enabled` | `BOOLEAN` | no | default `True` | `—` |
| `updated_at` | `DATETIME` | no | server default | `—` |

Named constraints: —
Indexes: `ix_fr_symbol_map_underlying`

## `fr_target_template`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `name` | `VARCHAR(100)` | no | unique, index | `—` |
| `description` | `VARCHAR(500)` | yes | — | `—` |
| `is_default` | `BOOLEAN` | no | default `False` | `—` |
| `enabled` | `BOOLEAN` | no | default `True` | `—` |
| `created_at` | `DATETIME` | no | server default | `—` |
| `updated_at` | `DATETIME` | no | server default | `—` |

Named constraints: —
Indexes: `idx_fr_target_template_default`, `ix_fr_target_template_name`

## `fr_trade`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | index | `—` |
| `mode` | `VARCHAR(10)` | no | default `live` | `—` |
| `underlying` | `VARCHAR(50)` | no | — | `—` |
| `option_symbol` | `VARCHAR(100)` | no | — | `—` |
| `option_exchange` | `VARCHAR(20)` | no | — | `—` |
| `option_type` | `VARCHAR(2)` | no | — | `—` |
| `side` | `VARCHAR(4)` | no | — | `—` |
| `product` | `VARCHAR(10)` | no | default `MIS` | `—` |
| `expiry` | `VARCHAR(20)` | yes | — | `—` |
| `strike` | `FLOAT` | yes | — | `—` |
| `lots` | `INTEGER` | no | default `1` | `—` |
| `lot_size` | `INTEGER` | no | default `1` | `—` |
| `total_qty` | `INTEGER` | no | default `0` | `—` |
| `remaining_qty` | `INTEGER` | no | default `0` | `—` |
| `entry_option_price` | `FLOAT` | no | default `0.0` | `—` |
| `entry_order_id` | `VARCHAR(60)` | yes | — | `—` |
| `futures_symbol` | `VARCHAR(100)` | no | — | `—` |
| `futures_exchange` | `VARCHAR(20)` | no | default `NFO` | `—` |
| `entry_futures_price` | `FLOAT` | no | default `0.0` | `—` |
| `direction` | `INTEGER` | no | default `1` | `—` |
| `sl_points` | `FLOAT` | no | default `0.0` | `—` |
| `sl_price` | `FLOAT` | no | default `0.0` | `—` |
| `sl_basis` | `VARCHAR(20)` | no | default `initial` | `—` |
| `status` | `VARCHAR(12)` | no | index, default `active` | `—` |
| `realized_pnl` | `FLOAT` | no | default `0.0` | `—` |
| `meta` | `JSONB` | yes | — | `—` |
| `exit_state` | `VARCHAR(20)` | no | default `idle` | `—` |
| `exit_attempt_id` | `VARCHAR(36)` | yes | — | `—` |
| `exit_attempt_reason` | `VARCHAR(20)` | yes | — | `—` |
| `exit_attempted_at` | `DATETIME` | yes | — | `—` |
| `exit_failure_count` | `INTEGER` | no | default `0` | `—` |
| `exit_block_reason` | `TEXT` | yes | — | `—` |
| `last_exit_order_id` | `VARCHAR(60)` | yes | — | `—` |
| `broker_remaining_qty` | `INTEGER` | yes | — | `—` |
| `broker_reconciled_at` | `DATETIME` | yes | — | `—` |
| `created_by` | `INTEGER` | yes | — | `—` |
| `modified_by` | `INTEGER` | yes | — | `—` |
| `phase_group` | `VARCHAR(120)` | yes | index | `—` |
| `phase_no` | `INTEGER` | no | default `0` | `—` |
| `closed_at` | `DATETIME` | yes | — | `—` |
| `created_at` | `DATETIME` | no | server default | `—` |
| `updated_at` | `DATETIME` | no | server default | `—` |

Named constraints: —
Indexes: `idx_fr_trade_exit_state`, `idx_fr_trade_fut_status`, `idx_fr_trade_phase_group`, `idx_fr_trade_user_status`, `ix_fr_trade_phase_group`, `ix_fr_trade_status`, `ix_fr_trade_user_id`

## `login_attempts`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `username` | `VARCHAR(255)` | no | index | `—` |
| `ip_address` | `VARCHAR(45)` | yes | — | `—` |
| `device_info` | `VARCHAR(500)` | yes | — | `—` |
| `status` | `VARCHAR(20)` | no | — | `—` |
| `login_type` | `VARCHAR(20)` | yes | — | `—` |
| `broker` | `VARCHAR(50)` | yes | — | `—` |
| `failure_reason` | `VARCHAR(255)` | yes | — | `—` |
| `created_at` | `DATETIME` | yes | index, server default | `—` |

Named constraints: —
Indexes: `ix_login_attempts_created_at`, `ix_login_attempts_username`

## `sandbox_config`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `key` | `VARCHAR(100)` | no | unique, index | `—` |
| `value` | `TEXT` | no | — | `—` |
| `description` | `VARCHAR(500)` | yes | — | `—` |
| `is_editable` | `BOOLEAN` | no | default `True` | `—` |
| `updated_at` | `DATETIME` | no | server default | `—` |

Named constraints: —
Indexes: `ix_sandbox_config_key`

## `sandbox_daily_pnl`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | index | `—` |
| `snapshot_date` | `VARCHAR(10)` | no | — | `—` |
| `starting_capital` | `FLOAT` | no | default `0.0` | `—` |
| `available` | `FLOAT` | no | default `0.0` | `—` |
| `used_margin` | `FLOAT` | no | default `0.0` | `—` |
| `realized_pnl` | `FLOAT` | no | default `0.0` | `—` |
| `unrealized_pnl` | `FLOAT` | no | default `0.0` | `—` |
| `total_pnl` | `FLOAT` | no | default `0.0` | `—` |
| `positions_pnl` | `FLOAT` | no | default `0.0` | `—` |
| `holdings_pnl` | `FLOAT` | no | default `0.0` | `—` |
| `trades_count` | `INTEGER` | no | default `0` | `—` |
| `created_at` | `DATETIME` | no | server default | `—` |

Named constraints: —
Indexes: `idx_sbx_daily_pnl_user_date`, `ix_sandbox_daily_pnl_user_id`

## `sandbox_funds`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | unique, index | `—` |
| `starting_capital` | `FLOAT` | no | default `10000000.0` | `—` |
| `available` | `FLOAT` | no | default `10000000.0` | `—` |
| `used_margin` | `FLOAT` | no | default `0.0` | `—` |
| `realized_pnl` | `FLOAT` | no | default `0.0` | `—` |
| `today_realized_pnl` | `FLOAT` | no | default `0.0` | `—` |
| `unrealized_pnl` | `FLOAT` | no | default `0.0` | `—` |
| `reset_at` | `DATETIME` | no | server default | `—` |
| `updated_at` | `DATETIME` | no | server default | `—` |

Named constraints: —
Indexes: `ix_sandbox_funds_user_id`

## `sandbox_holdings`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | index | `—` |
| `symbol` | `VARCHAR(100)` | no | — | `—` |
| `exchange` | `VARCHAR(20)` | no | — | `—` |
| `quantity` | `INTEGER` | no | default `0` | `—` |
| `average_price` | `FLOAT` | no | default `0.0` | `—` |
| `ltp` | `FLOAT` | no | default `0.0` | `—` |
| `pnl` | `FLOAT` | no | default `0.0` | `—` |
| `pnlpercent` | `FLOAT` | no | default `0.0` | `—` |
| `settlement_date` | `VARCHAR(10)` | yes | — | `—` |
| `added_on` | `DATETIME` | no | server default | `—` |

Named constraints: —
Indexes: `idx_sbx_holdings_user_sym`, `ix_sandbox_holdings_user_id`

## `sandbox_orders`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | index | `—` |
| `orderid` | `VARCHAR(40)` | no | unique, index | `—` |
| `symbol` | `VARCHAR(100)` | no | — | `—` |
| `exchange` | `VARCHAR(20)` | no | — | `—` |
| `action` | `VARCHAR(8)` | no | — | `—` |
| `quantity` | `INTEGER` | no | — | `—` |
| `filled_quantity` | `INTEGER` | no | default `0` | `—` |
| `pricetype` | `VARCHAR(10)` | no | — | `—` |
| `product` | `VARCHAR(10)` | no | — | `—` |
| `price` | `FLOAT` | no | default `0.0` | `—` |
| `trigger_price` | `FLOAT` | no | default `0.0` | `—` |
| `average_price` | `FLOAT` | no | default `0.0` | `—` |
| `status` | `VARCHAR(20)` | no | index, default `open` | `—` |
| `rejection_reason` | `VARCHAR(500)` | yes | — | `—` |
| `strategy` | `VARCHAR(100)` | yes | — | `—` |
| `margin_blocked` | `FLOAT` | no | default `0.0` | `—` |
| `order_timestamp` | `DATETIME` | no | server default | `—` |
| `update_timestamp` | `DATETIME` | no | server default | `—` |

Named constraints: —
Indexes: `idx_sbx_orders_symbol_status`, `idx_sbx_orders_user_status`, `ix_sandbox_orders_orderid`, `ix_sandbox_orders_status`, `ix_sandbox_orders_user_id`

## `sandbox_positions`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | index | `—` |
| `symbol` | `VARCHAR(100)` | no | — | `—` |
| `exchange` | `VARCHAR(20)` | no | — | `—` |
| `product` | `VARCHAR(10)` | no | — | `—` |
| `net_quantity` | `INTEGER` | no | default `0` | `—` |
| `average_price` | `FLOAT` | no | default `0.0` | `—` |
| `ltp` | `FLOAT` | no | default `0.0` | `—` |
| `pnl` | `FLOAT` | no | default `0.0` | `—` |
| `realized_pnl` | `FLOAT` | no | default `0.0` | `—` |
| `today_realized_pnl` | `FLOAT` | no | default `0.0` | `—` |
| `unrealized_pnl` | `FLOAT` | no | default `0.0` | `—` |
| `margin_blocked` | `FLOAT` | no | default `0.0` | `—` |
| `day_buy_quantity` | `INTEGER` | no | default `0` | `—` |
| `day_buy_value` | `FLOAT` | no | default `0.0` | `—` |
| `day_sell_quantity` | `INTEGER` | no | default `0` | `—` |
| `day_sell_value` | `FLOAT` | no | default `0.0` | `—` |
| `updated_at` | `DATETIME` | no | server default | `—` |

Named constraints: —
Indexes: `idx_sbx_positions_user_sym`, `ix_sandbox_positions_user_id`

## `sandbox_trades`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | index | `—` |
| `orderid` | `VARCHAR(40)` | no | index | `—` |
| `tradeid` | `VARCHAR(40)` | no | unique | `—` |
| `symbol` | `VARCHAR(100)` | no | — | `—` |
| `exchange` | `VARCHAR(20)` | no | — | `—` |
| `action` | `VARCHAR(8)` | no | — | `—` |
| `quantity` | `INTEGER` | no | — | `—` |
| `average_price` | `FLOAT` | no | — | `—` |
| `product` | `VARCHAR(10)` | no | — | `—` |
| `strategy` | `VARCHAR(100)` | yes | — | `—` |
| `timestamp` | `DATETIME` | no | server default | `—` |

Named constraints: —
Indexes: `idx_sbx_trades_user_ts`, `ix_sandbox_trades_orderid`, `ix_sandbox_trades_user_id`

## `symtoken`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `symbol` | `VARCHAR(100)` | no | index | `—` |
| `brsymbol` | `VARCHAR(100)` | no | index | `—` |
| `name` | `VARCHAR(100)` | yes | — | `—` |
| `exchange` | `VARCHAR(20)` | no | index | `—` |
| `brexchange` | `VARCHAR(20)` | yes | — | `—` |
| `token` | `VARCHAR(50)` | yes | index | `—` |
| `expiry` | `VARCHAR(20)` | yes | — | `—` |
| `strike` | `FLOAT` | yes | — | `—` |
| `lotsize` | `INTEGER` | yes | — | `—` |
| `instrumenttype` | `VARCHAR(20)` | yes | — | `—` |
| `tick_size` | `FLOAT` | yes | — | `—` |

Named constraints: —
Indexes: `idx_symtoken_brsymbol_exchange`, `idx_symtoken_exchange_type_symbol`, `idx_symtoken_symbol_exchange`, `ix_symtoken_brsymbol`, `ix_symtoken_exchange`, `ix_symtoken_symbol`, `ix_symtoken_token`

## `users`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `username` | `VARCHAR(80)` | no | unique, index | `—` |
| `email` | `VARCHAR(120)` | no | unique | `—` |
| `password_hash` | `VARCHAR(255)` | no | — | `—` |
| `is_admin` | `BOOLEAN` | yes | default `True` | `—` |
| `created_at` | `DATETIME` | yes | server default | `—` |

Named constraints: —
Indexes: `ix_users_username`

## `active_sessions`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | index | `users.id` |
| `session_token` | `VARCHAR(64)` | no | unique | `—` |
| `device_info` | `VARCHAR(500)` | yes | — | `—` |
| `ip_address` | `VARCHAR(45)` | yes | — | `—` |
| `broker` | `VARCHAR(50)` | yes | — | `—` |
| `login_time` | `DATETIME` | yes | server default | `—` |
| `last_seen` | `DATETIME` | yes | server default | `—` |

Named constraints: —
Indexes: `ix_active_sessions_user_id`

## `api_keys`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | unique | `users.id` |
| `api_key_hash` | `TEXT` | no | — | `—` |
| `api_key_encrypted` | `TEXT` | no | — | `—` |
| `created_at` | `DATETIME` | yes | server default | `—` |

## `broker_auth`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | — | `users.id` |
| `broker_name` | `VARCHAR(50)` | no | — | `—` |
| `access_token` | `TEXT` | no | — | `—` |
| `feed_token` | `TEXT` | yes | — | `—` |
| `broker_user_id` | `VARCHAR(255)` | yes | — | `—` |
| `is_revoked` | `BOOLEAN` | yes | index, default `False` | `—` |
| `created_at` | `DATETIME` | yes | server default | `—` |
| `updated_at` | `DATETIME` | yes | server default | `—` |

Named constraints: `uq_broker_auth_user_broker`
Indexes: `ix_broker_auth_is_revoked`

## `broker_configs`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | — | `users.id` |
| `broker_name` | `VARCHAR(50)` | no | — | `—` |
| `api_key` | `TEXT` | no | — | `—` |
| `api_secret` | `TEXT` | no | — | `—` |
| `redirect_url` | `VARCHAR(500)` | no | — | `—` |
| `is_active` | `BOOLEAN` | yes | index, default `False` | `—` |
| `extra_config` | `JSONB` | yes | default `dict` | `—` |
| `created_at` | `DATETIME` | yes | server default | `—` |
| `updated_at` | `DATETIME` | yes | server default | `—` |

Named constraints: `uq_broker_config_user_broker`
Indexes: `ix_broker_configs_is_active`

## `fr_target_level`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `template_id` | `INTEGER` | no | index | `fr_target_template.id` |
| `seq` | `INTEGER` | no | — | `—` |
| `points` | `FLOAT` | no | — | `—` |
| `exit_pct` | `FLOAT` | no | default `0.0` | `—` |
| `enabled` | `BOOLEAN` | no | default `True` | `—` |
| `updated_at` | `DATETIME` | no | server default | `—` |

Named constraints: —
Indexes: `idx_fr_target_template_seq`, `ix_fr_target_level_template_id`

## `fr_trade_event`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `trade_id` | `INTEGER` | yes | index | `fr_trade.id` |
| `user_id` | `INTEGER` | no | index | `—` |
| `ts` | `DATETIME` | no | server default | `—` |
| `kind` | `VARCHAR(20)` | no | — | `—` |
| `severity` | `VARCHAR(10)` | no | default `info` | `—` |
| `message` | `TEXT` | no | — | `—` |
| `payload` | `JSONB` | yes | — | `—` |

Named constraints: —
Indexes: `idx_fr_event_trade_ts`, `idx_fr_event_user_ts`, `ix_fr_trade_event_trade_id`, `ix_fr_trade_event_user_id`

## `fr_trade_target`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `trade_id` | `INTEGER` | no | index | `fr_trade.id` |
| `seq` | `INTEGER` | no | — | `—` |
| `points` | `FLOAT` | no | — | `—` |
| `exit_pct` | `FLOAT` | no | default `0.0` | `—` |
| `trigger_price` | `FLOAT` | no | — | `—` |
| `exit_qty` | `INTEGER` | no | default `0` | `—` |
| `status` | `VARCHAR(10)` | no | default `pending` | `—` |
| `hit_futures_price` | `FLOAT` | yes | — | `—` |
| `exit_order_id` | `VARCHAR(60)` | yes | — | `—` |
| `hit_at` | `DATETIME` | yes | — | `—` |

Named constraints: —
Indexes: `idx_fr_tgt_trade_seq`, `ix_fr_trade_target_trade_id`

## `sm_strategy`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | index | `users.id` |
| `name` | `VARCHAR(200)` | no | — | `—` |
| `strategy_kind` | `VARCHAR(20)` | no | default `batch` | `—` |
| `direction` | `VARCHAR(20)` | no | default `both` | `—` |
| `universe_tab` | `VARCHAR(30)` | no | — | `—` |
| `underlying` | `VARCHAR(50)` | no | — | `—` |
| `underlying_exchange` | `VARCHAR(20)` | no | — | `—` |
| `strategy_type` | `VARCHAR(20)` | no | — | `—` |
| `entry_time` | `TIME` | yes | — | `—` |
| `exit_time` | `TIME` | yes | — | `—` |
| `product` | `VARCHAR(10)` | no | default `NRML` | `—` |
| `pricetype` | `VARCHAR(10)` | no | default `MARKET` | `—` |
| `legs` | `JSONB` | no | — | `—` |
| `overall_sl_mtm` | `NUMERIC(18, 2)` | yes | — | `—` |
| `overall_target_mtm` | `NUMERIC(18, 2)` | yes | — | `—` |
| `lock_profit` | `JSONB` | yes | — | `—` |
| `trail_sl_to_entry` | `BOOLEAN` | no | default `False` | `—` |
| `scheduler` | `JSONB` | yes | — | `—` |
| `live_enabled` | `BOOLEAN` | no | default `False` | `—` |
| `webhook_token_hash` | `VARCHAR(64)` | no | unique | `—` |
| `webhook_ip_allowlist` | `JSONB` | yes | — | `—` |
| `webhook_locked` | `BOOLEAN` | no | default `False` | `—` |
| `daily_loss_limit_inr` | `NUMERIC(18, 2)` | yes | — | `—` |
| `status` | `VARCHAR(20)` | no | default `stopped` | `—` |
| `current_run_id` | `INTEGER` | yes | — | `sm_strategy_run.id` |
| `created_at` | `DATETIME` | no | server default | `—` |
| `updated_at` | `DATETIME` | no | server default | `—` |

Named constraints: `fk_sm_strategy_current_run`, `uq_sm_strategy_user_name`
Indexes: `ix_sm_strategy_user_id`, `ix_sm_strategy_user_status`

## `strategies`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `user_id` | `INTEGER` | no | index | `users.id` |
| `name` | `VARCHAR(200)` | no | — | `—` |
| `underlying` | `VARCHAR(50)` | no | — | `—` |
| `exchange` | `VARCHAR(20)` | no | — | `—` |
| `expiry_date` | `VARCHAR(20)` | yes | — | `—` |
| `mode` | `VARCHAR(20)` | no | default `live` | `—` |
| `status` | `VARCHAR(20)` | no | default `active` | `—` |
| `legs` | `JSONB` | no | — | `—` |
| `notes` | `TEXT` | yes | — | `—` |
| `created_at` | `DATETIME` | no | server default | `—` |
| `updated_at` | `DATETIME` | no | server default | `—` |
| `closed_at` | `DATETIME` | yes | — | `—` |

Named constraints: —
Indexes: `idx_strategies_user_mode_status`, `idx_strategies_user_underlying`, `ix_strategies_user_id`

## `sm_strategy_run`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `strategy_id` | `INTEGER` | no | index | `sm_strategy.id` |
| `mode` | `VARCHAR(10)` | no | — | `—` |
| `broker` | `VARCHAR(50)` | no | — | `—` |
| `started_at` | `DATETIME` | no | server default | `—` |
| `stopped_at` | `DATETIME` | yes | — | `—` |
| `stop_reason` | `VARCHAR(30)` | yes | — | `—` |
| `pnl_realized` | `NUMERIC(18, 2)` | no | default `0` | `—` |
| `pnl_peak` | `NUMERIC(18, 2)` | no | default `0` | `—` |
| `pnl_trough` | `NUMERIC(18, 2)` | no | default `0` | `—` |
| `trigger_source` | `VARCHAR(20)` | no | default `manual` | `—` |
| `webhook_event_id` | `INTEGER` | yes | — | `sm_webhook_event.id` |

Named constraints: `fk_sm_run_webhook_event`
Indexes: `ix_sm_run_strategy_started`, `ix_sm_strategy_run_strategy_id`

## `sm_webhook_event`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `strategy_id` | `INTEGER` | yes | index | `sm_strategy.id` |
| `action` | `VARCHAR(20)` | yes | — | `—` |
| `mode` | `VARCHAR(10)` | yes | — | `—` |
| `payload` | `JSONB` | yes | — | `—` |
| `ip` | `INET` | yes | — | `—` |
| `user_agent` | `VARCHAR(255)` | yes | — | `—` |
| `received_at` | `DATETIME` | no | server default | `—` |
| `result` | `VARCHAR(50)` | no | — | `—` |
| `error` | `TEXT` | yes | — | `—` |

Named constraints: —
Indexes: `ix_sm_webhook_event_strategy_id`, `ix_sm_webhook_strategy_received`

## `sm_strategy_checkpoint`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `BIGINT` | no | PK | `—` |
| `run_id` | `INTEGER` | no | index | `sm_strategy_run.id` |
| `ts` | `DATETIME` | no | server default | `—` |
| `pnl_realized` | `NUMERIC(18, 2)` | no | default `0` | `—` |
| `pnl_unrealized` | `NUMERIC(18, 2)` | no | default `0` | `—` |
| `pnl_total` | `NUMERIC(18, 2)` | no | default `0` | `—` |
| `pnl_peak` | `NUMERIC(18, 2)` | no | default `0` | `—` |
| `pnl_trough` | `NUMERIC(18, 2)` | no | default `0` | `—` |
| `lock_floor` | `NUMERIC(18, 2)` | yes | — | `—` |
| `trail_to_entry_active` | `BOOLEAN` | no | default `False` | `—` |
| `leg_state` | `JSONB` | no | — | `—` |

Named constraints: —
Indexes: `ix_sm_strategy_checkpoint_run_id`

## `sm_strategy_event`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `run_id` | `INTEGER` | yes | index | `sm_strategy_run.id` |
| `strategy_id` | `INTEGER` | no | index | `sm_strategy.id` |
| `user_id` | `INTEGER` | no | index | `users.id` |
| `ts` | `DATETIME` | no | server default | `—` |
| `kind` | `VARCHAR(40)` | no | — | `—` |
| `severity` | `VARCHAR(10)` | no | default `info` | `—` |
| `leg_id` | `INTEGER` | yes | — | `—` |
| `message` | `TEXT` | no | — | `—` |
| `payload` | `JSONB` | yes | — | `—` |

Named constraints: —
Indexes: `ix_sm_event_strategy_ts`, `ix_sm_event_user_ts`, `ix_sm_strategy_event_run_id`, `ix_sm_strategy_event_strategy_id`, `ix_sm_strategy_event_user_id`

## `sm_strategy_order`

| Column | Type | Nullable | Key/default | Foreign key |
|---|---|---:|---|---|
| `id` | `INTEGER` | no | PK | `—` |
| `run_id` | `INTEGER` | no | index | `sm_strategy_run.id` |
| `leg_id` | `INTEGER` | no | — | `—` |
| `kind` | `VARCHAR(30)` | no | — | `—` |
| `broker_order_id` | `VARCHAR(100)` | yes | index | `—` |
| `symbol` | `VARCHAR(100)` | no | — | `—` |
| `exchange` | `VARCHAR(20)` | no | — | `—` |
| `action` | `VARCHAR(10)` | no | — | `—` |
| `qty` | `INTEGER` | no | — | `—` |
| `pricetype` | `VARCHAR(10)` | no | — | `—` |
| `price` | `NUMERIC(18, 4)` | no | default `0` | `—` |
| `trigger_price` | `NUMERIC(18, 4)` | no | default `0` | `—` |
| `status` | `VARCHAR(20)` | no | default `pending` | `—` |
| `placed_at` | `DATETIME` | no | server default | `—` |
| `filled_at` | `DATETIME` | yes | — | `—` |
| `avg_fill_price` | `NUMERIC(18, 4)` | yes | — | `—` |
| `filled_qty` | `INTEGER` | yes | — | `—` |
| `reject_reason` | `TEXT` | yes | — | `—` |

Named constraints: —
Indexes: `ix_sm_order_run_placed`, `ix_sm_strategy_order_broker_order_id`, `ix_sm_strategy_order_run_id`
