// items: [{ label, text }]  → al pulsar se envía `text` como mensaje del usuario
export default function QuickReplies({ items = [], onPick, disabled }) {
  if (items.length === 0) return null
  return (
    <div className="quick">
      {items.map((it) => (
        <button key={it.label} className="chip" disabled={disabled} onClick={() => onPick(it.text ?? it.label)}>
          {it.label}
        </button>
      ))}
    </div>
  )
}
