import { useState } from 'react'
import { errorMessage } from '../../api/client.js'
import { usePushNotifications } from '../../hooks/usePushNotifications.js'
import Icon from '../Icon.jsx'

/*
  Tarjeta en vivo que aparece después de crear un recordatorio si el usuario
  todavía no activó las notificaciones. No se persiste: al recargar desaparece.
*/
export default function NotificationsCard({ data }) {
  const push = usePushNotifications()
  const [enabling, setEnabling] = useState(false)
  const [error, setError] = useState('')

  if (!push.ready || !push.supported || push.permission === 'denied' || push.subscribed) {
    return null
  }

  const enable = async () => {
    setError('')
    setEnabling(true)
    try {
      await push.enable()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setEnabling(false)
    }
  }

  const subject = data?.concept ? `"${data.concept}"` : 'tus recordatorios'

  return (
    <div className="card statement-card">
      <div className="card-head">
        <b>Activa las notificaciones</b>
        <span className="badge">Recomendado</span>
      </div>
      <div className="card-body">
        <div className="row">
          <span>
            Te avisaremos en este dispositivo cuando llegue la hora de {subject} y cuando
            crees uno nuevo.
          </span>
        </div>
        {error && <div className="error-text">{error}</div>}
      </div>
      <div className="card-actions">
        <button
          type="button"
          className="btn primary"
          onClick={enable}
          disabled={enabling || push.busy}
        >
          <Icon name="bell" size={14} />
          {enabling || push.busy ? 'Activando…' : 'Activar notificaciones'}
        </button>
      </div>
    </div>
  )
}
