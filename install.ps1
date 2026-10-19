param([string]$Destination, [switch]$Upgrade)
$ErrorActionPreference = 'Stop'
$taskPython = Join-Path $PSScriptRoot 'tools\windows-x64\python\python.exe'
$taskInstaller = Join-Path $PSScriptRoot 'scripts\install_offline.py'
$taskArguments = @($taskInstaller)
if ($Destination) { $taskArguments += @('--dest', $Destination) }
if ($Upgrade) { $taskArguments += @("--upgrade") }
& $taskPython @taskArguments
exit $LASTEXITCODE
