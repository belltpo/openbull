# Generated API Endpoint Inventory

> Generated from the FastAPI OpenAPI document. Authentication labels are classified from the current route families and must be read with the detailed security guide.

Operations: **166** across **148** paths.

| Method | Path | Operation | Authentication | Request | Success response | Handler |
|---|---|---|---|---|---|---|
| POST | /angel/login | Angel Login | Session cookie | AngelLoginPayload | Untyped JSON object; observed keys: status | `backend/routers/broker_oauth.py:204` |
| POST | /api/v1/analyzerstatus | Analyzer Status | OpenBull API key + active broker context | No request body | Untyped JSON object; observed keys: status, message, data | `backend/api/analyzer.py:72` |
| POST | /api/v1/analyzertoggle | Analyzer Toggle | OpenBull API key + active broker context + administrator | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message, data | `backend/api/analyzer.py:97` |
| POST | /api/v1/basketorder | Api Basket Order | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/basket_order.py:17` |
| POST | /api/v1/cancelallorder | Api Cancel All Orders | OpenBull API key + active broker context | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/api/place_order.py:182` |
| POST | /api/v1/cancelorder | Api Cancel Order | OpenBull API key + active broker context | No request body | Untyped JSON object; observed keys: status, message | `backend/api/place_order.py:150` |
| POST | /api/v1/closeposition | Api Close All Positions | OpenBull API key + active broker context | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/api/place_order.py:206` |
| POST | /api/v1/depth | Api Depth | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/depth.py:16` |
| POST | /api/v1/expiry | Api Expiry | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/expiry.py:18` |
| POST | /api/v1/funds | Api Funds | OpenBull API key + active broker context | No request body | Untyped JSON object; observed keys: status, message | `backend/api/funds.py:18` |
| POST | /api/v1/futures-risk/quick-order | Api Futures Risk Quick Order | OpenBull API key + active broker context | FuturesRiskQuickOrder | Untyped JSON object; observed keys: status, message, data | `backend/api/futures_risk.py:760` |
| POST | /api/v1/futures-risk/quick-order/options | Api Futures Risk Quick Order Options | OpenBull API key + active broker context | FuturesRiskQuickOrderOptions | Untyped JSON object; observed keys: status, message, data, mode | `backend/api/futures_risk.py:206` |
| POST | /api/v1/futures-risk/quick-order/preview | Api Futures Risk Quick Order Preview | OpenBull API key + active broker context | FuturesRiskQuickOrderPreview | Untyped JSON object; observed keys: status, message, data, mode | `backend/api/futures_risk.py:638` |
| POST | /api/v1/futures-risk/quick-order/settings | Api Futures Risk Quick Order Settings | OpenBull API key + active broker context | FuturesRiskQuickOrderSettings | Untyped JSON object; observed keys: status, message, data | `backend/api/futures_risk.py:307` |
| POST | /api/v1/futures-risk/quick-order/settings/delete | Api Futures Risk Quick Order Settings Delete | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/futures_risk.py:341` |
| GET | /api/v1/futures-risk/trades | Api Futures Risk Trade List | OpenBull API key (owner identity; broker context not required) | query:underlying, query:status, query:current_session, query:mode | Untyped JSON object; observed keys: status, data | `backend/api/futures_risk.py:879` |
| GET | /api/v1/futures-risk/trades/{trade_id} | Api Futures Risk Trade Detail | OpenBull API key (owner identity; broker context not required) | path:trade_id, query:mode | Untyped JSON object; observed keys: status, message, data | `backend/api/futures_risk.py:860` |
| POST | /api/v1/futures-risk/trades/{trade_id}/exit | Api Futures Risk Trade Exit | OpenBull API key + active broker context | path:trade_id | Untyped JSON object; observed keys: status, message, data | `backend/api/futures_risk.py:1007` |
| PUT | /api/v1/futures-risk/trades/{trade_id}/levels | Api Futures Risk Trade Levels | OpenBull API key + active broker context | path:trade_id | Untyped JSON object; observed keys: status, message, data | `backend/api/futures_risk.py:914` |
| POST | /api/v1/gex | Api Gex | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/gex.py:17` |
| POST | /api/v1/history | Api History | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/history.py:16` |
| POST | /api/v1/holdings | Api Holdings | OpenBull API key + active broker context | No request body | Untyped JSON object; observed keys: status, message | `backend/api/holdings.py:18` |
| POST | /api/v1/intervals | Api Intervals | OpenBull API key + active broker context | No request body | Untyped JSON object; observed keys: status, message | `backend/api/intervals.py:18` |
| POST | /api/v1/ivchart | Api Iv Chart | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/ivchart.py:17` |
| POST | /api/v1/ivsmile | Api Iv Smile | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/ivsmile.py:17` |
| POST | /api/v1/margin | Api Margin | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/margin.py:18` |
| POST | /api/v1/maxpain | Api Max Pain | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/maxpain.py:17` |
| POST | /api/v1/modifyorder | Api Modify Order | OpenBull API key + active broker context | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/api/place_order.py:116` |
| POST | /api/v1/multiquotes | Api Multiquotes | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/multiquotes.py:17` |
| POST | /api/v1/oitracker | Api Oi Tracker | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/oitracker.py:17` |
| POST | /api/v1/openposition | Api Openposition | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/openposition.py:18` |
| POST | /api/v1/optionchain | Api Option Chain | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/optionchain.py:19` |
| POST | /api/v1/optiongreeks | Api Option Greeks | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/optiongreeks.py:26` |
| POST | /api/v1/optionsmultiorder | Api Options Multiorder | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/optionsmultiorder.py:17` |
| POST | /api/v1/optionsorder | Api Options Order | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/optionsorder.py:16` |
| POST | /api/v1/optionsymbol | Api Option Symbol | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/optionsymbol.py:16` |
| POST | /api/v1/orderbook | Api Orderbook | OpenBull API key + active broker context | No request body | Untyped JSON object; observed keys: status, message | `backend/api/orderbook.py:18` |
| POST | /api/v1/orderstatus | Api Orderstatus | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/orderstatus.py:18` |
| POST | /api/v1/ping | Ping | OpenBull API key + active broker context | No request body | Untyped JSON object; observed keys: status, message | `backend/api/ping.py:18` |
| POST | /api/v1/placeorder | Api Place Order | OpenBull API key + active broker context | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/api/place_order.py:45` |
| POST | /api/v1/placesmartorder | Api Place Smart Order | OpenBull API key + active broker context | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/api/place_order.py:80` |
| POST | /api/v1/positionbook | Api Positions | OpenBull API key + active broker context | No request body | Untyped JSON object; observed keys: status, message | `backend/api/positions.py:18` |
| POST | /api/v1/positions | Api Positions | OpenBull API key + active broker context | No request body | Untyped JSON object; observed keys: status, message | `backend/api/positions.py:18` |
| POST | /api/v1/quotes | Api Quotes | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/quotes.py:17` |
| POST | /api/v1/search | Api Search | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/search.py:18` |
| POST | /api/v1/splitorder | Api Split Order | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/split_order.py:16` |
| POST | /api/v1/straddle | Api Straddle | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/straddle.py:17` |
| POST | /api/v1/symbol | Api Symbol | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/symbol.py:18` |
| POST | /api/v1/syntheticfuture | Api Synthetic Future | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/syntheticfuture.py:16` |
| POST | /api/v1/tradebook | Api Tradebook | OpenBull API key + active broker context | No request body | Untyped JSON object; observed keys: status, message | `backend/api/tradebook.py:18` |
| POST | /api/v1/volsurface | Api Vol Surface | OpenBull API key + active broker context | Untyped JSON body (handler-validated) | Untyped JSON object; observed keys: status, message | `backend/api/volsurface.py:21` |
| GET | /api/websocket/apikey | Websocket Apikey | Session cookie | No request body | Untyped JSON object; observed keys: status | `backend/routers/websocket.py:65` |
| GET | /api/websocket/config | Websocket Config | Session cookie | No request body | Untyped JSON object; observed keys: status | `backend/routers/websocket.py:42` |
| GET | /api/websocket/health | Websocket Health | Session cookie | No request body | Untyped JSON object; observed keys: status | `backend/routers/websocket.py:86` |
| GET | /api/websocket/market-data | Websocket Market Data | Session cookie | query:symbol, query:exchange | Untyped JSON object; observed keys: status, message, data | `backend/routers/websocket.py:117` |
| GET | /api/websocket/metrics | Websocket Metrics | Session cookie | No request body | Untyped JSON object; observed keys: status | `backend/routers/websocket.py:111` |
| GET | /api/websocket/trade-safe | Websocket Trade Safe | Session cookie | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/websocket.py:103` |
| GET | /auth/broker-redirect | Broker Redirect | Session cookie | query:broker | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/broker_oauth.py:58` |
| GET | /auth/check-setup | Check Setup | Public | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/auth.py:36` |
| POST | /auth/dhan/token-login | Dhan Token Login | Session cookie | DhanTokenPayload | Untyped JSON object; observed keys: status | `backend/routers/broker_oauth.py:240` |
| GET | /auth/error-logs | List Error Logs | Admin session cookie | query:limit, query:before_id, query:level | Untyped JSON object; observed keys: message, count, items | `backend/routers/error_logs.py:15` |
| POST | /auth/login | Login | Public | LoginRequest | AuthResponse | `.venv/Lib/site-packages/slowapi/extension.py:136` |
| POST | /auth/logout | Logout | Session cookie | No request body | AuthResponse | `.venv/Lib/site-packages/slowapi/extension.py:230` |
| GET | /auth/me | Me | Session cookie | No request body | UserInfo | `backend/routers/auth.py:273` |
| POST | /auth/setup | Setup | Public | SetupRequest | AuthResponse | `.venv/Lib/site-packages/slowapi/extension.py:43` |
| GET | /dhan/callback | Dhan Callback | Public | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/broker_oauth.py:185` |
| GET | /fyers/callback | Fyers Callback | Public | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/broker_oauth.py:170` |
| GET | /health | Health | Public | No request body | Untyped JSON object; observed keys: status | `backend/main.py:339` |
| GET | /upstox/callback | Upstox Callback | Public | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/broker_oauth.py:140` |
| GET | /web/apikey | Get Api Key | Session cookie | No request body | Untyped JSON object; observed keys: status, message | `backend/routers/api_key.py:21` |
| POST | /web/apikey | Generate New Api Key | Session cookie | No request body | Untyped JSON object; observed keys: status, message | `backend/routers/api_key.py:55` |
| PUT | /web/broker/credentials | Save Broker Credentials | Session cookie | BrokerConfigCreate | Untyped JSON object; observed keys: status, message | `backend/routers/broker_config.py:83` |
| GET | /web/broker/credentials/{broker_name} | Get Broker Credentials | Session cookie | path:broker_name | BrokerConfigResponse | `backend/routers/broker_config.py:54` |
| GET | /web/broker/list | List Brokers | Session cookie | No request body | array[BrokerListItem] | `backend/routers/broker_config.py:29` |
| GET | /web/dashboard | Dashboard | Session cookie | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/dashboard.py:17` |
| GET | /web/fr/config | Get Config | Session cookie | No request body | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:62` |
| POST | /web/fr/config | Update Config | Admin session cookie | backend__routers__futures_risk__ConfigUpdate | Untyped JSON object; observed keys: status | `backend/routers/futures_risk.py:67` |
| GET | /web/fr/expiries | Expiries | Session cookie | query:underlying, query:exchange | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:281` |
| GET | /web/fr/phases | List Phases | Session cookie | query:underlying, query:mode | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:488` |
| POST | /web/fr/quick-order-preview | Quick Order Preview | Session cookie | QuickOrderPreview | Untyped JSON object; observed keys: status, data, mode | `backend/routers/futures_risk.py:314` |
| POST | /web/fr/quick-order/settings | Save Quick Order Settings | Session cookie | ContractQuickOrderSettings | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:75` |
| GET | /web/fr/resolve-futures | Resolve Futures | Session cookie | query:underlying | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:273` |
| GET | /web/fr/strikes | Strikes | Session cookie | query:underlying, query:expiry, query:option_type, query:exchange | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:290` |
| GET | /web/fr/symbol-maps | Get Symbol Maps | Session cookie | No request body | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:238` |
| POST | /web/fr/symbol-maps | Add Symbol Map | Admin session cookie | SymbolMapCreate | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:243` |
| PUT | /web/fr/symbol-maps/{map_id} | Edit Symbol Map | Admin session cookie | SymbolMapUpdate | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:252` |
| DELETE | /web/fr/symbol-maps/{map_id} | Remove Symbol Map | Admin session cookie | path:map_id | Untyped JSON object; observed keys: status | `backend/routers/futures_risk.py:261` |
| GET | /web/fr/target-templates | Get Target Templates | Session cookie | No request body | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:142` |
| POST | /web/fr/target-templates | Add Target Template | Admin session cookie | TargetTemplateCreate | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:147` |
| PUT | /web/fr/target-templates/{template_id} | Edit Target Template | Admin session cookie | TargetTemplateUpdate | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:156` |
| DELETE | /web/fr/target-templates/{template_id} | Remove Target Template | Admin session cookie | path:template_id | Untyped JSON object; observed keys: status | `backend/routers/futures_risk.py:168` |
| GET | /web/fr/targets | Get Targets | Session cookie | query:template_id | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:179` |
| POST | /web/fr/targets | Add Target | Admin session cookie | TargetCreate | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:184` |
| PUT | /web/fr/targets/{target_id} | Edit Target | Admin session cookie | TargetUpdate | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:196` |
| DELETE | /web/fr/targets/{target_id} | Remove Target | Admin session cookie | path:target_id | Untyped JSON object; observed keys: status | `backend/routers/futures_risk.py:206` |
| POST | /web/fr/trade | Place Trade | Session cookie | PlaceTrade | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:436` |
| POST | /web/fr/trade/draft | Create Draft | Session cookie | PlaceTrade | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:458` |
| GET | /web/fr/trades | List Trades | Session cookie | query:status, query:mode | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:477` |
| GET | /web/fr/trades/{trade_id} | Get Trade | Session cookie | path:trade_id, query:mode | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:501` |
| PUT | /web/fr/trades/{trade_id} | Modify Trade | Session cookie | ModifyTrade | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:513` |
| DELETE | /web/fr/trades/{trade_id} | Delete Trade | Session cookie | path:trade_id | Untyped JSON object; observed keys: status | `backend/routers/futures_risk.py:553` |
| POST | /web/fr/trades/{trade_id}/emergency-exit | Emergency Exit | Session cookie | path:trade_id | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:583` |
| POST | /web/fr/trades/{trade_id}/exit | Exit Trade | Session cookie | path:trade_id | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:563` |
| POST | /web/fr/trades/{trade_id}/partial-exit | Partial Exit | Session cookie | PartialExit | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:573` |
| POST | /web/fr/trades/{trade_id}/place | Place Draft | Session cookie | path:trade_id | Untyped JSON object; observed keys: status, data | `backend/routers/futures_risk.py:534` |
| GET | /web/holdings | Holdings | Session cookie | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/holdings.py:17` |
| GET | /web/logs | List Api Logs | Session cookie | query:limit, query:before_id, query:method, query:mode, query:status, query:status_class, query:path_contains, query:start, query:end, query:user_id | Untyped JSON object; observed keys: status, count, items, mode | `backend/routers/api_logs.py:96` |
| GET | /web/logs/export.csv | Export Api Logs | Session cookie | query:method, query:mode, query:status, query:status_class, query:path_contains, query:start, query:end, query:user_id | Untyped JSON object; observed keys: status, mode | `backend/routers/api_logs.py:222` |
| GET | /web/logs/stats | Api Logs Stats | Session cookie | query:start, query:end | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/api_logs.py:137` |
| GET | /web/logs/{log_id} | Get Api Log | Session cookie | path:log_id | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/api_logs.py:202` |
| GET | /web/orderbook | Orderbook | Session cookie | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/orderbook.py:17` |
| GET | /web/playground/api-key | Playground Api Key | Session cookie | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/playground.py:307` |
| GET | /web/playground/endpoints | Playground Endpoints | Session cookie | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/playground.py:325` |
| GET | /web/playground/host | Playground Host | Session cookie | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/playground.py:345` |
| GET | /web/positions | Positions | Session cookie | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/positions.py:17` |
| GET | /web/sandbox/config | List Configs | Session cookie | No request body | Untyped JSON object; observed keys: status, data | `backend/routers/sandbox.py:47` |
| POST | /web/sandbox/config | Update Config | Admin session cookie | backend__routers__sandbox__ConfigUpdate | Untyped JSON object; observed keys: status | `backend/routers/sandbox.py:53` |
| GET | /web/sandbox/mypnl | My Daily Pnl | Session cookie | query:limit | Untyped JSON object; observed keys: status, data | `backend/routers/sandbox.py:96` |
| POST | /web/sandbox/reconcile-margin | Reconcile Margin Endpoint | Session cookie | query:auto_fix | Untyped JSON object; observed keys: status, consistent, discrepancy, details | `backend/routers/sandbox.py:237` |
| POST | /web/sandbox/reload-squareoff | Reload Squareoff | Admin session cookie | No request body | Untyped JSON object; observed keys: status, message | `backend/routers/sandbox.py:219` |
| POST | /web/sandbox/reset | Reset My Sandbox | Session cookie | No request body | Untyped JSON object; observed keys: status | `backend/routers/sandbox.py:69` |
| POST | /web/sandbox/settle-now | Settle Now | Admin session cookie | No request body | Untyped JSON object; observed keys: status | `backend/routers/sandbox.py:148` |
| POST | /web/sandbox/squareoff-now | Squareoff Now | Admin session cookie | query:bucket | Untyped JSON object; observed keys: status, placed | `backend/routers/sandbox.py:132` |
| GET | /web/sandbox/squareoff-status | Squareoff Status | Session cookie | No request body | Untyped JSON object; observed keys: status | `backend/routers/sandbox.py:177` |
| GET | /web/sandbox/summary | Summary | Session cookie | No request body | Untyped JSON object; observed keys: status, data | `backend/routers/sandbox.py:85` |
| POST | /web/sandbox/wipe-all | Wipe All | Admin session cookie | No request body | Untyped JSON object; observed keys: status | `backend/routers/sandbox.py:162` |
| GET | /web/strategies | List Strategies | Session cookie | query:mode, query:status, query:underlying | Untyped JSON object; observed keys: status | `backend/routers/strategies.py:54` |
| POST | /web/strategies | Create Strategy | Session cookie | backend__schemas__strategies__StrategyCreate | Untyped JSON object; observed keys: status | `backend/routers/strategies.py:98` |
| GET | /web/strategies/{strategy_id} | Get Strategy | Session cookie | path:strategy_id | Untyped JSON object; observed keys: status | `backend/routers/strategies.py:79` |
| PUT | /web/strategies/{strategy_id} | Update Strategy | Session cookie | backend__schemas__strategies__StrategyUpdate | Untyped JSON object; observed keys: status | `backend/routers/strategies.py:129` |
| DELETE | /web/strategies/{strategy_id} | Delete Strategy | Session cookie | path:strategy_id | Untyped JSON object; observed keys: status | `backend/routers/strategies.py:177` |
| GET | /web/strategy | List Strategies | Session cookie | query:status, query:universe_tab | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:133` |
| POST | /web/strategy | Create Strategy | Session cookie | backend__schemas__strategy_module__StrategyCreate | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/strategy_module.py:274` |
| GET | /web/strategy/expiries | List Expiries | Session cookie | query:underlying, query:underlying_exchange, query:instrument | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/strategy_module.py:181` |
| GET | /web/strategy/strikes | List Strikes | Session cookie | query:underlying, query:underlying_exchange, query:expiry, query:expiry_rank, query:option_type | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/strategy_module.py:201` |
| GET | /web/strategy/underlyings | List Underlyings | Session cookie | query:universe_tab | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/strategy_module.py:170` |
| GET | /web/strategy/{strategy_id} | Get Strategy | Session cookie | path:strategy_id | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:258` |
| PATCH | /web/strategy/{strategy_id} | Update Strategy | Session cookie | backend__schemas__strategy_module__StrategyUpdate | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:299` |
| DELETE | /web/strategy/{strategy_id} | Delete Strategy | Session cookie | path:strategy_id | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/strategy_module.py:322` |
| POST | /web/strategy/{strategy_id}/close_all | Close All Endpoint | Session cookie | path:strategy_id | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:517` |
| POST | /web/strategy/{strategy_id}/disable_live | Disable Live Mode | Session cookie | path:strategy_id | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:1133` |
| POST | /web/strategy/{strategy_id}/enable_live | Enable Live Mode | Session cookie | EnableLiveRequest | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:1057` |
| GET | /web/strategy/{strategy_id}/events | Get Strategy Events | Session cookie | path:strategy_id, query:run_id, query:limit | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:1032` |
| POST | /web/strategy/{strategy_id}/kill_switch | Kill Switch Endpoint | Session cookie | path:strategy_id | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:576` |
| POST | /web/strategy/{strategy_id}/legs/{leg_id}/close | Close Leg Endpoint | Session cookie | path:strategy_id, path:leg_id | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:632` |
| GET | /web/strategy/{strategy_id}/orders | Get Strategy Orders | Session cookie | path:strategy_id, query:run_id | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:660` |
| GET | /web/strategy/{strategy_id}/positions | Get Strategy Positions | Session cookie | path:strategy_id, query:run_id | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:705` |
| POST | /web/strategy/{strategy_id}/rotate_webhook_token | Rotate Webhook Token | Session cookie | path:strategy_id | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/strategy_module.py:338` |
| GET | /web/strategy/{strategy_id}/runs | Get Strategy Runs | Session cookie | path:strategy_id | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:1018` |
| POST | /web/strategy/{strategy_id}/start | Start Run | Session cookie | StartRunRequest | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:420` |
| POST | /web/strategy/{strategy_id}/stop | Stop Run Endpoint | Session cookie | path:strategy_id | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:467` |
| GET | /web/strategy/{strategy_id}/tradebook | Get Strategy Tradebook | Session cookie | path:strategy_id, query:run_id | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:961` |
| POST | /web/strategy/{strategy_id}/unlock_webhook | Unlock Webhook Endpoint | Session cookie | path:strategy_id | Untyped JSON object; observed keys: status | `backend/routers/strategy_module.py:608` |
| GET | /web/strategy/{strategy_id}/webhook_events | Get Strategy Webhook Events | Session cookie | path:strategy_id, query:limit | Untyped JSON object; observed keys: status, mode | `backend/routers/strategy_module.py:1184` |
| POST | /web/strategybuilder/chart | Strategy Chart | Session cookie | ChartRequest | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/strategybuilder.py:122` |
| POST | /web/strategybuilder/multi-strike-oi | Multi Strike Oi | Session cookie | MultiStrikeOIRequest | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/strategybuilder.py:182` |
| POST | /web/strategybuilder/snapshot | Snapshot | Session cookie | SnapshotRequest | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/strategybuilder.py:62` |
| POST | /web/symbols/download | Trigger Master Download | Session cookie | No request body | Untyped JSON object; observed keys: status, message | `backend/routers/symbols.py:61` |
| GET | /web/symbols/search | Symbol Search | Session cookie | query:q, query:exchange | Untyped JSON object; observed keys: status, data | `backend/routers/symbols.py:32` |
| GET | /web/symbols/status | Symbol Download Status | Session cookie | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/symbols.py:26` |
| GET | /web/symbols/underlyings | Option Underlyings | Session cookie | query:exchange | Untyped JSON object; observed keys: status, data | `backend/routers/symbols.py:46` |
| GET | /web/tradebook | Tradebook | Session cookie | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/tradebook.py:17` |
| GET | /web/trading-mode | Read Trading Mode | Session cookie | No request body | Untyped JSON object; observed keys: mode | `backend/routers/trading_mode.py:36` |
| POST | /web/trading-mode | Update Trading Mode | Admin session cookie | TradingModePayload | Untyped JSON object; observed keys: mode | `backend/routers/trading_mode.py:46` |
| POST | /webhook/strategy/{webhook_token} | Receive Webhook | Strategy webhook token | path:webhook_token | Untyped JSON object; observed keys: status | `backend/routers/strategy_webhook.py:33` |
| GET | /zerodha/callback | Zerodha Callback | Public | No request body | Untyped handler response; inspect linked handler/OpenAPI | `backend/routers/broker_oauth.py:155` |

Machine-readable contract: [openapi.json](openapi.json).
