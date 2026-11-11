import { useNavigate } from 'react-router-dom'
import AuthForm from '../components/auth/AuthForm.jsx'
import AuthLayout from '../components/auth/AuthLayout.jsx'

export default function Login() {
  const navigate = useNavigate()

  return (
    <AuthLayout>
      <AuthForm mode="login" onSuccess={() => navigate('/', { replace: true })} />
    </AuthLayout>
  )
}
