# Стили CSL для citeproc

`gost-r-7-0-5-2008-numeric.csl` — «Russian GOST R 7.0.5-2008 (numeric)» из репозитория
Citation Style Language (https://github.com/citation-style-language/styles),
лицензия CC BY-SA 3.0; наше изменение: разделитель номеров в цитате «, » вместо «,»
(как у biblatex: «[1, 2]»). Используется по умолчанию для `.bib`-библиографии (ADR 0005).
Свой стиль: ключ `csl:` в конфиге. Локали citeproc (ru-RU и др.) встроены в pandoc,
сеть не нужна.
