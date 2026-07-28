[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$Profile = 'diy',

    [switch]$DryRun,
    [switch]$Uninstall,
    [switch]$Force,

    [string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$UserHome = [Environment]::GetFolderPath('UserProfile')
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-WarningMessage {
    param([string]$Message)
    Write-Warning $Message
}

function Get-NormalizedPath {
    param([string]$Path)

    return [IO.Path]::GetFullPath($Path).TrimEnd([char[]]@([char]92, [char]47))
}

function Test-PathsEqual {
    param(
        [string]$Left,
        [string]$Right
    )

    $leftPath = Get-NormalizedPath -Path $Left
    $rightPath = Get-NormalizedPath -Path $Right
    return [StringComparer]::OrdinalIgnoreCase.Equals($leftPath, $rightPath)
}

function Join-RelativePath {
    param(
        [string]$BasePath,
        [string]$RelativePath
    )

    $result = $BasePath
    foreach ($segment in ($RelativePath -split '[\\/]')) {
        if ($segment) {
            $result = Join-Path $result $segment
        }
    }
    return $result
}

function Assert-ChildPath {
    param(
        [string]$RootPath,
        [string]$ChildPath,
        [string]$Description
    )

    $root = Get-NormalizedPath -Path $RootPath
    $child = Get-NormalizedPath -Path $ChildPath
    $prefix = $root + [IO.Path]::DirectorySeparatorChar
    if (-not $child.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "$Description escapes its allowed root: $ChildPath"
    }
}

function Get-ProfileItems {
    param(
        [string]$ProfilePath,
        [string]$SkillsRoot
    )

    if (-not (Test-Path -LiteralPath $ProfilePath -PathType Leaf)) {
        throw "Profile not found: $ProfilePath"
    }

    $seen = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $items = New-Object 'Collections.Generic.List[string]'
    foreach ($line in Get-Content -LiteralPath $ProfilePath) {
        $relativePath = $line.Trim()
        if (-not $relativePath -or $relativePath.StartsWith('#')) {
            continue
        }

        $skillPath = Join-RelativePath -BasePath $SkillsRoot -RelativePath $relativePath
        Assert-ChildPath -RootPath $SkillsRoot -ChildPath $skillPath -Description 'Skill path'
        if ($seen.Add($relativePath)) {
            $items.Add(($relativePath -replace '\\', '/'))
        }
    }
    return $items.ToArray()
}

function ConvertTo-DependencyName {
    param([string]$Value)

    return $Value.Trim().Trim([char[]]@([char]39, [char]34))
}

function Get-SkillDependencies {
    param([string]$SkillFile)

    $lines = @(Get-Content -LiteralPath $SkillFile)
    if ($lines.Count -eq 0 -or $lines[0].Trim() -ne '---') {
        return @()
    }

    $dependencies = New-Object 'Collections.Generic.List[string]'
    $collectingList = $false
    for ($index = 1; $index -lt $lines.Count; $index++) {
        $line = $lines[$index]
        if ($line.Trim() -eq '---') {
            break
        }

        if ($collectingList -and $line -match '^\s*-\s*(.+?)\s*$') {
            $name = ConvertTo-DependencyName -Value $Matches[1]
            if ($name) {
                $dependencies.Add($name)
            }
            continue
        }
        if ($collectingList -and $line -match '^[A-Za-z0-9_-]+\s*:') {
            $collectingList = $false
        }

        if ($line -match '^depends_on:\s*$') {
            $collectingList = $true
            continue
        }
        if ($line -match '^depends_on:\s*\[(.*)\]\s*$') {
            foreach ($value in ($Matches[1] -split ',')) {
                $name = ConvertTo-DependencyName -Value $value
                if ($name) {
                    $dependencies.Add($name)
                }
            }
        }
    }
    return $dependencies.ToArray()
}

function Get-SkillNameIndex {
    param([string]$SkillsRoot)

    $index = @{}
    foreach ($category in @(Get-ChildItem -LiteralPath $SkillsRoot -Directory)) {
        foreach ($skill in @(Get-ChildItem -LiteralPath $category.FullName -Directory)) {
            $skillFile = Join-Path $skill.FullName 'SKILL.md'
            if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) {
                continue
            }
            $relativePath = $category.Name + '/' + $skill.Name
            if (-not $index.ContainsKey($skill.Name)) {
                $index[$skill.Name] = New-Object 'Collections.Generic.List[string]'
            }
            $index[$skill.Name].Add($relativePath)
        }
    }
    return $index
}

function Resolve-DependencyPath {
    param(
        [string]$Dependency,
        [string]$SkillsRoot,
        [hashtable]$SkillNameIndex
    )

    if ($Dependency -match '[\\/]') {
        $relativePath = $Dependency -replace '\\', '/'
        $candidate = Join-RelativePath -BasePath $SkillsRoot -RelativePath $relativePath
        if (Test-Path -LiteralPath (Join-Path $candidate 'SKILL.md') -PathType Leaf) {
            return $relativePath
        }
        return $null
    }

    if (-not $SkillNameIndex.ContainsKey($Dependency)) {
        return $null
    }
    $matches = @($SkillNameIndex[$Dependency] | Sort-Object)
    if ($matches.Count -gt 1) {
        Write-WarningMessage "Dependency '$Dependency' matches multiple skills; using '$($matches[0])'."
    }
    return $matches[0]
}

function Expand-SkillDependencies {
    param(
        [string[]]$ProfileItems,
        [string]$SkillsRoot
    )

    $queue = New-Object 'Collections.Generic.List[string]'
    $selected = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($item in $ProfileItems) {
        if ($selected.Add($item)) {
            $queue.Add($item)
        }
    }

    $nameIndex = Get-SkillNameIndex -SkillsRoot $SkillsRoot
    for ($index = 0; $index -lt $queue.Count; $index++) {
        $relativePath = $queue[$index]
        $skillPath = Join-RelativePath -BasePath $SkillsRoot -RelativePath $relativePath
        $skillFile = Join-Path $skillPath 'SKILL.md'
        foreach ($dependency in @(Get-SkillDependencies -SkillFile $skillFile)) {
            $dependencyPath = Resolve-DependencyPath -Dependency $dependency -SkillsRoot $SkillsRoot -SkillNameIndex $nameIndex
            if (-not $dependencyPath) {
                Write-WarningMessage "Skill '$relativePath' depends on missing skill '$dependency'; skipping dependency."
                continue
            }
            if ($selected.Add($dependencyPath)) {
                $queue.Add($dependencyPath)
            }
        }
    }
    return $queue.ToArray()
}

function Assert-ValidSkills {
    param(
        [string[]]$SkillItems,
        [string]$SkillsRoot
    )

    $installNames = @{}
    foreach ($relativePath in $SkillItems) {
        $skillPath = Join-RelativePath -BasePath $SkillsRoot -RelativePath $relativePath
        Assert-ChildPath -RootPath $SkillsRoot -ChildPath $skillPath -Description 'Skill path'
        if (-not (Test-Path -LiteralPath $skillPath -PathType Container)) {
            throw "Skill directory not found: $skillPath"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $skillPath 'SKILL.md') -PathType Leaf)) {
            throw "SKILL.md not found: $skillPath"
        }

        $skillName = Split-Path -Leaf $skillPath
        if ($installNames.ContainsKey($skillName) -and $installNames[$skillName] -ne $relativePath) {
            throw "Skills '$($installNames[$skillName])' and '$relativePath' share install name '$skillName'."
        }
        $installNames[$skillName] = $relativePath
    }
}

