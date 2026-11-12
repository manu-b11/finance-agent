import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import { useConversationList } from '../hooks/useConversationList.js'
import { listInvoices, uploadInvoice } from '../api/invoices.js'
import { errorMessage } from '../api/client.js'
import { categoryLabel, formatCOP, formatDate } from '../lib/format.js'
import Icon from '../components/Icon.jsx'
import Sidebar from '../components/layout/Sidebar.jsx'
import Topbar from '../components/layout/Topbar.jsx'

const isDesktop = () => window.matchMedia('(min-width:1024px)').matches

export default function Invoices() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const history = useConversationList(Boolean(user))
  const inputRef = useRef(null)

  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [openId, setOpenId] = useState(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    listInvoices()
      .then(setInvoices)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  const openSidebar = () => (isDesktop() ? setCollapsed(false) : setDrawerOpen(true))
  const closeSidebar = () => (isDesktop() ? setCollapsed(true) : setDrawerOpen(false))

  async function handleFile(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setError('')
    setUploading(true)
    try {
      const invoice = await uploadInvoice(file)
      setInvoices((prev) => [invoice, ...prev])
      setOpenId(invoice.id)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className={`app${collapsed ? ' collapsed' : ''}`}>
      <Sidebar
        user={user}
        current="/facturas"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onCollapse={closeSidebar}
        history={history}
        onNewChat={() => navigate('/', { state: { newChat: true } })}
        onSelectChat={(item) => navigate('/', { state: { conversationId: item.id } })}
        onLogout={logout}
      />

      <main className="main">
        <Topbar onMenu={openSidebar} user={user} />

        <div className="content">
          <section className="page">
            <div className="page-head">
              <div>
                <h1>Facturas</h1>
                <p>Sube una factura y revisa lo que Finly encontró antes de registrarla.</p>
              </div>
              <button className="btn primary" disabled={uploading} onClick={() => inputRef.current?.click()}>
                <Icon name="upload" />{uploading ? 'Leyendo factura…' : 'Subir factura'}
              </button>
              <input
                ref={inputRef}
                type="file"
                hidden
                accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
                onChange={handleFile}
              />
            </div>

            {error && <div className="page-error">{error}</div>}

            {loading ? null : invoices.length === 0 ? (
              <div className="page-empty">Aún no tienes facturas. Sube una para empezar.</div>
            ) : (
              <div className="inv-list">
                {invoices.map((inv) => {
                  const confirmed = inv.status === 'confirmed'
                  const open = openId === inv.id
                  return (
                    <article className="card inv" key={inv.id}>
                      <button className="inv-head" onClick={() => setOpenId(open ? null : inv.id)} aria-expanded={open}>
                        <div className="inv-main">
                          <b>{inv.merchant ?? inv.original_filename ?? 'Factura sin nombre'}</b>
                          <span>
                            {formatDate(inv.issued_on ?? inv.created_at)}
                            {inv.category ? ` · ${categoryLabel(inv.category)}` : ''}
                          </span>
                        </div>
                        <div className="inv-side">
                          <span className="inv-total">{inv.total == null ? '—' : formatCOP(inv.total)}</span>
                          <span className={`badge ${confirmed ? 'ok' : 'warn'}`}>{confirmed ? 'Confirmada' : 'Borrador'}</span>
                        </div>
                      </button>

                      {open && (
                        <>
                          <div className="card-body">
                            {inv.invoice_number && <div className="row"><span>Número</span><span>{inv.invoice_number}</span></div>}
                            <div className="items">
                              {inv.items.length === 0 && <div className="row"><span>Sin ítems</span><span /></div>}
                              {inv.items.map((it) => (
                                <div className="row" key={it.position}>
                                  <span>{it.description}{Number(it.quantity) !== 1 ? ` x ${Number(it.quantity)}` : ''}</span>
                                  <span>{formatCOP(it.line_total)}</span>
                                </div>
                              ))}
                            </div>
                            <div className="row total">
                              <span style={{ color: 'var(--text)' }}>Total</span>
                              <span className="expense">{inv.total == null ? '—' : formatCOP(inv.total)}</span>
                            </div>
                          </div>
                          {!confirmed && (
                            <>
                              <div className="card-actions">
                                <button className="btn primary" onClick={() => navigate('/')}>Ir al chat para confirmar</button>
                              </div>
                              <div className="card-note">El gasto se crea solo después de tu confirmación en el chat.</div>
                            </>
                          )}
                        </>
                      )}
                    </article>
                  )
                })}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  )
}
