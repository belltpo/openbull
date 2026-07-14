$ErrorActionPreference = "Stop"

$source = Join-Path $PSScriptRoot "OpenBullQuickOrderSymbolMapper.cs"
if (-not (Test-Path -LiteralPath $source)) {
    throw "Missing mapper source: $source"
}

Add-Type -Path $source

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
