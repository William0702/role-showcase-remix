param([string]$Repository = (Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference = 'Stop'
$global:remixTestVersion = (Get-Content (Join-Path $Repository 'package-manifest.json') -Raw | ConvertFrom-Json).version
$global:remixTestfixtureArchive = Join-Path $Repository "dist/role-showcase-remix-v$global:remixTestVersion-windows-x64.zip"
$global:remixTestfixtureSums = Join-Path $Repository 'dist/SHA256SUMS.txt'
$global:remixTestdownloads = 0
$global:remixTestbadChecksum = $false
$prefix = "https://github.com/William0702/role-showcase-remix/releases/download/v$global:remixTestVersion/"
$global:remixTestfixtureRelease = [pscustomobject]@{ tag_name="v$global:remixTestVersion"; draft=$false; prerelease=$false; assets=@(
    [pscustomobject]@{name="role-showcase-remix-v$global:remixTestVersion-windows-x64.zip";browser_download_url=($prefix+"role-showcase-remix-v$global:remixTestVersion-windows-x64.zip")},
    [pscustomobject]@{name='SHA256SUMS.txt';browser_download_url=($prefix+'SHA256SUMS.txt')}
)}
function Invoke-RestMethod { param($Headers,$Uri) return $global:remixTestfixtureRelease }
function Invoke-WebRequest {
    param([switch]$UseBasicParsing,$Headers,$Uri,$OutFile,$TimeoutSec)
    $global:remixTestdownloads++
    if ($Uri.EndsWith('SHA256SUMS.txt')) {
        if ($global:remixTestbadChecksum) { ('0'*64 + "  role-showcase-remix-v$global:remixTestVersion-windows-x64.zip") | Set-Content -LiteralPath $OutFile -Encoding ASCII }
        else { Copy-Item -LiteralPath $global:remixTestfixtureSums -Destination $OutFile }
    } else { Copy-Item -LiteralPath $global:remixTestfixtureArchive -Destination $OutFile }
}
$runDirectory = Join-Path $Repository ('dist/acceptance-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runDirectory | Out-Null
$destination = Join-Path $runDirectory 'skills/role-showcase-remix'
$helper = Join-Path $Repository 'scripts/update-from-github.ps1'
& $helper -Destination $destination -CheckOnly | Out-File (Join-Path $runDirectory 'check.log') -Encoding utf8
if ($global:remixTestdownloads -ne 0 -or (Test-Path -LiteralPath $destination)) { throw 'CheckOnly changed the destination/downloaded archives' }
& $helper -Destination $destination | Out-File (Join-Path $runDirectory 'install.log') -Encoding utf8
if (-not (Test-Path -LiteralPath (Join-Path $destination 'tools/windows-x64/ffmpeg.exe'))) { throw 'Runtime missing after install' }
Write-Output 'PASS fresh installation and CheckOnly'
$beforeDownloads = $global:remixTestdownloads
try { & $helper -Destination $destination | Out-Null; throw 'GUARD_NOT_ENFORCED' } catch { if ($_.Exception.Message -notlike '*Destination exists*') { throw } }
if ($global:remixTestdownloads -ne $beforeDownloads) { throw 'Existing destination guard downloaded files' }
& $helper -Destination $destination -Update | Out-File (Join-Path $runDirectory 'upgrade.log') -Encoding utf8
$backups = Get-ChildItem -LiteralPath (Join-Path $runDirectory 'skill-backups') -Directory
if (-not $backups) { throw 'Upgrade did not create a backup' }
Write-Output 'PASS upgrade, backup and existing-destination protection'
$skill = Join-Path $destination 'SKILL.md'
Add-Content -LiteralPath $skill -Value 'Local modification fixture' -Encoding utf8
$modified = (Get-FileHash -LiteralPath $skill).Hash
try { & $helper -Destination $destination -Update | Out-File (Join-Path $runDirectory 'modified.log') -Encoding utf8; throw 'MODIFIED_GUARD_NOT_ENFORCED' } catch { if ($_.Exception.Message -notlike '*installer failed*') { throw } }
if ((Get-FileHash -LiteralPath $skill).Hash -ne $modified) { throw 'Local modification overwritten' }
Write-Output 'PASS locally modified skill preserved'
$global:remixTestbadChecksum = $true
$badDestination = Join-Path $runDirectory 'checksum-rejection'
try { & $helper -Destination $badDestination | Out-Null; throw 'CHECKSUM_GUARD_NOT_ENFORCED' } catch { if ($_.Exception.Message -notlike '*SHA256 verification failed*') { throw } }
if (Test-Path -LiteralPath $badDestination) { throw 'Bad checksum changed destination' }
Write-Output 'PASS corrupt archive checksum rejected before installation'
@{passed=$true;version=$global:remixTestVersion;scope='Mock public Release transport with actual archive extraction, offline installation, FilmCraft self-test and upgrade';directory=$runDirectory;tests=@('CheckOnly no mutation','fresh install','existing destination guarded','upgrade creates backup','local modifications preserved','checksum failure no install')} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Repository 'dist/update-acceptance.json') -Encoding UTF8
