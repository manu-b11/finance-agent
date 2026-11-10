import { API_URL, authHeaders, request, safeFetch, toApiError } from './client.js'

/*
  Contrato real de POST /chat  (backend: app/api/chat.py, body: { message } con 1–2000 caracteres)
  Responde SSE; cada evento llega como  "event: <tipo>\ndata: <json>\n\n":

    tool_call   { name }            el agente va a ejecutar una herramienta
    message     { text }            respuesta COMPLETA del agente (no llega por fragmentos)
    error       { code, message }
    done        {}

  El historial de la conversación lo guarda el servidor por usuario (tabla chat_message).
*/

function parseBlock(block) {
  let event = 'message'
  const dataLines = []
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
  }
  if (dataLines.length === 0) return null
  const raw = dataLines.join('\n')
  let data = raw
  try {
    data = JSON.parse(raw)
  } catch {
    /* texto plano */
  }
  return { event, data }
}

export async function* streamChat(message, { signal } = {}) {
  const res = await safeFetch(`${API_URL}/chat`, {
    method: 'POST',
    signal,
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...authHeaders() },
    body: JSON.stringify({ message }),
  })
  if (!res.ok) throw await toApiError(res)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop()
    for (const block of blocks) {
      const evt = parseBlock(block)
      if (evt) yield evt
    }
  }
  if (buffer.trim()) {
    const evt = parseBlock(buffer)
    if (evt) yield evt
  }
}

// GET /chat/history?limit=50 → [{ id, role: 'user'|'assistant', content, created_at }] en orden cronológico
export const getHistory = (limit = 50) => request(`/chat/history?limit=${limit}`)
