-- Shared helpers for tex2docx filters.
-- Usage at the top of a filter:
--   package.path = pandoc.path.directory(PANDOC_SCRIPT_FILE) .. '/?.lua;' .. package.path
--   local t2d = require 't2d'

local M = {}

-- Load the JSON written by stages/pandoc_run.py; path comes as metadata 't2d-meta'.
function M.load(meta)
  local v = meta['t2d-meta']
  if not v then return nil end
  local path = pandoc.utils.stringify(v)
  local fh = io.open(path, 'r')
  if not fh then
    M.report('error', 'filter.no-meta', path)
    return nil
  end
  local data = pandoc.json.decode(fh:read('a'), false)
  fh:close()
  return data
end

-- Report line, parsed by pandoc_run.py: "[t2d] <level> <code> <detail>".
-- detail: command/env/label name only, never document text.
function M.report(level, code, detail)
  io.stderr:write(string.format('[t2d] %s %s %s\n', level, code, detail or ''))
end

-- Numbers and references are emitted as marker Spans; filters/numbers.lua (the last
-- filter) turns them into text or, with config live_numbers, into Word fields (ADR 0006).
-- num: as LaTeX printed it; counter: SEQ name; label: for the bookmark; within:
-- "section" when numbered per section; level: heading level for headings.
function M.number(num, counter, label, within, level)
  return { pandoc.Span({ pandoc.Str(num) }, pandoc.Attr('', { 't2d-num' }, {
    counter = counter or '', label = label or '', within = within or '', level = level and tostring(level) or '' })) }
end

function M.ref(num, label)
  return { pandoc.Span({ pandoc.Str(num) }, pandoc.Attr('', { 't2d-ref' }, { label = label or '' })) }
end

return M
