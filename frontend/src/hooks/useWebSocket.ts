import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuthStore } from '@/store/authStore'

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000'

export interface WsMessage {
  type: string
  payload: Record<string, unknown>
  timestamp: string
}

interface UseWebSocketOptions {
  companyId?: number
  onMessage?: (msg: WsMessage) => void
  onAnomalyAlert?: (payload: Record<string, unknown>) => void
  onTaskCompleted?: (payload: Record<string, unknown>) => void
}

/**
 * Manages a WebSocket connection to the live emissions feed.
 * Auto-reconnects on unexpected disconnect; closes cleanly on unmount.
 */
export function useWebSocket({
  companyId,
  onMessage,
  onAnomalyAlert,
  onTaskCompleted,
}: UseWebSocketOptions) {
  const token = useAuthStore((s) => s.token)
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null)
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>()

  // Keep callbacks in refs so the connection isn't rebuilt on every render
  const handlersRef = useRef({ onMessage, onAnomalyAlert, onTaskCompleted })
  handlersRef.current = { onMessage, onAnomalyAlert, onTaskCompleted }

  const connect = useCallback(() => {
    if (!token || !companyId) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const url = `${WS_BASE}/api/v1/ws/live/${companyId}?token=${token}`
    const ws = new WebSocket(url)

    ws.onopen = () => {
      setIsConnected(true)
      clearTimeout(reconnectTimeout.current)
    }

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data)
        setLastMessage(msg)
        handlersRef.current.onMessage?.(msg)

        if (msg.type === 'anomaly_detected') handlersRef.current.onAnomalyAlert?.(msg.payload)
        if (msg.type === 'task_completed') handlersRef.current.onTaskCompleted?.(msg.payload)
      } catch { /* ignore parse errors */ }
    }

    ws.onclose = (event) => {
      setIsConnected(false)
      // Auto-reconnect unless intentionally closed (code 1000)
      if (event.code !== 1000) {
        reconnectTimeout.current = setTimeout(connect, 3000)
      }
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [token, companyId])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimeout.current)
      wsRef.current?.close(1000, 'component unmounted')
      wsRef.current = null
    }
  }, [connect])

  const send = useCallback((type: string, payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }))
    }
  }, [])

  return { isConnected, lastMessage, send }
}
