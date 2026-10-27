# Поведение pandoc, на которое мы опираемся и которое обходим

Проверено на pandoc 3.1.3 (LaTeX reader → docx writer). При обновлении pandoc
перепроверить; сквозные тесты должны поймать большую часть изменений.
Дописывай сюда каждую новую находку с датой.

## Теоремы (amsthm)

- `\newtheorem` pandoc понимает: окружение становится `Div(id=<label>, classes={env})`,
  первый абзац начинается с `Strong[Str title, Space, Str "N"]`, затем `Str "."`.
  Для стиля `remark` вместо `Strong` — `Emph`.
- **Номера pandoc считает сам и неправильно**: игнорирует `[section]` и `\numberwithin`
  (в корпусе: 1, 2, 3 вместо 1.1, 1.2, 1.3). Поэтому номера берем из `.aux`.
- `\newtheorem*` тоже получает номер («Гипотеза1» без пробела) — фильтр его удаляет.
- Необязательный аргумент (`[Основная]`) идет отдельным `Str "(Основная)."` после заголовка.
- Тело `plain`-теорем оборачивается в `Emph`.

## Доказательство

- `proof` → `Div(classes={"proof"})`, заголовок `Emph[Str "Proof."]` — всегда по-английски,
  независимо от babel. В конце абзаца `Str "\160◻"` (U+25FB).

## Ссылки

- `\ref{x}` → `Link` с атрибутами `reference-type=ref`, `reference=x`; текст — номер pandoc
  (неверный для теорем, см. выше).
- `\eqref{x}` → текст `[x]`: номера формул pandoc не знает вовсе.

## Метки (проверено 2026-10-27)

- `\label` сразу после `\begin{<теорема>}[opt]` становится `id` соответствующего `Div`;
  `\label` после `\caption{}` — `id` элемента `Figure`. На этом держится `autolabel`.
- `\label` внутри `equation`/`align` остается в тексте формулы (`\label{x}\na=b`) —
  фильтр `equations` обязан его вычищать до texmath.
- `subequations` целиком становится одной `DisplayMath` с `\begin{equation}`/`\begin{align}`
  внутри текста формулы; texmath это переводит, но в одну формулу Word — структура и номера
  подформул (1.9a, 1.9b) теряются. Поэтому `normalize` снимает обертку `subequations`,
  а внутренние окружения нумеруются своими метками (кейс `numbering`).

## Рисунки и таблицы

- `figure` с `\caption{}\label{x}` → `Figure(id=x, Caption)`; `table` → `Div(id=x)[Table(Caption)]`.
  Writer docx печатает только текст подписи, без «Рис. 1» — префикс ставит фильтр `captions`.
  Стили абзацев: `Image Caption` (после рисунка), `Table Caption` (перед таблицей).

## Формулы

- Выносная формула лежит внутри `Para` вместе с окружающим текстом.
- `align` → `DisplayMath` с `\begin{aligned}...\end{aligned}`; `\label` остается внутри текста формулы.
- texmath **не переводит** блок `aligned`, если в нем есть `\label`/`\notag` между строками, и тогда
  формула уходит в docx **сырым TeX-текстом** с `[WARNING] Could not convert TeX math`.
  То же для любой неизвестной команды (`unexpected control sequence \foo`).
- Номера формул (`\numberwithin{equation}{section}`) pandoc не ставит, команду пропускает.
- `gather` и `multline` → `gathered`; `eqnarray` → `aligned` (с `&=&` как есть);
  `alignat{2}` → `aligned`, но `{2}` остается в тексте формулы; `flalign` pandoc не знает —
  уходит текстом. Поэтому `normalize` переписывает `alignat`/`flalign` в `align`.
- Тело plain-теоремы pandoc оборачивает в `Emph`, и выносная формула внутри теоремы
  лежит в `Emph`, а не прямо в `Para`. Фильтр `equations` вытаскивает ее наружу.
- `RawInline('openxml', '<w:r><w:tab/></w:r>')` writer docx вставляет как есть — так ставим табуляторы.

## Макросы и пакеты

- `\newcommand`, `\DeclareMathOperator` из документа раскрываются.
- `\usepackage{name}` → pandoc пытается прочитать `name.sty` **из текущего каталога**
  (не из `--resource-path`) и раскрывает определения из него. Пакеты дистрибутива он не находит
  (`[INFO] Could not load include file ...`) — это нормально.

## Babel

- `"---` превращается в `"—` (кавычка остается). Решено в `stages/normalize.py`.
- `~` → неразрывный пробел U+00A0 — правильно.

## Сообщения

- С `--verbose` пропущенные команды выводятся как
  `[INFO] Skipped '<cmd...>' at <file> line N column M`.
- Неудачная формула: `[WARNING] Could not convert TeX math <текст формулы>, rendering as TeX:`
  и далее строки с `unexpected control sequence \foo`. Текст формулы в отчет не копируем.

## LibreOffice как средство просмотра

- Нужен модуль `libreoffice-math`, иначе формулы при конвертации в PDF пропадают.
- Даже с ним OMML рисуется приблизительно: `\mathbf` теряется, `&` в выравнивании показывается как «¿».
  Это проблема просмотра, а не docx.
