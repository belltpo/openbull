#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class OpenBullQuickOrderIndicator : Indicator
    {
        private static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };

        private Grid root;
        private Border popup;
        private Border settingsPanel;
        private TextBlock liveText;
        private TextBlock statusText;
        private Button buyCeButton;
        private Button sellCeButton;
        private Button buyPeButton;
        private Button sellPeButton;
        private bool controlsAdded;
        private bool isBusy;
        private bool wasDragged;
        private bool isDragging;
        private Point dragStart;
        private Thickness dragStartMargin;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "OpenBull Quick Order";
                Description = "Small chart overlay for sending OpenBull Futures-Risk quick orders from NinjaTrader.";
                Calculate = Calculate.OnPriceChange;
                IsOverlay = true;
                DisplayInDataBox = false;
                DrawOnPricePanel = false;
                PaintPriceMarkers = false;
                IsSuspendedWhileInactive = false;

                OpenBullUrl = "http://127.0.0.1:8000";
                ApiKey = "";
                Underlying = "NIFTY";
                UnderlyingExchange = "NSE_INDEX";
                Expiry = "07JUL26";
                CeStrike = 24100;
                PeStrike = 24100;
                Lots = 1;
                SlPoints = 5;
                Product = "NRML";
                TargetTemplateId = 0;
                UseOverrideTargets = false;
                AutoSplitTargets = true;
                Target1Points = 50;
                Target2Points = 100;
                Target3Points = 150;
                Target4Points = 200;
                Target1ExitPct = 25;
                Target2ExitPct = 25;
                Target3ExitPct = 25;
                Target4ExitPct = 25;
            }
            else if (State == State.Historical)
            {
                AddChartControls();
            }
            else if (State == State.Terminated)
            {
                RemoveChartControls();
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 0 || liveText == null || ChartControl == null)
                return;

            double last = Close[0];
            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                if (liveText != null)
                    liveText.Text = string.Format(CultureInfo.InvariantCulture, "{0} FUT  {1:N2}", Underlying, last);
            });
        }

        private void AddChartControls()
        {
            if (ChartControl == null)
                return;

            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                if (controlsAdded)
                    return;

                BuildControls();
                UserControlCollection.Add(root);
                controlsAdded = true;
                CenterPopup();
                if (ChartControl != null)
                    ChartControl.SizeChanged += OnChartSizeChanged;
            });
        }

        private void RemoveChartControls()
        {
            if (ChartControl == null)
                return;

            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                if (ChartControl != null)
                    ChartControl.SizeChanged -= OnChartSizeChanged;
                if (root != null && UserControlCollection.Contains(root))
                    UserControlCollection.Remove(root);
                controlsAdded = false;
                root = null;
            });
        }

        private void OnChartSizeChanged(object sender, SizeChangedEventArgs e)
        {
            if (!wasDragged)
                CenterPopup();
        }

        private void CenterPopup()
        {
            if (root == null || ChartControl == null)
                return;

            double width = Math.Max(0, ChartControl.ActualWidth);
            double left = Math.Max(12, (width - 248) / 2);
            root.Margin = new Thickness(left, 18, 0, 0);
        }

        private void BuildControls()
        {
            root = new Grid
            {
                Width = 248,
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Top,
                Background = Brushes.Transparent
            };

            StackPanel stack = new StackPanel { Orientation = Orientation.Vertical };
            popup = new Border
            {
                CornerRadius = new CornerRadius(10),
                Padding = new Thickness(8),
                Background = new SolidColorBrush(Color.FromArgb(238, 18, 18, 18)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(54, 54, 54)),
                BorderThickness = new Thickness(1),
                Child = stack
            };

            Grid header = new Grid { Margin = new Thickness(0, 0, 0, 5) };
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            header.MouseLeftButtonDown += StartDrag;
            header.MouseMove += DragMove;
            header.MouseLeftButtonUp += StopDrag;

            TextBlock title = new TextBlock
            {
                Text = "OB Quick",
                Foreground = Brushes.White,
                FontWeight = FontWeights.SemiBold,
                FontSize = 12,
                VerticalAlignment = VerticalAlignment.Center
            };
            Grid.SetColumn(title, 0);
            header.Children.Add(title);

            Button settingsButton = IconButton("S");
            settingsButton.Click += (s, e) => ToggleSettings();
            Grid.SetColumn(settingsButton, 1);
            header.Children.Add(settingsButton);

            Button closeButton = IconButton("X");
            closeButton.Click += (s, e) => root.Visibility = Visibility.Collapsed;
            Grid.SetColumn(closeButton, 2);
            header.Children.Add(closeButton);

            TextBlock grip = new TextBlock
            {
                Text = "...",
                Foreground = new SolidColorBrush(Color.FromRgb(130, 130, 130)),
                HorizontalAlignment = HorizontalAlignment.Center,
                FontSize = 11,
                Margin = new Thickness(0, -5, 0, -1)
            };
            grip.MouseLeftButtonDown += StartDrag;
            grip.MouseMove += DragMove;
            grip.MouseLeftButtonUp += StopDrag;
            stack.Children.Add(grip);
            stack.Children.Add(header);

            Border liveBox = new Border
            {
                CornerRadius = new CornerRadius(8),
                Background = new SolidColorBrush(Color.FromRgb(31, 31, 31)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(55, 55, 55)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(8, 6, 8, 6),
                Margin = new Thickness(0, 0, 0, 7)
            };
            Grid liveGrid = new Grid();
            liveGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            liveGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            TextBlock liveLabel = new TextBlock
            {
                Text = "LIVE",
                Foreground = new SolidColorBrush(Color.FromRgb(155, 155, 155)),
                FontSize = 9,
                FontWeight = FontWeights.SemiBold,
                VerticalAlignment = VerticalAlignment.Center
            };
            liveText = new TextBlock
            {
                Text = Underlying + " FUT  --",
                Foreground = Brushes.White,
                FontSize = 11,
                FontWeight = FontWeights.Bold,
                VerticalAlignment = VerticalAlignment.Center
            };
            Grid.SetColumn(liveLabel, 0);
            Grid.SetColumn(liveText, 1);
            liveGrid.Children.Add(liveLabel);
            liveGrid.Children.Add(liveText);
            liveBox.Child = liveGrid;
            stack.Children.Add(liveBox);

            Grid buttons = new Grid();
            buttons.ColumnDefinitions.Add(new ColumnDefinition());
            buttons.ColumnDefinitions.Add(new ColumnDefinition());
            buttons.RowDefinitions.Add(new RowDefinition());
            buttons.RowDefinitions.Add(new RowDefinition());

            buyCeButton = TradeButton("Buy CE", true);
            sellCeButton = TradeButton("Sell CE", false);
            buyPeButton = TradeButton("Buy PE", true);
            sellPeButton = TradeButton("Sell PE", false);
            buyCeButton.Click += async (s, e) => await SendQuickOrderAsync("BUY", "CE");
            sellCeButton.Click += async (s, e) => await SendQuickOrderAsync("SELL", "CE");
            buyPeButton.Click += async (s, e) => await SendQuickOrderAsync("BUY", "PE");
            sellPeButton.Click += async (s, e) => await SendQuickOrderAsync("SELL", "PE");

            AddButton(buttons, buyCeButton, 0, 0);
            AddButton(buttons, sellCeButton, 0, 1);
            AddButton(buttons, buyPeButton, 1, 0);
            AddButton(buttons, sellPeButton, 1, 1);
            stack.Children.Add(buttons);

            statusText = new TextBlock
            {
                Text = "* Ready",
                Foreground = new SolidColorBrush(Color.FromRgb(20, 190, 120)),
                FontSize = 10,
                Margin = new Thickness(1, 6, 0, 0)
            };
            stack.Children.Add(statusText);

            settingsPanel = BuildSettingsPanel();
            settingsPanel.Visibility = Visibility.Collapsed;
            stack.Children.Add(settingsPanel);
            root.Children.Add(popup);
        }

        private Button IconButton(string text)
        {
            return new Button
            {
                Content = text,
                Width = 22,
                Height = 22,
                Margin = new Thickness(3, 0, 0, 0),
                Padding = new Thickness(0),
                Foreground = Brushes.White,
                Background = Brushes.Transparent,
                BorderBrush = Brushes.Transparent,
                FontSize = 12
            };
        }

        private Button TradeButton(string text, bool isBuy)
        {
            string optionType = text.EndsWith("CE", StringComparison.OrdinalIgnoreCase) ? "CE" : "PE";
            double strike = optionType == "CE" ? CeStrike : PeStrike;
            TextBlock content = new TextBlock
            {
                Text = text + "\n" + strike.ToString("0", CultureInfo.InvariantCulture) + " " + optionType,
                TextAlignment = TextAlignment.Center,
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold,
                FontSize = 10,
                LineHeight = 11
            };

            return new Button
            {
                Content = content,
                Height = 40,
                Margin = new Thickness(3),
                Padding = new Thickness(2),
                Background = isBuy
                    ? new SolidColorBrush(Color.FromRgb(0, 132, 88))
                    : new SolidColorBrush(Color.FromRgb(205, 0, 52)),
                BorderBrush = Brushes.Transparent,
                Foreground = Brushes.White
            };
        }

        private static void AddButton(Grid grid, Button button, int row, int column)
        {
            Grid.SetRow(button, row);
            Grid.SetColumn(button, column);
            grid.Children.Add(button);
        }

        private Border BuildSettingsPanel()
        {
            StackPanel stack = new StackPanel { Margin = new Thickness(0, 8, 0, 0) };
            stack.Children.Add(new TextBlock
            {
                Text = "Settings",
                Foreground = Brushes.White,
                FontSize = 11,
                FontWeight = FontWeights.SemiBold,
                Margin = new Thickness(0, 0, 0, 5)
            });
            stack.Children.Add(Field("URL", OpenBullUrl, value => OpenBullUrl = value));
            stack.Children.Add(Field("API Key", ApiKey, value => ApiKey = value));
            stack.Children.Add(Field("Instrument", Underlying, value => Underlying = value.ToUpperInvariant()));
            stack.Children.Add(Field("Expiry", Expiry, value => Expiry = value.ToUpperInvariant()));
            stack.Children.Add(Field("CE", CeStrike.ToString(CultureInfo.InvariantCulture), value => CeStrike = ParseDouble(value, CeStrike)));
            stack.Children.Add(Field("PE", PeStrike.ToString(CultureInfo.InvariantCulture), value => PeStrike = ParseDouble(value, PeStrike)));
            stack.Children.Add(Field("Lots", Lots.ToString(CultureInfo.InvariantCulture), value => Lots = Math.Max(1, ParseInt(value, Lots))));
            stack.Children.Add(Field("SL pts", SlPoints.ToString(CultureInfo.InvariantCulture), value => SlPoints = ParseDouble(value, SlPoints)));
            stack.Children.Add(Field("Template", TargetTemplateId.ToString(CultureInfo.InvariantCulture), value => TargetTemplateId = Math.Max(0, ParseInt(value, TargetTemplateId))));

            return new Border
            {
                CornerRadius = new CornerRadius(8),
                Background = new SolidColorBrush(Color.FromRgb(24, 24, 24)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(55, 55, 55)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(8),
                Child = stack
            };
        }

        private UIElement Field(string label, string value, Action<string> onChanged)
        {
            Grid row = new Grid { Margin = new Thickness(0, 2, 0, 2) };
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(74) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

            TextBlock text = new TextBlock
            {
                Text = label,
                Foreground = new SolidColorBrush(Color.FromRgb(165, 165, 165)),
                FontSize = 10,
                VerticalAlignment = VerticalAlignment.Center
            };
            TextBox box = new TextBox
            {
                Text = value,
                FontSize = 10,
                Height = 23,
                Padding = new Thickness(4, 1, 4, 1),
                Foreground = Brushes.White,
                Background = new SolidColorBrush(Color.FromRgb(10, 10, 10)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(65, 65, 65))
            };
            box.TextChanged += (s, e) =>
            {
                onChanged(box.Text);
                RefreshButtonText();
            };

            Grid.SetColumn(text, 0);
            Grid.SetColumn(box, 1);
            row.Children.Add(text);
            row.Children.Add(box);
            return row;
        }

        private void ToggleSettings()
        {
            if (settingsPanel == null)
                return;
            settingsPanel.Visibility = settingsPanel.Visibility == Visibility.Visible
                ? Visibility.Collapsed
                : Visibility.Visible;
        }

        private void RefreshButtonText()
        {
            SetTradeButtonText(buyCeButton, "Buy CE", CeStrike, "CE");
            SetTradeButtonText(sellCeButton, "Sell CE", CeStrike, "CE");
            SetTradeButtonText(buyPeButton, "Buy PE", PeStrike, "PE");
            SetTradeButtonText(sellPeButton, "Sell PE", PeStrike, "PE");
        }

        private static void SetTradeButtonText(Button button, string label, double strike, string optionType)
        {
            if (button == null)
                return;
            TextBlock text = button.Content as TextBlock;
            if (text != null)
                text.Text = label + "\n" + strike.ToString("0", CultureInfo.InvariantCulture) + " " + optionType;
        }

        private async Task SendQuickOrderAsync(string side, string optionType)
        {
            if (isBusy)
                return;
            if (string.IsNullOrWhiteSpace(ApiKey))
            {
                SetStatus("API key missing", false);
                return;
            }

            isBusy = true;
            SetButtonsEnabled(false);
            SetStatus("Sending " + side + " " + optionType + "...", true);

            try
            {
                string url = OpenBullUrl.TrimEnd('/') + "/api/v1/futures-risk/quick-order";
                string json = BuildQuickOrderJson(side, optionType);
                using (StringContent content = new StringContent(json, Encoding.UTF8, "application/json"))
                {
                    HttpResponseMessage response = await Http.PostAsync(url, content);
                    string body = await response.Content.ReadAsStringAsync();
                    bool ok = response.IsSuccessStatusCode && body.IndexOf("\"status\":\"success\"", StringComparison.OrdinalIgnoreCase) >= 0;
                    SetStatus(ok ? "Order sent" : TrimForStatus(body), ok);
                }
            }
            catch (Exception ex)
            {
                SetStatus(ex.Message, false);
            }
            finally
            {
                isBusy = false;
                SetButtonsEnabled(true);
            }
        }

        private string BuildQuickOrderJson(string side, string optionType)
        {
            double strike = optionType == "CE" ? CeStrike : PeStrike;
            StringBuilder sb = new StringBuilder();
            sb.Append("{");
            JsonString(sb, "apikey", ApiKey, true);
            JsonString(sb, "client_order_id", "nt-" + Guid.NewGuid().ToString("N"), false);
            JsonString(sb, "source", "ninjatrader", false);
            JsonString(sb, "underlying", Underlying, false);
            JsonString(sb, "underlying_exchange", UnderlyingExchange, false);
            JsonString(sb, "expiry", Expiry, false);
            JsonString(sb, "option_type", optionType, false);
            JsonString(sb, "side", side, false);
            JsonString(sb, "product", Product, false);
            JsonNumber(sb, "lots", Lots, false);
            JsonNumber(sb, "strike", strike, false);
            JsonNumber(sb, "sl_points", SlPoints, false);
            if (TargetTemplateId > 0 && !UseOverrideTargets)
                JsonNumber(sb, "target_template_id", TargetTemplateId, false);
            else
                JsonNull(sb, "target_template_id", false);

            sb.Append(",\"targets\":");
            if (UseOverrideTargets)
                AppendTargets(sb);
            else
                sb.Append("null");
            sb.Append("}");
            return sb.ToString();
        }

        private void AppendTargets(StringBuilder sb)
        {
            double[] points = new[] { Target1Points, Target2Points, Target3Points, Target4Points };
            double[] pcts = AutoSplitTargets ? AutoSplit(points) : new[] { Target1ExitPct, Target2ExitPct, Target3ExitPct, Target4ExitPct };
            sb.Append("[");
            bool first = true;
            for (int i = 0; i < points.Length; i++)
            {
                if (points[i] <= 0)
                    continue;
                if (!first)
                    sb.Append(",");
                first = false;
                sb.Append("{");
                JsonNumber(sb, "points", points[i], true);
                JsonNumber(sb, "exit_pct", pcts[i], false);
                sb.Append("}");
            }
            sb.Append("]");
        }

        private static double[] AutoSplit(double[] points)
        {
            double[] pcts = new double[points.Length];
            int active = 0;
            for (int i = 0; i < points.Length; i++)
                if (points[i] > 0)
                    active++;
            if (active == 0)
                return pcts;
            double basePct = Math.Floor((100.0 / active) * 100.0) / 100.0;
            double used = 0;
            int seen = 0;
            for (int i = 0; i < points.Length; i++)
            {
                if (points[i] <= 0)
                    continue;
                seen++;
                pcts[i] = seen == active ? Math.Round(100.0 - used, 2) : basePct;
                used += pcts[i];
            }
            return pcts;
        }

        private static void JsonString(StringBuilder sb, string key, string value, bool first)
        {
            if (!first)
                sb.Append(",");
            sb.Append("\"").Append(Escape(key)).Append("\":\"").Append(Escape(value ?? "")).Append("\"");
        }

        private static void JsonNumber(StringBuilder sb, string key, double value, bool first)
        {
            if (!first)
                sb.Append(",");
            sb.Append("\"").Append(Escape(key)).Append("\":").Append(value.ToString("0.########", CultureInfo.InvariantCulture));
        }

        private static void JsonNull(StringBuilder sb, string key, bool first)
        {
            if (!first)
                sb.Append(",");
            sb.Append("\"").Append(Escape(key)).Append("\":null");
        }

        private static string Escape(string value)
        {
            return (value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");
        }

        private void SetStatus(string message, bool ok)
        {
            if (ChartControl == null)
                return;
            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                if (statusText == null)
                    return;
                statusText.Text = "* " + TrimForStatus(message);
                statusText.Foreground = ok
                    ? new SolidColorBrush(Color.FromRgb(20, 190, 120))
                    : new SolidColorBrush(Color.FromRgb(255, 95, 95));
            });
        }

        private static string TrimForStatus(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return "No response";
            value = value.Replace("\r", " ").Replace("\n", " ").Trim();
            return value.Length > 72 ? value.Substring(0, 72) + "..." : value;
        }

        private void SetButtonsEnabled(bool enabled)
        {
            if (ChartControl == null)
                return;
            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                if (buyCeButton != null) buyCeButton.IsEnabled = enabled;
                if (sellCeButton != null) sellCeButton.IsEnabled = enabled;
                if (buyPeButton != null) buyPeButton.IsEnabled = enabled;
                if (sellPeButton != null) sellPeButton.IsEnabled = enabled;
            });
        }

        private void StartDrag(object sender, MouseButtonEventArgs e)
        {
            if (root == null || ChartControl == null)
                return;
            isDragging = true;
            wasDragged = true;
            dragStart = e.GetPosition(ChartControl);
            dragStartMargin = root.Margin;
            Mouse.Capture(sender as IInputElement);
        }

        private void DragMove(object sender, MouseEventArgs e)
        {
            if (!isDragging || root == null || ChartControl == null)
                return;
            Point pos = e.GetPosition(ChartControl);
            double nextLeft = Math.Max(4, dragStartMargin.Left + pos.X - dragStart.X);
            double nextTop = Math.Max(4, dragStartMargin.Top + pos.Y - dragStart.Y);
            root.Margin = new Thickness(nextLeft, nextTop, 0, 0);
        }

        private void StopDrag(object sender, MouseButtonEventArgs e)
        {
            isDragging = false;
            Mouse.Capture(null);
        }

        private static double ParseDouble(string value, double fallback)
        {
            double parsed;
            return double.TryParse(value, NumberStyles.Any, CultureInfo.InvariantCulture, out parsed) ? parsed : fallback;
        }

        private static int ParseInt(string value, int fallback)
        {
            int parsed;
            return int.TryParse(value, NumberStyles.Any, CultureInfo.InvariantCulture, out parsed) ? parsed : fallback;
        }

        [NinjaScriptProperty]
        [Display(Name = "OpenBull URL", GroupName = "OpenBull", Order = 1)]
        public string OpenBullUrl { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "API Key", GroupName = "OpenBull", Order = 2)]
        public string ApiKey { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Underlying", GroupName = "Contract", Order = 10)]
        public string Underlying { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Underlying Exchange", GroupName = "Contract", Order = 11)]
        public string UnderlyingExchange { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Expiry", GroupName = "Contract", Order = 12)]
        public string Expiry { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "CE Strike", GroupName = "Contract", Order = 13)]
        public double CeStrike { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "PE Strike", GroupName = "Contract", Order = 14)]
        public double PeStrike { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Lots", GroupName = "Order", Order = 20)]
        public int Lots { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Product", GroupName = "Order", Order = 21)]
        public string Product { get; set; }

        [NinjaScriptProperty]
        [Range(0.01, double.MaxValue)]
        [Display(Name = "SL Points", GroupName = "Risk", Order = 30)]
        public double SlPoints { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Target Template Id", GroupName = "Risk", Order = 31)]
        public int TargetTemplateId { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Override Targets", GroupName = "Risk", Order = 32)]
        public bool UseOverrideTargets { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Auto Split Targets", GroupName = "Risk", Order = 33)]
        public bool AutoSplitTargets { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "T1 Points", GroupName = "Override Targets", Order = 40)]
        public double Target1Points { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "T2 Points", GroupName = "Override Targets", Order = 41)]
        public double Target2Points { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "T3 Points", GroupName = "Override Targets", Order = 42)]
        public double Target3Points { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "T4 Points", GroupName = "Override Targets", Order = 43)]
        public double Target4Points { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "T1 Exit %", GroupName = "Override Targets", Order = 50)]
        public double Target1ExitPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "T2 Exit %", GroupName = "Override Targets", Order = 51)]
        public double Target2ExitPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "T3 Exit %", GroupName = "Override Targets", Order = 52)]
        public double Target3ExitPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "T4 Exit %", GroupName = "Override Targets", Order = 53)]
        public double Target4ExitPct { get; set; }
    }
}
