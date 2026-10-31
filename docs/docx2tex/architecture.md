# docx2tex — архитектура

Зеркало tex2docx: тот же конвейер этапов над одним `Context`, тот же отчет,
тот же принцип «спрашивай инструмент, а не угадывай» — только теперь инструмент,
у которого спрашивают, это pandoc (структура и формулы) и сам LaTeX (проверка сборки).

## Поток данных

```
chapter.docx ─► extract ─► pandoc (+ structures.lua) ─► normalize ─► emit ─► chapter.tex (+ images/)
                 │ xml,       │ docx → latex с фильтром:    │ типограф.  │ фрагмент │
                 │ закладки,  │ theorem/equation/figure/    │ Word→TeX   │ или      ▼
                 │ спутник,   │ algorithm/thebibliography,  │            │ документ  chapter.report.{md,json}
                 ▼ prepared   ▼ ссылки, заголовки           ▼            ▼
            ctx.bookmarks  ctx.tex                       ctx.tex     chapter.t2d.xml ──► check (latexmk, --standalone)
```

Как сделано (M0–M1): этапы — `src/docx2tex/stages/*.py`, фильтр — `src/docx2tex/filters/structures.lua`.

| Этап | Что делает | Откуда берет истину |
|---|---|---|
| extract | `word/document.xml`: закладки, поля; спутник `<имя>.t2d.xml`; язык; рабочая копия `workdir/prepared.docx` (`stages/prepare.py`): закладки, поля `REF`/`SEQ` и табуляторы записаны в текст маркерами U+E000…U+E003, потому что pandoc их выбрасывает | XML docx |
| pandoc | `pandoc -f docx+styles -t latex --extract-media --lua-filter structures.lua`; формулы OMML → LaTeX (texmath); данные для фильтра — JSON `d2t-meta` (метки спутника и их хеши pandoc 3.12, объявления теорем, словарь имен, ключи цитат) | pandoc |
| structures (фильтр) | маркеры → метки; `Div` стилей `Theorem`/… → `theorem`; абзацы `Equation` → `equation`/`align`/`subequations`; подписи → `figure`/`table`; `Algorithm` → `algorithmic`; библиография → `thebibliography`, «[1]» → `\cite`; заголовки без номеров с `\label`; ссылки на закладки → `\ref`/`\eqref`; `\maketitle` | стили и закладки, положенные tex2docx (контракт круга) |
| normalize | типографика Word → TeX, чистка мусора Word (пустые абзацы, двойные пробелы, `\\` вместо абзацев), экранирование `% & # _` в тексте | таблица замен, та же, что `stages/normalize.py` tex2docx, в обратную сторону |
| emit | `pandoc -t latex` из AST + свои writer-правила; фрагмент без преамбулы, список нужных пакетов и `\newtheorem` — в отчет; `--standalone` — полный документ | — |
| check | `--standalone` компилируется `latexmk`; ошибки → отчет без текста; `.aux` сравнивается с ожиданиями (в тестах) | LaTeX |

Все промежуточные файлы — в `ctx.workdir`; исходный docx не меняется.

## Что общее с tex2docx

- `report.py` (коды `этап.что-случилось`, без текста документа), `tools.py` (pandoc, latexmk),
  `config.py` (один YAML с секциями `tex2docx:`/`docx2tex:` или общие ключи:
  `theorem_styles` в обе стороны, `figure_name`, `proof_name`, `macros`).
- Таблицы соответствий: стили Word ↔ окружения LaTeX, имена подписей ↔ язык, ключевые слова
  алгоритмов — один источник (`src/tex2docx/data/`), чтобы круг сходился.
- Корпус tex2docx — вход для тестов круга.

## Контракт круга (`roundtrip-contract.md`)

Зафиксированный список того, что tex2docx оставляет в docx и что docx2tex обязан прочитать:
имена стилей, вид абзаца формулы, имена закладок `t2d_<метка>`, поля `REF`, формат подписи
«Рис. N. текст», формат заголовка теоремы «**Теорема 1.2** (Имя).». Любое изменение
в tex2docx, затрагивающее этот список, меняет контракт и тест круга.

## Чего не будет в коде

- Своего парсера OMML: формулы — только через texmath (pandoc). Если texmath не перевел
  формулу, в `.tex` попадает `\text{[формула не распознана]}` с кодом в отчете, а не догадка.
- Своих `.sty`: выход — стандартный LaTeX (требование 2).
- Распознавания оформления: шрифты и размеры из docx игнорируются.
