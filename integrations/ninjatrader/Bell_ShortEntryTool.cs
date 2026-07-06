#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Core.FloatingPoint;
#endregion

namespace NinjaTrader.NinjaScript.DrawingTools
{
    public class Bell_ShortEntryTool : DrawingTool
    {
        #region Properties

        private int slDistancePoints = 25;
        private int t1DistancePoints = 50;
        private int t2DistancePoints = 100;
        private int t3DistancePoints = 150;
        private int t4DistancePoints = 200;
        private int t5DistancePoints = 250;
        private int t6DistancePoints = 300;

        [Range(1, 1000)]
        [Display(Name = "SL Distance (Points)", Description = "Stop Loss distance in points from Entry", GroupName = "Parameters", Order = 1)]
        public int SLDistancePoints
        {
            get { return slDistancePoints; }
            set
            {
                slDistancePoints = value;
                RecalculateLevels();
            }
        }

        [Display(Name = "Show ME1", Description = "Show/hide ME1", GroupName = "Targets", Order = 1)]
        public bool ShowT1 { get; set; }

        [Range(1, 1000)]
        [Display(Name = "ME1 Distance (Points)", Description = "ME1 distance from Entry", GroupName = "Targets", Order = 2)]
        public int T1DistancePoints
        {
            get { return t1DistancePoints; }
            set
            {
                t1DistancePoints = value;
                RecalculateLevels();
            }
        }

        [Display(Name = "Show ME2", Description = "Show/hide ME2", GroupName = "Targets", Order = 3)]
        public bool ShowT2 { get; set; }

        [Range(1, 1000)]
        [Display(Name = "ME2 Distance (Points)", Description = "ME2 distance from Entry", GroupName = "Targets", Order = 4)]
        public int T2DistancePoints
        {
            get { return t2DistancePoints; }
            set
            {
                t2DistancePoints = value;
                RecalculateLevels();
            }
        }

        [Display(Name = "Show ME3", Description = "Show/hide ME3", GroupName = "Targets", Order = 5)]
        public bool ShowT3 { get; set; }

        [Range(1, 1000)]
        [Display(Name = "ME3 Distance (Points)", Description = "ME3 distance from Entry", GroupName = "Targets", Order = 6)]
        public int T3DistancePoints
        {
            get { return t3DistancePoints; }
            set
            {
                t3DistancePoints = value;
                RecalculateLevels();
            }
        }

        [Display(Name = "Show ME4", Description = "Show/hide ME4", GroupName = "Targets", Order = 7)]
        public bool ShowT4 { get; set; }

        [Range(1, 1000)]
        [Display(Name = "ME4 Distance (Points)", Description = "ME4 distance from Entry", GroupName = "Targets", Order = 8)]
        public int T4DistancePoints
        {
            get { return t4DistancePoints; }
            set
            {
                t4DistancePoints = value;
                RecalculateLevels();
            }
        }

        [Display(Name = "Show ME5", Description = "Show/hide ME5", GroupName = "Targets", Order = 9)]
        public bool ShowT5 { get; set; }

        [Range(1, 1000)]
        [Display(Name = "ME5 Distance (Points)", Description = "ME5 distance from Entry", GroupName = "Targets", Order = 10)]
        public int T5DistancePoints
        {
            get { return t5DistancePoints; }
            set
            {
                t5DistancePoints = value;
                RecalculateLevels();
            }
        }

        [Display(Name = "Show ME6", Description = "Show/hide ME6", GroupName = "Targets", Order = 11)]
        public bool ShowT6 { get; set; }

        [Range(1, 1000)]
        [Display(Name = "ME6 Distance (Points)", Description = "ME6 distance from Entry", GroupName = "Targets", Order = 12)]
        public int T6DistancePoints
        {
            get { return t6DistancePoints; }
            set
            {
                t6DistancePoints = value;
                RecalculateLevels();
            }
        }

        [Range(1, 10)]
        [Display(Name = "Line Thickness", Description = "Thickness of all lines", GroupName = "Visual", Order = 1)]
        public int LineThickness { get; set; }

        [Range(8, 20)]
        [Display(Name = "Font Size", Description = "Font size for labels", GroupName = "Visual", Order = 2)]
        public int FontSize { get; set; }

        [XmlIgnore]
        [Display(Name = "Entry Color", Description = "Color of entry line", GroupName = "Visual", Order = 3)]
        public Brush EntryBrush { get; set; }

        [Browsable(false)]
        public string EntryBrushSerialize
        {
            get { return Serialize.BrushToString(EntryBrush); }
            set { EntryBrush = Serialize.StringToBrush(value); }
        }

        [XmlIgnore]
        [Display(Name = "SL Color", Description = "Color of stop loss line", GroupName = "Visual", Order = 4)]
        public Brush SLBrush { get; set; }

        [Browsable(false)]
        public string SLBrushSerialize
        {
            get { return Serialize.BrushToString(SLBrush); }
            set { SLBrush = Serialize.StringToBrush(value); }
        }

        [XmlIgnore]
        [Display(Name = "Target Color", Description = "Color of target lines", GroupName = "Visual", Order = 5)]
        public Brush TargetBrush { get; set; }

        [Browsable(false)]
        public string TargetBrushSerialize
        {
            get { return Serialize.BrushToString(TargetBrush); }
            set { TargetBrush = Serialize.StringToBrush(value); }
        }

        [Browsable(false)]
        public ChartAnchor EntryAnchor { get; set; }

        [Browsable(false)]
        public ChartAnchor EndAnchor { get; set; }

        [Browsable(false)]
        public ChartAnchor SLAnchor { get; set; }

        [Browsable(false)]
        public ChartAnchor SLEndAnchor { get; set; }

        [Browsable(false)]
        public ChartAnchor T1Anchor { get; set; }

        [Browsable(false)]
        public ChartAnchor T1EndAnchor { get; set; }

        [Browsable(false)]
        public ChartAnchor T2Anchor { get; set; }

        [Browsable(false)]
        public ChartAnchor T2EndAnchor { get; set; }

        [Browsable(false)]
        public ChartAnchor T3Anchor { get; set; }

        [Browsable(false)]
        public ChartAnchor T3EndAnchor { get; set; }

        [Browsable(false)]
        public ChartAnchor T4Anchor { get; set; }

        [Browsable(false)]
        public ChartAnchor T4EndAnchor { get; set; }

        [Browsable(false)]
        public ChartAnchor T5Anchor { get; set; }

