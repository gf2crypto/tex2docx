-- Bibliography placement and manual (thebibliography) citations. ADR 0005.
-- Status: implemented (M3).
-- normalize.py turns \printbibliography / \bibliography{} / \begin{thebibliography}
-- into \label{t2d:refs}; pandoc makes a Span with that id. Here it becomes a heading
-- ("Список литературы" by language) plus Div#refs, where citeproc puts the list.
-- When M.bibcites is non-empty (thebibliography: numbers from the .aux), every
-- Cite becomes plain "[1, 2]" text; otherwise Cite elements are left to citeproc.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local t2d = require 't2d'

local function is_marker(blk)
  if blk.t ~= 'Para' and blk.t ~= 'Plain' then return false end
  for _, x in ipairs(blk.content) do
    if x.t == 'Span' and x.identifier == 't2d:refs' then return true end
    if x.t ~= 'Space' and x.t ~= 'SoftBreak' then return false end
  end
  return false
end

function Pandoc(doc)
  local M = t2d.load(doc.meta)
  if not M then return nil end
  local bibcites = M.bibcites or {}
  local has_cites = next(bibcites) ~= nil
  local title = (M.names or {}).bibliography or 'References'

  local blocks = {}
  for _, blk in ipairs(doc.blocks) do
    if is_marker(blk) then
      blocks[#blocks + 1] = pandoc.Header(1, { pandoc.Str(title) }, pandoc.Attr('', { 'unnumbered' }))
      blocks[#blocks + 1] = pandoc.Div({}, pandoc.Attr('refs'))
    else
      blocks[#blocks + 1] = blk
    end
  end
  doc.blocks = blocks
  if not has_cites then return doc end

  return doc:walk {
    Cite = function(c)
      local nums = {}
      for _, cit in ipairs(c.citations) do
        local n = bibcites[cit.id]
        if not n then
          t2d.report('warning', 'bibliography.unknown-key', cit.id)
          return nil
        end
        nums[#nums + 1] = n
      end
      local inl = pandoc.List({ pandoc.Str('[' .. table.concat(nums, ', ')) })
      local suffix = c.citations[#c.citations].suffix
      if suffix and #suffix > 0 then
        inl:insert(pandoc.Str(','))
        inl:insert(pandoc.Space())
        inl:extend(suffix)
      end
      inl:insert(pandoc.Str(']'))
      return inl
    end,
  }
end
