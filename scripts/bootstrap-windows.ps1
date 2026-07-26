[CmdletBinding()]
param(
    [string]$Msys2Root = $(if ($env:MSYS2_ROOT) { $env:MSYS2_ROOT } else { 'C:\msys64' })
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($PSVersionTable.PSEdition -eq 'Core' -and -not $IsWindows) {
    throw 'This bootstrap script only supports Windows.'
}

$Msys2Root = [System.IO.Path]::GetFullPath($Msys2Root)
$Pacman = Join-Path $Msys2Root 'usr\bin\pacman.exe'
$Vercmp = Join-Path $Msys2Root 'usr\bin\vercmp.exe'

function Invoke-Checked {
    param(
        [Parameter(Mandatory)]
        [string]$FilePath,

        [Parameter(ValueFromRemainingArguments)]
        [string[]]$ArgumentList
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath exited with code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $Pacman -PathType Leaf)) {
    $Winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $Winget) {
        throw @"
MSYS2 is not installed at '$Msys2Root', and winget.exe is unavailable.
Install MSYS2 from https://www.msys2.org/ or set MSYS2_ROOT to its install path,
then run 'just setup' again.
"@
    }

    Write-Host "Installing MSYS2 at $Msys2Root..."
    Invoke-Checked $Winget.Source `
        install `
        --id MSYS2.MSYS2 `
        --exact `
        --force `
        --silent `
        --disable-interactivity `
        --accept-package-agreements `
        --accept-source-agreements `
        --location $Msys2Root

    if (-not (Test-Path -LiteralPath $Pacman -PathType Leaf)) {
        throw "MSYS2 installation completed, but '$Pacman' was not created."
    }
}
else {
    Write-Host "MSYS2 found at $Msys2Root."
}

# Package hooks require the core MSYS utilities even when pacman is launched
# from PowerShell.
$env:PATH = "$(Join-Path $Msys2Root 'usr\bin');$(Join-Path $Msys2Root 'clang64\bin');$env:PATH"

# MSYS2 does not support partial upgrades. Run the upgrade twice because the
# first pass may stop after replacing pacman and the MSYS2 runtime, leaving the
# CLANG64 packages for the second pass. This mirrors CI's fresh package
# resolution and repairs existing installations that have drifted behind it.
Write-Host 'Updating the MSYS2 package database and installed packages...'
Invoke-Checked $Pacman -Syu --noconfirm
Invoke-Checked $Pacman -Syu --noconfirm

$RequiredTools = @(
    'clang.exe'
    'clang++.exe'
    'lld.exe'
    'meson.exe'
    'ninja.exe'
    'cmake.exe'
    'node.exe'
    'npm.cmd'
    'python3.exe'
    'pkg-config.exe'
    'nasm.exe'
    'ccache.exe'
)

function Get-MissingTools {
    @(
        foreach ($Tool in $RequiredTools) {
            $ToolPath = Join-Path $Msys2Root "clang64\bin\$Tool"
            if (-not (Test-Path -LiteralPath $ToolPath -PathType Leaf)) {
                $ToolPath
            }
        }
    )
}

$ToolchainGroup = 'mingw-w64-clang-x86_64-toolchain'
$ExplicitPackages = @(
    'mingw-w64-clang-x86_64-meson'
    'mingw-w64-clang-x86_64-ninja'
    'mingw-w64-clang-x86_64-cmake'
    'mingw-w64-clang-x86_64-lld'
    'mingw-w64-clang-x86_64-nodejs'
    'mingw-w64-clang-x86_64-pkgconf'
    'mingw-w64-clang-x86_64-nasm'
    'mingw-w64-clang-x86_64-ccache'
)
$Packages = @($ToolchainGroup) + $ExplicitPackages

$GroupListing = @(& $Pacman -Sg $ToolchainGroup 2>$null)
$GroupQuerySucceeded = $LASTEXITCODE -eq 0
$InstalledPackages = @(& $Pacman -Qq)
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to query the installed MSYS2 packages.'
}

$ExpectedPackages = @($ExplicitPackages)
if ($GroupQuerySucceeded) {
    $ExpectedPackages += @(
        foreach ($Line in $GroupListing) {
            ($Line -split '\s+')[-1]
        }
    )
}

$MissingPackages = @(
    $ExpectedPackages |
        Sort-Object -Unique |
        Where-Object { $_ -notin $InstalledPackages }
)

if (-not $GroupQuerySucceeded -or $MissingPackages.Count -gt 0) {
    Write-Host 'Installing missing MSYS2 CLANG64 packages...'
    Invoke-Checked $Pacman -S --needed --noconfirm @Packages
}
else {
    Write-Host 'MSYS2 CLANG64 packages are already installed.'
}

$MinimumPackageVersions = [ordered]@{
    'mingw-w64-clang-x86_64-clang'   = '22.1.7-1'
    'mingw-w64-clang-x86_64-headers' = '14.0.0.r92.g818fa6510-1'
    'mingw-w64-clang-x86_64-crt'     = '14.0.0.r92.g818fa6510-1'
    'mingw-w64-clang-x86_64-meson'   = '1.11.1-1'
    'mingw-w64-clang-x86_64-ninja'   = '1.13.2-1'
    'mingw-w64-clang-x86_64-cmake'   = '4.3.3-1'
    'mingw-w64-clang-x86_64-nodejs'  = '24.16.0-1'
    'mingw-w64-clang-x86_64-python'  = '3.14.5-1'
    'mingw-w64-clang-x86_64-pkgconf' = '1~2.5.1-1'
}

if (-not (Test-Path -LiteralPath $Vercmp -PathType Leaf)) {
    throw "MSYS2 version comparison tool '$Vercmp' is missing."
}

foreach ($Entry in $MinimumPackageVersions.GetEnumerator()) {
    $Package = $Entry.Key
    $MinimumVersion = $Entry.Value
    $QueryResult = @(& $Pacman -Q $Package)
    if ($LASTEXITCODE -ne 0 -or $QueryResult.Count -ne 1) {
        throw "Unable to determine the installed version of '$Package'."
    }

    $InstalledVersion = ($QueryResult[0] -split '\s+', 2)[1]
    $Comparison = & $Vercmp $InstalledVersion $MinimumVersion
    if ($LASTEXITCODE -ne 0 -or [int]$Comparison -lt 0) {
        throw "'$Package' $InstalledVersion is older than the required $MinimumVersion."
    }
}

$MissingTools = @(Get-MissingTools)
if ($MissingTools.Count -gt 0) {
    throw "MSYS2 provisioning finished with missing tools:`n$($MissingTools -join "`n")"
}

Write-Host 'Windows build prerequisites are ready.'
