import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus, Upload } from 'lucide-react'
import { emissionsApi } from '@/api/emissions'
import { PageHeader } from '@/components/layout/PageHeader'
import { CompanySelect } from '@/components/CompanySelect'
import { EmissionTable } from '@/components/emissions/EmissionTable'
import { EmissionForm } from '@/components/emissions/EmissionForm'
import { BulkUploadForm } from '@/components/emissions/BulkUploadForm'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Pagination } from '@/components/ui/Pagination'
import { useAuthStore } from '@/store/authStore'
import { YEARS, SCOPES } from '@/utils/constants'
import { SCOPE_LABELS } from '@/utils/formatters'
import type { EmissionScope } from '@/types/emission'

const PAGE_SIZE = 20

const selectClass =
  'px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500'

export function EmissionsPage() {
  const [companyId, setCompanyId] = useState<number | null>(null)
  const [year, setYear] = useState<number | undefined>(2024)
  const [scope, setScope] = useState<EmissionScope | undefined>()
  const [page, setPage] = useState(1)
  const [modal, setModal] = useState<'create' | 'bulk' | null>(null)
  const hasRole = useAuthStore((s) => s.hasRole)
  const canWrite = hasRole(['admin', 'analyst', 'supplier'])

  const { data, isLoading } = useQuery({
    queryKey: ['emissions', companyId, year, scope, page],
    queryFn: () =>
      emissionsApi.listByCompany(companyId!, { year, scope, page, page_size: PAGE_SIZE }),
    enabled: companyId !== null,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Emissions"
        subtitle="GHG Protocol emission records"
        actions={
          canWrite && companyId !== null && (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setModal('bulk')}>
                <Upload className="w-4 h-4" /> Bulk upload
              </Button>
              <Button onClick={() => setModal('create')}>
                <Plus className="w-4 h-4" /> Add record
              </Button>
            </div>
          )
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <CompanySelect value={companyId} onChange={(id) => { setCompanyId(id); setPage(1) }} />
        <select
          value={year ?? ''}
          onChange={(e) => { setYear(e.target.value ? Number(e.target.value) : undefined); setPage(1) }}
          className={selectClass}
        >
          <option value="">All years</option>
          {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
        <select
          value={scope ?? ''}
          onChange={(e) => { setScope((e.target.value || undefined) as EmissionScope | undefined); setPage(1) }}
          className={selectClass}
        >
          <option value="">All scopes</option>
          {SCOPES.map((s) => <option key={s} value={s}>{SCOPE_LABELS[s]}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <EmissionTable records={data?.items ?? []} isLoading={isLoading} />
        {data && data.total > PAGE_SIZE && (
          <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />
        )}
      </div>

      {companyId !== null && (
        <>
          <Modal isOpen={modal === 'create'} onClose={() => setModal(null)} title="Add emission record">
            <EmissionForm companyId={companyId} onSuccess={() => setModal(null)} />
          </Modal>
          <Modal isOpen={modal === 'bulk'} onClose={() => setModal(null)} title="Bulk upload (CSV)" size="lg">
            <BulkUploadForm companyId={companyId} onSuccess={() => setModal(null)} />
          </Modal>
        </>
      )}
    </div>
  )
}
