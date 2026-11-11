import Icon from '../Icon.jsx'

export default function Topbar({ onMenu, user, onAuth }) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="icon-btn menu-btn" onClick={onMenu} aria-label="Abrir menú">
          <Icon name="menu" />
        </button>
      </div>

      {user ? (
        <button className="icon-btn" aria-label="Más opciones">
          <Icon name="dots" />
        </button>
      ) : (
        <div className="topbar-auth">
          <button className="btn ghost" onClick={() => onAuth?.('login')}>Iniciar sesión</button>
          <button className="btn primary" onClick={() => onAuth?.('register')}>Crear cuenta</button>
        </div>
      )}
    </header>
  )
}
