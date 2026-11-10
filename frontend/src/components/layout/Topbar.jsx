import Icon from '../Icon.jsx'

export default function Topbar({ onMenu }) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="icon-btn menu-btn" onClick={onMenu} aria-label="Abrir menú">
          <Icon name="menu" />
        </button>
      </div>
      <button className="icon-btn" aria-label="Más opciones">
        <Icon name="dots" />
      </button>
    </header>
  )
}
