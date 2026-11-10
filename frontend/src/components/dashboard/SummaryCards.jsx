import { formatCOP, formatDate } from '../../lib/format.js'

// data = MonthlyReportRead de /dashboard (summary): { total_income, total_expenses, balance, start_date, end_date, ... }
// Los totales los calcula services/ con Decimal; aquí solo se muestran (RNF-05).
export function BalanceCard({ data }) {
  const period = data.start_date && data.end_date ? `${formatDate(data.start_date)} – ${formatDate(data.end_date)}` : 'Este mes'
  return (
    <div className="card">
      <div className="card-head">
        <b>Balance del mes</b>
        <span className="badge">Datos reales</span>
      </div>
      <div className="card-body">
        <div className="row"><span>Periodo</span><span>{period}</span></div>
        <div className="row"><span>Ingresos</span><span className="income">{formatCOP(data.total_income)}</span></div>
        <div className="row"><span>Gastos</span><span className="expense">{formatCOP(data.total_expenses)}</span></div>
        <div className="items" />
        <div className="row total">
          <span style={{ color: 'var(--text)' }}>Balance</span>
          <span>{formatCOP(data.balance)}</span>
        </div>
      </div>
    </div>
  )
}
