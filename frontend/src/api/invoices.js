import { request } from './client.js'

/*
  InvoiceRead (app/schemas/invoice.py):
  { id, status: 'draft'|'confirmed', original_filename, merchant, invoice_number, issued_on, total, category,
    items: [{ position, description, quantity, unit_price, line_total }], items_total, total_matches_items,
    missing_fields: ['merchant'|'issued_on'|'total'|'category'], transaction_id, created_at, confirmed_at }
*/

// POST /invoices (multipart, campo "file"; JPG, PNG o PDF). Crea el borrador (RB-06).
export function uploadInvoice(file) {
  const form = new FormData()
  form.append('file', file)
  return request('/invoices', { method: 'POST', body: form })
}

export const getInvoice = (id) => request(`/invoices/${id}`)

export const listInvoices = () => request('/invoices')

// No existe endpoint REST para confirmar: la confirmación pasa por el chat (tool confirm_invoice).
