import { request } from './client.js'

// Respuesta esperada de login: { access_token, token_type }
export const login = ({ email, password }) =>
  request('/auth/login', { method: 'POST', body: { email, password } })

// UserCreate: { name, email, password (8-128), timezone }. La zona horaria se guarda con el usuario (RNF-10).
export const register = ({ name, email, password }) =>
  request('/auth/register', {
    method: 'POST',
    body: {
      name,
      email,
      password,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/Bogota',
    },
  })

export const getMe = () => request('/auth/me')
