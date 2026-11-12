import { request } from './client.js'

export const listReminders = () => request('/reminders')

export const createReminder = (data) =>
  request('/reminders', { method: 'POST', body: data })

export const cancelReminder = (id) => request(`/reminders/${id}`, { method: 'DELETE' })
