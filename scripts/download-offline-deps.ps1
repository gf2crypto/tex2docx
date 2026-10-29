# Собирает в папку offline\ все Python-зависимости и исходники tex2docx для переноса
# на компьютер без интернета (docs/windows-offline.md, шаг 5).
# Запускать на компьютере с интернетом из корня репозитория:
#   .\scripts\download-offline-deps.ps1 [-PythonVersion 3.12]
param([string]$PythonVersion = "3.12")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "offline"
$wheels = Join-Path $out "wheels"
New-Item -ItemType Directory -Force -Path $wheels | Out-Null

python -m pip download --dest $wheels --platform win_amd64 --python-version $PythonVersion `
    --only-binary=:all: python-docx lxml PyYAML Pillow pytest setuptools wheel
if ($LASTEXITCODE -ne 0) { throw "pip download failed" }

git -C $root archive -o (Join-Path $out "tex2docx-src.zip") HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }

Write-Host "Done: $out"
Get-ChildItem $wheels | Select-Object Name, Length
