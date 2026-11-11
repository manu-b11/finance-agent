import { categoryLabel, formatCOP, formatDate } from '../../lib/format.js'

const TITLES = {
  created: 'Movimiento registrado',
  updated: 'Movimiento actualizado',
  deleted: 'Movimiento eliminado',
}

const BADGES = { created: 'Registrado', updated: 'Actualizado', deleted: 'Eliminado' }

/*
  transaction: TransactionRead del backend.
  action: 'created' | 'updated' | 'deleted'. En deleted el orquestador devuelve
  { deleted, transaction }, y useChatStream ya extrae la transacción.
*/
export default function TransactionCard({ action = 'created', transaction }) {
  const income = transaction.type === 'income'
  return (
    <div className="card">
      <div className="card-head">
        <b>{TITLES[action] ?? TITLES.created}</b>
        <span className={`badge ${action === 'deleted' ? 'warn' : 'ok'}`}>
          {BADGES[action] ?? BADGES.created}
        </span>
      </div>

      <div className="card-body">
        <div className="row"><span>Concepto</span><span>{transaction.concept}</span></div>
        <div className="row"><span>Tipo</span><span>{income ? 'Ingreso' : 'Gasto'}</span></div>
        {transaction.category && (
          <div className="row"><span>Categoría</span><span>{categoryLabel(transaction.category)}</span></div>
        )}
        <div className="row"><span>Fecha</span><span>{formatDate(transaction.occurred_on)}</span></div>
        <div className="row total">
          <span style={{ color: 'var(--text)' }}>Monto</span>
          <span className={income ? 'income' : 'expense'}>
            {income ? '+' : '−'} {formatCOP(transaction.amount)}
          </span>
        </div>
      </div>
    </div>
  )
}
