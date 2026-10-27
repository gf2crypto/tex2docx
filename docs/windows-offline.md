# Установка на Windows без интернета

Конвертер не обращается к сети ни на одном этапе: все, что ему нужно, — программы и пакеты,
установленные заранее. Схема: на компьютере **с интернетом** скачать комплект (шаги 1–5),
перенести его на флешке, на компьютере **без интернета** установить (шаги 6–9) и проверить
командой `tex2docx --check` (шаг 10). Все пути ниже — примеры, можно выбрать свои.

Проверено с pandoc 3.1.3 и 3.12.1, TeX Live 2025/2026, Python 3.12. Объем комплекта —
около 6 ГБ, почти все — TeX Live.

## Что скачать (компьютер с интернетом)

### 1. TeX Live — полный образ ISO

Не MiKTeX: он докачивает пакеты по мере надобности, а без сети это означает сбой на первом
же редком пакете. TeX Live в полной установке («scheme-full») содержит все пакеты CTAN,
включая `preview`, `cyrillic`, `babel-russian`, `biblatex`, `biblatex-gost`, `gost`, `algorithms`,
`cryptocode`, `tempora`, `newtx` и latexmk с Perl.

- Каталог образов: https://www.ctan.org/tex-archive/systems/texlive/Images
  (файл `texlive.iso` или `texliveYYYY.iso`, ~5,5 ГБ; там же контрольные суммы).
- Зеркало на случай медленной загрузки: https://mirror.ctan.org/systems/texlive/Images/

### 2. pandoc (3.1 или новее)

- Страница выпусков: https://github.com/jgm/pandoc/releases/latest
- Нужен файл `pandoc-<версия>-windows-x86_64.msi` (установщик, сам добавляет pandoc в PATH).
  Инструкция pandoc: https://pandoc.org/installing

### 3. Poppler (утилита pdftoppm)

- Сборка для Windows: https://github.com/oschwartz10612/poppler-windows/releases/latest
- Нужен архив `Release-<версия>-0.zip`; внутри `poppler-<версия>\Library\bin\pdftoppm.exe`.

### 4. Python 3.10 или новее

- https://www.python.org/downloads/windows/ — «Windows installer (64-bit)», файл
  `python-3.x.y-amd64.exe`.

### 5. Пакеты Python и сам tex2docx

На компьютере с интернетом, где уже стоит Python той же версии (3.x) и разрядности, выполните
в папке репозитория (PowerShell):

```powershell
.\scripts\download-offline-deps.ps1
```

Скрипт кладет в папку `offline\wheels` колеса `python-docx`, `lxml`, `PyYAML`, `Pillow`,
`pytest`, `setuptools`, `wheel` для Windows x64, а в `offline\` — архив исходников
tex2docx (`tex2docx-src.zip`). Если PowerShell недоступен, те же команды вручную:

```powershell
pip download --dest offline\wheels --platform win_amd64 --python-version 3.12 --only-binary=:all: python-docx lxml PyYAML Pillow pytest setuptools wheel
git archive -o offline\tex2docx-src.zip HEAD
```

(`--python-version` — версия Python, которая будет стоять на целевом компьютере.)

Перенесите на флешку: ISO TeX Live, MSI pandoc, ZIP poppler, EXE Python, папку `offline`.

## Установка (компьютер без интернета)

### 6. TeX Live

Смонтируйте ISO (правой кнопкой → «Подключить») и запустите `install-tl-windows.bat`.
В установщике выберите схему **full** (полная) и оставьте галочку «Add TeX Live to PATH».
Установка длится 30–60 минут. После нее откройте новое окно командной строки и проверьте:

```
latexmk --version
kpsewhich preview.sty
```

Вторая команда должна напечатать путь к файлу. Нужных шрифтов (Times New Roman и др.)
в Windows достаточно; статьи с `fontspec` компилируются `--engine xelatex`.

### 7. pandoc

Запустите MSI. Проверка: `pandoc --version` (первая строка — версия, нужна ≥ 3.1).

### 8. Poppler

Распакуйте ZIP, например в `C:\Tools\poppler`, и добавьте в переменную PATH папку
`C:\Tools\poppler\poppler-<версия>\Library\bin` (Параметры → Система → О системе →
Дополнительные параметры → Переменные среды → Path → Изменить → Создать). Проверка в новом
окне: `pdftoppm -v`.

### 9. Python и tex2docx

Установите Python, отметив галочку **«Add python.exe to PATH»**. Затем:

```powershell
mkdir C:\tex2docx
Expand-Archive offline\tex2docx-src.zip -DestinationPath C:\tex2docx
cd C:\tex2docx
python -m venv .venv
.\.venv\Scripts\activate
pip install --no-index --find-links offline\wheels setuptools wheel
pip install --no-index --find-links offline\wheels ".[images,dev]"
```

(`--no-index` запрещает pip ходить в сеть; папку `offline` нужно скопировать внутрь `C:\tex2docx`
или указать к ней полный путь.)

### 10. Проверка

```powershell
tex2docx --check
pytest -q
tex2docx tests\corpus\basic\main.tex -o %USERPROFILE%\Desktop\basic.docx
```

`--check` печатает по строке на каждый инструмент, пакет Python и ключевой файл TeX;
строки со словом «НЕТ» — то, без чего работать не будет, «нет» — необязательное.
`pytest` должен показать все тесты пройденными (их число растет с версиями). Третья
команда делает docx из тестового документа — откройте его в Word.

## Использование

```powershell
.\.venv\Scripts\activate          # один раз в каждом новом окне
tex2docx C:\papers\paper\main.tex
tex2docx C:\papers\paper\main.tex --engine xelatex     # если статья собирается xelatex
tex2docx C:\papers\paper\main.tex -c my-config.yaml   # свои настройки (examples\config.yaml)
```

Рядом с `main.tex` появятся `main.docx` и `main.report.md`. Исходники не меняются.
Если результат плох — отправьте `main.report.md`: текста статьи в нем нет.

## Если что-то не нашлось

- `kpsewhich <файл>` молчит → пакета нет в TeX Live; при полной схеме такого не бывает,
  при частичной — нужен другой образ. Докачать отдельный пакет без сети нельзя.
- `pandoc` старее 3.1 → фильтры не работают; поставьте MSI новее.
- `tex2docx --check` ругается на `python-docx`/`lxml`/`PyYAML` → колеса скачаны не для той
  версии или разрядности Python; повторите шаг 5 с правильным `--python-version`.
- Картинки BMP/TIFF в статье: нужен Pillow (в комплекте) либо ImageMagick; без них
  в отчете будет `figures.unsupported-format`.
