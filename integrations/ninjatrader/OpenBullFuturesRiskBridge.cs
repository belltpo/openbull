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
            using (StringContent content = new StringContent(json, Encoding.UTF8, "application/json"))
            {
                HttpResponseMessage response = await Http.PutAsync(url, content);
                string body = await response.Content.ReadAsStringAsync();
                if (response.IsSuccessStatusCode && body.IndexOf("\"status\":\"success\"", StringComparison.OrdinalIgnoreCase) >= 0)
                    return "Levels synced";
                return TrimForStatus(body);
            }
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
    }
}
