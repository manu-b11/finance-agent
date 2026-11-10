import { useCallback, useEffect, useRef, useState } from 'react'
import { getHistory, streamChat } from '../api/chat.js'
import { getDashboard } from '../api/dashboard.js'

/*
  Mensaje de usuario: { id, role: 'user', text, fileName? }
  Mensaje de agente:  { id, role: 'agent', text, cards: [{type, data}], quickReplies: [{label, text}],
                        status: 'typing' | 'streaming' | 'done' | 'error', toolLabel?, error? }
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

export function useChatStream() {
  const [messages, setMessages] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const abortRef = useRef(null)

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

  const send = useCallback(
    async (text) => {
      pushUser(text)
      const id = beginAgent()
      const controller = new AbortController()
      abortRef.current = controller
      setIsStreaming(true)
      const tools = new Set()
      try {
        for await (const { event, data } of streamChat(text, { signal: controller.signal })) {
          if (event === 'tool_call') {
            tools.add(data?.name)
            updateMessage(id, { toolLabel: labelFor(data?.name ?? '') })
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
      }
    },
    [pushUser, beginAgent, updateMessage],
  )

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setMessages([])
    setIsStreaming(false)
  }, [])

  // Al montar: recuperar la conversación guardada en el servidor
  useEffect(() => {
    let alive = true
    getHistory()
      .then((items) => {
        if (!alive) return
        // Si el usuario ya escribió mientras cargaba, el historial va antes de esos mensajes
        setMessages((prev) => [
          ...items.map((m) =>
            m.role === 'user'
              ? { id: `h-${m.id}`, role: 'user', text: m.content }
              : { id: `h-${m.id}`, role: 'agent', text: m.content, cards: [], quickReplies: [], status: 'done' },
          ),
          ...prev,
        ])
      })
      .catch(() => {
        /* sin historial: se muestra la bienvenida */
      })
      .finally(() => alive && setHistoryLoaded(true))
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => () => abortRef.current?.abort(), [])

  return { messages, isStreaming, historyLoaded, send, pushUser, pushAgent, beginAgent, updateMessage, reset }
}
