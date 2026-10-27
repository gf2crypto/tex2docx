-- \ref / \eqref -> numbers computed by LaTeX (.aux).
-- Status: implemented (M0). Links stay links to the target's bookmark.
-- pandoc alone prints "[eq:square]" for \eqref and its own numbering for \ref.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local t2d = require 't2d'

function Pandoc(doc)
  local M = t2d.load(doc.meta)
  if not M then return nil end
  local labels = M.labels or {}

  return doc:walk {
    Link = function(el)
      local kind = el.attributes['reference-type']
      local ref = el.attributes['reference']
      if not kind or not ref then return nil end
      local num = labels[ref]
      if not num then
        t2d.report('warning', 'crossref.unresolved', ref)
        return nil
      end
      if kind == 'eqref' then num = '(' .. num .. ')' end
      el.content = { pandoc.Str(num) }
      return el
    end,
  }
end
