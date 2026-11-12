import { useEffect, useRef, useState } from 'react'
import { getInvoice } from '../../api/invoices.js'
import { ApiError } from '../../api/client.js'
import { categoryLabel, formatCOP, formatDate } from '../../lib/format.js'

const FIELD_LABELS = { merchant: 'establecimiento', issued_on: 'fecha', total: 'total', category: 'categoría' }

/*
  draft puede ser:
    - una factura completa (InvoiceRead), para mostrarla de inmediato, o
    - una referencia { invoice_id }, que se guarda en el historial.

  Al montar (y al terminar cada turno del agente) se consulta la factura real,
  así el estado siempre refleja si sigue en borrador, fue confirmada o descartada.
*/
export default function InvoiceDraftCard({ draft, busy, onAction }) {
  const invoiceId = draft?.invoice_id ?? draft?.id
  const [invoice, setInvoice] = useState(() => (draft?.status ? draft : null))
  const [discarded, setDiscarded] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const wasBusy = useRef(false)

  useEffect(() => {
    if (busy) {
      wasBusy.current = true
      return
    }
    if (wasBusy.current) {
      wasBusy.current = false
      setReloadKey((key) => key + 1)
    }
  }, [busy])

  useEffect(() => {
    if (!invoiceId || discarded) return undefined
    let alive = true
    setLoadError('')
    getInvoice(invoiceId)
      .then((fresh) => {
        if (alive) setInvoice(fresh)
      })
      .catch((err) => {
        if (!alive) return
        if (err instanceof ApiError && err.status === 404) setDiscarded(true)
        else setLoadError('No pude cargar la factura. Intenta de nuevo en un momento.')
      })
    return () => {
      alive = false
    }
  }, [invoiceId, reloadKey, discarded])

  if (discarded) {
    return (
      <div className="card invoice-card">
        <div className="card-head"><b>Factura descartada</b><span className="badge">Sin registrar</span></div>
      </div>
    )
  }

  if (!invoice) {
    return (
      <div className="card invoice-card">
        <div className="card-head">
          <b>Factura</b>
          <span className="badge">Consultando…</span>
        </div>
        <div className="card-body">
          {loadError ? (
            <div className="card-note warn-text" style={{ padding: 0 }}>{loadError}</div>
          ) : (
            <div className="invoice-skeleton" aria-label="Cargando factura">
              <i /><i /><i />
            </div>
          )}
        </div>
      </div>
    )
  }

  const confirmed = invoice.status === 'confirmed'
  const missing = invoice.missing_fields ?? []
  const incomplete = missing.length > 0 || invoice.total == null
  const mismatch = invoice.total_matches_items === false
  const items = invoice.items ?? []
  const merchant = invoice.merchant ?? 'Factura sin nombre'

  return (
    <div className="card invoice-card">
      <div className="card-head">
        <b>{confirmed ? 'Factura registrada' : 'Factura'}</b>
        {confirmed
          ? <span className="badge ok">Confirmada</span>
          : <span className="badge warn">Pendiente de confirmar</span>}
      </div>

      <div className="card-body">
        <div className="invoice-meta">
          <b>{merchant}</b>
          <span>
            {invoice.issued_on ? formatDate(invoice.issued_on) : 'Sin fecha'}
            {invoice.category ? ` · ${categoryLabel(invoice.category)}` : ''}
          </span>
        </div>

        {items.length > 0 && (
          <div className="items invoice-items">
            {items.map((it) => (
              <div className="row" key={it.position}>
                <span>
                  {it.description}
                  {Number(it.quantity) !== 1 ? ` × ${Number(it.quantity)}` : ''}
                </span>
                <span>{formatCOP(it.line_total)}</span>
              </div>
            ))}
          </div>
        )}

        <div className="row total invoice-total">
          <span>Total</span>
          <span>{invoice.total == null ? '—' : formatCOP(invoice.total)}</span>
        </div>

        {(invoice.invoice_number || invoice.original_filename) && (
          <details className="invoice-details">
            <summary>Ver detalle</summary>
            {invoice.invoice_number && (
              <div className="row">
                <span>Número</span>
                <span>{invoice.invoice_number}</span>
              </div>
            )}
            {invoice.original_filename && (
              <div className="row">
                <span>Archivo</span>
                <span>{invoice.original_filename}</span>
              </div>
            )}
          </details>
        )}
      </div>

      {!confirmed && missing.length > 0 && (
        <div className="card-note warn-text">
          No pude leer: {missing.map((f) => FIELD_LABELS[f] ?? f).join(', ')}. Indícame esos datos para poder registrarla.
        </div>
      )}
      {!confirmed && mismatch && (
        <div className="card-note warn-text">
          El total no coincide con la suma de los ítems ({formatCOP(invoice.items_total)}). Revísalo antes de confirmar.
        </div>
      )}

      {!confirmed && (
        <>
          <div className="card-actions">
            <button
              className="btn primary"
              disabled={busy || incomplete}
              onClick={() => onAction(`Confirmo los datos. Registra la factura ${invoice.id}.`)}
            >
              Confirmar y registrar
            </button>
            <button
              className="btn"
              disabled={busy}
              onClick={() => onAction(`Quiero corregir datos de la factura ${invoice.id}.`)}
            >
              Corregir datos
            </button>
          </div>
          <div className="card-note">El gasto se crea solo después de tu confirmación.</div>
        </>
      )}
    </div>
  )
}
