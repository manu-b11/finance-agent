import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import { useConfirm } from '../hooks/useConfirm.jsx'
import { useChatStream } from '../hooks/useChatStream.js'
import { uploadInvoice } from '../api/invoices.js'
import { errorMessage } from '../api/client.js'
import { formatCOP, formatDate, firstName } from '../lib/format.js'
import Sidebar from '../components/layout/Sidebar.jsx'
import Topbar from '../components/layout/Topbar.jsx'
import Welcome from '../components/chat/Welcome.jsx'
import Composer from '../components/chat/Composer.jsx'
import Messages from '../components/chat/Messages.jsx'
import AuthModal from '../components/auth/AuthModal.jsx'
import { detectIntent, LIMIT_INTENT } from '../lib/guestIntent.js'
import { capabilitiesText } from '../lib/capabilities.js'

const isDesktop = () => window.matchMedia('(min-width:1024px)').matches
const GUEST_LIMIT = 10

export default function Home() {
  const { user, loading, logout } = useAuth()
  const confirm = useConfirm()
  const location = useLocation()
  const navigate = useNavigate()
  const {
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
    removeMessage,
    reset,
    selectConversation,
    saveExchange,
  } = useChatStream({ enabled: !loading && !!user })

  const [value, setValue] = useState('')
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [authMode, setAuthMode] = useState(null)
  const [guestTurns, setGuestTurns] = useState(0)
  const [pending, setPending] = useState(null)
  const [pendingReady, setPendingReady] = useState(false)
  const composerRef = useRef(null)

  useEffect(() => {
    const incoming = location.state
    if (!incoming || !historyLoaded) return
    if (incoming.conversationId) selectConversation(incoming.conversationId)
    else if (incoming.newChat) reset()
    if (incoming.prefill) {
      setValue(incoming.prefill)
      window.setTimeout(() => composerRef.current?.focus(), 150)
    }
    navigate('/', { replace: true, state: null })
  }, [location.state, historyLoaded, selectConversation, reset, navigate])

  useEffect(() => {
    if (!user || !historyLoaded || !pending || pendingReady) return
    reset()
    setPendingReady(true)
  }, [user, historyLoaded, pending, pendingReady, reset])

  useEffect(() => {
    if (!pendingReady || !pending) return
    const { text, file: attached } = pending
    setPending(null)
    setPendingReady(false)
    if (attached) handleInvoice(attached, text)
    else send(text)
  }, [pendingReady, pending, send])

  const inChat = messages.length > 0
  const busy = isStreaming || uploading

  if (loading) return <div className="boot" />

  const openSidebar = () => (isDesktop() ? setCollapsed(false) : setDrawerOpen(true))
  const closeSidebar = () => (isDesktop() ? setCollapsed(true) : setDrawerOpen(false))

  const openAuth = (mode = 'login') => {
    setAuthMode(mode)
    setDrawerOpen(false)
  }

  const openSignup = (mode, data) => {
    if (data?.kind && data.kind !== 'limit') setPending({ text: data.text ?? '', file: data.file ?? null })
    openAuth(mode)
  }

  const closeAuth = () => {
    setAuthMode(null)
    setPending(null)
  }

  const finishAuth = () => {
    setAuthMode(null)
    setDrawerOpen(false)
    setGuestTurns(0)
    reset()
    window.setTimeout(() => composerRef.current?.focus(), 50)
  }

  const history = conversations.length
    ? [
        {
          label: 'Conversaciones',
          items: conversations.map((c) => ({ id: c.id, title: c.title })),
        },
      ]
    : []

  const openConversation = (item) => {
    selectConversation(item.id)
    setDrawerOpen(false)
  }

  const newChat = () => {
    reset()
    setValue('')
    setFile(null)
    setDrawerOpen(false)
  }

  const fill = (text) => {
    setValue(text)
    composerRef.current?.focus()
  }

  // Respuesta fija: no pasa por la IA. Con sesión se guarda en el historial (solo BD).
  const showCapabilities = async () => {
    const question = '¿Qué puedes hacer?'
    const answer = capabilitiesText({ guest: !user })
    pushUser(question)
    pushAgent({ text: answer })
    if (!user) return
    try {
      await saveExchange(question, answer, 'Qué puede hacer Finly')
    } catch {
      /* el mensaje ya se mostró; guardar el historial es opcional */
    }
  }

  const changeFile = (next) => setFile(next)

  // Subida de factura: se crea el borrador y se muestra para revisión (RF-19, RF-20)
  async function handleInvoice(attached, text, { appendUser = true } = {}) {
    if (appendUser) pushUser(text, attached.name, attached)
    const id = beginAgent()
    setUploading(true)
    try {
      const invoice = await uploadInvoice(attached)
      updateMessage(id, {
        status: 'done',
        text: 'Revisé tu factura. Esto fue lo que encontré; **aún no la he registrado**. Revísala y corrígela si algo no coincide.',
        cards: [{ type: 'invoice', data: invoice }],
      })

      // La subida no pasa por /chat: guardamos un resumen de texto para que quede en el historial.
      const details = [
        invoice.merchant ? `Comercio: ${invoice.merchant}` : null,
        invoice.total != null ? `Total: ${formatCOP(invoice.total)}` : null,
        invoice.issued_on ? `Fecha: ${formatDate(invoice.issued_on)}` : null,
      ]
        .filter(Boolean)
        .join(' · ')
      const userText = text || `Subí una factura (${attached.name})`
      const assistantText = `Revisé tu factura${details ? ` (${details})` : ''}. Aún no la he registrado; revísala y confírmala cuando esté lista.`
      try {
        await saveExchange(userText, assistantText, undefined, [
          { type: 'invoice', data: { invoice_id: invoice.id } },
        ])
      } catch {
        /* el historial es opcional; la factura ya se mostró */
      }
    } catch (err) {
      // La subida pudo crear el borrador antes de fallar: reintentar podría duplicarlo.
      updateMessage(id, { status: 'error', error: errorMessage(err), sideEffects: true })
    } finally {
      setUploading(false)
    }
  }

  // override: texto enviado desde un chip / sugerencia (no toca lo escrito ni el archivo)
  async function submit(override) {
    if (busy) return
    const text = (override ?? value).trim()
    const attached = override === undefined ? file : null
    if (!text && !attached) return

    if (!user) {
      const intent = detectIntent(text, Boolean(attached))
      const blocked = !intent && guestTurns >= GUEST_LIMIT
      if (override === undefined) {
        setValue('')
        setFile(null)
      }
      if (intent || blocked) {
        const prompt = intent ?? LIMIT_INTENT
        pushUser(text, attached?.name)
        pushAgent({ text: prompt.reply, cards: [{ type: 'signup', data: { ...prompt, text, file: attached } }] })
        return
      }
      setGuestTurns((n) => n + 1)
      await sendDemo(text)
      return
    }

    if (override === undefined) {
      setValue('')
      setFile(null)
    }
    if (attached) await handleInvoice(attached, text)
    else await send(text)
  }

  // Reintenta un turno: quita la respuesta y reenvía el mensaje ya visible.
  const retry = async (message) => {
    if (busy) return
    if (message.sideEffects) {
      const ok = await confirm({
        title: 'Repetir esta acción',
        message:
          'Esta respuesta ya registró o modificó datos. Si la generas de nuevo, podrías duplicar la operación.',
        confirmLabel: 'Sí, repetir',
        danger: true,
      })
      if (!ok) return
    }
    const index = messages.findIndex((m) => m.id === message.id)
    if (index < 0) return
    let previous = index - 1
    while (previous >= 0 && messages[previous].role !== 'user') previous -= 1
    if (previous < 0) return
    const prompt = messages[previous]
    removeMessage(message.id)
    if (!user) sendDemo(prompt.text, { appendUser: false })
    else if (prompt.file) handleInvoice(prompt.file, prompt.text, { appendUser: false })
    else send(prompt.text, { appendUser: false })
  }

  const composer = (
    <Composer
      ref={composerRef}
      value={value}
      onChange={setValue}
      file={file}
      onFileChange={changeFile}
      onSubmit={() => submit()}
      onSendText={(t) => submit(t)}
      disabled={busy}
      autoFocus={inChat}
    />
  )

  return (
    <div className={`app${inChat ? ' is-chat' : ''}${collapsed ? ' collapsed' : ''}`}>
      <Sidebar
        user={user}
        history={history}
        activeId={activeConversationId}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onCollapse={closeSidebar}
        onNewChat={newChat}
        onSelectChat={openConversation}
        onLogout={logout}
        onAuth={openAuth}
      />

      <main className="main">
        <Topbar onMenu={openSidebar} user={user} onAuth={openAuth} />

        <div className="content">
          {!historyLoaded ? null : inChat ? (
            <Messages
              messages={messages}
              busy={busy}
              onSend={submit}
              onSignup={openSignup}
              onRetry={retry}
            />
          ) : (
            <Welcome
              name={user ? firstName(user) : ''}
              guest={!user}
              onFill={fill}
              onSend={submit}
              onUpload={() => composerRef.current?.openFilePicker()}
              onCapabilities={showCapabilities}
            >
              {composer}
            </Welcome>
          )}
        </div>

        {inChat && <div className="dock">{composer}</div>}
      </main>

      {authMode && (
        <AuthModal
          mode={authMode}
          onSwitch={setAuthMode}
          onClose={closeAuth}
          onSuccess={finishAuth}
        />
      )}
    </div>
  )
}
