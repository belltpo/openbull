// Standalone OpenBull Live Data AddOn for NinjaTrader 8.
// Install this file in NinjaTrader's Custom\AddOns folder, then compile in
// NinjaTrader. It is independent of every OpenBull indicator and strategy.

using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Reflection;
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
using WpfLine = System.Windows.Shapes.Line;
using WpfRectangle = System.Windows.Shapes.Rectangle;
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
    /// Late-bound wrapper around NinjaTrader.Client.dll. Keeping this isolated
    /// lets the AddOn feed NinjaTrader's built-in External Data Feed without a
    /// compile-time DLL reference and without touching indicators, strategies,
    /// accounts, orders, or Quick Order.
    /// </summary>
    internal sealed class NinjaTraderExternalTickSink : IDisposable
    {
        private object client;
        private MethodInfo lastMethod;
        private MethodInfo tearDownMethod;

        public NinjaTraderExternalTickSink()
        {
            Assembly assembly = AppDomain.CurrentDomain.GetAssemblies()
                .FirstOrDefault(item => string.Equals(item.GetName().Name, "NinjaTrader.Client", StringComparison.OrdinalIgnoreCase));
            if (assembly == null)
                assembly = Assembly.LoadFrom(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "NinjaTrader.Client.dll"));

            Type clientType = assembly.GetType("NinjaTrader.Client.Client", true);
            client = Activator.CreateInstance(clientType);
            MethodInfo setUpMethod = clientType.GetMethod("SetUp", new[] { typeof(string), typeof(int) });
            MethodInfo connectedMethod = clientType.GetMethod("Connected", new[] { typeof(int) });
            lastMethod = clientType.GetMethod("Last", new[] { typeof(string), typeof(double), typeof(int) });
            tearDownMethod = clientType.GetMethod("TearDown", Type.EmptyTypes);

            if (setUpMethod == null || connectedMethod == null || lastMethod == null || tearDownMethod == null)
                throw new InvalidOperationException("NinjaTrader Client DLL does not expose the required External Data Feed functions.");
            if (Convert.ToInt32(setUpMethod.Invoke(client, new object[] { "127.0.0.1", 36973 })) != 0 ||
                Convert.ToInt32(connectedMethod.Invoke(client, new object[] { 0 })) != 0)
                throw new InvalidOperationException("External Data Feed is not connected. Connect it before enabling chart delivery.");
        }

        public void SendLast(string externalSymbol, double price)
        {
            if (client == null || string.IsNullOrWhiteSpace(externalSymbol) || price <= 0)
                return;
            int result = Convert.ToInt32(lastMethod.Invoke(client, new object[] { externalSymbol, price, 1 }));
            if (result != 0)
                throw new InvalidOperationException("NinjaTrader rejected tick for " + externalSymbol + ". Check its External symbol map.");
        }

        public void Dispose()
        {
            if (client != null && tearDownMethod != null)
            {
                try { tearDownMethod.Invoke(client, null); } catch { }
            }
            client = null;
            lastMethod = null;
            tearDownMethod = null;
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
        private const string MenuHeader = "OpenBull Live Data";
        private NTMenuItem menuItem;
        private NTMenuItem parentMenuItem;
        private OpenBullLiveDataWindow liveDataWindow;

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

            // NinjaTrader can retain menus from a prior AddOn instance across
            // a NinjaScript recompile. Remove those stale entries before
            // adding this instance's menu item.
            RemoveStaleMenuItems(parentMenuItem);

            menuItem = new NTMenuItem
            {
                Header = MenuHeader,
                Style = Application.Current.TryFindResource("MainMenuItem") as Style,
            };
            menuItem.Click += OnMenuItemClick;
            parentMenuItem.Items.Add(menuItem);
        }

        protected override void OnWindowDestroyed(Window window)
        {
            NTMenuItem item = menuItem;
            NTMenuItem parent = parentMenuItem;
            menuItem = null;
            parentMenuItem = null;
            if (item == null)
                return;

            // OnWindowDestroyed may be called on a different thread than the
            // Control Center. Manipulate WPF controls only on their dispatcher.
            Action remove = () =>
            {
                item.Click -= OnMenuItemClick;
                if (parent != null && parent.Items.Contains(item))
                    parent.Items.Remove(item);
            };
            try
            {
                if (item.Dispatcher.CheckAccess())
                    remove();
                else if (!item.Dispatcher.HasShutdownStarted)
                    item.Dispatcher.BeginInvoke(remove);
            }
            catch (InvalidOperationException)
            {
                // The Control Center is already closing; no cleanup is needed.
            }
        }

        private static void RemoveStaleMenuItems(NTMenuItem parent)
        {
            foreach (object candidate in parent.Items.Cast<object>().ToArray())
            {
                NTMenuItem existing = candidate as NTMenuItem;
                if (existing != null && string.Equals(Convert.ToString(existing.Header), MenuHeader, StringComparison.Ordinal))
                    parent.Items.Remove(existing);
            }
        }

        private void OnMenuItemClick(object sender, RoutedEventArgs e)
        {
            // A menu click already executes on the Control Center UI thread.
            // Creating the NTWindow directly keeps it on the same dispatcher.
            if (liveDataWindow == null || !liveDataWindow.IsVisible)
            {
                liveDataWindow = new OpenBullLiveDataWindow();
                liveDataWindow.Closed += (windowSender, windowArgs) => liveDataWindow = null;
                liveDataWindow.Show();
                return;
            }

            if (liveDataWindow.WindowState == WindowState.Minimized)
                liveDataWindow.WindowState = WindowState.Normal;
            liveDataWindow.Activate();
        }
    }

    /// <summary>
    /// A live-only 1-minute candle display. It deliberately has no historical
    /// data source: candles begin when the first OpenBull tick arrives.
    /// </summary>
    public sealed class OpenBullLiveCandlesWindow : NTWindow
    {
        private sealed class Candle
        {
            public DateTime Time;
            public double Open;
            public double High;
            public double Low;
            public double Close;
        }

        private readonly List<Candle> candles = new List<Candle>();
        private Canvas canvas;
        private TextBlock title;
        private string activeKey;

        public OpenBullLiveCandlesWindow()
        {
            Caption = "OpenBull Live Candles";
            Width = 980;
            Height = 580;
            MinWidth = 640;
            MinHeight = 400;

            Grid root = new Grid { Margin = new Thickness(12) };
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            title = new TextBlock
            {
                Text = "Waiting for OpenBull live ticks...",
                FontWeight = FontWeights.SemiBold,
                Margin = new Thickness(0, 0, 0, 8),
            };
            root.Children.Add(title);
            canvas = new Canvas { Background = Brushes.WhiteSmoke, ClipToBounds = true };
            canvas.SizeChanged += (sender, args) => Draw();
            Grid.SetRow(canvas, 1);
            root.Children.Add(canvas);
            Content = root;
        }

        public void Push(OpenBullLiveTick tick)
        {
            if (tick == null || tick.Ltp <= 0)
                return;

            string key = (tick.Exchange ?? "").ToUpperInvariant() + ":" + (tick.Symbol ?? "").ToUpperInvariant();
            if (string.IsNullOrWhiteSpace(activeKey))
                activeKey = key;
            if (!string.Equals(activeKey, key, StringComparison.Ordinal))
                return;

            DateTime local = tick.ReceivedUtc.ToLocalTime();
            DateTime minute = new DateTime(local.Year, local.Month, local.Day, local.Hour, local.Minute, 0, local.Kind);
            Candle candle = candles.Count == 0 ? null : candles[candles.Count - 1];
            if (candle == null || minute > candle.Time)
            {
                candle = new Candle { Time = minute, Open = tick.Ltp, High = tick.Ltp, Low = tick.Ltp, Close = tick.Ltp };
                candles.Add(candle);
                while (candles.Count > 90)
                    candles.RemoveAt(0);
            }
            else if (minute == candle.Time)
            {
                candle.High = Math.Max(candle.High, tick.Ltp);
                candle.Low = Math.Min(candle.Low, tick.Ltp);
                candle.Close = tick.Ltp;
            }
            else
            {
                return;
            }

            title.Text = activeKey + "  |  Live-only 1-minute candles  |  " + candle.Close.ToString("N2");
            Draw();
        }

        private void Draw()
        {
            if (canvas == null || canvas.ActualWidth < 80 || canvas.ActualHeight < 80)
                return;
            canvas.Children.Clear();
            if (candles.Count == 0)
                return;

            const double left = 54;
            const double right = 62;
            const double top = 16;
            const double bottom = 30;
            double plotWidth = Math.Max(1, canvas.ActualWidth - left - right);
            double plotHeight = Math.Max(1, canvas.ActualHeight - top - bottom);
            double low = candles.Min(item => item.Low);
            double high = candles.Max(item => item.High);
            double padding = Math.Max((high - low) * 0.08, 0.01);
            high += padding;
            low -= padding;
            double range = Math.Max(0.01, high - low);
            Func<double, double> y = price => top + (high - price) / range * plotHeight;

            for (int grid = 0; grid <= 4; grid++)
            {
                double gy = top + plotHeight * grid / 4.0;
                canvas.Children.Add(new WpfLine { X1 = left, X2 = left + plotWidth, Y1 = gy, Y2 = gy, Stroke = Brushes.Gainsboro, StrokeThickness = 1 });
                TextBlock label = new TextBlock { Text = (high - range * grid / 4.0).ToString("N2"), FontSize = 11, Foreground = Brushes.DimGray };
                Canvas.SetLeft(label, left + plotWidth + 5);
                Canvas.SetTop(label, gy - 8);
                canvas.Children.Add(label);
            }

            double step = plotWidth / Math.Max(1, candles.Count);
            double bodyWidth = Math.Max(2, Math.Min(12, step * 0.62));
            for (int index = 0; index < candles.Count; index++)
            {
                Candle candle = candles[index];
                double x = left + step * (index + 0.5);
                Brush color = candle.Close >= candle.Open ? Brushes.ForestGreen : Brushes.Crimson;
                canvas.Children.Add(new WpfLine { X1 = x, X2 = x, Y1 = y(candle.High), Y2 = y(candle.Low), Stroke = color, StrokeThickness = 1 });
                double openY = y(candle.Open);
                double closeY = y(candle.Close);
                WpfRectangle body = new WpfRectangle
                {
                    Width = bodyWidth,
                    Height = Math.Max(1, Math.Abs(closeY - openY)),
                    Fill = color,
                    Stroke = color,
                };
                Canvas.SetLeft(body, x - bodyWidth / 2.0);
                Canvas.SetTop(body, Math.Min(openY, closeY));
                canvas.Children.Add(body);
                if (index % Math.Max(1, candles.Count / 6) == 0)
                {
                    TextBlock time = new TextBlock { Text = candle.Time.ToString("HH:mm"), FontSize = 10, Foreground = Brushes.DimGray };
                    Canvas.SetLeft(time, Math.Max(left, x - 16));
                    Canvas.SetTop(time, top + plotHeight + 4);
                    canvas.Children.Add(time);
                }
            }
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
        private CheckBox feedChartsCheckBox;
        private Button liveCandlesButton;
        private OpenBullLiveDataClient client;
        private NinjaTraderExternalTickSink chartTickSink;
        private string chartTickError;
        private OpenBullLiveCandlesWindow liveCandlesWindow;

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
                Text = "Standalone OpenBull live quote monitor and External Data Feed bridge. Enter exact Dhan symbols as EXCHANGE:SYMBOL, one per line.",
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
            feedChartsCheckBox = new CheckBox
            {
                Content = "Send ticks to NinjaTrader charts",
                IsChecked = true,
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(8, 0, 0, 0),
                ToolTip = "Requires the built-in External Data Feed. The Dhan symbol must match the Instrument's External symbol map.",
            };
            Grid.SetColumn(feedChartsCheckBox, 2);
            actions.Children.Add(feedChartsCheckBox);
            liveCandlesButton = new Button { Content = "Open Live Candles", MinWidth = 125, Margin = new Thickness(8, 0, 0, 0) };
            liveCandlesButton.Click += (sender, args) => OpenLiveCandles();
            Grid.SetColumn(liveCandlesButton, 3);
            actions.Children.Add(liveCandlesButton);
            statusText = new TextBlock { Text = "Disconnected", VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(14, 0, 0, 0) };
            Grid.SetColumn(statusText, 4);
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
            chartTickError = null;
            if (feedChartsCheckBox.IsChecked == true)
            {
                try
                {
                    chartTickSink = new NinjaTraderExternalTickSink();
                }
                catch (Exception ex)
                {
                    chartTickSink = null;
                    SetStatus("Chart delivery disabled: " + ex.Message, false);
                }
            }
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
            if (chartTickSink != null)
            {
                chartTickSink.Dispose();
                chartTickSink = null;
            }
            if (connectButton != null) connectButton.IsEnabled = true;
            if (disconnectButton != null) disconnectButton.IsEnabled = false;
            if (statusText != null) SetStatus("Disconnected", false);
        }

        private void OpenLiveCandles()
        {
            if (liveCandlesWindow == null || !liveCandlesWindow.IsVisible)
            {
                liveCandlesWindow = new OpenBullLiveCandlesWindow();
                liveCandlesWindow.Closed += (sender, args) => liveCandlesWindow = null;
                liveCandlesWindow.Show();
                return;
            }
            if (liveCandlesWindow.WindowState == WindowState.Minimized)
                liveCandlesWindow.WindowState = WindowState.Normal;
            liveCandlesWindow.Activate();
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
            if (chartTickSink != null && chartTickError == null)
            {
                try
                {
                    // Dhan symbol and External map must match, for example
                    // CRUDEOIL20JUL26FUT.
                    chartTickSink.SendLast(tick.Symbol, tick.Ltp);
                }
                catch (Exception ex)
                {
                    chartTickError = ex.Message;
                    Dispatcher.BeginInvoke(new Action(() => SetStatus("Chart delivery stopped: " + chartTickError, false)));
                }
            }
            OpenBullLiveCandlesWindow candles = liveCandlesWindow;
            if (candles != null && candles.IsVisible)
                candles.Dispatcher.BeginInvoke(new Action(() => candles.Push(tick)));
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
