// OpenBull -> NinjaTrader External Data Feed bridge.
//
// This is a standalone .NET Framework console application. It has no
// NinjaScript, AddOn, indicator, strategy, broker-order, or Quick Order
// dependency. It does two independent jobs:
//   1. exports Dhan 1-minute candles supplied by OpenBull into NinjaTrader's
//      supported historical-import text format;
//   2. sends OpenBull live LTP ticks to NinjaTrader's built-in External Data
//      Feed through NinjaTrader.Client.dll.
//
// Build with build-external-feed.ps1. See README.md in this directory.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net.Http;
using System.Net.WebSockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using NinjaTrader.Client;

namespace OpenBull.ExternalDataFeed
{
    internal sealed class BridgeOptions
    {
        public string ApiKey;
        public string NtInstrument;
        public string DhanSymbol;
        public string Exchange;
        public string OpenBullUrl = "http://127.0.0.1:8000";
        public string StreamUrl = "ws://127.0.0.1:8765";
        public string FromDate;
        public string ToDate;
        public string OutputPath;
        public string NtHost = "127.0.0.1";
        public int NtPort = 36973;
        public bool ExportOnly;
        public bool SkipHistory;

        public static BridgeOptions Parse(string[] args)
        {
            BridgeOptions result = new BridgeOptions();
            for (int index = 0; index < args.Length; index++)
            {
                string name = args[index];
                if (string.Equals(name, "--export-only", StringComparison.OrdinalIgnoreCase))
                {
                    result.ExportOnly = true;
                    continue;
                }
                if (string.Equals(name, "--skip-history", StringComparison.OrdinalIgnoreCase))
                {
                    result.SkipHistory = true;
                    continue;
                }
                if (index + 1 >= args.Length)
                    throw new ArgumentException("Missing value for " + name);
                string value = args[++index];
                switch (name.ToLowerInvariant())
                {
                    case "--api-key": result.ApiKey = value; break;
                    case "--nt-instrument": result.NtInstrument = value; break;
                    case "--symbol": result.DhanSymbol = value; break;
                    case "--exchange": result.Exchange = value; break;
                    case "--openbull-url": result.OpenBullUrl = value.TrimEnd('/'); break;
                    case "--stream-url": result.StreamUrl = value; break;
                    case "--from": result.FromDate = value; break;
                    case "--to": result.ToDate = value; break;
                    case "--output": result.OutputPath = value; break;
                    case "--nt-host": result.NtHost = value; break;
                    case "--nt-port": result.NtPort = int.Parse(value, CultureInfo.InvariantCulture); break;
                    default: throw new ArgumentException("Unknown option " + name);
                }
            }

            Require(result.ApiKey, "--api-key");
            Require(result.NtInstrument, "--nt-instrument");
            Require(result.DhanSymbol, "--symbol");
            Require(result.Exchange, "--exchange");
            if (!result.SkipHistory)
            {
                Require(result.FromDate, "--from");
                Require(result.ToDate, "--to");
                DateTime.ParseExact(result.FromDate, "yyyy-MM-dd", CultureInfo.InvariantCulture);
                DateTime.ParseExact(result.ToDate, "yyyy-MM-dd", CultureInfo.InvariantCulture);
                if (string.IsNullOrWhiteSpace(result.OutputPath))
                {
                    string documents = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
                    result.OutputPath = Path.Combine(documents, "NinjaTrader 8", "import", result.NtInstrument + ".Last.txt");
                }
            }
            return result;
        }

        private static void Require(string value, string name)
        {
            if (string.IsNullOrWhiteSpace(value))
                throw new ArgumentException(name + " is required.");
        }
    }

