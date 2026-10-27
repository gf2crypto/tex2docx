-- Formulas texmath cannot convert -> pictures rendered by LaTeX (see stages/mathimg.py).
-- Status: implemented (M2). Runs last, after equations.lua stripped \label etc.
-- Mode "collect": test every formula (pandoc.write to MathML: no <math> means
--   texmath gave up) and write the failing ones to M.mathimg.out as JSON
--   [{text=..., display=true|false}].
-- Mode "replace": formulas whose text is a key of M.mathimg.images become
--   Image elements (inline or inside the Equation paragraph).

package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
local t2d = require 't2d'

local function convertible(m)
  local ok, out = pcall(pandoc.write, pandoc.Pandoc({ pandoc.Para({ m }) }), 'html',
                        { html_math_method = 'mathml' })
  return ok and out:find('<math', 1, true) ~= nil
end

function Pandoc(doc)
  local M = t2d.load(doc.meta)
  if not M or not M.mathimg then return nil end
  local cfg = M.mathimg

  if cfg.mode == 'collect' then
    local failed, seen = {}, {}
    doc:walk {
      Math = function(m)
        if not seen[m.text] and not convertible(m) then
          seen[m.text] = true
          failed[#failed + 1] = { text = m.text, display = (m.mathtype == 'DisplayMath') }
        end
      end,
    }
    local fh = io.open(cfg.out, 'w')
    if fh then
      fh:write(pandoc.json.encode(failed))
      fh:close()
    else
      t2d.report('error', 'mathimg.cannot-write', cfg.out)
    end
    return nil
  end

  if cfg.mode == 'replace' then
    local images, n = cfg.images or {}, 0
    return doc:walk {
      Math = function(m)
        local path = images[m.text]
        if not path then return nil end
        n = n + 1
        return pandoc.Image({}, path, '', pandoc.Attr('', { 'math-image' }))
      end,
    }
  end
  return nil
end
