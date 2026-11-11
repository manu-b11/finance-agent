import { API_URL, authHeaders, request, safeFetch, toApiError } from './client.js'

/*
  Contrato real de POST /chat  (backend: app/api/chat.py, body: { message, conversation_id? })
  Responde SSE; cada evento llega como  "event: <tipo>\ndata: <json>\n\n":

    conversation { id, title }      se creó la conversación al enviar el primer mensaje
    tool_call    { name }           el agente va a ejecutar una herramienta
    tool_result  { name, result }   resultado de esa herramienta (result.error si falló)
    message      { text }           respuesta COMPLETA del agente (no llega por fragmentos)
    error        { code, message }
    done         {}

  El historial se guarda por conversación (tabla chat_message + conversations).
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

async function* readSse(res) {
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

export async function* streamChat(message, { conversationId, signal } = {}) {
  const res = await safeFetch(`${API_URL}/chat`, {
    method: 'POST',
    signal,
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...authHeaders() },
    body: JSON.stringify(
      conversationId ? { message, conversation_id: conversationId } : { message },
    ),
  })
  if (!res.ok) throw await toApiError(res)
  yield* readSse(res)
}

// POST /chat/demo → vista previa para invitados (IA real, sin herramientas ni datos guardados).
export async function* streamDemoChat(message, { history = [], timezone, signal } = {}) {
  const res = await safeFetch(`${API_URL}/chat/demo`, {
    method: 'POST',
    signal,
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({
      message,
      history,
      ...(timezone ? { timezone } : {}),
    }),
  })
  if (!res.ok) throw await toApiError(res)
  yield* readSse(res)
}

// GET /chat/conversations?limit=50 → [{ id, title, created_at, updated_at }] (más reciente primero)
export const getConversations = (limit = 50) =>
  request(`/chat/conversations?limit=${limit}`)

// POST /chat/conversations → conversación vacía; si se envía title, se usa como título inicial
export const createConversation = (title) =>
  request('/chat/conversations', { method: 'POST', body: title ? { title } : undefined })

// GET /chat/conversations/{id}/messages?limit=50 → [{ id, role, content, created_at }]
export const getConversationMessages = (conversationId, limit = 50) =>
  request(
    `/chat/conversations/${encodeURIComponent(conversationId)}/messages?limit=${limit}`,
  )

// POST /chat/conversations/{id}/messages → guarda un intercambio ya resuelto (sin llamar a la IA)
export const addExchange = (conversationId, { userText, assistantText }) =>
  request(`/chat/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: 'POST',
    body: { user_text: userText, assistant_text: assistantText },
  })

// GET /chat/history?limit=50 → historial global reciente (compatibilidad)
export const getHistory = (limit = 50) => request(`/chat/history?limit=${limit}`)
