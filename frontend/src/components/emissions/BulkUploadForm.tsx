import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Upload } from 'lucide-react'
import { emissionsApi } from '@/api/emissions'
import { getErrorMessage } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { toast } from '@/components/ui/Toast'
import { useTaskPoller } from '@/hooks/useTaskPoller'
import type { EmissionCreate } from '@/types/emission'

interface Props {
  companyId: number
  onSuccess: () => void
}

const EXAMPLE = `scope,category,co2_tonnes,reporting_year,reporting_month
scope_1,stationary_combustion,120.5,2024,1
scope_2,purchased_electricity,89.3,2024,1
scope_3,supply_chain,1540.0,2024,1`

/**
 * Paste-CSV bulk upload. Parses client-side, submits to the async bulk
 * endpoint (202 + task id) and polls the task until completion.
 */
export function BulkUploadForm({ companyId, onSuccess }: Props) {
  const [csv, setCsv] = useState('')
  const [taskId, setTaskId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { result, isPolling } = useTaskPoller(taskId)

  const mutation = useMutation({
    mutationFn: (records: Omit<EmissionCreate, 'company_id'>[]) =>
      emissionsApi.bulkUpload(companyId, records),
    onSuccess: (response) => {
      setTaskId(response.task_id)
      toast.info('Upload queued — processing in background')
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const parseAndSubmit = () => {
    const lines = csv.trim().split('\n').filter(Boolean)
    if (lines.length < 2) {
      toast.error('Paste CSV data with a header row and at least one record')
      return
    }
    const headers = lines[0].split(',').map((h) => h.trim())
    const records: Omit<EmissionCreate, 'company_id'>[] = []

    for (const line of lines.slice(1)) {
      const values = line.split(',').map((v) => v.trim())
      const row = Object.fromEntries(headers.map((h, i) => [h, values[i]]))
      records.push({
        scope: row.scope as EmissionCreate['scope'],
        category: row.category as EmissionCreate['category'],
        co2_tonnes: Number(row.co2_tonnes),
        reporting_year: Number(row.reporting_year),
        reporting_month: row.reporting_month ? Number(row.reporting_month) : undefined,
        data_source: 'bulk upload',
      })
    }
    mutation.mutate(records)
  }

  if (result?.status === 'SUCCESS') {
    const created = (result.result as { records_created?: number })?.records_created
    return (
      <div className="text-center py-6 space-y-3">
        <p className="text-sm font-medium text-green-700">
          ✓ Upload complete — {created ?? '?'} records created
        </p>
        <Button onClick={() => {
          queryClient.invalidateQueries({ queryKey: ['emissions'] })
          queryClient.invalidateQueries({ queryKey: ['summary'] })
          onSuccess()
        }}>
          Done
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500">
        Paste CSV rows (columns: scope, category, co2_tonnes, reporting_year, reporting_month).
      </p>
      <textarea
        value={csv}
        onChange={(e) => setCsv(e.target.value)}
        rows={8}
        placeholder={EXAMPLE}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 focus:ring-primary-500"
      />
      {isPolling && (
        <p className="text-xs text-amber-600 animate-pulse">
          Processing… task status: {result?.status ?? 'PENDING'}
        </p>
      )}
      {result?.status === 'FAILURE' && (
        <p className="text-xs text-red-600">Task failed: {result.error}</p>
      )}
      <Button
        onClick={parseAndSubmit}
        isLoading={mutation.isPending || isPolling}
        className="w-full"
      >
        <Upload className="w-4 h-4" /> Upload records
      </Button>
    </div>
  )
}
