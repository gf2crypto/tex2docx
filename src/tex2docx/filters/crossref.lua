-- \ref / \eqref / \cref / \Cref / \autoref -> numbers computed by LaTeX (.aux).
-- Status: implemented (M0; cleveref in M2). Links stay links to the target's bookmark.
-- pandoc alone prints "[eq:square]" for \eqref and its own numbering for \ref;
-- \cref it turns into a plain \ref and \Cref it drops, so normalize.py rewrites
-- them into \ref{cref:a,b} / \ref{Cref:a,b} / \ref{crefrange:a,b}. The object
-- type comes from cleveref's "label@cref" entries in the .aux (M.types), the
-- words from M.cref (cleveref's defaults for the language + the document's
-- \crefname). \autoref (hyperref) is rendered the same way, singular.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local t2d = require 't2d'

local function split(s)
  local out = {}
  for part in s:gmatch('[^,]+') do
    part = part:match('^%s*(.-)%s*$')
    if part ~= '' then out[#out + 1] = part end
  end
  return out
end

local function join(items, conj)
  local n = #items
  if n == 1 then return items[1] end
  if n == 2 then return items[1] .. ' ' .. conj.pair .. ' ' .. items[2] end
  local s = items[1]
  for i = 2, n - 1 do s = s .. conj.middle .. ' ' .. items[i] end
  return s .. ' ' .. conj.last .. ' ' .. items[n]
end

function Pandoc(doc)
  local M = t2d.load(doc.meta)
  if not M then return nil end
  local labels, types = M.labels or {}, M.types or {}
  local cref = M.cref or { names = {}, conjunctions = {} }
  local conj = cref.conjunctions or {}
  conj.pair, conj.middle, conj.last = conj.pair or 'and', conj.middle or ',', conj.last or 'and'

  local function fmt_number(ref, typ)
    local num = labels[ref]
    if typ == 'equation' then num = '(' .. num .. ')' end
    return num
  end

  -- "теорема 1.1", "теоремы 1.1 и 1.2", "теорема 1.1 и формула (1)"
  local function smart(refs, capital, range)
    local groups = {}
    for _, ref in ipairs(refs) do
      if not labels[ref] then
        t2d.report('warning', 'crossref.unresolved', ref)
        return nil
      end
      local typ = types[ref] or ''
      local g = groups[#groups]
      if g and g.typ == typ then
        g.nums[#g.nums + 1] = fmt_number(ref, typ)
      else
        groups[#groups + 1] = { typ = typ, nums = { fmt_number(ref, typ) } }
      end
    end
    local parts = {}
    for i, g in ipairs(groups) do
      local names = cref.names[g.typ]
      if not names then
        t2d.report('warning', 'crossref.cref-no-name', g.typ ~= '' and g.typ or '?')
        names = { sg = '', pl = '', Sg = '', Pl = '' }
      end
      local plural = #g.nums > 1 or range
      local word = plural and (i == 1 and capital and names.Pl or names.pl)
                   or (i == 1 and capital and names.Sg or names.sg)
      local nums = range and (g.nums[1] .. (conj.range or '--') .. g.nums[#g.nums]) or join(g.nums, conj)
      parts[#parts + 1] = (word ~= '' and (word .. '\194\160') or '') .. nums
    end
    return join(parts, conj)
  end

  return doc:walk {
    Link = function(el)
      local kind = el.attributes['reference-type']
      local ref = el.attributes['reference']
      if not kind or not ref then return nil end
      local text
      local cmd, rest = ref:match('^(%a+):(.+)$')
      if cmd == 'cref' or cmd == 'Cref' or cmd == 'crefrange' or cmd == 'Crefrange' then
        text = smart(split(rest), cmd:sub(1, 1) == 'C', cmd:find('range') ~= nil)
        if text then el.target = '#' .. split(rest)[1] end
      elseif kind == 'autoref' or kind == 'ref+label' then  -- pandoc 3.1 / 3.12
        text = smart({ ref }, false, false)
      else
        local num = labels[ref]
        if not num then
          t2d.report('warning', 'crossref.unresolved', ref)
          return nil
        end
        local inl = pandoc.List({})
        if kind == 'eqref' then inl:insert(pandoc.Str('(')) end
        inl:extend(t2d.ref(num, ref))
        if kind == 'eqref' then inl:insert(pandoc.Str(')')) end
        el.content = inl
        return el
      end
      if not text then return nil end
      el.content = { pandoc.Str(text) }
      return el
    end,
  }
end
