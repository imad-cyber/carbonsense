import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Building2, Trash2 } from 'lucide-react'
import { companiesApi } from '@/api/companies'
import { getErrorMessage } from '@/api/client'
import { PageHeader } from '@/components/layout/PageHeader'
import { DataTable, type Column } from '@/components/ui/DataTable'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Pagination } from '@/components/ui/Pagination'
import { Badge } from '@/components/ui/Badge'
import { toast } from '@/components/ui/Toast'
import { useAuthStore } from '@/store/authStore'
import { formatDate } from '@/utils/formatters'
import { SECTORS } from '@/utils/constants'
import type { Company } from '@/types/company'

const schema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  country: z.string().length(2, 'Use a 2-letter ISO code (e.g. FR)').toUpperCase(),
  sector: z.enum([
    'energy', 'manufacturing', 'transport', 'finance',
    'technology', 'retail', 'healthcare', 'other',
  ]),
  employee_count: z.coerce.number().int().positive().optional(),
  annual_revenue_eur: z.coerce.number().positive().optional(),
})

type FormValues = z.infer<typeof schema>

const inputClass =
  'w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500'

export function CompaniesPage() {
  const [page, setPage] = useState(1)
  const [isModalOpen, setModalOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Company | null>(null)
  const queryClient = useQueryClient()
  const hasRole = useAuthStore((s) => s.hasRole)
  const canManage = hasRole(['admin', 'analyst'])
  const isAdmin = hasRole(['admin'])

  const { data, isLoading } = useQuery({
    queryKey: ['companies', page],
    queryFn: () => companiesApi.list(page, 20),
  })

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { sector: 'manufacturing' },
  })

  const createMutation = useMutation({
    mutationFn: companiesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['companies'] })
      toast.success('Company created')
      setModalOpen(false)
      reset()
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => companiesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['companies'] })
      toast.success('Company deleted')
      setDeleteTarget(null)
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const columns: Column<Company>[] = [
    {
      key: 'name',
      header: 'Company',
      render: (c) => (
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-primary-50 rounded-lg flex items-center justify-center">
            <Building2 className="w-3.5 h-3.5 text-primary-600" />
          </div>
          <span className="font-medium text-gray-900">{c.name}</span>
        </div>
      ),
    },
    { key: 'country', header: 'Country', render: (c) => c.country },
    {
      key: 'sector',
      header: 'Sector',
      render: (c) => <Badge variant="default" className="capitalize">{c.sector}</Badge>,
    },
    {
      key: 'employees',
      header: 'Employees',
      render: (c) => c.employee_count?.toLocaleString() ?? '—',
    },
    { key: 'created', header: 'Created', render: (c) => formatDate(c.created_at) },
    ...(isAdmin ? [{
      key: 'actions',
      header: '',
      render: (c: Company) => (
        <button
          onClick={(e) => { e.stopPropagation(); setDeleteTarget(c) }}
          className="p-1.5 text-gray-400 hover:text-red-600 rounded-md hover:bg-red-50"
          title="Delete company"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      ),
    } satisfies Column<Company>] : []),
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="Companies"
        subtitle="Reporting entities under CSRD scope"
        actions={
          canManage && (
            <Button onClick={() => setModalOpen(true)}>
              <Plus className="w-4 h-4" /> Add company
            </Button>
          )
        }
      />

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <DataTable
          columns={columns}
          data={data?.items ?? []}
          keyExtractor={(c) => c.id}
          isLoading={isLoading}
          emptyMessage="No companies yet — add your first reporting entity"
        />
        {data && data.total > 20 && (
          <Pagination page={page} pageSize={20} total={data.total} onPageChange={setPage} />
        )}
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setModalOpen(false)} title="Add company">
        <form onSubmit={handleSubmit((v) => createMutation.mutate(v))} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Name</label>
            <input {...register('name')} className={inputClass} placeholder="Acme Industries SA" />
            {errors.name && <p className="text-xs text-red-600 mt-1">{errors.name.message}</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Country (ISO-2)</label>
              <input {...register('country')} className={inputClass} placeholder="FR" maxLength={2} />
              {errors.country && <p className="text-xs text-red-600 mt-1">{errors.country.message}</p>}
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Sector</label>
              <select {...register('sector')} className={inputClass}>
                {SECTORS.map((s) => <option key={s} value={s} className="capitalize">{s}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Employees</label>
              <input type="number" {...register('employee_count')} className={inputClass} placeholder="500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Revenue (€)</label>
              <input type="number" step="1000" {...register('annual_revenue_eur')} className={inputClass} placeholder="120000000" />
            </div>
          </div>

          <Button type="submit" isLoading={createMutation.isPending} className="w-full">
            Create company
          </Button>
        </form>
      </Modal>

      <Modal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete company"
        size="sm"
      >
        <p className="text-sm text-gray-600 mb-4">
          Delete <strong>{deleteTarget?.name}</strong> and all its emission records?
          This cannot be undone.
        </p>
        <div className="flex gap-3">
          <Button variant="secondary" className="flex-1" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button
            variant="danger" className="flex-1"
            isLoading={deleteMutation.isPending}
            onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
          >
            Delete
          </Button>
        </div>
      </Modal>
    </div>
  )
}
