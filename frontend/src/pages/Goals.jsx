import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import { useConfirm } from '../hooks/useConfirm.jsx'
import { useConversationList } from '../hooks/useConversationList.js'
import {
  addContribution,
  createGoal,
  deleteGoal,
  listGoals,
  updateGoal,
} from '../api/goals.js'
import { errorMessage } from '../api/client.js'
import { formatCOP, formatDate } from '../lib/format.js'
import Icon from '../components/Icon.jsx'
import Sidebar from '../components/layout/Sidebar.jsx'
import Topbar from '../components/layout/Topbar.jsx'

const isDesktop = () => window.matchMedia('(min-width:1024px)').matches

// Los Decimal del backend llegan como string ("1500000.00").
const toNumber = (value) => {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

const percentageOf = (goal) => Math.max(0, Math.min(100, toNumber(goal.percentage)))

function deadlineText(goal) {
  if (!goal.deadline) return 'Sin fecha límite'
  const base = formatDate(goal.deadline)
  const days = goal.days_remaining
  if (days == null) return base
  if (days < 0) return `${base} · venció hace ${Math.abs(days)} días`
  if (days === 0) return `${base} · vence hoy`
  return `${base} · ${days} días restantes`
}

function GoalForm({ initial, submitLabel, busy, onSubmit, onCancel }) {
  const [name, setName] = useState(initial?.name ?? '')
  const [target, setTarget] = useState(
    initial?.target_amount == null ? '' : String(toNumber(initial.target_amount)),
  )
  const [deadline, setDeadline] = useState(initial?.deadline ?? '')

  const submit = (event) => {
    event.preventDefault()
    const amount = Number(target)
    if (!name.trim() || !Number.isFinite(amount) || amount <= 0) return
    onSubmit({
      name: name.trim(),
      target_amount: amount,
      deadline: deadline || null,
    })
  }

  return (
    <form className="form-stack" onSubmit={submit}>
      <label>
        <span>Nombre de la meta</span>
        <input
          type="text"
          required
          maxLength={120}
          placeholder="Ej. Viaje a Cartagena"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <div className="form-row">
        <label>
          <span>Monto objetivo</span>
          <input
            type="number"
            required
            min="1"
            step="100"
            placeholder="1500000"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
        </label>
        <label>
          <span>Fecha límite (opcional)</span>
          <input
            type="date"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
          />
        </label>
      </div>
      <div className="form-actions">
        <button type="button" className="btn" onClick={onCancel} disabled={busy}>
          Cancelar
        </button>
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? 'Guardando…' : submitLabel}
        </button>
      </div>
    </form>
  )
}

