using System.Text.Json;
using OpenAlgo.NET;

// ---------------------------------------------------------------------------
// OpenAlgo.NET sample wired to a local OpenBull instance.
//
// OpenBull mirrors the OpenAlgo /api/v1/* API, so this SDK talks to it directly.
// Ports come from OpenBull's .env:  API = 8000, WebSocket proxy = 8765.
//
// Get your API key from the running OpenBull app (Settings / API key page),
// then set it before running:
//   PowerShell:  $env:OPENBULL_API_KEY = "your_key_here"
// or pass it as the first argument:  dotnet run -- your_key_here
// ---------------------------------------------------------------------------

string apiKey = args.Length > 0
    ? args[0]
    : Environment.GetEnvironmentVariable("OPENBULL_API_KEY") ?? "";

if (string.IsNullOrWhiteSpace(apiKey))
{
    Console.WriteLine("No API key. Set OPENBULL_API_KEY or pass it as the first argument.");
    Console.WriteLine("Get the key from the running OpenBull app, then re-run.");
    return;
}

var client = new Api(
    apiKey: apiKey,
    host: "http://127.0.0.1:8000",   // OpenBull backend (OpenAlgo defaults to 5000)
    wsPort: 8765,                    // OpenBull unified WebSocket proxy
    verbose: 1
);

var json = new JsonSerializerOptions { WriteIndented = true };

Console.WriteLine("== OpenBull via OpenAlgo.NET ==\n");

// 1) Account funds
Console.WriteLine("-> Funds()");
var funds = await client.FundsAsync();
Console.WriteLine($"   status: {funds.Status}");
if (!funds.IsSuccess) Console.WriteLine($"   message: {funds.Message}");
Console.WriteLine(JsonSerializer.Serialize(funds, json));

// 2) Live quote
Console.WriteLine("\n-> Quotes(\"RELIANCE\", \"NSE\")");
var quote = await client.QuotesAsync("RELIANCE", "NSE");
Console.WriteLine($"   status: {quote.Status}");
if (!quote.IsSuccess) Console.WriteLine($"   message: {quote.Message}");
Console.WriteLine(JsonSerializer.Serialize(quote, json));

// 3) Place an order — left commented for safety. Uncomment to test (use Sandbox mode!).
// var order = await client.PlaceOrderAsync(
//     strategy: "CSharp",
//     symbol: "RELIANCE",
//     action: "BUY",
//     exchange: "NSE",
//     priceType: "MARKET",
//     product: "MIS",
//     quantity: 1);
// Console.WriteLine($"\nOrder status: {order.Status}, id: {order.OrderId}");

Console.WriteLine("\nDone.");
