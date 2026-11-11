import { useState } from 'react'
import { errorMessage } from '../../api/client.js'
import { downloadMonthlyReport } from '../../api/reports.js'
import { categoryLabel, formatCOP, formatMonth } from '../../lib/format.js'

/*
  report: resultado de la tool get_monthly_report
  { month, total_income, total_expenses, balance, transaction_count, top_category, pdf_url, ... }
  El PDF se pide con el mismo JWT del chat a través de api/reports.js.
*/
export default function ReportCard({ report }) {
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState('')
  const month = report.month

  const download = async () => {
    setDownloading(true)
    setError('')
    try {
      const blob = await downloadMonthlyReport(month)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `informe-financiero-${month}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="card">
      <div className="card-head">
        <b>Informe de {formatMonth(month)}</b>
        <span className="badge ok">PDF listo</span>
      </div>

      <div className="card-body">
        <div className="row"><span>Ingresos</span><span className="income">{formatCOP(report.total_income)}</span></div>
        <div className="row"><span>Gastos</span><span className="expense">{formatCOP(report.total_expenses)}</span></div>
        <div className="row"><span>Movimientos</span><span>{report.transaction_count}</span></div>
        {report.top_category && (
          <div className="row">
            <span>Mayor gasto</span>
            <span>{categoryLabel(report.top_category)}</span>
          </div>
        )}
        <div className="row total">
          <span style={{ color: 'var(--text)' }}>Balance</span>
          <span>{formatCOP(report.balance)}</span>
        </div>
      </div>

      <div className="card-actions">
        <button className="btn primary" onClick={download} disabled={downloading}>
          {downloading ? 'Generando PDF…' : 'Descargar PDF'}
        </button>
      </div>
      {error && <div className="card-note warn-text">{error}</div>}
    </div>
  )
}
