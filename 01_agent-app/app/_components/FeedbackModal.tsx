'use client'

import { useState } from 'react'
import type { ErrorType } from '../_lib/api-client'

interface FeedbackModalProps {
  traceId: string
  errorTypes: ErrorType[]
  onSubmit: (errorTypeId: number, observations: string) => Promise<void>
  onClose: () => void
}

export default function FeedbackModal({ errorTypes, onSubmit, onClose }: FeedbackModalProps) {
  const [selectedErrorTypeId, setSelectedErrorTypeId] = useState<number>(
    errorTypes[0]?.id ?? 0,
  )
  const [observations, setObservations] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  async function handleSubmit() {
    if (!selectedErrorTypeId) return
    setSubmitting(true)
    setApiError(null)
    try {
      await onSubmit(selectedErrorTypeId, observations)
      onClose()
    } catch (err) {
      if ((err as { status?: number }).status === 404) {
        setApiError('Esta respuesta ya no está disponible.')
      } else {
        setApiError('Error al enviar la calificación. Intentá de nuevo.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-sm font-semibold text-zinc-900">Calificar respuesta</h2>

        <div className="mb-3">
          <label className="mb-1 block text-xs font-medium text-zinc-700">
            Tipo de error
          </label>
          <select
            value={selectedErrorTypeId}
            onChange={(e) => setSelectedErrorTypeId(Number(e.target.value))}
            disabled={submitting}
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-500 focus:ring-2 focus:ring-zinc-200 disabled:opacity-50"
          >
            {errorTypes.map((et) => (
              <option key={et.id} value={et.id}>
                {et.description}
              </option>
            ))}
          </select>
        </div>

        <div className="mb-4">
          <label className="mb-1 block text-xs font-medium text-zinc-700">
            Observaciones
          </label>
          <textarea
            value={observations}
            onChange={(e) => setObservations(e.target.value)}
            disabled={submitting}
            rows={3}
            placeholder="Describí el problema con esta respuesta…"
            className="w-full resize-none rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-500 focus:ring-2 focus:ring-zinc-200 disabled:opacity-50"
          />
        </div>

        {apiError && (
          <p className="mb-3 text-xs text-red-600">{apiError}</p>
        )}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={submitting}
            className="rounded-lg px-4 py-2 text-sm text-zinc-600 transition-colors hover:bg-zinc-100 disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || !selectedErrorTypeId}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50"
          >
            {submitting ? 'Enviando…' : 'Enviar calificación'}
          </button>
        </div>
      </div>
    </div>
  )
}
