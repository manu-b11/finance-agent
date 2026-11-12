import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import { useConfirm } from '../hooks/useConfirm.jsx'
import { useConversationList } from '../hooks/useConversationList.js'
import { usePushNotifications } from '../hooks/usePushNotifications.js'
import { cancelReminder, createReminder, listReminders } from '../api/reminders.js'
import { errorMessage } from '../api/client.js'
import { formatDate } from '../lib/format.js'
import Icon from '../components/Icon.jsx'
import Sidebar from '../components/layout/Sidebar.jsx'
import Topbar from '../components/layout/Topbar.jsx'

const isDesktop = () => window.matchMedia('(min-width:1024px)').matches

const FIXED_FREQUENCY = {
  once: 'Una sola vez',
  daily: 'Todos los días',
  weekly: 'Cada semana',
  biweekly: 'Cada 15 días',
  monthly: 'Cada mes',
}
const UNIT_LABELS = { days: 'días', weeks: 'semanas', months: 'meses' }

const pad = (value) => String(value).padStart(2, '0')
const localDate = (date) =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`

// Propone la próxima hora en punto para que el recordatorio no nazca vencido.
function defaultWhen() {
  const next = new Date(Date.now() + 60 * 60 * 1000)
  return {
    date: localDate(next),
    time: `${pad(next.getHours())}:${pad(next.getMinutes())}`,
  }
}

function frequencyLabel(reminder) {
  if (reminder.frequency === 'custom') {
    return `Cada ${reminder.interval_count} ${UNIT_LABELS[reminder.interval_unit] ?? ''}`.trim()
  }
  return FIXED_FREQUENCY[reminder.frequency] ?? reminder.frequency
}

function ReminderForm({ busy, onSubmit, onCancel }) {
  const initial = defaultWhen()
  const [concept, setConcept] = useState('')
  const [date, setDate] = useState(initial.date)
  const [time, setTime] = useState(initial.time)
  const [frequency, setFrequency] = useState('once')

  const submit = (event) => {
    event.preventDefault()
    if (!concept.trim() || !date || !time) return
    onSubmit({
      concept: concept.trim(),
      remind_on: date,
      remind_at: time,
      frequency,
    })
  }

  return (
    <form className="form-stack" onSubmit={submit}>
      <label>
        <span>¿Qué quieres recordar?</span>
        <input
          type="text"
          required
          maxLength={255}
          placeholder="Ej. Pagar el arriendo"
          value={concept}
          onChange={(e) => setConcept(e.target.value)}
        />
      </label>
      <div className="form-row">
        <label>
          <span>Fecha</span>
          <input
            type="date"
            required
            min={localDate(new Date())}
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
        <label>
          <span>Hora</span>
          <input
            type="time"
            required
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
        </label>
      </div>
      <label>
        <span>Frecuencia</span>
        <select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
          {Object.entries(FIXED_FREQUENCY).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </label>
      <div className="form-note">
        Para recurrencias personalizadas, pídeselas a Finly en el chat.
      </div>
      <div className="form-actions">
        <button type="button" className="btn" onClick={onCancel} disabled={busy}>
          Cancelar
        </button>
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? 'Guardando…' : 'Crear recordatorio'}
        </button>
      </div>
    </form>
  )
}

export default function Reminders() {
  const { user, logout } = useAuth()
  const confirm = useConfirm()
  const navigate = useNavigate()
  const history = useConversationList(Boolean(user))
  const push = usePushNotifications()

  const [reminders, setReminders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [cancellingId, setCancellingId] = useState(null)
  const [creating, setCreating] = useState(false)
  const [busy, setBusy] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    listReminders()
      .then(setReminders)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  const openSidebar = () => (isDesktop() ? setCollapsed(false) : setDrawerOpen(true))
  const closeSidebar = () => (isDesktop() ? setCollapsed(true) : setDrawerOpen(false))

  async function handleCancel(reminder) {
    const ok = await confirm({
      title: 'Cancelar recordatorio',
      message: `Dejarás de recibir el aviso de "${reminder.concept}".`,
      confirmLabel: 'Cancelar recordatorio',
      danger: true,
    })
    if (!ok) return
    setError('')
    setCancellingId(reminder.id)
    try {
      await cancelReminder(reminder.id)
      setReminders((prev) => prev.filter((r) => r.id !== reminder.id))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setCancellingId(null)
    }
  }

  async function handleCreate(payload) {
    setError('')
    setInfo('')
    setBusy(true)
    try {
      const reminder = await createReminder(payload)
      setReminders((prev) =>
        [...prev, reminder].sort((a, b) =>
          String(a.next_run_at ?? '').localeCompare(String(b.next_run_at ?? '')),
        ),
      )
      setCreating(false)
      setInfo(`Recordatorio "${reminder.concept}" creado.`)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function run(action, message) {
    setError('')
    setInfo('')
    try {
      await action()
      if (message) setInfo(message)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  let pushText = 'Activa las notificaciones para recibir un aviso cuando crees un recordatorio y cuando llegue su hora.'
  if (!push.supported) pushText = 'Este navegador no admite notificaciones push.'
  else if (push.permission === 'denied') pushText = 'Bloqueaste las notificaciones. Permítelas desde la configuración del navegador.'
  else if (push.subscribed) pushText = 'Tus notificaciones están activas. Te avisaremos cuando crees un recordatorio y cuando llegue su hora.'

  return (
    <div className={`app${collapsed ? ' collapsed' : ''}`}>
      <Sidebar
        user={user}
        current="/recordatorios"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onCollapse={closeSidebar}
        history={history}
        onNewChat={() => navigate('/', { state: { newChat: true } })}
        onSelectChat={(item) => navigate('/', { state: { conversationId: item.id } })}
        onLogout={logout}
      />

      <main className="main">
        <Topbar onMenu={openSidebar} user={user} />

        <div className="content">
          <section className="page">
            <div className="page-head">
              <div>
                <h1>Recordatorios</h1>
                <p>Que no se te pase ningún pago: tus recordatorios, en un solo lugar.</p>
              </div>
              <button
                className="btn primary"
                onClick={() => setCreating((value) => !value)}
              >
                <Icon name={creating ? 'x' : 'plus'} />
                {creating ? 'Cerrar' : 'Crear recordatorio'}
              </button>
            </div>

            {error && <div className="page-error">{error}</div>}
            {info && <div className="page-info">{info}</div>}

            {creating && (
              <article className="card inv goal-form-card">
                <div className="card-head">
                  <b>Nuevo recordatorio</b>
                </div>
                <div className="card-body">
                  <ReminderForm
                    busy={busy}
                    onSubmit={handleCreate}
                    onCancel={() => setCreating(false)}
                  />
                </div>
              </article>
            )}

            <article className="card inv notify">
              <div className="card-head">
                <b>Notificaciones</b>
                <span className={`badge ${push.subscribed ? 'ok' : ''}`}>{push.subscribed ? 'Activas' : 'Desactivadas'}</span>
              </div>
              <div className="card-body"><span className="notify-text">{pushText}</span></div>
              {push.supported && push.permission !== 'denied' && (
                <div className="card-actions">
                  {push.subscribed ? (
                    <button className="btn" disabled={push.busy} onClick={() => run(push.disable)}>
                      Desactivar notificaciones
                    </button>
                  ) : (
                    <button className="btn primary" disabled={push.busy} onClick={() => run(push.enable)}>
                      {push.busy ? 'Activando…' : 'Activar notificaciones'}
                    </button>
                  )}
                </div>
              )}
            </article>

            {loading ? null : reminders.length === 0 ? (
              <div className="page-empty">No tienes recordatorios pendientes. Crea uno aquí o pídeselo a Finly en el chat.</div>
            ) : (
              <div className="inv-list">
                {reminders.map((r) => (
                  <article className="card inv rem-item" key={r.id}>
                    <div className="inv-main">
                      <b>{r.concept}</b>
                      <span>
                        {r.next_run_local ? `${formatDate(r.next_run_local)} · ${r.remind_at.slice(0, 5)}` : 'Sin próxima fecha'}
                        {' · '}{frequencyLabel(r)}
                      </span>
                    </div>
                    <button className="btn" disabled={cancellingId === r.id} onClick={() => handleCancel(r)}>
                      {cancellingId === r.id ? 'Cancelando…' : 'Cancelar'}
                    </button>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  )
}
