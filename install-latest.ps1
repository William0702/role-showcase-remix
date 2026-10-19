[CmdletBinding()]
param([switch]$Update,[switch]$CheckOnly,[string]$Version,[string]$Destination)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'scripts\update-from-github.ps1') @PSBoundParameters
