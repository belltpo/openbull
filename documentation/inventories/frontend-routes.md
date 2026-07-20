# Generated Frontend Route Inventory

Routes declared in `frontend/src/App.tsx`: **40**.

| Route | Route guard | Declaration | Notes |
|---|---|---|---|
| `/` | Public | `frontend/src/App.tsx:125` |  |
| `/login` | Public | `frontend/src/App.tsx:126` |  |
| `/setup` | Public | `frontend/src/App.tsx:127` |  |
| `/broker/select` | Authenticated session | `frontend/src/App.tsx:131` |  |
| `/broker/angel/totp` | Authenticated session | `frontend/src/App.tsx:141` |  |
| `/broker/dhan/token` | Authenticated session | `frontend/src/App.tsx:151` |  |
| `/quick-order` | Authenticated session + active broker | `frontend/src/App.tsx:161` |  |
| `/playground` | Authenticated session + active broker | `frontend/src/App.tsx:171` |  |
| `/dashboard` | Authenticated session + active broker | `frontend/src/App.tsx:190` |  |
| `/broker/config` | Authenticated session | `frontend/src/App.tsx:197` |  |
| `/apikey` | Authenticated session | `frontend/src/App.tsx:198` |  |
| `/search` | Authenticated session + active broker | `frontend/src/App.tsx:200` |  |
| `/orderbook` | Authenticated session + active broker | `frontend/src/App.tsx:208` |  |
| `/tradebook` | Authenticated session + active broker | `frontend/src/App.tsx:216` |  |
| `/positions` | Authenticated session + active broker | `frontend/src/App.tsx:224` |  |
| `/holdings` | Authenticated session + active broker | `frontend/src/App.tsx:232` |  |
| `/websocket/test` | Authenticated session + active broker | `frontend/src/App.tsx:240` |  |
| `/logs` | Authenticated session | `frontend/src/App.tsx:248` |  |
| `/sandbox` | Authenticated session | `frontend/src/App.tsx:256` |  |
| `/sandbox/mypnl` | Authenticated session | `frontend/src/App.tsx:264` |  |
| `/tools` | Authenticated session + active broker | `frontend/src/App.tsx:272` |  |
| `/tools/optionchain` | Authenticated session + active broker | `frontend/src/App.tsx:280` |  |
| `/tools/oitracker` | Authenticated session + active broker | `frontend/src/App.tsx:290` |  |
| `/tools/maxpain` | Authenticated session + active broker | `frontend/src/App.tsx:300` |  |
| `/tools/greeks` | Authenticated session + active broker | `frontend/src/App.tsx:310` |  |
| `/tools/ivsmile` | Authenticated session + active broker | `frontend/src/App.tsx:320` |  |
| `/tools/volsurface` | Authenticated session + active broker | `frontend/src/App.tsx:330` |  |
| `/tools/straddle` | Authenticated session + active broker | `frontend/src/App.tsx:340` |  |
| `/tools/gex` | Authenticated session + active broker | `frontend/src/App.tsx:350` |  |
| `/tools/straddles-strangle-chain` | Authenticated session + active broker | `frontend/src/App.tsx:360` |  |
| `/tools/strategybuilder` | Authenticated session + active broker | `frontend/src/App.tsx:370` |  |
| `/tools/strategyportfolio` | Authenticated session + active broker | `frontend/src/App.tsx:380` |  |
| `/tools/futures-risk` | Authenticated session + active broker | `frontend/src/App.tsx:390` |  |
| `/tools/futures-risk/admin` | Authenticated session + active broker | `frontend/src/App.tsx:400` | Route requires broker; page and mutation APIs enforce admin behavior separately |
| `/tools/futures-risk/card-demo` | Authenticated session + active broker | `frontend/src/App.tsx:410` | Source-defined UI demonstration route |
| `/strategy` | Authenticated session + active broker | `frontend/src/App.tsx:420` |  |
| `/strategy/new` | Authenticated session + active broker | `frontend/src/App.tsx:430` |  |
| `/strategy/:id` | Authenticated session + active broker | `frontend/src/App.tsx:440` |  |
| `/strategy/:id/edit` | Authenticated session + active broker | `frontend/src/App.tsx:450` |  |
| `*` | Public | `frontend/src/App.tsx:462` | Catch-all not-found page |
