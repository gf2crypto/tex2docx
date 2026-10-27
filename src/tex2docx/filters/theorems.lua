-- Theorem-like environments -> Word paragraph styles + LaTeX numbering.
-- Status: PARTIAL (M0).
--   done: number from .aux for labeled theorems; no number for \newtheorem*;
--         proof heading in the document language; custom-style by amsthm style.
--   TODO (M1): unlabeled numbered theorems (needs stages/autolabel.py);
--              optional note "(Основная)" formatting per amsthm style;
--              proof end mark as a right-aligned tab in postprocess.
--
-- What pandoc 3.1 gives us (see docs/pandoc-behavior.md):
--   Div(id=label, classes={env}) [ Para [ Strong[Str title, Space, Str "2"], Str ".", ... ] ]
--   remark style uses Emph instead of Strong; \newtheorem* still gets a number.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local t2d = require 't2d'

-- Replace or drop the trailing number inside the header Strong/Emph.
local function fix_number(header, number)
  local c = header.content
  local last = c[#c]
  if not (last and last.t == 'Str' and last.text:match('^[%d%.]+$')) then return end
  if number then
    last.text = number
  else
    c:remove(#c)
    if c[#c] and c[#c].t == 'Space' then c:remove(#c) end
  end
end

local function first_header(div)
  local para = div.content[1]
  if not para or (para.t ~= 'Para' and para.t ~= 'Plain') then return nil end
  local h = para.content[1]
  if h and (h.t == 'Strong' or h.t == 'Emph') then return h end
  return nil
end

function Pandoc(doc)
  local M = t2d.load(doc.meta)
  if not M then return nil end
  local decls, labels, styles = M.theorems or {}, M.labels or {}, M.styles or {}

  return doc:walk {
    Div = function(div)
      local env = div.classes[1]
      if env == 'proof' then
        local h = first_header(div)
        if h and pandoc.utils.stringify(h) == 'Proof.' then
          h.content = { pandoc.Str(M.proof_name .. '.') }
        end
        div.attributes['custom-style'] = 'Proof'
        return div
      end

      local d = decls[env]
      if not d then return nil end
      local h = first_header(div)
      if h then
        if not d.numbered then
          fix_number(h, nil)
        elseif div.identifier ~= '' and labels[div.identifier] then
          fix_number(h, labels[div.identifier])
        else
          t2d.report('warning', 'theorem.unlabeled', env)
        end
      else
        t2d.report('warning', 'theorem.no-header', env)
      end
      div.attributes['custom-style'] = styles[d.style] or 'Theorem'
      return div
    end,
  }
end
