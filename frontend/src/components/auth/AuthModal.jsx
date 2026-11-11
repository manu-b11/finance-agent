import { useEffect } from 'react'
import AuthForm from './AuthForm.jsx'
import Icon from '../Icon.jsx'

// Modal de acceso que se abre desde el chat cuando un invitado intenta escribir.
export default function AuthModal({ mode = 'login', onSwitch, onClose, onSuccess }) {
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="auth-modal" role="dialog" aria-modal="true" aria-label="Acceso a Finly">
      <div className="auth-modal-backdrop" onClick={onClose} />

      <div className="auth-modal-card">
        <button className="auth-modal-close" onClick={onClose} aria-label="Cerrar">
          <Icon name="x" />
        </button>

        <div className="auth-modal-brand">
          <span className="brand-mark"><Icon name="logo" /></span>
          <span className="wordmark">Finly</span>
        </div>

        <AuthForm key={mode} mode={mode} onSwitch={onSwitch} onSuccess={onSuccess} />

        <p className="auth-modal-note">
          Finly recuerda tus conversaciones y tus movimientos cuando tienes cuenta.
        </p>
      </div>
    </div>
  )
}
