import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'
import axios from 'axios'
import { useLogin } from '@/hooks/useAuth'
import { getErrorMessage } from '@/api/client'
import { Button } from '@/components/ui/Button'

const schema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
})

type FormValues = z.infer<typeof schema>

const inputClass =
  'w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500'

export function LoginForm() {
  const login = useLogin()
  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
  })

  const apiError = login.error
    ? axios.isAxiosError(login.error) && login.error.response?.status === 429
      ? 'Too many login attempts — wait a minute and try again.'
      : getErrorMessage(login.error)
    : null

  return (
    <form onSubmit={handleSubmit((v) => login.mutate(v))} className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Email</label>
        <input
          type="email" autoComplete="email" {...register('email')}
          className={inputClass} placeholder="you@company.com"
        />
        {errors.email && <p className="text-xs text-red-600 mt-1">{errors.email.message}</p>}
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Password</label>
        <input
          type="password" autoComplete="current-password" {...register('password')}
          className={inputClass} placeholder="••••••••"
        />
        {errors.password && <p className="text-xs text-red-600 mt-1">{errors.password.message}</p>}
      </div>

      {apiError && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {apiError}
        </p>
      )}

      <Button type="submit" isLoading={login.isPending} className="w-full">
        Sign in
      </Button>

      <p className="text-xs text-center text-gray-500">
        No account?{' '}
        <Link to="/register" className="text-primary-600 font-medium hover:underline">
          Register
        </Link>
      </p>
    </form>
  )
}
