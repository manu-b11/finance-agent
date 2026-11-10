import Icon from '../Icon.jsx'

const SUGGESTIONS = [
  { icon: 'expense', title: 'Registrar gasto', desc: 'Cuéntame qué compraste y cuánto costó.', fill: 'Registré un gasto de ' },
  { icon: 'balance', title: 'Balance del mes', desc: 'Ingresos, gastos y lo que te queda este mes.', send: '¿Cuál es mi balance de este mes?' },
  { icon: 'upload', title: 'Subir factura', desc: 'Envía un PDF o foto y confirma antes de guardar.', upload: true },
]

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
export default function Welcome({ name, onFill, onSend, onUpload, children }) {
  const [line1, line2] = greetingFor(name)

  const pick = (s) => {
    if (s.fill) onFill(s.fill)
    else if (s.send) onSend(s.send)
    else if (s.upload) onUpload()
  }

  return (
    <section className="welcome">
      <div className="orb-wrap" aria-hidden="true"><div className="orb" /></div>

      <h1 className="greeting">{line1}<br />{line2}</h1>

      <div className="composer-slot">{children}</div>

      <div className="suggestions">
        {SUGGESTIONS.map((s) => (
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
