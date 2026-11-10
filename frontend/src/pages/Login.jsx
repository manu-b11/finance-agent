import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import { errorMessage } from '../api/client.js'

export default function Login() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password) // al haber sesión, PublicRoute redirige a "/"
    } catch (err) {
      setError(errorMessage(err))
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1>Finly</h1>
        <p>Inicia sesión para continuar.</p>
        <label className="field">Correo
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">Contraseña
          <input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <div className="error-text">{error}</div>}
        <button className="btn primary" disabled={loading}>{loading ? 'Entrando…' : 'Entrar'}</button>
        <div className="auth-alt">¿No tienes cuenta? <Link to="/register">Regístrate</Link></div>
      </form>
    </div>
  )
}
