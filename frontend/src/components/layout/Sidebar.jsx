import { useEffect, useRef, useState } from 'react'
import Icon from '../Icon.jsx'
import { displayName, initial } from '../../lib/format.js'

const NAV = [
  { icon: 'dash', label: 'Dashboard' },
  { icon: 'receipt', label: 'Facturas' },
  { icon: 'report', label: 'Informes' },
  { icon: 'bell', label: 'Recordatorios' },
]

/*
  history: [{ label: 'Hoy', items: [{ id, title }] }]
  Sin usuario (invitado) se muestra un aviso para iniciar sesión.
*/
export default function Sidebar({
  user,
  history = [],
  activeId,
  open,
  onClose,
  onCollapse,
  onNewChat,
  onSelectChat,
  onLogout,
  onAuth,
}) {
  const [searchOpen, setSearchOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [userMenu, setUserMenu] = useState(false)
  const searchRef = useRef(null)
  const userRef = useRef(null)

  useEffect(() => {
    if (!user) return
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSearchOpen(true)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [user])

  useEffect(() => {
    if (searchOpen) searchRef.current?.focus()
  }, [searchOpen])

  useEffect(() => {
    if (!userMenu) return
    const onDown = (e) => {
      if (!userRef.current?.contains(e.target)) setUserMenu(false)
    }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [userMenu])

  const q = query.trim().toLowerCase()
  const groups = history
    .map((g) => ({ ...g, items: g.items.filter((i) => !q || i.title.toLowerCase().includes(q)) }))
    .filter((g) => g.items.length > 0)

  return (
    <>
      <aside className={`sidebar${open ? ' open' : ''}`} aria-label="Navegación">
        <div className="brand">
          <div className="brand-left">
            <div className="brand-mark"><Icon name="logo" /></div>
            <span className="wordmark">Finly</span>
          </div>
          <div className="brand-actions">
            {user && (
              <button className="side-icon" onClick={() => setSearchOpen(true)} aria-label="Buscar chats">
                <Icon name="search" />
              </button>
            )}
            <button className="side-icon" onClick={onCollapse} aria-label="Cerrar barra lateral">
              <Icon name="panel" />
            </button>
          </div>
        </div>

        {user && (
          <label className={`search${searchOpen ? ' open' : ''}`}>
            <Icon name="search" />
            <input
              ref={searchRef}
              type="search"
              placeholder="Buscar chats"
              aria-label="Buscar chats"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <span className="kbd">⌘</span>
          </label>
        )}

        <nav className="nav">
          <button className="nav-item active" onClick={onNewChat}>
            <Icon name="compose" />Nuevo chat
          </button>
          {NAV.map((item) => (
            <button key={item.label} className="nav-item" disabled title="Próximamente">
              <Icon name={item.icon} />{item.label}
            </button>
          ))}
        </nav>

        {!user && (
          <button className="guest-hint" onClick={() => onAuth?.('login')}>
            <Icon name="info" />
            <span><span className="guest-hint-link">Inicia sesión</span> para que Finly recuerde tus finanzas</span>
          </button>
        )}

        {user && (
          <div className="history">
            {groups.map((g) => (
              <section key={g.label}>
                <h4>{g.label}</h4>
                {g.items.map((item) => (
                  <button
                    key={item.id}
                    className={activeId === item.id ? 'active' : undefined}
                    aria-current={activeId === item.id ? 'page' : undefined}
                    onClick={() => onSelectChat?.(item)}
                  >
                    {item.title}
                  </button>
                ))}
              </section>
            ))}
          </div>
        )}

        {user ? (
          <div className="user-wrap" ref={userRef}>
            {userMenu && (
              <div className="user-pop">
                <button onClick={onLogout}><Icon name="out" />Cerrar sesión</button>
              </div>
            )}
            <button className="user" aria-label="Menú de usuario" onClick={() => setUserMenu((v) => !v)}>
              <div className="avatar">{initial(user)}</div>
              <div className="user-info">
                <b>{displayName(user)}</b>
                <span>{user?.plan ?? 'Free'}</span>
              </div>
            </button>
          </div>
        ) : (
          <div className="guest-user">
            <button className="btn" onClick={() => onAuth?.('login')}>Iniciar sesión</button>
            <button className="btn primary" onClick={() => onAuth?.('register')}>Crear cuenta</button>
          </div>
        )}
      </aside>
      <div className="overlay" onClick={onClose} />
    </>
  )
}
