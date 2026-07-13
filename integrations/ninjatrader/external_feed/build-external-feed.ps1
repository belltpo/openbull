$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$ntBin = 'C:\Program Files\NinjaTrader 8\bin'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$outputDir = Join-Path $PSScriptRoot 'bin'
$output = Join-Path $outputDir 'OpenBullExternalDataFeedBridge.exe'

if (!(Test-Path $compiler)) { throw "C# compiler not found: $compiler" }
if (!(Test-Path (Join-Path $ntBin 'NinjaTrader.Client.dll'))) { throw "NinjaTrader Client DLL not found: $ntBin" }

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
& $compiler /nologo /target:exe "/out:$output" `
    "/r:$ntBin\NinjaTrader.Client.dll" `
    /r:System.Net.Http.dll /r:System.Web.Extensions.dll `
    (Join-Path $repoRoot 'integrations\ninjatrader\external_feed\OpenBullExternalDataFeedBridge.cs')
if ($LASTEXITCODE -ne 0) { throw 'External Data Feed bridge compilation failed.' }

Copy-Item -LiteralPath (Join-Path $ntBin 'NinjaTrader.Client.dll') `
    -Destination (Join-Path $outputDir 'NinjaTrader.Client.dll') -Force

Write-Host "Built $output"
