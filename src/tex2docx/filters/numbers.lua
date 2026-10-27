-- Marker Spans (t2d.number / t2d.ref) -> text, or Word fields with live_numbers (ADR 0006).
-- Status: implemented (M3). Runs last, walking the document in order so that every
-- number knows the nearest heading above it.
-- Live mode: a number is a SEQ field inside a bookmark named after the label;
--   "2.1" within sections is REF(section bookmark) "." SEQ counter \s <section level>;
--   headings: level 1 -> SEQ h1, deeper -> REF(parent heading) "." SEQ hN \s N-1.
--   A reference is a REF field to the bookmark. Only plain numbers ("N", "N.N", "N.N.N")
--   qualify; \tag, "2.3a" and the like stay text.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local t2d = require 't2d'

local function esc(s)
  return (s:gsub('&', '&amp;'):gsub('<', '&lt;'):gsub('>', '&gt;'):gsub('"', '&quot;'))
end
local rpr = ''  -- run properties of the surrounding Strong/Emph (fields lose them otherwise)
local function run(text)
  return '<w:r>' .. rpr .. '<w:t xml:space="preserve">' .. esc(text) .. '</w:t></w:r>'
end
local function bookmark_name(label)
  return ('t2d_' .. label:gsub('[^%w]', '_')):sub(1, 40)
end
local function fld(instr, text)
  return '<w:fldSimple w:instr=" ' .. instr .. ' ">' .. run(text) .. '</w:fldSimple>'
end

function Pandoc(doc)
  local M = t2d.load(doc.meta)
  if not M then return nil end
  local live = M.live_numbers == true
  local section_level = math.floor(tonumber(M.section_level) or 1)
  local heading_bm = {}  -- level -> bookmark name of the nearest heading above
  local bookmark_id = 90000

  local function plain(span) return span.content end

  local function field_number(span)
    local a = span.attributes
    local num = pandoc.utils.stringify(span)
    if not num:match('^%d+[%d%.]*%d$') and not num:match('^%d+$') then return plain(span) end
    local label = a.label
    if label == '' then return plain(span) end
    local parts = {}
    for p in num:gmatch('%d+') do parts[#parts + 1] = p end
    local own = parts[#parts]
    local xml
    if a.counter == 'heading' then
      local level = tonumber(a.level) or 1
      if level == 1 or #parts == 1 then
        xml = fld('SEQ h' .. level .. ' \\* ARABIC', num)
      else
        local parent = heading_bm[level - 1]
        if not parent then return plain(span) end
        xml = fld('REF ' .. parent .. ' \\h', table.concat(parts, '.', 1, #parts - 1)) .. run('.') ..
              fld('SEQ h' .. level .. ' \\* ARABIC \\s ' .. (level - 1), own)
      end
    elseif #parts == 2 and a.within ~= '' then
      local parent = heading_bm[section_level]
      if not parent then return plain(span) end
      xml = fld('REF ' .. parent .. ' \\h', parts[1]) .. run('.') ..
            fld('SEQ ' .. a.counter .. ' \\* ARABIC \\s ' .. section_level, own)
    elseif #parts == 1 then
      xml = fld('SEQ ' .. a.counter .. ' \\* ARABIC', num)
    else
      return plain(span)
    end
    bookmark_id = bookmark_id + 1
    local name = bookmark_name(label)
    if a.counter == 'heading' then
      local level = tonumber(a.level) or 1
      heading_bm[level] = name
      for l = level + 1, 9 do heading_bm[l] = nil end
    end
    xml = '<w:bookmarkStart w:id="' .. bookmark_id .. '" w:name="' .. name .. '"/>' .. xml ..
          '<w:bookmarkEnd w:id="' .. bookmark_id .. '"/>'
    return { pandoc.RawInline('openxml', xml) }
  end

  local function field_ref(span)
    local num = pandoc.utils.stringify(span)
    local label = span.attributes.label
    if label == '' or not (num:match('^%d+[%d%.]*%d$') or num:match('^%d+$')) then return plain(span) end
    return { pandoc.RawInline('openxml', fld('REF ' .. bookmark_name(label) .. ' \\h', num)) }
  end

  local function convert(span)
    if span.classes:includes('t2d-num') then
      return live and field_number(span) or plain(span)
    elseif span.classes:includes('t2d-ref') then
      return live and field_ref(span) or plain(span)
    end
    return nil
  end

  -- Pass 1 only annotates markers inside bold/italic (theorem headers) with the run
  -- properties; pass 2 converts everything in document order (headings before the
  -- numbers that refer to them).
  local function annotate(props)
    return function(el)
      el.content = el.content:walk { Span = function(sp)
        if sp.classes:includes('t2d-num') or sp.classes:includes('t2d-ref') then
          sp.attributes.rpr = (sp.attributes.rpr or '') .. props
          return sp
        end
      end }
      return el
    end
  end
  doc = doc:walk { Strong = annotate('<w:b/><w:bCs/>'), Emph = annotate('<w:i/><w:iCs/>') }
  return doc:walk { Span = function(span)
    local props = span.attributes.rpr
    rpr = (props and props ~= '') and ('<w:rPr>' .. props .. '</w:rPr>') or ''
    return convert(span)
  end }
end
