-- Display equations: numbers to the right, as in LaTeX.
-- Status: PARTIAL (M0).
--   done: \label, \notag, \nonumber are removed from math text (texmath
--         cannot convert aligned blocks that contain them and falls back to
--         raw TeX); numbered equations are counted in the report.
--   TODO (M1) spec:
--   * DisplayMath with \label{x} and x in labels -> number "(labels[x])";
--     \tag{..} -> that tag; \notag/\nonumber or unlabeled -> no number
--     (unlabeled numbered ones get t2d:auto:* labels from stages/autolabel.py).
--   * aligned blocks with several labels: one number per line ->
--     split into separate equations or a borderless 2-column table.
--   * Layout in Word: "math centered, number at right tab" paragraph, or a
--     borderless table; decide in docs/decisions (ADR 0004).
--   * pandoc puts display math inside a Para together with surrounding text:
--     split the Para so the equation gets its own paragraph.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local t2d = require 't2d'

local function strip_service(tex)
  tex = tex:gsub('\\label%s*%b{}', '')
  tex = tex:gsub('\\notag%f[%A]', '')
  tex = tex:gsub('\\nonumber%f[%A]', '')
  return tex
end

function Pandoc(doc)
  local M = t2d.load(doc.meta)
  if not M then return nil end
  local numbered = 0
  doc = doc:walk {
    Math = function(m)
      if m.mathtype ~= 'DisplayMath' then return nil end
      local _, k = m.text:gsub('\\label%s*{', '')
      numbered = numbered + k
      m.text = strip_service(m.text)
      return m
    end,
  }
  if numbered > 0 then t2d.report('info', 'equations.not-numbered', tostring(numbered)) end
  return doc
end
