#region Using declarations
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Net.Http;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
#endregion

namespace NinjaTrader.NinjaScript
{
    public class OpenBullLevelTarget
    {
        public int Seq { get; set; }
        public double Price { get; set; }
        public double? ExitPct { get; set; }
    }

    public class OpenBullTradeLevel
    {
        public int Seq { get; set; }
        public double Price { get; set; }
        public double Points { get; set; }
        public double ExitPct { get; set; }
        public string Status { get; set; }
    }

    public class OpenBullTradeSnapshot
    {
        public int TradeId { get; set; }
        public string Mode { get; set; }
        public string Underlying { get; set; }
        public string OptionSymbol { get; set; }
        public string Side { get; set; }
        public string OptionType { get; set; }
        public string Status { get; set; }
        public int Direction { get; set; }
        public double EntryFuturesPrice { get; set; }
        public double EntryOptionPrice { get; set; }
        public double StopLossPrice { get; set; }
        public bool StopLossHit { get; set; }
        public double RealizedPnl { get; set; }
        public int RemainingQty { get; set; }
        public double LiveOptionPrice { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime EntryTime { get; set; }
        public List<OpenBullTradeLevel> Targets { get; set; }

        public OpenBullTradeSnapshot()
        {
            Targets = new List<OpenBullTradeLevel>();
        }

        public double Mtm
        {
            get
            {
                if (!string.Equals(Status, "active", StringComparison.OrdinalIgnoreCase) || LiveOptionPrice <= 0 || EntryOptionPrice <= 0 || RemainingQty <= 0)
                    return RealizedPnl;
                double direction = string.Equals(Side, "BUY", StringComparison.OrdinalIgnoreCase) ? 1.0 : -1.0;
                return RealizedPnl + ((LiveOptionPrice - EntryOptionPrice) * RemainingQty * direction);
            }
        }
    }

    public static class OpenBullFuturesRiskBridge
    {
        private static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };

        public static string OpenBullUrl { get; private set; } = "http://127.0.0.1:8000";
        public static string ApiKey { get; private set; } = "";

        public static void Configure(string openBullUrl, string apiKey)
        {
            if (!string.IsNullOrWhiteSpace(openBullUrl))
                OpenBullUrl = openBullUrl.TrimEnd('/');
            ApiKey = apiKey ?? "";
        }

        public static async Task<string> UpdateLevelsAsync(int tradeId, double slPrice, IList<OpenBullLevelTarget> targets)
        {
            if (tradeId <= 0)
                return "Drawing is not linked to an OpenBull trade";
            if (string.IsNullOrWhiteSpace(ApiKey))
                return "OpenBull API key missing";

            string url = OpenBullUrl.TrimEnd('/') + "/api/v1/futures-risk/trades/" + tradeId.ToString(CultureInfo.InvariantCulture) + "/levels";
            string json = BuildLevelsJson(slPrice, targets);
            using (HttpRequestMessage request = new HttpRequestMessage(HttpMethod.Put, url))
            using (StringContent content = new StringContent(json, Encoding.UTF8, "application/json"))
            {
                request.Headers.TryAddWithoutValidation("X-API-KEY", ApiKey);
                request.Content = content;
                HttpResponseMessage response = await Http.SendAsync(request);
                string body = await response.Content.ReadAsStringAsync();
                if (response.IsSuccessStatusCode && body.IndexOf("\"status\":\"success\"", StringComparison.OrdinalIgnoreCase) >= 0)
                    return "Levels synced";
                return TrimForStatus(body);
            }
        }

