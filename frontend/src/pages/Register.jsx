import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import { errorMessage } from '../api/client.js'

export default function Register() {
  const { register } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await register(name, email, password)
    } catch (err) {
      setError(errorMessage(err))
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1>Crear cuenta</h1>
        <p>Empieza a organizar tus finanzas.</p>
        <label className="field">Nombre
          <input type="text" required maxLength={100} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="field">Correo
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">Contraseña
          <input type="password" required minLength={8} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <div className="error-text">{error}</div>}
        <button className="btn primary" disabled={loading}>{loading ? 'Creando…' : 'Crear cuenta'}</button>
        <div className="auth-alt">¿Ya tienes cuenta? <Link to="/login">Inicia sesión</Link></div>
      </form>
    </div>
  )
}
