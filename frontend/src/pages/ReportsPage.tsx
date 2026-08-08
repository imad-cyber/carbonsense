import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, Download, Square } from 'lucide-react'
import { ragApi } from '@/api/rag'
import { PageHeader } from '@/components/layout/PageHeader'
import { CompanySelect } from '@/components/CompanySelect'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { useSSE } from '@/hooks/useSSE'
import { useAuthStore } from '@/store/authStore'
import { YEARS } from '@/utils/constants'

export function ReportsPage() {
  const [companyId, setCompanyId] = useState<number | null>(null)
  const [year, setYear] = useState(2024)
  const token = useAuthStore((s) => s.token)

  const { data: ragStatus } = useQuery({
    queryKey: ['rag-status'],
    queryFn: ragApi.status,
  })

  const { text, isStreaming, error, stream, cancel, reset } = useSSE()

  const generate = () => {
    if (companyId === null || !token) return
    stream(ragApi.streamReportFetch(companyId, year, token))
  }

  const download = () => {
    const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `csrd-report-company${companyId}-${year}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const llmReady = ragStatus?.llm_configured ?? false

  return (
    <div className="space-y-6">
      <PageHeader
        title="CSRD Reports"
        subtitle="AI-generated ESRS E1 climate disclosures"
        actions={
          <div className="flex items-center gap-3">
            <CompanySelect value={companyId} onChange={setCompanyId} />
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        }
      />

      {!llmReady && ragStatus && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
          Report generation requires an OpenAI API key on the backend
          (<code className="font-mono bg-amber-100 px-1 rounded">OPENAI_API_KEY</code> in .env).
        </div>
      )}

      <Card
        title="ESRS E1 Climate Change disclosure"
        subtitle="Streamed live from the RAG pipeline — grounded in your emission data and regulatory context"
        actions={
          <div className="flex items-center gap-2">
            {isStreaming && (
              <>
                <Badge variant="info">Generating…</Badge>
                <Button size="sm" variant="secondary" onClick={cancel}>
                  <Square className="w-3 h-3" /> Stop
                </Button>
              </>
            )}
            {!isStreaming && text && (
              <>
                <Button size="sm" variant="secondary" onClick={download}>
                  <Download className="w-3.5 h-3.5" /> Download .md
                </Button>
                <Button size="sm" variant="secondary" onClick={reset}>Clear</Button>
              </>
            )}
            <Button
              size="sm"
              onClick={generate}
              disabled={!llmReady || companyId === null || isStreaming}
            >
              <FileText className="w-3.5 h-3.5" /> Generate report
            </Button>
          </div>
        }
      >
        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-4">
            {error}
          </p>
        )}

        {!text && !isStreaming ? (
          <EmptyState
            icon={FileText}
            title="No report yet"
            description="Select a company and year, then generate the ESRS E1 narrative. Text streams in live as the LLM writes it."
          />
        ) : (
          <article className="prose-sm max-w-none whitespace-pre-wrap font-serif text-gray-800 leading-relaxed">
            {text}
            {isStreaming && (
              <span className="inline-block w-1.5 h-4 bg-primary-400 ml-0.5 animate-pulse align-text-bottom" />
            )}
          </article>
        )}
      </Card>
    </div>
  )
}
