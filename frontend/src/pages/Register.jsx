import { useNavigate } from 'react-router-dom'
import AuthForm from '../components/auth/AuthForm.jsx'
import AuthLayout from '../components/auth/AuthLayout.jsx'

export default function Register() {
  const navigate = useNavigate()

  return (
    <AuthLayout>
      <AuthForm mode="register" onSuccess={() => navigate('/', { replace: true })} />
    </AuthLayout>
  )
}