    internal static class Program
    {
        private static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(45) };
        private static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue };

        private static int Main(string[] args)
        {
            try
            {
                BridgeOptions options = BridgeOptions.Parse(args);
                if (!options.SkipHistory)
                    ExportMinuteHistoryAsync(options).GetAwaiter().GetResult();
                if (options.ExportOnly)
                    return 0;

                using (CancellationTokenSource cancellation = new CancellationTokenSource())
                {
                    Console.CancelKeyPress += (sender, eventArgs) =>
                    {
                        eventArgs.Cancel = true;
                        cancellation.Cancel();
                    };
                    RunLiveFeedAsync(options, cancellation.Token).GetAwaiter().GetResult();
                }
                return 0;
            }
            catch (Exception exception)
            {
                Console.Error.WriteLine("OpenBull External Feed failed: " + exception.Message);
                return 1;
            }
        }

        private static async Task ExportMinuteHistoryAsync(BridgeOptions options)
        {
            Dictionary<string, object> payload = new Dictionary<string, object>
            {
                { "symbol", options.DhanSymbol },
                { "exchange", options.Exchange },
                { "interval", "1m" },
                { "start_date", options.FromDate },
                { "end_date", options.ToDate },
            };
            using (HttpRequestMessage request = new HttpRequestMessage(HttpMethod.Post, options.OpenBullUrl + "/api/v1/history"))
            {
                request.Headers.TryAddWithoutValidation("X-API-KEY", options.ApiKey);
                request.Content = new StringContent(Json.Serialize(payload), Encoding.UTF8, "application/json");
                using (HttpResponseMessage response = await Http.SendAsync(request).ConfigureAwait(false))
                {
                    string responseText = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
                    if (!response.IsSuccessStatusCode)
                        throw new InvalidOperationException("OpenBull history request failed: " + responseText);
                    Dictionary<string, object> root = AsDictionary(Json.DeserializeObject(responseText));
                    if (root == null || !string.Equals(GetString(root, "status"), "success", StringComparison.OrdinalIgnoreCase))
                        throw new InvalidOperationException("OpenBull history response was not successful: " + responseText);
                    IEnumerable candles = root.ContainsKey("data") ? root["data"] as IEnumerable : null;
                    if (candles == null)
                        throw new InvalidOperationException("OpenBull history response did not contain candles.");

                    string directory = Path.GetDirectoryName(options.OutputPath);
                    if (!string.IsNullOrWhiteSpace(directory))
                        Directory.CreateDirectory(directory);
                    int written = 0;
                    using (StreamWriter writer = new StreamWriter(options.OutputPath, false, new UTF8Encoding(false)))
                    {
                        foreach (object item in candles)
                        {
                            Dictionary<string, object> candle = AsDictionary(item);
                            if (candle == null) continue;
                            long timestamp;
                            if (!TryInt64(candle, "timestamp", out timestamp)) continue;
                            double open = GetDouble(candle, "open");
                            double high = GetDouble(candle, "high");
                            double low = GetDouble(candle, "low");
                            double close = GetDouble(candle, "close");
                            if (open <= 0 || high <= 0 || low <= 0 || close <= 0) continue;
                            long volume = Math.Max(0L, GetInt64(candle, "volume"));

                            // Dhan's one-minute timestamp is the start of the
                            // candle. NinjaTrader's end-of-bar import format
                            // needs the close time, expressed in IST.
                            DateTime barEndIst = UnixToIndiaTime(timestamp).AddMinutes(1);
                            writer.WriteLine(
                                barEndIst.ToString("yyyyMMdd HHmmss", CultureInfo.InvariantCulture) + ";" +
                                open.ToString("0.########", CultureInfo.InvariantCulture) + ";" +
                                high.ToString("0.########", CultureInfo.InvariantCulture) + ";" +
                                low.ToString("0.########", CultureInfo.InvariantCulture) + ";" +
                                close.ToString("0.########", CultureInfo.InvariantCulture) + ";" +
                                volume.ToString(CultureInfo.InvariantCulture));
                            written++;
                        }
                    }
                    if (written == 0)
                        throw new InvalidOperationException("Dhan returned no valid one-minute candles for the requested date range.");
                    Console.WriteLine("Exported " + written + " one-minute candles to " + options.OutputPath);
                }
            }
        }

        private static async Task RunLiveFeedAsync(BridgeOptions options, CancellationToken cancellation)
        {
            Client ninjaTrader = new Client();
            if (ninjaTrader.SetUp(options.NtHost, options.NtPort) != 0)
                throw new InvalidOperationException("Could not configure NinjaTrader Client DLL connection.");
            Console.WriteLine("Waiting for NinjaTrader External Data Feed on " + options.NtHost + ":" + options.NtPort + ". Press Ctrl+C to stop.");

            int retrySeconds = 2;
            while (!cancellation.IsCancellationRequested)
            {
                try
                {
                    using (ClientWebSocket socket = new ClientWebSocket())
                    {
                        await socket.ConnectAsync(new Uri(options.StreamUrl), cancellation).ConfigureAwait(false);
                        await SendAsync(socket, "{\"action\":\"authenticate\",\"api_key\":\"" + Escape(options.ApiKey) + "\",\"request_id\":\"nt-external-feed\"}", cancellation).ConfigureAwait(false);
                        bool subscribed = false;
                        retrySeconds = 2;
                        while (!cancellation.IsCancellationRequested && socket.State == WebSocketState.Open)
                        {
                            string message = await ReceiveAsync(socket, cancellation).ConfigureAwait(false);
                            string type = JsonString(message, "type");
                            if (string.Equals(type, "auth", StringComparison.OrdinalIgnoreCase))
                            {
                                if (!string.Equals(JsonString(message, "status"), "success", StringComparison.OrdinalIgnoreCase))
                                    throw new InvalidOperationException("OpenBull WebSocket authentication failed: " + JsonString(message, "message"));
                                await SendAsync(socket, "{\"action\":\"subscribe\",\"mode\":\"LTP\",\"symbols\":[{\"symbol\":\"" + Escape(options.DhanSymbol) + "\",\"exchange\":\"" + Escape(options.Exchange) + "\"}]}", cancellation).ConfigureAwait(false);
                                subscribed = true;
                                Console.WriteLine("OpenBull authenticated; subscribed to " + options.Exchange + ":" + options.DhanSymbol);
                                continue;
                            }
                            if (!subscribed || !string.Equals(type, "market_data", StringComparison.OrdinalIgnoreCase))
                                continue;
                            double ltp;
                            if (!TryJsonDouble(message, "ltp", out ltp) || ltp <= 0)
                                continue;
                            int result = ninjaTrader.Last(options.NtInstrument, ltp, 1);
                            if (result != 0)
                                Console.Error.WriteLine("NinjaTrader rejected tick for " + options.NtInstrument + ". Ensure ATI and External Data Feed are enabled and the External symbol map matches.");
                        }
                    }
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception exception)
                {
                    Console.Error.WriteLine("OpenBull stream reconnecting: " + exception.Message);
                }
                await Task.Delay(TimeSpan.FromSeconds(retrySeconds), cancellation).ConfigureAwait(false);
                retrySeconds = Math.Min(30, retrySeconds * 2);
            }
            ninjaTrader.TearDown();
        }

        private static async Task SendAsync(ClientWebSocket socket, string message, CancellationToken cancellation)
        {
            byte[] bytes = Encoding.UTF8.GetBytes(message);
            await socket.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, cancellation).ConfigureAwait(false);
        }

        private static async Task<string> ReceiveAsync(ClientWebSocket socket, CancellationToken cancellation)
        {
            byte[] buffer = new byte[8192];
            using (MemoryStream stream = new MemoryStream())
            {
                WebSocketReceiveResult result;
                do
                {
                    result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), cancellation).ConfigureAwait(false);
                    if (result.MessageType == WebSocketMessageType.Close)
                        throw new WebSocketException("OpenBull WebSocket closed.");
                    stream.Write(buffer, 0, result.Count);
                }
                while (!result.EndOfMessage);
                return Encoding.UTF8.GetString(stream.ToArray());
            }
        }

        private static Dictionary<string, object> AsDictionary(object value)
        {
            return value as Dictionary<string, object>;
        }

        private static string GetString(Dictionary<string, object> dictionary, string key)
        {
            object value;
            return dictionary != null && dictionary.TryGetValue(key, out value) && value != null ? Convert.ToString(value, CultureInfo.InvariantCulture) : "";
        }

        private static double GetDouble(Dictionary<string, object> dictionary, string key)
        {
            object value;
            if (dictionary != null && dictionary.TryGetValue(key, out value) && value != null)
                return Convert.ToDouble(value, CultureInfo.InvariantCulture);
            return 0;
        }

        private static long GetInt64(Dictionary<string, object> dictionary, string key)
        {
            long value;
            return TryInt64(dictionary, key, out value) ? value : 0;
        }

        private static bool TryInt64(Dictionary<string, object> dictionary, string key, out long result)
        {
            object value;
            if (dictionary != null && dictionary.TryGetValue(key, out value) && value != null)
                return Int64.TryParse(Convert.ToString(value, CultureInfo.InvariantCulture), NumberStyles.Any, CultureInfo.InvariantCulture, out result);
            result = 0;
            return false;
        }

        private static DateTime UnixToIndiaTime(long epochSeconds)
        {
            DateTime utc = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc).AddSeconds(epochSeconds);
            return utc.AddHours(5.5);
        }

        private static string JsonString(string json, string field)
        {
            Match match = Regex.Match(json ?? "", "\\\"" + Regex.Escape(field) + "\\\"\\s*:\\s*\\\"(?<value>(?:\\\\.|[^\\\"])*)\\\"", RegexOptions.IgnoreCase);
            return match.Success ? Regex.Unescape(match.Groups["value"].Value) : "";
        }

        private static bool TryJsonDouble(string json, string field, out double value)
        {
            Match match = Regex.Match(json ?? "", "\\\"" + Regex.Escape(field) + "\\\"\\s*:\\s*(?<value>-?[0-9]+(?:\\.[0-9]+)?)", RegexOptions.IgnoreCase);
            return Double.TryParse(match.Success ? match.Groups["value"].Value : "", NumberStyles.Float, CultureInfo.InvariantCulture, out value);
        }

        private static string Escape(string value)
        {
            return (value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");
        }
    }
}
