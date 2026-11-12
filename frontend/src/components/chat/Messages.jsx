import { useEffect, useRef, useState } from 'react'
import InvoiceDraftCard from '../invoice/InvoiceDraftCard.jsx'
import NotificationsCard from './NotificationsCard.jsx'
import SignupCard from './SignupCard.jsx'
import RichText from './RichText.jsx'
import Icon from '../Icon.jsx'

function Typing({ label }) {
  return (
    <div className="typing-wrap" aria-label="Escribiendo">
      <div className="typing"><i /><i /><i /></div>
      {label && <span className="typing-label">{label}</span>}
    </div>
  )
}

function UserMessage({ message }) {
  return (
    <div className="msg user">
      <div className="bubble">
        {message.fileName && <>📎 {message.fileName}{message.text ? '\n' : ''}</>}
        {message.text}
      </div>
    </div>
  )
}

function AgentCard({ card, busy, onSend, onSignup }) {
  switch (card.type) {
    case 'invoice':
    case 'invoice_draft':
      return <InvoiceDraftCard draft={card.data} busy={busy} onAction={onSend} />
    case 'notifications':
      return <NotificationsCard data={card.data} />
    case 'signup':
      return <SignupCard data={card.data} onSignup={onSignup} />
    default:
      return null
  }
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return undefined
    const timer = setTimeout(() => setCopied(false), 1800)
    return () => clearTimeout(timer)
  }, [copied])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Contextos sin permiso de portapapeles (HTTP, navegadores antiguos).
      const area = document.createElement('textarea')
      area.value = text
      area.style.position = 'fixed'
      area.style.opacity = '0'
      document.body.appendChild(area)
      area.select()
      document.execCommand('copy')
      area.remove()
    }
    setCopied(true)
  }

  return (
    <button
      type="button"
      className="msg-action"
      onClick={copy}
      title={copied ? 'Copiado' : 'Copiar respuesta'}
      aria-label={copied ? 'Copiado' : 'Copiar respuesta'}
    >
      <Icon name={copied ? 'check' : 'copy'} size={20} />
    </button>
  )
}

function AgentMessage({ message, busy, onSend, onSignup, onRetry }) {
  const typing = message.status === 'typing'
  const showBubble = typing || message.text || message.error
  const copyText = message.text || message.error || ''
  const showActions = !typing && Boolean(copyText)
  return (
    <div className="msg agent">
      <div className="mini-orb" />
      <div className="agent-body">
        {showBubble && (
          <div className="bubble">
            {typing ? <Typing label={message.toolLabel} /> : <RichText text={message.text} />}
            {message.error && <div className="error-text">{message.error}</div>}
          </div>
        )}
        {showActions && (
          <div className="msg-actions">
            <CopyButton text={copyText} />
            <button
              type="button"
              className="msg-action"
              onClick={() => onRetry?.(message)}
              disabled={busy}
              title="Reintentar"
              aria-label="Reintentar"
            >
              <Icon name="refresh" size={20} />
            </button>
          </div>
        )}
        {message.status === 'error' && message.sideEffects && (
          <span className="retry-note">
            La operación anterior pudo haberse guardado. Revísala antes de reintentar.
          </span>
        )}
        {message.cards.map((card, i) => (
          <AgentCard key={i} card={card} busy={busy} onSend={onSend} onSignup={onSignup} />
        ))}
      </div>
    </div>
  )
}

export default function Messages({ messages, busy, onSend, onSignup, onRetry }) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  return (
    <section className="chat" aria-live="polite">
      {messages.map((m) =>
        m.role === 'user' ? (
          <UserMessage key={m.id} message={m} />
        ) : (
          <AgentMessage
            key={m.id}
            message={m}
            busy={busy}
            onSend={onSend}
            onSignup={onSignup}
            onRetry={onRetry}
          />
        ),
      )}
      <div ref={endRef} />
    </section>
  )
}
