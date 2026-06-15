# OpenBull .NET SDK example

Uses the official [`OpenAlgo.NET`](https://www.nuget.org/packages/OpenAlgo.NET) SDK
(class `OpenAlgo.NET.Api`) to talk to a local **OpenBull** instance. OpenBull mirrors
the OpenAlgo `/api/v1/*` API, so the SDK works against it unchanged — only the host/port differ.

| Setting | OpenAlgo default | OpenBull |
|---|---|---|
| API host  | `http://127.0.0.1:5000` | `http://127.0.0.1:8000` |
| WS proxy  | `8765` | `8765` |

## Prerequisites
- .NET SDK 8.0 (installed)
- OpenBull running (`start-openbull.ps1`)
- An OpenBull **API key** — create an account at http://127.0.0.1:5173/setup, log in, then generate/copy your API key in the app.

## Run
```powershell
$env:OPENBULL_API_KEY = "your_key_here"
dotnet run --project sdk-dotnet
# or:  dotnet run --project sdk-dotnet -- your_key_here
```

## What it does
`Program.cs` initializes the client against OpenBull, then calls `FundsAsync()` and
`QuotesAsync("RELIANCE","NSE")` and prints the JSON. A `PlaceOrderAsync` example is
included but commented out — uncomment to test (toggle OpenBull to **Sandbox** mode first).

## Key SDK surface
```csharp
var client = new Api(apiKey: key, host: "http://127.0.0.1:8000", wsPort: 8765);

await client.FundsAsync();
await client.QuotesAsync("RELIANCE", "NSE");
await client.PlaceOrderAsync(strategy:"CSharp", symbol:"RELIANCE", action:"BUY",
                             exchange:"NSE", priceType:"MARKET", product:"MIS", quantity:1);

// WebSocket streaming
client.Connect();
client.SubscribeLtp(new List<Instrument>{ new(){ Symbol="RELIANCE", Exchange="NSE" } });
```
Every method has a sync version (`Funds()`, `Quotes(...)`) and an async one (`FundsAsync()`, `QuotesAsync(...)`).

Docs: https://docs.openalgo.in/trading-platform/.net