function Get-ClientConfigurations {
    param([string]$HomePath)

    return @(
        [PSCustomObject]@{
            Name = 'Cursor'
            ConfigDirectory = Join-Path $HomePath '.cursor'
            Commands = @('cursor')
            Targets = @((Join-Path (Join-Path $HomePath '.cursor') 'skills'))
        },
        [PSCustomObject]@{
            Name = 'Claude Code'
            ConfigDirectory = Join-Path $HomePath '.claude'
            Commands = @('claude', 'claude-code')
            Targets = @((Join-Path (Join-Path $HomePath '.claude') 'skills'))
        },
        [PSCustomObject]@{
            Name = 'Codex'
            ConfigDirectory = Join-Path $HomePath '.codex'
            Commands = @('codex')
            Targets = @(
                (Join-Path (Join-Path $HomePath '.codex') 'skills.union'),
                (Join-Path (Join-Path $HomePath '.codex') 'skills')
            )
        }
    )
}

function Test-ClientDetected {
    param([PSCustomObject]$Client)

    if (Test-Path -LiteralPath $Client.ConfigDirectory -PathType Container) {
        return $true
    }
    foreach ($command in $Client.Commands) {
        if (Get-Command $command -ErrorAction SilentlyContinue) {
            return $true
        }
    }
    if ($Client.Name -eq 'Cursor' -and $env:LOCALAPPDATA) {
        $cursorDirectory = Join-Path (Join-Path $env:LOCALAPPDATA 'Programs') 'cursor'
        if (Test-Path -LiteralPath $cursorDirectory -PathType Container) {
            return $true
        }
    }
    return $false
}

function Get-JunctionTarget {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    $item = Get-Item -LiteralPath $Path -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) {
        return $null
    }

    $target = @($item.Target)[0]
    if (-not $target) {
        return $null
    }
    if (-not [IO.Path]::IsPathRooted($target)) {
        $target = Join-Path (Split-Path -Parent $Path) $target
    }
    return Get-NormalizedPath -Path $target
}

