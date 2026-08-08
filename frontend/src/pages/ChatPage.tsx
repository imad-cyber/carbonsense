import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Send, Sparkles, Database } from 'lucide-react'
import { clsx } from 'clsx'
import { ragApi } from '@/api/rag'
import { getErrorMessage } from '@/api/client'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { toast } from '@/components/ui/Toast'
import { useSSE } from '@/hooks/useSSE'
import { useAuthStore } from '@/store/authStore'
import { SUGGESTED_QUESTIONS } from '@/utils/constants'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const token = useAuthStore((s) => s.token)
  const hasRole = useAuthStore((s) => s.hasRole)
  const bottomRef = useRef<HTMLDivElement>(null)

  const { data: ragStatus, refetch: refetchStatus } = useQuery({
    queryKey: ['rag-status'],
    queryFn: ragApi.status,
  })

  const ingest = useMutation({
    mutationFn: ragApi.ingestRegulatory,
    onSuccess: (res) => {
      toast.success(`Knowledge base ready — ${res.chunks} chunks indexed`)
      refetchStatus()
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const { text: streamingText, isStreaming, error, stream } = useSSE({
    onDone: (fullText) => {
      setMessages((prev) => [...prev, { role: 'assistant', content: fullText }])
    },
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  const ask = (question: string) => {
    if (!question.trim() || isStreaming || !token) return
    setMessages((prev) => [...prev, { role: 'user', content: question }])
    setInput('')
    stream(ragApi.streamChatFetch(question, token))
  }

  const ready = ragStatus?.ready && ragStatus?.llm_configured

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <PageHeader
        title="ESG Assistant"
        subtitle="Ask about CSRD, ESRS E1 and GHG Protocol — answers grounded in regulatory texts"
        actions={
          <div className="flex items-center gap-2">
            {ragStatus && (
              <Badge variant={ready ? 'success' : 'warning'}>
                {!ragStatus.llm_configured
                  ? 'LLM not configured'
                  : ragStatus.ready
                    ? `${ragStatus.document_count} docs indexed`
                    : 'Knowledge base empty'}
              </Badge>
            )}
            {hasRole(['admin', 'analyst']) && !ragStatus?.ready && (
              <Button size="sm" variant="secondary" onClick={() => ingest.mutate()} isLoading={ingest.isPending}>
                <Database className="w-3.5 h-3.5" /> Ingest regulatory texts
              </Button>
            )}
          </div>
        }
      />

      {/* Message list */}
      <div className="flex-1 overflow-y-auto scrollbar-thin mt-4 space-y-4 pr-2">
        {messages.length === 0 && !isStreaming && (
          <div className="text-center py-10">
            <Sparkles className="w-8 h-8 text-primary-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500 mb-4">Ask anything about EU sustainability reporting.</p>
            <div className="flex flex-wrap justify-center gap-2 max-w-2xl mx-auto">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => ask(q)}
                  disabled={!ready}
                  className="text-xs px-3 py-1.5 bg-white border border-gray-200 rounded-full text-gray-600 hover:border-primary-300 hover:text-primary-700 transition-colors disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} role={msg.role} content={msg.content} />
        ))}

        {isStreaming && (
          <MessageBubble role="assistant" content={streamingText || '…'} streaming />
        )}

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 max-w-2xl">
            {error}
          </p>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={(e) => { e.preventDefault(); ask(input) }}
        className="mt-4 flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={ready ? 'e.g. What does ESRS E1 require for Scope 3?' : 'Configure the LLM and ingest documents first'}
          disabled={!ready || isStreaming}
          className="flex-1 px-4 py-2.5 border border-gray-300 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:bg-gray-50"
        />
        <Button type="submit" disabled={!ready || isStreaming || !input.trim()}>
          <Send className="w-4 h-4" />
        </Button>
      </form>
    </div>
  )
}

function MessageBubble({ role, content, streaming }: ChatMessage & { streaming?: boolean }) {
  const isUser = role === 'user'
  return (
    <div className={clsx('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={clsx(
          'max-w-2xl rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap',
          isUser
            ? 'bg-primary-600 text-white rounded-br-sm'
            : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm',
        )}
      >
        {content}
        {streaming && <span className="inline-block w-1.5 h-4 bg-primary-400 ml-0.5 animate-pulse align-text-bottom" />}
      </div>
    </div>
  )
}
