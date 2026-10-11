param([string]$Archive = (Join-Path $env:USERPROFILE 'Downloads\BMW-Data-20261010T183823Z-1-001.zip'))
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Assert-Command { if ($LASTEXITCODE -ne 0) { throw "Setup command failed with exit code $LASTEXITCODE." } }
if (!(Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    py -3.12 -m venv .venv
    Assert-Command
}
& ./.venv/Scripts/python.exe -m pip install -r requirements.txt
Assert-Command
pnpm install --frozen-lockfile
Assert-Command
& ./.venv/Scripts/python.exe -m backend.cli migrate
Assert-Command
if (!(Test-Path -LiteralPath $Archive)) { throw 'Pass -Archive with the supplied BMW ZIP path.' }
& ./.venv/Scripts/python.exe -m backend.cli import $Archive
Assert-Command
& ./.venv/Scripts/python.exe -m backend.cli openapi
Assert-Command
pnpm generate:types
Assert-Command
Write-Output 'Setup complete. Run pnpm dev, then open http://127.0.0.1:3000.'
