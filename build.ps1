# build.ps1  —  lean & fast PyInstaller builds for VideoSubTool
[CmdletBinding()]
param(
  [ValidateSet('release','debug','run','clean')]
  [string]$Task = 'release',

  # App metadata
  [string]$Name    = 'VideoSubTool',
  [string]$Entry   = 'src/app/main.py',
  [string]$Icon    = 'resources/branding/icon.ico',

  # Add-data pairs (SRC;DEST) -> --add-data SRC;DEST
  [string[]]$Resources = @('resources;resources'),

  # Build switches
  [switch]$OneFile = $false,   # onedir by default (faster startup)
  [switch]$Windowed = $true,   # GUI app

  # Dependency bootstrap
  [switch]$NoInstall = $false,

  # Power user pass-through
  [string]$ExtraArgs = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Exec {
  param([string]$CmdLine)
  Write-Host ">> $CmdLine" -ForegroundColor Cyan
  & $env:ComSpec /c $CmdLine
  if ($LASTEXITCODE -ne 0) { throw ("Command failed: {0}" -f $CmdLine) }
}

function Ensure-Poetry {
  if ($NoInstall) { return }
  if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
    Write-Host 'Poetry not found – installing via pip...' -ForegroundColor Yellow
    python -m pip install --user poetry
    # refresh PATH so "poetry" is available right away
    $usr  = [Environment]::GetEnvironmentVariable('Path','User')
    $mach = [Environment]::GetEnvironmentVariable('Path','Machine')
    $env:Path = ($usr, $mach -join ';')
  }
  Write-Host 'Installing dependencies via Poetry...' -ForegroundColor Green
  Invoke-Exec 'poetry install --no-interaction'
}

function Join-AddDataArgs {
  param([string[]]$Pairs)
  $args = @()
  foreach ($p in $Pairs) {
    if ($p -notmatch ';') { throw ("Invalid resources entry: {0}  (expected SRC;DEST)" -f $p) }
    $args += @('--add-data', $p)
  }
  ,$args
}

function Has-PyInstallerFlag {
  param([string]$Flag)
  $help = (& $env:ComSpec /c "poetry run pyinstaller -h" 2>&1) -join "`n"
  return ($help -match [Regex]::Escape($Flag))
}

function Get-PySideArgs {
  # Kompatibler, robuster Fallback (größeres Bundle, aber funktioniert überall):
  @('--collect-all','PySide6')
}


function Remove-PyCaches {
  Get-ChildItem -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  Get-ChildItem -Recurse -Include '*.pyc','*.pyo' |
    Remove-Item -Force -ErrorAction SilentlyContinue
}

function Build-CommonArgs {
  param([switch]$IsDebug)

  $pyArgs = @(
    '--noconfirm',
    '--clean'                  # clean intermediates inside build/
  )

  if ($IsDebug) { $pyArgs += @('--log-level','DEBUG') }

  # Fast startup by default
  if ($OneFile) { $pyArgs += '--onefile' }
  if ($Windowed) { $pyArgs += '--windowed' }

  $pyArgs += @('--name', $Name)
  $pyArgs += (Get-PySideArgs)
  $pyArgs += (Join-AddDataArgs -Pairs $Resources)

  if ($Icon) {
    if (-not (Test-Path $Icon)) { throw ("Icon not found: {0}" -f $Icon) }
    $pyArgs += @('--icon', $Icon)
  }

  if (-not (Test-Path $Entry)) { throw ("Entry not found: {0}" -f $Entry) }
  $pyArgs += $Entry

  if ($ExtraArgs) { $pyArgs += $ExtraArgs.Split(' ') }
  ,$pyArgs
}

function Task-Release {
  Ensure-Poetry
  Remove-PyCaches

  # Production build: INFO logs (default), windowed, minimal Qt
  $args = Build-CommonArgs
  $cmd  = 'poetry run pyinstaller ' + ($args -join ' ')
  Invoke-Exec $cmd

  Write-Host "`nArtifacts in dist/`n" -ForegroundColor Green
  if (Test-Path dist) { Get-ChildItem dist | Format-Table -AutoSize }
}

function Task-Debug {
  Ensure-Poetry
  Remove-PyCaches

  # Console + verbose logs – helpful during packaging issues
  $saved = $Windowed
  $global:Windowed = $false
  try {
    $args = Build-CommonArgs -IsDebug
  } finally {
    $global:Windowed = $saved
  }

  $cmd = 'poetry run pyinstaller ' + ($args -join ' ')
  Invoke-Exec $cmd

  Write-Host "`nDebug build done. Artifacts in dist/`n" -ForegroundColor Yellow
}

function Task-Run {
  Ensure-Poetry
  # ensure package markers (harmless if present)
  New-Item -ItemType File -Force src/app/__init__.py | Out-Null
  New-Item -ItemType File -Force src/app/controller/__init__.py | Out-Null
  New-Item -ItemType File -Force src/app/service/__init__.py | Out-Null
  New-Item -ItemType File -Force src/app/model/__init__.py | Out-Null
  New-Item -ItemType File -Force src/app/view/__init__.py | Out-Null

  Write-Host 'Starting app (dev)…' -ForegroundColor Green
  Invoke-Exec 'poetry run video-subtool'
}

function Task-Clean {
  Write-Host 'Removing build/ and dist/…' -ForegroundColor Yellow
  if (Test-Path build) { Remove-Item build -Recurse -Force }
  if (Test-Path dist)  { Remove-Item dist  -Recurse -Force }
  Write-Host 'Clean complete.' -ForegroundColor Green
}

switch ($Task) {
  'release' { Task-Release }
  'debug'   { Task-Debug }
  'run'     { Task-Run }
  'clean'   { Task-Clean }
  default   { throw ("Unknown task: {0}" -f $Task) }
}
