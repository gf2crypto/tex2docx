-- Block-level odds and ends pandoc's docx writer drops: description lists, the
-- abstract in place, center/flushright/flushleft alignment.
-- description lists as LaTeX sets them: "<bold term> text" in one paragraph.
-- Status: implemented (M2). pandoc's DefinitionList becomes Word's "Definition Term" /
-- "Definition" paragraphs (term on its own line), which also collides with the
-- Definition style of theorems. Each item becomes a paragraph starting with the
-- bold term; further blocks of the item follow as they are.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path

local t2d = require 't2d'

function Pandoc(doc)
  local M = t2d.load(doc.meta) or {}
  local abstract_title = (M.names or {}).abstract or 'Abstract'
  return doc:walk {
    Div = function(div)
      -- abstract kept in place (normalize renamed the environment), Word styles of pandoc
      local align = ({ center = 'Centered', flushright = 'Right Aligned', flushleft = 'Left Aligned' })[div.classes[1]]
      if align then
        div.attributes['custom-style'] = align
        return div
      end
      if div.classes[1] ~= 't2dabstract' then return nil end
      local out = { pandoc.Div({ pandoc.Para({ pandoc.Str(abstract_title) }) },
                               pandoc.Attr('', {}, { ['custom-style'] = 'Abstract Title' })) }
      out[#out + 1] = pandoc.Div(div.content, pandoc.Attr('', {}, { ['custom-style'] = 'Abstract' }))
      return out
    end,
    DefinitionList = function(dl)
      local out = {}
      for _, item in ipairs(dl.content) do
        local term, defs = item[1], item[2]
        local head = { pandoc.Strong(term) }
        local first = true
        for _, def in ipairs(defs) do
          for _, blk in ipairs(def) do
            if first and (blk.t == 'Para' or blk.t == 'Plain') then
              local inl = pandoc.List(head)
              inl:insert(pandoc.Space())
              inl:extend(blk.content)
              out[#out + 1] = pandoc.Para(inl)
              first = false
            else
              if first then out[#out + 1] = pandoc.Para(head); first = false end
              out[#out + 1] = blk
            end
          end
        end
        if first then out[#out + 1] = pandoc.Para(head) end
      end
      return out
    end,
  }
end
