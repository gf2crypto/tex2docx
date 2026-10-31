-- Display equations: own paragraph, number on the right, as in LaTeX (ADR 0004).
-- Status: implemented (M1).
--   * Every DisplayMath becomes its own paragraph of style "Equation":
--       <tab> formula <tab> (number)
--     with a centre tab and a right tab defined by the style (reference.docx).
--     The formula is written as inline OMML: Word lays out a formula that
--     shares its line with text (the number) only in inline mode, and texmath
--     keeps limits above/below and stacked fractions anyway.
--   * The number comes from \label{x} (labels[x], computed by LaTeX; autolabel
--     has labelled everything numbered), or from \tag{..}; \notag/\nonumber or
--     no label at all means no number.
--   * Multi-line blocks (align, gather, eqnarray and their aligned/gathered
--     forms; pandoc 3.1 rewrites align -> aligned, pandoc 3.12 keeps align)
--     with at most one number stay one formula; with several numbers each line
--     becomes its own paragraph with its own number (the & alignment across
--     lines is lost; reported as equations.split-lines). multline is never split.
--   * \label, \notag, \nonumber, \tag are removed from the math text: texmath
--     cannot convert aligned blocks that contain them.
--   * A Para holding display math together with text is split around it.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local t2d = require 't2d'

local TAB = pandoc.RawInline('openxml', '<w:r><w:tab/></w:r>')