export default function Goals() {
  const { user, logout } = useAuth()
  const confirm = useConfirm()
  const navigate = useNavigate()
  const history = useConversationList(Boolean(user))

  const [goals, setGoals] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [openId, setOpenId] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [amounts, setAmounts] = useState({})
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    listGoals()
      .then(setGoals)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  const totals = useMemo(() => {
    const saved = goals.reduce((sum, goal) => sum + toNumber(goal.accumulated), 0)
    const target = goals.reduce((sum, goal) => sum + toNumber(goal.target_amount), 0)
    return { saved, target, percentage: target > 0 ? Math.min(100, (saved / target) * 100) : 0 }
  }, [goals])

  const openSidebar = () => (isDesktop() ? setCollapsed(false) : setDrawerOpen(true))
  const closeSidebar = () => (isDesktop() ? setCollapsed(true) : setDrawerOpen(false))

  const replaceGoal = (updated) =>
    setGoals((prev) => prev.map((goal) => (goal.id === updated.id ? updated : goal)))

  async function handleCreate(payload) {
    setBusy(true)
    setError('')
    try {
      const goal = await createGoal(payload)
      setGoals((prev) => [goal, ...prev])
      setCreating(false)
      setOpenId(goal.id)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleUpdate(goal, payload) {
    setBusy(true)
    setError('')
    try {
      replaceGoal(await updateGoal(goal.id, payload))
      setEditingId(null)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(goal) {
    const ok = await confirm({
      title: 'Eliminar meta',
      message: `Se eliminará la meta "${goal.name}" y sus aportes. Esta acción no se puede deshacer.`,
      confirmLabel: 'Eliminar',
      danger: true,
    })
    if (!ok) return
    setBusy(true)
    setError('')
    try {
      await deleteGoal(goal.id)
      setGoals((prev) => prev.filter((item) => item.id !== goal.id))
      if (openId === goal.id) setOpenId(null)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleContribution(event, goal) {
    event.preventDefault()
    const amount = Number(amounts[goal.id])
    if (!Number.isFinite(amount) || amount <= 0) return
    setBusy(true)
    setError('')
    try {
      replaceGoal(await addContribution(goal.id, { amount }))
      setAmounts((prev) => ({ ...prev, [goal.id]: '' }))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`app${collapsed ? ' collapsed' : ''}`}>
      <Sidebar
        user={user}
        current="/metas"
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
                <h1>Metas de ahorro</h1>
                <p>Define un objetivo, registra tus aportes y mira cuánto te falta.</p>
              </div>
              <button
                className="btn primary"
                onClick={() => {
                  setCreating((value) => !value)
                  setEditingId(null)
                }}
              >
                <Icon name={creating ? 'x' : 'plus'} />
                {creating ? 'Cerrar' : 'Nueva meta'}
              </button>
            </div>

            {error && <div className="page-error">{error}</div>}

            {creating && (
              <article className="card inv goal-form-card">
                <div className="card-head">
                  <b>Nueva meta</b>
                </div>
                <div className="card-body">
                  <GoalForm
                    submitLabel="Crear meta"
                    busy={busy}
                    onSubmit={handleCreate}
                    onCancel={() => setCreating(false)}
                  />
                </div>
              </article>
            )}

            {loading ? null : goals.length === 0 ? (
              <div className="page-empty">
                Aún no tienes metas de ahorro. Crea una para empezar a separar dinero.
              </div>
            ) : (
              <>
                <article className="card inv goal-summary">
                  <div className="card-body">
                    <div className="goal-summary-line">
                      <div>
                        <span>Total ahorrado</span>
                        <b>{formatCOP(totals.saved)}</b>
                      </div>
                      <div>
                        <span>Objetivo total</span>
                        <b>{formatCOP(totals.target)}</b>
                      </div>
                      <span className="badge">{Math.round(totals.percentage)}%</span>
                    </div>
                    <div className="goal-bar">
                      <i style={{ width: `${totals.percentage}%` }} />
                    </div>
                  </div>
                </article>

                <div className="inv-list">
                  {goals.map((goal) => {
                    const open = openId === goal.id
                    const pct = percentageOf(goal)
                    const editing = editingId === goal.id
                    return (
                      <article className="card inv goal" key={goal.id}>
                        <button
                          className="inv-head"
                          onClick={() => setOpenId(open ? null : goal.id)}
                          aria-expanded={open}
                        >
                          <div className="inv-main">
                            <b>{goal.name}</b>
                            <span>
                              {formatCOP(goal.accumulated)} de {formatCOP(goal.target_amount)}
                              {goal.deadline ? ` · ${formatDate(goal.deadline)}` : ''}
                            </span>
                          </div>
                          <div className="inv-side">
                            <span className="inv-total">{Math.round(pct)}%</span>
                            <span className={`badge ${goal.completed ? 'ok' : 'warn'}`}>
                              {goal.completed ? 'Completada' : 'En curso'}
                            </span>
                          </div>
                        </button>
                        <div className="goal-bar">
                          <i
                            className={goal.completed ? 'done' : undefined}
                            style={{ width: `${pct}%` }}
                          />
                        </div>

                        {open && (
                          <div className="card-body goal-body">
                            {editing ? (
                              <GoalForm
                                key={goal.id}
                                initial={goal}
                                submitLabel="Guardar cambios"
                                busy={busy}
                                onSubmit={(payload) => handleUpdate(goal, payload)}
                                onCancel={() => setEditingId(null)}
                              />
                            ) : (
                              <>
                                <div className="row">
                                  <span>Ahorrado</span>
                                  <span className="income">{formatCOP(goal.accumulated)}</span>
                                </div>
                                <div className="row">
                                  <span>Falta</span>
                                  <span>{formatCOP(goal.remaining)}</span>
                                </div>
                                <div className="row">
                                  <span>Fecha límite</span>
                                  <span>{deadlineText(goal)}</span>
                                </div>
                                {goal.suggested_monthly_contribution != null && !goal.completed && (
                                  <div className="row">
                                    <span>Aporte mensual sugerido</span>
                                    <span>
                                      {formatCOP(goal.suggested_monthly_contribution)}
                                    </span>
                                  </div>
                                )}

                                {!goal.completed && (
                                  <form
                                    className="goal-contribute"
                                    onSubmit={(event) => handleContribution(event, goal)}
                                  >
                                    <input
                                      type="number"
                                      min="1"
                                      step="100"
                                      placeholder="Monto del aporte"
                                      aria-label={`Aporte para ${goal.name}`}
                                      value={amounts[goal.id] ?? ''}
                                      onChange={(e) =>
                                        setAmounts((prev) => ({
                                          ...prev,
                                          [goal.id]: e.target.value,
                                        }))
                                      }
                                    />
                                    <button type="submit" className="btn primary" disabled={busy}>
                                      <Icon name="plus" />Aportar
                                    </button>
                                  </form>
                                )}

                                <div className="goal-actions">
                                  <button
                                    className="btn"
                                    onClick={() => setEditingId(goal.id)}
                                    disabled={busy}
                                  >
                                    <Icon name="compose" />Editar
                                  </button>
                                  <button
                                    className="btn danger"
                                    onClick={() => handleDelete(goal)}
                                    disabled={busy}
                                  >
                                    <Icon name="x" />Eliminar
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        )}
                      </article>
                    )
                  })}
                </div>
              </>
            )}
          </section>
        </div>
      </main>
    </div>
  )
}
