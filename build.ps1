# build.ps1

[CmdletBinding()]
param(
  [ValidateSet('build','run','clean')]
  [string]$Task = 'build',

  [string]$Name = 'VideoSubTool',
  [string]$Entry = 'src/app/main.py',
  [string]$Icon = '',
  [string[]]$Resources = @('resources;resources'),

  [switch]$OneFile = $true,
  [switch]$Windowed = $true,
  [switch]$NoInstall = $false,

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
    $usr  = [System.Environment]::GetEnvironmentVariable('Path','User')
    $mach = [System.Environment]::GetEnvironmentVariable('Path','Machine')
    $env:Path = ($usr, $mach -join ';')
  }
  Write-Host 'Installing dependencies via Poetry...' -ForegroundColor Green
  Invoke-Exec 'poetry install --no-interaction'
}

function Join-AddDataArgs {
  param([string[]]$Pairs)
  $args = @()
  foreach ($p in $Pairs) {
    if ($p -notmatch ';') { throw ("Invalid resources entry: {0}" -f $p) }
    $args += @('--add-data', $p)
  }
  ,$args
}

function Get-PyInstallerCollectArgs {
  <#
    Ermittelt, welche Sammel-Flags verfügbar sind.
    - Falls --collect-plugins/--collect-binaries existieren -> nutze die (präziser, kleineres Bundle)
    - Sonst fallback auf --collect-all PySide6
  #>
  $help = (& $env:ComSpec /c "poetry run pyinstaller -h" 2>&1) -join "`n"
  $args = @()
  if ($help -match '--collect-plugins' -and $help -match '--collect-binaries') {
    $args += @('--collect-plugins','PySide6','--collect-binaries','PySide6')
  } else {
    $args += @('--collect-all','PySide6')
  }
  ,$args
}

function Build-Project {
  Ensure-Poetry

  # Optional: __pycache__ aufräumen
  Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

  $pyArgs = @('--noconfirm')

  # Sammel-Flags dynamisch ermitteln
  $pyArgs += (Get-PyInstallerCollectArgs)

  # Immer sinnvoll:
  $pyArgs += @(
    '--name', $Name,
    '--collect-submodules', 'PySide6',
    '--collect-data', 'PySide6'
  )

  if ($OneFile)   { $pyArgs += '--onefile' }
  if ($Windowed)  { $pyArgs += '--windowed' }

  if ($Icon) {
    if (-not (Test-Path $Icon)) { throw ("Icon not found: {0}" -f $Icon) }
    $pyArgs += @('--icon', $Icon)
  }

  # Ressourcen
  $pyArgs += (Join-AddDataArgs -Pairs $Resources)

  # ExtraArgs vom Benutzer zuletzt (dürfen Flags überschreiben)
  if ($ExtraArgs) { $pyArgs += $ExtraArgs.Split(' ') }

  # Entry prüfen
  if (-not (Test-Path $Entry)) { throw ("Entry not found: {0}" -f $Entry) }
  $pyArgs += $Entry

  $cmd = 'poetry run pyinstaller ' + ($pyArgs -join ' ')
  Invoke-Exec $cmd

  Write-Host ''
  Write-Host 'Build done. Artifacts in dist/' -ForegroundColor Green
  if (Test-Path dist) { Get-ChildItem dist | Format-Table -AutoSize }
}

function Run-App {
  Ensure-Poetry
  # Package-Marker sicherstellen (harmlos, falls vorhanden)
  New-Item -ItemType File -Force src/app/__init__.py        | Out-Null
  New-Item -ItemType File -Force src/app/controller/__init__.py | Out-Null
  New-Item -ItemType File -Force src/app/service/__init__.py | Out-Null
  New-Item -ItemType File -Force src/app/model/__init__.py   | Out-Null
  New-Item -ItemType File -Force src/app/view/__init__.py    | Out-Null

  Write-Host 'Starting app (dev)...' -ForegroundColor Green
  Invoke-Exec 'poetry run video-subtool'
}

function Clean-Project {
  Write-Host 'Removing build/ and dist/...' -ForegroundColor Yellow
  if (Test-Path build) { Remove-Item build -Recurse -Force }
  if (Test-Path dist)  { Remove-Item dist -Recurse -Force }
  Write-Host 'Clean complete.' -ForegroundColor Green
}

switch ($Task) {
  'clean' { Clean-Project }
  'run'   { Run-App }
  'build' { Build-Project }
  default { throw ("Unknown task: {0}" -f $Task) }
}
