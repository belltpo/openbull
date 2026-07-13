// OpenBull live-market-data WebSocket client for NinjaTrader 8.
// Install this file in NinjaTrader's Custom\AddOns folder. The
// OpenBullQuickOrderIndicator in Custom\Indicators references it.

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.WebSockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace NinjaTrader.NinjaScript.AddOns
{
    public sealed class OpenBullLiveSymbol
    {
        public string Symbol { get; private set; }
        public string Exchange { get; private set; }

        public OpenBullLiveSymbol(string symbol, string exchange)
        {
            Symbol = symbol ?? "";
            Exchange = exchange ?? "";
        }

        public string Key
        {
            get { return Exchange.ToUpperInvariant() + ":" + Symbol.ToUpperInvariant(); }
        }
    }

    public sealed class OpenBullLiveTick
    {
        public string Symbol { get; set; }
        public string Exchange { get; set; }
        public string Mode { get; set; }
        public double Ltp { get; set; }
        public DateTime ReceivedUtc { get; set; }
    }

    /// <summary>
    /// Maintains one authenticated OpenBull WebSocket connection for an
    /// indicator instance.  The OpenBull server pools duplicate symbols from
    /// all chart instances before forwarding subscriptions to Dhan.
    /// </summary>
    public sealed class OpenBullLiveDataClient : IDisposable
    {
        private readonly object stateLock = new object();
        private readonly SemaphoreSlim sendLock = new SemaphoreSlim(1, 1);
        private readonly Action<OpenBullLiveTick> onTick;
        private readonly Action<string, bool> onState;
        private readonly CancellationTokenSource cancel = new CancellationTokenSource();
        private readonly Dictionary<string, OpenBullLiveSymbol> desired = new Dictionary<string, OpenBullLiveSymbol>();
        private readonly Dictionary<string, OpenBullLiveSymbol> sent = new Dictionary<string, OpenBullLiveSymbol>();
        private readonly Task runTask;

        private ClientWebSocket socket;
        private string apiKey;
        private Uri endpoint;
        private bool authenticated;
        private bool disposed;
        private DateTime lastTickUtc = DateTime.MinValue;

        public OpenBullLiveDataClient(string streamUrl, string key, Action<OpenBullLiveTick> tickHandler, Action<string, bool> stateHandler)
        {
            endpoint = new Uri(streamUrl);
            apiKey = key ?? "";
            onTick = tickHandler;
            onState = stateHandler;
            runTask = Task.Run((Func<Task>)RunAsync);
        }

        public DateTime LastTickUtc
        {
            get { lock (stateLock) return lastTickUtc; }
        }

        public bool IsLive(TimeSpan staleAfter)
        {
            lock (stateLock)
                return authenticated && lastTickUtc != DateTime.MinValue && DateTime.UtcNow - lastTickUtc <= staleAfter;
        }

        public void UpdateSymbols(IEnumerable<OpenBullLiveSymbol> symbols)
        {
            lock (stateLock)
            {
                desired.Clear();
                foreach (OpenBullLiveSymbol symbol in symbols ?? Enumerable.Empty<OpenBullLiveSymbol>())
                {
                    if (!string.IsNullOrWhiteSpace(symbol.Symbol) && !string.IsNullOrWhiteSpace(symbol.Exchange))
                        desired[symbol.Key] = symbol;
                }
            }
            Task.Run((Func<Task>)SyncSubscriptionsAsync);
        }

        private async Task RunAsync()
        {
            int attempts = 0;
            while (!cancel.IsCancellationRequested)
            {
                try
                {
                    socket = new ClientWebSocket();
                    await socket.ConnectAsync(endpoint, cancel.Token).ConfigureAwait(false);
                    attempts = 0;
                    Notify("OpenBull stream connected; authenticating", true);
                    await SendJsonAsync("{\"action\":\"authenticate\",\"api_key\":\"" + Escape(apiKey) + "\",\"request_id\":\"nt-stream\"}").ConfigureAwait(false);
                    await ReceiveLoopAsync().ConfigureAwait(false);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    Notify("OpenBull stream reconnecting: " + ex.Message, false);
                }
                finally
                {
                    lock (stateLock)
                    {
                        authenticated = false;
                        sent.Clear();
                    }
                    if (socket != null)
                    {
                        socket.Dispose();
                        socket = null;
                    }
                }

                attempts++;
                int delaySeconds = Math.Min(30, Math.Max(2, attempts * 2));
                try
                {
                    await Task.Delay(TimeSpan.FromSeconds(delaySeconds), cancel.Token).ConfigureAwait(false);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
            }
        }

        private async Task ReceiveLoopAsync()
        {
            while (!cancel.IsCancellationRequested && socket != null && socket.State == WebSocketState.Open)
            {
                string message = await ReceiveTextAsync().ConfigureAwait(false);
                if (string.IsNullOrWhiteSpace(message))
                    continue;

                string type = JsonString(message, "type");
                if (string.Equals(type, "auth", StringComparison.OrdinalIgnoreCase))
                {
                    if (string.Equals(JsonString(message, "status"), "success", StringComparison.OrdinalIgnoreCase))
                    {
                        lock (stateLock) authenticated = true;
                        Notify("OpenBull live stream authenticated", true);
                        await SyncSubscriptionsAsync().ConfigureAwait(false);
                    }
                    else
                    {
                        throw new InvalidOperationException("OpenBull stream authentication failed: " + JsonString(message, "message"));
                    }
                    continue;
                }

                if (string.Equals(type, "market_data", StringComparison.OrdinalIgnoreCase))
                {
                    double ltp;
                    if (!TryJsonDouble(message, "ltp", out ltp) || ltp <= 0)
                        continue;
                    OpenBullLiveTick tick = new OpenBullLiveTick
                    {
                        Symbol = JsonString(message, "symbol"),
                        Exchange = JsonString(message, "exchange"),
                        Mode = JsonString(message, "mode"),
                        Ltp = ltp,
                        ReceivedUtc = DateTime.UtcNow,
                    };
                    lock (stateLock) lastTickUtc = tick.ReceivedUtc;
                    if (onTick != null) onTick(tick);
                }
            }
        }

        private async Task SyncSubscriptionsAsync()
        {
            Dictionary<string, OpenBullLiveSymbol> wanted;
            Dictionary<string, OpenBullLiveSymbol> previous;
            lock (stateLock)
            {
                if (!authenticated || socket == null || socket.State != WebSocketState.Open)
                    return;
                wanted = new Dictionary<string, OpenBullLiveSymbol>(desired);
                previous = new Dictionary<string, OpenBullLiveSymbol>(sent);
            }

            List<OpenBullLiveSymbol> removed = previous.Where(pair => !wanted.ContainsKey(pair.Key)).Select(pair => pair.Value).ToList();
            List<OpenBullLiveSymbol> added = wanted.Where(pair => !previous.ContainsKey(pair.Key)).Select(pair => pair.Value).ToList();
            if (removed.Count > 0)
                await SendJsonAsync(BuildSubscriptionMessage("unsubscribe", removed)).ConfigureAwait(false);
            if (added.Count > 0)
                await SendJsonAsync(BuildSubscriptionMessage("subscribe", added)).ConfigureAwait(false);

            lock (stateLock)
            {
                sent.Clear();
                foreach (KeyValuePair<string, OpenBullLiveSymbol> pair in wanted)
                    sent[pair.Key] = pair.Value;
            }
        }

        private async Task SendJsonAsync(string json)
        {
            await sendLock.WaitAsync(cancel.Token).ConfigureAwait(false);
            try
            {
                if (socket == null || socket.State != WebSocketState.Open)
                    return;
                byte[] bytes = Encoding.UTF8.GetBytes(json);
                await socket.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, cancel.Token).ConfigureAwait(false);
            }
            finally
            {
                sendLock.Release();
            }
        }

        private async Task<string> ReceiveTextAsync()
        {
            byte[] buffer = new byte[8192];
            using (MemoryStream stream = new MemoryStream())
            {
                WebSocketReceiveResult result;
                do
                {
                    result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), cancel.Token).ConfigureAwait(false);
                    if (result.MessageType == WebSocketMessageType.Close)
                        throw new WebSocketException("OpenBull stream closed");
                    stream.Write(buffer, 0, result.Count);
                }
                while (!result.EndOfMessage);
                return Encoding.UTF8.GetString(stream.ToArray());
            }
        }

        private static string BuildSubscriptionMessage(string action, IEnumerable<OpenBullLiveSymbol> symbols)
        {
            StringBuilder builder = new StringBuilder("{\"action\":\"").Append(action).Append("\",\"mode\":\"LTP\",\"symbols\":[");
            bool first = true;
            foreach (OpenBullLiveSymbol symbol in symbols)
            {
                if (!first) builder.Append(',');
                first = false;
                builder.Append("{\"symbol\":\"").Append(Escape(symbol.Symbol)).Append("\",\"exchange\":\"").Append(Escape(symbol.Exchange)).Append("\"}");
            }
            return builder.Append("]}").ToString();
        }

        private static string JsonString(string json, string field)
        {
            Match match = Regex.Match(json ?? "", "\\\"" + Regex.Escape(field) + "\\\"\\s*:\\s*\\\"(?<value>(?:\\\\.|[^\\\"])*)\\\"", RegexOptions.IgnoreCase);
            return match.Success ? Regex.Unescape(match.Groups["value"].Value) : "";
        }

        private static bool TryJsonDouble(string json, string field, out double value)
        {
            Match match = Regex.Match(json ?? "", "\\\"" + Regex.Escape(field) + "\\\"\\s*:\\s*(?<value>-?[0-9]+(?:\\.[0-9]+)?)", RegexOptions.IgnoreCase);
            return double.TryParse(match.Success ? match.Groups["value"].Value : "", System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out value);
        }

        private static string Escape(string value)
        {
            return (value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");
        }

        private void Notify(string message, bool healthy)
        {
            if (onState != null) onState(message, healthy);
        }

        public void Dispose()
        {
            if (disposed) return;
            disposed = true;
            cancel.Cancel();
            try { if (socket != null) socket.Abort(); } catch { }
            try { runTask.Wait(TimeSpan.FromSeconds(2)); } catch { }
            if (socket != null) socket.Dispose();
            sendLock.Dispose();
            cancel.Dispose();
        }
    }
}
