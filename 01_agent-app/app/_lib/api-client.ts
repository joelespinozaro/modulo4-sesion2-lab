const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8080'

async function apiFetch<T>(path: string, token: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...options?.headers,
    },
  })

  if (!res.ok) {
    throw Object.assign(new Error(`API error ${res.status}`), { status: res.status })
  }

  return res.json() as Promise<T>
}

export interface UserSessionsResponse {
  user: string
  sessions: string[]
}

export function getSessions(user: string, token: string): Promise<UserSessionsResponse> {
  return apiFetch<UserSessionsResponse>(`/api/sessions/${user}`, token)
}

export interface RetrievedContext {
  page_content: string
  metadata: Record<string, unknown>
  score: number
}

export interface SourceField {
  label: string
  value: string
}

// Una ficha estructurada dentro de una tool que devuelve varios resultados en una
// sola llamada (ej. search_superheroes: uno por cada personaje encontrado).
export interface SourceItem {
  title?: string | null
  image_url?: string | null
  // Algunos hosts de imágenes (ej. superherodb.com) bloquean el embed cross-origin;
  // cuando viene en true, se muestra un enlace en vez de un <img>.
  image_link_only?: boolean
  fields: SourceField[]
}

// Una cita de una tool que usó el agente para responder (Qdrant, PokeAPI,
// SuperheroAPI, Neon, etc).
// - `contexts` solo viene lleno para retrieve_documents (RAG).
// - `title`/`image_url`/`fields` vienen llenos para tools con una única ficha
//   estructurada (ej. get_pokemon, get_superhero).
// - `items` viene lleno para tools que devuelven varias fichas en una sola llamada
//   (ej. search_superheroes).
// - `content` es el fallback de texto plano para el resto de las tools.
export interface ToolSource {
  tool: string
  label: string
  input?: Record<string, unknown> | null
  content?: string | null
  title?: string | null
  image_url?: string | null
  image_link_only?: boolean
  fields: SourceField[]
  items: SourceItem[]
  contexts: RetrievedContext[]
}

// Un archivo generado por una tool (ej. generate_pptx) para descargar, no una cita.
// No se persiste en el historial: solo viaja en la respuesta del turno en que se
// generó, así que al recargar una sesión vieja no vuelve a aparecer.
export interface GeneratedFile {
  tool: string
  filename: string
  mime_type: string
  data_base64: string
}

export interface HistoryItem {
  question: string
  answer: string
  trace_id: string
  session_id: string
  user: string | null
  created_at: string
  is_ok: boolean | null
  sources?: ToolSource[] | null
  files?: GeneratedFile[] | null
}

export function getHistory(sessionId: string, token: string): Promise<HistoryItem[]> {
  return apiFetch<HistoryItem[]>(`/api/history/${sessionId}`, token)
}

export interface ChatRequest {
  question: string
  user: string
  session_id?: string
}

export interface ChatResponse {
  user: string
  answer: string
  session_id: string
  trace_id: string
  sources: ToolSource[]
  files: GeneratedFile[]
}

export function sendMessage(request: ChatRequest, token: string): Promise<ChatResponse> {
  return apiFetch<ChatResponse>('/api/chat', token, {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export interface ErrorType {
  id: number
  description: string
}

export function getErrorTypes(token: string): Promise<ErrorType[]> {
  return apiFetch<ErrorType[]>('/api/errors', token)
}

export interface FeedbackRequest {
  trace_id: string
  is_ok: boolean
  error_type_id?: number
  observations?: string
}

export interface FeedbackResponse {
  trace_id: string
  session_id: string
  question: string
  answer: string
  user: string | null
  created_at: string
  is_ok: boolean | null
  error_type_id: number | null
  observations: string | null
  sources?: ToolSource[] | null
  files?: GeneratedFile[] | null
}

export function postFeedback(request: FeedbackRequest, token: string): Promise<FeedbackResponse> {
  return apiFetch<FeedbackResponse>('/api/feedback', token, {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

