# tex2docx

Конвертер математических статей LaTeX → Word (.docx):

- формулы — нативные формулы Word (редактируемые, не картинки);
- теоремы, леммы, определения, доказательства — абзацы со своими стилями Word;
- номера теорем, формул и ссылок — **ровно как в PDF**: берутся из `.aux` настоящего LaTeX;
- рисунки (TikZ и др.) — картинками, отрисованными с преамбулой документа;
- библиография: `.bib` → список по ГОСТ Р 7.0.5 (citeproc, офлайн), `thebibliography` → список с номерами из LaTeX;
- по желанию — живые номера: поля Word SEQ/REF, пересчитываются после правок (`live_numbers`);
- отчет обо всем, что передано неточно, **без текста документа** — его можно пересылать.

Состояние: M0 (каркас), M1 (нумерация как в LaTeX), M2 (устойчивость: личные пакеты,
формулы-картинки, thmtools/ntheorem, cleveref) готовы; M3 (полировка Word) частично. См. `ROADMAP.md`.

## Установка (macOS)

Нужны pandoc ≥ 3.1, TeX Live (MacTeX) с latexmk, poppler, Python ≥ 3.10.

```sh
brew install pandoc poppler          # TeX Live / MacTeX — если еще нет
git clone <repo> tex2docx && cd tex2docx
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest -q                            # проверка, что все на месте
```

## Использование

```sh
tex2docx paper.tex                     # → paper.docx + paper.report.md
tex2docx paper.tex -o out/paper.docx -c examples/config.yaml
tex2docx paper.tex --engine xelatex
tex2docx paper.tex --workdir /tmp/wd   # оставить промежуточные файлы
```

Документ должен компилироваться (`latexmk` из каталога, где лежит `paper.tex`).
Личные пакеты из `~/texmf` (или `~/Library/texmf`) конвертер находит сам через `kpsewhich`
и переносит из них макросы и `\newtheorem`; что перенести не удалось, перечислено в отчете
(`macros.skipped`) — такие макросы можно подменить в конфиге (`macros:`).

## Отчет

`paper.report.md` — таблица: этап, код, объект (имя команды/окружения/метки), сколько раз,
номера строк. Текста статьи там нет. Если результат плохой — пришлите отчет, по нему
делается синтетический тестовый пример и исправление.

## Настройка

См. `examples/config.yaml`: движок TeX, шаблон стилей Word, имя доказательства, стили теорем,
ручная подмена макросов, окружения-рисунки.

Свой шаблон стилей: скопируйте `src/tex2docx/data/reference.docx`, поменяйте стили в Word
(имена стилей Theorem, Definition, Remark, Proof, Equation не трогайте) и укажите в `reference_docx`.
У стиля Equation два табулятора — центральный и правый; при другой ширине текста поправьте их.

## Разработка

Правила и команды — `CLAUDE.md`; устройство — `docs/architecture.md`;
решения — `docs/decisions/`; что запланировано — `ROADMAP.md`.
