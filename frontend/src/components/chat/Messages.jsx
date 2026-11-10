import { useEffect, useRef } from 'react'
import QuickReplies from './QuickReplies.jsx'
import InvoiceDraftCard from '../invoice/InvoiceDraftCard.jsx'
import { BalanceCard } from '../dashboard/SummaryCards.jsx'

// Texto plano con **negrita** (nunca HTML del modelo, para evitar inyección).
function RichText({ text }) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4
      ? <b key={i}>{part.slice(2, -2)}</b>
      : part,
  )
}

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

function AgentCard({ card, busy, onSend }) {
  switch (card.type) {
    case 'invoice_draft':
      return <InvoiceDraftCard draft={card.data} busy={busy} onAction={onSend} />
    case 'balance':
      return <BalanceCard data={card.data} />
    default:
      return null
  }
}

function AgentMessage({ message, isLast, busy, onSend }) {
  const typing = message.status === 'typing'
  const showBubble = typing || message.text || message.error
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
        {message.cards.map((card, i) => (
          <AgentCard key={i} card={card} busy={busy} onSend={onSend} />
        ))}
        <QuickReplies items={message.quickReplies} onPick={onSend} disabled={busy || !isLast} />
      </div>
    </div>
  )
}

export default function Messages({ messages, busy, onSend }) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  return (
    <section className="chat" aria-live="polite">
      {messages.map((m, i) =>
        m.role === 'user' ? (
          <UserMessage key={m.id} message={m} />
        ) : (
          <AgentMessage
            key={m.id}
            message={m}
            isLast={i === messages.length - 1}
            busy={busy}
            onSend={onSend}
          />
        ),
      )}
      <div ref={endRef} />
    </section>
  )
}
