import { useCallback, useEffect, useRef, useState } from 'react'
import {
  addExchange,
  createConversation,
  getConversationMessages,
  getConversations,
  streamChat,
  streamDemoChat,
} from '../api/chat.js'
import { getDashboard } from '../api/dashboard.js'

/*
  Mensaje de usuario: { id, role: 'user', text, fileName? }
  Mensaje de agente:  { id, role: 'agent', text, cards: [{type, data}], quickReplies: [{label, text}],
                        status: 'typing' | 'streaming' | 'done' | 'error', toolLabel?, error? }
  Conversación:       { id, title, created_at, updated_at }
*/
const uid = () => crypto.randomUUID()

const TOOL_LABELS = [
  [/^(add|update|delete|list)_transaction/, 'Revisando tus movimientos…'],
  [/^get_balance$/, 'Calculando tu balance…'],
  [/budget/, 'Revisando tu presupuesto…'],
  [/goal/, 'Revisando tus metas…'],
  [/report|by_category/, 'Preparando el informe…'],
  [/reminder/, 'Gestionando tus recordatorios…'],
  [/invoice/, 'Revisando la factura…'],
]
const labelFor = (name) => TOOL_LABELS.find(([re]) => re.test(name))?.[1] ?? 'Trabajando en ello…'

// Tras estas herramientas el balance del mes cambió: se muestra una tarjeta con datos reales de /dashboard
const BALANCE_CHANGING = new Set(['add_transaction', 'update_transaction', 'delete_transaction', 'confirm_invoice'])

// Resultado de la herramienta → tarjeta del chat. Los errores no generan tarjeta.
const TRANSACTION_ACTIONS = {
  add_transaction: 'created',
  update_transaction: 'updated',
  delete_transaction: 'deleted',
}

function cardFromToolResult(name, result) {
  if (!result || result.error) return null
  const action = TRANSACTION_ACTIONS[name]
  if (action) {
    const transaction = action === 'deleted' ? result.transaction : result
    return transaction?.id ? { type: 'transaction', data: { action, transaction } } : null
  }
  if (name === 'get_monthly_report' && result.month && result.pdf_url) {
    return { type: 'report', data: result }
  }
  return null
}

// Mensaje guardado en el servidor → mensaje del chat
function fromServer(item) {
  if (item.role === 'user') {
    return { id: `h-${item.id}`, role: 'user', text: item.content }
  }
  return {
    id: `h-${item.id}`,
    role: 'agent',
    text: item.content,
    cards: [],
    quickReplies: [],
    status: 'done',
  }
}

const titleFrom = (text) => text.trim().slice(0, 120)

