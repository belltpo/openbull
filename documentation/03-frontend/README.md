# 3. Frontend Documentation

## Stack

- React 19 and TypeScript 6 in Vite 8.
- React Router 7 for browser routing.
- TanStack Query 5 for server state, caching, invalidation, and mutations.
- Axios for HTTP with credentials.
- Tailwind CSS 4, shadcn/Base UI primitives, Geist font, Lucide icons, and Sonner toasts.
- Plotly and lightweight-charts for analytics and historical/live charts.

Exact versions are defined in `frontend/package.json` and locked in `frontend/package-lock.json`.

## Provider composition

`frontend/src/App.tsx` wraps the application in this order:

1. `QueryClientProvider`
2. `ThemeProvider`
3. `BrowserRouter`
4. `AuthProvider`
5. route-chunk preloader
6. `TradingModeProvider`
7. route tree and global toaster

Default queries retry once, do not refetch on focus, remain fresh for 30 seconds, and remain in the cache for 30 minutes unless a feature overrides those values.

## Routing and access

The generated [frontend route inventory](../inventories/frontend-routes.md) is the complete current list. `ProtectedRoute` enforces a valid browser session and optionally an active broker. Admin-only mutations are enforced by backend endpoints; hiding a button is only a usability measure.

Heavy analytics, futures-risk, strategy, and playground routes are lazy loaded. Frequently used route chunks are preloaded after authentication, while the remaining analytics chunks are loaded during browser idle time.

## State management

| State | Owner | Persistence/refresh |
|---|---|---|
| Current user/session | `AuthContext` + query `['auth','me']` | HttpOnly cookie; five-minute query freshness |
| Live/sandbox mode | `TradingModeContext` | Backend `app_settings`; 30-second query freshness; mode-sensitive queries invalidated after change |
| Light/dark theme | `ThemeContext` | `localStorage.theme` and document class |
| Server data | TanStack Query in pages/hooks | Query-specific keys and invalidation |
| Live ticks | `useMarketData` | Per-hook `Map<exchange:symbol, tick>`; reconnect/reauth/replay |
| Form/dialog state | Component-local React state | Page/dialog lifetime unless explicitly saved |

## HTTP integration

`frontend/src/config/api.ts` creates one same-origin Axios client with cookies and JSON headers. It detects structured broker issues and redirects unauthenticated protected pages to `/login`. Page-specific wrappers live under `frontend/src/api/`; shared TypeScript contracts live under `frontend/src/types/`.

## Real-time integration

`useMarketData` obtains the public WebSocket URL and the current user's OpenBull API key through cookie-authenticated helper endpoints. It then:

1. Opens the WebSocket.
2. Sends `authenticate` with the OpenBull API key.
3. Subscribes to desired symbols after the acknowledgement.
4. Merges normalized ticks into a map.
5. Sends incremental subscribe/unsubscribe changes.
6. Reconnects with exponential backoff and replays current demand.
7. Converts broker-auth failures to an actionable broker-configuration notification.

## Component organization

- `components/ui`: reusable primitives; business rules should not be added here.
- `components/layout`: navigation, mode switch/banner, master-contract state, global quick-order affordances.
- `components/trading`: reusable order/basket/modify dialogs and underlying picker.
- `components/charts`: Plotly wrappers and chart error boundaries.
- `components/strategy-builder` and `strategy-portfolio`: legacy analytical strategy feature.
- `components/futures-risk`: trade cards, history/timeline, modify/exit/order dialogs.
- `components/playground`: API/WebSocket tester.

See [component and data-flow guide](components-and-data-flow.md) and the [page catalogue](page-catalogue.md).

## Frontend development

```powershell
cd D:\openbull\frontend
npm ci
npm run dev
npm run lint
npm run build
```

Do not commit `dist/` or `node_modules/`. Keep API DTOs aligned with backend schemas and include query invalidation when a mutation changes visible state.
