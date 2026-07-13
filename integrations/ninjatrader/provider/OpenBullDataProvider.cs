// Native NinjaTrader 8 data-provider adapter for OpenBull.
//
// Compile this file together with ../addons/OpenBullLiveDataClient.cs into
// OpenBull.NativeProvider.dll and place that DLL in NinjaTrader's
// bin\Custom folder.  It is intentionally data-only: OpenBull continues to
// own broker authentication and order routing.

using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.Linq;
using NinjaTrader.Adapter;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.AddOns;
using NinjaTrader.NinjaScript.Adapters;

namespace OpenBull.NinjaTrader
{
    /// <summary>Connection definition shown in NinjaTrader's Connections menu.</summary>
    public sealed class OpenBullConnectOptions : CustomConnectOptions
    {
        public OpenBullConnectOptions()
        {
            CanManageOrders = false;
            IsPasswordRequiredOnStartup = true;
            Name = "OpenBull";
            Provider = Provider.Custom40;
            StreamUrl = "ws://127.0.0.1:8765";
        }

        public override Type AdapterClassType { get { return typeof(OpenBullDataAdapter); } }
        public override string AssemblyName { get { return "OpenBull.NativeProvider"; } }
        public override string BrandName { get { return "OpenBull"; } }
        public override bool IsDataProviderOnly { get { return true; } }

        [Display(Name = "OpenBull WebSocket URL", GroupName = "Connection", Order = 10)]
        public string StreamUrl { get; set; }

        [Display(Name = "Symbol mappings", GroupName = "Connection", Order = 20,
            Description = "Optional: NT symbol=NFO:DhanSymbol; separated by semicolons. Required for F&O and MCX contracts whose NinjaTrader names differ from Dhan.")]
        public string SymbolMappings { get; set; }
    }

    /// <summary>
    /// Data-only native connection. NinjaTrader asks this adapter to subscribe
    /// to a chart instrument; the adapter turns that into one pooled OpenBull
    /// WebSocket subscription and forwards Last ticks back through the native
    /// market-data callback.
    /// </summary>
    public sealed class OpenBullDataAdapter : AdapterBase, IAdapter, IDisposable
    {
        private readonly object sync = new object();
        private readonly Dictionary<string, Subscription> subscriptions = new Dictionary<string, Subscription>();
        private IConnection connection;
        private OpenBullConnectOptions options;
        private OpenBullLiveDataClient stream;
        private bool disposed;

        public void Connect(IConnection value)
        {
            connection = value;
            options = value == null ? null : value.Options as OpenBullConnectOptions;
            if (options == null || String.IsNullOrWhiteSpace(options.StreamUrl) || String.IsNullOrWhiteSpace(options.Password))
            {
                Status(ConnectionStatus.Disconnected, ErrorCode.LogOnFailed, "Set OpenBull WebSocket URL and API key (Password) in the connection settings.");
                return;
            }

            Status(ConnectionStatus.Connecting, ErrorCode.NoError, "Connecting to OpenBull");
            try
            {
                stream = new OpenBullLiveDataClient(options.StreamUrl, options.Password, OnTick, OnStreamState);
            }
            catch (Exception ex)
            {
                Status(ConnectionStatus.Disconnected, ErrorCode.LogOnFailed, ex.Message);
            }
        }

        public void Disconnect()
        {
            if (stream != null)
            {
                stream.Dispose();
                stream = null;
            }
            lock (sync) subscriptions.Clear();
            Status(ConnectionStatus.Disconnected, ErrorCode.NoError, "Disconnected");
        }

        public void Dispose()
        {
            if (disposed) return;
            disposed = true;
            Disconnect();
        }

        public void SubscribeMarketData(Instrument instrument, Action<MarketDataType, double, long, DateTime, long> callback)
        {
            OpenBullLiveSymbol symbol;
            if (!TryMap(instrument, out symbol))
                return;
            lock (sync)
                subscriptions[symbol.Key] = new Subscription(instrument, symbol, callback);
            SyncSubscriptions();
        }

        public void UnsubscribeMarketData(Instrument instrument)
        {
            lock (sync)
            {
                foreach (string key in subscriptions.Where(pair => Object.ReferenceEquals(pair.Value.Instrument, instrument)).Select(pair => pair.Key).ToArray())
                    subscriptions.Remove(key);
            }
            SyncSubscriptions();
        }

        public void SubscribeMarketDepth(Instrument instrument, Action<int, string, Operation, MarketDataType, double, long, DateTime> callback)
        {
            // OpenBull subscribes at quote level. Last, bid and ask are sent
            // through the L1 callback; Dhan depth can be added without
            // changing the native connection contract.
            SubscribeMarketData(instrument, delegate { });
        }

