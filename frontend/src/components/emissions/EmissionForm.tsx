import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { emissionsApi } from '@/api/emissions'
import { getErrorMessage } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { toast } from '@/components/ui/Toast'
import { SCOPE_CATEGORIES, YEARS, MONTHS } from '@/utils/constants'
import { CATEGORY_LABELS, SCOPE_LABELS } from '@/utils/formatters'
import type { EmissionScope } from '@/types/emission'

const schema = z.object({
  scope: z.enum(['scope_1', 'scope_2', 'scope_3']),
  category: z.enum([
    'stationary_combustion', 'mobile_combustion',
    'purchased_electricity', 'purchased_heat',
    'business_travel', 'employee_commuting',
    'supply_chain', 'waste',
  ]),
  co2_tonnes: z.coerce.number().positive('Must be a positive number'),
  reporting_year: z.coerce.number().min(2000).max(2100),
  reporting_month: z.coerce.number().min(1).max(12),
  data_source: z.string().max(255).optional(),
  notes: z.string().optional(),
}).refine(
  (data) => SCOPE_CATEGORIES[data.scope].includes(data.category),
  { message: 'Category is not valid for the selected scope', path: ['category'] },
)

type FormValues = z.infer<typeof schema>

interface Props {
  companyId: number
  onSuccess: () => void
}

const inputClass =
  'w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500'

export function EmissionForm({ companyId, onSuccess }: Props) {
  const queryClient = useQueryClient()
  const {
    register, handleSubmit, watch, formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      scope: 'scope_1',
      category: 'stationary_combustion',
      reporting_year: 2024,
      reporting_month: 1,
    },
  })

  const scope = watch('scope') as EmissionScope

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      emissionsApi.create({ ...values, company_id: companyId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emissions'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
      toast.success('Emission record created')
      onSuccess()
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  return (
    <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Scope</label>
          <select {...register('scope')} className={inputClass}>
            {(['scope_1', 'scope_2', 'scope_3'] as const).map((s) => (
              <option key={s} value={s}>{SCOPE_LABELS[s]}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Category</label>
          <select {...register('category')} className={inputClass}>
            {SCOPE_CATEGORIES[scope]?.map((c) => (
              <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
            ))}
          </select>
          {errors.category && (
            <p className="text-xs text-red-600 mt-1">{errors.category.message}</p>
          )}
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">CO₂e (tonnes)</label>
        <input
          type="number" step="0.01" {...register('co2_tonnes')}
          className={inputClass} placeholder="125.5"
        />
        {errors.co2_tonnes && (
          <p className="text-xs text-red-600 mt-1">{errors.co2_tonnes.message}</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Year</label>
          <select {...register('reporting_year')} className={inputClass}>
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Month</label>
          <select {...register('reporting_month')} className={inputClass}>
            {MONTHS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Data source</label>
        <input
          {...register('data_source')} className={inputClass}
          placeholder="ERP export Q4 2024"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Notes</label>
        <textarea {...register('notes')} rows={2} className={inputClass} />
      </div>

      <Button type="submit" isLoading={mutation.isPending} className="w-full">
        Create record
      </Button>
    </form>
  )
}
