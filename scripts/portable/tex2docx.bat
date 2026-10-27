@echo off
rem Portable launcher: everything lives next to this file (docs/windows-portable.md).
rem Usage: tex2docx.bat paper.tex [options]      tex2docx.bat --check
setlocal
set "ROOT=%~dp0"
set "PATH=%ROOT%python;%ROOT%pandoc;%ROOT%poppler\bin;%ROOT%texlive\bin\windows;%PATH%"
rem TeX Live portable keeps its settings inside its own tree:
set "TEXMFCNF=%ROOT%texlive\texmf-dist\web2c"
set "TEXMFHOME=%ROOT%texmf-home"
set "PYTHONUTF8=1"
"%ROOT%python\python.exe" -m tex2docx %*
endlocal
