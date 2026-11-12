import { formatCOP } from '../../lib/format.js'

const TYPE_LABELS = { expense: 'Gasto', income: 'Ingreso' }

export default function SignupCard({ data, onSignup }) {
  const showDetails = data.kind === 'expense' || data.kind === 'income'
  const hasNote = data.kind !== 'limit'

  return (
    <div className="card">
      <div className="card-head">
        <b>{data.title}</b>
        {data.saves && <span className="badge warn">Sin guardar</span>}
      </div>

      {showDetails && (
        <div className="card-body">
          <div className="row"><span>Tipo</span><span>{TYPE_LABELS[data.kind]}</span></div>
          {data.amount != null && <div className="row"><span>Valor</span><span>{formatCOP(data.amount)}</span></div>}
          <div className="row"><span>Fecha</span><span>Hoy</span></div>
        </div>
      )}

      <div className="card-actions" style={showDetails ? undefined : { paddingTop: 14 }}>
        <button className="btn primary" onClick={() => onSignup('register', data)}>Crear cuenta gratis</button>
        <button className="btn" onClick={() => onSignup('login', data)}>Ya tengo cuenta</button>
      </div>
      {hasNote && (
        <div className="card-note">
          {data.saves ? 'Se guardará con lo que acabas de escribir.' : 'Lo respondemos apenas entres a tu cuenta.'}
        </div>
      )}
    </div>
  )
}
