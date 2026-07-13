$ErrorActionPreference = 'Stop'

# Enables only NinjaTrader's local ATI/DLL listener required by the official
# External Data Feed bridge. It does not submit orders, create a connection,
# or alter any NinjaScript/Quick Order file.

$ntProcess = Get-Process -Name NinjaTrader -ErrorAction SilentlyContinue
if ($ntProcess) {
    throw 'Close NinjaTrader before enabling the ATI/DLL listener, then run this script again.'
}

$ninjaHome = Join-Path $env:USERPROFILE 'Documents\NinjaTrader 8'
$configPath = Join-Path $ninjaHome 'Config.xml'
if (!(Test-Path -LiteralPath $configPath)) { throw "NinjaTrader configuration not found: $configPath" }

$backupPath = Join-Path $ninjaHome ('Config.before-openbull-external-feed-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.xml')
Copy-Item -LiteralPath $configPath -Destination $backupPath -Force

[xml]$config = Get-Content -LiteralPath $configPath
$ati = $config.NinjaTrader.AtiOptions.AtiOptions
if ($null -eq $ati) { throw 'NinjaTrader ATI configuration was not found; no change was made.' }
$ati.IsAtiEnabled = 'true'
if ([int]$ati.ServerPort -le 0) { $ati.ServerPort = '36973' }
$config.Save($configPath)

Write-Host "Enabled NinjaTrader ATI/DLL listener on port $($ati.ServerPort)."
Write-Host "Backup created: $backupPath"
Write-Host 'Start NinjaTrader, then connect Connections > External Data Feed.'
