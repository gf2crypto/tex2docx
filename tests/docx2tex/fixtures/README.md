# Заготовки для синтетических docx

- `omml/*.xml` — формулы Word (OMML), снятые с вывода pandoc для коротких LaTeX-формул
  (`pandoc -t docx` от `$x^2$`, `$\sum_{i=1}^{n} x_i$`), чтобы `make.py` кейсов вставлял их
  как есть. Пересоздать: `python tests/docx2tex/fixtures/make_omml.py`.
- `pic.png` — картинка 40×20 px (генерируется тем же скриптом).