        public static async Task<string> CloseTradeAsync(int tradeId, string mode, int qty)
        {
            if (tradeId <= 0)
                return "No linked OpenBull trade to close";
            if (string.IsNullOrWhiteSpace(ApiKey))
                return "OpenBull API key missing";

            string normalizedMode = string.IsNullOrWhiteSpace(mode) ? "full" : mode.Trim().ToLowerInvariant();
            if (normalizedMode != "full" && normalizedMode != "partial" && normalizedMode != "emergency")
                normalizedMode = "full";

            string url = OpenBullUrl.TrimEnd('/') + "/api/v1/futures-risk/trades/" + tradeId.ToString(CultureInfo.InvariantCulture) + "/exit";
            StringBuilder sb = new StringBuilder();
            sb.Append("{");
            JsonString(sb, "apikey", ApiKey, true);
            JsonString(sb, "mode", normalizedMode, false);
            if (normalizedMode == "partial")
                JsonNumber(sb, "qty", Math.Max(1, qty), false);
            sb.Append("}");

            using (HttpRequestMessage request = new HttpRequestMessage(HttpMethod.Post, url))
            using (StringContent content = new StringContent(sb.ToString(), Encoding.UTF8, "application/json"))
            {
                request.Headers.TryAddWithoutValidation("X-API-KEY", ApiKey);
                request.Content = content;
                HttpResponseMessage response = await Http.SendAsync(request);
                string body = await response.Content.ReadAsStringAsync();
                if (response.IsSuccessStatusCode && body.IndexOf("\"status\":\"success\"", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    string message = ExtractJsonValue(body, "message");
                    return string.IsNullOrWhiteSpace(message) || message == "null" ? "Exit placed" : message;
                }
                return "ERROR: " + TrimForStatus(body);
            }
        }

        public static async Task<OpenBullTradeSnapshot> FetchTradeAsync(int tradeId, string mode = null)
        {
            if (tradeId <= 0 || string.IsNullOrWhiteSpace(ApiKey))
                return null;

            string url = OpenBullUrl.TrimEnd('/') + "/api/v1/futures-risk/trades/" + tradeId.ToString(CultureInfo.InvariantCulture);
            string normalizedMode = NormalizeMode(mode);
            if (!string.IsNullOrWhiteSpace(normalizedMode))
                url += "?mode=" + Uri.EscapeDataString(normalizedMode);
            using (HttpRequestMessage request = new HttpRequestMessage(HttpMethod.Get, url))
            {
                request.Headers.TryAddWithoutValidation("X-API-KEY", ApiKey);
                HttpResponseMessage response = await Http.SendAsync(request);
                string body = await response.Content.ReadAsStringAsync();
                if (!response.IsSuccessStatusCode || body.IndexOf("\"status\":\"success\"", StringComparison.OrdinalIgnoreCase) < 0)
                    return null;
                return ParseTradeSnapshot(body);
            }
        }

        public static async Task<List<OpenBullTradeSnapshot>> FetchTradesAsync(string underlying, string mode = null)
        {
            List<OpenBullTradeSnapshot> trades = new List<OpenBullTradeSnapshot>();
            if (string.IsNullOrWhiteSpace(ApiKey))
                return trades;

            string url = OpenBullUrl.TrimEnd('/') + "/api/v1/futures-risk/trades?status=all&current_session=true";
            string normalizedMode = NormalizeMode(mode);
            if (!string.IsNullOrWhiteSpace(normalizedMode))
                url += "&mode=" + Uri.EscapeDataString(normalizedMode);
            if (!string.IsNullOrWhiteSpace(underlying))
                url += "&underlying=" + Uri.EscapeDataString(underlying.Trim().ToUpperInvariant());
            using (HttpRequestMessage request = new HttpRequestMessage(HttpMethod.Get, url))
            {
                request.Headers.TryAddWithoutValidation("X-API-KEY", ApiKey);
                HttpResponseMessage response = await Http.SendAsync(request);
                string body = await response.Content.ReadAsStringAsync();
                if (!response.IsSuccessStatusCode || body.IndexOf("\"status\":\"success\"", StringComparison.OrdinalIgnoreCase) < 0)
                    return trades;
                string array = ExtractArray(body, "data");
                if (string.IsNullOrWhiteSpace(array))
                    return trades;
                foreach (string obj in SplitObjects(array))
                {
                    OpenBullTradeSnapshot trade = ParseTradeSnapshot(obj);
                    if (trade != null && trade.TradeId > 0)
                        trades.Add(trade);
                }
            }
            return trades;
        }

        public static OpenBullTradeSnapshot ParseTradeSnapshot(string body)
        {
            if (string.IsNullOrWhiteSpace(body))
                return null;
            string data = ExtractObject(body, "data");
            if (string.IsNullOrWhiteSpace(data))
                data = body;
            OpenBullTradeSnapshot trade = new OpenBullTradeSnapshot();
            trade.TradeId = (int)ExtractNumber(data, "id");
            trade.Mode = ExtractJsonValue(data, "mode");
            trade.Underlying = ExtractJsonValue(data, "underlying");
            trade.OptionSymbol = ExtractJsonValue(data, "option_symbol");
            trade.Side = ExtractJsonValue(data, "side");
            trade.OptionType = ExtractJsonValue(data, "option_type");
            trade.Status = ExtractJsonValue(data, "status");
            trade.Direction = (int)ExtractNumber(data, "direction");
            trade.EntryFuturesPrice = ExtractNumber(data, "entry_futures_price");
            trade.EntryOptionPrice = ExtractNumber(data, "entry_option_price");
            trade.LiveOptionPrice = ExtractNumber(data, "live_option_price");
            trade.StopLossPrice = ExtractNumber(data, "sl_price");
            trade.StopLossHit = ExtractBool(data, "sl_hit")
                || data.IndexOf("\"kind\":\"sl_hit\"", StringComparison.OrdinalIgnoreCase) >= 0
                || data.IndexOf("\"kind\": \"sl_hit\"", StringComparison.OrdinalIgnoreCase) >= 0;
            trade.RealizedPnl = ExtractNumber(data, "realized_pnl");
            trade.RemainingQty = (int)ExtractNumber(data, "remaining_qty");
            trade.CreatedAt = ExtractDateTime(data, "created_at");
            trade.EntryTime = ExtractDateTime(data, "entry_time");
            if (trade.EntryTime == DateTime.MinValue)
                trade.EntryTime = ExtractDateTime(data, "created_at_utc");
            if (trade.EntryTime == DateTime.MinValue)
                trade.EntryTime = trade.CreatedAt;
            trade.Targets = ExtractTargets(data);
            if (trade.TradeId <= 0)
                return null;
            return trade;
        }

        private static string NormalizeMode(string mode)
        {
            if (string.IsNullOrWhiteSpace(mode))
                return null;
            string value = mode.Trim().ToLowerInvariant();
            if (value == "live" || value == "sandbox")
                return value;
            return null;
        }

        private static string BuildLevelsJson(double slPrice, IList<OpenBullLevelTarget> targets)
        {
            StringBuilder sb = new StringBuilder();
            sb.Append("{");
            JsonString(sb, "apikey", ApiKey, true);
            if (slPrice > 0)
                JsonNumber(sb, "sl_price", slPrice, false);
            sb.Append(",\"targets\":[");
            bool firstTarget = true;
            if (targets != null)
            {
                foreach (OpenBullLevelTarget target in targets)
                {
                    if (target == null || target.Price <= 0)
                        continue;
                    if (!firstTarget)
                        sb.Append(",");
                    firstTarget = false;
                    sb.Append("{");
                    JsonNumber(sb, "seq", target.Seq, true);
                    JsonNumber(sb, "price", target.Price, false);
                    if (target.ExitPct.HasValue && target.ExitPct.Value > 0)
                        JsonNumber(sb, "exit_pct", target.ExitPct.Value, false);
                    sb.Append("}");
                }
            }
            sb.Append("]}");
            return sb.ToString();
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

        private static string Escape(string value)
        {
            return (value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");
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
            return value.Length > 90 ? value.Substring(0, 90) + "..." : value;
        }

        private static double ExtractNumber(string body, string key)
        {
            double parsed;
            string raw = ExtractJsonValue(body, key);
            return double.TryParse(raw, NumberStyles.Any, CultureInfo.InvariantCulture, out parsed) ? parsed : 0;
        }

        private static bool ExtractBool(string body, string key)
        {
            Match m = Regex.Match(
                body,
                "\"" + Regex.Escape(key) + "\"\\s*:\\s*(?<bool>true|false)",
                RegexOptions.IgnoreCase
            );
            return m.Success && string.Equals(m.Groups["bool"].Value, "true", StringComparison.OrdinalIgnoreCase);
        }

        private static DateTime ExtractDateTime(string body, string key)
        {
            string raw = ExtractJsonValue(body, key);
            if (string.IsNullOrWhiteSpace(raw) || raw == "null")
                return DateTime.MinValue;
            DateTimeOffset parsedOffset;
            if (DateTimeOffset.TryParse(raw, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out parsedOffset))
                return parsedOffset.ToLocalTime().DateTime;
            DateTime parsed;
            if (DateTime.TryParse(raw, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out parsed))
                return parsed.ToLocalTime();
            return DateTime.MinValue;
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
                return m.Groups["str"].Value.Replace("\\\"", "\"").Replace("\\\\", "\\");
            if (m.Groups["num"].Success)
                return m.Groups["num"].Value;
            return "null";
        }

        private static List<OpenBullTradeLevel> ExtractTargets(string body)
        {
            List<OpenBullTradeLevel> targets = new List<OpenBullTradeLevel>();
            string array = ExtractArray(body, "targets");
            if (string.IsNullOrWhiteSpace(array))
                return targets;
            foreach (Match m in Regex.Matches(array, "\\{(?<obj>.*?)\\}", RegexOptions.Singleline))
            {
                string obj = m.Groups["obj"].Value;
                int seq = (int)ExtractNumber(obj, "seq");
                double price = ExtractNumber(obj, "trigger_price");
                if (seq <= 0 || price <= 0)
                    continue;
                string status = ExtractJsonValue(obj, "status");
                if (string.IsNullOrWhiteSpace(status) || status == "null")
                    status = "pending";
                targets.Add(new OpenBullTradeLevel
                {
                    Seq = seq,
                    Price = price,
                    Points = ExtractNumber(obj, "points"),
                    ExitPct = ExtractNumber(obj, "exit_pct"),
                    Status = status
                });
            }
            return targets;
        }

        private static string ExtractArray(string body, string key)
        {
            int keyIndex = body.IndexOf("\"" + key + "\"", StringComparison.OrdinalIgnoreCase);
            if (keyIndex < 0)
                return "";
            int start = body.IndexOf('[', keyIndex);
            if (start < 0)
                return "";
            int depth = 0;
            for (int i = start; i < body.Length; i++)
            {
                if (body[i] == '[')
                    depth++;
                else if (body[i] == ']')
                {
                    depth--;
                    if (depth == 0)
                        return body.Substring(start + 1, i - start - 1);
                }
            }
            return "";
        }

        private static List<string> SplitObjects(string arrayBody)
        {
            List<string> objects = new List<string>();
            if (string.IsNullOrWhiteSpace(arrayBody))
                return objects;
            int depth = 0;
            int start = -1;
            for (int i = 0; i < arrayBody.Length; i++)
            {
                char c = arrayBody[i];
                if (c == '{')
                {
                    if (depth == 0)
                        start = i;
                    depth++;
                }
                else if (c == '}')
                {
                    depth--;
                    if (depth == 0 && start >= 0)
                    {
                        objects.Add(arrayBody.Substring(start + 1, i - start - 1));
                        start = -1;
                    }
                }
            }
            return objects;
        }

        private static string ExtractObject(string body, string key)
        {
            int keyIndex = body.IndexOf("\"" + key + "\"", StringComparison.OrdinalIgnoreCase);
            if (keyIndex < 0)
                return "";
            int start = body.IndexOf('{', keyIndex);
            if (start < 0)
                return "";
            int depth = 0;
            for (int i = start; i < body.Length; i++)
            {
                if (body[i] == '{')
                    depth++;
                else if (body[i] == '}')
                {
                    depth--;
                    if (depth == 0)
                        return body.Substring(start + 1, i - start - 1);
                }
            }
            return "";
        }
    }
}
