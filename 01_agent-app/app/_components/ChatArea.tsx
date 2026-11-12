'use client'

import { useEffect, useRef } from 'react'
import type { ErrorType, HistoryItem } from '../_lib/api-client'
import ChatMessage from './ChatMessage'

interface ChatAreaProps {
  history: HistoryItem[]
  loading: boolean
  activeSession: string | null
  errorTypes: ErrorType[]
  ratedItems: Map<string, boolean>
  onFeedback: (traceId: string, isOk: boolean, errorTypeId?: number, observations?: string) => Promise<void>
}

export default function ChatArea({ history, loading, activeSession, errorTypes, ratedItems, onFeedback }: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  const hasMessages = history.length > 0

  return (
    <div className="flex flex-1 flex-col overflow-y-auto px-4 py-4">
      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <span className="text-sm text-zinc-400">Cargando historial…</span>
        </div>
      ) : !hasMessages ? (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm text-zinc-400">
            {activeSession
              ? 'Esta sesión no tiene mensajes.'
              : 'Seleccioná una conversación o escribí tu primera pregunta.'}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {history.map((item) => (
            <ChatMessage
              key={item.trace_id}
              item={item}
              showFeedback={item.trace_id !== '__pending__'}
              rating={ratedItems.get(item.trace_id) ?? null}
              errorTypes={errorTypes}
              onFeedback={onFeedback}
            />
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}
