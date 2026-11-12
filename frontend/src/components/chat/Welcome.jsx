import { useEffect, useState } from 'react'
import Icon from '../Icon.jsx'

const SUGGESTIONS = [
  { icon: 'info', title: '¿Qué puedes hacer?', desc: 'Descubre todo lo que Finly puede hacer por ti.', capabilities: true },
  { icon: 'expense', title: 'Registrar gasto', desc: 'Cuéntame qué compraste y cuánto costó.', fill: 'Registré un gasto de ' },
  { icon: 'balance', title: 'Balance del mes', desc: 'Ingresos, gastos y lo que te queda este mes.', send: '¿Cuál es mi balance de este mes?' },
  { icon: 'upload', title: 'Subir factura', desc: 'Envía un PDF o foto y confirma antes de guardar.', upload: true },
]

// Sin cuenta se priorizan las preguntas: solo pedimos registro al guardar algo.
const GUEST_SUGGESTIONS = [
  { icon: 'info', title: '¿Qué puedes hacer?', desc: 'Descubre todo lo que Finly puede hacer por ti.', capabilities: true },
  { icon: 'balance', title: '¿Cómo armo un presupuesto?', desc: 'Te explico cómo repartir tus ingresos por categorías.', send: '¿Cómo armo un presupuesto?' },
  { icon: 'goal', title: '¿Cómo empiezo a ahorrar?', desc: 'Ideas para apartar dinero sin que duela.', send: '¿Cómo empiezo a ahorrar?' },
  { icon: 'expense', title: 'Registrar gasto', desc: 'Cuéntame qué compraste y cuánto costó.', fill: 'Registré un gasto de ' },
]

// La primera vez que se abre el chat solo se muestra la sugerencia de bienvenida.
const WELCOME_KEY = 'finly:welcomed'

function greetingFor(name, date = new Date()) {
  const h = date.getHours()
  const [a, b] =
    h < 12
      ? ['Buenos días', '¿Empezamos revisando tu presupuesto?']
      : h < 19
        ? ['Buenas tardes', '¿Registramos algún gasto de hoy?']
        : ['Buenas noches', '¿Cerramos el día con tus movimientos?']
  return [name ? `${a}, ${name}.` : `${a}.`, b]
}

// children = el <Composer/>, que Home coloca aquí mientras no hay conversación.
export default function Welcome({ name, guest, onFill, onSend, onUpload, onCapabilities, children }) {
  const [line1, line2] = greetingFor(name)
  const subtitle = guest ? '¿Qué quieres entender hoy de tus finanzas?' : line2

  const [showAll, setShowAll] = useState(() => {
    try {
      return Boolean(localStorage.getItem(WELCOME_KEY))
    } catch {
      return true
    }
  })

  // A partir de la segunda visita se mantienen las cuatro sugerencias.
  useEffect(() => {
    if (showAll) return
    try {
      localStorage.setItem(WELCOME_KEY, '1')
    } catch {
      /* sin almacenamiento: la próxima visita vuelve a mostrar solo la de bienvenida */
    }
  }, [showAll])

  const suggestions = guest ? GUEST_SUGGESTIONS : SUGGESTIONS
  const items = showAll ? suggestions : suggestions.slice(0, 1)

  const pick = (s) => {
    if (s.capabilities) onCapabilities?.()
    else if (s.fill) onFill(s.fill)
    else if (s.send) onSend(s.send)
    else if (s.upload) onUpload()
  }

  return (
    <section className="welcome">
      <div className="orb-wrap" aria-hidden="true"><div className="orb" /></div>

      <h1 className="greeting">{line1}<br />{subtitle}</h1>

      <div className="composer-slot">{children}</div>

      <div className="suggestions">
        {items.map((s) => (
          <button key={s.title} className="sug" onClick={() => pick(s)}>
            <span className="sug-icon"><Icon name={s.icon} /></span>
            <span>
              <span className="sug-title">{s.title}</span>
              <span className="sug-desc">{s.desc}</span>
            </span>
          </button>
        ))}
      </div>
    </section>
  )
}
