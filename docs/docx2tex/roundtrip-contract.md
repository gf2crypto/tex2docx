# Контракт круга tex2docx ↔ docx2tex

Что tex2docx гарантированно оставляет в docx (и не меняет без правки этого файла и теста круга),
и как docx2tex это читает.

| В docx (tex2docx) | В LaTeX (docx2tex) |
|---|---|
| Абзац стиля `Theorem`/`Definition`/`Remark`: начинается с `Strong`/`Emph` «Имя N.M» + «.», затем «(Заметка)» если был `[opt]` | `\begin{<env>}[Заметка] … \end{<env>}`; `<env>` по имени через `theorem_styles`/словарь имен («Теорема»→`theorem`, «Лемма»→`lemma`, «Следствие»→`corollary`, «Определение»→`definition`, «Замечание»→`remark`, «Пример»→`example`, «Утверждение»→`proposition`); номер отбрасывается |
| Абзац стиля `Proof`: «Доказательство.» … «◻» (табулятор + знак) | `\begin{proof} … \end{proof}`, знак отбрасывается |
| Абзац стиля `Equation`: `<tab> oMath <tab> (N)`; без номера — `<tab> oMath` | `\begin{equation}\label{…} … \end{equation}` / `\[ … \]`; несколько подряд с `&` в формуле → один `align` |
| Закладка `t2d_<метка>` вокруг номера (режим `live_numbers`) | `\label{<метка>}` (обратная замена `_` → исходная метка хранится в `docProps/custom.xml`, см. ниже) |
| Поле `REF t2d_<метка> \h` или гиперссылка `w:anchor=<метка>` с текстом-номером | `\ref{<метка>}`; в скобках — `\eqref` |
| Заголовок `Heading N` с текстом «K Имя» или полем `SEQ hN` | `\section{Имя}` и т.д.; `\label{<метка>}` если есть закладка |
| `Image Caption` «Рис. N. Текст» после картинки / `Table Caption` «Таблица N. Текст» перед таблицей | `figure`/`table` с `\centering`, `\includegraphics{images/…}`, `\caption{Текст}`, `\label` |
| `Algorithm Caption` «**Алгоритм N.** Текст» + абзацы `Algorithm` («k:» tab×уровень строка) | `\begin{algorithm}\caption{Текст}\begin{algorithmic}[1] … ` с `\State`/`\If`/… по ключевым словам |
| Абзацы `Bibliography` («1. Текст записи») и цитаты «[1, 2]» | `\begin{thebibliography}` с `\bibitem{bib:1}` и `\cite{bib:1,bib:2}` |
| `Centered` / `Right Aligned` | `\begin{center}` / `\begin{flushright}` |
| Неразрывные пробелы (`postprocess.nbsp`) | `~` только там, где LaTeX-автор поставил бы: после коротких слов и перед тире; остальное — пробел |

## Метаданные круга

Чтобы круг сходился без догадок, tex2docx с версии M4 пишет в `docProps/custom.xml` свойство
`t2d.labels` — JSON «имя закладки → исходная метка», `t2d.theorems` — объявления `\newtheorem`
документа, `t2d.source` — имя исходного `.tex`. docx2tex читает их, если есть; без них работает
по таблице выше (документ, набранный в Word).

## Тест круга

Для каждого кейса `tests/corpus/<case>`:

1. `tex2docx main.tex → a.docx`; `docx2tex a.docx → a.tex`; `a.tex` подставляется в
   `main.tex` вместо тела (`\begin{document}…\end{document}`), собирается `latexmk`,
   `.aux` сравнивается с `.aux` оригинала: те же метки с теми же номерами.
2. `tex2docx` над полученным документом → `b.docx`; зонд `DocxProbe` для `a.docx` и `b.docx`
   совпадает (текст, число формул и картинок, стили, поля).
3. Третий круг не меняет `b.tex` (idempotent) — это ловит накопление пробелов, `{}`, пустых абзацев.
