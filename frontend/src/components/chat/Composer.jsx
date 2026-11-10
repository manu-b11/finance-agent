import { forwardRef, useEffect, useImperativeHandle, useLayoutEffect, useRef, useState } from 'react'
import Icon from '../Icon.jsx'

const MENU = [
  { icon: 'clip', label: 'Subir factura', upload: true },
  { sep: true },
  { icon: 'expense', label: 'Registrar gasto', fill: 'Registré un gasto de ' },
  { icon: 'income', label: 'Registrar ingreso', fill: 'Registré un ingreso de ' },
  { icon: 'goal', label: 'Crear meta de ahorro', fill: 'Quiero crear una meta de ahorro de ' },
  { icon: 'bell', label: 'Crear recordatorio', fill: 'Recuérdame ' },
  { icon: 'report', label: 'Informe del mes', send: 'Quiero descargar el informe PDF del mes' },
]

/*
  Componente controlado: el texto y el archivo viven en Home.
  Ref expuesta: focus(), openFilePicker()
*/
const Composer = forwardRef(function Composer(
  { value, onChange, file, onFileChange, onSubmit, onSendText, disabled, autoFocus },
  ref,
) {
  const textRef = useRef(null)
  const fileRef = useRef(null)
  const attachRef = useRef(null)
  const menuRef = useRef(null)
  const [menuOpen, setMenuOpen] = useState(false)

  useImperativeHandle(ref, () => ({
    focus: () => textRef.current?.focus(),
    openFilePicker: () => fileRef.current?.click(),
  }), [])

  useEffect(() => {
    if (autoFocus) textRef.current?.focus()
  }, [autoFocus])

  // Autoajuste de altura (en móvil queda fija en 38px, como el prototipo)
  useLayoutEffect(() => {
    const el = textRef.current
    if (!el) return
    if (window.matchMedia('(max-width:1023px)').matches) {
      el.style.height = '38px'
      return
    }
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 180) + 'px'
  }, [value])

  // Posicionar el menú "+" sobre (o bajo) el botón
  useLayoutEffect(() => {
    if (!menuOpen || !menuRef.current || !attachRef.current) return
    const r = attachRef.current.getBoundingClientRect()
    const { offsetHeight: h, offsetWidth: w } = menuRef.current
    const above = r.top - h - 12
    const top = above >= 8 ? above : Math.min(r.bottom + 12, window.innerHeight - h - 8)
    menuRef.current.style.top = Math.max(8, top) + 'px'
    menuRef.current.style.left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8)) + 'px'
  }, [menuOpen])

  useEffect(() => {
    if (!menuOpen) return
    const close = () => setMenuOpen(false)
    const onDown = (e) => {
      if (!menuRef.current?.contains(e.target) && !attachRef.current?.contains(e.target)) close()
    }
    const onKey = (e) => e.key === 'Escape' && close()
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    window.addEventListener('resize', close)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', close)
    }
  }, [menuOpen])

  const choose = (item) => {
    setMenuOpen(false)
    if (item.upload) fileRef.current?.click()
    else if (item.fill) {
      onChange(item.fill)
      textRef.current?.focus()
    } else if (item.send) onSendText(item.send)
  }

  const ready = value.trim().length > 0 || !!file

  return (
    <div className="composer-wrap">
      <form
        className={`composer${file ? ' has-file' : ''}`}
        autoComplete="off"
        onSubmit={(e) => {
          e.preventDefault()
          onSubmit()
        }}
      >
        {file && (
          <div className="file-tag show">
            <Icon name="receipt" />
            <span>{file.name}</span>
            <button type="button" onClick={() => onFileChange(null)} aria-label="Quitar archivo">
              <Icon name="x" />
            </button>
          </div>
        )}

        <textarea
          ref={textRef}
          rows={1}
          placeholder="Pregúntale a Finly"
          aria-label="Mensaje"
          maxLength={2000}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              onSubmit()
            }
          }}
        />

        <button
          ref={attachRef}
          type="button"
          className={`round-btn attach${menuOpen ? ' open' : ''}`}
          aria-label="Abrir menú de acciones"
          onClick={() => setMenuOpen((v) => !v)}
        >
          <Icon name="plus" />
        </button>

        <button
          type="submit"
          className={`round-btn send${ready ? ' ready' : ''}`}
          aria-label="Enviar"
          disabled={disabled}
        >
          <Icon name="up" />
        </button>

        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) onFileChange(f)
            e.target.value = ''
          }}
        />
      </form>

      {menuOpen && (
        <div className="plus-menu" ref={menuRef}>
          {MENU.map((item, i) =>
            item.sep ? (
              <div key={i} className="plus-sep" />
            ) : (
              <button key={item.label} type="button" className="plus-item" onClick={() => choose(item)}>
                <Icon name={item.icon} />{item.label}
              </button>
            ),
          )}
        </div>
      )}
    </div>
  )
})

export default Composer