        public void UnsubscribeMarketDepth(Instrument instrument) { UnsubscribeMarketData(instrument); }
        public void SubscribeFundamentalData(Instrument instrument, Action<FundamentalDataType, object> callback) { }
        public void UnsubscribeFundamentalData(Instrument instrument) { }
        public void SubscribeAccount(Account account) { }
        public void UnsubscribeAccount(Account account) { }
        public void SubscribeHotlist(Hotlist hotlist, Action callback) { }
        public void UnsubscribeHotlist(Hotlist hotlist) { }
        public void SubscribeNews() { }
        public void UnsubscribeNews() { }
        public void Cancel(Order[] orders) { }
        public void Change(Order[] orders) { }
        public void Submit(Order[] orders) { }

        public void ResolveInstrument(Instrument instrument, Action<Instrument, ErrorCode, string> callback)
        {
            if (callback != null) callback(instrument, ErrorCode.NoError, String.Empty);
        }

        public void RequestBars(IBars bars, Action<IBars, ErrorCode, string> callback, global::NinjaTrader.Core.IProgress progress)
        {
            if (callback != null)
                callback(bars, ErrorCode.Panic, "OpenBull native connection currently supplies realtime data only.");
        }

        public void RequestHotlistNames(Action<string[], ErrorCode, string> callback)
        {
            if (callback != null) callback(new string[0], ErrorCode.NoError, String.Empty);
        }

        private void OnStreamState(string message, bool healthy)
        {
            if (healthy && message.IndexOf("authenticated", StringComparison.OrdinalIgnoreCase) >= 0)
                Status(ConnectionStatus.Connected, ErrorCode.NoError, "OpenBull live data connected");
            else if (!healthy)
                Status(ConnectionStatus.ConnectionLost, ErrorCode.NoError, message);
        }

        private void OnTick(OpenBullLiveTick tick)
        {
            if (tick == null || tick.Ltp <= 0) return;
            Subscription subscription;
            string key = (tick.Exchange ?? String.Empty).ToUpperInvariant() + ":" + (tick.Symbol ?? String.Empty).ToUpperInvariant();
            lock (sync) subscriptions.TryGetValue(key, out subscription);
            if (subscription != null && subscription.Callback != null)
                subscription.Callback(MarketDataType.Last, tick.Ltp, 0, tick.ReceivedUtc.ToLocalTime(), 0);
        }

        private void SyncSubscriptions()
        {
            OpenBullLiveDataClient client = stream;
            if (client == null) return;
            List<OpenBullLiveSymbol> symbols;
            lock (sync) symbols = subscriptions.Values.Select(value => value.Symbol).ToList();
            client.UpdateSymbols(symbols);
        }

        private bool TryMap(Instrument instrument, out OpenBullLiveSymbol result)
        {
            result = null;
            if (instrument == null) return false;
            string nativeSymbol = instrument.FullName ?? String.Empty;
            string configured = LookupMapping(nativeSymbol, instrument.MasterInstrument == null ? String.Empty : instrument.MasterInstrument.Name);
            if (!String.IsNullOrWhiteSpace(configured))
            {
                int separator = configured.IndexOf(':');
                if (separator > 0 && separator < configured.Length - 1)
                {
                    result = new OpenBullLiveSymbol(configured.Substring(separator + 1), configured.Substring(0, separator));
                    return true;
                }
            }

            string symbol = nativeSymbol.Replace(" ", String.Empty).ToUpperInvariant();
            if (String.IsNullOrWhiteSpace(symbol)) return false;
            string exchange = instrument.Exchange == Exchange.Nse ? "NSE" : instrument.Exchange == Exchange.Bse ? "BSE" : "NSE";
            if (symbol.EndsWith("FUT", StringComparison.OrdinalIgnoreCase) || symbol.EndsWith("CE", StringComparison.OrdinalIgnoreCase) || symbol.EndsWith("PE", StringComparison.OrdinalIgnoreCase))
                exchange = "NFO";
            result = new OpenBullLiveSymbol(symbol, exchange);
            return true;
        }

        private string LookupMapping(string fullName, string masterName)
        {
            foreach (string entry in (options == null ? String.Empty : options.SymbolMappings ?? String.Empty).Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries))
            {
                string[] pair = entry.Split(new[] { '=' }, 2);
                if (pair.Length != 2) continue;
                string left = pair[0].Trim();
                if (String.Equals(left, fullName, StringComparison.OrdinalIgnoreCase) || String.Equals(left, masterName, StringComparison.OrdinalIgnoreCase))
                    return pair[1].Trim();
            }
            return String.Empty;
        }

        private void Status(ConnectionStatus status, ErrorCode error, string message)
        {
            if (connection != null)
                connection.ConnectionStatusCallback(status, status, error, message ?? String.Empty);
        }

        private sealed class Subscription
        {
            public readonly Instrument Instrument;
            public readonly OpenBullLiveSymbol Symbol;
            public readonly Action<MarketDataType, double, long, DateTime, long> Callback;
            public Subscription(Instrument instrument, OpenBullLiveSymbol symbol, Action<MarketDataType, double, long, DateTime, long> callback)
            {
                Instrument = instrument; Symbol = symbol; Callback = callback;
            }
        }
    }
}
