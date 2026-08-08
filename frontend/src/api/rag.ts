import { apiClient, BASE_URL } from './client'

export interface RagStatus {
  ready: boolean
  document_count: number
  llm_configured: boolean
}

export interface RagSearchResult {
  content: string
  metadata: Record<string, string>
  score: number
}

export const ragApi = {
  status: () =>
    apiClient.get<RagStatus>('/rag/status').then(r => r.data),

  ingestRegulatory: () =>
    apiClient.post<{ status: string; chunks: number }>('/rag/ingest/regulatory').then(r => r.data),

  search: (query: string, k = 5) =>
    apiClient
      .post<{ query: string; results: RagSearchResult[] }>('/rag/search', { query, k })
      .then(r => r.data),

  /**
   * Streaming chat via fetch + ReadableStream (consumed by useSSE).
   * EventSource can't POST and can't send Authorization headers —
   * fetch solves both.
   */
  streamChatFetch: (question: string, token: string): Promise<Response> =>
    fetch(`${BASE_URL}/api/v1/rag/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ question }),
    }),

  streamReportFetch: (companyId: number, year: number, token: string): Promise<Response> =>
    fetch(`${BASE_URL}/api/v1/rag/report/${companyId}/${year}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    }),
}
