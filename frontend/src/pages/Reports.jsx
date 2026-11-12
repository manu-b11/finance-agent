import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import { useConversationList } from '../hooks/useConversationList.js'
import { downloadMonthlyReport, getMonthlyReport } from '../api/reports.js'
import { errorMessage } from '../api/client.js'
import { categoryLabel, formatCOP, formatDate, formatMonth } from '../lib/format.js'
import Icon from '../components/Icon.jsx'
import Sidebar from '../components/layout/Sidebar.jsx'
import Topbar from '../components/layout/Topbar.jsx'

const isDesktop = () => window.matchMedia('(min-width:1024px)').matches

const MONTH_NAMES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]
const NOW = new Date()
const THIS_YEAR = NOW.getFullYear()
const THIS_MONTH = NOW.getMonth() + 1
const YEARS = Array.from({ length: 6 }, (_, i) => THIS_YEAR - i)

export default function Reports() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const history = useConversationList(Boolean(user))

  const [year, setYear] = useState(THIS_YEAR)
  const [monthNumber, setMonthNumber] = useState(THIS_MONTH)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  const month = `${year}-${String(monthNumber).padStart(2, '0')}`
  const maxMonth = year === THIS_YEAR ? THIS_MONTH : 12

  const changeYear = (value) => {
    const next = Number(value)
    setYear(next)
    if (next === THIS_YEAR && monthNumber > THIS_MONTH) setMonthNumber(THIS_MONTH)
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    getMonthlyReport(month)
      .then((data) => active && setReport(data))
      .catch((err) => {
        if (!active) return
        setReport(null)
        setError(errorMessage(err))
      })
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [month])

  const openSidebar = () => (isDesktop() ? setCollapsed(false) : setDrawerOpen(true))
  const closeSidebar = () => (isDesktop() ? setCollapsed(true) : setDrawerOpen(false))

  async function download() {
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

  const empty = report && report.transaction_count === 0

  return (
    <div className={`app${collapsed ? ' collapsed' : ''}`}>
      <Sidebar
        user={user}
        current="/informes"
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
                <h1>Informes</h1>
                <p>Resumen mensual de tus ingresos, gastos y balance.</p>
              </div>
              <div className="page-tools">
                <select
                  className="month-input"
                  value={monthNumber}
                  onChange={(e) => setMonthNumber(Number(e.target.value))}
                  aria-label="Mes del informe"
                >
                  {MONTH_NAMES.slice(0, maxMonth).map((name, i) => (
                    <option key={name} value={i + 1}>{name}</option>
                  ))}
                </select>
                <select
                  className="month-input"
                  value={year}
                  onChange={(e) => changeYear(e.target.value)}
                  aria-label="Año del informe"
                >
                  {YEARS.map((y) => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
                <button className="btn primary" disabled={downloading || loading || !report || empty} onClick={download}>
                  <Icon name="upload" />{downloading ? 'Generando PDF…' : 'Descargar PDF'}
                </button>
              </div>
            </div>

            {error && <div className="page-error">{error}</div>}

            {loading || !report ? null : empty ? (
              <div className="page-empty">No hay movimientos registrados en {formatMonth(month)}.</div>
            ) : (
              <div className="inv-list">
                <article className="card inv">
                  <div className="inv-head static">
                    <div className="inv-main">
                      <b className="cap">{formatMonth(report.month)}</b>
                      <span>
                        {report.transaction_count} {report.transaction_count === 1 ? 'movimiento' : 'movimientos'}
                        {report.top_category ? ` · Mayor gasto en ${categoryLabel(report.top_category).toLowerCase()}` : ''}
                      </span>
                    </div>
                    <div className="inv-side">
                      <span className="inv-total">{formatCOP(report.balance)}</span>
                      <span className={`badge ${Number(report.balance) >= 0 ? 'ok' : 'warn'}`}>
                        {Number(report.balance) >= 0 ? 'Positivo' : 'Negativo'}
                      </span>
                    </div>
                  </div>

                  <div className="card-body">
                    <div className="row"><span>Ingresos</span><span className="income">{formatCOP(report.total_income)}</span></div>
                    <div className="row"><span>Gastos</span><span className="expense">{formatCOP(report.total_expenses)}</span></div>
                    {report.categories.length > 0 && (
                      <div className="items">
                        {report.categories.map((c) => (
                          <div className="row" key={c.category}>
                            <span>{categoryLabel(c.category) || c.label}</span>
                            <span>{formatCOP(c.total)} · {Math.round(Number(c.percentage))}%</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {report.expenses?.length > 0 && (
                      <div className="report-expenses">
                        <div className="report-subhead">
                          <span>Gastos del mes</span>
                          <span className="expense">{formatCOP(report.total_expenses)}</span>
                        </div>
                        <div className="items tx-items">
                          {report.expenses.map((tx) => (
                            <div className="row tx-row" key={tx.id}>
                              <span className="tx-concept">
                                {tx.concept}
                                <small>
                                  {formatDate(tx.occurred_on)}
                                  {tx.category ? ` · ${categoryLabel(tx.category)}` : ''}
                                </small>
                              </span>
                              <span className="expense">− {formatCOP(tx.amount)}</span>
                            </div>
                          ))}
                        </div>
                        {report.expense_count > report.expenses.length && (
                          <div className="card-note">
                            Mostrando los últimos {report.expenses.length} de{' '}
                            {report.expense_count} gastos.
                          </div>
                        )}
                      </div>
                    )}
                    <div className="row total">
                      <span style={{ color: 'var(--text)' }}>Balance</span>
                      <span>{formatCOP(report.balance)}</span>
                    </div>
                  </div>
                </article>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  )
}
