# Known Limitations and Unverified External States

This file records facts that cannot be validated solely from the repository. They must remain explicit rather than being filled with assumptions.

| Area | Current limitation | Required evidence |
|---|---|---|
| Broker availability and entitlements | Provider accounts, subscriptions, segments, tokens, and rate limits are external state. | Provider portal plus sanitized runtime response/log. |
| Live market values | Prices, volume, OI, and market depth are time-dependent. | Timestamped sandbox-safe capture during the relevant market session. |
| Production infrastructure | DNS, TLS, firewall, Cloudflare, database size, backups, and service health differ by server. | Named host audit with secrets removed. |
| Tenant administration | The current source has per-user ownership checks but no tenant entity, tenant membership model, or tenant-admin role. | A future schema and permission implementation is required before a tenant-admin workflow can be documented as available. |
| Runtime screenshots | The isolated capture validates every declared route, labelled sandbox order/position/holding/trade/strategy fixtures, and 17 safe interactions without a provider. It does not claim that fixture prices are live, and it does not submit destructive confirmations or broker orders. | A sanitized entitled provider account is required for timestamped live values and successful/rejected provider outcomes. |
| Frontend static quality | Production build passes, but the current lint gate reports 42 errors and 12 warnings and no frontend unit/E2E suite exists. | Fix lint debt and add automated component/browser coverage. |
