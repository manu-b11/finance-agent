import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import ConfirmDialog from '../components/ConfirmDialog.jsx'

const ConfirmContext = createContext(null)

/*
  Provee confirm({ title, message, confirmLabel, cancelLabel, danger }):
  devuelve una promesa que resuelve true si el usuario confirma y false si
  cancela. Se usa en lugar de window.confirm.
*/
export function ConfirmProvider({ children }) {
  const [request, setRequest] = useState(null)
  const resolver = useRef(null)

  const confirm = useCallback((options) => {
    const opts = typeof options === 'string' ? { message: options } : (options ?? {})
    setRequest(opts)
    return new Promise((resolve) => {
      resolver.current = resolve
    })
  }, [])

  const close = useCallback((result) => {
    setRequest(null)
    resolver.current?.(result)
    resolver.current = null
  }, [])

  const value = useMemo(() => ({ confirm }), [confirm])

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      <ConfirmDialog
        open={Boolean(request)}
        title={request?.title}
        message={request?.message}
        confirmLabel={request?.confirmLabel ?? 'Confirmar'}
        cancelLabel={request?.cancelLabel ?? 'Cancelar'}
        danger={request?.danger}
        onConfirm={() => close(true)}
        onCancel={() => close(false)}
      />
    </ConfirmContext.Provider>
  )
}

export function useConfirm() {
  const context = useContext(ConfirmContext)
  if (!context) throw new Error('useConfirm necesita un ConfirmProvider.')
  return context.confirm
}
