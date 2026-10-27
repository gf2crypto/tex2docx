-- Section numbers: "1 Введение", "2.1 Выкладки" from the .aux (pandoc's docx has none).
-- Status: implemented (M3). Headers with class "unnumbered" (\section*) are left alone;
-- the number comes from the header's label (autolabel marks every numbered heading).

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local t2d = require 't2d'

function Pandoc(doc)
  local M = t2d.load(doc.meta)
  if not M then return nil end
  local labels = M.labels or {}
  return doc:walk {
    Header = function(h)
      if h.classes:includes('unnumbered') or h.identifier == '' then return nil end
      local num = labels[h.identifier]
      if not num then return nil end  -- e.g. a heading pandoc made from something else
      local inl = pandoc.List(t2d.number(num, 'heading', h.identifier, nil, h.level))
      inl:insert(pandoc.Str('\194\160'))
      inl:extend(h.content)
      h.content = inl
      return h
    end,
  }
end