function Test-OwnedJunction {
    param(
        [string]$Source,
        [string]$Destination
    )

    $target = Get-JunctionTarget -Path $Destination
    return $null -ne $target -and (Test-PathsEqual -Left $Source -Right $target)
}

function Remove-ExistingTarget {
    param([string]$Path)

    $item = Get-Item -LiteralPath $Path -Force
    $isLink = ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
    if ($isLink) {
        Remove-Item -LiteralPath $Path -Force
        return
    }
    Remove-Item -LiteralPath $Path -Recurse -Force
}

function Install-SkillJunction {
    param(
        [string]$Source,
        [string]$Destination,
        [switch]$Preview,
        [switch]$Replace
    )

    if (Test-Path -LiteralPath $Destination) {
        if (Test-OwnedJunction -Source $Source -Destination $Destination) {
            Write-Info "Already installed: $Destination"
            return
        }
        if (-not $Replace) {
            Write-WarningMessage "Target exists; skipping (use -Force to replace): $Destination"
            return
        }
        if ($Preview) {
            Write-Info "[dry-run] Replace target: $Destination"
        } else {
            Remove-ExistingTarget -Path $Destination
        }
    }

    $parent = Split-Path -Parent $Destination
    if ($Preview) {
        Write-Info "[dry-run] Create junction: $Destination -> $Source"
        return
    }
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    New-Item -ItemType Junction -Path $Destination -Target $Source | Out-Null
    Write-Info "Installed: $Destination"
}

function Uninstall-SkillJunction {
    param(
        [string]$Source,
        [string]$Destination,
        [switch]$Preview
    )

    if (-not (Test-Path -LiteralPath $Destination)) {
        return
    }
    if (-not (Test-OwnedJunction -Source $Source -Destination $Destination)) {
        Write-WarningMessage "Target is not owned by this repository; keeping it: $Destination"
        return
    }
    if ($Preview) {
        Write-Info "[dry-run] Remove junction: $Destination"
        return
    }
    Remove-Item -LiteralPath $Destination -Force
    Write-Info "Uninstalled: $Destination"
}

function Invoke-ClientOperation {
    param(
        [PSCustomObject]$Client,
        [string[]]$SkillItems,
        [string]$SkillsRoot,
        [switch]$Remove,
        [switch]$Preview,
        [switch]$Replace
    )

    Write-Info "Processing $($Client.Name)."
    foreach ($relativePath in $SkillItems) {
        $source = Join-RelativePath -BasePath $SkillsRoot -RelativePath $relativePath
        $skillName = Split-Path -Leaf $source
        foreach ($targetRoot in $Client.Targets) {
            $destination = Join-Path $targetRoot $skillName
            if ($Remove) {
                Uninstall-SkillJunction -Source $source -Destination $destination -Preview:$Preview
            } else {
                Install-SkillJunction -Source $source -Destination $destination -Preview:$Preview -Replace:$Replace
            }
        }
    }
}

if ($env:OS -ne 'Windows_NT') {
    throw 'This installer is for native Windows. Use scripts/install_team_bundle.sh on macOS or Linux.'
}

$repository = Get-NormalizedPath -Path $RepositoryRoot
$skillsRoot = Join-Path $repository 'skills'
$profilePath = Join-Path (Join-Path (Join-Path $repository 'config') 'profiles') ($Profile + '.skills')
if (-not (Test-Path -LiteralPath $skillsRoot -PathType Container)) {
    throw "Skills directory not found: $skillsRoot"
}

$profileItems = @(Get-ProfileItems -ProfilePath $profilePath -SkillsRoot $skillsRoot)
$skillItems = @(Expand-SkillDependencies -ProfileItems $profileItems -SkillsRoot $skillsRoot)
Assert-ValidSkills -SkillItems $skillItems -SkillsRoot $skillsRoot

Write-Info "Profile '$Profile': $($skillItems.Count) skills selected."
if ($DryRun) {
    Write-Info 'Mode: dry-run.'
}
if ($Uninstall) {
    Write-Info 'Mode: uninstall.'
}

$detectedClients = 0
foreach ($client in @(Get-ClientConfigurations -HomePath (Get-NormalizedPath -Path $UserHome))) {
    if (-not (Test-ClientDetected -Client $client)) {
        Write-WarningMessage "Client not detected; skipping $($client.Name)."
        continue
    }
    $detectedClients++
    Invoke-ClientOperation -Client $client -SkillItems $skillItems -SkillsRoot $skillsRoot `
        -Remove:$Uninstall -Preview:$DryRun -Replace:$Force
}

if ($detectedClients -eq 0) {
    Write-WarningMessage 'No supported client was detected. Install or start a client once, then retry.'
}
Write-Info 'Done.'
