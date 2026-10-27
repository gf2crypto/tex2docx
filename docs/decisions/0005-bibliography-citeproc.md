# ADR 0005. Библиография: .bib через citeproc + CSL ГОСТ; thebibliography — списком

Статус: принято (2026-10-27).

## Контекст

В статьях литература оформляется либо biblatex (`\addbibresource`, `\printbibliography`,
обычно biblatex-gost), либо BibTeX (`\bibliography{}`, `\bibliographystyle{}`), либо вручную
(`thebibliography`). pandoc `\printbibliography` пропускает, `\cite` без citeproc выводит
пустым, `thebibliography` портит (теряет `\bibitem`). Нужен список литературы и номера
цитат в docx, офлайн.

## Решение

1. Есть `.bib` (из `\addbibresource` или `\bibliography`) → pandoc `--citeproc` с этим `.bib`
   и стилем CSL «ГОСТ Р 7.0.5-2008 (numeric)», вшитым в `data/csl/` (лицензия CC BY-SA 3.0;
   локали встроены в pandoc). Цитаты «[1, 2]», «[1, с. 5]», порядок — по первому упоминанию
   (как `sorting=none`); `\nocite{*}` pandoc понимает сам. Список ставится там, где стоял
   `\printbibliography`/`\bibliography` (маркер `\label{t2d:refs}` → `Div#refs`), под заголовком
   «Список литературы» по языку babel. Стиль заменяется ключом `csl:` в конфиге.
2. `thebibliography` → `enumerate` с `\item` вместо `\bibitem`, заголовок по языку;
   номера цитат берутся из `\bibcite{key}{n}` в `.aux` (ровно как в PDF).

## Альтернативы

- Вытаскивать готовый список из PDF, собранного LaTeX (`pdftotext`): символ в символ как
  biblatex-gost, но переносы и дефисы в тексте PDF ломают записи. Отвергнуто.
- Разбирать `.bbl` biblatex: формат внутренний, формат вывода пришлось бы воспроизводить. Отвергнуто.

## Последствия

- Вид записей близок к biblatex-gost, но не идентичен (например, у англоязычных записей
  ГОСТ-стиль пишет «Т.», «С.»; biblatex-gost переключал бы язык по `langid`). Это в `limitations.md`.
- Цитаты и список — обычный текст, редактируемый в Word; живые поля — отдельная задача M3.
- Новых внешних инструментов нет: citeproc входит в pandoc.
