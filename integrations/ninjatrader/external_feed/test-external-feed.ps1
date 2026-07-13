$ErrorActionPreference = 'Stop'

# Offline contract test for the supported NinjaTrader historical import path.
# It proves that the bridge converts an OpenBull /history response into the
# exact one-minute, end-of-bar NinjaTrader Last import format. No Dhan or
# NinjaTrader connection is required.

$here = $PSScriptRoot
& (Join-Path $here 'build-external-feed.ps1')

$port = 18890
$output = Join-Path $env:TEMP 'OpenBullExternalFeedBridge.test.Last.txt'
Remove-Item -LiteralPath $output -Force -ErrorAction SilentlyContinue
$json = '{"status":"success","data":[{"timestamp":1783914300,"open":7000,"high":7010,"low":6995,"close":7008,"volume":42}]}'

$server = Start-Job -ScriptBlock {
    param($listenerPort, $body)
    $listener = [System.Net.HttpListener]::new()
    $listener.Prefixes.Add("http://127.0.0.1:$listenerPort/")
    $listener.Start()
    try {
        $context = $listener.GetContext()
        $bytes = [Text.Encoding]::UTF8.GetBytes($body)
        $context.Response.StatusCode = 200
        $context.Response.ContentType = 'application/json'
        $context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
        $context.Response.Close()
    }
    finally {
        $listener.Stop()
        $listener.Close()
    }
} -ArgumentList $port, $json

try {
    Start-Sleep -Milliseconds 250
    & (Join-Path $here 'bin\OpenBullExternalDataFeedBridge.exe') `
        --api-key test --nt-instrument CRUDEOIL20JUL26FUT `
        --symbol CRUDEOIL20JUL26FUT --exchange MCX `
        --from 2026-07-13 --to 2026-07-13 `
        --openbull-url "http://127.0.0.1:$port" --output $output --export-only
    if ($LASTEXITCODE -ne 0) { throw 'Bridge export command failed.' }

    $actual = Get-Content -LiteralPath $output -Raw
    $expected = "20260713 091600;7000;7010;6995;7008;42`r`n"
    if ($actual -ne $expected) { throw "Unexpected output: $actual" }
    Write-Host 'OpenBull External Data Feed bridge test passed.'
}
finally {
    if ($server) { Receive-Job $server -Wait -AutoRemoveJob -ErrorAction SilentlyContinue | Out-Null }
    Remove-Item -LiteralPath $output -Force -ErrorAction SilentlyContinue
}
