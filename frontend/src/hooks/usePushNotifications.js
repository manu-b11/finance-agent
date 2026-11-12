import { useCallback, useEffect, useState } from 'react'
import { getPushPublicKey, subscribePush, unsubscribePush } from '../api/push.js'

const supported =
  typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

function urlBase64ToUint8Array(base64) {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4)
  const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(raw, (char) => char.charCodeAt(0))
}

export function usePushNotifications() {
  const [permission, setPermission] = useState(supported ? Notification.permission : 'unsupported')
  const [subscribed, setSubscribed] = useState(false)
  const [ready, setReady] = useState(!supported)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!supported) return
    navigator.serviceWorker
      .register('/sw.js')
      .then((registration) => registration.pushManager.getSubscription())
      .then((subscription) => setSubscribed(Boolean(subscription)))
      .catch(() => {})
      .finally(() => setReady(true))
  }, [])

  const enable = useCallback(async () => {
    setBusy(true)
    try {
      const result = await Notification.requestPermission()
      setPermission(result)
      if (result !== 'granted') return
      const registration = await navigator.serviceWorker.register('/sw.js')
      await navigator.serviceWorker.ready
      const { public_key: publicKey } = await getPushPublicKey()
      const subscription =
        (await registration.pushManager.getSubscription()) ??
        (await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey),
        }))
      await subscribePush(subscription.toJSON())
      setSubscribed(true)
      await registration.showNotification('Notificaciones activadas', {
        body: 'Te avisaremos cuando crees un recordatorio y cuando llegue su hora.',
        tag: 'push-enabled',
      })
    } finally {
      setBusy(false)
    }
  }, [])

  const disable = useCallback(async () => {
    setBusy(true)
    try {
      const registration = await navigator.serviceWorker.register('/sw.js')
      const subscription = await registration.pushManager.getSubscription()
      if (subscription) {
        await unsubscribePush(subscription.endpoint)
        await subscription.unsubscribe()
      }
      setSubscribed(false)
    } finally {
      setBusy(false)
    }
  }, [])

  return { supported, permission, subscribed, ready, busy, enable, disable }
}
