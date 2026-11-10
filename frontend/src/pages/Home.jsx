import { useRef, useState } from 'react'
import { useAuth } from '../hooks/useAuth.jsx'
import { useChatStream } from '../hooks/useChatStream.js'
import { uploadInvoice } from '../api/invoices.js'
import { errorMessage } from '../api/client.js'
import { firstName } from '../lib/format.js'
import Sidebar from '../components/layout/Sidebar.jsx'
import Topbar from '../components/layout/Topbar.jsx'
import Welcome from '../components/chat/Welcome.jsx'
import Composer from '../components/chat/Composer.jsx'
import Messages from '../components/chat/Messages.jsx'

const isDesktop = () => window.matchMedia('(min-width:1024px)').matches

export default function Home() {
  const { user, logout } = useAuth()
  const { messages, isStreaming, historyLoaded, send, pushUser, beginAgent, updateMessage, reset } = useChatStream()

  const [value, setValue] = useState('')
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const composerRef = useRef(null)

  const inChat = messages.length > 0
  const busy = isStreaming || uploading

  const openSidebar = () => (isDesktop() ? setCollapsed(false) : setDrawerOpen(true))
  const closeSidebar = () => (isDesktop() ? setCollapsed(true) : setDrawerOpen(false))

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
      onFileChange={setFile}
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
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onCollapse={closeSidebar}
        onNewChat={newChat}
        onLogout={logout}
      />

      <main className="main">
        <Topbar onMenu={openSidebar} />

        <div className="content">
          {!historyLoaded ? null : inChat ? (
            <Messages messages={messages} busy={busy} onSend={submit} />
          ) : (
            <Welcome
              name={firstName(user)}
              onFill={fill}
              onSend={submit}
              onUpload={() => composerRef.current?.openFilePicker()}
            >
              {composer}
            </Welcome>
          )}
        </div>

        {inChat && <div className="dock">{composer}</div>}
      </main>
    </div>
  )
}
