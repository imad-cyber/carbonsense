import { useState, useCallback, useRef } from 'react'

interface UseSSEOptions {
  onChunk?: (chunk: string) => void
  onDone?: (fullText: string) => void
  onError?: (error: Error) => void
}

/**
 * Hook for consuming Server-Sent Events (SSE) from the backend.
 * Used for the RAG chat and CSRD report streaming endpoints.
 *
 * Uses fetch + ReadableStream instead of EventSource because:
 * 1. EventSource doesn't support POST requests
 * 2. EventSource doesn't support custom headers (we need Authorization)
 */
export function useSSE(options: UseSSEOptions = {}) {
  const [text, setText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const optionsRef = useRef(options)
  optionsRef.current = options

  const stream = useCallback(async (fetchPromise: Promise<Response>) => {
    // Cancel any in-flight stream
    abortRef.current?.abort()
    abortRef.current = new AbortController()

    setText('')
    setError(null)
    setIsStreaming(true)

    let accumulated = ''

    try {
      const response = await fetchPromise

      if (!response.ok) {
        let detail = `${response.status} ${response.statusText}`
        try {
          const body = (await response.json()) as { detail?: string }
          if (body.detail) detail = body.detail
        } catch { /* non-JSON error body */ }
        throw new Error(detail)
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      streaming:
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // SSE frames are separated by a blank line
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''

        for (const frame of frames) {
          const dataLines = frame
            .split('\n')
            .filter((l) => l.startsWith('data:'))
            .map((l) => l.slice(5).trim())
          if (dataLines.length === 0) continue

          try {
            const json = JSON.parse(dataLines.join('')) as { chunk: string; done: boolean }
            if (json.done) {
              optionsRef.current.onDone?.(accumulated)
              break streaming
            }
            accumulated += json.chunk
            setText(accumulated)
            optionsRef.current.onChunk?.(json.chunk)
          } catch {
            // Malformed SSE line — skip it
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message)
        optionsRef.current.onError?.(err)
      }
    } finally {
      setIsStreaming(false)
    }

    return accumulated
  }, [])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setIsStreaming(false)
  }, [])

  const reset = useCallback(() => {
    setText('')
    setError(null)
  }, [])

  return { text, isStreaming, error, stream, cancel, reset }
}