export function useChatStream({ enabled = true } = {}) {
  const [messages, setMessages] = useState([])
  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(() => !enabled)
  const abortRef = useRef(null)
  const loadSeqRef = useRef(0)

  const updateMessage = useCallback((id, patch) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, ...(typeof patch === 'function' ? patch(m) : patch) } : m)),
    )
  }, [])

  const pushUser = useCallback((text, fileName) => {
    setMessages((prev) => [...prev, { id: uid(), role: 'user', text, fileName }])
  }, [])

  // Mensaje de agente local (no viene del stream)
  const pushAgent = useCallback((partial) => {
    setMessages((prev) => [
      ...prev,
      { id: uid(), role: 'agent', text: '', cards: [], quickReplies: [], status: 'done', ...partial },
    ])
  }, [])

  // Crea un mensaje de agente en estado "escribiendo" y devuelve su id
  const beginAgent = useCallback(() => {
    const id = uid()
    setMessages((prev) => [...prev, { id, role: 'agent', text: '', cards: [], quickReplies: [], status: 'typing' }])
    return id
  }, [])

  const refreshConversations = useCallback(async () => {
    const items = await getConversations()
    setConversations(items)
    return items
  }, [])

  const ensureConversation = useCallback(
    async (title) => {
      if (activeConversationId) return activeConversationId
      const created = await createConversation(title)
      setActiveConversationId(created.id)
      setConversations((prev) => [created, ...prev.filter((c) => c.id !== created.id)])
      return created.id
    },
    [activeConversationId],
  )

  // Guarda un intercambio que no pasó por la IA (por ejemplo, una factura revisada).
  const saveExchange = useCallback(
    async (userText, assistantText) => {
      const conversationId = await ensureConversation(titleFrom(userText))
      await addExchange(conversationId, { userText, assistantText })
      await refreshConversations()
    },
    [ensureConversation, refreshConversations],
  )

  const send = useCallback(
    async (text) => {
      if (!enabled) return
      // Cualquier carga de historial pendiente ya no debe sobrescribir este envío.
      loadSeqRef.current += 1
      pushUser(text)
      const id = beginAgent()
      const controller = new AbortController()
      abortRef.current = controller
      setIsStreaming(true)
      const tools = new Set()
      let conversationId = activeConversationId
      try {
        // Un chat nuevo no tiene conversación en el servidor todavía.
        if (!conversationId) {
          const created = await createConversation(titleFrom(text))
          conversationId = created.id
          setActiveConversationId(created.id)
          setConversations((prev) => [created, ...prev.filter((c) => c.id !== created.id)])
        }

        for await (const { event, data } of streamChat(text, {
          conversationId,
          signal: controller.signal,
        })) {
          if (event === 'conversation' && data?.id) {
            // Solo llega si el backend creó la conversación por su cuenta.
            conversationId = data.id
            setActiveConversationId(data.id)
          } else if (event === 'tool_call') {
            tools.add(data?.name)
            updateMessage(id, { toolLabel: labelFor(data?.name ?? '') })
          } else if (event === 'tool_result') {
            const card = cardFromToolResult(data?.name, data?.result)
            if (card) updateMessage(id, (m) => ({ cards: [...m.cards, card] }))
          } else if (event === 'message') {
            updateMessage(id, { text: data?.text ?? '', status: 'streaming', toolLabel: undefined })
          } else if (event === 'error') {
            throw new Error(data?.message ?? 'El agente no pudo responder.')
          }
        }
        updateMessage(id, { status: 'done', toolLabel: undefined })

        if ([...tools].some((t) => BALANCE_CHANGING.has(t))) {
          try {
            const { summary } = await getDashboard()
            updateMessage(id, (m) => ({ cards: [...m.cards, { type: 'balance', data: summary }] }))
          } catch {
            /* la tarjeta es opcional */
          }
        }
      } catch (err) {
        if (err?.name === 'AbortError') updateMessage(id, { status: 'done', toolLabel: undefined })
        else updateMessage(id, { status: 'error', toolLabel: undefined, error: err?.message || 'Ocurrió un error inesperado.' })
      } finally {
        setIsStreaming(false)
        abortRef.current = null
        refreshConversations().catch(() => {
          /* el sidebar se actualizará en la próxima carga */
        })
      }
    },
    [activeConversationId, enabled, pushUser, beginAgent, updateMessage, refreshConversations],
  )

  // Vista previa para invitados: usa la IA real, sin herramientas ni historial guardado.
  const sendDemo = useCallback(
    async (text) => {
      const history = messages
        .filter((m) => m.text && m.status !== 'error')
        .slice(-8)
        .map((m) => ({
          role: m.role === 'user' ? 'user' : 'assistant',
          content: m.text,
        }))

      loadSeqRef.current += 1
      pushUser(text)
      const id = beginAgent()
      const controller = new AbortController()
      abortRef.current = controller
      setIsStreaming(true)
      try {
        for await (const { event, data } of streamDemoChat(text, {
          history,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          signal: controller.signal,
        })) {
          if (event === 'message') {
            updateMessage(id, { text: data?.text ?? '', status: 'streaming' })
          } else if (event === 'error') {
            throw new Error(data?.message ?? 'Finly no pudo responder.')
          }
        }
        updateMessage(id, { status: 'done' })
      } catch (err) {
        if (err?.name === 'AbortError') updateMessage(id, { status: 'done' })
        else updateMessage(id, { status: 'error', error: err?.message || 'Ocurrió un error inesperado.' })
      } finally {
        setIsStreaming(false)
        abortRef.current = null
      }
    },
    [messages, pushUser, beginAgent, updateMessage],
  )

  // Al activarse (sesión iniciada): cargar conversaciones y abrir la más reciente.
  // Sin sesión, el chat funciona en modo invitado y no consulta el backend.
  useEffect(() => {
    if (!enabled) {
      abortRef.current?.abort()
      abortRef.current = null
      loadSeqRef.current += 1
      setMessages([])
      setConversations([])
      setActiveConversationId(null)
      setIsStreaming(false)
      setHistoryLoaded(true)
      return undefined
    }

    let alive = true
    const seq = ++loadSeqRef.current
    setHistoryLoaded(false)

    getConversations()
      .then(async (items) => {
        if (!alive || seq !== loadSeqRef.current) return
        setConversations(items)
        if (items.length === 0) return
        const latest = items[0]
        setActiveConversationId(latest.id)
        try {
          const history = await getConversationMessages(latest.id)
          if (alive && seq === loadSeqRef.current) setMessages(history.map(fromServer))
        } catch {
          if (alive && seq === loadSeqRef.current) setMessages([])
        }
      })
      .catch(() => {
        /* sin conversaciones: se muestra la bienvenida */
      })
      .finally(() => {
        if (alive) setHistoryLoaded(true)
      })

    return () => {
      alive = false
    }
  }, [enabled])

  // Cambiar de conversación desde el sidebar
  const selectConversation = useCallback(async (conversationId) => {
    if (!conversationId) return
    abortRef.current?.abort()
    const seq = ++loadSeqRef.current
    setActiveConversationId(conversationId)
    setMessages([])
    try {
      const history = await getConversationMessages(conversationId)
      if (seq === loadSeqRef.current) setMessages(history.map(fromServer))
    } catch {
      if (seq === loadSeqRef.current) setMessages([])
    }
  }, [])

  // "Nuevo chat": empieza vacío; la conversación se crea al enviar el primer mensaje
  const reset = useCallback(() => {
    abortRef.current?.abort()
    loadSeqRef.current += 1
    setMessages([])
    setActiveConversationId(null)
    setIsStreaming(false)
  }, [])

  useEffect(() => () => abortRef.current?.abort(), [])

  return {
    messages,
    conversations,
    activeConversationId,
    isStreaming,
    historyLoaded,
    send,
    sendDemo,
    pushUser,
    pushAgent,
    beginAgent,
    updateMessage,
    reset,
    selectConversation,
    saveExchange,
  }
}
