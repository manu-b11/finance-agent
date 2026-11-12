import { categoryLabel, formatCOP, formatDate } from '../../lib/format.js'

/*
  data = resultado de la tool list_transactions
  { count, transactions: [{ id, type, amount, concept, category, occurred_on }], filters }
*/
export default function TransactionsCard({ data }) {
  const items = data?.transactions ?? []
  const count = data?.count ?? items.length
  const filters = data?.filters ?? {}
  const isExpense = filters.type === 'expense'
  const isIncome = filters.type === 'income'
  const title = isExpense ? 'Gastos' : isIncome ? 'Ingresos' : 'Movimientos'

  let period = ''
  if (filters.start_date && filters.end_date) {
    period = `${formatDate(filters.start_date)} – ${formatDate(filters.end_date)}`
  } else if (filters.start_date) {
    period = `Desde ${formatDate(filters.start_date)}`
  } else if (filters.end_date) {
    period = `Hasta ${formatDate(filters.end_date)}`
  }

  return (
    <div className="card statement-card">
      <div className="card-head">
        <b>{title}</b>
        <span className="badge">{count}</span>
      </div>
      <div className="card-body">
        {period && <div className="card-note tx-period">{period}</div>}
        {items.length === 0 ? (
          <div className="row">
            <span>
              {isExpense
                ? 'No hay gastos en ese periodo.'
                : isIncome
                  ? 'No hay ingresos en ese periodo.'
                  : 'No hay movimientos en ese periodo.'}
            </span>
          </div>
        ) : (
          <div className="items tx-items">
            {items.map((tx) => {
              const income = tx.type === 'income'
              return (
                <div className="row tx-row" key={tx.id}>
                  <span className="tx-concept">
                    {tx.concept}
                    <small>
                      {formatDate(tx.occurred_on)}
                      {tx.category ? ` · ${categoryLabel(tx.category)}` : ''}
                    </small>
                  </span>
                  <span className={income ? 'income' : 'expense'}>
                    {income ? '+' : '−'} {formatCOP(tx.amount)}
                  </span>
                </div>
              )
            })}
          </div>
        )}
        {count > items.length && (
          <div className="card-note" style={{ padding: '8px 0 0' }}>
            Mostrando los últimos {items.length} de {count}.
          </div>
        )}
      </div>
    </div>
  )
}
