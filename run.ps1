$runtime = Join-Path $PSScriptRoot 'tools\windows-x64\python\python.exe'
$entry = Join-Path $PSScriptRoot 'scripts\remix.py'
& $runtime $entry @args
exit $LASTEXITCODE
