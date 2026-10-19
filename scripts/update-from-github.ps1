[CmdletBinding()]
param([switch]$Update, [switch]$CheckOnly, [string]$Version, [string]$Destination)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$repository = 'William0702/role-showcase-remix'
$headers = @{ 'User-Agent' = 'role-showcase-remix-installer'; 'Accept' = 'application/vnd.github+json' }
if (-not $Destination) {
    $codexDirectory = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
    $Destination = Join-Path $codexDirectory 'skills\role-showcase-remix'
}
$Destination = [IO.Path]::GetFullPath($Destination)
if ($Version -and $Version -notmatch '^v?\d+\.\d+\.\d+$') { throw 'Version must have the form 1.7.1 or v1.7.1.' }
$releaseEndpoint = if ($Version) { 'tags/v' + $Version.TrimStart('v') } else { 'latest' }
$release = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repository/releases/$releaseEndpoint"
$tag = [string]$release.tag_name
if ($tag -notmatch '^v\d+\.\d+\.\d+$' -or $release.draft -or $release.prerelease) { throw 'A published stable release is required.' }
$installedVersion = $null
$oldManifest = Join-Path $Destination 'package-manifest.json'
if (Test-Path -LiteralPath $oldManifest) { $installedVersion = (Get-Content -LiteralPath $oldManifest -Raw -Encoding UTF8 | ConvertFrom-Json).version }
Write-Output "Installed: $installedVersion; selected stable release: $tag; destination: $Destination"
if ($CheckOnly) { return }
if ((Test-Path -LiteralPath $Destination) -and -not $Update) { throw 'Destination exists. Run with -Update to verify, back up and upgrade the existing skill.' }
$archiveName = "role-showcase-remix-$tag-windows-x64.zip"
$archiveAsset = @($release.assets | Where-Object { $_.name -eq $archiveName })
$checksumAsset = @($release.assets | Where-Object { $_.name -eq 'SHA256SUMS.txt' })
if ($archiveAsset.Count -ne 1 -or $checksumAsset.Count -ne 1) { throw 'Release archive/checksum asset missing or ambiguous.' }
$releasePrefix = "https://github.com/$repository/releases/download/$tag/"
foreach ($asset in @($archiveAsset[0], $checksumAsset[0])) {
    if (-not ([string]$asset.browser_download_url).StartsWith($releasePrefix,[StringComparison]::Ordinal)) { throw 'Unexpected release asset origin.' }
}
$workDirectory = Join-Path ([IO.Path]::GetTempPath()) ('role-showcase-remix-update-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $workDirectory | Out-Null
$archivePath = Join-Path $workDirectory $archiveName
$checksumPath = Join-Path $workDirectory 'SHA256SUMS.txt'
Write-Output "Downloading $tag ..."
Invoke-WebRequest -UseBasicParsing -Headers $headers -Uri $checksumAsset[0].browser_download_url -OutFile $checksumPath -TimeoutSec 240
Invoke-WebRequest -UseBasicParsing -Headers $headers -Uri $archiveAsset[0].browser_download_url -OutFile $archivePath -TimeoutSec 600
$expectedHash = $null
foreach ($line in (Get-Content -LiteralPath $checksumPath -Encoding UTF8)) {
    if ($line -match '^([a-fA-F0-9]{64})\s+\*?(.+)$' -and $Matches[2] -eq $archiveName) { $expectedHash = $Matches[1].ToLowerInvariant() }
}
if (-not $expectedHash -or (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) { throw 'Release archive SHA256 verification failed; nothing installed.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($archivePath)
try {
    foreach ($entry in $zip.Entries) {
        $entryName = $entry.FullName.Replace('\','/')
        if (-not $entryName.StartsWith('role-showcase-remix/',[StringComparison]::Ordinal) -or $entryName -match '(^|/)\.\.(/|$)|:' -or $entryName.StartsWith('/')) { throw 'Unsafe archive path.' }
    }
} finally { $zip.Dispose() }
$extractDirectory = Join-Path $workDirectory 'extract'
Expand-Archive -LiteralPath $archivePath -DestinationPath $extractDirectory
$sourceDirectory = Join-Path $extractDirectory 'role-showcase-remix'
$manifest = Get-Content -LiteralPath (Join-Path $sourceDirectory 'package-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ('v' + $manifest.version -ne $tag -or $manifest.name -ne 'role-showcase-remix') { throw 'Manifest version/name differs from the selected release.' }
$sourcePrefix = [IO.Path]::GetFullPath($sourceDirectory).TrimEnd('\') + '\'
foreach ($file in $manifest.files) {
    $targetFile = [IO.Path]::GetFullPath((Join-Path $sourceDirectory $file.path))
    if (-not $targetFile.StartsWith($sourcePrefix,[StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $targetFile -PathType Leaf)) { throw 'Invalid manifest path.' }
    if ((Get-FileHash -LiteralPath $targetFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) { throw ('Package file mismatch: ' + $file.path) }
}
$runtime = Join-Path $sourceDirectory 'tools\windows-x64\python\python.exe'
$installer = Join-Path $sourceDirectory 'scripts\install_offline.py'
$installerArguments = @('-X','utf8',$installer,'--dest',$Destination)
if ($Update) { $installerArguments += '--upgrade' }
& $runtime @installerArguments
if ($LASTEXITCODE -ne 0) { throw "Skill installer failed with code $LASTEXITCODE. Cache preserved at $workDirectory" }
$actualVersion = (Get-Content -LiteralPath (Join-Path $Destination 'package-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json).version
if ($actualVersion -ne $manifest.version) { throw 'Installed version verification failed.' }
Write-Output "Ready: $actualVersion. Cached verified package: $workDirectory"
Write-Output 'Start a new Codex turn to use the updated skill. Use update.cmd for the next update.'
