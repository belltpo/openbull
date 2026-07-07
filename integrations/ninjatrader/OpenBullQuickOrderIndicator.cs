#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.Net.Http;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class OpenBullQuickOrderIndicator : Indicator
    {
        private static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };
        private static string[] cachedExpiries = new string[0];
        private static double[] cachedStrikes = new double[0];
        private static int[] cachedTemplateIds = new int[] { 0 };
        private static readonly Dictionary<int, string> cachedTemplateLabels = new Dictionary<int, string> { { 0, "0 - Saved/default" } };
        private static readonly object templateCacheLock = new object();
        private static string templateCacheKey = "";
        private static DateTime templateCacheAt = DateTime.MinValue;

        private Grid root;
        private Border popup;
        private Border settingsPanel;
        private Button restoreButton;
        private TextBlock liveText;
        private TextBlock mtmText;
        private TextBlock modeText;
        private TextBlock restoreMtmText;
        private TextBlock statusText;
        private Button buyCeButton;
        private Button sellCeButton;
        private Button buyPeButton;
        private Button sellPeButton;
        private ComboBox instrumentCombo;
        private ComboBox expiryCombo;
        private ComboBox ceCombo;
        private ComboBox peCombo;
        private ComboBox templateCombo;
        private ComboBox productCombo;
        private CheckBox previousDrawingsCheck;
        private TextBox urlBox;
        private TextBox lotsBox;
        private TextBox slBox;
        private PasswordBox apiBox;
        private DispatcherTimer liveTimer;
        private bool controlsAdded;
        private bool isBusy;
        private bool settingsHydrating;
        private bool wasDragged;
        private bool isDragging;
        private bool dragMoved;
        private bool rehydrateAttempted;
        private bool liveRefreshRunning;
        private int optionsPollTick;
        private Point dragStart;
        private Thickness dragStartMargin;
        private double futuresLtp;
        private double ceLtp;
        private double peLtp;
        private double mtmValue;
        private ChartScale activeChartScale;
        private OpenBullTradeSnapshot managedTrade;
        private DrawingTool linkedBellTool;
        private string linkedBellTag;
        private bool linkedBellSeenOnChart;
        private readonly Dictionary<int, OpenBullTradeSnapshot> managedTrades = new Dictionary<int, OpenBullTradeSnapshot>();
        private readonly Dictionary<int, DrawingTool> linkedBellTools = new Dictionary<int, DrawingTool>();
        private readonly HashSet<int> linkedBellSeenTradeIds = new HashSet<int>();
        private bool levelDragging;
        private string draggedLevelKey;
        private string tradingMode = "--";
        private readonly Dictionary<ComboBox, TextBlock> comboDisplays = new Dictionary<ComboBox, TextBlock>();

        public override string DisplayName
        {
            get { return "OpenBull Quick Order"; }
        }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "OpenBull Quick Order";
                Description = "Small chart overlay for sending OpenBull Futures-Risk quick orders from NinjaTrader.";
                Calculate = Calculate.OnPriceChange;
                IsOverlay = true;
                DisplayInDataBox = false;
                DrawOnPricePanel = true;
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
                Product = "MIS";
                TargetTemplateId = 0;
                TargetTemplate = TemplateFallbackLabel(0);
                UseOverrideTargets = false;
                AutoSplitTargets = true;
                ShowPreviousTradeDrawings = false;
                LivePollMs = 1000;
                Target1Points = 50;
                Target2Points = 100;
                Target3Points = 150;
                Target4Points = 200;
                Target1ExitPct = 25;
                Target2ExitPct = 25;
                Target3ExitPct = 25;
                Target4ExitPct = 25;
                LinkedTradeId = 0;
                LinkedTradeIds = "";
                RemovedLinkedTradeIds = "";
                LinkedTradeRemovedByUser = false;
                NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.Configure(OpenBullUrl, ApiKey);
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
            // Prices shown in the widget come from OpenBull, not the NT chart instrument.
        }

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            base.OnRender(chartControl, chartScale);
            activeChartScale = chartScale;
            if (linkedBellTool != null && !string.IsNullOrWhiteSpace(linkedBellTag) && DrawingToolExists(linkedBellTag))
            {
                linkedBellSeenOnChart = true;
                return;
            }
            if (managedTrade == null || managedTrade.EntryFuturesPrice <= 0 || ChartBars == null || ChartBars.Bars == null)
                return;

            int endBarIndex = Math.Max(0, ChartBars.Bars.Count - 1);
            int startBarIndex = Math.Max(0, endBarIndex - 22);
            float startX = chartControl.GetXByBarIndex(ChartBars, startBarIndex);
            float endX = chartControl.GetXByBarIndex(ChartBars, endBarIndex);
            DrawManagedLine(chartScale, startX, endX, managedTrade.EntryFuturesPrice, EntryBrushForTrade(), EntryLabelForTrade(), false);
            DrawManagedLine(chartScale, startX, endX, managedTrade.StopLossPrice, Brushes.Red, "SL @ " + FormatChartPrice(managedTrade.StopLossPrice), true);
            foreach (OpenBullTradeLevel target in managedTrade.Targets)
            {
                if (target == null || target.Price <= 0)
                    continue;
                string label = "T" + target.Seq.ToString(CultureInfo.InvariantCulture) + " @ " + FormatChartPrice(target.Price);
                if (!string.IsNullOrWhiteSpace(target.Status) && !string.Equals(target.Status, "pending", StringComparison.OrdinalIgnoreCase))
                    label += " " + target.Status;
                DrawManagedLine(chartScale, startX, endX, target.Price, Brushes.MediumSpringGreen, label, string.Equals(target.Status, "pending", StringComparison.OrdinalIgnoreCase));
            }
            DrawManagedPnlLabel(chartScale, endX + 8, managedTrade.EntryFuturesPrice);
        }

        private Brush EntryBrushForTrade()
        {
            return string.Equals(managedTrade == null ? "" : managedTrade.Side, "BUY", StringComparison.OrdinalIgnoreCase)
                ? Brushes.DeepSkyBlue
                : Brushes.OrangeRed;
        }

        private string EntryLabelForTrade()
        {
            if (managedTrade == null)
                return "React";
            string prefix = string.Equals(managedTrade.Side, "BUY", StringComparison.OrdinalIgnoreCase) ? "L React" : "S React";
            return prefix + " @ " + FormatChartPrice(managedTrade.EntryFuturesPrice);
        }

        private void DrawManagedPnlLabel(ChartScale chartScale, float x, double entryPrice)
        {
            if (managedTrade == null || entryPrice <= 0)
                return;
            string sign = managedTrade.Mtm >= 0 ? "+" : "";
            Brush pnlBrush = managedTrade.Mtm >= 0 ? Brushes.MediumSpringGreen : Brushes.Red;
            float y = chartScale.GetYByValue(entryPrice) + 20f;
            DrawManagedLabel("P&L " + sign + managedTrade.Mtm.ToString("N2", CultureInfo.InvariantCulture), x, y, pnlBrush);
        }

        private void DrawManagedLine(ChartScale chartScale, float startX, float endX, double price, Brush brush, string label, bool draggable)
        {
            if (price <= 0 || RenderTarget == null)
                return;
            float y = chartScale.GetYByValue(price);
            var start = new SharpDX.Vector2(startX, y);
            var end = new SharpDX.Vector2(endX, y);
            var stroke = new Stroke(brush, DashStyleHelper.Dot, draggable ? 1.8f : 1.3f) { RenderTarget = RenderTarget };
            RenderTarget.DrawLine(start, end, stroke.BrushDX, stroke.Width, stroke.StrokeStyle);
            using (var dotBrush = brush.ToDxBrush(RenderTarget))
            {
                var center = new SharpDX.Vector2(endX, y);
                var outer = new SharpDX.Direct2D1.Ellipse(center, draggable ? 6f : 4f, draggable ? 6f : 4f);
                RenderTarget.DrawEllipse(outer, dotBrush, 1.4f);
                if (draggable)
                    RenderTarget.FillEllipse(new SharpDX.Direct2D1.Ellipse(center, 2.8f, 2.8f), dotBrush);
            }
            DrawManagedLabel(label, endX + 8, y, brush);
        }

        private void DrawManagedLabel(string text, float x, float y, Brush textBrush)
        {
            var font = new SimpleFont("Arial", 12) { Bold = true };
            using (var textFormat = font.ToDirectWriteTextFormat())
            using (var layout = new SharpDX.DirectWrite.TextLayout(Core.Globals.DirectWriteFactory, text, textFormat, 260, 44))
            {
                float padding = 4f;
                float textY = y - layout.Metrics.Height / 2f;
                var rect = new SharpDX.RectangleF(x - padding, textY - padding, layout.Metrics.Width + padding * 2, layout.Metrics.Height + padding * 2);
                using (var bg = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new SharpDX.Color4(0, 0, 0, 0.72f)))
                using (var fg = textBrush.ToDxBrush(RenderTarget))
                {
                    RenderTarget.FillRectangle(rect, bg);
                    RenderTarget.DrawTextLayout(new SharpDX.Vector2(x, textY), layout, fg);
                }
            }
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
                NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.Configure(OpenBullUrl, ApiKey);
                UserControlCollection.Add(root);
                controlsAdded = true;
                CenterPopup();
                StartLiveTimer();
                Task.Run(async () => await RehydrateLinkedTradeAsync());
                if (ChartControl != null)
                {
                    ChartControl.SizeChanged += OnChartSizeChanged;
                    ChartControl.PreviewMouseLeftButtonDown += OnChartMouseDown;
                    ChartControl.PreviewMouseMove += OnChartMouseMove;
                    ChartControl.PreviewMouseLeftButtonUp += OnChartMouseUp;
                }
            });
        }

        private void RemoveChartControls()
        {
            if (ChartControl == null)
                return;

            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                StopLiveTimer();
                if (ChartControl != null)
                {
                    ChartControl.SizeChanged -= OnChartSizeChanged;
                    ChartControl.PreviewMouseLeftButtonDown -= OnChartMouseDown;
                    ChartControl.PreviewMouseMove -= OnChartMouseMove;
                    ChartControl.PreviewMouseLeftButtonUp -= OnChartMouseUp;
                }
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

        private void OnChartMouseDown(object sender, MouseButtonEventArgs e)
        {
            if (linkedBellTool != null || managedTrade == null || activeChartScale == null || root == null || root.IsMouseOver)
                return;
            Point point = e.GetPosition(ChartControl);
            string hit = HitTestManagedLevel(point);
            if (string.IsNullOrWhiteSpace(hit))
                return;
            levelDragging = true;
            draggedLevelKey = hit;
            Mouse.Capture(ChartControl);
            e.Handled = true;
        }

        private void OnChartMouseMove(object sender, MouseEventArgs e)
        {
            if (!levelDragging || managedTrade == null || activeChartScale == null || string.IsNullOrWhiteSpace(draggedLevelKey))
                return;
            Point point = e.GetPosition(ChartControl);
            double price = RoundToChartTick(activeChartScale.GetValueByY((float)point.Y));
            if (price <= 0)
                return;
            if (draggedLevelKey == "SL")
            {
                managedTrade.StopLossPrice = price;
            }
            else if (draggedLevelKey.StartsWith("T", StringComparison.OrdinalIgnoreCase))
            {
                int seq = ParseInt(draggedLevelKey.Substring(1), 0);
                OpenBullTradeLevel target = managedTrade.Targets.Find(t => t.Seq == seq);
                if (target != null && string.Equals(target.Status, "pending", StringComparison.OrdinalIgnoreCase))
                    target.Price = price;
            }
            RequestChartRefresh();
            e.Handled = true;
        }

        private void OnChartMouseUp(object sender, MouseButtonEventArgs e)
        {
            if (!levelDragging)
                return;
            levelDragging = false;
            string released = draggedLevelKey;
            draggedLevelKey = null;
            Mouse.Capture(null);
            e.Handled = true;
            if (!string.IsNullOrWhiteSpace(released))
                Task.Run(async () => await SyncManagedLevelsAsync());
        }

        private string HitTestManagedLevel(Point point)
        {
            if (managedTrade == null || activeChartScale == null)
                return "";
            if (Math.Abs(activeChartScale.GetYByValue(managedTrade.StopLossPrice) - point.Y) <= 8)
                return "SL";
            foreach (OpenBullTradeLevel target in managedTrade.Targets)
            {
                if (target == null || !string.Equals(target.Status, "pending", StringComparison.OrdinalIgnoreCase))
                    continue;
                if (Math.Abs(activeChartScale.GetYByValue(target.Price) - point.Y) <= 8)
                    return "T" + target.Seq.ToString(CultureInfo.InvariantCulture);
            }
            return "";
        }

        private void RequestChartRefresh()
        {
            if (ChartControl == null)
                return;
            ChartControl.InvalidateVisual();
        }

        private void CenterPopup()
        {
            if (root == null || ChartControl == null)
                return;

            double width = Math.Max(0, ChartControl.ActualWidth);
            double left = Math.Max(12, (width - 580) / 2);
            root.Margin = new Thickness(left, 18, 0, 0);
        }

        private void StartLiveTimer()
        {
            StopLiveTimer();
            int pollMs = Math.Max(500, LivePollMs);
            liveTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(pollMs) };
            liveTimer.Tick += async (s, e) =>
            {
                if (liveRefreshRunning)
                    return;
                liveRefreshRunning = true;
                try
                {
                    await FetchLiveAsync();
                    optionsPollTick++;
                    if (settingsPanel != null && settingsPanel.Visibility == Visibility.Visible && optionsPollTick % Math.Max(5, 10000 / pollMs) == 0)
                        await FetchOptionsAsync();
                }
                finally
                {
                    liveRefreshRunning = false;
                }
            };
            liveTimer.Start();
            Task.Run(async () =>
            {
                await FetchOptionsAsync();
                await FetchLiveAsync();
            });
        }

        private void StopLiveTimer()
        {
            if (liveTimer == null)
                return;
            liveTimer.Stop();
            liveTimer = null;
        }

        private void BuildControls()
        {
            root = new Grid
            {
                Width = 580,
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Top,
                Background = null
            };

            StackPanel stack = new StackPanel { Orientation = Orientation.Vertical };
            popup = new Border
            {
                Width = 260,
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Top,
                CornerRadius = new CornerRadius(10),
                Padding = new Thickness(8),
                Background = new SolidColorBrush(Color.FromArgb(242, 18, 18, 18)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(54, 54, 54)),
                BorderThickness = new Thickness(1),
                Child = stack
            };

            TextBlock grip = new TextBlock
            {
                Text = "...",
                Foreground = new SolidColorBrush(Color.FromRgb(130, 130, 130)),
                HorizontalAlignment = HorizontalAlignment.Center,
                FontSize = 10,
                Margin = new Thickness(0, -5, 0, 0)
            };
            grip.MouseLeftButtonDown += StartDrag;
            grip.MouseMove += DragMove;
            grip.MouseLeftButtonUp += StopDrag;
            stack.Children.Add(grip);

            Grid header = new Grid { Margin = new Thickness(0, 0, 0, 6) };
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

            Button settingsButton = IconButton("\u2699");
            settingsButton.Click += (s, e) => ToggleSettings();
            Grid.SetColumn(settingsButton, 1);
            header.Children.Add(settingsButton);

            Button closeButton = IconButton("X");
            closeButton.Click += (s, e) => CollapseQuickPopup();
            Grid.SetColumn(closeButton, 2);
            header.Children.Add(closeButton);
            stack.Children.Add(header);

            stack.Children.Add(BuildLiveBox());
            stack.Children.Add(BuildButtonGrid());

            statusText = new TextBlock
            {
                Text = "* Ready",
                Foreground = new SolidColorBrush(Color.FromRgb(20, 190, 120)),
                FontSize = 10,
                Margin = new Thickness(1, 6, 0, 0)
            };
            stack.Children.Add(statusText);

            restoreButton = BuildRestoreButton();
            restoreButton.Visibility = Visibility.Collapsed;
            root.Children.Add(restoreButton);

            settingsPanel = BuildSettingsPanel();
            settingsPanel.Margin = new Thickness(270, 0, 0, 0);
            settingsPanel.HorizontalAlignment = HorizontalAlignment.Left;
            settingsPanel.VerticalAlignment = VerticalAlignment.Top;
            settingsPanel.Visibility = Visibility.Collapsed;
            root.Children.Add(popup);
            root.Children.Add(settingsPanel);
        }

        private Button BuildRestoreButton()
        {
            StackPanel content = new StackPanel
            {
                Orientation = Orientation.Vertical,
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center
            };
            content.Children.Add(new TextBlock
            {
                Text = "OB",
                Foreground = Brushes.White,
                FontSize = 12,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(0, 0, 0, -1),
                TextAlignment = TextAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center
            });
            restoreMtmText = new TextBlock
            {
                Text = "MTM --",
                Foreground = new SolidColorBrush(Color.FromRgb(20, 220, 150)),
                FontSize = 8.5,
                FontWeight = FontWeights.SemiBold,
                TextAlignment = TextAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center
            };
            content.Children.Add(restoreMtmText);

            Button button = new Button
            {
                Content = content,
                Width = 112,
                Height = 40,
                Padding = new Thickness(0),
                Foreground = Brushes.White,
                Background = new SolidColorBrush(Color.FromArgb(235, 18, 18, 18)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(70, 70, 70)),
                FontSize = 12,
                FontWeight = FontWeights.Bold
            };
            ApplyRoundedButton(button, 9);
            button.PreviewMouseLeftButtonDown += StartDrag;
            button.PreviewMouseMove += DragMove;
            button.PreviewMouseLeftButtonUp += RestoreMouseUp;
            return button;
        }

        private Border BuildLiveBox()
        {
            Border liveBox = new Border
            {
                CornerRadius = new CornerRadius(8),
                Background = new SolidColorBrush(Color.FromRgb(31, 31, 31)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(55, 55, 55)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(8, 5, 8, 5),
                Margin = new Thickness(0, 0, 0, 7)
            };
            Grid liveGrid = new Grid();
            liveGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            liveGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            liveGrid.RowDefinitions.Add(new RowDefinition());
            liveGrid.RowDefinitions.Add(new RowDefinition());
            liveGrid.RowDefinitions.Add(new RowDefinition());

            TextBlock liveLabel = new TextBlock
            {
                Text = "FUT LIVE",
                Foreground = new SolidColorBrush(Color.FromRgb(155, 155, 155)),
                FontSize = 9,
                FontWeight = FontWeights.SemiBold,
                VerticalAlignment = VerticalAlignment.Center
            };
            liveText = new TextBlock
            {
                Text = Underlying + " FUT --",
                Foreground = Brushes.White,
                FontSize = 11,
                FontWeight = FontWeights.Bold,
                VerticalAlignment = VerticalAlignment.Center
            };
            Grid.SetColumn(liveLabel, 0);
            Grid.SetColumn(liveText, 1);
            liveGrid.Children.Add(liveLabel);
            liveGrid.Children.Add(liveText);

            TextBlock mtmLabel = new TextBlock
            {
                Text = "MTM",
                Foreground = new SolidColorBrush(Color.FromRgb(155, 155, 155)),
                FontSize = 9,
                FontWeight = FontWeights.SemiBold,
                Margin = new Thickness(0, 4, 0, 0),
                VerticalAlignment = VerticalAlignment.Center
            };
            mtmText = new TextBlock
            {
                Text = "--",
                Foreground = new SolidColorBrush(Color.FromRgb(20, 220, 150)),
                FontSize = 11,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(0, 4, 0, 0),
                VerticalAlignment = VerticalAlignment.Center
            };
            Grid.SetRow(mtmLabel, 1);
            Grid.SetColumn(mtmLabel, 0);
            Grid.SetRow(mtmText, 1);
            Grid.SetColumn(mtmText, 1);
            liveGrid.Children.Add(mtmLabel);
            liveGrid.Children.Add(mtmText);

            TextBlock modeLabel = new TextBlock
            {
                Text = "MODE",
                Foreground = new SolidColorBrush(Color.FromRgb(155, 155, 155)),
                FontSize = 9,
                FontWeight = FontWeights.SemiBold,
                Margin = new Thickness(0, 4, 0, 0),
                VerticalAlignment = VerticalAlignment.Center
            };
            modeText = new TextBlock
            {
                Text = "--",
                Foreground = new SolidColorBrush(Color.FromRgb(150, 150, 150)),
                FontSize = 10,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(0, 4, 0, 0),
                VerticalAlignment = VerticalAlignment.Center
            };
            Grid.SetRow(modeLabel, 2);
            Grid.SetColumn(modeLabel, 0);
            Grid.SetRow(modeText, 2);
            Grid.SetColumn(modeText, 1);
            liveGrid.Children.Add(modeLabel);
            liveGrid.Children.Add(modeText);
            liveBox.Child = liveGrid;
            return liveBox;
        }

        private Grid BuildButtonGrid()
        {
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
            RefreshButtonText();
            return buttons;
        }

        private Button IconButton(string text)
        {
            Button button = new Button
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
            ApplyRoundedButton(button, 7);
            return button;
        }

        private Button TradeButton(string text, bool isBuy)
        {
            TextBlock content = new TextBlock
            {
                Text = text,
                TextAlignment = TextAlignment.Center,
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold,
                FontSize = 9,
                LineHeight = 10
            };

            Button button = new Button
            {
                Content = content,
                Height = 46,
                Margin = new Thickness(3),
                Padding = new Thickness(2),
                Background = isBuy
                    ? new SolidColorBrush(Color.FromRgb(0, 132, 88))
                    : new SolidColorBrush(Color.FromRgb(205, 0, 52)),
                BorderBrush = Brushes.Transparent,
                Foreground = Brushes.White
            };
            ApplyRoundedButton(button, 9);
            return button;
        }

        private static void AddButton(Grid grid, Button button, int row, int column)
        {
            Grid.SetRow(button, row);
            Grid.SetColumn(button, column);
            grid.Children.Add(button);
        }

        private Border BuildSettingsPanel()
        {
            StackPanel stack = new StackPanel();
            Grid header = new Grid { Margin = new Thickness(0, 0, 0, 6) };
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            header.MouseLeftButtonDown += StartDrag;
            header.MouseMove += DragMove;
            header.MouseLeftButtonUp += StopDrag;
            TextBlock title = new TextBlock
            {
                Text = "Quick Settings",
                Foreground = Brushes.White,
                FontSize = 11,
                FontWeight = FontWeights.SemiBold,
                VerticalAlignment = VerticalAlignment.Center
            };
            Button close = IconButton("X");
            close.Click += (s, e) => settingsPanel.Visibility = Visibility.Collapsed;
            Grid.SetColumn(title, 0);
            Grid.SetColumn(close, 1);
            header.Children.Add(title);
            header.Children.Add(close);
            stack.Children.Add(header);
            stack.Children.Add(Field("URL", OpenBullUrl, value =>
            {
                OpenBullUrl = value;
                NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.Configure(OpenBullUrl, ApiKey);
            }, out urlBox));
            WireCommitSave(urlBox);
            stack.Children.Add(PasswordField("API Key", value =>
            {
                ApiKey = value;
                NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.Configure(OpenBullUrl, ApiKey);
            }));
            instrumentCombo = ComboRow(stack, "Instrument", value =>
            {
                Underlying = value.ToUpperInvariant();
                futuresLtp = 0;
                ceLtp = 0;
                peLtp = 0;
                CeStrike = 0;
                PeStrike = 0;
                RefreshButtonText();
                Task.Run(async () => await FetchOptionsAsync());
            });
            expiryCombo = ComboRow(stack, "Expiry", value =>
            {
                Expiry = value.ToUpperInvariant();
                ceLtp = 0;
                peLtp = 0;
                CeStrike = 0;
                PeStrike = 0;
                RefreshButtonText();
                Task.Run(async () => await FetchOptionsAsync());
            });
            ceCombo = ComboRow(stack, "CE", value =>
            {
                CeStrike = ParseDouble(value, CeStrike);
                RefreshButtonText();
            });
            peCombo = ComboRow(stack, "PE", value =>
            {
                PeStrike = ParseDouble(value, PeStrike);
                RefreshButtonText();
            });
            stack.Children.Add(Field("Lots", Lots.ToString(CultureInfo.InvariantCulture), value =>
            {
                Lots = Math.Max(1, ParseInt(value, Lots));
                if (lotsBox != null && lotsBox.Text != Lots.ToString(CultureInfo.InvariantCulture))
                    lotsBox.Text = Lots.ToString(CultureInfo.InvariantCulture);
            }, out lotsBox));
            WireCommitSave(lotsBox);
            stack.Children.Add(Field("SL pts", SlPoints.ToString(CultureInfo.InvariantCulture), value =>
            {
                SlPoints = ParseDouble(value, SlPoints);
                if (slBox != null && slBox.Text != SlPoints.ToString(CultureInfo.InvariantCulture))
                    slBox.Text = SlPoints.ToString(CultureInfo.InvariantCulture);
            }, out slBox));
            WireCommitSave(slBox);
            templateCombo = ComboRow(stack, "Template", value =>
            {
                TargetTemplateId = Math.Max(0, ParseTemplateId(value, TargetTemplateId));
                TargetTemplate = string.IsNullOrWhiteSpace(value) ? TemplateFallbackLabel(TargetTemplateId) : value;
                Task.Run(async () => await SaveSettingsAsync());
            });
            productCombo = ComboRow(stack, "Product", value =>
            {
                Product = string.IsNullOrWhiteSpace(value) ? "NRML" : value.ToUpperInvariant();
                Task.Run(async () => await SaveSettingsAsync());
            });
            stack.Children.Add(CheckRow("Prev levels", ShowPreviousTradeDrawings, value =>
            {
                ShowPreviousTradeDrawings = value;
                RefreshDrawingVisibility();
            }, out previousDrawingsCheck));

            SeedCombo(instrumentCombo, Underlying);
            SeedCombo(expiryCombo, Expiry);
            SeedCombo(ceCombo, CeStrike.ToString("0", CultureInfo.InvariantCulture));
            SeedCombo(peCombo, PeStrike.ToString("0", CultureInfo.InvariantCulture));
            SeedCombo(templateCombo, string.IsNullOrWhiteSpace(TargetTemplate) ? TemplateFallbackLabel(TargetTemplateId) : TargetTemplate);
            FillCombo(productCombo, new List<string> { "NRML", "MIS", "CNC" }, Product);

            Grid actions = new Grid { Margin = new Thickness(0, 6, 0, 0) };
            actions.ColumnDefinitions.Add(new ColumnDefinition());
            actions.ColumnDefinitions.Add(new ColumnDefinition());
            actions.ColumnDefinitions.Add(new ColumnDefinition());
            actions.ColumnDefinitions.Add(new ColumnDefinition());
            Button refresh = SmallAction("Refresh");
            Button save = SmallAction("Save");
            Button remove = SmallAction("Remove");
            Button delete = SmallAction("Delete");
            WireActionButton(refresh, "Refresh", async () => await FetchOptionsAsync());
            WireActionButton(save, "Save", async () =>
            {
                CommitAllSettingInputs();
                await SaveSettingsAsync();
            });
            WireActionButton(remove, "Remove", async () => await RemoveCurrentTradeDrawingAsync());
            WireActionButton(delete, "Delete", async () => await DeleteSettingsAsync());
            Grid.SetColumn(refresh, 0);
            Grid.SetColumn(save, 1);
            Grid.SetColumn(remove, 2);
            Grid.SetColumn(delete, 3);
            actions.Children.Add(refresh);
            actions.Children.Add(save);
            actions.Children.Add(remove);
            actions.Children.Add(delete);
            stack.Children.Add(actions);

            return new Border
            {
                Width = 300,
                CornerRadius = new CornerRadius(8),
                Background = new SolidColorBrush(Color.FromArgb(242, 20, 20, 20)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(55, 55, 55)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(8),
                Child = stack
            };
        }

        private UIElement PasswordField(string label, Action<string> onChanged)
        {
            Grid row = FieldRow(label);
            PasswordBox box = new PasswordBox
            {
                Password = ApiKey ?? "",
                FontSize = 10,
                Height = 23,
                Padding = new Thickness(4, 1, 4, 1),
                Foreground = Brushes.White,
                Background = new SolidColorBrush(Color.FromRgb(10, 10, 10)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(65, 65, 65))
            };
            apiBox = box;
            EnableTextEntry(box);
            box.PasswordChanged += (s, e) => onChanged(box.Password);
            Grid.SetColumn(box, 1);
            row.Children.Add(box);
            return row;
        }

        private UIElement Field(string label, string value, Action<string> onChanged, out TextBox outBox)
        {
            Grid row = FieldRow(label);
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
            outBox = box;
            EnableTextEntry(box);
            box.Tag = onChanged;
            Grid.SetColumn(box, 1);
            row.Children.Add(box);
            return row;
        }

        private void WireCommitSave(TextBox box)
        {
            if (box == null)
                return;
            box.LostKeyboardFocus += (s, e) =>
            {
                CommitTextBox(box);
                Task.Run(async () => await SaveSettingsAsync());
            };
            box.KeyDown += (s, e) =>
            {
                if (e.Key == Key.Enter)
                {
                    e.Handled = true;
                    CommitTextBox(box);
                    Task.Run(async () => await SaveSettingsAsync());
                }
                else if (IsTextEditingKey(e.Key))
                {
                    e.Handled = true;
                }
            };
        }

        private void CommitTextBox(TextBox box)
        {
            if (box == null || settingsHydrating)
                return;
            string value = box.Text == null ? "" : box.Text.Trim();
            if (string.IsNullOrWhiteSpace(value))
                return;
            Action<string> onChanged = box.Tag as Action<string>;
            if (onChanged == null)
                return;
            onChanged(value);
            RefreshButtonText();
        }

        private void CommitAllSettingInputs()
        {
            CommitTextBox(urlBox);
            CommitTextBox(lotsBox);
            CommitTextBox(slBox);
        }

        private static bool IsTextEditingKey(Key key)
        {
            return (key >= Key.D0 && key <= Key.D9)
                || (key >= Key.NumPad0 && key <= Key.NumPad9)
                || key == Key.Back
                || key == Key.Delete
                || key == Key.Decimal
                || key == Key.OemPeriod
                || key == Key.OemMinus
                || key == Key.Subtract
                || key == Key.Left
                || key == Key.Right
                || key == Key.Home
                || key == Key.End;
        }

        private UIElement CheckRow(string label, bool value, Action<bool> onChanged, out CheckBox outBox)
        {
            Grid row = FieldRow(label);
            CheckBox box = new CheckBox
            {
                IsChecked = value,
                VerticalAlignment = VerticalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Left,
                Foreground = Brushes.White
            };
            outBox = box;
            box.Checked += (s, e) =>
            {
                if (settingsHydrating)
                    return;
                onChanged(true);
                Task.Run(async () => await SaveSettingsAsync());
            };
            box.Unchecked += (s, e) =>
            {
                if (settingsHydrating)
                    return;
                onChanged(false);
                Task.Run(async () => await SaveSettingsAsync());
            };
            Grid.SetColumn(box, 1);
            row.Children.Add(box);
            return row;
        }

        private ComboBox ComboRow(StackPanel stack, string label, Action<string> onChanged)
        {
            Grid row = FieldRow(label);
            ComboBox combo = new ComboBox
            {
                FontSize = 10,
                Height = 24,
                IsEditable = false,
                IsTextSearchEnabled = true,
                Foreground = Brushes.Transparent,
                Background = new SolidColorBrush(Color.FromRgb(10, 10, 10)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(65, 65, 65))
            };
            combo.Resources[SystemColors.WindowBrushKey] = new SolidColorBrush(Color.FromRgb(10, 10, 10));
            combo.Resources[SystemColors.ControlBrushKey] = new SolidColorBrush(Color.FromRgb(10, 10, 10));
            combo.Resources[SystemColors.ControlTextBrushKey] = Brushes.White;
            combo.Resources[SystemColors.HighlightBrushKey] = new SolidColorBrush(Color.FromRgb(45, 86, 160));
            combo.Resources[SystemColors.HighlightTextBrushKey] = Brushes.White;
            combo.ItemTemplate = BuildComboItemTemplate();
            combo.ItemContainerStyle = BuildComboItemStyle();
            combo.Loaded += (s, e) => ApplyComboTextColors(combo);
            combo.DropDownOpened += (s, e) => ApplyComboTextColors(combo);
            combo.SelectionChanged += (s, e) =>
            {
                RefreshComboDisplay(combo);
                if (settingsHydrating || combo.SelectedItem == null)
                    return;
                onChanged(combo.SelectedItem.ToString());
                RefreshButtonText();
            };
            combo.LostKeyboardFocus += (s, e) =>
            {
                RefreshComboDisplay(combo);
                if (settingsHydrating || string.IsNullOrWhiteSpace(combo.Text))
                    return;
                onChanged(combo.Text.Trim());
                SeedCombo(combo, combo.Text.Trim());
                RefreshButtonText();
            };

            Grid comboShell = new Grid { Height = 24 };
            comboShell.Children.Add(combo);
            TextBlock display = new TextBlock
            {
                Text = "",
                Foreground = Brushes.White,
                FontSize = 10,
                FontWeight = FontWeights.SemiBold,
                VerticalAlignment = VerticalAlignment.Center,
                TextTrimming = TextTrimming.CharacterEllipsis,
                IsHitTestVisible = false
            };
            Border displayCover = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(10, 10, 10)),
                Margin = new Thickness(2, 2, 21, 2),
                Padding = new Thickness(5, 0, 0, 0),
                Child = display,
                IsHitTestVisible = false
            };
            TextBlock arrow = new TextBlock
            {
                Text = "\u25BE",
                Foreground = Brushes.White,
                FontSize = 9,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(0, 0, 7, 0),
                HorizontalAlignment = HorizontalAlignment.Right,
                VerticalAlignment = VerticalAlignment.Center,
                IsHitTestVisible = false
            };
            comboShell.Children.Add(displayCover);
            comboShell.Children.Add(arrow);
            comboDisplays[combo] = display;

            Grid.SetColumn(comboShell, 1);
            row.Children.Add(comboShell);
            stack.Children.Add(row);
            return combo;
        }

        private static Style BuildComboItemStyle()
        {
            Style style = new Style(typeof(ComboBoxItem));
            style.Setters.Add(new Setter(Control.ForegroundProperty, Brushes.White));
            style.Setters.Add(new Setter(Control.BackgroundProperty, new SolidColorBrush(Color.FromRgb(10, 10, 10))));
            style.Setters.Add(new Setter(Control.BorderBrushProperty, new SolidColorBrush(Color.FromRgb(65, 65, 65))));
            style.Setters.Add(new Setter(Control.PaddingProperty, new Thickness(6, 3, 6, 3)));

            Trigger highlighted = new Trigger { Property = ComboBoxItem.IsHighlightedProperty, Value = true };
            highlighted.Setters.Add(new Setter(Control.ForegroundProperty, Brushes.White));
            highlighted.Setters.Add(new Setter(Control.BackgroundProperty, new SolidColorBrush(Color.FromRgb(45, 86, 160))));
            style.Triggers.Add(highlighted);
            return style;
        }

        private static DataTemplate BuildComboItemTemplate()
        {
            DataTemplate template = new DataTemplate();
            FrameworkElementFactory text = new FrameworkElementFactory(typeof(TextBlock));
            text.SetBinding(TextBlock.TextProperty, new System.Windows.Data.Binding("."));
            text.SetValue(TextBlock.ForegroundProperty, Brushes.White);
            text.SetValue(TextBlock.FontSizeProperty, 10.0);
            text.SetValue(TextBlock.PaddingProperty, new Thickness(3, 1, 3, 1));
            template.VisualTree = text;
            return template;
        }

        private static void ApplyComboTextColors(ComboBox combo)
        {
            TextBox editable = FindVisualChild<TextBox>(combo);
            if (editable == null)
                return;
            editable.Foreground = Brushes.White;
            editable.Background = new SolidColorBrush(Color.FromRgb(10, 10, 10));
            editable.BorderBrush = new SolidColorBrush(Color.FromRgb(65, 65, 65));
            editable.CaretBrush = Brushes.White;
        }

        private static T FindVisualChild<T>(DependencyObject parent) where T : DependencyObject
        {
            if (parent == null)
                return null;
            int count = VisualTreeHelper.GetChildrenCount(parent);
            for (int i = 0; i < count; i++)
            {
                DependencyObject child = VisualTreeHelper.GetChild(parent, i);
                T typed = child as T;
                if (typed != null)
                    return typed;
                T nested = FindVisualChild<T>(child);
                if (nested != null)
                    return nested;
            }
            return null;
        }

        private Button SmallAction(string text)
        {
            Button button = new Button
            {
                Content = text,
                Height = 24,
                Margin = new Thickness(2),
                Padding = new Thickness(4, 0, 4, 0),
                Foreground = Brushes.White,
                Background = new SolidColorBrush(Color.FromRgb(35, 35, 35)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(70, 70, 70)),
                FontSize = 10
            };
            ApplyRoundedButton(button, 7);
            return button;
        }

        private void WireActionButton(Button button, string label, Func<Task> action)
        {
            if (button == null || action == null)
                return;
            button.PreviewMouseLeftButtonDown += (s, e) =>
            {
                SetStatus(label + " clicked", true);
                button.Background = new SolidColorBrush(Color.FromRgb(58, 58, 58));
                e.Handled = false;
            };
            button.PreviewMouseLeftButtonUp += (s, e) =>
            {
                button.ReleaseMouseCapture();
                Mouse.Capture(null);
                e.Handled = false;
            };
            button.Click += async (s, e) =>
            {
                SetStatus(label + " running...", true);
                try
                {
                    await action();
                }
                finally
                {
                    button.Background = new SolidColorBrush(Color.FromRgb(35, 35, 35));
                }
            };
        }

        private static void EnableTextEntry(Control control)
        {
            if (control == null)
                return;
            control.Focusable = true;
            control.PreviewMouseLeftButtonDown += (s, e) =>
            {
                Control target = s as Control;
                if (target == null || target.IsKeyboardFocusWithin)
                    return;
                e.Handled = true;
                target.Dispatcher.BeginInvoke(new Action(() =>
                {
                    Window window = Window.GetWindow(target);
                    if (window != null)
                        FocusManager.SetFocusedElement(window, target);
                    target.Focus();
                    Keyboard.Focus(target);
                    TextBox textBox = target as TextBox;
                    if (textBox != null)
                    {
                        textBox.SelectAll();
                    }
                }), DispatcherPriority.Input);
            };
            control.PreviewKeyDown += (s, e) =>
            {
                if (IsTextEditingKey(e.Key) || e.Key == Key.Enter || e.Key == Key.Tab)
                    e.Handled = false;
            };
        }

        private static void ApplyRoundedButton(Button button, double radius)
        {
            Style style = new Style(typeof(Button));
            ControlTemplate template = new ControlTemplate(typeof(Button));
            FrameworkElementFactory border = new FrameworkElementFactory(typeof(Border));
            border.Name = "buttonBorder";
            border.SetValue(Border.CornerRadiusProperty, new CornerRadius(radius));
            border.SetValue(Border.BackgroundProperty, new TemplateBindingExtension(Button.BackgroundProperty));
            border.SetValue(Border.BorderBrushProperty, new TemplateBindingExtension(Button.BorderBrushProperty));
            border.SetValue(Border.BorderThicknessProperty, new TemplateBindingExtension(Button.BorderThicknessProperty));

            FrameworkElementFactory presenter = new FrameworkElementFactory(typeof(ContentPresenter));
            presenter.SetValue(ContentPresenter.HorizontalAlignmentProperty, HorizontalAlignment.Center);
            presenter.SetValue(ContentPresenter.VerticalAlignmentProperty, VerticalAlignment.Center);
            presenter.SetValue(ContentPresenter.MarginProperty, new TemplateBindingExtension(Button.PaddingProperty));
            border.AppendChild(presenter);
            template.VisualTree = border;

            Trigger disabled = new Trigger { Property = Button.IsEnabledProperty, Value = false };
            disabled.Setters.Add(new Setter(UIElement.OpacityProperty, 0.55, "buttonBorder"));
            template.Triggers.Add(disabled);

            style.Setters.Add(new Setter(Button.TemplateProperty, template));
            button.Style = style;
        }

        private Grid FieldRow(string label)
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
            Grid.SetColumn(text, 0);
            row.Children.Add(text);
            return row;
        }

        private void ToggleSettings()
        {
            if (settingsPanel == null)
                return;
            settingsPanel.Visibility = settingsPanel.Visibility == Visibility.Visible
                ? Visibility.Collapsed
                : Visibility.Visible;
            if (settingsPanel.Visibility == Visibility.Visible)
                Task.Run(async () => await FetchOptionsAsync());
        }

        private void CollapseQuickPopup()
        {
            if (popup != null)
                popup.Visibility = Visibility.Collapsed;
            if (settingsPanel != null)
                settingsPanel.Visibility = Visibility.Collapsed;
            if (restoreButton != null)
                restoreButton.Visibility = Visibility.Visible;
            if (root != null)
                root.Width = 112;
        }

        private void RefreshButtonText()
        {
            SetTradeButtonText(buyCeButton, "Buy CE", CeStrike, "CE", ceLtp);
            SetTradeButtonText(sellCeButton, "Sell CE", CeStrike, "CE", ceLtp);
            SetTradeButtonText(buyPeButton, "Buy PE", PeStrike, "PE", peLtp);
            SetTradeButtonText(sellPeButton, "Sell PE", PeStrike, "PE", peLtp);
        }

        private static void SetTradeButtonText(Button button, string label, double strike, string optionType, double ltp)
        {
            if (button == null)
                return;
            TextBlock text = button.Content as TextBlock;
            if (text == null)
                return;
            string ltpText = ltp > 0 ? ltp.ToString("0.##", CultureInfo.InvariantCulture) : "--";
            text.Text = label + "\n" + strike.ToString("0", CultureInfo.InvariantCulture) + " " + optionType + "\nLTP " + ltpText;
        }

        private async Task FetchLiveAsync()
        {
            if (string.IsNullOrWhiteSpace(ApiKey) || string.IsNullOrWhiteSpace(OpenBullUrl))
                return;

            try
            {
                string url = OpenBullUrl.TrimEnd('/') + "/api/v1/futures-risk/quick-order/preview";
                using (StringContent content = new StringContent(BuildPreviewJson(), Encoding.UTF8, "application/json"))
                {
                    HttpResponseMessage response = await Http.PostAsync(url, content);
                    string body = await response.Content.ReadAsStringAsync();
                    if (!response.IsSuccessStatusCode || body.IndexOf("\"status\":\"success\"", StringComparison.OrdinalIgnoreCase) < 0)
                    {
                        if (!isBusy)
                            SetStatus(TrimForStatus(body), false);
                        return;
                    }
                    double nextFut = ExtractLtp(body, "futures");
                    double nextCe = ExtractLtp(body, "ce");
                    double nextPe = ExtractLtp(body, "pe");
                    double nextMtm = ExtractNestedNumber(body, "mtm", "total");
                    string nextMode = ExtractJsonValue(body, "mode");

                    ChartControl.Dispatcher.InvokeAsync(() =>
                    {
                        futuresLtp = nextFut > 0 ? nextFut : futuresLtp;
                        ceLtp = nextCe > 0 ? nextCe : ceLtp;
                        peLtp = nextPe > 0 ? nextPe : peLtp;
                        mtmValue = nextMtm;
                        if (!string.IsNullOrWhiteSpace(nextMode) && nextMode != "null")
                            tradingMode = nextMode.ToUpperInvariant();
                        if (liveText != null)
                        {
                            string futText = futuresLtp > 0 ? futuresLtp.ToString("N2", CultureInfo.InvariantCulture) : "--";
                            liveText.Text = Underlying + " FUT " + futText;
                        }
                        UpdateMtmText();
                        UpdateModeText();
                        RefreshButtonText();
                    });
                    await RefreshManagedTradeAsync();
                }
            }
            catch (Exception ex)
            {
                if (!isBusy)
                    SetStatus(ex.Message, false);
            }
        }

        private async Task FetchOptionsAsync()
        {
            if (string.IsNullOrWhiteSpace(ApiKey) || string.IsNullOrWhiteSpace(OpenBullUrl))
            {
                SetStatus("Cannot refresh: API key or URL missing", false);
                return;
            }

            try
            {
                string url = OpenBullUrl.TrimEnd('/') + "/api/v1/futures-risk/quick-order/options";
                using (StringContent content = new StringContent(BuildOptionsJson(), Encoding.UTF8, "application/json"))
                {
                    HttpResponseMessage response = await Http.PostAsync(url, content);
                    string body = await response.Content.ReadAsStringAsync();
                    if (!response.IsSuccessStatusCode || body.IndexOf("\"status\":\"success\"", StringComparison.OrdinalIgnoreCase) < 0)
                    {
                        SetStatus(TrimForStatus(body), false);
                        return;
                    }

                    List<string> expiryValues = ParseExpiryValues(body);
                    List<string> strikeValues = ParseNumberArray(body, "strikes");
                    List<string> templateValues = ParseTemplates(body);
                    double atmStrike = ParseDouble(ExtractJsonValue(body, "atm"), 0);
                    double ceDefaultStrike = ParseDouble(ExtractJsonValue(body, "ce_default_strike"), atmStrike);
                    double peDefaultStrike = ParseDouble(ExtractJsonValue(body, "pe_default_strike"), atmStrike);
                    cachedExpiries = expiryValues.ToArray();
                    cachedStrikes = ParseStrikeCache(strikeValues);
                    CacheTemplateLabels(templateValues);
                    ChartControl.Dispatcher.InvokeAsync(() =>
                    {
                        settingsHydrating = true;
                        try
                        {
                            string mappedExchange = ExtractJsonValue(body, "underlying_exchange");
                            if (!string.IsNullOrWhiteSpace(mappedExchange))
                                UnderlyingExchange = mappedExchange.ToUpperInvariant();
                            string nextMode = ExtractJsonValue(body, "mode");
                            if (!string.IsNullOrWhiteSpace(nextMode) && nextMode != "null")
                                tradingMode = nextMode.ToUpperInvariant();

                            string saved = ExtractBlock(body, "saved");
                            string selectedExpiry = Expiry;
                            double selectedCe = SelectValidStrike(strikeValues, CeStrike, ceDefaultStrike);
                            double selectedPe = SelectValidStrike(strikeValues, PeStrike, peDefaultStrike);
                            if (!string.IsNullOrEmpty(saved))
                            {
                                string lots = ExtractJsonValue(saved, "lots");
                                string sl = ExtractJsonValue(saved, "sl_points");
                                string product = ExtractJsonValue(saved, "product");
                                string template = ExtractJsonValue(saved, "target_template_id");
                                string savedExchange = ExtractJsonValue(saved, "underlying_exchange");
                                string savedExpiry = ExtractJsonValue(saved, "expiry");
                                string savedCe = ExtractJsonValue(saved, "ce_strike");
                                string savedPe = ExtractJsonValue(saved, "pe_strike");
                                if (!string.IsNullOrEmpty(savedExchange) && savedExchange != "null")
                                    UnderlyingExchange = savedExchange.ToUpperInvariant();
                                if (!string.IsNullOrEmpty(savedExpiry) && savedExpiry != "null")
                                    selectedExpiry = savedExpiry.ToUpperInvariant();
                                if (!string.IsNullOrEmpty(savedCe) && savedCe != "null")
                                    selectedCe = SelectValidStrike(strikeValues, ParseDouble(savedCe, selectedCe), ceDefaultStrike);
                                if (!string.IsNullOrEmpty(savedPe) && savedPe != "null")
                                    selectedPe = SelectValidStrike(strikeValues, ParseDouble(savedPe, selectedPe), peDefaultStrike);
                                if (!string.IsNullOrEmpty(lots))
                                {
                                    Lots = Math.Max(1, ParseInt(lots, Lots));
                                    if (lotsBox != null) lotsBox.Text = Lots.ToString(CultureInfo.InvariantCulture);
                                }
                                if (!string.IsNullOrEmpty(sl))
                                {
                                    SlPoints = ParseDouble(sl, SlPoints);
                                    if (slBox != null) slBox.Text = SlPoints.ToString(CultureInfo.InvariantCulture);
                                }
                                if (!string.IsNullOrEmpty(product))
                                {
                                    Product = product.ToUpperInvariant();
                                    SelectCombo(productCombo, Product);
                                }
                                if (!string.IsNullOrEmpty(template) && template != "null")
                                {
                                    TargetTemplateId = Math.Max(0, ParseInt(template, TargetTemplateId));
                                    TargetTemplate = TemplateFallbackLabel(TargetTemplateId);
                                    SelectTemplateCombo(TargetTemplateId);
                                }
                            }
                            if (!ContainsText(expiryValues, selectedExpiry) && expiryValues.Count > 0)
                                selectedExpiry = expiryValues[0];
                            Expiry = string.IsNullOrWhiteSpace(selectedExpiry) ? Expiry : selectedExpiry.ToUpperInvariant();
                            CeStrike = selectedCe;
                            PeStrike = selectedPe;

                            string ceText = FormatStrikeText(CeStrike);
                            string peText = FormatStrikeText(PeStrike);
                            FillCombo(instrumentCombo, ParseStringArray(body, "underlyings"), Underlying);
                            FillCombo(expiryCombo, expiryValues, Expiry);
                            FillCombo(ceCombo, strikeValues, ceText);
                            FillCombo(peCombo, strikeValues, peText);
                            FillCombo(templateCombo, templateValues, TemplateFallbackLabel(TargetTemplateId));
                            FillCombo(productCombo, new List<string> { "NRML", "MIS", "CNC" }, Product);
                        }
                        finally
                        {
                            settingsHydrating = false;
                        }
                        UpdateModeText();
                        RefreshButtonText();
                    });
                }
            }
            catch (Exception ex)
            {
                SetStatus(ex.Message, false);
            }
        }

        private async Task SaveSettingsAsync()
        {
            if (settingsHydrating || string.IsNullOrWhiteSpace(ApiKey) || string.IsNullOrWhiteSpace(OpenBullUrl) || string.IsNullOrWhiteSpace(Underlying))
            {
                SetStatus("Cannot save: API key, URL, or instrument missing", false);
                return;
            }
            try
            {
                string url = OpenBullUrl.TrimEnd('/') + "/api/v1/futures-risk/quick-order/settings";
                using (StringContent content = new StringContent(BuildSettingsJson(), Encoding.UTF8, "application/json"))
                {
                    HttpResponseMessage response = await Http.PostAsync(url, content);
                    string body = await response.Content.ReadAsStringAsync();
                    if (!response.IsSuccessStatusCode || body.IndexOf("\"status\":\"success\"", StringComparison.OrdinalIgnoreCase) < 0)
                        SetStatus(TrimForStatus(body), false);
                    else
                        SetStatus("Settings saved", true);
                }
            }
            catch (Exception ex)
            {
                SetStatus(ex.Message, false);
            }
        }

        private async Task DeleteSettingsAsync()
        {
            if (string.IsNullOrWhiteSpace(ApiKey) || string.IsNullOrWhiteSpace(OpenBullUrl) || string.IsNullOrWhiteSpace(Underlying))
            {
                SetStatus("Cannot delete: API key, URL, or instrument missing", false);
                return;
            }
            try
            {
                string url = OpenBullUrl.TrimEnd('/') + "/api/v1/futures-risk/quick-order/settings/delete";
                StringBuilder sb = new StringBuilder();
                sb.Append("{");
                JsonString(sb, "apikey", ApiKey, true);
                JsonString(sb, "underlying", Underlying, false);
                sb.Append("}");
                using (StringContent content = new StringContent(sb.ToString(), Encoding.UTF8, "application/json"))
                {
                    HttpResponseMessage response = await Http.PostAsync(url, content);
                    string body = await response.Content.ReadAsStringAsync();
                    if (!response.IsSuccessStatusCode || body.IndexOf("\"status\":\"success\"", StringComparison.OrdinalIgnoreCase) < 0)
                        SetStatus(TrimForStatus(body), false);
                    else
                    {
                        SetStatus("Settings deleted", true);
                        await FetchOptionsAsync();
                    }
                }
            }
            catch (Exception ex)
            {
                SetStatus(ex.Message, false);
            }
        }

        private async Task SendQuickOrderAsync(string side, string optionType)
        {
            if (isBusy)
                return;
            CommitAllSettingInputs();
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
                    int tradeId = response.IsSuccessStatusCode ? (int)ExtractNestedNumber(body, "data", "id") : 0;
                    if (tradeId <= 0 && response.IsSuccessStatusCode)
                        tradeId = (int)ParseDouble(ExtractJsonValue(body, "id"), 0);

                    if (tradeId > 0)
                    {
                        await LinkPlacedTradeAsync(tradeId, optionType, ok);
                    }
                    else if (ok)
                    {
                        SetStatus("Order sent; trade id unavailable for chart levels", true);
                    }
                    else
                    {
                        SetStatus(TrimForStatus(body), false);
                    }
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
                await FetchLiveAsync();
            }
        }

        private async Task LinkPlacedTradeAsync(int tradeId, string optionType, bool orderAccepted = true)
        {
            OpenBullTradeSnapshot snapshot = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradeAsync(tradeId);
            if (snapshot == null)
            {
                SetStatus("Order sent; unable to load linked trade levels", false);
                return;
            }
            ApplyLiveOptionPrice(snapshot);
            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                LinkedTradeId = tradeId;
                AddLinkedTradeId(tradeId);
                RemoveDeletedLinkedTradeId(tradeId);
                LinkedTradeRemovedByUser = false;
                linkedBellSeenOnChart = false;
                managedTrade = snapshot;
                managedTrades[tradeId] = snapshot;
                if (!ShowPreviousTradeDrawings)
                    RemoveOtherTradeDrawings(tradeId, false);
                bool bellLinked = AttachBellDrawingTool(snapshot);
                if (orderAccepted)
                    SetStatus(bellLinked ? "Order sent - Bell drawing tool linked" : "Order sent - chart levels linked", true);
                else
                    SetStatus(bellLinked ? "Order recorded with broker issue - Bell drawing linked" : "Order recorded with broker issue - chart levels linked", false);
                RequestChartRefresh();
            });
        }

        private async Task RehydrateLinkedTradeAsync()
        {
            if (rehydrateAttempted || string.IsNullOrWhiteSpace(ApiKey))
                return;
            rehydrateAttempted = true;
            if (LinkedTradeRemovedByUser && LinkedTradeId > 0)
                AddDeletedLinkedTradeId(LinkedTradeId);
            await Task.Delay(500);
            List<OpenBullTradeSnapshot> snapshots = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradesAsync(Underlying);
            if (snapshots.Count == 0)
            {
                foreach (int id in ParseTradeIds(LinkedTradeIds))
                {
                    if (IsDeletedLinkedTradeId(id))
                        continue;
                    OpenBullTradeSnapshot snapshot = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradeAsync(id);
                    if (snapshot != null)
                        snapshots.Add(snapshot);
                }
                if (LinkedTradeId > 0 && !IsDeletedLinkedTradeId(LinkedTradeId))
                {
                    OpenBullTradeSnapshot snapshot = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradeAsync(LinkedTradeId);
                    if (snapshot != null)
                        snapshots.Add(snapshot);
                }
            }
            foreach (OpenBullTradeSnapshot snapshot in snapshots)
                ApplyLiveOptionPrice(snapshot);
            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                int restored = 0;
                List<OpenBullTradeSnapshot> visibleSnapshots = SelectVisibleSnapshots(snapshots);
                foreach (OpenBullTradeSnapshot snapshot in visibleSnapshots)
                {
                    if (snapshot == null || snapshot.TradeId <= 0 || IsDeletedLinkedTradeId(snapshot.TradeId))
                        continue;
                    managedTrade = snapshot;
                    managedTrades[snapshot.TradeId] = snapshot;
                    AddLinkedTradeId(snapshot.TradeId);
                    linkedBellTag = "OpenBull_FR_" + snapshot.TradeId.ToString(CultureInfo.InvariantCulture);
                    if (AttachBellDrawingTool(snapshot))
                        restored++;
                }
                if (restored > 0)
                    SetStatus("Restored " + restored.ToString(CultureInfo.InvariantCulture) + " Bell drawing tool(s)", true);
                RequestChartRefresh();
            });
        }

        private async Task RefreshManagedTradeAsync()
        {
            List<int> ids = new List<int>(managedTrades.Keys);
            if (managedTrade != null && managedTrade.TradeId > 0 && !ids.Contains(managedTrade.TradeId))
                ids.Add(managedTrade.TradeId);
            if (ids.Count == 0)
                return;
            foreach (int id in ids)
            {
                string tag = BellTag(id);
                if (linkedBellTools.ContainsKey(id) && linkedBellSeenTradeIds.Contains(id) && !DrawingToolExists(tag))
                {
                    AddDeletedLinkedTradeId(id);
                    linkedBellTools.Remove(id);
                    linkedBellSeenTradeIds.Remove(id);
                    managedTrades.Remove(id);
                    if (managedTrade != null && managedTrade.TradeId == id)
                        managedTrade = null;
                    SetStatus("Bell drawing removed manually; link kept off this chart", true);
                    RequestChartRefresh();
                    continue;
                }
                if (IsDeletedLinkedTradeId(id))
                    continue;
                if (!ShowPreviousTradeDrawings && LinkedTradeId > 0 && id != LinkedTradeId)
                {
                    RemoveTradeDrawing(id, false);
                    continue;
                }
                OpenBullTradeSnapshot snapshot = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradeAsync(id);
                if (snapshot == null)
                    continue;
                ApplyLiveOptionPrice(snapshot);
                ChartControl.Dispatcher.InvokeAsync(() =>
                {
                    if (managedTrade == null || snapshot.TradeId == LinkedTradeId)
                        managedTrade = snapshot;
                    managedTrades[snapshot.TradeId] = snapshot;
                    if (linkedBellTools.ContainsKey(snapshot.TradeId))
                        AttachBellDrawingTool(snapshot);
                    RequestChartRefresh();
                });
            }
        }

        private bool AttachBellDrawingTool(OpenBullTradeSnapshot snapshot)
        {
            if (snapshot == null || snapshot.TradeId <= 0 || snapshot.EntryFuturesPrice <= 0 || snapshot.StopLossPrice <= 0)
                return false;
            if (IsDeletedLinkedTradeId(snapshot.TradeId))
                return false;
            if (ChartBars == null || ChartBars.Bars == null || ChartBars.Bars.Count <= 0)
                return false;

            DateTime entryTime;
            DateTime endTime;
            ResolveBellToolTimes(snapshot, out entryTime, out endTime);
            linkedBellTag = BellTag(snapshot.TradeId);
            if (snapshot.Direction >= 0)
            {
                Bell_LongEntryTool tool = Draw.BellLongEntry(
                    this,
                    linkedBellTag,
                    false,
                    entryTime,
                    endTime,
                    snapshot.EntryFuturesPrice,
                    snapshot.StopLossPrice,
                    snapshot.Targets,
                    snapshot.TradeId,
                    snapshot.Mtm
                );
                linkedBellTool = tool;
                linkedBellTools[snapshot.TradeId] = tool;
            }
            else
            {
                Bell_ShortEntryTool tool = Draw.BellShortEntry(
                    this,
                    linkedBellTag,
                    false,
                    entryTime,
                    endTime,
                    snapshot.EntryFuturesPrice,
                    snapshot.StopLossPrice,
                    snapshot.Targets,
                    snapshot.TradeId,
                    snapshot.Mtm
                );
                linkedBellTool = tool;
                linkedBellTools[snapshot.TradeId] = tool;
            }
            linkedBellSeenOnChart = linkedBellTool != null && DrawingToolExists(linkedBellTag);
            if (linkedBellSeenOnChart)
                linkedBellSeenTradeIds.Add(snapshot.TradeId);
            return linkedBellTool != null;
        }

        private List<OpenBullTradeSnapshot> SelectVisibleSnapshots(List<OpenBullTradeSnapshot> snapshots)
        {
            if (ShowPreviousTradeDrawings)
                return snapshots ?? new List<OpenBullTradeSnapshot>();
            OpenBullTradeSnapshot selected = null;
            if (snapshots != null)
            {
                foreach (OpenBullTradeSnapshot snapshot in snapshots)
                {
                    if (snapshot == null || snapshot.TradeId <= 0 || IsDeletedLinkedTradeId(snapshot.TradeId))
                        continue;
                    if (selected == null)
                    {
                        selected = snapshot;
                        continue;
                    }
                    bool snapshotActive = string.Equals(snapshot.Status, "active", StringComparison.OrdinalIgnoreCase);
                    bool selectedActive = string.Equals(selected.Status, "active", StringComparison.OrdinalIgnoreCase);
                    if ((snapshotActive && !selectedActive) ||
                        (snapshotActive == selectedActive && snapshot.CreatedAt > selected.CreatedAt) ||
                        (snapshotActive == selectedActive && snapshot.CreatedAt == selected.CreatedAt && snapshot.TradeId > selected.TradeId))
                        selected = snapshot;
                }
            }
            if (selected == null)
                return new List<OpenBullTradeSnapshot>();
            LinkedTradeId = selected.TradeId;
            RemoveOtherTradeDrawings(selected.TradeId, false);
            return new List<OpenBullTradeSnapshot> { selected };
        }

        private void RefreshDrawingVisibility()
        {
            if (ShowPreviousTradeDrawings)
            {
                Task.Run(async () => await RehydrateAdditionalTradeDrawingsAsync());
                return;
            }
            int keepId = LinkedTradeId;
            if (keepId <= 0 && managedTrade != null)
                keepId = managedTrade.TradeId;
            RemoveOtherTradeDrawings(keepId, false);
            RequestChartRefresh();
        }

        private async Task RehydrateAdditionalTradeDrawingsAsync()
        {
            List<OpenBullTradeSnapshot> snapshots = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradesAsync(Underlying);
            foreach (OpenBullTradeSnapshot snapshot in snapshots)
                ApplyLiveOptionPrice(snapshot);
            if (ChartControl == null)
                return;
            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                foreach (OpenBullTradeSnapshot snapshot in snapshots)
                {
                    if (snapshot == null || snapshot.TradeId <= 0 || IsDeletedLinkedTradeId(snapshot.TradeId))
                        continue;
                    managedTrades[snapshot.TradeId] = snapshot;
                    AddLinkedTradeId(snapshot.TradeId);
                    AttachBellDrawingTool(snapshot);
                }
                RequestChartRefresh();
            });
        }

        private async Task RemoveCurrentTradeDrawingAsync()
        {
            if (ChartControl == null)
                return;
            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                int id = LinkedTradeId;
                if (id <= 0 && managedTrade != null)
                    id = managedTrade.TradeId;
                if (id <= 0)
                {
                    SetStatus("No linked OpenBull drawing to remove", false);
                    return;
                }
                RemoveTradeDrawing(id, true);
                if (LinkedTradeId == id)
                    LinkedTradeId = 0;
                SetStatus("OpenBull trade drawing removed", true);
                RequestChartRefresh();
            });
            await Task.CompletedTask;
        }

        private void RemoveOtherTradeDrawings(int keepTradeId, bool remember)
        {
            List<int> ids = new List<int>(managedTrades.Keys);
            foreach (int id in ParseTradeIds(LinkedTradeIds))
                if (!ids.Contains(id))
                    ids.Add(id);
            foreach (int id in ids)
            {
                if (id > 0 && id != keepTradeId)
                    RemoveTradeDrawing(id, remember);
            }
        }

        private void RemoveTradeDrawing(int tradeId, bool remember)
        {
            if (tradeId <= 0)
                return;
            string tag = BellTag(tradeId);
            try
            {
                RemoveDrawObject(tag);
            }
            catch
            {
            }
            if (remember)
                AddDeletedLinkedTradeId(tradeId);
            linkedBellTools.Remove(tradeId);
            linkedBellSeenTradeIds.Remove(tradeId);
            managedTrades.Remove(tradeId);
            if (managedTrade != null && managedTrade.TradeId == tradeId)
                managedTrade = null;
            if (linkedBellTag == tag)
            {
                linkedBellTag = "";
                linkedBellTool = null;
            }
        }

        private bool DrawingToolExists(string tag)
        {
            if (string.IsNullOrWhiteSpace(tag))
                return false;
            try
            {
                foreach (DrawingTool tool in DrawObjects)
                {
                    if (tool != null && string.Equals(tool.Tag, tag, StringComparison.Ordinal))
                        return true;
                }
            }
            catch
            {
                return linkedBellTool != null;
            }
            return false;
        }

        private static string BellTag(int tradeId)
        {
            return "OpenBull_FR_" + tradeId.ToString(CultureInfo.InvariantCulture);
        }

        private static HashSet<int> ParseTradeIds(string value)
        {
            HashSet<int> ids = new HashSet<int>();
            if (string.IsNullOrWhiteSpace(value))
                return ids;
            string[] parts = value.Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            foreach (string part in parts)
            {
                int id = ParseInt(part.Trim(), 0);
                if (id > 0)
                    ids.Add(id);
            }
            return ids;
        }

        private static string FormatTradeIds(HashSet<int> ids)
        {
            if (ids == null || ids.Count == 0)
                return "";
            List<int> sorted = new List<int>(ids);
            sorted.Sort();
            StringBuilder sb = new StringBuilder();
            foreach (int id in sorted)
            {
                if (sb.Length > 0)
                    sb.Append(",");
                sb.Append(id.ToString(CultureInfo.InvariantCulture));
            }
            return sb.ToString();
        }

        private void AddLinkedTradeId(int tradeId)
        {
            if (tradeId <= 0)
                return;
            HashSet<int> ids = ParseTradeIds(LinkedTradeIds);
            ids.Add(tradeId);
            LinkedTradeIds = FormatTradeIds(ids);
        }

        private bool IsDeletedLinkedTradeId(int tradeId)
        {
            return tradeId > 0 && ParseTradeIds(RemovedLinkedTradeIds).Contains(tradeId);
        }

        private void AddDeletedLinkedTradeId(int tradeId)
        {
            if (tradeId <= 0)
                return;
            HashSet<int> ids = ParseTradeIds(RemovedLinkedTradeIds);
            ids.Add(tradeId);
            RemovedLinkedTradeIds = FormatTradeIds(ids);
            if (LinkedTradeId == tradeId)
                LinkedTradeRemovedByUser = true;
        }

        private void RemoveDeletedLinkedTradeId(int tradeId)
        {
            if (tradeId <= 0)
                return;
            HashSet<int> ids = ParseTradeIds(RemovedLinkedTradeIds);
            if (ids.Remove(tradeId))
                RemovedLinkedTradeIds = FormatTradeIds(ids);
            LinkedTradeRemovedByUser = false;
        }

        private void ResolveBellToolTimes(OpenBullTradeSnapshot snapshot, out DateTime entryTime, out DateTime endTime)
        {
            entryTime = DateTime.MinValue;
            endTime = DateTime.MinValue;
            if (ChartBars == null || ChartBars.Bars == null || ChartBars.Bars.Count <= 0)
                return;

            int count = ChartBars.Bars.Count;
            int startIndex = Math.Max(0, count - 12);
            int endIndex = Math.Max(0, count - 1);
            if (snapshot != null && snapshot.CreatedAt != DateTime.MinValue)
            {
                int createdIndex = ChartBars.Bars.GetBar(snapshot.CreatedAt);
                if (createdIndex >= 0)
                {
                    startIndex = Math.Max(0, Math.Min(createdIndex, count - 1));
                    endIndex = Math.Min(count - 1, startIndex + 10);
                    if (endIndex == startIndex && startIndex > 0)
                        startIndex = Math.Max(0, startIndex - 10);
                }
            }
            entryTime = ChartBars.Bars.GetTime(startIndex);
            endTime = ChartBars.Bars.GetTime(endIndex);
            if (endTime <= entryTime)
                endTime = entryTime.AddMinutes(10);
        }

        private async Task SyncManagedLevelsAsync()
        {
            if (managedTrade == null || managedTrade.TradeId <= 0)
                return;
            List<OpenBullLevelTarget> targets = new List<OpenBullLevelTarget>();
            foreach (OpenBullTradeLevel target in managedTrade.Targets)
            {
                if (target == null || target.Price <= 0 || !string.Equals(target.Status, "pending", StringComparison.OrdinalIgnoreCase))
                    continue;
                targets.Add(new OpenBullLevelTarget { Seq = target.Seq, Price = target.Price, ExitPct = target.ExitPct > 0 ? (double?)target.ExitPct : null });
            }
            string result = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.UpdateLevelsAsync(managedTrade.TradeId, managedTrade.StopLossPrice, targets);
            bool ok = string.Equals(result, "Levels synced", StringComparison.OrdinalIgnoreCase);
            SetStatus(ok ? "Levels synced to OpenBull" : result, ok);
            await RefreshManagedTradeAsync();
        }

        private void ApplyLiveOptionPrice(OpenBullTradeSnapshot snapshot)
        {
            if (snapshot == null)
                return;
            if (snapshot.LiveOptionPrice > 0)
                return;
            if (string.Equals(snapshot.OptionType, "CE", StringComparison.OrdinalIgnoreCase))
                snapshot.LiveOptionPrice = ceLtp;
            else if (string.Equals(snapshot.OptionType, "PE", StringComparison.OrdinalIgnoreCase))
                snapshot.LiveOptionPrice = peLtp;
        }

        private string BuildPreviewJson()
        {
            StringBuilder sb = new StringBuilder();
            sb.Append("{");
            JsonString(sb, "apikey", ApiKey, true);
            JsonString(sb, "underlying", Underlying, false);
            JsonString(sb, "underlying_exchange", UnderlyingExchange, false);
            JsonString(sb, "expiry", Expiry, false);
            JsonNumber(sb, "ce_strike", CeStrike, false);
            JsonNumber(sb, "pe_strike", PeStrike, false);
            sb.Append("}");
            return sb.ToString();
        }

        private string BuildOptionsJson()
        {
            StringBuilder sb = new StringBuilder();
            sb.Append("{");
            JsonString(sb, "apikey", ApiKey, true);
            JsonString(sb, "underlying", Underlying, false);
            JsonString(sb, "underlying_exchange", UnderlyingExchange, false);
            JsonString(sb, "expiry", Expiry, false);
            sb.Append("}");
            return sb.ToString();
        }

        private string BuildSettingsJson()
        {
            StringBuilder sb = new StringBuilder();
            sb.Append("{");
            JsonString(sb, "apikey", ApiKey, true);
            JsonString(sb, "underlying", Underlying, false);
            JsonString(sb, "underlying_exchange", UnderlyingExchange, false);
            JsonString(sb, "expiry", Expiry, false);
            JsonNumber(sb, "ce_strike", CeStrike, false);
            JsonNumber(sb, "pe_strike", PeStrike, false);
            JsonNumber(sb, "lots", Lots, false);
            JsonNumber(sb, "sl_points", SlPoints, false);
            JsonString(sb, "product", Product, false);
            JsonNumber(sb, "target_template_id", CurrentTargetTemplateId(), false);
            sb.Append("}");
            return sb.ToString();
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
            int templateId = CurrentTargetTemplateId();
            if (templateId > 0 && !UseOverrideTargets)
                JsonNumber(sb, "target_template_id", templateId, false);
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

        private static double ExtractLtp(string body, string blockName)
        {
            if (string.IsNullOrEmpty(body))
                return 0;
            Match block = Regex.Match(
                body,
                "\"" + Regex.Escape(blockName) + "\"\\s*:\\s*\\{(?<body>.*?)\\}",
                RegexOptions.Singleline | RegexOptions.IgnoreCase
            );
            if (!block.Success)
                return 0;
            Match ltp = Regex.Match(block.Groups["body"].Value, "\"ltp\"\\s*:\\s*(?<ltp>-?\\d+(?:\\.\\d+)?)", RegexOptions.IgnoreCase);
            if (!ltp.Success)
                return 0;
            double parsed;
            return double.TryParse(ltp.Groups["ltp"].Value, NumberStyles.Any, CultureInfo.InvariantCulture, out parsed) ? parsed : 0;
        }

        private static double ExtractNestedNumber(string body, string blockName, string key)
        {
            if (string.IsNullOrEmpty(body))
                return 0;
            string blockBody = ExtractBlock(body, blockName);
            if (string.IsNullOrEmpty(blockBody))
                return 0;
            string raw = ExtractJsonValue(blockBody, key);
            double parsed;
            return double.TryParse(raw, NumberStyles.Any, CultureInfo.InvariantCulture, out parsed) ? parsed : 0;
        }

        private static string ExtractBlock(string body, string blockName)
        {
            Match block = Regex.Match(
                body,
                "\"" + Regex.Escape(blockName) + "\"\\s*:\\s*\\{(?<body>.*?)\\}",
                RegexOptions.Singleline | RegexOptions.IgnoreCase
            );
            return block.Success ? block.Groups["body"].Value : "";
        }

        private static string ExtractJsonValue(string body, string key)
        {
            Match m = Regex.Match(
                body,
                "\"" + Regex.Escape(key) + "\"\\s*:\\s*(?:\"(?<str>[^\"]*)\"|(?<num>-?\\d+(?:\\.\\d+)?)|(?<null>null))",
                RegexOptions.IgnoreCase
            );
            if (!m.Success)
                return "";
            if (m.Groups["str"].Success)
                return Unescape(m.Groups["str"].Value);
            if (m.Groups["num"].Success)
                return m.Groups["num"].Value;
            return "null";
        }

        private static List<string> ParseStringArray(string body, string key)
        {
            List<string> result = new List<string>();
            Match array = Regex.Match(body, "\"" + Regex.Escape(key) + "\"\\s*:\\s*\\[(?<body>.*?)\\]", RegexOptions.Singleline | RegexOptions.IgnoreCase);
            if (!array.Success)
                return result;
            foreach (Match m in Regex.Matches(array.Groups["body"].Value, "\"(?<v>[^\"]+)\""))
                result.Add(Unescape(m.Groups["v"].Value));
            return result;
        }

        private static List<string> ParseNumberArray(string body, string key)
        {
            List<string> result = new List<string>();
            Match array = Regex.Match(body, "\"" + Regex.Escape(key) + "\"\\s*:\\s*\\[(?<body>.*?)\\]", RegexOptions.Singleline | RegexOptions.IgnoreCase);
            if (!array.Success)
                return result;
            foreach (Match m in Regex.Matches(array.Groups["body"].Value, "-?\\d+(?:\\.\\d+)?"))
                result.Add(m.Value);
            return result;
        }

        private static double[] ParseStrikeCache(List<string> values)
        {
            List<double> strikes = new List<double>();
            if (values == null)
                return strikes.ToArray();
            foreach (string value in values)
            {
                double parsed = ParseDouble(value, 0);
                if (parsed > 0)
                    strikes.Add(parsed);
            }
            return strikes.ToArray();
        }

        private static bool ContainsText(List<string> values, string selected)
        {
            if (values == null || string.IsNullOrWhiteSpace(selected))
                return false;
            foreach (string value in values)
                if (string.Equals(value, selected, StringComparison.OrdinalIgnoreCase))
                    return true;
            return false;
        }

        private static string FormatStrikeText(double strike)
        {
            if (strike <= 0)
                return "";
            return Math.Abs(strike - Math.Round(strike)) < 0.0001
                ? strike.ToString("0", CultureInfo.InvariantCulture)
                : strike.ToString("0.##", CultureInfo.InvariantCulture);
        }

        private static double SelectValidStrike(List<string> strikeValues, double preferred, double fallback)
        {
            double[] strikes = ParseStrikeCache(strikeValues);
            if (strikes.Length == 0)
                return preferred > 0 ? preferred : fallback;

            if (preferred > 0)
            {
                foreach (double strike in strikes)
                    if (Math.Abs(strike - preferred) < 0.0001)
                        return strike;
            }

            if (fallback > 0)
            {
                double closest = strikes[0];
                double closestDistance = Math.Abs(closest - fallback);
                for (int i = 1; i < strikes.Length; i++)
                {
                    double distance = Math.Abs(strikes[i] - fallback);
                    if (distance < closestDistance)
                    {
                        closest = strikes[i];
                        closestDistance = distance;
                    }
                }
                return closest;
            }

            return strikes[strikes.Length / 2];
        }

        private static List<string> ParseExpiryValues(string body)
        {
            List<string> result = new List<string>();
            Match array = Regex.Match(body, "\"expiries\"\\s*:\\s*\\[(?<body>.*?)\\]", RegexOptions.Singleline | RegexOptions.IgnoreCase);
            if (!array.Success)
                return result;
            foreach (Match m in Regex.Matches(array.Groups["body"].Value, "\"value\"\\s*:\\s*\"(?<v>[^\"]+)\"", RegexOptions.IgnoreCase))
                result.Add(Unescape(m.Groups["v"].Value));
            return result;
        }

        private static List<string> ParseTemplates(string body)
        {
            List<string> result = new List<string>();
            result.Add(TemplateFallbackLabel(0));
            Match array = Regex.Match(body, "\"templates\"\\s*:\\s*\\[(?<body>.*?)\\]", RegexOptions.Singleline | RegexOptions.IgnoreCase);
            if (!array.Success)
                return result;
            foreach (Match m in Regex.Matches(array.Groups["body"].Value, "\\{(?<obj>.*?)\\}", RegexOptions.Singleline))
            {
                string obj = m.Groups["obj"].Value;
                string id = ExtractJsonValue(obj, "id");
                if (string.IsNullOrWhiteSpace(id) || id == "null")
                    continue;
                string name = ExtractJsonValue(obj, "name");
                if (string.IsNullOrWhiteSpace(name) || name == "null")
                    name = "Template";
                string defaultMark = Regex.IsMatch(obj, "\"is_default\"\\s*:\\s*true", RegexOptions.IgnoreCase) ? " (default)" : "";
                result.Add(id + " - " + name + defaultMark);
            }
            return result;
        }

        private static void CacheTemplateLabels(List<string> labels)
        {
            Dictionary<int, string> nextLabels = new Dictionary<int, string>();
            List<int> nextIds = new List<int>();
            nextLabels[0] = TemplateFallbackLabel(0);
            nextIds.Add(0);
            foreach (string label in labels)
            {
                int id = ParseTemplateId(label, -1);
                if (id < 0)
                    continue;
                nextLabels[id] = label;
                if (!nextIds.Contains(id))
                    nextIds.Add(id);
            }
            lock (templateCacheLock)
            {
                cachedTemplateLabels.Clear();
                foreach (KeyValuePair<int, string> pair in nextLabels)
                    cachedTemplateLabels[pair.Key] = pair.Value;
                cachedTemplateIds = nextIds.ToArray();
            }
        }

        private static void TryRefreshTemplateCache(OpenBullQuickOrderIndicator instance)
        {
            if (instance == null || string.IsNullOrWhiteSpace(instance.ApiKey) || string.IsNullOrWhiteSpace(instance.OpenBullUrl))
                return;
            string key = instance.OpenBullUrl.TrimEnd('/') + "|" + instance.ApiKey + "|" + instance.Underlying + "|" + instance.UnderlyingExchange + "|" + instance.Expiry;
            lock (templateCacheLock)
            {
                if (key == templateCacheKey && (DateTime.UtcNow - templateCacheAt).TotalSeconds < 20)
                    return;
                templateCacheKey = key;
                templateCacheAt = DateTime.UtcNow;
            }
            try
            {
                string url = instance.OpenBullUrl.TrimEnd('/') + "/api/v1/futures-risk/quick-order/options";
                using (StringContent content = new StringContent(instance.BuildOptionsJson(), Encoding.UTF8, "application/json"))
                {
                    HttpResponseMessage response = Http.PostAsync(url, content).GetAwaiter().GetResult();
                    string body = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    if (response.IsSuccessStatusCode && body.IndexOf("\"status\":\"success\"", StringComparison.OrdinalIgnoreCase) >= 0)
                        CacheTemplateLabels(ParseTemplates(body));
                }
            }
            catch
            {
            }
        }

        private static string TemplateFallbackLabel(int id)
        {
            lock (templateCacheLock)
            {
                string label;
                if (cachedTemplateLabels.TryGetValue(id, out label) && !string.IsNullOrWhiteSpace(label))
                    return label;
            }
            return id <= 0 ? "0 - Saved/default" : id.ToString(CultureInfo.InvariantCulture);
        }

        private static int ParseTemplateId(string value, int fallback)
        {
            if (string.IsNullOrWhiteSpace(value))
                return fallback;
            Match m = Regex.Match(value.Trim(), "^(?<id>\\d+)");
            if (m.Success)
                return ParseInt(m.Groups["id"].Value, fallback);
            return ParseInt(value, fallback);
        }

        private void SelectTemplateCombo(int templateId)
        {
            if (templateCombo == null)
                return;
            string fallback = TemplateFallbackLabel(templateId);
            foreach (object item in templateCombo.Items)
            {
                string text = item == null ? "" : item.ToString();
                if (ParseTemplateId(text, -1) == templateId)
                {
                    TargetTemplate = text;
                    SelectCombo(templateCombo, text);
                    return;
                }
            }
            TargetTemplate = fallback;
            SeedCombo(templateCombo, fallback);
            SelectCombo(templateCombo, fallback);
        }

        private int CurrentTargetTemplateId()
        {
            int id = ParseTemplateId(TargetTemplate, TargetTemplateId);
            TargetTemplateId = Math.Max(0, id);
            if (string.IsNullOrWhiteSpace(TargetTemplate))
                TargetTemplate = TemplateFallbackLabel(TargetTemplateId);
            return TargetTemplateId;
        }

        private static string Unescape(string value)
        {
            return (value ?? "").Replace("\\\"", "\"").Replace("\\\\", "\\");
        }

        private void FillCombo(ComboBox combo, List<string> values, string selected)
        {
            if (combo == null)
                return;
            combo.Items.Clear();
            foreach (string value in values)
                if (!string.IsNullOrWhiteSpace(value))
                    combo.Items.Add(value);
            SeedCombo(combo, selected);
            SelectCombo(combo, selected);
            RefreshComboDisplay(combo);
        }

        private void SeedCombo(ComboBox combo, string selected)
        {
            if (combo == null || string.IsNullOrWhiteSpace(selected))
                return;
            bool exists = false;
            foreach (object item in combo.Items)
            {
                if (string.Equals(item.ToString(), selected, StringComparison.OrdinalIgnoreCase))
                {
                    exists = true;
                    break;
                }
            }
            if (!exists)
                combo.Items.Add(selected);
            combo.Text = selected;
            RefreshComboDisplay(combo);
        }

        private void SelectCombo(ComboBox combo, string selected)
        {
            if (combo == null || string.IsNullOrEmpty(selected))
                return;
            foreach (object item in combo.Items)
            {
                if (string.Equals(item.ToString(), selected, StringComparison.OrdinalIgnoreCase))
                {
                    combo.SelectedItem = item;
                    combo.Text = item.ToString();
                    RefreshComboDisplay(combo);
                    return;
                }
            }
            if (combo.Items.Count > 0 && combo.SelectedItem == null)
            {
                combo.SelectedIndex = 0;
                combo.Text = combo.SelectedItem == null ? selected : combo.SelectedItem.ToString();
            }
            RefreshComboDisplay(combo);
        }

        private void RefreshComboDisplay(ComboBox combo)
        {
            if (combo == null || !comboDisplays.ContainsKey(combo))
                return;
            TextBlock display = comboDisplays[combo];
            string value = combo.SelectedItem == null ? combo.Text : combo.SelectedItem.ToString();
            display.Text = string.IsNullOrWhiteSpace(value) ? "--" : value;
        }

        private void UpdateMtmText()
        {
            string value = (mtmValue >= 0 ? "+" : "") + mtmValue.ToString("N2", CultureInfo.InvariantCulture);
            Brush brush = mtmValue >= 0
                ? new SolidColorBrush(Color.FromRgb(20, 220, 150))
                : new SolidColorBrush(Color.FromRgb(255, 95, 95));
            if (mtmText != null)
            {
                mtmText.Text = value;
                mtmText.Foreground = brush;
            }
            if (restoreMtmText != null)
            {
                restoreMtmText.Text = "MTM " + value;
                restoreMtmText.Foreground = brush;
            }
        }

        private void UpdateModeText()
        {
            if (modeText == null)
                return;
            string value = string.IsNullOrWhiteSpace(tradingMode) ? "--" : tradingMode.ToUpperInvariant();
            if (value != "LIVE" && value != "SANDBOX")
                value = "--";
            modeText.Text = value;
            modeText.Foreground = value == "LIVE"
                ? new SolidColorBrush(Color.FromRgb(20, 220, 150))
                : value == "SANDBOX"
                    ? new SolidColorBrush(Color.FromRgb(150, 118, 255))
                    : new SolidColorBrush(Color.FromRgb(150, 150, 150));
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
            if (value.StartsWith("{", StringComparison.Ordinal))
            {
                string message = ExtractJsonValue(value, "message");
                if (string.IsNullOrWhiteSpace(message) || message == "null")
                    message = ExtractJsonValue(value, "detail");
                if (!string.IsNullOrWhiteSpace(message) && message != "null")
                    value = message;
            }
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
            dragMoved = false;
            dragStart = e.GetPosition(ChartControl);
            dragStartMargin = root.Margin;
            Mouse.Capture(sender as IInputElement);
        }

        private void DragMove(object sender, MouseEventArgs e)
        {
            if (!isDragging || root == null || ChartControl == null)
                return;
            Point pos = e.GetPosition(ChartControl);
            double dx = pos.X - dragStart.X;
            double dy = pos.Y - dragStart.Y;
            if (Math.Abs(dx) > 2 || Math.Abs(dy) > 2)
                dragMoved = true;
            double nextLeft = Math.Max(4, dragStartMargin.Left + dx);
            double nextTop = Math.Max(4, dragStartMargin.Top + dy);
            root.Margin = new Thickness(nextLeft, nextTop, 0, 0);
        }

        private void StopDrag(object sender, MouseButtonEventArgs e)
        {
            isDragging = false;
            Mouse.Capture(null);
        }

        private void RestoreMouseUp(object sender, MouseButtonEventArgs e)
        {
            bool shouldOpen = !dragMoved;
            StopDrag(sender, e);
            if (!shouldOpen)
            {
                dragMoved = false;
                return;
            }
            if (root != null)
                root.Width = 580;
            if (popup != null)
                popup.Visibility = Visibility.Visible;
            if (restoreButton != null)
                restoreButton.Visibility = Visibility.Collapsed;
            dragMoved = false;
        }

        private static double ParseDouble(string value, double fallback)
        {
            double parsed;
            return double.TryParse(value, NumberStyles.Any, CultureInfo.InvariantCulture, out parsed) ? parsed : fallback;
        }

        private double RoundToChartTick(double price)
        {
            try
            {
                if (Instrument != null && Instrument.MasterInstrument != null)
                {
                    double tickSize = Instrument.MasterInstrument.TickSize;
                    if (tickSize > 0)
                        return Math.Round(price / tickSize) * tickSize;
                }
            }
            catch
            {
            }
            return Math.Round(price, 2);
        }

        private string FormatChartPrice(double price)
        {
            try
            {
                if (Instrument != null && Instrument.MasterInstrument != null)
                    return price.ToString(Core.Globals.GetTickFormatString(Instrument.MasterInstrument.TickSize));
            }
            catch
            {
            }
            return price.ToString("0.##", CultureInfo.InvariantCulture);
        }

        private static int ParseInt(string value, int fallback)
        {
            int parsed;
            return int.TryParse(value, NumberStyles.Any, CultureInfo.InvariantCulture, out parsed) ? parsed : fallback;
        }

        public class UnderlyingListConverter : StringConverter
        {
            public override bool GetStandardValuesSupported(ITypeDescriptorContext context) { return true; }
            public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) { return false; }
            public override TypeConverter.StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
            {
                return new TypeConverter.StandardValuesCollection(new string[] { "NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "SILVER", "GOLD" });
            }
        }

        public class UnderlyingExchangeListConverter : StringConverter
        {
            public override bool GetStandardValuesSupported(ITypeDescriptorContext context) { return true; }
            public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) { return false; }
            public override TypeConverter.StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
            {
                return new TypeConverter.StandardValuesCollection(new string[] { "NSE_INDEX", "BSE_INDEX", "MCX" });
            }
        }

        public class ProductListConverter : StringConverter
        {
            public override bool GetStandardValuesSupported(ITypeDescriptorContext context) { return true; }
            public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) { return false; }
            public override TypeConverter.StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
            {
                return new TypeConverter.StandardValuesCollection(new string[] { "NRML", "MIS", "CNC" });
            }
        }

        public class ExpiryListConverter : StringConverter
        {
            public override bool GetStandardValuesSupported(ITypeDescriptorContext context) { return true; }
            public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) { return false; }
            public override TypeConverter.StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
            {
                return new TypeConverter.StandardValuesCollection(cachedExpiries);
            }
        }

        public class StrikeListConverter : System.ComponentModel.DoubleConverter
        {
            public override bool GetStandardValuesSupported(ITypeDescriptorContext context) { return true; }
            public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) { return false; }
            public override TypeConverter.StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
            {
                return new TypeConverter.StandardValuesCollection(cachedStrikes);
            }
        }

        public class TargetTemplateListConverter : StringConverter
        {
            public override bool GetStandardValuesSupported(ITypeDescriptorContext context) { return true; }
            public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) { return false; }
            public override TypeConverter.StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
            {
                OpenBullQuickOrderIndicator instance = context == null ? null : context.Instance as OpenBullQuickOrderIndicator;
                TryRefreshTemplateCache(instance);
                List<string> values = new List<string>();
                lock (templateCacheLock)
                {
                    foreach (int id in cachedTemplateIds)
                    {
                        string label = TemplateFallbackLabel(id);
                        if (!values.Contains(label))
                            values.Add(label);
                    }
                }
                if (instance != null && !string.IsNullOrWhiteSpace(instance.TargetTemplate) && !values.Contains(instance.TargetTemplate))
                    values.Add(instance.TargetTemplate);
                return new TypeConverter.StandardValuesCollection(values);
            }
        }

        [NinjaScriptProperty]
        [Display(Name = "OpenBull URL", GroupName = "OpenBull", Order = 1)]
        public string OpenBullUrl { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "API Key", GroupName = "OpenBull", Order = 2)]
        public string ApiKey { get; set; }

        [NinjaScriptProperty]
        [TypeConverter(typeof(UnderlyingListConverter))]
        [Display(Name = "Underlying", GroupName = "Contract", Order = 10)]
        public string Underlying { get; set; }

        [NinjaScriptProperty]
        [TypeConverter(typeof(UnderlyingExchangeListConverter))]
        [Display(Name = "Underlying Exchange", GroupName = "Contract", Order = 11)]
        public string UnderlyingExchange { get; set; }

        [NinjaScriptProperty]
        [TypeConverter(typeof(ExpiryListConverter))]
        [Display(Name = "Expiry", GroupName = "Contract", Order = 12)]
        public string Expiry { get; set; }

        [NinjaScriptProperty]
        [TypeConverter(typeof(StrikeListConverter))]
        [Display(Name = "CE Strike", GroupName = "Contract", Order = 13)]
        public double CeStrike { get; set; }

        [NinjaScriptProperty]
        [TypeConverter(typeof(StrikeListConverter))]
        [Display(Name = "PE Strike", GroupName = "Contract", Order = 14)]
        public double PeStrike { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Lots", GroupName = "Order", Order = 20)]
        public int Lots { get; set; }

        [NinjaScriptProperty]
        [TypeConverter(typeof(ProductListConverter))]
        [Display(Name = "Product", GroupName = "Order", Order = 21)]
        public string Product { get; set; }

        [NinjaScriptProperty]
        [Range(0.01, double.MaxValue)]
        [Display(Name = "SL Points", GroupName = "Risk", Order = 30)]
        public double SlPoints { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        public int TargetTemplateId { get; set; }

        [NinjaScriptProperty]
        [TypeConverter(typeof(TargetTemplateListConverter))]
        [Display(Name = "Target Template", GroupName = "Risk", Order = 31)]
        public string TargetTemplate { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Previous Trade Drawings", GroupName = "Chart Levels", Order = 1)]
        public bool ShowPreviousTradeDrawings { get; set; }

        [NinjaScriptProperty]
        [Range(500, 10000)]
        [Display(Name = "Live Poll Ms", GroupName = "OpenBull", Order = 3)]
        public int LivePollMs { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        [Display(Name = "Use Override Targets", GroupName = "Risk", Order = 32)]
        public bool UseOverrideTargets { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        [Display(Name = "Auto Split Targets", GroupName = "Risk", Order = 33)]
        public bool AutoSplitTargets { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        [Display(Name = "T1 Points", GroupName = "Override Targets", Order = 40)]
        public double Target1Points { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        [Display(Name = "T2 Points", GroupName = "Override Targets", Order = 41)]
        public double Target2Points { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        [Display(Name = "T3 Points", GroupName = "Override Targets", Order = 42)]
        public double Target3Points { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        [Display(Name = "T4 Points", GroupName = "Override Targets", Order = 43)]
        public double Target4Points { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        [Display(Name = "T1 Exit %", GroupName = "Override Targets", Order = 50)]
        public double Target1ExitPct { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        [Display(Name = "T2 Exit %", GroupName = "Override Targets", Order = 51)]
        public double Target2ExitPct { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        [Display(Name = "T3 Exit %", GroupName = "Override Targets", Order = 52)]
        public double Target3ExitPct { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        [Display(Name = "T4 Exit %", GroupName = "Override Targets", Order = 53)]
        public double Target4ExitPct { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        public int LinkedTradeId { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        public string LinkedTradeIds { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        public string RemovedLinkedTradeIds { get; set; }

        [NinjaScriptProperty]
        [Browsable(false)]
        public bool LinkedTradeRemovedByUser { get; set; }
    }
}
