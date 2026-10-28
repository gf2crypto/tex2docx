# tex2docx

Конвертер математических статей LaTeX → Word (.docx). Работает локально, без интернета.

- формулы — нативные формулы Word (редактируемые, не картинки); то, что Word не умеет
  (`\sideset`, tikz в формуле), — картинкой, набранной LaTeX с преамбулой статьи;
- теоремы, леммы, определения, доказательства — абзацы со своими стилями Word
  (amsthm, thmtools, ntheorem);
- номера разделов, теорем, формул, рисунков и все ссылки (`\ref`, `\eqref`, `\cref`) —
  **ровно как в PDF**: берутся из `.aux` настоящего LaTeX;
- алгоритмы (`algorithmic`/`algpseudocode`) — редактируемый псевдокод в рамке: ключевые слова, номера строк,
  отступы, формулы — формулы Word (или картинкой: `algorithms: image`);
- рисунки TikZ и псевдокод cryptocode — картинками с преамбулой документа;
  PNG/JPG/PDF-картинки вставляются как есть (PDF/BMP/TIFF переводятся в PNG);
- библиография: biblatex/`.bib` → список по ГОСТ Р 7.0.5 (citeproc, офлайн),
  BibTeX/`.bst` и `thebibliography` → список ровно как в PDF, цитаты с номерами LaTeX;
- кодировки cp1251/koi8-r, личные пакеты из `~/texmf`, свои классы журналов, многофайловые
  документы, `\input` внутри макросов шаблона;
- стандартный шаблон оформления (`--profile standard`) или свой `reference.docx`;
- по желанию живые номера — поля Word SEQ/REF, пересчитываются после правок (`live_numbers`);
- отчет обо всем, что передано неточно, **без текста документа** — его можно пересылать.

## Установка

Нужны: pandoc ≥ 3.1, TeX Live (полный; на macOS — MacTeX) с latexmk, poppler (`pdftoppm`),
Python ≥ 3.10.

macOS:

```sh
brew install pandoc poppler          # TeX Live / MacTeX — если еще нет
git clone https://github.com/gf2crypto/tex2docx.git && cd tex2docx
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,images]'
tex2docx --check                     # все ли инструменты и пакеты TeX на месте
pytest -q                            # сквозные тесты на корпусе
```

Windows без интернета: `docs/windows-offline.md` — что скачать заранее (TeX Live ISO, pandoc,
poppler, Python, колеса) и как поставить; `docs/windows-portable.md` — переносимая папка
без установщиков и прав администратора, запуск через `tex2docx.bat`.

## Использование

```sh
tex2docx paper.tex                       # → paper.docx и paper.report.md рядом с paper.tex
tex2docx paper.tex --profile standard    # стандартный шаблон оформления (см. ниже)
tex2docx paper.tex --engine xelatex      # если статья собирается xelatex (fontspec)
tex2docx paper.tex -o out/paper.docx -c my.yaml   # свой конфиг (образец: examples/config.yaml)
tex2docx paper.tex --workdir /tmp/wd     # оставить промежуточные файлы (склейка, лог LaTeX, картинки)
tex2docx --check                         # проверка окружения
```

Условие одно: статья должна собираться своим LaTeX (`latexmk` из ее каталога). Исходники
не меняются; все промежуточные файлы — во временном каталоге. Личные пакеты из `~/texmf`
(`~/Library/texmf`) находятся через `kpsewhich`; что из них перенести не удалось, перечислено
в отчете (`macros.skipped`), такие макросы подменяются в конфиге (`macros:`).

Что проверить в Word после конвертации: номера формул у правого края (стиль `Equation`
с табуляторами), пределы у сумм и интегралов, списки литературы. Если включены живые
номера (`live_numbers: true`), после правок обновите поля: Ctrl+A, F9.

## Стандартный шаблон оформления

`--profile standard` (или `profile: standard` в конфиге): Times New Roman 14 во всех стилях,
межстрочный интервал 1,5, без интервалов между абзацами, абзацный отступ 1,25 см, текст по
ширине, заголовки всех уровней черные полужирные, титул и подписи по центру.

Требования к шаблону хранятся в одном месте — таблице `PROFILES["standard"]` в
`scripts/make_reference_docx.py`. Новое требование: строка в таблице → пересборка
(`python scripts/make_reference_docx.py`) → коммит `src/tex2docx/data/reference-standard.docx`;
тест `tests/corpus/standard` проверяет стили готового docx.

Свой шаблон (например, под журнал): скопируйте `src/tex2docx/data/reference.docx`, поменяйте
стили в Word (имена стилей Theorem, Definition, Remark, Proof, Equation, Algorithm, Algorithm Caption,
Centered, Right Aligned, Left Aligned не трогайте; у Equation два табулятора — центральный и правый,
под свою ширину текста) и укажите путь в конфиге: `reference_docx: journal.docx`.

## Отчет

`paper.report.md` — таблица: этап, код, объект (имя команды, окружения или метки), сколько раз,
файл и строка в исходниках. Текста статьи там нет. `warning` — что-то передано неточно,
`error` — результат заведомо неполон, `info` — к сведению. Если результат плохой, пришлите
отчет: по нему делается синтетический тестовый пример и исправление.

## Настройка

Все ключи — в `examples/config.yaml` с комментариями: движок TeX, профиль или свой шаблон
стилей, стиль CSL для библиографии, имя доказательства и имена подписей («Рис.», «Таблица»),
стили теорем, подмена макросов, какие окружения рендерить картинками, живые номера,
что делать с непереводимыми формулами.

## Разработка

Правила и команды — `CLAUDE.md`; устройство — `docs/architecture.md`; принятые решения —
`docs/decisions/`; поведение pandoc, на которое опираемся, — `docs/pandoc-behavior.md`;
что не поддерживаем и почему — `docs/limitations.md`; планы — `ROADMAP.md`.
Тестовый корпус — только синтетика (`tests/corpus/`), реальных статей в репозитории нет.
