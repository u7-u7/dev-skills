[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('install', 'preview', 'uninstall')]
    [string]$Action = 'install',

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$Profile = 'diy',

    [switch]$Force
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$installer = Join-Path (Join-Path $PSScriptRoot 'scripts') 'install_team_bundle.ps1'
$parameters = @{ Profile = $Profile }
if ($Action -eq 'preview') {
    $parameters.DryRun = $true
}
if ($Action -eq 'uninstall') {
    $parameters.Uninstall = $true
}
if ($Force) {
    $parameters.Force = $true
}

& $installer @parameters
