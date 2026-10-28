-- Pseudocode lines (stages/algorithms.py markers) -> Word paragraphs in a box.
-- Status: implemented (M3). Div.t2dalgo: "T2DALGCAP: <label> text" -> paragraph of style
-- Algorithm Caption ("Алгоритм 1. text", number from the .aux); "T2DALG:<n>:<level>: ..."
-- -> paragraph of style Algorithm (bordered; consecutive ones merge into one box in Word)
-- with "<n>:" and one tab per nesting level.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local t2d = require 't2d'

local TAB = pandoc.RawInline('openxml', '<w:r><w:tab/></w:r>')

function Pandoc(doc)
  local M = t2d.load(doc.meta)
  if not M then return nil end
  local labels = M.labels or {}
  local name = (M.names or {}).algorithm or 'Algorithm'
  local sep = (M.names or {}).sep or '.'

  return doc:walk {
    Div = function(div)
      if div.classes[1] ~= 't2dalgo' then return nil end
      local out = {}
      for _, blk in ipairs(div.content) do
        if (blk.t == 'Para' or blk.t == 'Plain') and blk.content[1] and blk.content[1].t == 'Str' then
          local first = blk.content[1].text
          local rest = pandoc.List(blk.content)
          rest:remove(1)
          if rest[1] and rest[1].t == 'Space' then rest:remove(1) end
          if first == 'T2DALGCAP:' then
            local inl = pandoc.List({})
            local label
            if rest[1] and rest[1].t == 'Span' and rest[1].attributes.label then
              label = rest[1].attributes.label
              rest:remove(1)
              if rest[1] and rest[1].t == 'Space' then rest:remove(1) end
            end
            local head = name
            local num = label and labels[label]
            if num then
              local strong = pandoc.List({ pandoc.Str(head .. '\194\160') })
              strong:extend(t2d.number(num, 'algorithm', label, nil))
              inl:insert(pandoc.Strong(strong))
              inl:insert(pandoc.Str(sep .. ' '))
            else
              if label then t2d.report('warning', 'captions.unresolved', label) end
              inl:insert(pandoc.Strong({ pandoc.Str(head .. sep .. ' ') }))
            end
            inl:extend(rest)
            out[#out + 1] = pandoc.Div({ pandoc.Para(inl) },
              pandoc.Attr('', {}, { ['custom-style'] = 'Algorithm Caption' }))
          else
            local num, level = first:match('^T2DALG:(%d*):(%d+):$')
            if num then
              local inl = pandoc.List({})
              if num ~= '' then inl:insert(pandoc.Str(num .. ':')) end
              inl:insert(TAB)
              for _ = 1, tonumber(level) do inl:insert(TAB) end
              inl:extend(rest)
              out[#out + 1] = pandoc.Div({ pandoc.Para(inl) },
                pandoc.Attr('', {}, { ['custom-style'] = 'Algorithm' }))
            else
              out[#out + 1] = blk
            end
          end
        else
          out[#out + 1] = blk
        end
      end
      return out
    end,
  }
end
