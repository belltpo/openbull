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
using System.Windows.Controls.Primitives;
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
    public enum StrikeSelectionMethod
    {
        ATM,
        ITM_OTM,
        MANUAL,
        OFFSET
    }

    public class OpenBullQuickOrderIndicator : Indicator
    {
        private static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };
        private static string[] cachedExpiries = new string[0];
        private static double[] cachedStrikes = new double[0];
        private static string[] cachedUnderlyings = new string[] { "NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "SILVER", "GOLD" };
        private static int[] cachedTemplateIds = new int[] { 0 };
        private static readonly Dictionary<int, string> cachedTemplateLabels = new Dictionary<int, string> { { 0, "0 - Saved/default" } };
        private static readonly object templateCacheLock = new object();
        private static string optionsCacheKey = "";
        private static DateTime optionsCacheAt = DateTime.MinValue;

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
        private Button closeTradeButton;
        private Border closeTradePanel;
        private Button closeFullButton;
        private Button closePartialButton;
        private Button closeEmergencyButton;
        private Button closeConfirmButton;
        private TextBox closeQtyBox;
        private ComboBox instrumentCombo;
        private ComboBox expiryCombo;
        private ComboBox moneynessCombo;
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
        private DateTime liveBackoffUntilUtc = DateTime.MinValue;
        private string closeMode = "full";
        private int optionsPollTick;
        private Point dragStart;
        private Thickness dragStartMargin;
        private double futuresLtp;
        private double ceLtp;
        private double peLtp;
        private double mtmValue;
        private double currentAtmStrike;
        private double currentCeOffsetStrike;
        private double currentPeOffsetStrike;
        private double manualCeStrike;
        private double manualPeStrike;
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
        private string lastSettingsSignature = "";
        private readonly Dictionary<ComboBox, TextBlock> comboDisplays = new Dictionary<ComboBox, TextBlock>();
        private readonly Dictionary<ComboBox, Grid> comboRows = new Dictionary<ComboBox, Grid>();
        private readonly Dictionary<StrikeSelectionMethod, RadioButton> strikeMethodButtons = new Dictionary<StrikeSelectionMethod, RadioButton>();
        private readonly string strikeRadioGroupName = "OpenBullStrikeSelection_" + Guid.NewGuid().ToString("N");

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
                AutoDetectUnderlying = true;
                Underlying = "NIFTY";
                UnderlyingExchange = "NSE_INDEX";
                Expiry = "07JUL26";
                CeStrike = 24100;
                PeStrike = 24100;
                manualCeStrike = CeStrike;
                manualPeStrike = PeStrike;
                StrikeSelection = StrikeSelectionMethod.ATM;
                MoneynessSelection = "ATM";
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
            else if (State == State.DataLoaded)
            {
                ApplyChartUnderlying();
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
            QueueIndicatorSettingsSync();
        }

        private void ApplyChartUnderlying()
        {
            if (!AutoDetectUnderlying || Instrument == null)
                return;
            string masterName = "";
            string fullName = "";
            try
            {
                fullName = Instrument.FullName ?? "";
                if (Instrument.MasterInstrument != null)
                    masterName = Instrument.MasterInstrument.Name ?? "";
            }
            catch
            {
                return;
            }
            string inferred = OpenBullQuickOrderSymbolMapper.InferUnderlying(masterName, fullName, cachedUnderlyings);
            if (string.IsNullOrWhiteSpace(inferred))
                return;
            Underlying = inferred;
            UnderlyingExchange = OpenBullQuickOrderSymbolMapper.InferExchange(inferred);
        }

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            base.OnRender(chartControl, chartScale);
            activeChartScale = chartScale;
            if (linkedBellTool != null && !string.IsNullOrWhiteSpace(linkedBellTag) && DrawingToolExists(linkedBellTag))
                linkedBellSeenOnChart = true;
            // Trade levels are intentionally owned only by Bell_LongEntryTool /
            // Bell_ShortEntryTool. The indicator only links and refreshes those
            // tools; drawing a second SL/T overlay creates duplicate levels and
            // competing drag handlers.
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

        private string StopLossLabelForTrade()
        {
            if (managedTrade == null)
                return "SL";
            string label = "SL @ " + FormatChartPrice(managedTrade.StopLossPrice);
            if (managedTrade.StopLossHit)
                label += " hit";
            return label;
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

        private bool IsEditingLevel(string levelKey)
        {
            return levelDragging && !string.IsNullOrWhiteSpace(levelKey) && string.Equals(draggedLevelKey, levelKey, StringComparison.OrdinalIgnoreCase);
        }

        private void DrawManagedLine(ChartScale chartScale, float startX, float endX, double price, Brush brush, string label, bool draggable, string levelKey)
        {
            if (price <= 0 || RenderTarget == null)
                return;
            bool editing = IsEditingLevel(levelKey);
            float y = chartScale.GetYByValue(price);
            var start = new SharpDX.Vector2(startX, y);
            var end = new SharpDX.Vector2(endX, y);
            var stroke = new Stroke(brush, DashStyleHelper.Dot, editing ? 2.5f : (draggable ? 1.8f : 1.3f)) { RenderTarget = RenderTarget };
            RenderTarget.DrawLine(start, end, stroke.BrushDX, stroke.Width, stroke.StrokeStyle);
            using (var dotBrush = brush.ToDxBrush(RenderTarget))
            {
                var center = new SharpDX.Vector2(endX, y);
                float radius = editing ? 7.5f : (draggable ? 6f : 4f);
                var outer = new SharpDX.Direct2D1.Ellipse(center, radius, radius);
                RenderTarget.DrawEllipse(outer, dotBrush, editing ? 2.2f : 1.4f);
                if (draggable)
                    RenderTarget.FillEllipse(new SharpDX.Direct2D1.Ellipse(center, editing ? 4.1f : 2.8f, editing ? 4.1f : 2.8f), dotBrush);
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
            // Bell drawing tools own RL/ME level editing.
        }

        private void OnChartMouseMove(object sender, MouseEventArgs e)
        {
            // Bell drawing tools own RL/ME level editing.
        }

        private void UpdateEditedLevel(Point point)
        {
            if (!levelDragging || managedTrade == null || activeChartScale == null || string.IsNullOrWhiteSpace(draggedLevelKey))
                return;
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
        }

        private void OnChartMouseUp(object sender, MouseButtonEventArgs e)
        {
            // Bell drawing tools own RL/ME level editing.
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
                    QueueIndicatorSettingsSync();
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

            Border headerShell = new Border
            {
                Height = 30,
                Margin = new Thickness(0, -1, 0, 7),
                CornerRadius = new CornerRadius(7),
                Background = new SolidColorBrush(Color.FromRgb(33, 33, 33)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(72, 72, 72)),
                BorderThickness = new Thickness(1)
            };
            Grid header = new Grid();
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            Border dragArea = new Border
            {
                Background = Brushes.Transparent,
                Cursor = Cursors.SizeAll,
                Padding = new Thickness(8, 0, 4, 0),
                ToolTip = "Drag to move OpenBull Quick Order"
            };
            dragArea.MouseLeftButtonDown += StartDrag;
            dragArea.MouseMove += DragMove;
            dragArea.MouseLeftButtonUp += StopDrag;
            StackPanel dragContent = new StackPanel { Orientation = Orientation.Horizontal, VerticalAlignment = VerticalAlignment.Center };
            TextBlock dragGlyph = new TextBlock
            {
                Text = "\u2630",
                Foreground = new SolidColorBrush(Color.FromRgb(115, 175, 255)),
                FontSize = 13,
                Margin = new Thickness(0, 0, 7, 0),
                VerticalAlignment = VerticalAlignment.Center
            };
            TextBlock title = new TextBlock
            {
                Text = "OB Quick",
                Foreground = Brushes.White,
                FontWeight = FontWeights.SemiBold,
                FontSize = 12,
                VerticalAlignment = VerticalAlignment.Center
            };
            TextBlock dragHint = new TextBlock
            {
                Text = "DRAG",
                Foreground = new SolidColorBrush(Color.FromRgb(145, 145, 145)),
                FontSize = 8,
                FontWeight = FontWeights.SemiBold,
                Margin = new Thickness(8, 1, 0, 0),
                VerticalAlignment = VerticalAlignment.Center
            };
            dragContent.Children.Add(dragGlyph);
            dragContent.Children.Add(title);
            dragContent.Children.Add(dragHint);
            dragArea.Child = dragContent;
            Grid.SetColumn(dragArea, 0);
            header.Children.Add(dragArea);

            Button settingsButton = HeaderIconButton("\u2699", "Open Quick Settings");
            settingsButton.Click += (s, e) => ToggleSettings();
            Grid.SetColumn(settingsButton, 1);
            header.Children.Add(settingsButton);

            Button closeButton = HeaderIconButton("X", "Minimize OpenBull Quick Order");
            closeButton.Click += (s, e) => CollapseQuickPopup();
            Grid.SetColumn(closeButton, 2);
            header.Children.Add(closeButton);
            headerShell.Child = header;
            stack.Children.Add(headerShell);

            stack.Children.Add(BuildLiveBox());
            stack.Children.Add(BuildButtonGrid());
            closeTradePanel = BuildCloseTradePanel();
            closeTradePanel.Visibility = Visibility.Collapsed;
            stack.Children.Add(closeTradePanel);

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
            buttons.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

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
            closeTradeButton = SmallCloseAction("Close / Partial");
            closeTradeButton.Click += (s, e) => ToggleCloseTradePanel();
            Grid.SetRow(closeTradeButton, 2);
            Grid.SetColumn(closeTradeButton, 0);
            Grid.SetColumnSpan(closeTradeButton, 2);
            buttons.Children.Add(closeTradeButton);
            RefreshButtonText();
            UpdateCloseTradeButtonState();
            return buttons;
        }

        private Border BuildCloseTradePanel()
        {
            StackPanel stack = new StackPanel();
            Grid modes = new Grid { Margin = new Thickness(0, 2, 0, 5) };
            modes.ColumnDefinitions.Add(new ColumnDefinition());
            modes.ColumnDefinitions.Add(new ColumnDefinition());
            modes.ColumnDefinitions.Add(new ColumnDefinition());

            closeFullButton = CloseModeButton("Full", "full");
            closePartialButton = CloseModeButton("Partial", "partial");
            closeEmergencyButton = CloseModeButton("Emergency", "emergency");
            Grid.SetColumn(closeFullButton, 0);
            Grid.SetColumn(closePartialButton, 1);
            Grid.SetColumn(closeEmergencyButton, 2);
            modes.Children.Add(closeFullButton);
            modes.Children.Add(closePartialButton);
            modes.Children.Add(closeEmergencyButton);
            stack.Children.Add(modes);

            Grid qtyRow = FieldRow("Qty");
            closeQtyBox = new TextBox
            {
                Text = Math.Max(1, Lots).ToString(CultureInfo.InvariantCulture),
                FontSize = 10,
                Height = 23,
                Padding = new Thickness(4, 1, 4, 1),
                Foreground = Brushes.White,
                Background = new SolidColorBrush(Color.FromRgb(10, 10, 10)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(65, 65, 65))
            };
            EnableTextEntry(closeQtyBox);
            Grid.SetColumn(closeQtyBox, 1);
            qtyRow.Children.Add(closeQtyBox);
            stack.Children.Add(qtyRow);

            closeConfirmButton = SmallCloseAction("Confirm full exit");
            closeConfirmButton.Click += async (s, e) => await ConfirmCloseTradeAsync();
            stack.Children.Add(closeConfirmButton);

            UpdateCloseModeButtons();
            return new Border
            {
                CornerRadius = new CornerRadius(8),
                Background = new SolidColorBrush(Color.FromRgb(24, 24, 24)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(58, 58, 58)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(7),
                Margin = new Thickness(3, 5, 3, 0),
                Child = stack
            };
        }

        private Button CloseModeButton(string label, string mode)
        {
            Button button = new Button
            {
                Content = label,
                Height = 24,
                Margin = new Thickness(2),
                Padding = new Thickness(4, 0, 4, 0),
                Foreground = Brushes.White,
                Background = new SolidColorBrush(Color.FromRgb(32, 32, 32)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(70, 70, 70)),
                FontSize = 9,
                FontWeight = FontWeights.SemiBold,
                Tag = mode
            };
            ApplyRoundedButton(button, 7);
            button.Click += (s, e) =>
            {
                closeMode = mode;
                UpdateCloseModeButtons();
            };
            return button;
        }

        private Button SmallCloseAction(string text)
        {
            Button button = new Button
            {
                Content = text,
                Height = 27,
                Margin = new Thickness(3, 5, 3, 0),
                Padding = new Thickness(4, 0, 4, 0),
                Foreground = Brushes.White,
                Background = new SolidColorBrush(Color.FromRgb(36, 36, 36)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(72, 72, 72)),
                FontSize = 10,
                FontWeight = FontWeights.SemiBold
            };
            ApplyRoundedButton(button, 8);
            return button;
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

        private Button HeaderIconButton(string text, string tooltip)
        {
            Button button = new Button
            {
                Content = text,
                ToolTip = tooltip,
                Width = 25,
                Height = 24,
                Margin = new Thickness(2, 2, 2, 2),
                Padding = new Thickness(0),
                Foreground = new SolidColorBrush(Color.FromRgb(230, 230, 230)),
                Background = new SolidColorBrush(Color.FromRgb(46, 46, 46)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(86, 86, 86)),
                BorderThickness = new Thickness(1),
                FontSize = 12
            };
            ApplyRoundedButton(button, 5);
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
                AutoDetectUnderlying = false;
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
            stack.Children.Add(BuildStrikeMethodRow());
            moneynessCombo = ComboRow(stack, "ITM / OTM", value =>
            {
                MoneynessSelection = NormalizeMoneynessSelection(value);
                RecalculateSelectedStrikes();
                RefreshButtonText();
                Task.Run(async () => await SaveSettingsAsync());
            });
            ceCombo = ComboRow(stack, "CE", value =>
            {
                CeStrike = ParseDouble(value, CeStrike);
                manualCeStrike = CeStrike;
                RefreshButtonText();
            });
            peCombo = ComboRow(stack, "PE", value =>
            {
                PeStrike = ParseDouble(value, PeStrike);
                manualPeStrike = PeStrike;
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
            FillCombo(moneynessCombo, MoneynessValues(), MoneynessSelection);
            SeedCombo(ceCombo, CeStrike.ToString("0", CultureInfo.InvariantCulture));
            SeedCombo(peCombo, PeStrike.ToString("0", CultureInfo.InvariantCulture));
            SeedCombo(templateCombo, string.IsNullOrWhiteSpace(TargetTemplate) ? TemplateFallbackLabel(TargetTemplateId) : TargetTemplate);
            FillCombo(productCombo, new List<string> { "NRML", "MIS", "CNC" }, Product);
            UpdateStrikeSelectionUi();

            Grid actions = new Grid { Margin = new Thickness(0, 6, 0, 0) };
            actions.ColumnDefinitions.Add(new ColumnDefinition());
            actions.ColumnDefinitions.Add(new ColumnDefinition());
            actions.ColumnDefinitions.Add(new ColumnDefinition());
            actions.ColumnDefinitions.Add(new ColumnDefinition());
            Button refresh = SmallAction("Refresh");
            Button save = SmallAction("Save");
            Button remove = SmallAction("Clear");
            Button delete = SmallAction("Delete");
            WireActionButton(refresh, "Refresh", async () => await FetchOptionsAsync());
            WireActionButton(save, "Save", async () =>
            {
                CommitAllSettingInputs();
                await SaveSettingsAsync();
            });
            WireActionButton(remove, "Clear", async () => await RemoveAllTradeDrawingsAsync());
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
                MaxDropDownHeight = 180,
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
            combo.DropDownOpened += (s, e) =>
            {
                ApplyComboTextColors(combo);
                ScrollComboToSelected(combo);
            };
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
            comboRows[combo] = row;
            return combo;
        }

        private UIElement BuildStrikeMethodRow()
        {
            Grid row = FieldRow("Strike method");
            Grid choices = new Grid { Margin = new Thickness(0, -1, 0, -1) };
            choices.ColumnDefinitions.Add(new ColumnDefinition());
            choices.ColumnDefinitions.Add(new ColumnDefinition());
            choices.RowDefinitions.Add(new RowDefinition());
            choices.RowDefinitions.Add(new RowDefinition());
            Style radioStyle = BuildStrikeMethodRadioStyle();
            int index = 0;
            foreach (StrikeSelectionMethod method in Enum.GetValues(typeof(StrikeSelectionMethod)))
            {
                RadioButton button = new RadioButton
                {
                    Content = method == StrikeSelectionMethod.ITM_OTM ? "ITM / OTM" : method.ToString(),
                    Tag = method,
                    GroupName = strikeRadioGroupName,
                    Margin = new Thickness(index % 2 == 0 ? 0 : 3, index < 2 ? 2 : 0, index % 2 == 0 ? 3 : 0, 2),
                    Style = radioStyle,
                    IsChecked = method == StrikeSelection
                };
                button.Checked += (s, e) =>
                {
                    if (settingsHydrating)
                        return;
                    if (StrikeSelection == StrikeSelectionMethod.MANUAL)
                    {
                        manualCeStrike = CeStrike;
                        manualPeStrike = PeStrike;
                    }
                    StrikeSelection = method;
                    RecalculateSelectedStrikes();
                    UpdateStrikeSelectionUi();
                    RefreshButtonText();
                    Task.Run(async () => await SaveSettingsAsync());
                };
                strikeMethodButtons[method] = button;
                Grid.SetRow(button, index / 2);
                Grid.SetColumn(button, index % 2);
                choices.Children.Add(button);
                index++;
            }
            Grid.SetColumn(choices, 1);
            row.Children.Add(choices);
            return row;
        }

        private static Style BuildStrikeMethodRadioStyle()
        {
            Style style = new Style(typeof(RadioButton));
            style.Setters.Add(new Setter(Control.HeightProperty, 22.0));
            style.Setters.Add(new Setter(Control.PaddingProperty, new Thickness(7, 0, 6, 0)));
            style.Setters.Add(new Setter(Control.ForegroundProperty, new SolidColorBrush(Color.FromRgb(220, 220, 220))));
            style.Setters.Add(new Setter(Control.BackgroundProperty, new SolidColorBrush(Color.FromRgb(20, 20, 20))));
            style.Setters.Add(new Setter(Control.BorderBrushProperty, new SolidColorBrush(Color.FromRgb(65, 65, 65))));
            style.Setters.Add(new Setter(Control.BorderThicknessProperty, new Thickness(1)));
            style.Setters.Add(new Setter(Control.FontSizeProperty, 9.0));
            style.Setters.Add(new Setter(Control.CursorProperty, Cursors.Hand));

            ControlTemplate template = new ControlTemplate(typeof(RadioButton));
            FrameworkElementFactory border = new FrameworkElementFactory(typeof(Border));
            border.Name = "choiceBorder";
            border.SetValue(Border.CornerRadiusProperty, new CornerRadius(4));
            border.SetValue(Border.BackgroundProperty, new TemplateBindingExtension(Control.BackgroundProperty));
            border.SetValue(Border.BorderBrushProperty, new TemplateBindingExtension(Control.BorderBrushProperty));
            border.SetValue(Border.BorderThicknessProperty, new TemplateBindingExtension(Control.BorderThicknessProperty));

            FrameworkElementFactory content = new FrameworkElementFactory(typeof(StackPanel));
            content.SetValue(StackPanel.OrientationProperty, Orientation.Horizontal);
            content.SetValue(StackPanel.VerticalAlignmentProperty, VerticalAlignment.Center);

            FrameworkElementFactory indicator = new FrameworkElementFactory(typeof(Border));
            indicator.Name = "indicatorBorder";
            indicator.SetValue(Border.WidthProperty, 12.0);
            indicator.SetValue(Border.HeightProperty, 12.0);
            indicator.SetValue(Border.CornerRadiusProperty, new CornerRadius(6));
            indicator.SetValue(Border.BorderThicknessProperty, new Thickness(1));
            indicator.SetValue(Border.BorderBrushProperty, new SolidColorBrush(Color.FromRgb(150, 150, 150)));
            indicator.SetValue(Border.BackgroundProperty, Brushes.Transparent);
            indicator.SetValue(Border.MarginProperty, new Thickness(0, 0, 5, 0));
            indicator.SetValue(FrameworkElement.VerticalAlignmentProperty, VerticalAlignment.Center);

            FrameworkElementFactory dot = new FrameworkElementFactory(typeof(Border));
            dot.Name = "indicatorDot";
            dot.SetValue(Border.WidthProperty, 6.0);
            dot.SetValue(Border.HeightProperty, 6.0);
            dot.SetValue(Border.CornerRadiusProperty, new CornerRadius(3));
            dot.SetValue(Border.BackgroundProperty, new SolidColorBrush(Color.FromRgb(85, 150, 255)));
            dot.SetValue(FrameworkElement.HorizontalAlignmentProperty, HorizontalAlignment.Center);
            dot.SetValue(FrameworkElement.VerticalAlignmentProperty, VerticalAlignment.Center);
            dot.SetValue(UIElement.VisibilityProperty, Visibility.Collapsed);
            indicator.AppendChild(dot);

            FrameworkElementFactory presenter = new FrameworkElementFactory(typeof(ContentPresenter));
            presenter.SetValue(ContentPresenter.ContentProperty, new TemplateBindingExtension(ContentControl.ContentProperty));
            presenter.SetValue(ContentPresenter.VerticalAlignmentProperty, VerticalAlignment.Center);
            presenter.SetValue(ContentPresenter.RecognizesAccessKeyProperty, true);

            content.AppendChild(indicator);
            content.AppendChild(presenter);
            border.AppendChild(content);
            template.VisualTree = border;

            Trigger checkedTrigger = new Trigger { Property = ToggleButton.IsCheckedProperty, Value = true };
            checkedTrigger.Setters.Add(new Setter(Border.BackgroundProperty, new SolidColorBrush(Color.FromRgb(25, 63, 110)), "choiceBorder"));
            checkedTrigger.Setters.Add(new Setter(Border.BorderBrushProperty, new SolidColorBrush(Color.FromRgb(85, 150, 255)), "choiceBorder"));
            checkedTrigger.Setters.Add(new Setter(Border.BorderBrushProperty, new SolidColorBrush(Color.FromRgb(85, 150, 255)), "indicatorBorder"));
            checkedTrigger.Setters.Add(new Setter(UIElement.VisibilityProperty, Visibility.Visible, "indicatorDot"));
            template.Triggers.Add(checkedTrigger);

            Trigger hoverTrigger = new Trigger { Property = UIElement.IsMouseOverProperty, Value = true };
            hoverTrigger.Setters.Add(new Setter(Border.BorderBrushProperty, new SolidColorBrush(Color.FromRgb(125, 125, 125)), "choiceBorder"));
            template.Triggers.Add(hoverTrigger);

            Trigger disabledTrigger = new Trigger { Property = UIElement.IsEnabledProperty, Value = false };
            disabledTrigger.Setters.Add(new Setter(UIElement.OpacityProperty, 0.5, "choiceBorder"));
            template.Triggers.Add(disabledTrigger);

            style.Setters.Add(new Setter(Control.TemplateProperty, template));
            return style;
        }

        private void SetComboRowVisible(ComboBox combo, bool visible)
        {
            Grid row;
            if (combo != null && comboRows.TryGetValue(combo, out row))
                row.Visibility = visible ? Visibility.Visible : Visibility.Collapsed;
        }

        private void UpdateStrikeSelectionUi()
        {
            foreach (KeyValuePair<StrikeSelectionMethod, RadioButton> pair in strikeMethodButtons)
                pair.Value.IsChecked = pair.Key == StrikeSelection;
            SetComboRowVisible(moneynessCombo, StrikeSelection == StrikeSelectionMethod.ITM_OTM);
            SetComboRowVisible(ceCombo, StrikeSelection == StrikeSelectionMethod.MANUAL);
            SetComboRowVisible(peCombo, StrikeSelection == StrikeSelectionMethod.MANUAL);
        }

        private void RecalculateSelectedStrikes()
        {
            if (StrikeSelection == StrikeSelectionMethod.MANUAL)
            {
                if (manualCeStrike > 0) CeStrike = manualCeStrike;
                if (manualPeStrike > 0) PeStrike = manualPeStrike;
            }
            else
            {
                CeStrike = ResolveSelectedStrike(ToStrikeStrings(), currentAtmStrike, currentCeOffsetStrike, "CE", StrikeSelection, MoneynessSelection, manualCeStrike);
                PeStrike = ResolveSelectedStrike(ToStrikeStrings(), currentAtmStrike, currentPeOffsetStrike, "PE", StrikeSelection, MoneynessSelection, manualPeStrike);
            }
            if (ceCombo != null)
                SelectCombo(ceCombo, FormatStrikeText(CeStrike));
            if (peCombo != null)
                SelectCombo(peCombo, FormatStrikeText(PeStrike));
        }

        private static List<string> ToStrikeStrings()
        {
            List<string> values = new List<string>();
            lock (templateCacheLock)
            {
                foreach (double strike in cachedStrikes)
                    values.Add(FormatStrikeText(strike));
            }
            return values;
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

            // WPF's default selected-item colours are a light system blue with
            // dark text. Keep the Quick Settings list readable in its dark UI.
            Trigger selected = new Trigger { Property = ComboBoxItem.IsSelectedProperty, Value = true };
            selected.Setters.Add(new Setter(Control.ForegroundProperty, Brushes.White));
            selected.Setters.Add(new Setter(Control.BackgroundProperty, new SolidColorBrush(Color.FromRgb(24, 104, 190))));
            selected.Setters.Add(new Setter(Control.BorderBrushProperty, new SolidColorBrush(Color.FromRgb(98, 181, 255))));
            style.Triggers.Add(selected);
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

        private static void ScrollComboToSelected(ComboBox combo)
        {
            if (combo == null || combo.SelectedItem == null || combo.SelectedIndex < 0)
                return;

            combo.Dispatcher.BeginInvoke(new Action(() =>
            {
                try
                {
                    combo.ApplyTemplate();
                    combo.UpdateLayout();
                    ComboBoxItem selectedItem = combo.ItemContainerGenerator.ContainerFromIndex(combo.SelectedIndex) as ComboBoxItem;
                    if (selectedItem != null)
                    {
                        selectedItem.BringIntoView();
                        selectedItem.Focus();
                    }
                }
                catch
                {
                    // Best-effort visual positioning only. Trading behavior must never depend on it.
                }
            }), DispatcherPriority.ContextIdle);
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
            TextBox editableTextBox = control as TextBox;
            if (editableTextBox != null)
            {
                editableTextBox.AddHandler(Keyboard.PreviewKeyDownEvent, new KeyEventHandler((s, e) =>
                {
                    TextBox textBox = s as TextBox;
                    if (textBox == null)
                        return;
                    if (HandleTextBoxKey(textBox, e.Key))
                        e.Handled = true;
                }), true);
                editableTextBox.AddHandler(TextCompositionManager.PreviewTextInputEvent, new TextCompositionEventHandler((s, e) =>
                {
                    TextBox textBox = s as TextBox;
                    if (textBox == null || string.IsNullOrEmpty(e.Text))
                        return;
                    InsertTextBoxText(textBox, e.Text);
                    e.Handled = true;
                }), true);
                DataObject.AddPastingHandler(editableTextBox, OnTextBoxPaste);
            }
            control.PreviewKeyDown += (s, e) =>
            {
                if (IsTextEditingKey(e.Key) || e.Key == Key.Enter || e.Key == Key.Tab)
                    e.Handled = false;
            };
        }

        private static bool HandleTextBoxKey(TextBox textBox, Key key)
        {
            string text = KeyToText(key);
            if (!string.IsNullOrEmpty(text))
            {
                InsertTextBoxText(textBox, text);
                return true;
            }
            if (key == Key.Back)
            {
                DeleteTextBoxText(textBox, -1);
                return true;
            }
            if (key == Key.Delete)
            {
                DeleteTextBoxText(textBox, 1);
                return true;
            }
            return false;
        }

        private static string KeyToText(Key key)
        {
            if (key >= Key.D0 && key <= Key.D9)
                return ((int)(key - Key.D0)).ToString(CultureInfo.InvariantCulture);
            if (key >= Key.NumPad0 && key <= Key.NumPad9)
                return ((int)(key - Key.NumPad0)).ToString(CultureInfo.InvariantCulture);
            if (key == Key.Decimal || key == Key.OemPeriod)
                return ".";
            if (key == Key.Subtract || key == Key.OemMinus)
                return "-";
            return "";
        }

        private static void InsertTextBoxText(TextBox textBox, string text)
        {
            if (textBox == null || string.IsNullOrEmpty(text))
                return;
            int selectionStart = Math.Max(0, textBox.SelectionStart);
            int selectionLength = Math.Max(0, textBox.SelectionLength);
            string existing = textBox.Text ?? "";
            if (selectionStart > existing.Length)
                selectionStart = existing.Length;
            if (selectionStart + selectionLength > existing.Length)
                selectionLength = existing.Length - selectionStart;
            textBox.Text = existing.Remove(selectionStart, selectionLength).Insert(selectionStart, text);
            textBox.CaretIndex = selectionStart + text.Length;
            textBox.SelectionLength = 0;
        }

        private static void DeleteTextBoxText(TextBox textBox, int direction)
        {
            if (textBox == null)
                return;
            string existing = textBox.Text ?? "";
            int selectionStart = Math.Max(0, textBox.SelectionStart);
            int selectionLength = Math.Max(0, textBox.SelectionLength);
            if (selectionLength > 0)
            {
                if (selectionStart + selectionLength > existing.Length)
                    selectionLength = existing.Length - selectionStart;
                textBox.Text = existing.Remove(selectionStart, selectionLength);
                textBox.CaretIndex = selectionStart;
                return;
            }
            if (direction < 0 && selectionStart > 0)
            {
                textBox.Text = existing.Remove(selectionStart - 1, 1);
                textBox.CaretIndex = selectionStart - 1;
            }
            else if (direction > 0 && selectionStart < existing.Length)
            {
                textBox.Text = existing.Remove(selectionStart, 1);
                textBox.CaretIndex = selectionStart;
            }
        }

        private static void OnTextBoxPaste(object sender, DataObjectPastingEventArgs e)
        {
            TextBox textBox = sender as TextBox;
            if (textBox == null || !e.DataObject.GetDataPresent(DataFormats.Text))
                return;
            string text = e.DataObject.GetData(DataFormats.Text) as string;
            if (string.IsNullOrEmpty(text))
                return;
            InsertTextBoxText(textBox, text);
            e.CancelCommand();
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
            if (closeTradePanel != null)
                closeTradePanel.Visibility = Visibility.Collapsed;
            if (restoreButton != null)
                restoreButton.Visibility = Visibility.Visible;
            if (root != null)
                root.Width = 112;
        }

        private void ToggleCloseTradePanel()
        {
            if (!HasActiveLinkedTrade())
            {
                SetStatus("No active linked OpenBull trade to close", false);
                return;
            }
            if (closeTradePanel == null)
                return;
            if (closeQtyBox != null)
            {
                int qty = managedTrade != null && managedTrade.RemainingQty > 0 ? managedTrade.RemainingQty : Math.Max(1, Lots);
                closeQtyBox.Text = qty.ToString(CultureInfo.InvariantCulture);
            }
            closeTradePanel.Visibility = closeTradePanel.Visibility == Visibility.Visible
                ? Visibility.Collapsed
                : Visibility.Visible;
            UpdateCloseModeButtons();
        }

        private bool HasActiveLinkedTrade()
        {
            return managedTrade != null
                && managedTrade.TradeId > 0
                && managedTrade.RemainingQty > 0
                && string.Equals(managedTrade.Status, "active", StringComparison.OrdinalIgnoreCase);
        }

        private void UpdateCloseTradeButtonState()
        {
            if (closeTradeButton != null)
                closeTradeButton.IsEnabled = HasActiveLinkedTrade();
            if (closeConfirmButton != null)
                closeConfirmButton.IsEnabled = HasActiveLinkedTrade();
        }

        private void UpdateCloseModeButtons()
        {
            ApplyCloseModeStyle(closeFullButton, closeMode == "full", false);
            ApplyCloseModeStyle(closePartialButton, closeMode == "partial", false);
            ApplyCloseModeStyle(closeEmergencyButton, closeMode == "emergency", true);
            if (closeQtyBox != null)
                closeQtyBox.IsEnabled = closeMode == "partial";
            if (closeConfirmButton != null)
            {
                string label = closeMode == "partial" ? "Confirm partial exit"
                    : closeMode == "emergency" ? "Confirm emergency"
                    : "Confirm full exit";
                closeConfirmButton.Content = label;
                closeConfirmButton.Background = closeMode == "emergency"
                    ? new SolidColorBrush(Color.FromRgb(115, 22, 22))
                    : new SolidColorBrush(Color.FromRgb(42, 88, 200));
                closeConfirmButton.BorderBrush = closeMode == "emergency"
                    ? new SolidColorBrush(Color.FromRgb(170, 55, 55))
                    : new SolidColorBrush(Color.FromRgb(75, 115, 220));
            }
            UpdateCloseTradeButtonState();
        }

        private void ApplyCloseModeStyle(Button button, bool selected, bool emergency)
        {
            if (button == null)
                return;
            button.Background = selected
                ? emergency
                    ? new SolidColorBrush(Color.FromRgb(115, 22, 22))
                    : new SolidColorBrush(Color.FromRgb(42, 88, 200))
                : new SolidColorBrush(Color.FromRgb(32, 32, 32));
            button.BorderBrush = selected
                ? emergency
                    ? new SolidColorBrush(Color.FromRgb(170, 55, 55))
                    : new SolidColorBrush(Color.FromRgb(75, 115, 220))
                : new SolidColorBrush(Color.FromRgb(70, 70, 70));
        }

        private async Task ConfirmCloseTradeAsync()
        {
            if (isBusy)
                return;
            if (!HasActiveLinkedTrade())
            {
                SetStatus("No active linked OpenBull trade to close", false);
                return;
            }

            int tradeId = managedTrade.TradeId;
            int qty = managedTrade.RemainingQty > 0 ? managedTrade.RemainingQty : Math.Max(1, Lots);
            if (closeMode == "partial" && closeQtyBox != null)
                qty = Math.Max(1, Math.Min(ParseInt(closeQtyBox.Text, qty), managedTrade.RemainingQty));

            isBusy = true;
            SetButtonsEnabled(false);
            SetStatus("Closing linked trade...", true);
            try
            {
                NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.Configure(OpenBullUrl, ApiKey);
                string result = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.CloseTradeAsync(tradeId, closeMode, qty);
                bool closeOk = !result.StartsWith("ERROR:", StringComparison.OrdinalIgnoreCase);
                if (!closeOk)
                    result = result.Substring("ERROR:".Length).Trim();
                OpenBullTradeSnapshot snapshot = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradeAsync(tradeId, CurrentOpenBullModeParam());
                if (snapshot != null)
                {
                    ApplyLiveOptionPrice(snapshot);
                    ChartControl.Dispatcher.InvokeAsync(() =>
                    {
                        managedTrade = snapshot;
                        managedTrades[tradeId] = snapshot;
                        AttachBellDrawingTool(snapshot);
                        if (!string.Equals(snapshot.Status, "active", StringComparison.OrdinalIgnoreCase) || snapshot.RemainingQty <= 0)
                            closeTradePanel.Visibility = Visibility.Collapsed;
                        UpdateCloseTradeButtonState();
                        SetStatus(result, closeOk);
                        RequestChartRefresh();
                    });
                }
                else
                {
                    SetStatus(result, closeOk);
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
            if (DateTime.UtcNow < liveBackoffUntilUtc)
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
                        MaybeBackoffLivePolling(response, body);
                        if (!isBusy)
                            SetStatus(TrimForStatus(body), false);
                        return;
                    }
                    liveBackoffUntilUtc = DateTime.MinValue;
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
                MaybeBackoffLivePolling(null, ex.Message);
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
                    List<string> strikeValues = NormalizeStrikeValues(ParseNumberArray(body, "strikes"));
                    List<string> templateValues = ParseTemplates(body);
                    List<string> underlyingValues = ParseStringArray(body, "underlyings");
                    double atmStrike = ParseDouble(ExtractJsonValue(body, "atm"), 0);
                    double ceDefaultStrike = ParseDouble(ExtractJsonValue(body, "ce_default_strike"), atmStrike);
                    double peDefaultStrike = ParseDouble(ExtractJsonValue(body, "pe_default_strike"), atmStrike);
                    currentAtmStrike = atmStrike;
                    currentCeOffsetStrike = ceDefaultStrike;
                    currentPeOffsetStrike = peDefaultStrike;
                    CacheOptionValues(underlyingValues, expiryValues, strikeValues, templateValues);
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
                            StrikeSelectionMethod selectedMethod = StrikeSelection;
                            string selectedMoneyness = string.IsNullOrWhiteSpace(MoneynessSelection) ? "ATM" : MoneynessSelection;
                            double selectedCe = ResolveSelectedStrike(strikeValues, atmStrike, ceDefaultStrike, "CE", selectedMethod, selectedMoneyness, CeStrike);
                            double selectedPe = ResolveSelectedStrike(strikeValues, atmStrike, peDefaultStrike, "PE", selectedMethod, selectedMoneyness, PeStrike);
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
                                string savedMethod = ExtractJsonValue(saved, "strike_selection_method");
                                string savedMoneyness = ExtractJsonValue(saved, "moneyness_selection");
                                if (!string.IsNullOrWhiteSpace(savedMethod) && savedMethod != "null")
                                    selectedMethod = ParseStrikeSelectionMethod(savedMethod, selectedMethod);
                                if (!string.IsNullOrWhiteSpace(savedMoneyness) && savedMoneyness != "null")
                                    selectedMoneyness = NormalizeMoneynessSelection(savedMoneyness);
                                if (!string.IsNullOrEmpty(savedExchange) && savedExchange != "null")
                                    UnderlyingExchange = savedExchange.ToUpperInvariant();
                                if (!string.IsNullOrEmpty(savedExpiry) && savedExpiry != "null")
                                    selectedExpiry = savedExpiry.ToUpperInvariant();
                                if (selectedMethod == StrikeSelectionMethod.MANUAL)
                                {
                                    if (!string.IsNullOrEmpty(savedCe) && savedCe != "null")
                                        selectedCe = SelectValidStrike(strikeValues, ParseDouble(savedCe, selectedCe), selectedCe);
                                    if (!string.IsNullOrEmpty(savedPe) && savedPe != "null")
                                        selectedPe = SelectValidStrike(strikeValues, ParseDouble(savedPe, selectedPe), selectedPe);
                                }
                                else
                                {
                                    selectedCe = ResolveSelectedStrike(strikeValues, atmStrike, ceDefaultStrike, "CE", selectedMethod, selectedMoneyness, selectedCe);
                                    selectedPe = ResolveSelectedStrike(strikeValues, atmStrike, peDefaultStrike, "PE", selectedMethod, selectedMoneyness, selectedPe);
                                }
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
                            StrikeSelection = selectedMethod;
                            MoneynessSelection = selectedMoneyness;
                            CeStrike = selectedCe;
                            PeStrike = selectedPe;
                            if (StrikeSelection == StrikeSelectionMethod.MANUAL)
                            {
                                manualCeStrike = CeStrike;
                                manualPeStrike = PeStrike;
                            }

                            string ceText = FormatStrikeText(CeStrike);
                            string peText = FormatStrikeText(PeStrike);
                            FillCombo(instrumentCombo, underlyingValues, Underlying);
                            FillCombo(expiryCombo, expiryValues, Expiry);
                            FillCombo(moneynessCombo, MoneynessValues(), MoneynessSelection);
                            FillCombo(ceCombo, strikeValues, ceText);
                            FillCombo(peCombo, strikeValues, peText);
                            FillCombo(templateCombo, templateValues, TemplateFallbackLabel(TargetTemplateId));
                            FillCombo(productCombo, new List<string> { "NRML", "MIS", "CNC" }, Product);
                            UpdateStrikeSelectionUi();
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
                    {
                        lastSettingsSignature = BuildSettingsSignature();
                        SetStatus("Settings saved", true);
                    }
                }
            }
            catch (Exception ex)
            {
                SetStatus(ex.Message, false);
            }
        }

        private string BuildSettingsSignature()
        {
            return string.Join("|", OpenBullUrl ?? "", ApiKey ?? "", Underlying ?? "", UnderlyingExchange ?? "", Expiry ?? "",
                CeStrike.ToString("R", CultureInfo.InvariantCulture), PeStrike.ToString("R", CultureInfo.InvariantCulture),
                StrikeSelection.ToString(), NormalizeMoneynessSelection(MoneynessSelection), Lots.ToString(CultureInfo.InvariantCulture),
                SlPoints.ToString("R", CultureInfo.InvariantCulture), Product ?? "", CurrentTargetTemplateId().ToString(CultureInfo.InvariantCulture));
        }

        private void QueueIndicatorSettingsSync()
        {
            if (!controlsAdded || settingsHydrating || isBusy || string.IsNullOrWhiteSpace(ApiKey) || string.IsNullOrWhiteSpace(OpenBullUrl) || string.IsNullOrWhiteSpace(Underlying))
                return;
            if (StrikeSelection == StrikeSelectionMethod.MANUAL)
            {
                manualCeStrike = CeStrike;
                manualPeStrike = PeStrike;
            }
            string signature = BuildSettingsSignature();
            if (string.IsNullOrEmpty(lastSettingsSignature))
            {
                lastSettingsSignature = signature;
                return;
            }
            if (string.Equals(signature, lastSettingsSignature, StringComparison.Ordinal))
                return;
            lastSettingsSignature = signature;
            Task.Run(async () => await SaveSettingsAsync());
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
            OpenBullTradeSnapshot snapshot = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradeAsync(tradeId, CurrentOpenBullModeParam());
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
                UpdateCloseTradeButtonState();
                if (orderAccepted)
                    SetStatus(bellLinked ? "Order sent - Bell drawing tool linked" : "Order sent - chart levels linked", true);
                else
                    SetStatus(bellLinked ? "Order recorded with broker issue - Bell drawing linked" : "Order recorded with broker issue - chart levels linked", false);
                RequestChartRefresh();
            });
        }

        private string CurrentOpenBullModeParam()
        {
            if (string.IsNullOrWhiteSpace(tradingMode))
                return null;
            string value = tradingMode.Trim().ToLowerInvariant();
            if (value == "live" || value == "sandbox")
                return value;
            return null;
        }

        private async Task RehydrateLinkedTradeAsync()
        {
            if (rehydrateAttempted || string.IsNullOrWhiteSpace(ApiKey))
                return;
            rehydrateAttempted = true;
            if (LinkedTradeRemovedByUser && LinkedTradeId > 0)
                AddDeletedLinkedTradeId(LinkedTradeId);
            await Task.Delay(500);
            string modeParam = CurrentOpenBullModeParam();
            List<OpenBullTradeSnapshot> snapshots = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradesAsync(Underlying, modeParam);
            if (snapshots.Count == 0)
            {
                foreach (int id in ParseTradeIds(LinkedTradeIds))
                {
                    if (IsDeletedLinkedTradeId(id))
                        continue;
                    OpenBullTradeSnapshot snapshot = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradeAsync(id, modeParam);
                    if (snapshot != null)
                        snapshots.Add(snapshot);
                }
                if (LinkedTradeId > 0 && !IsDeletedLinkedTradeId(LinkedTradeId))
                {
                    OpenBullTradeSnapshot snapshot = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradeAsync(LinkedTradeId, modeParam);
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
                UpdateCloseTradeButtonState();
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
                OpenBullTradeSnapshot snapshot = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradeAsync(id, CurrentOpenBullModeParam());
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
                    UpdateCloseTradeButtonState();
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
            if (IsBellRefreshBlocked(snapshot.TradeId))
                return true;

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
                    snapshot.Mtm,
                    snapshot.StopLossHit
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
                    snapshot.Mtm,
                    snapshot.StopLossHit
                );
                linkedBellTool = tool;
                linkedBellTools[snapshot.TradeId] = tool;
            }
            linkedBellSeenOnChart = linkedBellTool != null && DrawingToolExists(linkedBellTag);
            if (linkedBellSeenOnChart)
                linkedBellSeenTradeIds.Add(snapshot.TradeId);
            return linkedBellTool != null;
        }

        private bool IsBellRefreshBlocked(int tradeId)
        {
            DrawingTool tool;
            if (!linkedBellTools.TryGetValue(tradeId, out tool) || tool == null)
                return false;

            Bell_LongEntryTool longTool = tool as Bell_LongEntryTool;
            if (longTool != null)
                return longTool.IsOpenBullRefreshBlocked;

            Bell_ShortEntryTool shortTool = tool as Bell_ShortEntryTool;
            if (shortTool != null)
                return shortTool.IsOpenBullRefreshBlocked;

            return false;
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
                    DateTime snapshotTime = SnapshotTime(snapshot);
                    DateTime selectedTime = SnapshotTime(selected);
                    if ((snapshotActive && !selectedActive) ||
                        (snapshotActive == selectedActive && snapshotTime > selectedTime) ||
                        (snapshotActive == selectedActive && snapshotTime == selectedTime && snapshot.TradeId > selected.TradeId))
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
            List<OpenBullTradeSnapshot> snapshots = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.FetchTradesAsync(Underlying, CurrentOpenBullModeParam());
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

        private async Task RemoveAllTradeDrawingsAsync()
        {
            if (ChartControl == null)
                return;
            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                HashSet<int> ids = CollectKnownTradeIds();
                List<string> tags = new List<string>();
                try
                {
                    foreach (DrawingTool tool in DrawObjects)
                    {
                        if (tool == null || string.IsNullOrWhiteSpace(tool.Tag))
                            continue;
                        int id;
                        if (TryParseBellTradeId(tool.Tag, out id))
                        {
                            ids.Add(id);
                            if (!tags.Contains(tool.Tag))
                                tags.Add(tool.Tag);
                        }
                    }
                }
                catch
                {
                }

                foreach (string tag in tags)
                {
                    try
                    {
                        RemoveDrawObject(tag);
                    }
                    catch
                    {
                    }
                }

                foreach (int id in ids)
                    RemoveTradeDrawing(id, true);

                linkedBellTools.Clear();
                linkedBellSeenTradeIds.Clear();
                managedTrades.Clear();
                managedTrade = null;
                linkedBellTool = null;
                linkedBellTag = "";
                linkedBellSeenOnChart = false;
                LinkedTradeId = 0;
                LinkedTradeIds = "";

                SetStatus(ids.Count > 0 ? "All OpenBull trade drawings removed" : "No OpenBull trade drawings to remove", ids.Count > 0);
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

        private static bool TryParseBellTradeId(string tag, out int tradeId)
        {
            tradeId = 0;
            const string prefix = "OpenBull_FR_";
            if (string.IsNullOrWhiteSpace(tag) || !tag.StartsWith(prefix, StringComparison.Ordinal))
                return false;
            return int.TryParse(tag.Substring(prefix.Length), NumberStyles.Integer, CultureInfo.InvariantCulture, out tradeId) && tradeId > 0;
        }

        private HashSet<int> CollectKnownTradeIds()
        {
            HashSet<int> ids = new HashSet<int>();
            foreach (int id in managedTrades.Keys)
                if (id > 0)
                    ids.Add(id);
            foreach (int id in linkedBellTools.Keys)
                if (id > 0)
                    ids.Add(id);
            foreach (int id in ParseTradeIds(LinkedTradeIds))
                if (id > 0)
                    ids.Add(id);
            if (LinkedTradeId > 0)
                ids.Add(LinkedTradeId);
            if (managedTrade != null && managedTrade.TradeId > 0)
                ids.Add(managedTrade.TradeId);
            return ids;
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
            DateTime tradeTime = SnapshotTime(snapshot);
            if (tradeTime != DateTime.MinValue)
            {
                int createdIndex = FindNearestBarIndex(tradeTime);
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

        private DateTime SnapshotTime(OpenBullTradeSnapshot snapshot)
        {
            if (snapshot == null)
                return DateTime.MinValue;
            if (snapshot.EntryTime != DateTime.MinValue)
                return snapshot.EntryTime;
            return snapshot.CreatedAt;
        }

        private int FindNearestBarIndex(DateTime timestamp)
        {
            if (ChartBars == null || ChartBars.Bars == null || ChartBars.Bars.Count <= 0 || timestamp == DateTime.MinValue)
                return -1;
            int count = ChartBars.Bars.Count;
            int exact = ChartBars.Bars.GetBar(timestamp);
            if (exact >= 0)
                return Math.Max(0, Math.Min(exact, count - 1));

            int start = Math.Max(0, count - 2000);
            int bestIndex = -1;
            long bestDiff = long.MaxValue;
            for (int i = start; i < count; i++)
            {
                DateTime barTime = ChartBars.Bars.GetTime(i);
                long diff = Math.Abs(barTime.Ticks - timestamp.Ticks);
                if (diff < bestDiff)
                {
                    bestDiff = diff;
                    bestIndex = i;
                }
            }
            return bestIndex;
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
            JsonString(sb, "strike_selection_method", StrikeSelection.ToString(), false);
            JsonString(sb, "moneyness_selection", NormalizeMoneynessSelection(MoneynessSelection), false);
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
            JsonString(sb, "strike_selection_method", StrikeSelection.ToString(), false);
            JsonString(sb, "moneyness_selection", NormalizeMoneynessSelection(MoneynessSelection), false);
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
            strikes.Sort();
            for (int index = strikes.Count - 1; index > 0; index--)
            {
                if (Math.Abs(strikes[index] - strikes[index - 1]) < 0.0001)
                    strikes.RemoveAt(index);
            }
            return strikes.ToArray();
        }

        private static List<string> NormalizeStrikeValues(List<string> values)
        {
            List<string> result = new List<string>();
            foreach (double strike in ParseStrikeCache(values))
                result.Add(FormatStrikeText(strike));
            return result;
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

        private static StrikeSelectionMethod ParseStrikeSelectionMethod(string value, StrikeSelectionMethod fallback)
        {
            string raw = Regex.Replace((value ?? "").Trim().ToUpperInvariant(), @"[\s/\-]+", "_");
            if (raw == "ITMOTM") raw = "ITM_OTM";
            StrikeSelectionMethod parsed;
            return Enum.TryParse(raw, true, out parsed) ? parsed : fallback;
        }

        private static string NormalizeMoneynessSelection(string value)
        {
            string raw = (value ?? "ATM").Trim().ToUpperInvariant().Replace(" ", "");
            if (raw == "ATM") return raw;
            if (Regex.IsMatch(raw, "^(ITM|OTM)([1-9]|10)$")) return raw;
            return "ATM";
        }

        private static List<string> MoneynessValues()
        {
            return new List<string>
            {
                "ITM1", "ITM2", "ITM3", "ITM4", "ITM5", "ITM6", "ITM7", "ITM8", "ITM9", "ITM10",
                "ATM",
                "OTM1", "OTM2", "OTM3", "OTM4", "OTM5", "OTM6", "OTM7", "OTM8", "OTM9", "OTM10"
            };
        }

        private static double ResolveSelectedStrike(
            List<string> strikeValues,
            double atm,
            double offsetStrike,
            string optionType,
            StrikeSelectionMethod method,
            string moneyness,
            double manualStrike)
        {
            if (method == StrikeSelectionMethod.MANUAL)
                return SelectValidStrike(strikeValues, manualStrike, atm);
            if (method == StrikeSelectionMethod.OFFSET)
                return SelectValidStrike(strikeValues, offsetStrike, atm);
            if (atm <= 0)
                return SelectValidStrike(strikeValues, manualStrike, offsetStrike);
            if (method == StrikeSelectionMethod.ATM || string.Equals(moneyness, "ATM", StringComparison.OrdinalIgnoreCase))
                return SelectValidStrike(strikeValues, atm, atm);

            double[] strikes = ParseStrikeCache(strikeValues);
            int atmIndex = -1;
            for (int i = 0; i < strikes.Length; i++)
                if (Math.Abs(strikes[i] - atm) < 0.0001) { atmIndex = i; break; }
            Match match = Regex.Match(moneyness ?? "", "^(ITM|OTM)([0-9]+)$", RegexOptions.IgnoreCase);
            if (atmIndex < 0 || !match.Success)
                return SelectValidStrike(strikeValues, atm, atm);
            int count = ParseInt(match.Groups[2].Value, 0);
            bool itm = string.Equals(match.Groups[1].Value, "ITM", StringComparison.OrdinalIgnoreCase);
            int direction = optionType == "CE" ? (itm ? -1 : 1) : (itm ? 1 : -1);
            int targetIndex = atmIndex + direction * count;
            return targetIndex >= 0 && targetIndex < strikes.Length ? strikes[targetIndex] : SelectValidStrike(strikeValues, atm, atm);
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

        private static void CacheOptionValues(List<string> underlyings, List<string> expiries, List<string> strikes, List<string> templates)
        {
            lock (templateCacheLock)
            {
                if (underlyings != null && underlyings.Count > 0)
                    cachedUnderlyings = UniqueStrings(underlyings).ToArray();
                if (expiries != null && expiries.Count > 0)
                    cachedExpiries = UniqueStrings(expiries).ToArray();
                if (strikes != null && strikes.Count > 0)
                    cachedStrikes = ParseStrikeCache(strikes);
            }
            CacheTemplateLabels(templates);
        }

        private static List<string> UniqueStrings(List<string> values)
        {
            List<string> result = new List<string>();
            if (values == null)
                return result;
            foreach (string value in values)
            {
                if (string.IsNullOrWhiteSpace(value))
                    continue;
                bool exists = false;
                foreach (string current in result)
                {
                    if (string.Equals(current, value, StringComparison.OrdinalIgnoreCase))
                    {
                        exists = true;
                        break;
                    }
                }
                if (!exists)
                    result.Add(value.Trim());
            }
            return result;
        }

        private static void TryRefreshOptionsCache(OpenBullQuickOrderIndicator instance)
        {
            if (instance == null || string.IsNullOrWhiteSpace(instance.ApiKey) || string.IsNullOrWhiteSpace(instance.OpenBullUrl))
                return;
            string key = instance.OpenBullUrl.TrimEnd('/') + "|" + instance.ApiKey + "|" + instance.Underlying + "|" + instance.UnderlyingExchange + "|" + instance.Expiry;
            lock (templateCacheLock)
            {
                if (key == optionsCacheKey && (DateTime.UtcNow - optionsCacheAt).TotalSeconds < 20)
                    return;
                optionsCacheKey = key;
                optionsCacheAt = DateTime.UtcNow;
            }
            try
            {
                string url = instance.OpenBullUrl.TrimEnd('/') + "/api/v1/futures-risk/quick-order/options";
                using (StringContent content = new StringContent(instance.BuildOptionsJson(), Encoding.UTF8, "application/json"))
                {
                    HttpResponseMessage response = Http.PostAsync(url, content).GetAwaiter().GetResult();
                    string body = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    if (response.IsSuccessStatusCode && body.IndexOf("\"status\":\"success\"", StringComparison.OrdinalIgnoreCase) >= 0)
                        CacheOptionValues(
                            ParseStringArray(body, "underlyings"),
                            ParseExpiryValues(body),
                            ParseNumberArray(body, "strikes"),
                            ParseTemplates(body)
                        );
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

        private void MaybeBackoffLivePolling(HttpResponseMessage response, string body)
        {
            int statusCode = response == null ? 0 : (int)response.StatusCode;
            if (!ShouldBackoffLivePolling(statusCode, body))
                return;

            int retryAfter = ParseRetryAfterSeconds(body);
            if (retryAfter <= 0 && response != null && response.Headers.RetryAfter != null)
            {
                if (response.Headers.RetryAfter.Delta.HasValue)
                    retryAfter = Math.Max(1, (int)response.Headers.RetryAfter.Delta.Value.TotalSeconds);
                else if (response.Headers.RetryAfter.Date.HasValue)
                    retryAfter = Math.Max(1, (int)(response.Headers.RetryAfter.Date.Value.UtcDateTime - DateTime.UtcNow).TotalSeconds);
            }
            if (retryAfter <= 0)
                retryAfter = statusCode == 429 ? 90 : 300;

            liveBackoffUntilUtc = DateTime.UtcNow.AddSeconds(retryAfter);
        }

        private static bool ShouldBackoffLivePolling(int statusCode, string body)
        {
            if (statusCode == 401 || statusCode == 403 || statusCode == 429)
                return true;
            string text = (body ?? "").ToLowerInvariant();
            return text.Contains("authentication failed")
                || text.Contains("token invalid")
                || text.Contains("invalid or expired")
                || text.Contains("unauthorized")
                || text.Contains("too many requests")
                || text.Contains("rate limit")
                || text.Contains("retry_after_seconds");
        }

        private static int ParseRetryAfterSeconds(string body)
        {
            if (string.IsNullOrWhiteSpace(body))
                return 0;
            Match match = Regex.Match(body, "\"retry_after_seconds\"\\s*:\\s*(\\d+)", RegexOptions.IgnoreCase);
            if (!match.Success)
                return 0;
            int seconds;
            return int.TryParse(match.Groups[1].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out seconds) ? seconds : 0;
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
            string lower = value.ToLowerInvariant();
            if (lower.Contains("broker_rate_limit") || lower.Contains("rate limit") || lower.Contains("\"805\""))
                return "Dhan rate limit - re-login/regenerate API in OpenBull Broker Config";
            if (lower.Contains("broker_auth_required") || lower.Contains("authentication expired")
                || lower.Contains("token invalid") || lower.Contains("invalid or expired"))
                return "Dhan login expired - re-login in OpenBull Broker Config";
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
                if (closeTradeButton != null) closeTradeButton.IsEnabled = enabled && HasActiveLinkedTrade();
                if (closeConfirmButton != null) closeConfirmButton.IsEnabled = enabled && HasActiveLinkedTrade();
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
                OpenBullQuickOrderIndicator instance = context == null ? null : context.Instance as OpenBullQuickOrderIndicator;
                TryRefreshOptionsCache(instance);
                List<string> values = new List<string>();
                lock (templateCacheLock)
                {
                    values.AddRange(cachedUnderlyings);
                }
                if (instance != null && !string.IsNullOrWhiteSpace(instance.Underlying) && !ContainsText(values, instance.Underlying))
                    values.Add(instance.Underlying);
                return new TypeConverter.StandardValuesCollection(values);
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

        public class MoneynessListConverter : StringConverter
        {
            private static readonly string[] Values = new string[]
            {
                "ITM1", "ITM2", "ITM3", "ITM4", "ITM5", "ITM6", "ITM7", "ITM8", "ITM9", "ITM10",
                "ATM",
                "OTM1", "OTM2", "OTM3", "OTM4", "OTM5", "OTM6", "OTM7", "OTM8", "OTM9", "OTM10"
            };

            public override bool GetStandardValuesSupported(ITypeDescriptorContext context) { return true; }
            public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) { return true; }
            public override TypeConverter.StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
            {
                return new TypeConverter.StandardValuesCollection(Values);
            }
        }

        public class TargetTemplateListConverter : StringConverter
        {
            public override bool GetStandardValuesSupported(ITypeDescriptorContext context) { return true; }
            public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) { return false; }
            public override TypeConverter.StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
            {
                OpenBullQuickOrderIndicator instance = context == null ? null : context.Instance as OpenBullQuickOrderIndicator;
                TryRefreshOptionsCache(instance);
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
        [Display(Name = "Auto-detect from chart", GroupName = "Contract", Order = 9)]
        public bool AutoDetectUnderlying { get; set; }

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
        [Display(Name = "Strike Selection Method", GroupName = "Contract", Order = 15)]
        public StrikeSelectionMethod StrikeSelection { get; set; }

        [NinjaScriptProperty]
        [TypeConverter(typeof(MoneynessListConverter))]
        [Display(Name = "ITM / OTM Selection", GroupName = "Contract", Order = 16)]
        public string MoneynessSelection { get; set; }

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

    // This helper intentionally lives in the indicator source file. Users only
    // need to copy OpenBullQuickOrderIndicator.cs into NinjaTrader.
    public static class OpenBullQuickOrderSymbolMapper
    {
        private static readonly string[] KnownUnderlyings = new[]
        {
            "MIDCPNIFTY", "NIFTYNXT50", "BANKNIFTY", "FINNIFTY", "NATURALGAS",
            "NATGASMINI", "GOLDPETAL", "SILVERMIC", "SILVER100", "CRUDEOILM",
            "CRUDEOIL", "ALUMINIUM", "SENSEX50", "SENSEX", "BANKEX", "NIFTY",
            "INDIAVIX", "SILVERM", "SILVER", "COPPERM", "COPPER", "ALUMINI",
            "GOLDM", "GOLD", "ZINC", "LEAD"
        };

        private static readonly HashSet<string> McxUnderlyings = new HashSet<string>(
            new[]
            {
                "CRUDEOIL", "CRUDEOILM", "NATURALGAS", "NATGASMINI", "GOLD",
                "GOLDM", "GOLDPETAL", "SILVER", "SILVERM", "SILVERMIC",
                "SILVER100", "COPPER", "COPPERM", "ALUMINIUM", "ALUMINI",
                "ZINC", "LEAD"
            },
            StringComparer.OrdinalIgnoreCase
        );

        private static readonly HashSet<string> BseUnderlyings = new HashSet<string>(
            new[] { "SENSEX", "SENSEX50", "BANKEX" },
            StringComparer.OrdinalIgnoreCase
        );

        public static string InferUnderlying(
            string masterInstrumentName,
            string fullInstrumentName,
            IEnumerable<string> configuredUnderlyings
        )
        {
            List<string> candidates = new List<string>();
            HashSet<string> knownCandidates = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (configuredUnderlyings != null)
            {
                foreach (string configured in configuredUnderlyings)
                {
                    string candidate = NormalizeCandidate(configured);
                    if (!string.IsNullOrWhiteSpace(candidate) && knownCandidates.Add(candidate))
                        candidates.Add(candidate);
                }
            }
            foreach (string configured in KnownUnderlyings)
            {
                string candidate = NormalizeCandidate(configured);
                if (!string.IsNullOrWhiteSpace(candidate) && knownCandidates.Add(candidate))
                    candidates.Add(candidate);
            }
            candidates.Sort(delegate(string left, string right)
            {
                int lengthComparison = right.Length.CompareTo(left.Length);
                return lengthComparison != 0
                    ? lengthComparison
                    : string.Compare(left, right, StringComparison.OrdinalIgnoreCase);
            });

            foreach (string input in new[] { masterInstrumentName, fullInstrumentName })
            {
                string symbol = NormalizeInstrument(input);
                if (string.IsNullOrWhiteSpace(symbol))
                    continue;

                foreach (string candidate in candidates)
                {
                    if (IsCandidateMatch(symbol, candidate))
                        return candidate;
                }

                string parsed = ParseContractBase(symbol);
                if (!string.IsNullOrWhiteSpace(parsed))
                    return parsed;
            }
            return "";
        }

        public static string InferExchange(string underlying)
        {
            string value = NormalizeCandidate(underlying);
            if (McxUnderlyings.Contains(value))
                return "MCX";
            if (BseUnderlyings.Contains(value))
                return "BSE_INDEX";
            return "NSE_INDEX";
        }

        private static bool IsCandidateMatch(string symbol, string candidate)
        {
            if (string.Equals(symbol, candidate, StringComparison.OrdinalIgnoreCase))
                return true;
            if (!symbol.StartsWith(candidate, StringComparison.OrdinalIgnoreCase))
                return false;
            string suffix = symbol.Substring(candidate.Length);
            if (string.IsNullOrWhiteSpace(suffix))
                return true;
            return Regex.IsMatch(
                suffix,
                "^(?:_?I|[0-9]{2}[A-Z]{3}[0-9]{2}(?:FUT|[0-9]+(?:\\.[0-9]+)?(?:CE|PE)))$",
                RegexOptions.IgnoreCase
            );
        }

        private static string ParseContractBase(string symbol)
        {
            Match contract = Regex.Match(
                symbol,
                "^(?<base>[A-Z]+?)[0-9]{2}[A-Z]{3}[0-9]{2}(?:FUT|[0-9]+(?:\\.[0-9]+)?(?:CE|PE))$",
                RegexOptions.IgnoreCase
            );
            if (contract.Success)
                return contract.Groups["base"].Value.ToUpperInvariant();
            if (symbol.EndsWith("_I", StringComparison.OrdinalIgnoreCase))
                return symbol.Substring(0, symbol.Length - 2).ToUpperInvariant();
            return Regex.IsMatch(symbol, "^[A-Z]+$") ? symbol.ToUpperInvariant() : "";
        }

        private static string NormalizeCandidate(string value)
        {
            return (value ?? "").Trim().ToUpperInvariant();
        }

        private static string NormalizeInstrument(string value)
        {
            string result = (value ?? "").Trim().ToUpperInvariant();
            int colon = result.LastIndexOf(':');
            if (colon >= 0 && colon < result.Length - 1)
                result = result.Substring(colon + 1);
            int space = result.IndexOf(' ');
            if (space > 0)
                result = result.Substring(0, space);
            return result.Trim();
        }
    }
}
