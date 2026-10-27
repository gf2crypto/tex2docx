-- Figure and table captions: "Рис. 1. Окружность", number from the .aux.
-- Status: implemented (M1).
-- pandoc 3.1: \begin{figure}...\caption{}\label{x} -> Figure(id=x, Caption);
-- \begin{table} -> Div(id=x)[Table(Caption)]. The docx writer prints the caption
-- text only, so the prefix is added here. Names and separator come from the
-- config (names.figure, names.table, names.sep), defaults follow babel.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local t2d = require 't2d'

local function prefix(caption, text)
  local blk = caption.long and caption.long[1]
  if not blk then return end
  if blk.t == 'Plain' or blk.t == 'Para' then
    blk.content:insert(1, pandoc.Str(text))
  end
end

function Pandoc(doc)
  local M = t2d.load(doc.meta)
  if not M then return nil end
  local labels, names = M.labels or {}, M.names or {}
  local sep = names.sep or '.'

  local function number(id, kind)
    if id == '' then return nil end
    local num = labels[id]
    if not num then
      t2d.report('warning', 'captions.unresolved', id)
      return nil
    end
    return (names[kind] or kind) .. ' ' .. num .. sep .. ' '
  end

  return doc:walk {
    Figure = function(fig)
      local p = number(fig.identifier, 'figure')
      if p then prefix(fig.caption, p) end
      return fig
    end,
    Div = function(div)
      if div.identifier == '' or #div.content ~= 1 or div.content[1].t ~= 'Table' then
        return nil
      end
      local p = number(div.identifier, 'table')
      if p then prefix(div.content[1].caption, p) end
      return div
    end,
  }
end
