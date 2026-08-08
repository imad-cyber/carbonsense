import { Navigate, Link } from 'react-router-dom'
import { Zap } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { RegisterForm } from '@/components/auth/RegisterForm'

export function RegisterPage() {
  const token = useAuthStore((s) => s.token)
  if (token) return <Navigate to="/dashboard" replace />

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-primary-600 rounded-xl flex items-center justify-center mx-auto mb-4">
            <Zap className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Create your account</h1>
          <p className="text-sm text-gray-500 mt-1">Start tracking your carbon footprint</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <RegisterForm />
        </div>

        <p className="text-xs text-center text-gray-500 mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-primary-600 font-medium hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
