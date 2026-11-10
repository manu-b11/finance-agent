import { request } from './client.js'

// month: "2026-11". Devuelve un Blob PDF.
export const downloadMonthlyReport = (month) =>
  request(`/reports/monthly/${encodeURIComponent(month)}/pdf`, { responseType: 'blob' })

export const getMonthlyReport = (month) => request(`/reports/monthly/${encodeURIComponent(month)}`)
