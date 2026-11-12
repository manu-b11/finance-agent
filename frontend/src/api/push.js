import { request } from './client.js'

export const getPushPublicKey = () => request('/push/public-key')

export const subscribePush = (subscription) => request('/push/subscriptions', { method: 'POST', body: subscription })

export const unsubscribePush = (endpoint) => request('/push/subscriptions', { method: 'DELETE', body: { endpoint } })
