import { useRef, useState } from 'react'
import { useAuth } from '../hooks/useAuth.jsx'
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

const isDesktop = () => window.matchMedia('(min-width:1024px)').matches
const GUEST_LIMIT = 3

export default function Home() {
  const { user, loading, logout } = useAuth()
  const {
    messages,
    conversations,
    activeConversationId,
    isStreaming,
    historyLoaded,
    send,
    sendDemo,
    pushUser,
    beginAgent,
    updateMessage,
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
  const composerRef = useRef(null)

  const inChat = messages.length > 0
  const busy = isStreaming || uploading

  if (loading) return <div className="boot" />

  const openSidebar = () => (isDesktop() ? setCollapsed(false) : setDrawerOpen(true))
  const closeSidebar = () => (isDesktop() ? setCollapsed(true) : setDrawerOpen(false))

  const openAuth = (mode = 'login') => {
    setAuthMode(mode)
    setDrawerOpen(false)
  }

  // Tras registrarse o iniciar sesión se conserva lo que el invitado había escrito.
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

  // El invitado puede adjuntar la factura, pero necesita cuenta para subirla:
  // se conserva el archivo y se abre el registro.
  const changeFile = (next) => {
    setFile(next)
    if (next && !user) setAuthMode('register')
  }

  // Subida de factura: se crea el borrador y se muestra para revisión (RF-19, RF-20)
  async function handleInvoice(attached, text) {
    pushUser(text, attached.name)
    const id = beginAgent()
    setUploading(true)
    try {
      const invoice = await uploadInvoice(attached)
      updateMessage(id, {
        status: 'done',
        text: 'Revisé tu factura. Esto fue lo que encontré; **aún no la he registrado**. Revísala y corrígela si algo no coincide.',
        cards: [{ type: 'invoice_draft', data: invoice }],
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
        await saveExchange(userText, assistantText)
      } catch {
        /* el historial es opcional; la factura ya se mostró */
      }
    } catch (err) {
      updateMessage(id, { status: 'error', error: errorMessage(err) })
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

    // Invitado: puede probar la demo unas cuantas veces; después se le pide cuenta.
    if (!user) {
      if (attached || guestTurns >= GUEST_LIMIT) {
        if (text) setValue(text)
        setAuthMode('register')
        return
      }
      setValue('')
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
            <Messages messages={messages} busy={busy} onSend={submit} />
          ) : (
            <Welcome
              name={user ? firstName(user) : ''}
              guest={!user}
              guestLeft={!user ? Math.max(GUEST_LIMIT - guestTurns, 0) : 0}
              onFill={fill}
              onSend={submit}
              onUpload={() => composerRef.current?.openFilePicker()}
            >
              {composer}
            </Welcome>
          )}
        </div>

        {!user && guestTurns >= GUEST_LIMIT && (
          <div className="guest-limit">
            <div className="guest-limit-copy">
              <b>¿Seguimos?</b>
              <span>Crea una cuenta para seguir conversando y guardar tus finanzas.</span>
            </div>
            <button className="btn primary" onClick={() => openAuth('register')}>
              Crear cuenta
            </button>
          </div>
        )}

        {inChat && <div className="dock">{composer}</div>}
      </main>

      {authMode && (
        <AuthModal
          mode={authMode}
          onSwitch={setAuthMode}
          onClose={() => setAuthMode(null)}
          onSuccess={finishAuth}
        />
      )}
    </div>
  )
}