        [Browsable(false)]
        public ChartAnchor T5EndAnchor { get; set; }

        [Browsable(false)]
        public ChartAnchor T6Anchor { get; set; }

        [Browsable(false)]
        public ChartAnchor T6EndAnchor { get; set; }

        [Display(Name = "Move Lines Together", Description = "When enabled, dragging any line moves all lines together", GroupName = "Parameters", Order = 0)]
        public bool MoveLinesTogether { get; set; }

        [Display(Name = "OpenBull Trade ID", Description = "Linked OpenBull Futures-Risk trade id", GroupName = "OpenBull", Order = 1)]
        public int OpenBullTradeId { get; set; }

        [Display(Name = "OpenBull MTM", Description = "Live MTM shown near S React", GroupName = "OpenBull", Order = 2)]
        public double OpenBullMtm { get; set; }

        [Display(Name = "OpenBull Sync Status", Description = "Last OpenBull level-sync result", GroupName = "OpenBull", Order = 3)]
        public string OpenBullSyncStatus { get; set; }

        [Browsable(false)]
        public string T1Status { get; set; }

        [Browsable(false)]
        public string T2Status { get; set; }

        [Browsable(false)]
        public string T3Status { get; set; }

        [Browsable(false)]
        public string T4Status { get; set; }

        [Browsable(false)]
        public string T5Status { get; set; }

        [Browsable(false)]
        public string T6Status { get; set; }

        public override IEnumerable<ChartAnchor> Anchors
        {
            get
            {
                if (EntryAnchor != null) yield return EntryAnchor;
                if (EndAnchor != null) yield return EndAnchor;
                if (SLAnchor != null) yield return SLAnchor;
                if (SLEndAnchor != null) yield return SLEndAnchor;
                if (T1Anchor != null && ShowT1) yield return T1Anchor;
                if (T1EndAnchor != null && ShowT1) yield return T1EndAnchor;
                if (T2Anchor != null && ShowT2) yield return T2Anchor;
                if (T2EndAnchor != null && ShowT2) yield return T2EndAnchor;
                if (T3Anchor != null && ShowT3) yield return T3Anchor;
                if (T3EndAnchor != null && ShowT3) yield return T3EndAnchor;
                if (T4Anchor != null && ShowT4) yield return T4Anchor;
                if (T4EndAnchor != null && ShowT4) yield return T4EndAnchor;
                if (T5Anchor != null && ShowT5) yield return T5Anchor;
                if (T5EndAnchor != null && ShowT5) yield return T5EndAnchor;
                if (T6Anchor != null && ShowT6) yield return T6Anchor;
                if (T6EndAnchor != null && ShowT6) yield return T6EndAnchor;
            }
        }

        #endregion

        public override object Icon { get { return Gui.Tools.Icons.DrawArrowDown; } }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Short Entry Tool with Entry, SL, and 6 Targets";
                Name = "Bell Short Entry Tool";
                DrawingState = DrawingState.Building;

                SLDistancePoints = 25;

                // Individual target distances
                T1DistancePoints = 50;
                T2DistancePoints = 100;
                T3DistancePoints = 150;
                T4DistancePoints = 200;
                T5DistancePoints = 250;
                T6DistancePoints = 300;

                ShowT1 = true;
                ShowT2 = true;
                ShowT3 = true;
                ShowT4 = true;
                ShowT5 = false;
                ShowT6 = false;

                MoveLinesTogether = true; // Default: dragging any line moves all lines
                OpenBullTradeId = 0;
                OpenBullMtm = 0;
                OpenBullSyncStatus = "";
                T1Status = "pending";
                T2Status = "pending";
                T3Status = "pending";
                T4Status = "pending";
                T5Status = "pending";
                T6Status = "pending";

                LineThickness = 3;
                FontSize = 15;

                EntryBrush = Brushes.DeepPink;
                SLBrush = Brushes.Orange;
                TargetBrush = Brushes.LimeGreen;

                EntryAnchor = new ChartAnchor
                {
                    DisplayName = "Entry",
                    IsEditing = true,
                    DrawingTool = this
                };

                EndAnchor = new ChartAnchor
                {
                    DisplayName = "End",
                    IsEditing = false,
                    DrawingTool = this
                };

                SLAnchor = new ChartAnchor
                {
                    DisplayName = "Stop Loss",
                    IsEditing = false,
                    DrawingTool = this
                };

                SLEndAnchor = new ChartAnchor { DisplayName = "SL End", IsEditing = false, DrawingTool = this };

                T1Anchor = new ChartAnchor { DisplayName = "T1", IsEditing = false, DrawingTool = this };
                T1EndAnchor = new ChartAnchor { DisplayName = "T1 End", IsEditing = false, DrawingTool = this };

                T2Anchor = new ChartAnchor { DisplayName = "T2", IsEditing = false, DrawingTool = this };
                T2EndAnchor = new ChartAnchor { DisplayName = "T2 End", IsEditing = false, DrawingTool = this };

                T3Anchor = new ChartAnchor { DisplayName = "T3", IsEditing = false, DrawingTool = this };
                T3EndAnchor = new ChartAnchor { DisplayName = "T3 End", IsEditing = false, DrawingTool = this };

                T4Anchor = new ChartAnchor { DisplayName = "T4", IsEditing = false, DrawingTool = this };
                T4EndAnchor = new ChartAnchor { DisplayName = "T4 End", IsEditing = false, DrawingTool = this };

                T5Anchor = new ChartAnchor { DisplayName = "T5", IsEditing = false, DrawingTool = this };
                T5EndAnchor = new ChartAnchor { DisplayName = "T5 End", IsEditing = false, DrawingTool = this };

