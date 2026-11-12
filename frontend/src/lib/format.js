const copFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
})

// El backend serializa Decimal como string ("40500.00"); Number() solo se usa para mostrar.
export function formatCOP(value) {
  const n = Number(value)
  return copFormatter.format(Number.isFinite(n) ? n : 0)
}

// Acepta "2026-11-08" (sin desfase de zona horaria) o un ISO completo.
export function formatDate(value) {
  if (!value) return ''
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  const date = m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(date)
}

// "2026-11" → "noviembre de 2026"
export function formatMonth(value) {
  const m = /^(\d{4})-(\d{2})$/.exec(value ?? '')
  if (!m) return value ?? ''
  return new Intl.DateTimeFormat('es-CO', { month: 'long', year: 'numeric' }).format(
    new Date(+m[1], +m[2] - 1, 1),
  )
}

// Valores de ExpenseCategory en el backend (sin tildes) → texto para el usuario.
const CATEGORY_LABELS = {
  alimentacion: 'Alimentación',
  transporte: 'Transporte',
  vivienda: 'Vivienda',
  servicios: 'Servicios',
  salud: 'Salud',
  educacion: 'Educación',
  entretenimiento: 'Entretenimiento',
  ropa: 'Ropa',
  belleza: 'Belleza',
  hogar: 'Hogar',
  mascotas: 'Mascotas',
  regalos: 'Regalos',
  viajes: 'Viajes',
  suscripciones: 'Suscripciones',
  deporte: 'Deporte',
  tecnologia: 'Tecnología',
  seguros: 'Seguros',
  impuestos: 'Impuestos',
  otros: 'Otros',
}
export const categoryLabel = (c) => CATEGORY_LABELS[c] ?? c ?? ''

const capitalize = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s)

// UserRead incluye name. Se mantiene el correo como respaldo para datos antiguos.
export function displayName(user) {
  if (user?.name) return user.name
  if (user?.full_name) return user.full_name
  const local = (user?.email ?? '').split('@')[0]
  return capitalize(local.split(/[._-]/)[0])
}

export function firstName(user) {
  return displayName(user).split(/\s/)[0]
}

export function initial(user) {
  return (displayName(user)[0] ?? '?').toUpperCase()
}
