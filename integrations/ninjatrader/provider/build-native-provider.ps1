$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$ninjaRoot = Join-Path $env:USERPROFILE 'Documents\NinjaTrader 8'
$ninjaBin = 'C:\Program Files\NinjaTrader 8\bin'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$output = Join-Path $ninjaRoot 'bin\Custom\OpenBull.NativeProvider.dll'
$configPath = Join-Path $ninjaRoot 'Config.xml'

if (!(Test-Path $compiler)) { throw "C# compiler not found: $compiler" }
if (!(Test-Path (Join-Path $ninjaBin 'NinjaTrader.Core.dll'))) { throw "NinjaTrader 8 was not found at $ninjaBin" }

& $compiler /nologo /target:library "/out:$output" "/r:$ninjaBin\NinjaTrader.Core.dll" /r:System.ComponentModel.DataAnnotations.dll `
    (Join-Path $repoRoot 'integrations\ninjatrader\provider\OpenBullDataProvider.cs') `
    (Join-Path $repoRoot 'integrations\ninjatrader\addons\OpenBullLiveDataClient.cs')
if ($LASTEXITCODE -ne 0) { throw 'OpenBull native-provider compilation failed.' }

if (!(Test-Path $configPath)) { throw "NinjaTrader configuration not found: $configPath" }
[xml]$config = Get-Content -LiteralPath $configPath
if ($null -eq $config.NinjaTrader.ConnectOptions.OpenBullConnectOptions) {
    $connection = $config.CreateElement('OpenBullConnectOptions')
    @{
        CanManageOrders = 'false'
        ConnectOnStartup = 'false'
        DisableL2Data = 'false'
        IsHdsEnabled = 'false'
        IsPasswordRequiredOnStartup = 'true'
        RunAsProcess = 'false'
        TypeName = 'OpenBull.NinjaTrader.OpenBullConnectOptions'
        Mode = 'Live'
        Name = 'OpenBull'
        Password = ''
        Provider = 'Custom40'
        User = ''
        StreamUrl = 'ws://127.0.0.1:8765'
        SymbolMappings = ''
    }.GetEnumerator() | ForEach-Object {
        $node = $config.CreateElement($_.Key)
        $node.InnerText = $_.Value
        [void]$connection.AppendChild($node)
    }
    [void]$config.NinjaTrader.ConnectOptions.AppendChild($connection)
    $config.Save($configPath)
    Write-Host "Registered the OpenBull connection in $configPath"
}

Write-Host "Built $output"
