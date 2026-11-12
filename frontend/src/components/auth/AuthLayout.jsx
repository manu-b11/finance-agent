import { Link } from 'react-router-dom'
import Icon from '../Icon.jsx'
import BrandMark from '../BrandMark.jsx'

const POINTS = [
  'Registra gastos e ingresos conversando',
  'Sube una factura y confírmala en segundos',
  'Consulta tu balance y tus informes cuando quieras',
]

// Estructura compartida por /login y /register.
export default function AuthLayout({ children }) {
  return (
    <div className="auth-page">
      <aside className="auth-visual" aria-hidden="true">
        <div className="auth-brand-lg">
          <BrandMark />
          <span className="wordmark">Finly</span>
        </div>

        <h1>Tus finanzas,<br />en una conversación.</h1>
        <p>
          Habla con Finly como lo harías con un asesor: registra movimientos, revisa
          tu balance y entiende en qué se va tu dinero.
        </p>

        <div className="auth-chat-preview">
          <div className="preview-bubble user">Gasté 32.000 en el mercado</div>
          <div className="preview-bubble agent">
            <span className="preview-orb" />
            <span>Listo, registré <b>Mercado</b> por <b>$32.000</b> en Alimentación.</span>
          </div>
        </div>

        <ul className="auth-points">
          {POINTS.map((point) => (
            <li key={point}><Icon name="check" />{point}</li>
          ))}
        </ul>
      </aside>

      <main className="auth-main">
        <Link className="auth-back" to="/"><Icon name="back" />Volver al chat</Link>

        <div className="auth-panel">
          <div className="auth-mobile-brand">
            <BrandMark />
            <span className="wordmark">Finly</span>
          </div>
          {children}
        </div>

        <p className="auth-legal">Tus datos se guardan de forma segura y privada.</p>
      </main>
    </div>
  )
}
