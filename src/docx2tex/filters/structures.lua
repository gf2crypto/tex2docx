-- Word structures -> LaTeX structures (docx2tex). Status: M1.
-- Input: pandoc's reading of workdir/prepared.docx (stages/prepare.py): bookmarks are
-- U+E000 name U+E001 markers in the text, REF fields are links, tabs are U+E002.
-- Everything follows docs/docx2tex/roundtrip-contract.md:
--   * theorem-like styles (Theorem, Definition, Remark, ...) -> \begin{env}[note] ... \end{env},
--     env by the header word (meta theorem_envs, sidecar theorems); the number is dropped,
--     the label comes from the bookmarks; Proof -> \begin{proof} without the end sign;
--   * Equation paragraphs -> equation / \[ \] / align (consecutive aligned lines);
--   * links to bookmarks -> \ref, \eqref when the text is "(N)";
--   * headings lose the number ("1 Введение"), get \label from their bookmark, and are
--     starred when other headings of the level are numbered and this one is not;
--   * Image Caption / Table Caption / Algorithm Caption -> figure / table / algorithm;
--   * the bibliography heading with its numbered list -> thebibliography, "[1, 2]" -> \cite;
--   * Centered / Right Aligned / Left Aligned -> center / flushright / flushleft;
--   * Title / Author / Abstract (pandoc metadata) -> \title \author \maketitle, abstract;
--   * M0 leftovers: list Divs unwrapped, default numbering, formula-only paragraph ->
--     display math, images without size attributes, simple tables -> tabular.
-- Everything the filter cannot place is reported as [d2t] lines, never written as text.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local d2t = require 'd2t'

local MS, ME, MT = '\238\128\128', '\238\128\129', '\238\128\130' -- U+E000, U+E001, U+E002
-- U+E003 name U+E001: end of a bookmark that spans several paragraphs (theorem with its formulas)
local NBSP = '\194\160'
local END_SIGNS = { ['\226\151\187'] = true, ['\226\136\142'] = true, ['\226\150\161'] = true } -- ◻ ∎ □

local M = {}             -- meta from d2t-meta.json
local labels_map = {}    -- bookmark -> label (sidecar)
local theorem_envs = {}  -- header word (lower) -> env
local theorem_titles = {} -- env -> title as declared
local names = {}
local cites = {}
local has_bib = false
local numbered_levels = {}
local link_labels = {}   -- "(2.5)" -> label, from the references in the text (for subequations)
local header_labels = {} -- heading identifier -> its label (pandoc 3.12 points links at the identifier)
local bookmarked = {}    -- label -> true when a bookmark carries it

local stringify = pandoc.utils.stringify
local lower = pandoc.text.lower  -- string.lower knows no Cyrillic

local function report(level, code, detail) d2t.report(level, code, detail) end

local function write_inlines(inlines)
  local s = pandoc.write(pandoc.Pandoc({ pandoc.Plain(inlines) }), 'latex')
  return (s:gsub('%s+$', ''))
end

local function write_blocks(blocks)
  local s = pandoc.write(pandoc.Pandoc(blocks), 'latex')
  return (s:gsub('%s+$', ''))
end

local function trim(s) return (s:gsub('^[%s' .. NBSP .. ']+', ''):gsub('[%s' .. NBSP .. ']+$', '')) end

local function escape_pattern(s) return (s:gsub('%W', '%%%0')) end

-- ---------------------------------------------------------------------------
-- labels

-- bookmark name -> label: the sidecar, else t2d_<label> as tex2docx builds it, else the
-- name itself (a bookmark the author made in Word). nil: pandoc 3.12's hashed names for
-- Div identifiers ("_" + 39 hex digits), Word's own "_Toc..." and autolabels.
local function resolve_label(name)
  if name == nil or name == '' then return nil end
  if labels_map[name] then return labels_map[name] end
  if name:match('^t2d_t2d_auto') or name:match('^t2d:auto:') then return nil end
  if name:match('^t2d_') then
    report('warning', 'label.unmapped', name)
    return name:sub(5)
  end
  if name:match('^_') then return nil end
  return name
end

local name_labels = {}  -- bookmark name -> label learned from the document (pass 2)

