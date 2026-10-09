import { useCallback, useEffect, useRef, useState } from 'react'
import { getJson } from './api'

export const POLLING_REFRESH_EVENT = 'adflow:refresh-active-view'

export type PollingResult<T> = {
  data: T | null
  error: Error | null
  fetching: boolean
  stale: boolean
  lastSuccessAt: string | null
  refresh: () => Promise<void>
}

export function usePolling<T>(
  path: string,
  paused: boolean,
  intervalMs = 5_000,
  enabled = true,
): PollingResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [fetching, setFetching] = useState(false)
  const [lastSuccessAt, setLastSuccessAt] = useState<string | null>(null)
  const [hidden, setHidden] = useState(document.visibilityState === 'hidden')
  const inFlight = useRef(false)
  const activeController = useRef<AbortController | null>(null)

  const run = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    const controller = new AbortController()
    activeController.current = controller
    setFetching(true)
    try {
      const result = await getJson<T>(path, controller.signal)
      setData(result)
      setError(null)
      setLastSuccessAt(new Date().toISOString())
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === 'AbortError')) {
        setError(caught instanceof Error ? caught : new Error('Refresh failed.'))
      }
    } finally {
      if (activeController.current === controller) activeController.current = null
      inFlight.current = false
      setFetching(false)
    }
  }, [path])
  const refresh = useCallback(() => run(), [run])

  useEffect(() => {
    const onVisibilityChange = () => setHidden(document.visibilityState === 'hidden')
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => document.removeEventListener('visibilitychange', onVisibilityChange)
  }, [])

  useEffect(() => {
    const onManualRefresh = () => void run()
    window.addEventListener(POLLING_REFRESH_EVENT, onManualRefresh)
    return () => window.removeEventListener(POLLING_REFRESH_EVENT, onManualRefresh)
  }, [run])

  useEffect(() => {
    let disposed = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const schedule = () => {
      if (!disposed && enabled && !paused && !hidden) {
        timer = setTimeout(async () => {
          await run()
          schedule()
        }, intervalMs)
      }
    }

    if (enabled && !paused && !hidden) {
      void Promise.resolve()
        .then(() => (disposed ? undefined : run()))
        .then(schedule)
    }
    return () => {
      disposed = true
      if (timer) clearTimeout(timer)
      activeController.current?.abort()
    }
  }, [enabled, hidden, intervalMs, paused, run])

  return { data, error, fetching, stale: data !== null && error !== null, lastSuccessAt, refresh }
}
