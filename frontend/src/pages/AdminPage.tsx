import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { UserPlus, Database, RefreshCw, Activity } from 'lucide-react'
import { predictionsApi } from '@/api/predictions'
import { ragApi } from '@/api/rag'
import { getErrorMessage } from '@/api/client'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { toast } from '@/components/ui/Toast'
import { RegisterForm } from '@/components/auth/RegisterForm'

export function AdminPage() {
  const [inviteOpen, setInviteOpen] = useState(false)

  const { data: modelStatus, refetch: refetchModels } = useQuery({
    queryKey: ['model-status'],
    queryFn: predictionsApi.status,
  })

  const { data: ragStatus, refetch: refetchRag } = useQuery({
    queryKey: ['rag-status'],
    queryFn: ragApi.status,
  })

  const retrain = useMutation({
    mutationFn: predictionsApi.triggerRetrain,
    onSuccess: () => toast.info('Model retraining queued'),
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const ingest = useMutation({
    mutationFn: ragApi.ingestRegulatory,
    onSuccess: (res) => {
      toast.success(`Regulatory texts ingested — ${res.chunks} chunks`)
      refetchRag()
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Admin"
        subtitle="Platform administration and system health"
        actions={
          <Button onClick={() => setInviteOpen(true)}>
            <UserPlus className="w-4 h-4" /> Invite user
          </Button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          title="ML models"
          subtitle="Forecasting and anomaly detection model status"
          actions={
            <Button
              size="sm" variant="secondary"
              onClick={() => retrain.mutate()}
              isLoading={retrain.isPending}
            >
              <RefreshCw className="w-3.5 h-3.5" /> Retrain now
            </Button>
          }
        >
          <div className="space-y-3">
            <StatusRow
              label="XGBoost forecasting model"
              ok={modelStatus?.forecasting_model ?? false}
              okText="Trained & loaded"
              koText="Not trained"
            />
            <StatusRow
              label="Isolation Forest anomaly detector"
              ok={modelStatus?.anomaly_detector ?? false}
              okText="Trained & loaded"
              koText="Not trained"
            />
            <button
              onClick={() => refetchModels()}
              className="text-xs text-primary-600 hover:underline flex items-center gap-1"
            >
              <Activity className="w-3 h-3" /> Refresh status
            </button>
          </div>
        </Card>

        <Card
          title="RAG knowledge base"
          subtitle="Vector store powering the ESG Assistant and CSRD reports"
          actions={
            <Button
              size="sm" variant="secondary"
              onClick={() => ingest.mutate()}
              isLoading={ingest.isPending}
            >
              <Database className="w-3.5 h-3.5" /> Ingest texts
            </Button>
          }
        >
          <div className="space-y-3">
            <StatusRow
              label="OpenAI LLM"
              ok={ragStatus?.llm_configured ?? false}
              okText="Configured"
              koText="OPENAI_API_KEY missing"
            />
            <StatusRow
              label="FAISS vector store"
              ok={ragStatus?.ready ?? false}
              okText={`Ready — ${ragStatus?.document_count ?? 0} chunks`}
              koText="Empty — run ingestion"
            />
          </div>
        </Card>
      </div>

      <Modal isOpen={inviteOpen} onClose={() => setInviteOpen(false)} title="Invite a new user">
        <RegisterForm
          autoLogin={false}
          onSuccess={() => {
            toast.success('User account created')
            setInviteOpen(false)
          }}
        />
      </Modal>
    </div>
  )
}

function StatusRow({ label, ok, okText, koText }: {
  label: string; ok: boolean; okText: string; koText: string
}) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
      <span className="text-sm text-gray-700">{label}</span>
      <Badge variant={ok ? 'success' : 'warning'}>{ok ? okText : koText}</Badge>
    </div>
  )
}
