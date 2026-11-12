const norm = (text) => text.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')

const EDUCATIONAL = /^\W*(como|que es|que son|por que|para que|explica|me explicas|cual es la diferencia)\b/

const AMOUNT = /\$?\s?(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(?:\s*(millones|millon|mil|k))?/g

export function parseAmount(text) {
  for (const match of norm(text).matchAll(AMOUNT)) {
    const [, raw, unit] = match
    let value
    if (unit) value = parseFloat(raw.replace(',', '.')) * (unit === 'mil' || unit === 'k' ? 1e3 : 1e6)
    else if (/^\d{1,3}([.,]\d{3})+$/.test(raw)) value = Number(raw.replace(/[.,]/g, ''))
    else value = Number(raw.replace(',', '.'))
    if (Number.isFinite(value) && value >= 100) return Math.round(value)
  }
  return null
}

const INTENTS = [
  {
    kind: 'invoice',
    title: 'Factura sin leer',
    saves: true,
    test: (t) => /factura/.test(t),
    reply: 'Puedo leer tu factura y mostrarte lo que encuentre para que la confirmes antes de registrarla. Para guardarla, te recomiendo crear tu cuenta: es gratis y toma menos de un minuto.',
  },
  {
    kind: 'reminder',
    title: 'Recordatorio sin crear',
    saves: true,
    test: (t) => /recordatorio|recuerdame|recuerda me|avisame/.test(t),
    reply: 'Puedo programar ese recordatorio y avisarte cuando llegue la hora. Para que quede guardado, te recomiendo crear tu cuenta: es gratis y toma menos de un minuto.',
  },
  {
    kind: 'report',
    title: 'Tu informe mensual',
    saves: false,
    test: (t) => /\b(informe|reporte)s?\b/.test(t),
    reply: 'Puedo armarte un informe con tus ingresos, gastos y categorías, y dejártelo en PDF. Se genera con tus movimientos guardados, así que te recomiendo crear tu cuenta para empezar a registrarlos.',
  },
  {
    kind: 'budget',
    title: 'Presupuesto sin guardar',
    saves: true,
    test: (t, amount) =>
      /presupuesto/.test(t) && (amount != null || /(mi presupuesto|cuanto me queda|establec|defin|fij|crear|quiero)/.test(t)),
    reply: 'Puedo ayudarte a fijar tu presupuesto mensual y decirte cuánto te queda disponible. Para guardarlo, te recomiendo crear tu cuenta: es gratis y toma menos de un minuto.',
  },
  {
    kind: 'goal',
    title: 'Meta sin crear',
    saves: true,
    test: (t, amount) => /\bmeta\b/.test(t) && (amount != null || /ahorr/.test(t)),
    reply: 'Puedo crear esa meta de ahorro y seguir tu progreso con cada aporte. Para guardarla, te recomiendo crear tu cuenta: es gratis y toma menos de un minuto.',
  },
  {
    kind: 'income',
    title: 'Ingreso sin guardar',
    saves: true,
    test: (t) => /(me pagaron|me pagan|recibi|cobre|consignaron|depositaron|ingreso de|registr\w* un ingreso)/.test(t),
    reply: 'Puedo registrar ese ingreso y reflejarlo en tu balance. Para guardarlo, te recomiendo crear tu cuenta: es gratis y toma menos de un minuto.',
  },
  {
    kind: 'expense',
    title: 'Gasto sin guardar',
    saves: true,
    test: (t) => /(\bgaste\b|\bgastamos\b|\bpague\b|\bpagamos\b|\bcompre\b|\bcompramos\b|registr\w* un gasto|gasto de)/.test(t),
    reply: 'Puedo registrar ese gasto, clasificarlo por categoría y sumarlo a tu balance. Para guardarlo, te recomiendo crear tu cuenta: es gratis y toma menos de un minuto.',
  },
  {
    kind: 'balance',
    title: 'Tu balance',
    saves: false,
    test: (t) => /(mi balance|balance de (este|el|mi)|cuanto (he gastado|gaste|llevo|me queda|tengo)|mis (gastos|ingresos|movimientos)|en que gasto)/.test(t),
    reply: 'Puedo calcular tu balance con tus ingresos y gastos reales. Para llevarlo al día, te recomiendo crear tu cuenta y registrar tus movimientos.',
  },
]

export const LIMIT_INTENT = {
  kind: 'limit',
  title: 'Guarda tus finanzas',
  saves: false,
  amount: null,
  reply: 'Si quieres seguir y guardar la información de tus finanzas, te recomiendo crear tu cuenta. Es gratis y toma menos de un minuto.',
}

export function detectIntent(text, hasFile = false) {
  if (hasFile) {
    const { test, ...invoice } = INTENTS[0]
    return { ...invoice, amount: null }
  }
  const t = norm(text)
  if (EDUCATIONAL.test(t)) return null
  const amount = parseAmount(text)
  const found = INTENTS.find((intent) => intent.test(t, amount))
  if (!found) return null
  const { test, ...intent } = found
  return { ...intent, amount: intent.kind === 'expense' || intent.kind === 'income' ? amount : null }
}
