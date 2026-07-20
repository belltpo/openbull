> Generated from the matching in-repository API guide and redacted by `documentation/tools/generate_reference.py`. Verify its route/schema against the generated OpenAPI contract for this commit.

# PlaceOrder

Place a new order with the broker.

## Endpoint URL

```http
POST http://127.0.0.1:8000/api/v1/placeorder
```

## Sample API Request (Market Order)

```json
{
  "apikey": "${OPENBULL_API_KEY}",
  "strategy": "Python",
  "symbol": "INFY",
  "action": "BUY",
  "exchange": "NSE",
  "pricetype": "MARKET",
  "product": "MIS",
  "quantity": "1"
}
```

## Sample API Response

```json
{
  "orderid": "260415000382402",
  "status": "success"
}
```

## Sample API Request (Limit Order)

```json
{
  "apikey": "${OPENBULL_API_KEY}",
  "strategy": "Python",
  "symbol": "INFY",
  "action": "BUY",
  "exchange": "NSE",
  "pricetype": "LIMIT",
  "product": "MIS",
  "quantity": "1",
  "price": "1500",
  "trigger_price": "0",
  "disclosed_quantity": "0"
}
```

## Sample API Request (Stop-Loss Order)

```json
{
  "apikey": "${OPENBULL_API_KEY}",
  "strategy": "Python",
  "symbol": "RELIANCE",
  "action": "SELL",
  "exchange": "NSE",
  "pricetype": "SL",
  "product": "MIS",
  "quantity": "1",
  "price": "1180",
  "trigger_price": "1185"
}
```

## Request Body

| Parameter | Description | Mandatory/Optional | Default Value |
|-----------|-------------|-------------------|---------------|
| apikey | Your OpenBull API key | Mandatory | - |
| strategy | Strategy identifier for tracking | Mandatory | - |
| symbol | Trading symbol (e.g., RELIANCE, NIFTY28APR26FUT) | Mandatory | - |
| action | Order action: BUY or SELL | Mandatory | - |
| exchange | Exchange code: NSE, BSE, NFO, BFO, CDS, BCD, MCX, NCDEX | Mandatory | - |
| pricetype | Price type: MARKET, LIMIT, SL, SL-M | Mandatory | - |
| product | Product type: MIS, CNC, NRML | Mandatory | - |
| quantity | Order quantity | Mandatory | - |
| price | Order price (required for LIMIT and SL orders) | Optional | 0 |
| trigger_price | Trigger price (required for SL and SL-M orders) | Optional | 0 |
| disclosed_quantity | Disclosed quantity for iceberg orders | Optional | 0 |

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| status | string | "success" or "error" |
| orderid | string | Unique order ID from broker (on success) |
| message | string | Error message (on error) |

## Notes

- For **MARKET** orders, price and trigger_price are not required
- For **LIMIT** orders, price is required
- For **SL** (Stop-Loss Limit) orders, both price and trigger_price are required
- For **SL-M** (Stop-Loss Market) orders, only trigger_price is required
- The **symbol** must be in OpenBull standard format:
  - Equity: `RELIANCE`
  - Futures: `NIFTY28APR26FUT`
  - Options: `NIFTY28APR2624250CE`
- Use **MIS** for intraday, **CNC** for equity delivery, **NRML** for F&O overnight positions

---

**Back to**: [API Documentation](../README.md)