-- Split the body of an aligned/gathered block at top-level \\ (not inside braces
-- or nested environments).
local function split_lines(body)
  local lines, depth, env, i, start = {}, 0, 0, 1, 1
  local n = #body
  while i <= n do
    local c = body:sub(i, i)
    if c == '\\' then
      local nxt = body:sub(i + 1, i + 1)
      if nxt == '\\' and depth == 0 and env == 0 then
        lines[#lines + 1] = body:sub(start, i - 1)
        i = i + 2
        local opt = body:match('^%*?%b[]', i) or body:match('^%*', i)
        if opt then i = i + #opt end
        start = i
      else
        if body:sub(i, i + 6) == '\\begin{' then env = env + 1
        elseif body:sub(i, i + 4) == '\\end{' then env = env - 1 end
        i = i + 2
      end
    else
      if c == '{' then depth = depth + 1 elseif c == '}' then depth = depth - 1 end
      i = i + 1
    end
  end
  lines[#lines + 1] = body:sub(start)
  return lines
end

-- Number of one equation (or one line): "(1.2)", "X" for \tag*, or nil.
-- Second result: cleaned math text.
-- Returns the number as inlines (nil when none) and the cleaned math text.
local function number_of(tex, labels)
  local num
  local tag_star, tag = tex:match('\\tag(%*?)%s*(%b{})')
  if tag then
    tag = tag:sub(2, -2)
    local label = tex:match('\\label%s*(%b{})')
    if label then  -- a marker Span too, so that the label keeps its bookmark (docx2tex)
      num = pandoc.List({ pandoc.Str((tag_star == '*') and '' or '(') })
      num:extend(t2d.number(tag, 'equation', label:sub(2, -2), nil))
      num:insert(pandoc.Str((tag_star == '*') and '' or ')'))
    else
      num = { pandoc.Str((tag_star == '*') and tag or ('(' .. tag .. ')')) }
    end
  elseif not (tex:find('\\notag%f[%A]') or tex:find('\\nonumber%f[%A]')) then
    local label = tex:match('\\label%s*(%b{})')
    if label then
      label = label:sub(2, -2)
      local v = labels[label]
      if v then
        num = pandoc.List({ pandoc.Str('(') })
        num:extend(t2d.number(v, 'equation', label, v:find('%.') and 'section' or nil))
        num:insert(pandoc.Str(')'))
      else
        t2d.report('warning', 'equations.unresolved', label)
      end
    end
  end
  tex = tex:gsub('\\label%s*%b{}', '')
  tex = tex:gsub('\\tag%*?%s*%b{}', '')
  tex = tex:gsub('\\notag%f[%A]', '')
  tex = tex:gsub('\\nonumber%f[%A]', '')
  return num, tex
end

local function equation_block(tex, num)
  local inl = pandoc.List({ TAB, pandoc.Math('InlineMath', tex) })
  if num then
    inl:insert(TAB)
    inl:extend(num)
  end
  return pandoc.Div({ pandoc.Para(inl) }, pandoc.Attr('', {}, { ['custom-style'] = 'Equation' }))
end

local split_count = 0

-- Environments whose lines can carry their own numbers.
local LINE_ENVS = { aligned = true, gathered = true, align = true, gather = true,
                    eqnarray = true, alignat = true, flalign = true }

-- One DisplayMath -> list of blocks.
local function render(math, labels)
  local tex = math.text
  local kind, body = tex:match('^%s*\\begin{(%a+)}(.-)\\end{%a+}%s*$')
  if kind and LINE_ENVS[kind] then
    local lines = split_lines(body)
    local nums, cleaned, count = {}, {}, 0
    for i, ln in ipairs(lines) do
      nums[i], cleaned[i] = number_of(ln, labels)
      if nums[i] then count = count + 1 end
    end
    if count <= 1 then
      local num
      for i = 1, #lines do num = num or nums[i] end
      local joined = '\\begin{' .. kind .. '}' .. table.concat(cleaned, '\\\\') .. '\\end{' .. kind .. '}'
      return { equation_block(joined, num) }
    end
    split_count = split_count + 1
    local out = {}
    for i = 1, #lines do
      if cleaned[i]:match('%S') or nums[i] then
        local one = '\\begin{' .. kind .. '}' .. cleaned[i] .. '\\end{' .. kind .. '}'
        out[#out + 1] = equation_block(one, nums[i])
      end
    end
    return out
  end
  local num, cleaned = number_of(tex, labels)
  return { equation_block(cleaned, num) }
end

local WRAPPERS = { Emph = true, Strong = true, Underline = true, Span = true, SmallCaps = true }

local function has_display(inlines)
  for _, x in ipairs(inlines) do
    if x.t == 'Math' and x.mathtype == 'DisplayMath' then return true end
    if WRAPPERS[x.t] and has_display(x.content) then return true end
  end
  return false
end

-- Bring display math to the top level: Emph[a, Math, b] -> Emph[a], Math, Emph[b].
-- (pandoc wraps the body of plain-style theorems in Emph.)
local function is_blank(inl)
  return inl.t == 'Space' or inl.t == 'SoftBreak' or inl.t == 'LineBreak'
end

local function trim(inlines)
  local a, b = 1, #inlines
  while a <= b and is_blank(inlines[a]) do a = a + 1 end
  while b >= a and is_blank(inlines[b]) do b = b - 1 end
  local out = {}
  for i = a, b do out[#out + 1] = inlines[i] end
  return out
end

local function explode(inlines)
  local out = {}
  for _, x in ipairs(inlines) do
    if WRAPPERS[x.t] and has_display(x.content) then
      local buf = {}
      local function flush()
        local t = trim(buf)  -- no space left hanging before/after the display formula
        if #t > 0 then
          local w = x:clone()
          w.content = t
          out[#out + 1] = w
        end
        buf = {}
      end
      for _, y in ipairs(explode(x.content)) do
        if y.t == 'Math' and y.mathtype == 'DisplayMath' then
          flush()
          out[#out + 1] = y
        else
          buf[#buf + 1] = y
        end
      end
      flush()
    else
      out[#out + 1] = x
    end
  end
  return out
end

function Pandoc(doc)
  local M = t2d.load(doc.meta)
  if not M then return nil end
  local labels = M.labels or {}

  doc = doc:walk {
    Para = function(p)
      if not has_display(p.content) then return nil end
      local blocks, buf = {}, {}
      local function flush()
        local t = trim(buf)
        if #t > 0 then blocks[#blocks + 1] = pandoc.Para(t) end
        buf = {}
      end
      for _, x in ipairs(explode(p.content)) do
        if x.t == 'Math' and x.mathtype == 'DisplayMath' then
          flush()
          for _, b in ipairs(render(x, labels)) do blocks[#blocks + 1] = b end
        else
          buf[#buf + 1] = x
        end
      end
      flush()
      return blocks
    end,
  }
  if split_count > 0 then t2d.report('info', 'equations.split-lines', tostring(split_count)) end
  return doc
end
