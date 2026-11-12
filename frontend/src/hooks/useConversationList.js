import { useEffect, useState } from 'react'
import { getConversations } from '../api/chat.js'

export function useConversationList(enabled = true) {
  const [conversations, setConversations] = useState([])

  useEffect(() => {
    if (!enabled) return undefined
    let alive = true
    getConversations()
      .then((items) => alive && setConversations(items))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [enabled])

  return conversations.length
    ? [{ label: 'Conversaciones', items: conversations.map((c) => ({ id: c.id, title: c.title })) }]
    : []
}
