# Собирает переносимую папку tex2docx-portable\ (без установки и прав администратора):
#   python\   — Python embeddable + пакеты из колес, tex2docx внутри site-packages
#   pandoc\   — pandoc.exe из zip
#   poppler\  — pdftoppm.exe и его DLL из zip poppler-windows
#   texlive\  — сюда отдельно ставится TeX Live с ключом -portable (см. docs/windows-portable.md)
#   tex2docx.bat, docx2tex.bat — запуск
# Запускать на компьютере с интернетом из корня репозитория (PowerShell 5+):
#   .\scripts\portable\make-portable.ps1 -PythonVersion 3.12.7 -PandocZip pandoc-3.x-windows-x86_64.zip -PopplerZip Release-xx.yy.z-0.zip
param(
    [string]$PythonVersion = "3.12.7",
    [Parameter(Mandatory = $true)][string]$PandocZip,
    [Parameter(Mandatory = $true)][string]$PopplerZip,
    [string]$Out = "tex2docx-portable"
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$out = Join-Path (Get-Location) $Out
New-Item -ItemType Directory -Force -Path $out | Out-Null

# 1. Python embeddable
$pyMajor = ($PythonVersion -split '\.')[0..1] -join ''
$pyZip = Join-Path $out "python-embed.zip"
Invoke-WebRequest "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip" -OutFile $pyZip
Expand-Archive $pyZip -DestinationPath (Join-Path $out "python") -Force
Remove-Item $pyZip
$site = Join-Path $out "python\Lib\site-packages"
New-Item -ItemType Directory -Force -Path $site | Out-Null
# python3XX._pth: let the interpreter see site-packages
$pth = Get-ChildItem (Join-Path $out "python") -Filter "python*._pth" | Select-Object -First 1
@("python$pyMajor.zip", ".", "Lib\site-packages", "import site") | Set-Content $pth.FullName -Encoding ASCII

# 2. Пакеты Python: колеса -> распаковать в site-packages (колесо = zip)
$wheels = Join-Path $out "wheels"
New-Item -ItemType Directory -Force -Path $wheels | Out-Null
python -m pip download --dest $wheels --platform win_amd64 --python-version ($PythonVersion -replace '\.\d+$','') `
    --only-binary=:all: python-docx lxml PyYAML Pillow
if ($LASTEXITCODE -ne 0) { throw "pip download failed" }
Get-ChildItem $wheels -Filter *.whl | ForEach-Object {
    # Expand-Archive accepts only the .zip extension: a wheel is a zip under another name
    $zip = [System.IO.Path]::ChangeExtension($_.FullName, ".zip")
    Copy-Item $_.FullName $zip -Force
    Expand-Archive $zip -DestinationPath $site -Force
    Remove-Item $zip
}
Remove-Item $wheels -Recurse

# 3. tex2docx itself
Copy-Item (Join-Path $root "src\tex2docx") (Join-Path $site "tex2docx") -Recurse -Force
Copy-Item (Join-Path $root "examples") (Join-Path $out "examples") -Recurse -Force
Copy-Item (Join-Path $root "docs\windows-portable.md") $out -Force

# 4. pandoc и poppler из скачанных архивов
Expand-Archive $PandocZip -DestinationPath (Join-Path $out "pandoc-tmp") -Force
$pandocExe = Get-ChildItem (Join-Path $out "pandoc-tmp") -Recurse -Filter pandoc.exe | Select-Object -First 1
New-Item -ItemType Directory -Force -Path (Join-Path $out "pandoc") | Out-Null
Copy-Item $pandocExe.FullName (Join-Path $out "pandoc\pandoc.exe") -Force
Remove-Item (Join-Path $out "pandoc-tmp") -Recurse

Expand-Archive $PopplerZip -DestinationPath (Join-Path $out "poppler-tmp") -Force
$bin = Get-ChildItem (Join-Path $out "poppler-tmp") -Recurse -Filter pdftoppm.exe | Select-Object -First 1
New-Item -ItemType Directory -Force -Path (Join-Path $out "poppler\bin") | Out-Null
Copy-Item (Join-Path $bin.DirectoryName "*") (Join-Path $out "poppler\bin") -Recurse -Force
Remove-Item (Join-Path $out "poppler-tmp") -Recurse

# 5. запуск
Copy-Item (Join-Path $PSScriptRoot "tex2docx.bat") $out -Force
Copy-Item (Join-Path $PSScriptRoot "docx2tex.bat") $out -Force
New-Item -ItemType Directory -Force -Path (Join-Path $out "texmf-home") | Out-Null
Write-Host "Done: $out. Now install TeX Live into $out\texlive (install-tl-windows.bat -portable)."
