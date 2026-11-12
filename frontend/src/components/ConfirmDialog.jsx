import { useEffect } from 'react'
import Icon from './Icon.jsx'

/*
  Modal de confirmación propio de Finly. Sustituye al window.confirm del
  navegador, que muestra el dominio en el título, no se puede estilizar y en
  algunos navegadores (PWA, iframes) se bloquea.
*/
export default function ConfirmDialog({
  open,
  title = '¿Confirmas?',
  message,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  danger = false,
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') onCancel?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  if (!open) return null

  return (
    <div className="confirm-modal" role="dialog" aria-modal="true" aria-label={title}>
      <div className="confirm-backdrop" onClick={onCancel} />
      <div className="confirm-card">
        <div className="confirm-icon">
          <Icon name={danger ? 'info' : 'check'} />
        </div>
        <h3 className="confirm-title">{title}</h3>
        {message && <p className="confirm-message">{message}</p>}
        <div className="confirm-actions">
          <button type="button" className="btn" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`btn ${danger ? 'danger-solid' : 'primary'}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
