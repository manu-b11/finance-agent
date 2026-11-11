import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth.jsx'
import { errorMessage } from '../../api/client.js'
import Icon from '../Icon.jsx'

const COPY = {
  login: {
    title: 'Bienvenido de nuevo',
    subtitle: 'Inicia sesión para retomar tus conversaciones y tus finanzas.',
    submit: 'Iniciar sesión',
    loading: 'Entrando…',
    switchText: '¿Aún no tienes cuenta?',
    switchAction: 'Crear una cuenta',
  },
  register: {
    title: 'Crea tu cuenta',
    subtitle: 'Empieza a organizar tus finanzas en una conversación.',
    submit: 'Crear cuenta',
    loading: 'Creando cuenta…',
    switchText: '¿Ya tienes cuenta?',
    switchAction: 'Iniciar sesión',
  },
}

export default function AuthForm({ mode = 'login', onSwitch, onSuccess }) {
  const { login, register } = useAuth()
  const copy = COPY[mode]
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    if (loading) return
    setError('')
    setLoading(true)
    try {
      if (mode === 'register') await register(name.trim(), email.trim(), password)
      else await login(email.trim(), password)
      onSuccess?.()
    } catch (err) {
      setError(errorMessage(err))
      setLoading(false)
    }
  }

  const otherMode = mode === 'login' ? 'register' : 'login'

  return (
    <>
      <header className="auth-head">
        <h1 className="auth-title">{copy.title}</h1>
        <p className="auth-sub">{copy.subtitle}</p>
      </header>

      <form className="auth-form" onSubmit={onSubmit}>
        {error && (
          <div className="auth-alert" role="alert">
            <Icon name="x" />
            <span>{error}</span>
          </div>
        )}

        {mode === 'register' && (
          <label className="field auth-field">
            <span>Nombre</span>
            <div className="input-wrap">
              <Icon name="user" />
              <input
                type="text"
                required
                maxLength={255}
                autoComplete="name"
                placeholder="Tu nombre"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
              />
            </div>
          </label>
        )}

        <label className="field auth-field">
          <span>Correo</span>
          <div className="input-wrap">
            <Icon name="mail" />
            <input
              type="email"
              required
              autoComplete="email"
              placeholder="tu@correo.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus={mode === 'login'}
            />
          </div>
        </label>

        <label className="field auth-field">
          <span>Contraseña</span>
          <div className="input-wrap">
            <Icon name="lock" />
            <input
              type={showPassword ? 'text' : 'password'}
              required
              minLength={8}
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              placeholder={mode === 'register' ? 'Mínimo 8 caracteres' : 'Tu contraseña'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="button"
              className="reveal"
              aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((v) => !v)}
            >
              <Icon name={showPassword ? 'eyeOff' : 'eye'} />
            </button>
          </div>
          {mode === 'register' && <small className="field-hint">Usa al menos 8 caracteres.</small>}
        </label>

        <button className="btn primary auth-submit" disabled={loading}>
          {loading ? copy.loading : copy.submit}
        </button>
      </form>

      <p className="auth-switch">
        {copy.switchText}{' '}
        {onSwitch ? (
          <button type="button" className="auth-switch-link" onClick={() => onSwitch(otherMode)}>
            {copy.switchAction}
          </button>
        ) : (
          <Link to={`/${otherMode}`}>{copy.switchAction}</Link>
        )}
      </p>
    </>
  )
}
