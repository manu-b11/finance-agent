import { useEffect, useRef, useState } from 'react'
import { getInvoice } from '../../api/invoices.js'
import { ApiError } from '../../api/client.js'
import { categoryLabel, formatCOP, formatDate } from '../../lib/format.js'

const FIELD_LABELS = { merchant: 'establecimiento', issued_on: 'fecha', total: 'total', category: 'categoría' }

/*
  draft: InvoiceRead (ver api/invoices.js).
  La confirmación y las correcciones las hace el agente (tools confirm_invoice / update_invoice...),
  así que los botones envían un mensaje al chat con el id de la factura (onAction).
  Al terminar cada turno del agente (busy: true → false) la tarjeta vuelve a consultar la factura.
*/
export default function InvoiceDraftCard({ draft, busy, onAction }) {
  const [invoice, setInvoice] = useState(draft)
  const [discarded, setDiscarded] = useState(false)
  const wasBusy = useRef(false)

  useEffect(() => {
    if (busy) {
      wasBusy.current = true
      return
    }
    if (!wasBusy.current || invoice.status === 'confirmed' || discarded) return
    wasBusy.current = false
    getInvoice(invoice.id)
      .then(setInvoice)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) setDiscarded(true)
      })
  }, [busy, invoice.id, invoice.status, discarded])

  const confirmed = invoice.status === 'confirmed'
  const missing = invoice.missing_fields ?? []
  const incomplete = missing.length > 0 || invoice.total == null
  const mismatch = invoice.total_matches_items === false

  if (discarded) {
    return (
      <div className="card">
        <div className="card-head"><b>Factura descartada</b><span className="badge">Sin registrar</span></div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-head">
        <b>{confirmed ? 'Factura registrada' : 'Factura en borrador'}</b>
        {confirmed
          ? <span className="badge ok">Confirmada</span>
          : <span className="badge warn">Pendiente de confirmar</span>}
      </div>

      <div className="card-body">
        <div className="row"><span>Comercio</span><span>{invoice.merchant ?? '—'}</span></div>
        {invoice.invoice_number && <div className="row"><span>Número</span><span>{invoice.invoice_number}</span></div>}
        <div className="row"><span>Fecha</span><span>{invoice.issued_on ? formatDate(invoice.issued_on) : '—'}</span></div>
        <div className="row">
          <span>{confirmed ? 'Categoría' : 'Categoría sugerida'}</span>
          <span>{invoice.category ? categoryLabel(invoice.category) : '—'}</span>
        </div>

        <div className="items">
          {(invoice.items ?? []).map((it) => (
            <div className="row" key={it.position}>
              <span>{it.description}{Number(it.quantity) !== 1 ? ` x ${Number(it.quantity)}` : ''}</span>
              <span>{formatCOP(it.line_total)}</span>
            </div>
          ))}
        </div>

        <div className="row total">
          <span style={{ color: 'var(--text)' }}>Total</span>
          <span className="expense">{invoice.total == null ? '—' : formatCOP(invoice.total)}</span>
        </div>
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
