# Requires Windows PowerShell 5.1+ or PowerShell 7; no execution-policy changes.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$demoPython = Join-Path $repoRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $demoPython)) {
    throw 'Create the repository virtual environment and install .[dev] first.'
}
& $demoPython (Join-Path $PSScriptRoot 'demo.py') deploy
if ($LASTEXITCODE -ne 0) { throw 'Demo command failed. See STOP message; do not blindly retry apply.' }
