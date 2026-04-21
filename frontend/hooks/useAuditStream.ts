import { useEffect, useRef, useState } from 'react'
import { supabase } from '@/lib/api'
import type { AuditEvent } from '@/lib/api/types'

const RECONNECT_DELAY_MS = 3000
const MAX_RECONNECT_ATTEMPTS = 10

export function useAuditStream(jobId: string | null, endpoint: 'audit-stream' | 'evaluation-report' = 'audit-stream') {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)
  const lastEventIdRef = useRef<string | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!jobId) return

    let active = true

    const connect = async () => {
      if (!active) return
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }

      // Get JWT from Supabase client — EventSource can't send headers so we
      // pass the token as a query param; the backend accepts ?token= for SSE.
      const { data: { session } } = await supabase.auth.getSession()
      const accessToken = session?.access_token
      if (!accessToken) {
        setError('Not authenticated')
        return
      }

      const params = new URLSearchParams()
      params.set('token', accessToken)
      if (lastEventIdRef.current) {
        params.set('last_event_id', lastEventIdRef.current)
      }

      const url = `/api/v1/jobs/${jobId}/${endpoint}?${params.toString()}`
      const es = new EventSource(url)
      esRef.current = es

      es.onopen = () => {
        if (!active) return
        setConnected(true)
        setError(null)
        reconnectAttemptsRef.current = 0
      }

      es.onmessage = (ev) => {
        if (!active) return
        try {
          const event: AuditEvent = JSON.parse(ev.data)
          lastEventIdRef.current = event.id
          setEvents((prev) => {
            if (prev.some((e) => e.id === event.id)) return prev
            return [...prev, event]
          })
        } catch {
          // Ignore keepalive comments and parse errors
        }
      }

      es.onerror = () => {
        if (!active) return
        setConnected(false)
        es.close()
        esRef.current = null

        if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
          setError('Connection lost. Please refresh the page.')
          return
        }

        reconnectAttemptsRef.current += 1
        const delay = RECONNECT_DELAY_MS * Math.min(reconnectAttemptsRef.current, 5)
        reconnectTimerRef.current = setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      active = false
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
      setConnected(false)
    }
  }, [jobId, endpoint])

  const clearEvents = () => setEvents([])

  return { events, connected, error, clearEvents }
}
