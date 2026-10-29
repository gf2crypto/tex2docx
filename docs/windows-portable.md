# Переносимая установка на Windows (без установщиков и прав администратора)

Все кладется в одну папку (например, `D:\tex2docx-portable` или флешку), ничего не
прописывается в систему: ни PATH, ни реестр. Запуск — через `tex2docx.bat` из этой папки.
Схема та же, что в `windows-offline.md`: собрать на компьютере с интернетом, перенести,
проверить `tex2docx.bat --check`.

Состав папки:

```
tex2docx-portable\
  tex2docx.bat        запуск (выставляет PATH только внутри своего окна)
  python\             Python embeddable + пакеты + сам tex2docx (в Lib\site-packages)
  pandoc\pandoc.exe
  poppler\bin\        pdftoppm.exe и DLL
  texlive\            TeX Live, установленный с ключом -portable
  texmf-home\         личные пакеты TeX пользователя (можно оставить пустой)
  examples\config.yaml
```

## Сборка (компьютер с интернетом, PowerShell)

1. Скачайте вручную два архива (не MSI, а zip):
   - pandoc: `pandoc-<версия>-windows-x86_64.zip` со страницы
     https://github.com/jgm/pandoc/releases/latest (версия ≥ 3.1);
   - poppler: `Release-<версия>-0.zip` с
     https://github.com/oschwartz10612/poppler-windows/releases/latest.

2. В корне репозитория выполните (нужен установленный Python и `git`). PowerShell по умолчанию
   запрещает запуск скриптов («running scripts is disabled on this system») — разрешите его
   для текущего окна: `Set-ExecutionPolicy -Scope Process Bypass` (без прав администратора,
   действует до закрытия окна). Имена архивов подставьте свои:

   ```powershell
   .\scripts\portable\make-portable.ps1 -PythonVersion 3.12.7 `
       -PandocZip C:\Downloads\pandoc-3.x-windows-x86_64.zip `
       -PopplerZip C:\Downloads\Release-xx.yy.z-0.zip
   ```

   Скрипт сам скачивает Python embeddable с python.org (укажите существующую версию 3.10+;
   список: https://www.python.org/downloads/windows/), колеса `python-docx`, `lxml`,
   `PyYAML`, `Pillow`, распаковывает их в `python\Lib\site-packages` (колесо — это zip,
   pip для этого не нужен), кладет туда же `tex2docx`, копирует pandoc и poppler и
   создает `tex2docx-portable\` рядом с текущей папкой.

3. TeX Live — в ту же папку, в переносимом режиме. Смонтируйте ISO-образ
   (https://www.ctan.org/tex-archive/systems/texlive/Images) и запустите из него:

   ```
   install-tl-windows.bat -portable -texdir D:\tex2docx-portable\texlive
   ```

   Ключ `-portable` — «установка для переносного использования, например на USB-носитель,
   без изменений в системе»: отключает правку PATH, ярлыки и ассоциации файлов. В окне
   установщика выберите схему **full**. Папка `texlive` займет около 8 ГБ; установка
   30–60 минут. Можно делать это и сразу на целевом компьютере, если ISO переносится вместе
   с папкой.

   Альтернатива для скрипта без окон: `install-tl-windows.bat -portable -no-gui
   -texdir ... -scheme full` (в разных версиях установщика имя ключа схемы может отличаться:
   `-scheme scheme-full`).

4. Перенесите папку `tex2docx-portable` целиком (с `texlive` внутри — порядка 8–9 ГБ).

## Проверка и работа (компьютер без интернета)

```
D:\tex2docx-portable\tex2docx.bat --check
D:\tex2docx-portable\tex2docx.bat C:\papers\paper\main.tex
D:\tex2docx-portable\tex2docx.bat C:\papers\paper\main.tex --engine xelatex
```

`--check` должен показать `ok` для pandoc, latexmk, pdflatex, kpsewhich, bibtex, pdftoppm,
python-docx, lxml, PyYAML и ключевых файлов TeX. Результат — `main.docx` и `main.report.md`
рядом со статьей.

Как это работает: `tex2docx.bat` добавляет в PATH **только для своего окна** папки
`python`, `pandoc`, `poppler\bin`, `texlive\bin\windows`, указывает TeX Live на его
собственные настройки (`TEXMFCNF`) и на `texmf-home` как личное дерево пакетов, и запускает
`python -m tex2docx`. Папку можно переносить и переименовывать: все пути относительные.

## Особенности и ограничения

- Шрифты: статьи с `fontspec` (`\setmainfont{Times New Roman}`) используют системные шрифты
  Windows — они есть на любой машине; TeX Live portable свои шрифты (Latin Modern, CM) несет с собой.
- `pytest` в переносимой сборке не включен (нет pip); проверка — `--check` и пробная конвертация
  любого документа. Если нужны тесты, скачайте дополнительно колеса `pytest`, `iniconfig`,
  `pluggy`, `packaging` и распакуйте их в `python\Lib\site-packages`, а папку `tests` скопируйте
  в корень; запуск: `python\python.exe -m pytest tests`.
- Обновление tex2docx: заменить `python\Lib\site-packages\tex2docx` на новую версию из `src`.
- Первый запуск LaTeX с новыми шрифтами может быть медленным (TeX Live строит кэш шрифтов
  в своем дереве, не в системе).