                T6Anchor = new ChartAnchor { DisplayName = "T6", IsEditing = false, DrawingTool = this };
                T6EndAnchor = new ChartAnchor { DisplayName = "T6 End", IsEditing = false, DrawingTool = this };
            }
        }

        public override void OnMouseDown(ChartControl chartControl, ChartPanel chartPanel, ChartScale chartScale, ChartAnchor dataPoint)
        {
            if (DrawingState == DrawingState.Building)
            {
                if (EntryAnchor.IsEditing)
                {
                    // Get the bar index at click point
                    ChartBars chartBars = chartControl.BarsArray[0];
                    if (chartBars != null && chartBars.Bars != null)
                    {
                        int barIndex = chartBars.Bars.GetBar(dataPoint.Time);
                        if (barIndex >= 0 && barIndex < chartBars.Bars.Count)
                        {
                            // Get the Open price of the clicked candle
                            double openPrice = chartBars.Bars.GetOpen(barIndex);

                            // Round to tick size
                            double tickSize = AttachedTo.Instrument.MasterInstrument.TickSize;
                            openPrice = Math.Round(openPrice / tickSize) * tickSize;

                            // Set entry at Open price
                            EntryAnchor.Time = dataPoint.Time;
                            EntryAnchor.Price = openPrice;
                            EntryAnchor.IsEditing = false;

                            // Set end anchor 10 bars to the right
                            int endBarIndex = Math.Min(barIndex + 10, chartBars.Bars.Count - 1);
                            EndAnchor.Time = chartBars.Bars.GetTime(endBarIndex);
                            EndAnchor.Price = openPrice; // Same price as entry for horizontal line

                            // Distances are raw price points (NOT multiplied by tickSize)
                            // Example: Entry 25941.60 - 50 points = 25891.60 for short
                            double slDistance = SLDistancePoints;
                            double t1Distance = T1DistancePoints;
                            double t2Distance = T2DistancePoints;
                            double t3Distance = T3DistancePoints;
                            double t4Distance = T4DistancePoints;
                            double t5Distance = T5DistancePoints;
                            double t6Distance = T6DistancePoints;

                            // Set Stop Loss (above entry for short)
                            SLAnchor.Time = dataPoint.Time;
                            SLAnchor.Price = openPrice + slDistance;
                            SLEndAnchor.Time = chartBars.Bars.GetTime(endBarIndex);
                            SLEndAnchor.Price = openPrice + slDistance;

                            // Set Targets (below entry for short) - each with individual distance
                            T1Anchor.Time = dataPoint.Time;
                            T1Anchor.Price = openPrice - t1Distance;
                            T1EndAnchor.Time = chartBars.Bars.GetTime(endBarIndex);
                            T1EndAnchor.Price = openPrice - t1Distance;

                            T2Anchor.Time = dataPoint.Time;
                            T2Anchor.Price = openPrice - t2Distance;
                            T2EndAnchor.Time = chartBars.Bars.GetTime(endBarIndex);
                            T2EndAnchor.Price = openPrice - t2Distance;

                            T3Anchor.Time = dataPoint.Time;
                            T3Anchor.Price = openPrice - t3Distance;
                            T3EndAnchor.Time = chartBars.Bars.GetTime(endBarIndex);
                            T3EndAnchor.Price = openPrice - t3Distance;

                            T4Anchor.Time = dataPoint.Time;
                            T4Anchor.Price = openPrice - t4Distance;
                            T4EndAnchor.Time = chartBars.Bars.GetTime(endBarIndex);
                            T4EndAnchor.Price = openPrice - t4Distance;

                            T5Anchor.Time = dataPoint.Time;
                            T5Anchor.Price = openPrice - t5Distance;
                            T5EndAnchor.Time = chartBars.Bars.GetTime(endBarIndex);
                            T5EndAnchor.Price = openPrice - t5Distance;

                            T6Anchor.Time = dataPoint.Time;
                            T6Anchor.Price = openPrice - t6Distance;
                            T6EndAnchor.Time = chartBars.Bars.GetTime(endBarIndex);
                            T6EndAnchor.Price = openPrice - t6Distance;

                            DrawingState = DrawingState.Normal;
                        }
                    }
                }
            }
            else if (DrawingState == DrawingState.Normal)
            {
                Point point = dataPoint.GetPoint(chartControl, chartPanel, chartScale);
                ChartAnchor closest = GetClosestEditableAnchor(chartControl, chartPanel, chartScale, point);

                if (closest != null)
                {
                    if (OpenBullTradeId > 0 && closest == EntryAnchor)
                    {
                        OpenBullSyncStatus = "Entry is fixed after order placement";
                        return;
                    }
                    if (OpenBullTradeId > 0 && IsCompletedTargetAnchor(closest))
                    {
                        OpenBullSyncStatus = "Completed target is locked";
                        return;
                    }
                    closest.IsEditing = true;
                    DrawingState = DrawingState.Editing;
                }
            }
        }

        public override void OnMouseMove(ChartControl chartControl, ChartPanel chartPanel, ChartScale chartScale, ChartAnchor dataPoint)
        {
            if (DrawingState == DrawingState.Editing)
            {
                if (EntryAnchor.IsEditing)
                {
                    // When dragging entry, ALWAYS move all lines relative to it
                    double priceDelta = dataPoint.Price - EntryAnchor.Price;

                    dataPoint.CopyDataValues(EntryAnchor);
                    EndAnchor.Price += priceDelta;
                    SLAnchor.Price += priceDelta;
                    SLEndAnchor.Price += priceDelta;
                    T1Anchor.Price += priceDelta;
                    T1EndAnchor.Price += priceDelta;
                    T2Anchor.Price += priceDelta;
                    T2EndAnchor.Price += priceDelta;
                    T3Anchor.Price += priceDelta;
                    T3EndAnchor.Price += priceDelta;
                    T4Anchor.Price += priceDelta;
                    T4EndAnchor.Price += priceDelta;
                    T5Anchor.Price += priceDelta;
                    T5EndAnchor.Price += priceDelta;
                    T6Anchor.Price += priceDelta;
                    T6EndAnchor.Price += priceDelta;
                }
                else if (EndAnchor.IsEditing || SLEndAnchor.IsEditing || T1EndAnchor.IsEditing ||
                         T2EndAnchor.IsEditing || T3EndAnchor.IsEditing || T4EndAnchor.IsEditing ||
                         T5EndAnchor.IsEditing || T6EndAnchor.IsEditing)
                {
                    // Dragging any end anchor - extend/shorten lines
                    DateTime newTime = dataPoint.Time;

                    // Update all line ends together
                    EndAnchor.Time = newTime;
                    SLEndAnchor.Time = newTime;
                    T1EndAnchor.Time = newTime;
                    T2EndAnchor.Time = newTime;
                    T3EndAnchor.Time = newTime;
                    T4EndAnchor.Time = newTime;
                    T5EndAnchor.Time = newTime;
                    T6EndAnchor.Time = newTime;
                }
                else if (SLAnchor.IsEditing)
                {
                    if (MoveLinesTogether && OpenBullTradeId <= 0)
                    {
                        // Move all lines together
                        double priceDelta = dataPoint.Price - SLAnchor.Price;
                        SLAnchor.Price += priceDelta;
                        SLEndAnchor.Price += priceDelta;
                        T1Anchor.Price += priceDelta;
                        T1EndAnchor.Price += priceDelta;
                        T2Anchor.Price += priceDelta;
                        T2EndAnchor.Price += priceDelta;
                        T3Anchor.Price += priceDelta;
                        T3EndAnchor.Price += priceDelta;
                        T4Anchor.Price += priceDelta;
                        T4EndAnchor.Price += priceDelta;
                        T5Anchor.Price += priceDelta;
                        T5EndAnchor.Price += priceDelta;
                        T6Anchor.Price += priceDelta;
                        T6EndAnchor.Price += priceDelta;
                        EntryAnchor.Price += priceDelta;
                        EndAnchor.Price += priceDelta;
                    }
                    else
                    {
                        // Move only SL
                        SLAnchor.Price = dataPoint.Price;
                        SLEndAnchor.Price = dataPoint.Price;
                    }
                }
                else if (T1Anchor.IsEditing)
                {
                    if (MoveLinesTogether && OpenBullTradeId <= 0)
                    {
                        // Move all lines together
                        double priceDelta = dataPoint.Price - T1Anchor.Price;
                        SLAnchor.Price += priceDelta;
                        SLEndAnchor.Price += priceDelta;
                        T1Anchor.Price += priceDelta;
                        T1EndAnchor.Price += priceDelta;
                        T2Anchor.Price += priceDelta;
                        T2EndAnchor.Price += priceDelta;
                        T3Anchor.Price += priceDelta;
                        T3EndAnchor.Price += priceDelta;
                        T4Anchor.Price += priceDelta;
                        T4EndAnchor.Price += priceDelta;
                        T5Anchor.Price += priceDelta;
                        T5EndAnchor.Price += priceDelta;
                        T6Anchor.Price += priceDelta;
                        T6EndAnchor.Price += priceDelta;
                        EntryAnchor.Price += priceDelta;
                        EndAnchor.Price += priceDelta;
                    }
                    else
                    {
                        // Move only T1
                        T1Anchor.Price = dataPoint.Price;
                        T1EndAnchor.Price = dataPoint.Price;
                    }
                }
                else if (T2Anchor.IsEditing)
                {
                    if (MoveLinesTogether && OpenBullTradeId <= 0)
                    {
                        // Move all lines together
                        double priceDelta = dataPoint.Price - T2Anchor.Price;
                        SLAnchor.Price += priceDelta;
                        SLEndAnchor.Price += priceDelta;
                        T1Anchor.Price += priceDelta;
                        T1EndAnchor.Price += priceDelta;
                        T2Anchor.Price += priceDelta;
                        T2EndAnchor.Price += priceDelta;
                        T3Anchor.Price += priceDelta;
                        T3EndAnchor.Price += priceDelta;
                        T4Anchor.Price += priceDelta;
                        T4EndAnchor.Price += priceDelta;
                        T5Anchor.Price += priceDelta;
                        T5EndAnchor.Price += priceDelta;
                        T6Anchor.Price += priceDelta;
                        T6EndAnchor.Price += priceDelta;
                        EntryAnchor.Price += priceDelta;
                        EndAnchor.Price += priceDelta;
                    }
                    else
                    {
                        // Move only T2
                        T2Anchor.Price = dataPoint.Price;
                        T2EndAnchor.Price = dataPoint.Price;
                    }
                }
                else if (T3Anchor.IsEditing)
                {
                    if (MoveLinesTogether && OpenBullTradeId <= 0)
                    {
                        // Move all lines together
                        double priceDelta = dataPoint.Price - T3Anchor.Price;
                        SLAnchor.Price += priceDelta;
                        SLEndAnchor.Price += priceDelta;
                        T1Anchor.Price += priceDelta;
                        T1EndAnchor.Price += priceDelta;
                        T2Anchor.Price += priceDelta;
                        T2EndAnchor.Price += priceDelta;
                        T3Anchor.Price += priceDelta;
                        T3EndAnchor.Price += priceDelta;
                        T4Anchor.Price += priceDelta;
                        T4EndAnchor.Price += priceDelta;
                        T5Anchor.Price += priceDelta;
                        T5EndAnchor.Price += priceDelta;
                        T6Anchor.Price += priceDelta;
                        T6EndAnchor.Price += priceDelta;
                        EntryAnchor.Price += priceDelta;
                        EndAnchor.Price += priceDelta;
                    }
                    else
                    {
                        // Move only T3
                        T3Anchor.Price = dataPoint.Price;
                        T3EndAnchor.Price = dataPoint.Price;
                    }
                }
                else if (T4Anchor.IsEditing)
                {
                    if (MoveLinesTogether && OpenBullTradeId <= 0)
                    {
                        // Move all lines together
                        double priceDelta = dataPoint.Price - T4Anchor.Price;
                        SLAnchor.Price += priceDelta;
                        SLEndAnchor.Price += priceDelta;
                        T1Anchor.Price += priceDelta;
                        T1EndAnchor.Price += priceDelta;
                        T2Anchor.Price += priceDelta;
                        T2EndAnchor.Price += priceDelta;
                        T3Anchor.Price += priceDelta;
                        T3EndAnchor.Price += priceDelta;
                        T4Anchor.Price += priceDelta;
                        T4EndAnchor.Price += priceDelta;
                        T5Anchor.Price += priceDelta;
                        T5EndAnchor.Price += priceDelta;
                        T6Anchor.Price += priceDelta;
                        T6EndAnchor.Price += priceDelta;
                        EntryAnchor.Price += priceDelta;
                        EndAnchor.Price += priceDelta;
                    }
                    else
                    {
                        // Move only T4
                        T4Anchor.Price = dataPoint.Price;
                        T4EndAnchor.Price = dataPoint.Price;
                    }
                }
                else if (T5Anchor.IsEditing)
                {
                    if (MoveLinesTogether && OpenBullTradeId <= 0)
                    {
                        // Move all lines together
                        double priceDelta = dataPoint.Price - T5Anchor.Price;
                        SLAnchor.Price += priceDelta;
                        SLEndAnchor.Price += priceDelta;
                        T1Anchor.Price += priceDelta;
                        T1EndAnchor.Price += priceDelta;
                        T2Anchor.Price += priceDelta;
                        T2EndAnchor.Price += priceDelta;
                        T3Anchor.Price += priceDelta;
                        T3EndAnchor.Price += priceDelta;
                        T4Anchor.Price += priceDelta;
                        T4EndAnchor.Price += priceDelta;
                        T5Anchor.Price += priceDelta;
                        T5EndAnchor.Price += priceDelta;
                        T6Anchor.Price += priceDelta;
                        T6EndAnchor.Price += priceDelta;
                        EntryAnchor.Price += priceDelta;
                        EndAnchor.Price += priceDelta;
                    }
                    else
                    {
                        // Move only T5
                        T5Anchor.Price = dataPoint.Price;
                        T5EndAnchor.Price = dataPoint.Price;
                    }
                }
                else if (T6Anchor.IsEditing)
                {
                    if (MoveLinesTogether && OpenBullTradeId <= 0)
                    {
                        // Move all lines together
                        double priceDelta = dataPoint.Price - T6Anchor.Price;
                        SLAnchor.Price += priceDelta;
                        SLEndAnchor.Price += priceDelta;
                        T1Anchor.Price += priceDelta;
                        T1EndAnchor.Price += priceDelta;
                        T2Anchor.Price += priceDelta;
                        T2EndAnchor.Price += priceDelta;
                        T3Anchor.Price += priceDelta;
                        T3EndAnchor.Price += priceDelta;
                        T4Anchor.Price += priceDelta;
                        T4EndAnchor.Price += priceDelta;
                        T5Anchor.Price += priceDelta;
                        T5EndAnchor.Price += priceDelta;
                        T6Anchor.Price += priceDelta;
                        T6EndAnchor.Price += priceDelta;
                        EntryAnchor.Price += priceDelta;
                        EndAnchor.Price += priceDelta;
                    }
                    else
                    {
                        // Move only T6
                        T6Anchor.Price = dataPoint.Price;
                        T6EndAnchor.Price = dataPoint.Price;
                    }
                }
            }
        }

        public override void OnMouseUp(ChartControl chartControl, ChartPanel chartPanel, ChartScale chartScale, ChartAnchor dataPoint)
        {
            if (DrawingState == DrawingState.Editing)
            {
                EntryAnchor.IsEditing = false;
                EndAnchor.IsEditing = false;
                SLAnchor.IsEditing = false;
                SLEndAnchor.IsEditing = false;
                T1Anchor.IsEditing = false;
                T1EndAnchor.IsEditing = false;
                T2Anchor.IsEditing = false;
                T2EndAnchor.IsEditing = false;
                T3Anchor.IsEditing = false;
                T3EndAnchor.IsEditing = false;
                T4Anchor.IsEditing = false;
                T4EndAnchor.IsEditing = false;
                T5Anchor.IsEditing = false;
                T5EndAnchor.IsEditing = false;
                T6Anchor.IsEditing = false;
                T6EndAnchor.IsEditing = false;
                DrawingState = DrawingState.Normal;
                SyncLevelsToOpenBull();
            }
        }

        public override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            if (EntryAnchor == null || EntryAnchor.Time == DateTime.MinValue)
                return;

            if (DrawingState == DrawingState.Building && EntryAnchor.IsEditing)
                return;

            ChartPanel chartPanel = chartControl.ChartPanels[chartScale.PanelIndex];
            ChartBars chartBars = chartControl.BarsArray[0];

            if (chartBars == null)
                return;

            // Create dotted stroke style
            var dashStyle = DashStyleHelper.Dot;

            // Draw Entry Line (uses EndAnchor for its end point)
            DrawLineWithDot(chartControl, chartBars, chartScale, EntryAnchor, EndAnchor, EntryBrush, dashStyle, EntryLabel("S React"));

            // Draw Stop Loss Line (uses SLEndAnchor)
            DrawLineWithDot(chartControl, chartBars, chartScale, SLAnchor, SLEndAnchor, SLBrush, dashStyle, $"RL @ {FormatPrice(SLAnchor.Price)}");

            // Draw Target Lines (each with its own end anchor)
            if (ShowT1)
                DrawLineWithDot(chartControl, chartBars, chartScale, T1Anchor, T1EndAnchor, TargetBrush, dashStyle, TargetLabel(1, T1Anchor.Price, T1Status));

            if (ShowT2)
                DrawLineWithDot(chartControl, chartBars, chartScale, T2Anchor, T2EndAnchor, TargetBrush, dashStyle, TargetLabel(2, T2Anchor.Price, T2Status));

            if (ShowT3)
                DrawLineWithDot(chartControl, chartBars, chartScale, T3Anchor, T3EndAnchor, TargetBrush, dashStyle, TargetLabel(3, T3Anchor.Price, T3Status));

            if (ShowT4)
                DrawLineWithDot(chartControl, chartBars, chartScale, T4Anchor, T4EndAnchor, TargetBrush, dashStyle, TargetLabel(4, T4Anchor.Price, T4Status));

            if (ShowT5)
                DrawLineWithDot(chartControl, chartBars, chartScale, T5Anchor, T5EndAnchor, TargetBrush, dashStyle, TargetLabel(5, T5Anchor.Price, T5Status));

            if (ShowT6)
                DrawLineWithDot(chartControl, chartBars, chartScale, T6Anchor, T6EndAnchor, TargetBrush, dashStyle, TargetLabel(6, T6Anchor.Price, T6Status));

            DrawOpenBullPnlLabel(chartControl, chartBars, chartScale);
        }

        private void DrawLineWithDot(ChartControl chartControl, ChartBars chartBars, ChartScale chartScale,
                                      ChartAnchor startAnchor, ChartAnchor endAnchor, Brush brush, DashStyleHelper dashStyle, string label)
        {
            if (startAnchor == null || endAnchor == null)
                return;
            Brush renderBrush = startAnchor.IsEditing ? Brushes.Red : brush;

            int startBarIndex = chartBars.Bars.GetBar(startAnchor.Time);
            int endBarIndex = chartBars.Bars.GetBar(endAnchor.Time);

            if (startBarIndex < 0 || endBarIndex < 0)
                return;

            float startX = chartControl.GetXByBarIndex(chartBars, startBarIndex);
            float endX = chartControl.GetXByBarIndex(chartBars, endBarIndex);
            float y = chartScale.GetYByValue(startAnchor.Price);

            // Draw the line
            var start = new SharpDX.Vector2(startX, y);
            var end = new SharpDX.Vector2(endX, y);
            var stroke = new Stroke(renderBrush, dashStyle, LineThickness) { RenderTarget = RenderTarget };
            RenderTarget.DrawLine(start, end, stroke.BrushDX, stroke.Width, stroke.StrokeStyle);

            // Draw a dot at the end (for dragging)
            using (var dotBrush = renderBrush.ToDxBrush(RenderTarget))
            {
                var center = new SharpDX.Vector2(endX, y);
                var outer = new SharpDX.Direct2D1.Ellipse(center, 6f, 6f);
                var inner = new SharpDX.Direct2D1.Ellipse(center, 3f, 3f);
                RenderTarget.DrawEllipse(outer, dotBrush, 1.5f);
                RenderTarget.FillEllipse(inner, dotBrush);
                RenderTarget.DrawLine(new SharpDX.Vector2(endX - 3f, y), new SharpDX.Vector2(endX + 3f, y), dotBrush, 1f);
                RenderTarget.DrawLine(new SharpDX.Vector2(endX, y - 3f), new SharpDX.Vector2(endX, y + 3f), dotBrush, 1f);
            }

            // Draw label on the right
            DrawLabel(label, endX + 10, y, renderBrush);
        }

        private void DrawHorizontalLine(float startX, float endX, ChartScale chartScale, double price, Brush brush, DashStyleHelper dashStyle, string label)
        {
            float y = chartScale.GetYByValue(price);
            var start = new SharpDX.Vector2(startX, y);
            var end = new SharpDX.Vector2(endX, y);

            // Draw line
            var stroke = new Stroke(brush, dashStyle, LineThickness) { RenderTarget = RenderTarget };
            RenderTarget.DrawLine(start, end, stroke.BrushDX, stroke.Width, stroke.StrokeStyle);

            // Draw label on the right
            DrawLabel(label, endX + 5, y, brush);
        }

        private void DrawLabel(string text, float x, float y, Brush textBrush)
        {
            var font = new SimpleFont("Arial", FontSize) { Bold = true };

            using (var textFormat = font.ToDirectWriteTextFormat())
            using (var layout = new SharpDX.DirectWrite.TextLayout(Core.Globals.DirectWriteFactory, text, textFormat, 200, 50))
            {
                float padding = 4f;
                float textX = x;
                float textY = y - layout.Metrics.Height / 2;

                // Background
                var bgRect = new SharpDX.RectangleF(
                    textX - padding,
                    textY - padding,
                    layout.Metrics.Width + padding * 2,
                    layout.Metrics.Height + padding * 2
                );
                var rounded = new SharpDX.Direct2D1.RoundedRectangle
                {
                    Rect = bgRect,
                    RadiusX = 6f,
                    RadiusY = 6f
                };
                Brush finalTextBrush = textBrush;
                if (text.IndexOf("P&L -", StringComparison.OrdinalIgnoreCase) >= 0
                    || text.IndexOf("MTM -", StringComparison.OrdinalIgnoreCase) >= 0)
                    finalTextBrush = Brushes.Red;
                else if (text.IndexOf("P&L +", StringComparison.OrdinalIgnoreCase) >= 0
                    || text.IndexOf("MTM +", StringComparison.OrdinalIgnoreCase) >= 0)
                    finalTextBrush = Brushes.LimeGreen;

                using (var bgBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new SharpDX.Color4(0, 0, 0, 0.7f)))
                using (var textBrushDx = finalTextBrush.ToDxBrush(RenderTarget))
                {
                    RenderTarget.FillRoundedRectangle(rounded, bgBrush);
                    RenderTarget.DrawTextLayout(new SharpDX.Vector2(textX, textY), layout, textBrushDx);
                }
            }
        }

        private string FormatPrice(double price)
        {
            if (AttachedTo != null && AttachedTo.Instrument != null)
            {
                double tickSize = AttachedTo.Instrument.MasterInstrument.TickSize;
                return price.ToString(Core.Globals.GetTickFormatString(tickSize));
            }
            return price.ToString("F2");
        }

        private string EntryLabel(string prefix)
        {
            return $"{prefix} @ {FormatPrice(EntryAnchor.Price)}";
        }

        private void DrawOpenBullPnlLabel(ChartControl chartControl, ChartBars chartBars, ChartScale chartScale)
        {
            if (OpenBullTradeId <= 0 || EntryAnchor == null || EndAnchor == null || chartBars == null)
                return;

            int endBarIndex = chartBars.Bars.GetBar(EndAnchor.Time);
            if (endBarIndex < 0)
                return;

            float endX = chartControl.GetXByBarIndex(chartBars, endBarIndex);
            float y = chartScale.GetYByValue(EntryAnchor.Price) + Math.Max(18f, FontSize + 8f);
            Brush pnlBrush = OpenBullMtm >= 0 ? Brushes.LimeGreen : Brushes.Red;
            DrawLabel(OpenBullPnlLabel(), endX + 10, y, pnlBrush);
        }

        private string OpenBullPnlLabel()
        {
            string sign = OpenBullMtm >= 0 ? "+" : "";
            return $"P&L {sign}{OpenBullMtm.ToString("N2", System.Globalization.CultureInfo.InvariantCulture)}";
        }

        private string TargetLabel(int seq, double price, string status)
        {
            string label = $"ME{seq} @ {FormatPrice(price)}";
            if (!string.IsNullOrWhiteSpace(status) && !string.Equals(status, "pending", StringComparison.OrdinalIgnoreCase))
                label += $" {status}";
            return label;
        }

        private bool IsPendingStatus(string status)
        {
            return string.IsNullOrWhiteSpace(status) || string.Equals(status, "pending", StringComparison.OrdinalIgnoreCase);
        }

        private bool IsCompletedTargetAnchor(ChartAnchor anchor)
        {
            if (anchor == null)
                return false;
            if ((anchor == T1Anchor || anchor == T1EndAnchor) && !IsPendingStatus(T1Status)) return true;
            if ((anchor == T2Anchor || anchor == T2EndAnchor) && !IsPendingStatus(T2Status)) return true;
            if ((anchor == T3Anchor || anchor == T3EndAnchor) && !IsPendingStatus(T3Status)) return true;
            if ((anchor == T4Anchor || anchor == T4EndAnchor) && !IsPendingStatus(T4Status)) return true;
            if ((anchor == T5Anchor || anchor == T5EndAnchor) && !IsPendingStatus(T5Status)) return true;
            if ((anchor == T6Anchor || anchor == T6EndAnchor) && !IsPendingStatus(T6Status)) return true;
            return false;
        }

        private ChartAnchor GetClosestEditableAnchor(ChartControl chartControl, ChartPanel chartPanel, ChartScale chartScale, Point point)
        {
            ChartAnchor closest = GetClosestAnchor(chartControl, chartPanel, chartScale, 10, point);
            if (closest != null)
                return closest;
            return GetClosestLineAnchor(chartControl, chartPanel, chartScale, point);
        }

        private ChartAnchor GetClosestLineAnchor(ChartControl chartControl, ChartPanel chartPanel, ChartScale chartScale, Point point)
        {
            if (IsPointNearLine(chartControl, chartPanel, chartScale, SLAnchor, SLEndAnchor, point))
                return SLAnchor;
            if (ShowT1 && IsPointNearLine(chartControl, chartPanel, chartScale, T1Anchor, T1EndAnchor, point))
                return T1Anchor;
            if (ShowT2 && IsPointNearLine(chartControl, chartPanel, chartScale, T2Anchor, T2EndAnchor, point))
                return T2Anchor;
            if (ShowT3 && IsPointNearLine(chartControl, chartPanel, chartScale, T3Anchor, T3EndAnchor, point))
                return T3Anchor;
            if (ShowT4 && IsPointNearLine(chartControl, chartPanel, chartScale, T4Anchor, T4EndAnchor, point))
                return T4Anchor;
            if (ShowT5 && IsPointNearLine(chartControl, chartPanel, chartScale, T5Anchor, T5EndAnchor, point))
                return T5Anchor;
            if (ShowT6 && IsPointNearLine(chartControl, chartPanel, chartScale, T6Anchor, T6EndAnchor, point))
                return T6Anchor;
            return null;
        }

        private bool IsPointNearLine(ChartControl chartControl, ChartPanel chartPanel, ChartScale chartScale, ChartAnchor startAnchor, ChartAnchor endAnchor, Point point)
        {
            if (startAnchor == null || endAnchor == null || startAnchor.Time == DateTime.MinValue)
                return false;
            Point start = startAnchor.GetPoint(chartControl, chartPanel, chartScale);
            Point end = endAnchor.GetPoint(chartControl, chartPanel, chartScale);
            double minX = Math.Min(start.X, end.X) - 18;
            double maxX = Math.Max(start.X, end.X) + 120;
            if (point.X < minX || point.X > maxX)
                return false;
            return Math.Abs(point.Y - start.Y) <= 10;
        }

        private void SyncLevelsToOpenBull()
        {
            if (OpenBullTradeId <= 0 || SLAnchor == null)
                return;
            var targets = new List<NinjaTrader.NinjaScript.OpenBullLevelTarget>();
            if (ShowT1 && T1Anchor != null && IsPendingStatus(T1Status)) targets.Add(new NinjaTrader.NinjaScript.OpenBullLevelTarget { Seq = 1, Price = T1Anchor.Price });
            if (ShowT2 && T2Anchor != null && IsPendingStatus(T2Status)) targets.Add(new NinjaTrader.NinjaScript.OpenBullLevelTarget { Seq = 2, Price = T2Anchor.Price });
            if (ShowT3 && T3Anchor != null && IsPendingStatus(T3Status)) targets.Add(new NinjaTrader.NinjaScript.OpenBullLevelTarget { Seq = 3, Price = T3Anchor.Price });
            if (ShowT4 && T4Anchor != null && IsPendingStatus(T4Status)) targets.Add(new NinjaTrader.NinjaScript.OpenBullLevelTarget { Seq = 4, Price = T4Anchor.Price });
            if (ShowT5 && T5Anchor != null && IsPendingStatus(T5Status)) targets.Add(new NinjaTrader.NinjaScript.OpenBullLevelTarget { Seq = 5, Price = T5Anchor.Price });
            if (ShowT6 && T6Anchor != null && IsPendingStatus(T6Status)) targets.Add(new NinjaTrader.NinjaScript.OpenBullLevelTarget { Seq = 6, Price = T6Anchor.Price });
            System.Threading.Tasks.Task.Run(async () =>
            {
                try
                {
                    OpenBullSyncStatus = await NinjaTrader.NinjaScript.OpenBullFuturesRiskBridge.UpdateLevelsAsync(OpenBullTradeId, SLAnchor.Price, targets);
                }
                catch (Exception ex)
                {
                    OpenBullSyncStatus = ex.Message;
                }
            });
        }

        public void LoadOpenBullTrade(DateTime entryTime, DateTime endTime, double entryPrice, double slPrice,
            IList<NinjaTrader.NinjaScript.OpenBullTradeLevel> targets, int tradeId, double mtm)
        {
            if (entryTime == DateTime.MinValue)
                entryTime = DateTime.Now;
            if (endTime == DateTime.MinValue || endTime <= entryTime)
                endTime = entryTime.AddMinutes(10);

            bool preserveTimes = OpenBullTradeId == tradeId && IsValidAnchorTime(EntryAnchor) && IsValidAnchorTime(EndAnchor);
            DateTime lineEntryTime = ExistingTimeOr(EntryAnchor, entryTime, preserveTimes);
            DateTime lineEndTime = ExistingTimeOr(EndAnchor, endTime, preserveTimes);

            OpenBullTradeId = tradeId;
            OpenBullMtm = mtm;
            OpenBullSyncStatus = "Linked to OpenBull";

            if (DrawingState == DrawingState.Editing)
                return;

            MoveLinesTogether = false;
            DrawingState = DrawingState.Normal;

            SetAnchor(EntryAnchor, lineEntryTime, entryPrice, false);
            SetAnchor(EndAnchor, lineEndTime, entryPrice, false);
            SetAnchor(SLAnchor, ExistingTimeOr(SLAnchor, lineEntryTime, preserveTimes), slPrice, false);
            SetAnchor(SLEndAnchor, ExistingTimeOr(SLEndAnchor, lineEndTime, preserveTimes), slPrice, false);
            slDistancePoints = Math.Max(1, (int)Math.Round(Math.Abs(entryPrice - slPrice)));

            HideAllTargets();
            if (targets != null)
            {
                foreach (NinjaTrader.NinjaScript.OpenBullTradeLevel target in targets)
                {
                    if (target == null || target.Seq < 1 || target.Seq > 6 || target.Price <= 0)
                        continue;
                    ApplyTarget(target.Seq, lineEntryTime, lineEndTime, entryPrice, target.Price, target.Status, preserveTimes);
                }
            }
        }

        private bool IsValidAnchorTime(ChartAnchor anchor)
        {
            return anchor != null && anchor.Time != DateTime.MinValue;
        }

        private DateTime ExistingTimeOr(ChartAnchor anchor, DateTime fallback, bool preserveTimes)
        {
            return preserveTimes && IsValidAnchorTime(anchor) ? anchor.Time : fallback;
        }

        private void SetAnchor(ChartAnchor anchor, DateTime time, double price, bool editing)
        {
            if (anchor == null)
                return;
            anchor.Time = time;
            anchor.Price = price;
            anchor.IsEditing = editing;
            anchor.DrawingTool = this;
        }

        private void HideAllTargets()
        {
            ShowT1 = ShowT2 = ShowT3 = ShowT4 = ShowT5 = ShowT6 = false;
            T1Status = T2Status = T3Status = T4Status = T5Status = T6Status = "pending";
        }

        private void ApplyTarget(int seq, DateTime entryTime, DateTime endTime, double entryPrice, double targetPrice, string status, bool preserveTimes)
        {
            int distance = Math.Max(1, (int)Math.Round(Math.Abs(targetPrice - entryPrice)));
            string cleanStatus = string.IsNullOrWhiteSpace(status) || status == "null" ? "pending" : status;
            if (seq == 1)
            {
                ShowT1 = true; t1DistancePoints = distance; T1Status = cleanStatus;
                SetAnchor(T1Anchor, ExistingTimeOr(T1Anchor, entryTime, preserveTimes), targetPrice, false); SetAnchor(T1EndAnchor, ExistingTimeOr(T1EndAnchor, endTime, preserveTimes), targetPrice, false);
            }
            else if (seq == 2)
            {
                ShowT2 = true; t2DistancePoints = distance; T2Status = cleanStatus;
                SetAnchor(T2Anchor, ExistingTimeOr(T2Anchor, entryTime, preserveTimes), targetPrice, false); SetAnchor(T2EndAnchor, ExistingTimeOr(T2EndAnchor, endTime, preserveTimes), targetPrice, false);
            }
            else if (seq == 3)
            {
                ShowT3 = true; t3DistancePoints = distance; T3Status = cleanStatus;
                SetAnchor(T3Anchor, ExistingTimeOr(T3Anchor, entryTime, preserveTimes), targetPrice, false); SetAnchor(T3EndAnchor, ExistingTimeOr(T3EndAnchor, endTime, preserveTimes), targetPrice, false);
            }
            else if (seq == 4)
            {
                ShowT4 = true; t4DistancePoints = distance; T4Status = cleanStatus;
                SetAnchor(T4Anchor, ExistingTimeOr(T4Anchor, entryTime, preserveTimes), targetPrice, false); SetAnchor(T4EndAnchor, ExistingTimeOr(T4EndAnchor, endTime, preserveTimes), targetPrice, false);
            }
            else if (seq == 5)
            {
                ShowT5 = true; t5DistancePoints = distance; T5Status = cleanStatus;
                SetAnchor(T5Anchor, ExistingTimeOr(T5Anchor, entryTime, preserveTimes), targetPrice, false); SetAnchor(T5EndAnchor, ExistingTimeOr(T5EndAnchor, endTime, preserveTimes), targetPrice, false);
            }
            else if (seq == 6)
            {
                ShowT6 = true; t6DistancePoints = distance; T6Status = cleanStatus;
                SetAnchor(T6Anchor, ExistingTimeOr(T6Anchor, entryTime, preserveTimes), targetPrice, false); SetAnchor(T6EndAnchor, ExistingTimeOr(T6EndAnchor, endTime, preserveTimes), targetPrice, false);
            }
        }

        private void RecalculateLevels()
        {
            // Only recalculate if entry anchor has been set
            if (EntryAnchor == null || EntryAnchor.Time == DateTime.MinValue)
                return;

            double entryPrice = EntryAnchor.Price;

            // Recalculate Stop Loss (above entry for short)
            if (SLAnchor != null)
                SLAnchor.Price = entryPrice + SLDistancePoints;

            // Recalculate Targets (below entry for short)
            if (T1Anchor != null)
            {
                T1Anchor.Price = entryPrice - T1DistancePoints;
                if (T1EndAnchor != null) T1EndAnchor.Price = entryPrice - T1DistancePoints;
            }

            if (T2Anchor != null)
            {
                T2Anchor.Price = entryPrice - T2DistancePoints;
                if (T2EndAnchor != null) T2EndAnchor.Price = entryPrice - T2DistancePoints;
            }

            if (T3Anchor != null)
            {
                T3Anchor.Price = entryPrice - T3DistancePoints;
                if (T3EndAnchor != null) T3EndAnchor.Price = entryPrice - T3DistancePoints;
            }

            if (T4Anchor != null)
            {
                T4Anchor.Price = entryPrice - T4DistancePoints;
                if (T4EndAnchor != null) T4EndAnchor.Price = entryPrice - T4DistancePoints;
            }

            if (T5Anchor != null)
            {
                T5Anchor.Price = entryPrice - T5DistancePoints;
                if (T5EndAnchor != null) T5EndAnchor.Price = entryPrice - T5DistancePoints;
            }

            if (T6Anchor != null)
            {
                T6Anchor.Price = entryPrice - T6DistancePoints;
                if (T6EndAnchor != null) T6EndAnchor.Price = entryPrice - T6DistancePoints;
            }
        }
    }

    public static partial class Draw
    {
        public static Bell_ShortEntryTool BellShortEntry(NinjaScriptBase owner, string tag, bool isAutoScale,
            DateTime entryTime, DateTime endTime, double entryPrice, double slPrice,
            IList<NinjaTrader.NinjaScript.OpenBullTradeLevel> targets, int tradeId, double mtm)
        {
            if (owner == null)
                throw new ArgumentException("owner");
            if (string.IsNullOrWhiteSpace(tag))
                throw new ArgumentException(@"tag cant be null or empty", nameof(tag));
            Bell_ShortEntryTool tool = DrawingTool.GetByTagOrNew(owner, typeof(Bell_ShortEntryTool), tag, null) as Bell_ShortEntryTool;
            if (tool == null)
                return null;
            DrawingTool.SetDrawingToolCommonValues(tool, tag, isAutoScale, owner, false);
            tool.LoadOpenBullTrade(entryTime, endTime, entryPrice, slPrice, targets, tradeId, mtm);
            tool.SetState(State.Active);
            return tool;
        }
    }
}
