import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth.jsx'
import { ConfirmProvider } from './hooks/useConfirm.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Home from './pages/Home.jsx'
import Invoices from './pages/Invoices.jsx'
import Goals from './pages/Goals.jsx'
import Reminders from './pages/Reminders.jsx'
import Reports from './pages/Reports.jsx'

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="boot" />
  return user ? children : <Navigate to="/" replace />
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="boot" />
  return user ? <Navigate to="/" replace /> : children
}

export default function App() {
  return (
    <BrowserRouter>
      <ConfirmProvider>
        <AuthProvider>
          <Routes>
            {/* El chat es público: se pide cuenta cuando el usuario quiere guardar su información. */}
            <Route path="/" element={<Home />} />
            <Route path="/facturas" element={<ProtectedRoute><Invoices /></ProtectedRoute>} />
            <Route path="/metas" element={<ProtectedRoute><Goals /></ProtectedRoute>} />
            <Route path="/informes" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
            <Route path="/recordatorios" element={<ProtectedRoute><Reminders /></ProtectedRoute>} />
            <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
            <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </ConfirmProvider>
    </BrowserRouter>
  )
}
