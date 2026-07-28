[CmdletBinding()]
param(
    [switch]$DryRunOnly
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw "Assertion failed: $Message"
    }
}

function Test-ReparsePoint {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $item = Get-Item -LiteralPath $Path -Force
    return ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
}

function Remove-TestJunction {
    param([string]$Path)

    if (Test-ReparsePoint -Path $Path) {
        Remove-Item -LiteralPath $Path -Force
    }
}

if (-not $DryRunOnly -and $env:OS -ne 'Windows_NT') {
    throw 'These tests require native Windows junction support.'
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$installer = Join-Path (Join-Path $repositoryRoot 'scripts') 'install_team_bundle.ps1'
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('dev-skill-windows-test-' + [Guid]::NewGuid().ToString('N'))
$fixtureRepository = Join-Path $testRoot 'repository'
$fixtureHome = Join-Path $testRoot 'home'
$profileDirectory = Join-Path (Join-Path $fixtureRepository 'config') 'profiles'
$skillsDirectory = Join-Path $fixtureRepository 'skills'
$primaryDirectory = Join-Path (Join-Path $skillsDirectory 'development') 'primary'
$helperDirectory = Join-Path (Join-Path $skillsDirectory 'platform') 'helper'
$cursorDirectory = Join-Path $fixtureHome '.cursor'
$cursorSkills = Join-Path $cursorDirectory 'skills'
$primaryTarget = Join-Path $cursorSkills 'primary'
$helperTarget = Join-Path $cursorSkills 'helper'
$originalOperatingSystem = $env:OS

try {
    New-Item -ItemType Directory -Path $profileDirectory -Force | Out-Null
    New-Item -ItemType Directory -Path $primaryDirectory -Force | Out-Null
    New-Item -ItemType Directory -Path $helperDirectory -Force | Out-Null
    New-Item -ItemType Directory -Path $cursorDirectory -Force | Out-Null

    Set-Content -LiteralPath (Join-Path $profileDirectory 'test.skills') -Encoding UTF8 -Value 'development/primary'
    Set-Content -LiteralPath (Join-Path $primaryDirectory 'SKILL.md') -Encoding UTF8 -Value @(
        '---',
        'name: primary',
        'description: Primary test skill.',
        'depends_on:',
        '  - helper',
        '---'
    )
    Set-Content -LiteralPath (Join-Path $helperDirectory 'SKILL.md') -Encoding UTF8 -Value @(
        '---',
        'name: helper',
        'description: Helper test skill.',
        '---'
    )

    # Dry-run is platform-neutral once client discovery uses the isolated fixture home.
    if ($DryRunOnly) {
        $env:OS = 'Windows_NT'
    }
    $dryRunOutput = @(& $installer -Profile test -RepositoryRoot $fixtureRepository -UserHome $fixtureHome -DryRun 6>&1)
    $dryRunText = $dryRunOutput -join [Environment]::NewLine
    Assert-True -Condition (-not (Test-Path -LiteralPath $cursorSkills)) -Message 'dry-run must not create target directories'
    Assert-True -Condition ($dryRunText -match 'primary') -Message 'dry-run should include the profile skill'
    Assert-True -Condition ($dryRunText -match 'helper') -Message 'dry-run should expand dependencies'

    if ($DryRunOnly) {
        Write-Host 'Windows installer dry-run tests passed.' -ForegroundColor Green
        return
    }

    & $installer -Profile test -RepositoryRoot $fixtureRepository -UserHome $fixtureHome
    Assert-True -Condition (Test-ReparsePoint -Path $primaryTarget) -Message 'profile skill should be installed as a junction'
    Assert-True -Condition (Test-ReparsePoint -Path $helperTarget) -Message 'dependency should be installed as a junction'

    & $installer -Profile test -RepositoryRoot $fixtureRepository -UserHome $fixtureHome
    Assert-True -Condition (Test-ReparsePoint -Path $primaryTarget) -Message 'reinstall should be idempotent'

    & $installer -Profile test -RepositoryRoot $fixtureRepository -UserHome $fixtureHome -Uninstall
    Assert-True -Condition (-not (Test-Path -LiteralPath $primaryTarget)) -Message 'uninstall should remove an owned junction'
    Assert-True -Condition (-not (Test-Path -LiteralPath $helperTarget)) -Message 'uninstall should remove dependency junctions'

    New-Item -ItemType Directory -Path $primaryTarget -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $primaryTarget 'keep.txt') -Value 'keep'
    & $installer -Profile test -RepositoryRoot $fixtureRepository -UserHome $fixtureHome
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $primaryTarget 'keep.txt')) -Message 'install without force must preserve conflicts'

    & $installer -Profile test -RepositoryRoot $fixtureRepository -UserHome $fixtureHome -Force
    Assert-True -Condition (Test-ReparsePoint -Path $primaryTarget) -Message 'force should replace a physical conflict with a junction'

    Remove-TestJunction -Path $primaryTarget
    New-Item -ItemType Directory -Path $primaryTarget -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $primaryTarget 'keep.txt') -Value 'keep'
    & $installer -Profile test -RepositoryRoot $fixtureRepository -UserHome $fixtureHome -Uninstall
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $primaryTarget 'keep.txt')) -Message 'uninstall must preserve targets not owned by the repository'
    Assert-True -Condition (-not (Test-Path -LiteralPath $helperTarget)) -Message 'uninstall should still remove owned junctions'

    Write-Host 'Windows installer tests passed.' -ForegroundColor Green
} finally {
    $env:OS = $originalOperatingSystem
    Remove-TestJunction -Path $primaryTarget
    Remove-TestJunction -Path $helperTarget
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}
