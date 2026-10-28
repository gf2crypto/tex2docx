# Дорожная карта

Исполняемая часть дорожной карты — `xfail_*` в `tests/corpus/*/expect.yaml`
(`pytest -rxX` покажет, что запланировано и что уже начало проходить).

## M0 — каркас (готово)

- [x] Конвейер этапов, контекст, отчет без текста документа, CLI.
- [x] `flatten`: склейка `\input`/`\include`, вычищение строк-комментариев.
- [x] `latex`: компиляция latexmk, номера меток из `.aux` (включая `\@input` и hyperref).
- [x] `theorems`: сбор `\newtheorem`/`\theoremstyle` (amsthm) из документа и локальных `.sty`.
- [x] `normalize`: бабелевские сокращения `"---`, `"=`, `"<`, `">` и др.
- [x] `figures`: окружения из `figure_envs` → PNG через `preview`, подстановка `\includegraphics`.
- [x] `pandoc`: запуск из каталога исходника (так pandoc видит локальные `.sty`),
      сбор пропущенных команд и формул, ушедших текстом, в отчет.
- [x] Фильтры: `crossref` (номера из `.aux`), `theorems` (номера, стиль, «Доказательство»,
      без номера для `\newtheorem*`), `equations` (вычищение `\label`/`\notag` из формул).
- [x] `reference.docx` со стилями Theorem/Definition/Remark/Proof.
- [x] Корпус `basic` + сквозной тест по `expect.yaml`, юнит-тесты.

## M1 — нумерация как в LaTeX (готово)

- [x] `autolabel`: метки `t2d:auto:N` для всех нумеруемых объектов без `\label`
      (теоремы, equation/multline/subequations, строки align/gather/eqnarray, рисунки, таблицы)
      → номера всех объектов из `.aux`.
- [x] `equations.lua`: номер справа у выносных формул; `\tag`; align с номерами по строкам
      (ADR 0004: абзац стиля `Equation` с табуляторами).
- [x] Разрезать `Para` вокруг выносной формулы, чтобы формула была отдельным абзацем.
- [x] Подписи рисунков и таблиц с номером: «Рис. 1. Окружность» (имя из babel/конфига).
- [x] Кейс корпуса `numbering`: `\numberwithin`, общие счетчики, `\newtheorem*`, `\tag`, `subequations`.

## M2 — устойчивость на чужих документах (готово)

- [x] `macros`: определения (и `\newtheorem`) из пакетов и классов, найденных через `kpsewhich`
      вне дистрибутива (личный texmf); кейс `texmfhome`.
- [x] Формула, которую pandoc не смог перевести → картинка через `preview` (`math_fallback`); кейс `mathimage`.
- [x] Отображение строк отчета на исходные файлы (`ctx.line_map`; этапы сохраняют число строк).
- [x] thmtools (`\declaretheorem`), ntheorem (стили `nonumber*`, `\newframedtheorem`); кейсы `thmtools`, `ntheorem`.
- [x] Кейс корпуса: документ из нескольких файлов (`multifile`).
- [x] Кейсы корпуса: `amsart`, `cleveref` (hyperref + `\cref`/`\Cref`/`\crefrange`/`\autoref`
      с именами из cleveref и `\crefname`), `xelatex` (fontspec + polyglossia + unicode-math).

## M3 — полировка Word

- [x] `postprocess`: неразрывные пробелы после коротких предлогов/союзов и перед тире, keep-with-next
      (абзац перед формулой, рисунок перед подписью, подпись перед таблицей), знак конца
      доказательства по правому краю, ссылки без синего стиля Hyperlink.
- [x] Живые номера: поля SEQ + закладки, ссылки как поля REF (`live_numbers`, ADR 0006); кейс `livenumbers`.
- [x] Номера разделов «1 Введение» из `.aux` (`headings.lua`; pandoc в docx их не ставит).
- [x] Библиография: `.bib` (biblatex/BibTeX) → citeproc + CSL ГОСТ Р 7.0.5 (ADR 0005);
      `thebibliography` → нумерованный список, номера цитат из `\bibcite`; кейсы `bibliography`, `thebib`.
- [ ] Шаблоны под журналы: `examples/<journal>.yaml` + свой `reference.docx` — когда будут требования
      конкретного журнала (механизм `reference_docx`/`csl`/`theorem_styles` готов).
- [x] Алгоритмы: редактируемые строки в рамке (`stages/algorithms.py`, стили Algorithm/Algorithm Caption),
      картинкой — `algorithms: image`.

## Сделано, но стоит пересмотреть

- `data/package-macros/`: пока только cryptocode; пополнять по отчетам (`pandoc.math-as-image` с именем команды).

- `oldmath`: `\rm X` без фигурных скобок (`$\rm tr\, x$`) не переписывается — такая формула уйдет картинкой.

- `flatten`: макросы с `\input`/`\include` в теле раскрываются только если определены через
  `\newcommand`; `\def\Source{...}` и `\import`/`\subimport` не поддержаны — появятся в отчетах, добавим.

- `equations`: `align` с несколькими номерами режется на строки, выравнивание по `&` между
  строками теряется. Если будет мешать — таблица без рамок для этого случая (ADR 0004).
- `autolabel`: сканер не видит окружения, спрятанные в макросах (`\newenvironment{thm}{\begin{theorem}}...`),
  и не знает нумеруемых окружений других пакетов. Признак: `theorem.unlabeled` в отчете.

- `figures`: регэксп по окружениям не видит окружения, спрятанные в макросах. Если такие
  встретятся в отчетах — перейти на подсчет страниц `preview` с маркерами в тексте.
