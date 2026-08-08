import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { clsx } from 'clsx'
import { useRegister, useLogin } from '@/hooks/useAuth'
import { getErrorMessage } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { ROLES } from '@/utils/constants'
import type { UserRole } from '@/types/auth'

const schema = z.object({
  email: z.string().email('Enter a valid email'),
  full_name: z.string().max(255).optional(),
  password: z.string()
    .min(8, 'At least 8 characters')
    .regex(/[A-Z]/, 'Must contain an uppercase letter')
    .regex(/\d/, 'Must contain a digit'),
  confirm_password: z.string(),
  role: z.enum(['admin', 'analyst', 'auditor', 'supplier']),
}).refine((d) => d.password === d.confirm_password, {
  message: 'Passwords do not match',
  path: ['confirm_password'],
})

type FormValues = z.infer<typeof schema>

const inputClass =
  'w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500'

function passwordStrength(pw: string): { level: number; label: string; color: string } {
  let score = 0
  if (pw.length >= 8) score++
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++
  if (/\d/.test(pw)) score++
  if (/[^A-Za-z0-9]/.test(pw) || pw.length >= 14) score++

  if (score <= 1) return { level: 1, label: 'Weak', color: 'bg-red-500' }
  if (score <= 3) return { level: 2, label: 'Medium', color: 'bg-amber-500' }
  return { level: 3, label: 'Strong', color: 'bg-green-500' }
}

interface Props {
  /** In the admin "invite user" modal we don't auto-login */
  autoLogin?: boolean
  onSuccess?: () => void
}

export function RegisterForm({ autoLogin = true, onSuccess }: Props) {
  const registerMutation = useRegister()
  const login = useLogin()
  const {
    register, handleSubmit, watch, formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { role: 'analyst' as UserRole },
  })

  const password = watch('password') ?? ''
  const strength = passwordStrength(password)

  const onSubmit = (values: FormValues) => {
    registerMutation.mutate(
      {
        email: values.email,
        password: values.password,
        full_name: values.full_name || undefined,
        role: values.role,
      },
      {
        onSuccess: () => {
          onSuccess?.()
          if (autoLogin) {
            login.mutate({ email: values.email, password: values.password })
          }
        },
      },
    )
  }

  const isLoading = registerMutation.isPending || login.isPending

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Email</label>
        <input type="email" {...register('email')} className={inputClass} placeholder="you@company.com" />
        {errors.email && <p className="text-xs text-red-600 mt-1">{errors.email.message}</p>}
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Full name</label>
        <input {...register('full_name')} className={inputClass} placeholder="Jane Dupont" />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Password</label>
        <input type="password" {...register('password')} className={inputClass} placeholder="••••••••" />
        {password && (
          <div className="mt-1.5 flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={clsx('h-full rounded-full transition-all', strength.color)}
                style={{ width: `${(strength.level / 3) * 100}%` }}
              />
            </div>
            <span className="text-xs text-gray-500">{strength.label}</span>
          </div>
        )}
        {errors.password && <p className="text-xs text-red-600 mt-1">{errors.password.message}</p>}
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Confirm password</label>
        <input type="password" {...register('confirm_password')} className={inputClass} placeholder="••••••••" />
        {errors.confirm_password && (
          <p className="text-xs text-red-600 mt-1">{errors.confirm_password.message}</p>
        )}
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Role</label>
        <select {...register('role')} className={inputClass}>
          {ROLES.map((r) => (
            <option key={r} value={r} className="capitalize">{r}</option>
          ))}
        </select>
      </div>

      {registerMutation.error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {getErrorMessage(registerMutation.error)}
        </p>
      )}

      <Button type="submit" isLoading={isLoading} className="w-full">
        Create account
      </Button>
    </form>
  )
}
