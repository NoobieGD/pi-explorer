param([Parameter(Mandatory=$true)][string]$Zig)
$ErrorActionPreference='Stop'
$project=Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Path "$project\native" -Force | Out-Null
& $Zig cc -O3 -DNDEBUG -shared -target x86_64-windows-gnu "$project\native\scan.c" -o "$project\native\pi_scan.dll" '-Wl,--strip-all'
if($LASTEXITCODE -ne 0){throw 'Native scanner build failed'}
Get-Item -LiteralPath "$project\native\pi_scan.dll" | Select-Object FullName,Length
