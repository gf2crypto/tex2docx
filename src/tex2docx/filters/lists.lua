-- description lists as LaTeX sets them: "<bold term> text" in one paragraph.
-- Status: implemented (M2). pandoc's DefinitionList becomes Word's "Definition Term" /
-- "Definition" paragraphs (term on its own line), which also collides with the
-- Definition style of theorems. Each item becomes a paragraph starting with the
-- bold term; further blocks of the item follow as they are.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path

function Pandoc(doc)
  return doc:walk {
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
