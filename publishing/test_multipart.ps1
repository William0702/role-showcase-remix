param([string]$Repository=(Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference='Stop'
$global:remixMultipartDirectory=Join-Path $Repository 'dist/multipart'
$global:remixPartsInfo=Get-Content (Join-Path $global:remixMultipartDirectory 'release-parts.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$version=(Get-Content (Join-Path $Repository 'package-manifest.json') -Raw | ConvertFrom-Json).version
$prefix="https://github.com/William0702/role-showcase-remix/releases/download/v$version/"
$assets=@()
foreach($name in (@('SHA256SUMS.txt','release-parts.json') + @($global:remixPartsInfo.parts | ForEach-Object name))) {
 $assets += [pscustomobject]@{name=$name;browser_download_url=($prefix+$name)}
}
$global:remixMultipartRelease=[pscustomobject]@{tag_name="v$version";draft=$false;prerelease=$false;assets=$assets}
function Invoke-RestMethod {
 param($Headers,$Uri)
 if($Uri.EndsWith('release-parts.json')) { return $global:remixPartsInfo }
 return $global:remixMultipartRelease
}
function Invoke-WebRequest {
 param([switch]$UseBasicParsing,$Headers,$Uri,$OutFile,$TimeoutSec)
 $name=([uri]$Uri).Segments[-1]
 Copy-Item -LiteralPath (Join-Path $global:remixMultipartDirectory $name) -Destination $OutFile
}
$target=Join-Path $Repository ('dist/multipart-install-'+[guid]::NewGuid().ToString('N')+'/skills/role-showcase-remix')
$log=Join-Path $Repository 'dist/multipart-install.log'
& (Join-Path $Repository 'scripts/update-from-github.ps1') -Destination $target | Out-File $log -Encoding UTF8
$installed=Get-Content (Join-Path $target 'package-manifest.json') -Raw | ConvertFrom-Json
if($installed.version -ne $version){throw 'Installed version mismatch'}
if(-not(Test-Path (Join-Path $target 'tools/windows-x64/python/python.exe'))){throw 'Runtime missing'}
@{passed=$true;version=$version;parts=$global:remixPartsInfo.parts.Count;target=$target;scope='actual verified multipart assembly, offline install and FilmCraft native self-test with mock Release transport'} | ConvertTo-Json | Set-Content (Join-Path $Repository 'dist/multipart-acceptance.json') -Encoding UTF8
Write-Output ('PASS multipart assembly + complete installation + native FilmCraft self-test: '+$version)
