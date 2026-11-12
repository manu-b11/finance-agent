import { request } from './client.js'

/*
  GoalProgressRead (app/schemas/savings_goal.py):
  { id, name, target_amount, deadline, accumulated, remaining, percentage, completed,
    days_remaining, suggested_monthly_contribution }
*/

export const listGoals = () => request('/goals')

export const createGoal = (data) => request('/goals', { method: 'POST', body: data })

export const updateGoal = (id, data) =>
  request(`/goals/${id}`, { method: 'PATCH', body: data })

export const deleteGoal = (id) => request(`/goals/${id}`, { method: 'DELETE' })

export const addContribution = (id, data) =>
  request(`/goals/${id}/contributions`, { method: 'POST', body: data })
