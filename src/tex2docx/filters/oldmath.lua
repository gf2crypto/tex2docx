-- Plain-TeX font switches inside math -> LaTeX commands texmath understands.
-- Status: implemented (M2 follow-up). {\rm Hom} -> \mathrm{Hom}, {\bf x} -> \mathbf{x},
-- {\cal B} -> \mathcal{B}, {\it x} -> \mathit{x}, {\sf x}, {\tt x}; nested groups too.
-- texmath reports "unexpected control sequence \rm" and gives up on the formula otherwise.

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path

local MAP = { rm = 'mathrm', bf = 'mathbf', cal = 'mathcal', it = 'mathit', sf = 'mathsf', tt = 'mathtt' }

local function fix(tex)
  -- innermost groups first: rewrite until nothing changes
  local changed = true
  while changed do
    changed = false
    tex = tex:gsub('%b{}', function(g)
      local cmd, rest = g:match('^{%s*\\(%a+)%s*(.*)}$')
      if cmd and MAP[cmd] and not rest:find('\\' .. cmd .. '%f[%A]') then
        changed = true
        return '\\' .. MAP[cmd] .. '{' .. fix(rest) .. '}'
      end
      local inner = fix(g:sub(2, -2))
      if inner ~= g:sub(2, -2) then changed = true end
      return '{' .. inner .. '}'
    end)
  end
  return tex
end

function Math(m)
  if m.text:find('\\[rbcist][mfalt]') then
    local t = fix(m.text)
    if t ~= m.text then
      m.text = t
      return m
    end
  end
  return nil
end
