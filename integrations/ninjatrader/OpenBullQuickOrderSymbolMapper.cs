// Pure symbol mapping used by OpenBullQuickOrderIndicator.
// Keep this file beside the indicator in NinjaTrader's Custom\Indicators folder.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;

namespace NinjaTrader.NinjaScript.Indicators
{
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
            if (configuredUnderlyings != null)
                candidates.AddRange(configuredUnderlyings);
            candidates.AddRange(KnownUnderlyings);
            candidates = candidates
                .Select(NormalizeCandidate)
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderByDescending(value => value.Length)
                .ToList();

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
            // NinjaTrader full names may append a display expiry after a space.
            int space = result.IndexOf(' ');
            if (space > 0)
                result = result.Substring(0, space);
            return result.Trim();
        }
    }
}
