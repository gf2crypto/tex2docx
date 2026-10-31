-- Word structures -> LaTeX structures (docx2tex). Status: M0 part.
--   * headings lose pandoc's identifiers (no \hypertarget/\label noise);
--     a heading made of "N Title" by tex2docx drops the number;
--   * a paragraph that is one formula is a display formula;
--   * list items lose the "List Bullet"/"List Number" Divs; default numbering;
--   * simple tables (no spans) become plain tabular (RawBlock) instead of longtable;
--   * images: path as extracted by --extract-media, no size attributes.
-- M1 (theorems, equations with numbers, captions, algorithms, bibliography) comes next.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local d2t = require 'd2t'

local function strip_number(inlines)
  -- "1 Введение" / "2.1 Текст": first Str of digits and dots followed by Space
  local first = inlines[1]
  if first and first.t == 'Str' and first.text:match('^%d[%d%.]*$') and inlines[2] and inlines[2].t == 'Space' then
    local out = pandoc.List(inlines)
    out:remove(1)
    out:remove(1)
    return out
  end
  return inlines
end

local function cell_text(cell)
  local blocks = cell.contents or cell.content
  local parts = {}
  for _, b in ipairs(blocks) do
    parts[#parts + 1] = pandoc.write(pandoc.Pandoc({ b }), 'latex'):gsub('\n$', '')
  end
  return table.concat(parts, ' ')
end

local function simple_table(tbl)
  -- plain tabular with l columns and \hline, when no cell spans
  local ncols = #tbl.colspecs
  local rows = {}
  local function add_rows(rowlist)
    for _, row in ipairs(rowlist) do
      local cells = {}
      for _, c in ipairs(row.cells) do
        if c.row_span > 1 or c.col_span > 1 then return false end
        cells[#cells + 1] = cell_text(c)
      end
      rows[#rows + 1] = table.concat(cells, ' & ') .. ' \\\\'
    end
    return true
  end
  if not add_rows(tbl.head.rows) then return nil end
  for _, body in ipairs(tbl.bodies) do
    if not add_rows(body.body) then return nil end
  end
  if not add_rows(tbl.foot.rows) then return nil end
  local spec = '|' .. string.rep('l|', ncols)
  local lines = { '\\begin{center}', '\\begin{tabular}{' .. spec .. '}', '\\hline' }
  for i, r in ipairs(rows) do
    lines[#lines + 1] = r
    if i == #tbl.head.rows and #tbl.head.rows > 0 then lines[#lines + 1] = '\\hline' end
  end
  lines[#lines + 1] = '\\hline'
  lines[#lines + 1] = '\\end{tabular}'
  lines[#lines + 1] = '\\end{center}'
  return pandoc.RawBlock('latex', table.concat(lines, '\n'))
end

function Pandoc(doc)
  local M = d2t.load(doc.meta) or {}
  doc = doc:walk {
    Header = function(h)
      h.identifier = ''
      h.content = strip_number(h.content)
      return h
    end,
    Div = function(div)
      local style = div.attributes['custom-style']
      if style == 'List Bullet' or style == 'List Number' or style == 'List Paragraph' then
        return div.content
      end
      return nil
    end,
    OrderedList = function(ol)
      local n, sty, delim = table.unpack(ol.listAttributes and { ol.listAttributes.start, ol.listAttributes.style, ol.listAttributes.delimiter } or { ol.start, ol.style, ol.delimiter })
      if (sty == 'Decimal' or sty == 'DefaultStyle') and (delim == 'Period' or delim == 'DefaultDelim') then
        ol.listAttributes = pandoc.ListAttributes(n or 1, 'DefaultStyle', 'DefaultDelim')
      end
      return ol
    end,
    Para = function(p)
      local only = nil
      for _, x in ipairs(p.content) do
        if x.t == 'Math' then
          if only then return nil end
          only = x
        elseif x.t ~= 'Space' and x.t ~= 'SoftBreak' then
          return nil
        end
      end
      if only and only.mathtype == 'InlineMath' then
        return pandoc.Para({ pandoc.Math('DisplayMath', only.text) })
      end
      return nil
    end,
    Image = function(img)
      img.attributes = {}
      img.caption = {}
      return img
    end,
    Table = function(tbl)
      return simple_table(tbl)
    end,
  }
  return doc
end
