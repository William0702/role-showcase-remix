param([string]$Directory = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
$info = Get-Content -LiteralPath (Join-Path $Directory 'release-parts.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($info.archive_name -notmatch '^role-showcase-remix-v\d+\.\d+\.\d+-windows-x64\.zip$') { throw 'Invalid archive name' }
$path = Join-Path $Directory $info.archive_name
if (Test-Path -LiteralPath $path) { throw 'Output exists; preserved.' }
$out = [IO.File]::Create($path)
try {
 foreach ($part in $info.parts) {
  if ($part.name -notmatch ('^'+[regex]::Escape($info.archive_name)+'\.\d{3}$')) { throw 'Invalid part name' }
  $file = Join-Path $Directory $part.name
  if ((Get-Item -LiteralPath $file).Length -ne $part.size -or (Get-FileHash -LiteralPath $file).Hash.ToLowerInvariant() -ne $part.sha256) { throw ('Part mismatch: '+$part.name) }
  $inputFile = [IO.File]::OpenRead($file)
  try { $inputFile.CopyTo($out) } finally { $inputFile.Dispose() }
 }
} finally { $out.Dispose() }
if ((Get-Item -LiteralPath $path).Length -ne $info.archive_size -or (Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ne $info.archive_sha256) { throw 'Archive mismatch; do not install' }
Write-Output ('Verified offline archive: '+$path)
