import { useEffect, useRef } from 'react'
import InvoiceDraftCard from '../invoice/InvoiceDraftCard.jsx'
import { BalanceCard } from '../dashboard/SummaryCards.jsx'
import TransactionCard from './TransactionCard.jsx'
import ReportCard from './ReportCard.jsx'
import RichText from './RichText.jsx'

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
    case 'transaction':
      return <TransactionCard action={card.data.action} transaction={card.data.transaction} />
    case 'report':
      return <ReportCard report={card.data} />
    default:
      return null
  }
}

function AgentMessage({ message, busy, onSend }) {
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
      {messages.map((m) =>
        m.role === 'user' ? (
          <UserMessage key={m.id} message={m} />
        ) : (
          <AgentMessage
            key={m.id}
            message={m}
            busy={busy}
            onSend={onSend}
          />
        ),
      )}
      <div ref={endRef} />
    </section>
  )
}
