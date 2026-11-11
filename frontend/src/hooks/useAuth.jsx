import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { clearToken, getToken, setToken } from '../api/client.js'
import { getMe, login as apiLogin, register as apiRegister } from '../api/auth.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(() => !!getToken())

  // Restaurar sesión si hay token guardado
  useEffect(() => {
    if (!getToken()) return
    let alive = true
    getMe()
      .then((u) => alive && setUser(u))
      .catch(() => clearToken())
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [])

  // El cliente HTTP emite este evento cuando el backend responde 401
  useEffect(() => {
    const onExpired = () => setUser(null)
    window.addEventListener('auth:expired', onExpired)
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [])

  const login = useCallback(async (email, password) => {
    const { access_token } = await apiLogin({ email, password })
    setToken(access_token)
    setUser(await getMe())
  }, [])

  const register = useCallback(
    async (name, email, password) => {
      await apiRegister({ name, email, password })
      await login(email, password)
    },
    [login],
  )

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return ctx
}
