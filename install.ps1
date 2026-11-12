param(
    [ValidateSet("client", "server")][string]$Side = "server",
    [ValidateSet("full", "strict")][string]$Profile = "full",
    [string]$Dir = ".",
    [switch]$DryRun,
    [switch]$ForceConfig
)

$ErrorActionPreference = "Stop"
$argsList = @("--side", $Side, "--profile", $Profile, "--dir", $Dir)
if ($DryRun) { $argsList += "--dry-run" }
if ($ForceConfig) { $argsList += "--force-config" }

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python 3 is required. Install it from https://www.python.org/downloads/" }

& $python.Source (Join-Path $PSScriptRoot "install.py") @argsList
exit $LASTEXITCODE
