import { request } from './client.js'

// DashboardRead: { month, summary (MonthlyReportRead), budget, goals, upcoming_reminders, recent_transactions }
export const getDashboard = (month) =>
  request(`/dashboard${month ? `?month=${encodeURIComponent(month)}` : ''}`)
