$ErrorActionPreference = "Stop"

$source = Join-Path $PSScriptRoot "OpenBullQuickOrderIndicator.cs"
if (-not (Test-Path -LiteralPath $source)) {
    throw "Missing Quick Order indicator source: $source"
}

$indicatorSource = Get-Content -LiteralPath $source -Raw
$classMarker = "public static class OpenBullQuickOrderSymbolMapper"
$classStart = $indicatorSource.IndexOf($classMarker, [StringComparison]::Ordinal)
if ($classStart -lt 0) {
    throw "Quick Order symbol mapper must be embedded in OpenBullQuickOrderIndicator.cs"
}

$openBrace = $indicatorSource.IndexOf('{', $classStart)
if ($openBrace -lt 0) {
    throw "Could not find the opening brace of the embedded symbol mapper"
}

$depth = 0
$classEnd = -1
for ($index = $openBrace; $index -lt $indicatorSource.Length; $index++) {
    if ($indicatorSource[$index] -eq '{') { $depth++ }
    elseif ($indicatorSource[$index] -eq '}') {
        $depth--
        if ($depth -eq 0) {
            $classEnd = $index
            break
        }
    }
}
if ($classEnd -lt 0) {
    throw "Could not find the closing brace of the embedded symbol mapper"
}

$mapperSource = $indicatorSource.Substring($classStart, $classEnd - $classStart + 1)
$testSource = @"
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;

namespace NinjaTrader.NinjaScript.Indicators
{
$mapperSource
}
"@
Add-Type -TypeDefinition $testSource

$configured = [string[]]@(
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "NATURALGAS"
)

$cases = @(
    @{ Master = "NIFTY"; Full = "NIFTY"; Want = "NIFTY"; Exchange = "NSE_INDEX" },
    @{ Master = "BANKNIFTY_I"; Full = "BANKNIFTY_I"; Want = "BANKNIFTY"; Exchange = "NSE_INDEX" },
    @{ Master = "CRUDEOIL20JUL26FUT"; Full = "MCX:CRUDEOIL20JUL26FUT"; Want = "CRUDEOIL"; Exchange = "MCX" },
    @{ Master = "BANKNIFTY28JUL2655900CE"; Full = "NFO:BANKNIFTY28JUL2655900CE"; Want = "BANKNIFTY"; Exchange = "NSE_INDEX" },
    @{ Master = "SENSEX"; Full = "SENSEX"; Want = "SENSEX"; Exchange = "BSE_INDEX" }
)

foreach ($case in $cases) {
    $actual = [NinjaTrader.NinjaScript.Indicators.OpenBullQuickOrderSymbolMapper]::InferUnderlying(
        $case.Master,
        $case.Full,
        $configured
    )
    if ($actual -ne $case.Want) {
        throw "Expected '$($case.Want)' for '$($case.Master)'/'$($case.Full)', got '$actual'"
    }
    $exchange = [NinjaTrader.NinjaScript.Indicators.OpenBullQuickOrderSymbolMapper]::InferExchange($actual)
    if ($exchange -ne $case.Exchange) {
        throw "Expected exchange '$($case.Exchange)' for '$actual', got '$exchange'"
    }
}

$nifty = [NinjaTrader.NinjaScript.Indicators.OpenBullQuickOrderSymbolMapper]::InferUnderlying("NIFTY", "NIFTY", $configured)
$bankNifty = [NinjaTrader.NinjaScript.Indicators.OpenBullQuickOrderSymbolMapper]::InferUnderlying("BANKNIFTY_I", "BANKNIFTY_I", $configured)
if ($nifty -eq $bankNifty) {
    throw "Separate NIFTY and BANKNIFTY charts collapsed to '$nifty'"
}

Write-Host "OpenBull Quick Order symbol mapping tests passed ($($cases.Count) cases)."
