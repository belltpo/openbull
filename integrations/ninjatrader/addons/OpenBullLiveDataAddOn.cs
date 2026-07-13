// Standalone OpenBull Live Data AddOn for NinjaTrader 8.
// Install this file in NinjaTrader's Custom\AddOns folder, then compile in
// NinjaTrader. It is independent of every OpenBull indicator and strategy.

using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Linq;
using System.Net.WebSockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Media;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;

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
    /// Maintains one authenticated OpenBull WebSocket connection for the
    /// standalone Live Data AddOn window.
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

    /// <summary>
    /// Adds a standalone <c>New &gt; OpenBull Live Data</c> menu entry to the
    /// NinjaTrader Control Center. It displays live Dhan ticks obtained only
    /// through the local OpenBull WebSocket proxy; it does not touch charts,
    /// indicators, strategies, accounts, or order routing.
    /// </summary>
    public sealed class OpenBullLiveDataAddOn : AddOnBase
    {
        private NTMenuItem menuItem;
        private NTMenuItem parentMenuItem;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "OpenBull Live Data";
                Description = "Standalone OpenBull live-market-data monitor.";
            }
        }

        protected override void OnWindowCreated(Window window)
        {
            ControlCenter controlCenter = window as ControlCenter;
            if (controlCenter == null || menuItem != null)
                return;

            parentMenuItem = controlCenter.FindFirst("ControlCenterMenuItemNew") as NTMenuItem;
            if (parentMenuItem == null)
                return;

            menuItem = new NTMenuItem
            {
                Header = "OpenBull Live Data",
                Style = Application.Current.TryFindResource("MainMenuItem") as Style,
            };
            menuItem.Click += OnMenuItemClick;
            parentMenuItem.Items.Add(menuItem);
        }

        protected override void OnWindowDestroyed(Window window)
        {
            if (menuItem == null)
                return;
            menuItem.Click -= OnMenuItemClick;
            if (parentMenuItem != null)
                parentMenuItem.Items.Remove(menuItem);
            menuItem = null;
            parentMenuItem = null;
        }

        private void OnMenuItemClick(object sender, RoutedEventArgs e)
        {
            NinjaTrader.Core.Globals.RandomDispatcher.InvokeAsync(
                new Action(() => new OpenBullLiveDataWindow().Show()));
        }
    }

    /// <summary>Independent window for OpenBull quote subscriptions.</summary>
    public sealed class OpenBullLiveDataWindow : NTWindow
    {
        private readonly ObservableCollection<OpenBullLiveQuote> quotes = new ObservableCollection<OpenBullLiveQuote>();
        private readonly Dictionary<string, OpenBullLiveQuote> quotesByKey = new Dictionary<string, OpenBullLiveQuote>();
        private TextBox streamUrlBox;
        private PasswordBox apiKeyBox;
        private TextBox symbolsBox;
        private TextBlock statusText;
        private Button connectButton;
        private Button disconnectButton;
        private OpenBullLiveDataClient client;

        public OpenBullLiveDataWindow()
        {
            Caption = "OpenBull Live Data";
            Width = 820;
            Height = 580;
            MinWidth = 640;
            MinHeight = 420;
            Content = BuildContent();
            Closed += (sender, args) => Disconnect();
        }

        private Grid BuildContent()
        {
            Grid root = new Grid { Margin = new Thickness(12) };
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(72) });
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

            TextBlock info = new TextBlock
            {
                Text = "Standalone OpenBull live quote monitor. Enter exact Dhan symbols as EXCHANGE:SYMBOL, one per line.",
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(0, 0, 0, 10),
            };
            Grid.SetRow(info, 0);
            root.Children.Add(info);

            Grid connection = new Grid { Margin = new Thickness(0, 0, 0, 8) };
            connection.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            connection.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            connection.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            connection.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(200) });
            connection.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

            connection.Children.Add(Label("WebSocket URL", 0, 0));
            streamUrlBox = new TextBox { Text = "ws://127.0.0.1:8765", Margin = new Thickness(8, 0, 16, 0) };
            Grid.SetColumn(streamUrlBox, 1);
            connection.Children.Add(streamUrlBox);
            connection.Children.Add(Label("OpenBull API key", 2, 0));
            apiKeyBox = new PasswordBox { Margin = new Thickness(8, 0, 0, 0) };
            Grid.SetColumn(apiKeyBox, 3);
            connection.Children.Add(apiKeyBox);
            Grid.SetRow(connection, 1);
            root.Children.Add(connection);

            symbolsBox = new TextBox
            {
                AcceptsReturn = true,
                TextWrapping = TextWrapping.NoWrap,
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
                Text = "MCX:CRUDEOIL20JUL26FUT",
                ToolTip = "One exact Dhan symbol per line, for example: MCX:CRUDEOIL20JUL26FUT or NSE_INDEX:NIFTY",
            };
            Grid.SetRow(symbolsBox, 2);
            root.Children.Add(symbolsBox);

            Grid actions = new Grid { Margin = new Thickness(0, 10, 0, 10) };
            actions.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            actions.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            actions.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            connectButton = new Button { Content = "Connect", MinWidth = 90, Margin = new Thickness(0, 0, 8, 0) };
            connectButton.Click += (sender, args) => Connect();
            actions.Children.Add(connectButton);
            disconnectButton = new Button { Content = "Disconnect", MinWidth = 90, IsEnabled = false };
            disconnectButton.Click += (sender, args) => Disconnect();
            Grid.SetColumn(disconnectButton, 1);
            actions.Children.Add(disconnectButton);
            statusText = new TextBlock { Text = "Disconnected", VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(14, 0, 0, 0) };
            Grid.SetColumn(statusText, 2);
            actions.Children.Add(statusText);
            Grid.SetRow(actions, 3);
            root.Children.Add(actions);

            DataGrid quoteGrid = new DataGrid
            {
                ItemsSource = quotes,
                AutoGenerateColumns = false,
                CanUserAddRows = false,
                CanUserDeleteRows = false,
                IsReadOnly = true,
            };
            quoteGrid.Columns.Add(new DataGridTextColumn { Header = "Exchange", Binding = new Binding("Exchange") });
            quoteGrid.Columns.Add(new DataGridTextColumn { Header = "Symbol", Binding = new Binding("Symbol") });
            quoteGrid.Columns.Add(new DataGridTextColumn { Header = "LTP", Binding = new Binding("Ltp") { StringFormat = "N2" } });
            quoteGrid.Columns.Add(new DataGridTextColumn { Header = "Mode", Binding = new Binding("Mode") });
            quoteGrid.Columns.Add(new DataGridTextColumn { Header = "Updated (local)", Binding = new Binding("UpdatedLocal") { StringFormat = "HH:mm:ss.fff" } });
            Grid.SetRow(quoteGrid, 4);
            root.Children.Add(quoteGrid);
            return root;
        }

        private static Label Label(string text, int column, int row)
        {
            Label label = new Label { Content = text, VerticalContentAlignment = VerticalAlignment.Center, Padding = new Thickness(0) };
            Grid.SetColumn(label, column);
            Grid.SetRow(label, row);
            return label;
        }

        private void Connect()
        {
            Uri endpoint;
            if (!Uri.TryCreate(streamUrlBox.Text.Trim(), UriKind.Absolute, out endpoint) || (endpoint.Scheme != "ws" && endpoint.Scheme != "wss"))
            {
                SetStatus("Enter a valid ws:// or wss:// OpenBull URL.", false);
                return;
            }
            if (string.IsNullOrWhiteSpace(apiKeyBox.Password))
            {
                SetStatus("OpenBull API key is required.", false);
                return;
            }

            List<OpenBullLiveSymbol> symbols = ParseSymbols(symbolsBox.Text);
            if (symbols.Count == 0)
            {
                SetStatus("Add at least one symbol as EXCHANGE:SYMBOL.", false);
                return;
            }

            Disconnect();
            quotes.Clear();
            quotesByKey.Clear();
            client = new OpenBullLiveDataClient(endpoint.AbsoluteUri, apiKeyBox.Password, OnTick, OnState);
            client.UpdateSymbols(symbols);
            connectButton.IsEnabled = false;
            disconnectButton.IsEnabled = true;
            SetStatus("Connecting to OpenBull…", true);
        }

        private void Disconnect()
        {
            if (client != null)
            {
                client.Dispose();
                client = null;
            }
            if (connectButton != null) connectButton.IsEnabled = true;
            if (disconnectButton != null) disconnectButton.IsEnabled = false;
            if (statusText != null) SetStatus("Disconnected", false);
        }

        private static List<OpenBullLiveSymbol> ParseSymbols(string text)
        {
            Dictionary<string, OpenBullLiveSymbol> result = new Dictionary<string, OpenBullLiveSymbol>();
            foreach (string raw in (text ?? "").Replace(";", "\n").Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries))
            {
                string value = raw.Trim();
                int separator = value.IndexOf(':');
                if (separator <= 0 || separator == value.Length - 1)
                    continue;
                OpenBullLiveSymbol symbol = new OpenBullLiveSymbol(value.Substring(separator + 1).Trim(), value.Substring(0, separator).Trim());
                if (!string.IsNullOrWhiteSpace(symbol.Symbol) && !string.IsNullOrWhiteSpace(symbol.Exchange))
                    result[symbol.Key] = symbol;
            }
            return result.Values.ToList();
        }

        private void OnTick(OpenBullLiveTick tick)
        {
            if (tick == null || tick.Ltp <= 0)
                return;
            Dispatcher.BeginInvoke(new Action(() =>
            {
                string key = (tick.Exchange ?? "").ToUpperInvariant() + ":" + (tick.Symbol ?? "").ToUpperInvariant();
                OpenBullLiveQuote quote;
                if (!quotesByKey.TryGetValue(key, out quote))
                {
                    quote = new OpenBullLiveQuote { Exchange = tick.Exchange, Symbol = tick.Symbol };
                    quotesByKey[key] = quote;
                    quotes.Add(quote);
                }
                quote.Ltp = tick.Ltp;
                quote.Mode = tick.Mode;
                quote.UpdatedLocal = tick.ReceivedUtc.ToLocalTime();
            }));
        }

        private void OnState(string message, bool healthy)
        {
            Dispatcher.BeginInvoke(new Action(() => SetStatus(message, healthy)));
        }

        private void SetStatus(string message, bool healthy)
        {
            statusText.Text = message ?? "";
            statusText.Foreground = healthy ? Brushes.ForestGreen : Brushes.IndianRed;
        }
    }

    public sealed class OpenBullLiveQuote : INotifyPropertyChanged
    {
        private double ltp;
        private string mode;
        private DateTime updatedLocal;

        public string Exchange { get; set; }
        public string Symbol { get; set; }
        public double Ltp { get { return ltp; } set { ltp = value; Changed("Ltp"); } }
        public string Mode { get { return mode; } set { mode = value; Changed("Mode"); } }
        public DateTime UpdatedLocal { get { return updatedLocal; } set { updatedLocal = value; Changed("UpdatedLocal"); } }

        public event PropertyChangedEventHandler PropertyChanged;
        private void Changed(string property)
        {
            PropertyChangedEventHandler handler = PropertyChanged;
            if (handler != null) handler(this, new PropertyChangedEventArgs(property));
        }
    }
}
