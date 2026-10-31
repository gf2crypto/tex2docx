-- Shared helpers for docx2tex filters (mirror of tex2docx/filters/t2d.lua).
local M = {}

function M.load(meta)
  local v = meta['d2t-meta']
  if not v then return nil end
  local fh = io.open(pandoc.utils.stringify(v), 'r')
  if not fh then
    M.report('error', 'filter.no-meta', '')
    return nil
  end
  local data = pandoc.json.decode(fh:read('a'), false)
  fh:close()
  return data
end

function M.report(level, code, detail)
  io.stderr:write(string.format('[d2t] %s %s %s\n', level, code, detail or ''))
end

return M
