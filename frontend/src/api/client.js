// Cliente HTTP base: URL, JWT y errores. Ningún otro archivo usa fetch directamente
// (salvo api/chat.js para SSE, que reutiliza safeFetch y authHeaders).

export const API_URL = import.meta.env.VITE_API_URL ?? '/api'
const TOKEN_KEY = 'finly_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

export class ApiError extends Error {
  constructor(message, status = 0, detail = null, code = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.code = code
  }
}

const DEFAULT_MESSAGES = {
  0: 'No pude conectar con el servidor. Revisa tu conexión.',
  401: 'Tu sesión expiró. Inicia sesión de nuevo.',
  413: 'El archivo es demasiado grande.',
  415: 'Ese tipo de archivo no es válido. Sube un PDF o una imagen.',
  422: 'Los datos enviados no son válidos.',
  503: 'El asistente de IA no está disponible en este momento. Inténtalo de nuevo en unos minutos.',
}

export function authHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function toApiError(res) {
  let detail = null
  let code = null
  try {
    const data = await res.json()
    detail = data?.message ?? data?.detail ?? null
    code = data?.code ?? null
  } catch {
    /* respuesta sin JSON */
  }
  if (res.status === 401 && getToken()) {
    clearToken()
    window.dispatchEvent(new Event('auth:expired'))
  }
  const message = typeof detail === 'string' ? detail : (DEFAULT_MESSAGES[res.status] ?? 'Ocurrió un error inesperado.')
  return new ApiError(message, res.status, detail, code)
}

// fetch que convierte fallos de red en ApiError y deja pasar AbortError.
export async function safeFetch(url, init) {
  try {
    return await fetch(url, init)
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw new ApiError(DEFAULT_MESSAGES[0], 0)
  }
}

export async function request(path, { method = 'GET', body, headers, signal, responseType = 'json' } = {}) {
  const isForm = body instanceof FormData
  const res = await safeFetch(`${API_URL}${path}`, {
    method,
    signal,
    headers: {
      ...(body != null && !isForm ? { 'Content-Type': 'application/json' } : {}),
      ...authHeaders(),
      ...headers,
    },
    body: body == null ? undefined : isForm ? body : JSON.stringify(body),
  })
  if (!res.ok) throw await toApiError(res)
  if (res.status === 204) return null
  return responseType === 'blob' ? res.blob() : res.json()
}

export function errorMessage(err) {
  return err instanceof ApiError ? err.message : (err?.message || 'Ocurrió un error inesperado.')
}
