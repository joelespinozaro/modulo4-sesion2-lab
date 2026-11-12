'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from './_lib/auth-context'
import { getSessions, getHistory, sendMessage, getErrorTypes, postFeedback, type HistoryItem, type ErrorType } from './_lib/api-client'
import ChatArea from './_components/ChatArea'

export default function HomePage() {
  const { user, token, loading, signOut } = useAuth()
  const router = useRouter()

  async function handleSignOut() {
    await signOut()
    router.push('/login')
  }

  const [sessions, setSessions] = useState<string[]>([])
  const [loadingSessions, setLoadingSessions] = useState(true)
  const [activeSession, setActiveSession] = useState<string | null>(null)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)

  const [inputValue, setInputValue] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [sessionRef, setSessionRef] = useState<string | null>(null)

  const [errorTypes, setErrorTypes] = useState<ErrorType[]>([])
  const [ratedItems, setRatedItems] = useState<Map<string, boolean>>(new Map())

  useEffect(() => {
    if (loading || !user || !token) return

    getSessions(user.email!, token)
      .then((data) => setSessions(data.sessions))
      .catch(() => setSessions([]))
      .finally(() => setLoadingSessions(false))

    getErrorTypes(token)
      .then(setErrorTypes)
      .catch(() => {})
  }, [loading, user, token])

  useEffect(() => {
    if (!activeSession || !token) {
      setHistory([])
      return
    }

    setLoadingHistory(true)
    setHistory([])

    getHistory(activeSession, token)
      .then((data) => {
        setHistory(data)
        const initialRatings = new Map<string, boolean>()
        for (const item of data) {
          if (item.is_ok !== null) initialRatings.set(item.trace_id, item.is_ok)
        }
        setRatedItems(initialRatings)
      })
      .catch(() => setHistory([]))
      .finally(() => setLoadingHistory(false))
  }, [activeSession, token])

  async function handleSend() {
    if (!inputValue.trim() || sending || !user || !token) return

    const question = inputValue.trim()
    setSending(true)
    setSendError(null)
    setInputValue('')

    const placeholder: HistoryItem = {
      question,
      answer: '',
      trace_id: '__pending__',
      session_id: sessionRef ?? '',
      user: user.email,
      created_at: new Date().toISOString(),
      is_ok: null,
    }
    setHistory((prev) => [...prev, placeholder])

    try {
      const response = await sendMessage(
        { question, user: user.email!, session_id: sessionRef ?? undefined },
        token,
      )

      const newItem: HistoryItem = {
        question,
        answer: response.answer,
        trace_id: response.trace_id,
        session_id: response.session_id,
        user: user.email,
        created_at: new Date().toISOString(),
        is_ok: null,
        sources: response.sources,
        files: response.files,
      }

      setHistory((prev) => [...prev.slice(0, -1), newItem])

      if (!sessionRef) {
        setSessionRef(response.session_id)
        setActiveSession(response.session_id)
        setSessions((prev) => [response.session_id, ...prev])
      }
    } catch (err: unknown) {
      setHistory((prev) => prev.slice(0, -1))
      const status = (err as { status?: number }).status
      if (status === 422) {
        setSendError('La pregunta no es válida. Revisá el formato e intentá de nuevo.')
      } else {
        setSendError('Error del servidor. Intentá de nuevo en unos momentos.')
      }
    } finally {
      setSending(false)
    }
  }

  function handleNewSession() {
    setActiveSession(null)
    setSessionRef(null)
    setHistory([])
    setInputValue('')
    setSendError(null)
  }

  async function handleFeedback(
    traceId: string,
    isOk: boolean,
    errorTypeId?: number,
    observations?: string,
  ): Promise<void> {
    await postFeedback({ trace_id: traceId, is_ok: isOk, error_type_id: errorTypeId, observations }, token!)
    setRatedItems((prev) => new Map(prev).set(traceId, isOk))
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50">
        <span className="text-sm text-zinc-500">Cargando…</span>
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-zinc-50">
      {/* Panel lateral */}
      <aside className="flex w-64 flex-col border-r border-zinc-200 bg-white">
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
          <span className="text-sm font-medium text-zinc-700">Conversaciones</span>
          <button
            onClick={handleNewSession}
            title="Nueva conversación"
            className="rounded-md p-1 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-700"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7" />
              <path d="M18.375 2.625a1 1 0 0 1 3 3l-9.75 9.75-4 1 1-4z" />
            </svg>
          </button>
        </div>

        <nav className="flex flex-1 flex-col overflow-y-auto p-2">
          {loadingSessions ? (
            <p className="px-2 py-3 text-xs text-zinc-400">Cargando sesiones…</p>
          ) : sessions.length === 0 ? (
            <p className="px-2 py-3 text-xs text-zinc-400">Sin conversaciones previas</p>
          ) : (
            sessions.map((sessionId) => (
              <button
                key={sessionId}
                onClick={() => { setActiveSession(sessionId); setSessionRef(sessionId) }}
                className={`w-full rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                  activeSession === sessionId
                    ? 'bg-zinc-100 text-zinc-900 font-medium'
                    : 'text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900'
                }`}
              >
                {sessionId.slice(0, 8)}…
              </button>
            ))
          )}
        </nav>

        <div className="border-t border-zinc-200 p-3">
          <p className="mb-2 truncate px-1 text-xs text-zinc-400">{user?.email}</p>
          <button
            onClick={handleSignOut}
            className="w-full rounded-lg px-3 py-2 text-left text-xs text-zinc-500 transition-colors hover:bg-zinc-50 hover:text-zinc-900"
          >
            Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Área de chat */}
      <main className="flex flex-1 flex-col overflow-hidden">
        <ChatArea
          history={history}
          loading={loadingHistory}
          activeSession={activeSession}
          errorTypes={errorTypes}
          ratedItems={ratedItems}
          onFeedback={handleFeedback}
        />

        <div className="border-t border-zinc-200 bg-white px-4 py-3">
          {sendError && (
            <p className="mb-2 text-xs text-red-600">{sendError}</p>
          )}
          <div className="flex gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              disabled={sending}
              placeholder="Escribí tu pregunta…"
              className="flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-500 focus:ring-2 focus:ring-zinc-200 disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={sending || !inputValue.trim()}
              className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50"
            >
              {sending ? '…' : 'Enviar'}
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}
