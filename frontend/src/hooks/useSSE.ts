import { useState, useEffect, useRef, useCallback } from 'react'
import { Snapshot } from '../types'

interface SSEState {
  snapshot: Snapshot | null
  connected: boolean
  lastUpdate: number | null
}

export function useSSE(url: string): SSEState {
  const [state, setState] = useState<SSEState>({
    snapshot: null,
    connected: false,
    lastUpdate: null,
  })
  const retryDelay = useRef(1000)
  const esRef = useRef<EventSource | null>(null)
  const cancelledRef = useRef(false)

  const connect = useCallback(() => {
    if (cancelledRef.current) return

    const es = new EventSource(url)
    esRef.current = es

    es.addEventListener('update', (e: MessageEvent) => {
      retryDelay.current = 1000
      try {
        const snapshot: Snapshot = JSON.parse(e.data)
        setState({ snapshot, connected: true, lastUpdate: Date.now() })
      } catch {
        // malformed JSON — ignore
      }
    })

    es.onerror = () => {
      setState(prev => ({ ...prev, connected: false }))
      es.close()
      if (!cancelledRef.current) {
        setTimeout(connect, retryDelay.current)
        retryDelay.current = Math.min(retryDelay.current * 2, 30_000)
      }
    }
  }, [url])

  useEffect(() => {
    cancelledRef.current = false
    connect()
    return () => {
      cancelledRef.current = true
      esRef.current?.close()
    }
  }, [connect])

  return state
}
