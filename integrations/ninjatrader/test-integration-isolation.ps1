$ErrorActionPreference = 'Stop'

$quickOrderPath = Join-Path $PSScriptRoot 'OpenBullQuickOrderIndicator.cs'
$liveDataPath = Join-Path $PSScriptRoot 'addons\OpenBullLiveDataAddOn.cs'
$externalFeedPath = Join-Path $PSScriptRoot 'external_feed\OpenBullExternalDataFeedBridge.cs'

foreach ($path in @($quickOrderPath, $liveDataPath, $externalFeedPath)) {
    if (!(Test-Path -LiteralPath $path)) {
        throw "Required NinjaTrader integration source is missing: $path"
    }
}

$quickOrder = Get-Content -LiteralPath $quickOrderPath -Raw
$liveData = Get-Content -LiteralPath $liveDataPath -Raw
$externalFeed = Get-Content -LiteralPath $externalFeedPath -Raw

function Assert-DoesNotContain {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string[]]$Patterns,
        [Parameter(Mandatory = $true)][string]$Owner
    )

    foreach ($pattern in $Patterns) {
        if ($Text.IndexOf($pattern, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            throw "$Owner must remain independent but references '$pattern'."
        }
    }
}

Assert-DoesNotContain -Text $quickOrder -Owner 'Quick Order' -Patterns @(
    'OpenBullLiveData',
    'OpenBullLiveTick',
    'OpenBullLiveCandles',
    'NinjaTrader.Client',
    '127.0.0.1:8765',
    'External Data Feed'
)

Assert-DoesNotContain -Text $liveData -Owner 'Live Data AddOn' -Patterns @(
    'OpenBullQuickOrderIndicator',
    '/api/v1/futures-risk/quick-order'
)

Assert-DoesNotContain -Text $externalFeed -Owner 'External Data Feed bridge' -Patterns @(
    'OpenBullQuickOrderIndicator',
    '/api/v1/futures-risk/quick-order'
)

if ($quickOrder.IndexOf('/api/v1/futures-risk/quick-order', [StringComparison]::OrdinalIgnoreCase) -lt 0) {
    throw 'Quick Order no longer contains its independent Futures-Risk HTTP endpoint.'
}
if ($quickOrder.IndexOf('http://127.0.0.1:8000', [StringComparison]::OrdinalIgnoreCase) -lt 0) {
    throw 'Quick Order no longer has its independent local OpenBull HTTP default.'
}

foreach ($required in @(
    'EXCHANGE:SYMBOL => NinjaTrader @INSTRUMENT_FULL',
    'ResolveInstrument(symbol.NinjaTraderInstrument)',
    'chartTickSink.SendLast(ninjaTraderInstrument, tick.Ltp)',
    'if (!(window is ControlCenter))'
)) {
    if ($liveData.IndexOf($required, [StringComparison]::Ordinal) -lt 0) {
        throw "Live Data AddOn safety contract is missing '$required'."
    }
}
if ($liveData.IndexOf('chartTickSink.SendLast(tick.Symbol', [StringComparison]::Ordinal) -ge 0) {
    throw 'Live Data AddOn must never pass a broker symbol directly to NinjaTrader.Client.Last().'
}

Write-Host 'NinjaTrader integration isolation test passed.'
Write-Host 'Quick Order: HTTP Futures-Risk API + chart symbol mapper only (port 8000).'
Write-Host 'Live Data: explicit broker-to-NinjaTrader full-instrument mapping; no Quick Order reference.'