-- Str with markers -> Str pieces and marker Spans (t2d-label / t2d-tab)
local function explode(text)
  local out, pos = {}, 1
  while true do
    local s = text:find('\238\128', pos, true)
    if not s then break end
    local third = text:sub(s + 2, s + 2)
    if third == '\128' then
      local e = text:find(ME, s + 3, true)
      if not e then break end
      if s > pos then out[#out + 1] = pandoc.Str(text:sub(pos, s - 1)) end
      local name = text:sub(s + 3, e - 1)
      local label = resolve_label(name)
      if label then bookmarked[label] = true end
      out[#out + 1] = pandoc.Span({}, pandoc.Attr('', { 't2d-label' }, { label = label or '', name = name }))
      pos = e + 3
    elseif third == '\130' then
      if s > pos then out[#out + 1] = pandoc.Str(text:sub(pos, s - 1)) end
      out[#out + 1] = pandoc.Span({}, pandoc.Attr('', { 't2d-tab' }))
      pos = s + 3
    elseif third == '\131' then
      local e = text:find(ME, s + 3, true)
      if not e then break end
      if s > pos then out[#out + 1] = pandoc.Str(text:sub(pos, s - 1)) end
      out[#out + 1] = pandoc.Span({}, pandoc.Attr('', { 't2d-label-end' }, { name = text:sub(s + 3, e - 1) }))
      pos = e + 3
    else
      pos = s + 2
    end
  end
  if pos == 1 then return nil end
  if pos <= #text then out[#out + 1] = pandoc.Str(text:sub(pos)) end
  return out
end

local function split_markers(inlines)
  local out, changed = pandoc.List(), false
  for _, x in ipairs(inlines) do
    if x.t == 'Str' then
      local pieces = explode(x.text)
      if pieces then
        changed = true
        out:extend(pieces)
      else
        out:insert(x)
      end
    elseif x.t == 'Span' and x.classes:includes('anchor') and #x.content == 0 then
      changed = true -- pandoc's own anchor for a referenced bookmark: the marker carries it
    else
      out:insert(x)
    end
  end
  return changed and out or nil
end

local function is_label(x) return x.t == 'Span' and x.classes:includes('t2d-label') end

-- the label a marker stands for: resolved at once, or (Word's own cross-reference bookmarks
-- _RefNNN) made up from the context in pass 2
local function label_of(sp)
  local l = sp.attributes.label
  if l ~= '' then return l end
  local name = sp.attributes.name
  if name:match('^_Ref%d+$') then return name_labels[name] end
  return nil
end
local function is_tab(x) return x.t == 'Span' and x.classes:includes('t2d-tab') end
local function is_end(x) return x.t == 'Span' and x.classes:includes('t2d-label-end') end

-- index of the block (within blocks, from index i on) that holds the end marker of one of the names
local function find_end(blocks, i, names)
  local want = {}
  for _, n in ipairs(names) do want[n] = true end
  for k = i, #blocks do
    local hit = false
    blocks[k]:walk { Span = function(sp) if is_end(sp) and want[sp.attributes.name] then hit = true end end }
    if hit then return k end
  end
  return nil
end

-- remove the label spans from blocks/inlines (a walked copy is returned too);
-- returns the labels, the copy, and the raw bookmark names
local function take_labels(obj)
  local found, names, seen = {}, {}, {}
  local function f(sp)
    if is_label(sp) then
      local l = label_of(sp)
      if l and not seen[l] then seen[l] = true; found[#found + 1] = l end
      names[#names + 1] = sp.attributes.name
      return {}
    end
  end
  local res
  if obj.walk then res = obj:walk { Span = f } else res = pandoc.Inlines(obj):walk { Span = f } end
  return found, res, names
end

local function label_cmds(labels)
  local s = ''
  for _, l in ipairs(labels) do s = s .. '\\label{' .. l .. '}' end
  return s
end

-- drop marker spans and empty strings; collapse doubled spaces; merge Strong/Emph runs that
-- a bookmark (marker run) split in two ("Теорема " + "1.2")
local function clean_inlines(inlines)
  local out = pandoc.List()
  for _, x in ipairs(inlines) do
    if is_tab(x) or is_label(x) or is_end(x) or (x.t == 'Str' and x.text == '') then
      -- skip
    elseif x.t == 'Space' and (#out == 0 or out[#out].t == 'Space') then
      -- skip
    elseif (x.t == 'Strong' or x.t == 'Emph') and #out > 0 and out[#out].t == x.t then
      local merged = pandoc.List(out[#out].content)
      merged:extend(x.content)
      out[#out] = x.t == 'Strong' and pandoc.Strong(merged) or pandoc.Emph(merged)
    elseif (x.t == 'Strong' or x.t == 'Emph') and #out > 1 and out[#out].t == 'Space' and out[#out - 1].t == x.t then
      local merged = pandoc.List(out[#out - 1].content)
      merged:insert(pandoc.Space())
      merged:extend(x.content)
      out:remove(#out)
      out[#out] = x.t == 'Strong' and pandoc.Strong(merged) or pandoc.Emph(merged)
    else
      out:insert(x)
    end
  end
  while #out > 0 and out[#out].t == 'Space' do out:remove(#out) end
  return out
end

-- ---------------------------------------------------------------------------
-- block helpers

-- style names as tex2docx writes them; Word's own ids come lower-cased ("caption")
local CANONICAL = {}
for _, name in ipairs({ 'Theorem', 'Definition', 'Remark', 'Lemma', 'Corollary', 'Proposition', 'Example',
  'Conjecture', 'Claim', 'Problem', 'Proof', 'Equation', 'Captioned Figure', 'Image Caption', 'Table Caption',
  'Algorithm Caption', 'Algorithm', 'Bibliography', 'Centered', 'Right Aligned', 'Left Aligned', 'Abstract',
  'Abstract Title', 'Title', 'Author', 'Date', 'Body Text', 'First Paragraph', 'Normal', 'Compact',
  'List Bullet', 'List Number', 'List Paragraph' }) do
  CANONICAL[name:lower()] = name
end
CANONICAL['caption'] = 'Image Caption'

local function style_of(b)
  if b.t ~= 'Div' then return nil end
  local st = b.attributes['custom-style']
  if not st and b.identifier == '' and #b.classes == 1 then st = b.classes[1] end
  if not st then return nil end
  return CANONICAL[st:lower()] or st
end

local function only_math(para)
  if para.t ~= 'Para' and para.t ~= 'Plain' then return nil end
  local only
  for _, x in ipairs(para.content) do
    if x.t == 'Math' then
      if only then return nil end
      only = x
    elseif x.t ~= 'Space' and x.t ~= 'SoftBreak' and not is_label(x) and not is_tab(x) and not is_end(x) then
      return nil
    end
  end
  return only
end

local function first_image(block)
  local img
  block:walk { Image = function(i) img = img or i end }
  return img
end

local function raw(s) return pandoc.RawBlock('latex', s) end

-- ---------------------------------------------------------------------------
-- equations

-- texmath wraps a line of an align (one row, &) or a multi-line block (rows) in a matrix
local function strip_matrix(tex)
  local inner = tex:match('^%s*\\begin{matrix}%s*(.-)%s*\\end{matrix}%s*$')
    or tex:match('^%s*\\begin{aligned}%s*(.-)%s*\\end{aligned}%s*$')  -- pandoc 3.12
  if not inner then return tex, false, false end
  local rows = inner:find('\\\\') ~= nil
  return inner, (not rows) and inner:find('&') ~= nil, rows
end

-- Equation paragraph: formula, then the number "(2.1)" / a tag "(A)" / "B" (tex2docx
-- prints \tag and \tag* that way); strict (Word paragraph of one formula): no text at all
local function parse_equation(para, strict)
  local labels, content = take_labels(pandoc.Inlines(para.content))
  local math
  local strs = {}
  for _, x in ipairs(content) do
    if x.t == 'Math' then
      if math then return nil end
      math = x
    elseif x.t == 'Str' then
      strs[#strs + 1] = x.text -- the number: "(", bookmark, "1.1", ")" come as several Str
    elseif x.t ~= 'Space' and not is_tab(x) and not is_end(x) then
      return nil
    end
  end
  if not math then return nil end
  local text = trim(table.concat(strs))
  if strict and text ~= '' then return nil end
  local num, tag
  if text ~= '' then
    local inner = text:match('^%((.+)%)$')
    if inner and inner:match('^%d[%d%.]*%a?$') then
      num = text
    elseif inner then
      num, tag = text, '\\tag{' .. inner .. '}'
    else
      num, tag = text, '\\tag*{' .. text .. '}'
    end
  end
  local body, aligned, rows = strip_matrix(math.text)
  body = trim(body:gsub('%s*\n%s*', ' '))
  return { body = body, aligned = aligned, rows = rows, num = num, tag = tag or '', labels = labels }
end

local function sub_base(it)
  return it.num and it.num:match('^%((%d[%d%.]*)%a%)$') or nil
end

local emit_equations -- forward

-- a run of "(2.5a)", "(2.5b)": subequations, labelled from a reference "(2.5)" if there is one
local function emit_subequations(items)
  local base = sub_base(items[1])
  local label = link_labels['(' .. base .. ')']
  local head = '\\begin{subequations}'
  if label and not bookmarked[label] then head = head .. '\\label{' .. label .. '}' end
  local out = { raw(head) }
  for _, b in ipairs(emit_equations(items, true)) do out[#out + 1] = b end
  out[#out + 1] = raw('\\end{subequations}')
  return out
end

emit_equations = function(items, inside_sub)
  local out = {}
  local j = 1
  while j <= #items do
    if not inside_sub and sub_base(items[j]) then
      local base, k = sub_base(items[j]), j
      while k < #items and sub_base(items[k + 1]) == base do k = k + 1 end
      local slice = {}
      for q = j, k do slice[#slice + 1] = items[q] end
      for _, b in ipairs(emit_subequations(slice)) do out[#out + 1] = b end
      j = k + 1
    elseif items[j].aligned then
      local k = j
      while k < #items and items[k + 1].aligned do k = k + 1 end
      local numbered = false
      for q = j, k do if items[q].num then numbered = true end end
      local lines = {}
      for q = j, k do
        local it = items[q]
        local line = '  ' .. it.body
        if numbered then
          if it.num then line = line .. label_cmds(it.labels) .. it.tag else line = line .. ' \\notag' end
        end
        lines[#lines + 1] = line
      end
      local env = numbered and 'align' or 'align*'
      out[#out + 1] = raw('\\begin{' .. env .. '}\n' .. table.concat(lines, ' \\\\\n') .. '\n\\end{' .. env .. '}')
      j = k + 1
    else
      local it = items[j]
      if it.rows then
        -- several rows under one number: aligned inside equation (with &) or multline
        local lines = {}
        for row in (it.body .. ' \\\\ '):gmatch('(.-)%s*\\\\%s*') do
          if trim(row) ~= '' then lines[#lines + 1] = '  ' .. trim(row) end
        end
        local body = table.concat(lines, ' \\\\\n')
        if it.body:find('&') then
          local env = it.num and 'equation' or 'equation*'
          out[#out + 1] = raw('\\begin{' .. env .. '}' .. label_cmds(it.labels) .. it.tag .. '\n\\begin{aligned}\n' .. body ..
            '\n\\end{aligned}\n\\end{' .. env .. '}')
        else
          local env = it.num and 'multline' or 'multline*'
          out[#out + 1] = raw('\\begin{' .. env .. '}' .. label_cmds(it.labels) .. it.tag .. '\n' .. body .. '\n\\end{' .. env .. '}')
        end
      elseif it.num then
        out[#out + 1] = raw('\\begin{equation}' .. label_cmds(it.labels) .. it.tag .. '\n  ' .. it.body .. '\n\\end{equation}')
      else
        out[#out + 1] = raw('\\[\n  ' .. it.body .. '\n\\]')
      end
      j = j + 1
    end
  end
  return out
end

-- ---------------------------------------------------------------------------
-- theorems and proofs

-- Para of a theorem: head (Strong/Emph "Name N.M"), ".", optional "(note).", body.
local function split_theorem_head(para)
  local ins = clean_inlines(para.content)
  local head = ins[1]
  if not head or (head.t ~= 'Strong' and head.t ~= 'Emph') then return nil end
  local htext = trim(stringify(head))
  local title = trim((htext:gsub('[%s' .. NBSP .. ']*[%d%.]+%.?$', '')))
  if title == '' then return nil end
  local i = 2
  -- "." right after the head
  if ins[i] and ins[i].t == 'Str' and ins[i].text:match('^%.') then
    ins[i].text = ins[i].text:sub(2)
    if ins[i].text == '' then i = i + 1 end
  end
  while ins[i] and ins[i].t == 'Space' do i = i + 1 end
  local note
  if ins[i] and ins[i].t == 'Str' and ins[i].text:match('^%(') then
    local parts, k = {}, i
    while ins[k] do
      parts[#parts + 1] = ins[k]
      if ins[k].t == 'Str' and ins[k].text:match('%)%.?$') then break end
      k = k + 1
    end
    if ins[k] then
      note = stringify(pandoc.Inlines(parts)):gsub('^%(', ''):gsub('%)%.?$', '')
      i = k + 1
      while ins[i] and ins[i].t == 'Space' do i = i + 1 end
    end
  end
  local rest = pandoc.List()
  for k = i, #ins do rest:insert(ins[k]) end
  return title, note, rest
end

-- the body of a plain-style theorem is italic in Word: unwrap when every word is in Emph
local function unwrap_emph(inlines)
  local any = false
  for _, x in ipairs(inlines) do
    if x.t == 'Emph' then any = true
    elseif x.t == 'Str' or x.t == 'Strong' or x.t == 'Link' or x.t == 'Quoted' then return inlines end
  end
  if not any then return inlines end
  local out = pandoc.List()
  for _, x in ipairs(inlines) do
    if x.t == 'Emph' then out:extend(x.content) else out:insert(x) end
  end
  return out
end

local function env_for(title, style)
  local key = lower(title)
  if theorem_envs[key] then return theorem_envs[key] end
  local first = key:match('^(%S+)')
  if first and theorem_envs[first] then return theorem_envs[first] end
  report('warning', 'theorem.unknown-name', title)
  return (lower(style):gsub('%s+', ''))
end

local in_theorem = 0  -- inside a theorem/proof the "bold word" heuristics are off

local function emit_theorem(div, style, process, extra)
  local labels, body = take_labels(div)
  local inner = pandoc.List(body.content)
  if extra then inner:extend(extra) end
  in_theorem = in_theorem + 1
  local content = process(inner)
  in_theorem = in_theorem - 1
  local first = content[1]
  if not first or first.t ~= 'Para' then
    report('warning', 'theorem.no-head', style)
    return content
  end
  local title, note, rest = split_theorem_head(first)
  if not title then
    report('warning', 'theorem.no-head', style)
    return content
  end
  local env = env_for(title, style)
  if not theorem_titles[env] then
    theorem_titles[env] = title
    report('info', 'theorem.env', env .. '|' .. title)
  end
  local out = { raw('\\begin{' .. env .. '}' .. (note and ('[' .. note .. ']') or '') .. label_cmds(labels)) }
  rest = unwrap_emph(rest)
  if #rest > 0 then out[#out + 1] = pandoc.Para(rest) end
  for k = 2, #content do
    local b = content[k]
    if b.t == 'Para' then b.content = unwrap_emph(clean_inlines(b.content)) end
    out[#out + 1] = b
  end
  out[#out + 1] = raw('\\end{' .. env .. '}')
  return out
end

-- a paragraph typed in Word without the styles: bold "Теорема 3." / italic "Доказательство."
local PROOF_NAMES = { 'Доказательство', 'Proof' }

local function text_theorem(para)
  local ins = clean_inlines(para.content)
  local head = ins[1]
  if not head or (head.t ~= 'Strong' and head.t ~= 'Emph') then return nil end
  local text = trim(stringify(head))
  local title = text:match('^(.-)[%s' .. NBSP .. ']*[%d%.]*%.?$')
  if not title or title == '' then return nil end
  local key = lower(title)
  if theorem_envs[key] then return title, key end
  return nil
end

local function text_proof(para)
  local ins = clean_inlines(para.content)
  local head = ins[1]
  if not head or (head.t ~= 'Strong' and head.t ~= 'Emph') then return false end
  local text = trim(stringify(head)):gsub('%.$', '')
  if names.proof and text == names.proof then return true end
  for _, n in ipairs(PROOF_NAMES) do if text == n then return true end end
  return false
end

local function emit_proof(div, process)
  local _, body = take_labels(div)
  in_theorem = in_theorem + 1
  local content = process(body.content)
  in_theorem = in_theorem - 1
  local first = content[1]
  if first and first.t == 'Para' then
    local ins = clean_inlines(first.content)
    local h = ins[1]
    if h and (h.t == 'Emph' or h.t == 'Strong') then
      ins:remove(1)
      while ins[1] and (ins[1].t == 'Space' or (ins[1].t == 'Str' and ins[1].text == '.')) do ins:remove(1) end
    end
    first.content = ins
  end
  local last = content[#content]
  if last and (last.t == 'Para' or last.t == 'Plain') then
    local ins = clean_inlines(last.content)
    local x = ins[#ins]
    if x and x.t == 'Str' and END_SIGNS[x.text] then
      ins:remove(#ins)
      while #ins > 0 and ins[#ins].t == 'Space' do ins:remove(#ins) end
    end
    last.content = ins
    if #ins == 0 then content[#content] = nil end
  end
  local out = { raw('\\begin{proof}') }
  for _, b in ipairs(content) do out[#out + 1] = b end
  out[#out + 1] = raw('\\end{proof}')
  return out
end

-- ---------------------------------------------------------------------------
-- captions: figures, tables, algorithms

local function caption_text(para, kinds)
  local labels, content = take_labels(pandoc.Inlines(para.content))
  content = clean_inlines(content)
  -- "Алгоритм 1." in bold (Algorithm Caption): drop the bold head and its period
  local head = content[1]
  if head and (head.t == 'Strong' or head.t == 'Emph') then
    local text = trim(stringify(head))
    for _, name in ipairs(kinds) do
      if name and name ~= '' and text:match('^' .. escape_pattern(name) .. '[%s' .. NBSP .. ']*%d+%.?$') then
        content:remove(1)
        if content[1] and content[1].t == 'Str' and content[1].text:match('^[%.:]') then
          content[1].text = content[1].text:sub(2)
          if content[1].text == '' then content:remove(1) end
        end
        while content[1] and content[1].t == 'Space' do content:remove(1) end
        break
      end
    end
  end
  local tex = write_inlines(content)
  for _, name in ipairs(kinds) do
    if name and name ~= '' then
      local pat = '^' .. escape_pattern(name) .. '[~%s]*%d+[%.:]?[~%s]*%-*[~%s]*'
      local stripped, n = tex:gsub(pat, '')
      if n > 0 then return trim(stripped), labels end
    end
  end
  return trim(tex), labels
end

local FIGURE_NAMES = { 'Рис.', 'Рисунок', 'Figure', 'Fig.' }
local TABLE_NAMES = { 'Таблица', 'Табл.', 'Table' }
local ALGORITHM_NAMES = { 'Алгоритм', 'Algorithm' }

local function with_name(first, list)
  local out = { first }
  for _, n in ipairs(list) do out[#out + 1] = n end
  return out
end

local function emit_figure(img, caption_para)
  local lines = { '\\begin{figure}[ht]', '  \\centering', '  \\includegraphics{' .. img.src .. '}' }
  if caption_para then
    local text, labels = caption_text(caption_para, with_name(names.figure, FIGURE_NAMES))
    lines[#lines + 1] = '  \\caption{' .. text .. '}' .. label_cmds(labels)
  end
  lines[#lines + 1] = '\\end{figure}'
  return raw(table.concat(lines, '\n'))
end

local function cell_text(cell)
  local blocks = cell.contents or cell.content
  local parts = {}
  for _, b in ipairs(blocks) do
    parts[#parts + 1] = pandoc.write(pandoc.Pandoc({ b }), 'latex'):gsub('\n$', '')
  end
  return table.concat(parts, ' ')
end

-- plain tabular with l columns and \hline, when no cell spans; nil otherwise
-- tabular with | borders and \hline; merged cells -> \multicolumn / \multirow (with \cline
-- where a row span continues); a column whose text is long gets p{<width>\linewidth}
local LONG_CELL = 40

local function tabular_lines(tbl)
  local ncols = #tbl.colspecs
  if ncols == 0 then return nil end
  local grid = {}       -- grid[r][c] = { origin = cell, dr = , dc = }
  local nrows = 0
  local longest = {}    -- per column: longest cell text
  local has_multirow = false
  local function add_rows(rowlist)
    for _, row in ipairs(rowlist) do
      nrows = nrows + 1
      local r = nrows
      grid[r] = grid[r] or {}
      local c = 1
      for _, cell in ipairs(row.cells) do
        while grid[r][c] do c = c + 1 end
        local text = cell_text(cell)
        local cs, rs = math.max(1, cell.col_span), math.max(1, cell.row_span)
        local origin = { text = text, cols = cs, rows = rs }
        longest[c] = math.max(longest[c] or 0, utf8.len(text) or #text)
        if rs > 1 then has_multirow = true end
        for dr = 0, rs - 1 do
          grid[r + dr] = grid[r + dr] or {}
          for dc = 0, cs - 1 do grid[r + dr][c + dc] = { origin = origin, dr = dr, dc = dc } end
        end
        c = c + cs
      end
    end
  end
  add_rows(tbl.head.rows)
  for _, body in ipairs(tbl.bodies) do add_rows(body.body) end
  add_rows(tbl.foot.rows)
  if has_multirow then report('info', 'table.multirow', '') end
  local colspec = {}
  for c = 1, ncols do
    local w = tbl.colspecs[c] and tbl.colspecs[c][2]
    if (longest[c] or 0) > LONG_CELL then
      local frac = (type(w) == 'number' and w > 0) and w or (1 / ncols)
      colspec[c] = string.format('p{%.2f\\linewidth}', frac * 0.9)
    else
      colspec[c] = 'l'
    end
  end
  local lines = { '\\begin{tabular}{|' .. table.concat(colspec, '|') .. '|}', '\\hline' }
  for r = 1, nrows do
    local cells = {}
    local c = 1
    while c <= ncols do
      local g = grid[r][c]
      if not g then
        cells[#cells + 1] = ''
        c = c + 1
      else
        local o = g.origin
        local text = g.dr == 0 and o.text or ''
        if g.dr == 0 and o.rows > 1 then text = '\\multirow{' .. o.rows .. '}{*}{' .. text .. '}' end
        if o.cols > 1 then
          text = '\\multicolumn{' .. o.cols .. '}{' .. (c == 1 and '|' or '') .. 'l|}{' .. text .. '}'
        end
        cells[#cells + 1] = text
        c = c + o.cols
      end
    end
    lines[#lines + 1] = table.concat(cells, ' & ') .. ' \\\\'
    -- the rule under the row: \hline, or \cline around cells whose row span goes on
    local open = false
    for cc = 1, ncols do
      local g = grid[r][cc]
      if g and g.origin.rows - 1 > g.dr then open = true end
    end
    if not open then
      lines[#lines + 1] = '\\hline'
    else
      local a = nil
      for cc = 1, ncols + 1 do
        local g = grid[r][cc]
        local continues = cc <= ncols and g and (g.origin.rows - 1 > g.dr)
        if cc <= ncols and not continues then
          a = a or cc
        elseif a then
          lines[#lines + 1] = '\\cline{' .. a .. '-' .. (cc - 1) .. '}'
          a = nil
        end
      end
    end
  end
  lines[#lines + 1] = '\\end{tabular}'
  return lines
end

local function emit_table(tbl, caption_para)
  local body = tabular_lines(tbl)
  if not body then
    report('warning', 'table.empty', '')
    return {}
  end
  local lines = {}
  if caption_para then
    local text, labels = caption_text(caption_para, with_name(names.table, TABLE_NAMES))
    lines = { '\\begin{table}[ht]', '  \\centering', '  \\caption{' .. text .. '}' .. label_cmds(labels) }
    for _, l in ipairs(body) do lines[#lines + 1] = '  ' .. l end
    lines[#lines + 1] = '\\end{table}'
  else
    lines = { '\\begin{center}' }
    for _, l in ipairs(body) do lines[#lines + 1] = l end
    lines[#lines + 1] = '\\end{center}'
  end
  return { raw(table.concat(lines, '\n')) }
end

-- algorithmic: one Algorithm paragraph = one line "N:" tabs (level + 1) text with bold keywords
local OPENERS = { ['if'] = 'EndIf', ['for'] = 'EndFor', ['for all'] = 'EndFor', ['for each'] = 'EndFor',
  ['while'] = 'EndWhile', ['loop'] = 'EndLoop', ['function'] = 'EndFunction', ['procedure'] = 'EndProcedure',
  ['repeat'] = 'Until' }
local CLOSERS = { ['end if'] = 'EndIf', ['end for'] = 'EndFor', ['end while'] = 'EndWhile', ['end loop'] = 'EndLoop',
  ['end function'] = 'EndFunction', ['end procedure'] = 'EndProcedure' }

local function strong_text(x)
  if x and x.t == 'Strong' then return trim(stringify(x)):lower() end
  return nil
end

-- inlines between index i and the next Strong (exclusive); returns tex, index of that Strong
local function until_strong(ins, i)
  local parts = pandoc.List()
  local k = i
  while ins[k] and ins[k].t ~= 'Strong' do parts:insert(ins[k]); k = k + 1 end
  return trim(write_inlines(clean_inlines(parts))), k
end

local function algorithm_line(para)
  local ins = pandoc.List(para.content)
  local numbered = false
  local level, i = 0, 1
  while ins[i] and (ins[i].t == 'Space' or is_tab(ins[i]) or is_label(ins[i])) do
    if is_tab(ins[i]) then level = level + 1 end
    i = i + 1
  end
  if ins[i] and ins[i].t == 'Str' and ins[i].text:match('^%d+:$') then
    numbered = true
    i = i + 1
  end
  local tabs = 0
  while ins[i] and (ins[i].t == 'Space' or is_tab(ins[i])) do
    if is_tab(ins[i]) then tabs = tabs + 1 end
    i = i + 1
  end
  level = level + tabs
  if level > 0 then level = level - 1 end
  local rest = pandoc.List()
  for k = i, #ins do rest:insert(ins[k]) end
  rest = clean_inlines(rest)
  local kw = strong_text(rest[1])
  local line = { level = level, numbered = numbered, kind = 'State', text = '' }
  if kw == 'require:' or kw == 'ensure:' then
    line.kind = kw == 'require:' and 'Require' or 'Ensure'
    rest:remove(1)
    line.text = '\\' .. line.kind .. ' ' .. write_inlines(clean_inlines(rest))
    line.numbered = false
  elseif kw == 'if' or kw == 'else if' or kw == 'for' or kw == 'for all' or kw == 'for each' or kw == 'while' then
    local cond, k = until_strong(rest, 2)
    local cmd = ({ ['if'] = 'If', ['else if'] = 'ElsIf', ['for'] = 'For', ['for all'] = 'ForAll',
      ['for each'] = 'ForAll', ['while'] = 'While' })[kw]
    line.kind = cmd
    line.text = '\\' .. cmd .. '{' .. cond .. '}'
    local tail = pandoc.List()
    for q = k + 1, #rest do tail:insert(rest[q]) end
    tail = clean_inlines(tail)
    if #tail > 0 then line.text = line.text .. ' ' .. write_inlines(tail) end
  elseif kw == 'until' then
    rest:remove(1)
    line.kind = 'Until'
    line.text = '\\Until{' .. write_inlines(clean_inlines(rest)) .. '}'
  elseif kw == 'function' or kw == 'procedure' then
    line.kind = kw == 'function' and 'Function' or 'Procedure'
    local name, args = '', ''
    local k = 2
    while rest[k] and rest[k].t == 'Space' do k = k + 1 end
    local x = rest[k]
    if x and (x.t == 'SmallCaps' or x.t == 'Str') then
      name = stringify(x)
      local tail = pandoc.List()
      for q = k + 1, #rest do tail:insert(rest[q]) end
      args = trim(write_inlines(clean_inlines(tail)))
      if x.t == 'Str' then -- "Name(args)" in one Str
        local n2, a2 = name:match('^([^(]+)%((.*)$')
        if n2 then name, args = n2, a2 .. args end
      end
      args = (args:gsub('^%(', ''):gsub('%)$', ''))
    end
    line.text = '\\' .. line.kind .. '{' .. name .. '}{' .. args .. '}'
  elseif kw == 'else' then
    line.kind = 'Else'
    line.text = '\\Else'
  elseif kw == 'repeat' or kw == 'loop' then
    line.kind = kw == 'repeat' and 'Repeat' or 'Loop'
    line.text = '\\' .. line.kind
  elseif kw and CLOSERS[kw] then
    line.kind = CLOSERS[kw]
    line.text = '\\' .. line.kind
  elseif kw == 'return' then
    rest:remove(1)
    line.text = '\\State \\Return ' .. write_inlines(clean_inlines(rest))
  else
    line.text = '\\State ' .. write_inlines(rest)
  end
  return line
end

local function emit_algorithm(caption_para, line_paras)
  local lines, numbered = {}, false
  for _, p in ipairs(line_paras) do
    local l = algorithm_line(p)
    lines[#lines + 1] = l
    if l.numbered then numbered = true end
  end
  local out = { '\\begin{algorithm}[H]' }
  if caption_para then
    local text, labels = caption_text(caption_para, with_name(names.algorithm, ALGORITHM_NAMES))
    out[#out + 1] = '  \\caption{' .. text .. '}' .. label_cmds(labels)
  end
  out[#out + 1] = '  \\begin{algorithmic}' .. (numbered and '[1]' or '')
  -- close blocks that Word shows by indentation only ([noend] documents)
  local stack = {} -- { closer = 'EndIf', level = n }
  local function closes(kind) return kind:match('^End') or kind == 'Until' end
  local function continues(kind) return kind == 'Else' or kind == 'ElsIf' end
  for _, l in ipairs(lines) do
    if closes(l.kind) then
      if #stack > 0 then stack[#stack] = nil end
    else
      while #stack > 0 and l.level <= stack[#stack].level and not (continues(l.kind) and l.level == stack[#stack].level) do
        out[#out + 1] = string.rep('  ', #stack + 1) .. '\\' .. stack[#stack].closer
        stack[#stack] = nil
      end
    end
    out[#out + 1] = string.rep('  ', #stack + 2) .. l.text
    if OPENERS[l.kind:lower()] then
      stack[#stack + 1] = { closer = OPENERS[l.kind:lower()], level = l.level }
    end
  end
  while #stack > 0 do
    out[#out + 1] = string.rep('  ', #stack + 1) .. '\\' .. stack[#stack].closer
    stack[#stack] = nil
  end
  out[#out + 1] = '  \\end{algorithmic}'
  out[#out + 1] = '\\end{algorithm}'
  return raw(table.concat(out, '\n'))
end

-- ---------------------------------------------------------------------------
-- bibliography and citations

local BIB_TITLES = { 'Список литературы', 'Литература', 'Библиографический список', 'References', 'Bibliography' }

local function is_bib_header(b)
  if b.t ~= 'Header' then return false end
  local text = trim(stringify(b.content))
  if names.bibliography and text == names.bibliography then return true end
  for _, t in ipairs(BIB_TITLES) do if text == t then return true end end
  return false
end

local function cite_key(n) return cites[n] or ('bib:' .. n) end

local function emit_thebibliography(entries)
  local widest = #entries < 10 and '9' or (#entries < 100 and '99' or '999')
  local out = { '\\begin{thebibliography}{' .. widest .. '}' }
  for n, blocks in ipairs(entries) do
    out[#out + 1] = '\\bibitem{' .. cite_key(tostring(n)) .. '} ' .. write_blocks(blocks)
  end
  out[#out + 1] = '\\end{thebibliography}'
  return raw(table.concat(out, '\n'))
end

-- "[1]", "[1, 2]", "[2, гл. 2]" in the running text -> \cite
local function cite_inlines(inlines)
  local out, buf, changed = pandoc.List(), {}, false
  local function flush()
    if #buf == 0 then return end
    local text = table.concat(buf)
    buf = {}
    local pos = 1
    local pieces = {}
    while true do
      local s, e, inner = text:find('%[([^%[%]]-)%]', pos)
      if not s then break end
      local nums, note = {}, nil
      local ok = true
      for part in (inner .. ','):gmatch('%s*([^,]-)%s*,') do
        local p = trim(part)
        if p:match('^%d+$') then
          nums[#nums + 1] = p
        elseif #nums > 0 and not note then
          note = p
        else
          ok = false
          break
        end
      end
      if ok and #nums > 0 then
        changed = true
        pieces[#pieces + 1] = text:sub(pos, s - 1)
        local keys = {}
        for _, n in ipairs(nums) do keys[#keys + 1] = cite_key(n) end
        local opt = note and ('[' .. note:gsub(NBSP, '~') .. ']') or ''
        pieces[#pieces + 1] = { '\\cite' .. opt .. '{' .. table.concat(keys, ',') .. '}' }
        pos = e + 1
      else
        pos = e
      end
    end
    pieces[#pieces + 1] = text:sub(pos)
    for _, p in ipairs(pieces) do
      if type(p) == 'table' then
        out:insert(pandoc.RawInline('latex', p[1]))
      elseif p ~= '' then
        local first = true
        for word in (p .. ' '):gmatch('(.-) ') do
          if not first then out:insert(pandoc.Space()) end
          if word ~= '' then out:insert(pandoc.Str(word)) end
          first = false
        end
        if p:sub(-1) == ' ' then out:insert(pandoc.Space()) end
      end
    end
  end
  for _, x in ipairs(inlines) do
    if x.t == 'Str' then buf[#buf + 1] = x.text
    elseif x.t == 'Space' then buf[#buf + 1] = ' '
    else flush(); out:insert(x) end
  end
  flush()
  return changed and out or nil
end

-- ---------------------------------------------------------------------------
-- headings

local LEVELS = { 'section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph' }

local function header_number(inlines)
  -- "1 Введение" (number, Space) or "1\160Введение" (one Str)
  local first = inlines[1]
  if not first or first.t ~= 'Str' then return inlines, false end
  local rest = first.text:match('^%d[%d%.]*' .. NBSP .. '(.*)$')
  local out = pandoc.List(inlines)
  if rest then
    out[1] = pandoc.Str(rest)
    if rest == '' then out:remove(1) end
    return out, true
  end
  if first.text:match('^%d[%d%.]*$') and (inlines[2] == nil or inlines[2].t == 'Space') then
    out:remove(1)
    if out[1] and out[1].t == 'Space' then out:remove(1) end
    return out, true
  end
  return inlines, false
end

local function emit_header(h)
  local labels, hh = take_labels(h)
  local content, numbered = header_number(clean_inlines(hh.content))
  local star = (not numbered) and numbered_levels[h.level] and '*' or ''
  local cmd = LEVELS[h.level] or 'paragraph'
  return raw('\\' .. cmd .. star .. '{' .. write_inlines(content) .. '}' .. label_cmds(labels))
end

-- ---------------------------------------------------------------------------
-- labels for Word's own cross-references (bookmarks _RefNNN) from where they sit

local TRANSLIT = { ['а'] = 'a', ['б'] = 'b', ['в'] = 'v', ['г'] = 'g', ['д'] = 'd', ['е'] = 'e', ['ё'] = 'e',
  ['ж'] = 'zh', ['з'] = 'z', ['и'] = 'i', ['й'] = 'j', ['к'] = 'k', ['л'] = 'l', ['м'] = 'm', ['н'] = 'n',
  ['о'] = 'o', ['п'] = 'p', ['р'] = 'r', ['с'] = 's', ['т'] = 't', ['у'] = 'u', ['ф'] = 'f', ['х'] = 'h',
  ['ц'] = 'c', ['ч'] = 'ch', ['ш'] = 'sh', ['щ'] = 'shch', ['ъ'] = '', ['ы'] = 'y', ['ь'] = '', ['э'] = 'e',
  ['ю'] = 'yu', ['я'] = 'ya' }

local function slug(text)
  local out = {}
  for _, cp in utf8.codes(lower(text)) do
    local ch = utf8.char(cp)
    if TRANSLIT[ch] then out[#out + 1] = TRANSLIT[ch]
    elseif ch:match('^[%w]$') then out[#out + 1] = ch
    else out[#out + 1] = '-' end
  end
  local s = table.concat(out):gsub('%-+', '-'):gsub('^%-', ''):gsub('%-$', '')
  return s:sub(1, 30):gsub('%-$', '')
end

local function word_ref_label(inlines, style, is_header, name)
  local text = trim(stringify(clean_inlines(inlines)))
  if is_header then
    local rest = text:match('^%d[%d%.]*[%s' .. NBSP .. ']+(.*)$') or text
    return 'sec:' .. slug(rest)
  end
  local function number_after(list, prefix)
    for _, n in ipairs(list) do
      if n and n ~= '' then
        local num = text:match('^' .. escape_pattern(n) .. '[%s' .. NBSP .. ']*(%d+)')
        if num then return prefix .. ':' .. num end
      end
    end
    return nil
  end
  if style == 'Image Caption' or style == 'Table Caption' or style == 'Algorithm Caption' or style == nil then
    return number_after(with_name(names.figure, FIGURE_NAMES), 'fig')
      or number_after(with_name(names.table, TABLE_NAMES), 'tab')
      or number_after(with_name(names.algorithm, ALGORITHM_NAMES), 'alg')
      or (text:match('^%((%d[%d%.]*)%)$') and 'eq:' .. text:match('^%((%d[%d%.]*)%)$'))
      or ('ref:' .. name:match('%d+'))
  end
  if style == 'Equation' then
    local num = text:match('%((%d[%d%.]*)%)')
    if num then return 'eq:' .. num end
  end
  return 'ref:' .. name:match('%d+')
end

-- ---------------------------------------------------------------------------
-- the block pass

local THEOREM_STYLES = { Theorem = true, Definition = true, Remark = true, Lemma = true, Corollary = true,
  Proposition = true, Example = true, Conjecture = true, Claim = true, Problem = true }
local ALIGN = { ['Centered'] = 'center', ['Right Aligned'] = 'flushright', ['Left Aligned'] = 'flushleft' }
local WRAPPERS = { ['Body Text'] = true, ['First Paragraph'] = true, ['Normal'] = true, ['Compact'] = true,
  ['List Bullet'] = true, ['List Number'] = true, ['List Paragraph'] = true, ['Captioned Figure'] = true }

local process -- forward

local function wrap_env(env, blocks)
  local out = { raw('\\begin{' .. env .. '}') }
  for _, b in ipairs(blocks) do out[#out + 1] = b end
  out[#out + 1] = raw('\\end{' .. env .. '}')
  return out
end

process = function(blocks)
  local out = {}
  local function push(list) for _, b in ipairs(list) do out[#out + 1] = b end end
  local i = 1
  while i <= #blocks do
    local b = blocks[i]
    local st = style_of(b)
    local para = (b.t == 'Div' and #b.content == 1) and b.content[1] or b
    local eq = (st == 'Equation' and para.t == 'Para') and parse_equation(para)
      or (b.t == 'Para' and only_math(b) and parse_equation(b, true)) or nil
    if eq then
      local items = { eq }
      while i < #blocks do
        local nb = blocks[i + 1]
        local nst = style_of(nb)
        local np = (nb.t == 'Div' and #nb.content == 1) and nb.content[1] or nb
        local ne = (nst == 'Equation' and np.t == 'Para') and parse_equation(np)
          or (nb.t == 'Para' and only_math(nb) and parse_equation(nb, true)) or nil
        if not ne then break end
        items[#items + 1] = ne
        i = i + 1
      end
      push(emit_equations(items))
    elseif b.t == 'Figure' then  -- pandoc 3.12 reads picture + Image Caption as a Figure
      local img = first_image(b)
      local cap = nil
      if b.caption and b.caption.long then
        pandoc.Blocks(b.caption.long):walk {
          Para = function(p) cap = cap or p end,
          Plain = function(p) cap = cap or pandoc.Para(p.content) end,
        }
      end
      if img then
        push({ emit_figure(img, cap) })
      else
        push(process(b.content))
      end
    elseif (st == 'Captioned Figure' or (b.t == 'Para' and #b.content == 1 and b.content[1].t == 'Image'))
        and first_image(b) then
      local img = first_image(b)
      local nb = blocks[i + 1]
      local nst = nb and style_of(nb)
      if nst == 'Image Caption' then
        push({ emit_figure(img, nb.content[1]) })
        i = i + 1
      else
        push({ raw('\\begin{center}\n  \\includegraphics{' .. img.src .. '}\n\\end{center}') })
      end
    elseif (st == 'Table Caption' or st == 'Image Caption') and blocks[i + 1] and blocks[i + 1].t == 'Table' then
      push(emit_table(blocks[i + 1], b.content[1]))
      i = i + 1
    elseif b.t == 'Table' then
      local cap = b.caption and b.caption.long and b.caption.long[1]
      push(emit_table(b, cap and cap.content and pandoc.Para(cap.content) or nil))
    elseif st == 'Algorithm Caption' or st == 'Algorithm' then
      local cap = nil
      if st == 'Algorithm Caption' then
        cap = b.content[1]
        i = i + 1
      end
      local lines = {}
      while blocks[i] and style_of(blocks[i]) == 'Algorithm' do
        for _, p in ipairs(blocks[i].content) do if p.t == 'Para' or p.t == 'Plain' then lines[#lines + 1] = p end end
        i = i + 1
      end
      i = i - 1
      push({ emit_algorithm(cap, lines) })
    elseif b.t == 'Para' and in_theorem == 0 and text_theorem(b) then
      local title = text_theorem(b)
      report('info', 'theorem.by-text', title)
      push(emit_theorem(pandoc.Div({ b }), title, process))
    elseif b.t == 'Para' and in_theorem == 0 and text_proof(b) then
      report('info', 'proof.by-text', '')
      push(emit_proof(pandoc.Div({ b }), process))
    elseif st and THEOREM_STYLES[st] then
      -- the bookmark of the theorem may run over the following paragraphs (its formulas)
      local _, _, names = take_labels(b)
      local k = find_end(blocks, i + 1, names)
      local extra = nil
      if k then
        extra = {}
        for q = i + 1, k do extra[#extra + 1] = blocks[q] end
        i = k
      end
      push(emit_theorem(b, st, process, extra))
    elseif st == 'Proof' then
      push(emit_proof(b, process))
    elseif is_bib_header(b) and blocks[i + 1] and blocks[i + 1].t == 'OrderedList' then
      push({ emit_thebibliography(blocks[i + 1].content) })
      i = i + 1
    elseif is_bib_header(b) and blocks[i + 1] and style_of(blocks[i + 1]) == 'Bibliography' then
      -- thebibliography prints the heading itself
    elseif st == 'Bibliography' then
      local entries = {}
      while blocks[i] and style_of(blocks[i]) == 'Bibliography' do
        local p = blocks[i].content[1]
        if p and (p.t == 'Para' or p.t == 'Plain') then
          local ins = clean_inlines(p.content)
          if ins[1] and ins[1].t == 'Str' and ins[1].text:match('^%d+%.?$') then
            ins:remove(1)
            if ins[1] and ins[1].t == 'Space' then ins:remove(1) end
          end
          entries[#entries + 1] = { pandoc.Para(ins) }
        end
        i = i + 1
      end
      i = i - 1
      push({ emit_thebibliography(entries) })
    elseif st and ALIGN[st] then
      push(wrap_env(ALIGN[st], process(b.content)))
    elseif st == 'Abstract' then
      push(wrap_env('abstract', process(b.content)))
    elseif st == 'Abstract Title' or st == 'Title' or st == 'Author' or st == 'Date' then
      report('info', 'style.dropped', st)
    elseif b.t == 'Div' then
      if st and not WRAPPERS[st] then report('info', 'style.unknown', st) end
      push(process(b.content))
    elseif b.t == 'Header' then
      push({ emit_header(b) })
    elseif b.t == 'OrderedList' or b.t == 'BulletList' then
      local items = {}
      for _, item in ipairs(b.content) do items[#items + 1] = process(item) end
      b.content = items
      push({ b })
    elseif b.t == 'BlockQuote' then
      b.content = process(b.content)
      push({ b })
    else
      push({ b })
    end
    i = i + 1
  end
  return out
end

-- ---------------------------------------------------------------------------

local function front_matter(meta)
  local out = {}
  if meta.title then
    -- the main document declares \title in its preamble: here only as comments, plus \maketitle
    local lines = { '% docx2tex: title block of the chapter (move to the preamble if needed)',
      '% \\title{' .. write_inlines(meta.title) .. '}' }
    if meta.author then
      local authors = meta.author
      if authors.t == 'MetaList' or (type(authors) == 'table' and authors[1] and authors[1].t == 'MetaInlines') then
        local parts = {}
        for _, a in ipairs(authors) do parts[#parts + 1] = write_inlines(a) end
        lines[#lines + 1] = '% \\author{' .. table.concat(parts, ' \\and ') .. '}'
      else
        lines[#lines + 1] = '% \\author{' .. write_inlines(authors) .. '}'
      end
    end
    if meta.date then lines[#lines + 1] = '% \\date{' .. write_inlines(meta.date) .. '}' end
    lines[#lines + 1] = '\\maketitle'
    out[#out + 1] = raw(table.concat(lines, '\n'))
    report('info', 'emit.maketitle', '')
  end
  if meta.abstract then
    local blocks = meta.abstract
    if blocks.t == 'MetaBlocks' or (blocks[1] and blocks[1].t ~= 'Str') then
      out[#out + 1] = raw('\\begin{abstract}')
      for _, b in ipairs(process(pandoc.List(blocks))) do out[#out + 1] = b end
      out[#out + 1] = raw('\\end{abstract}')
    else
      out[#out + 1] = raw('\\begin{abstract}\n' .. write_inlines(blocks) .. '\n\\end{abstract}')
    end
  end
  return out
end

function Pandoc(doc)
  M = d2t.load(doc.meta) or {}
  labels_map = M.labels or {}
  names = M.names or {}
  cites = M.cites or {}
  link_labels, bookmarked = {}, {}
  theorem_envs = {}
  for word, env in pairs(M.theorem_envs or {}) do theorem_envs[lower(word)] = env end
  for env, attrs in pairs(M.theorems or {}) do
    if attrs.title then theorem_envs[lower(attrs.title)] = env end
  end

  -- 1. markers -> label/tab spans; pandoc's anchors dropped; images without attributes
  doc = doc:walk {
    Inlines = split_markers,
    Image = function(img) img.attributes = {}; img.caption = {}; return img end,
    OrderedList = function(ol)
      local n, sty, delim = table.unpack(ol.listAttributes and { ol.listAttributes.start, ol.listAttributes.style, ol.listAttributes.delimiter } or { ol.start, ol.style, ol.delimiter })
      if (sty == 'Decimal' or sty == 'DefaultStyle') and (delim == 'Period' or delim == 'DefaultDelim') then
        ol.listAttributes = pandoc.ListAttributes(n or 1, 'DefaultStyle', 'DefaultDelim')
      end
      return ol
    end,
  }

  -- 2. facts: numbered heading levels, bibliography present, heading ids; bookmark names
  -- without a label of their own (pandoc 3.12 hashes Div identifiers) take the first label
  -- found inside their extent (the theorem's own number, the figure's caption)
  has_bib = false
  numbered_levels = {}
  header_labels = {}
  name_labels = {}
  local open = {}
  local function learn(inlines, style, is_header)
    local found = {}
    for _, x in ipairs(inlines) do
      if is_label(x) and x.attributes.label == '' and x.attributes.name:match('^_Ref%d+$')
          and not name_labels[x.attributes.name] then
        local l = word_ref_label(inlines, style, is_header, x.attributes.name)
        name_labels[x.attributes.name] = l
        bookmarked[l] = true
        report('info', 'label.word-ref', l)
      end
    end
    for _, x in ipairs(inlines) do
      if is_label(x) then
        local l = label_of(x)
        if l then found[#found + 1] = l else open[x.attributes.name] = true end
      end
    end
    for n in pairs(open) do
      if not name_labels[n] and found[1] then name_labels[n] = found[1] end
    end
    for _, x in ipairs(inlines) do
      if is_end(x) then open[x.attributes.name] = nil end
    end
  end
  local function learn_blocks(blocks, style)
    for _, b in ipairs(blocks) do
      if b.t == 'Para' or b.t == 'Plain' then learn(b.content, style, false)
      elseif b.t == 'Header' then learn(b.content, style, true)
      elseif b.t == 'Div' then learn_blocks(b.content, style_of(b) or style)
      elseif b.t == 'Figure' then
        learn_blocks(b.content, style)
        if b.caption and b.caption.long then learn_blocks(pandoc.Blocks(b.caption.long), 'Image Caption') end
      elseif b.t == 'BlockQuote' then learn_blocks(b.content, style)
      elseif b.t == 'OrderedList' or b.t == 'BulletList' then
        for _, item in ipairs(b.content) do learn_blocks(item, style) end
      elseif b.t == 'Table' then
        b:walk { Para = function(p) learn(p.content, 'Table', false) end,
                 Plain = function(p) learn(p.content, 'Table', false) end }
      end
    end
  end
  learn_blocks(doc.blocks, nil)
  for i, b in ipairs(doc.blocks) do
    if b.t == 'Header' then
      local hl = take_labels(b)
      if hl[1] and b.identifier ~= '' then header_labels[b.identifier] = hl[1] end
      local _, numbered = header_number(clean_inlines(b.content))
      if numbered then numbered_levels[b.level] = true end
      if is_bib_header(b) and doc.blocks[i + 1] and doc.blocks[i + 1].t == 'OrderedList' then has_bib = true end
    elseif style_of(b) == 'Bibliography' then
      has_bib = true
    end
  end

  -- 3. links -> \ref / \eqref; citations
  doc = doc:walk {
    Link = function(link)
      local target = link.target
      if target:sub(1, 1) ~= '#' then return nil end
      local name = target:sub(2)
      local label = header_labels[name] or name_labels[name] or resolve_label(name)
      local text = trim(stringify(link.content))
      if not label then
        report('info', 'link.unresolved', target:sub(2))
        return link.content
      end
      if text:match('^%(.*%)$') then
        link_labels[text] = link_labels[text] or label
        return pandoc.RawInline('latex', '\\eqref{' .. label .. '}')
      end
      -- Word's cross-reference "Рисунок 1": the word stays text, the number is the reference
      local word = text:match('^(.-)[%s' .. NBSP .. ']+%d[%d%.]*$')
      if word and word ~= '' and not word:match('[%d%p]$') then
        return pandoc.RawInline('latex', word .. '~\\ref{' .. label .. '}')
      end
      return pandoc.RawInline('latex', '\\ref{' .. label .. '}')
    end,
  }
  if has_bib then doc = doc:walk { Inlines = cite_inlines } end

  -- 4. blocks
  local blocks = front_matter(doc.meta)
  for _, b in ipairs(process(doc.blocks)) do blocks[#blocks + 1] = b end
  -- leftover tab spans (Word tabs in running text) and label spans outside structures
  doc.blocks = pandoc.Blocks(blocks):walk {
    Span = function(sp)
      if is_tab(sp) then return pandoc.Space() end
      if is_end(sp) then return {} end
      if is_label(sp) then
        local l = label_of(sp)
        if not l then return {} end
        return pandoc.RawInline('latex', '\\label{' .. l .. '}')
      end
    end,
  }
  doc.meta = pandoc.Meta({})
  return doc
end
