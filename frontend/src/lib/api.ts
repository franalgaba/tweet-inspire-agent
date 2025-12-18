const API_BASE = '/api'

// Types
export interface InspireRequest {
  username: string
  tweet_url?: string
  topic?: string
  content_type: string
  thread_count: number
  vibe?: string
  context?: string
  profile_file?: string
  deep_research: boolean
  use_full_content: boolean
}

export interface InspireResponse {
  original_tweet?: {
    text: string
    author_username?: string
    like_count?: number
    retweet_count?: number
    reply_count?: number
    created_at?: string
  }
  proposals: {
    quote?: Array<{ content: string | string[]; suggested_date?: string; based_on?: string[] }>
    tweet?: Array<{ content: string | string[]; suggested_date?: string; based_on?: string[] }>
    reply?: Array<{ content: string | string[]; suggested_date?: string; based_on?: string[] }>
    thread?: Array<{ content: string[]; suggested_date?: string; based_on?: string[] }>
  }
  research_id?: string
  prompt?: string
}

export interface RegenerateRequest {
  research_id: string
  content_type: string
  thread_count: number
  vibe?: string
  context?: string
  suggestions?: string
}

export interface RegenerateResponse {
  proposals: InspireResponse['proposals']
}

// Progress event from SSE stream
export interface ProgressEvent {
  step: string
  message: string
  progress?: number
  data?: InspireResponse
}

// API Error
class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

// Helper function
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`

  let response: Response

  try {
    response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })
  } catch (error) {
    // Network error (backend not running, CORS, etc.)
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ApiError(
        'Unable to connect to the server. Please make sure the backend is running.',
        0
      )
    }
    throw error
  }

  // Check if response has content before parsing JSON
  const contentType = response.headers.get('content-type')
  const hasJsonContent = contentType?.includes('application/json')
  const text = await response.text()

  let data: any
  if (hasJsonContent && text) {
    try {
      data = JSON.parse(text)
    } catch (parseError) {
      throw new ApiError(
        'Invalid response from server',
        response.status
      )
    }
  } else {
    // Non-JSON response or empty response
    data = text || {}
  }

  if (!response.ok) {
    throw new ApiError(
      data.detail || data.message || `Server error: ${response.statusText}`,
      response.status
    )
  }

  return data as T
}

/**
 * Inspire with streaming progress updates via SSE.
 * 
 * @param data - The inspire request data
 * @param onProgress - Callback for progress updates
 * @returns Promise that resolves with the final InspireResponse
 */
export async function inspireWithProgress(
  data: InspireRequest,
  onProgress: (event: ProgressEvent) => void
): Promise<InspireResponse> {
  const url = `${API_BASE}/inspire/stream`

  let response: Response

  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(data),
    })
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError(
        'Unable to connect to the server. Please make sure the backend is running.',
        0
      )
    }
    throw error
  }

  if (!response.ok) {
    const text = await response.text()
    let errorMessage = `Server error: ${response.statusText}`
    try {
      const errorData = JSON.parse(text)
      errorMessage = errorData.detail || errorData.message || errorMessage
    } catch {
      // Not JSON, use default message
    }
    throw new ApiError(errorMessage, response.status)
  }

  if (!response.body) {
    throw new ApiError('No response body received', 0)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult: InspireResponse | null = null

  try {
    while (true) {
      const { done, value } = await reader.read()

      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Process complete SSE events (separated by double newlines)
      const events = buffer.split('\n\n')
      buffer = events.pop() || '' // Keep incomplete event in buffer

      for (const event of events) {
        if (!event.trim()) continue

        // Parse SSE data line
        const dataMatch = event.match(/^data:\s*(.+)$/m)
        if (!dataMatch) continue

        try {
          const eventData: ProgressEvent = JSON.parse(dataMatch[1])

          // Call progress callback
          onProgress(eventData)

          // Check for error
          if (eventData.step === 'error') {
            throw new ApiError(eventData.message, 0)
          }

          // Check for completion
          if (eventData.step === 'complete' && eventData.data) {
            finalResult = eventData.data
          }
        } catch (parseError) {
          if (parseError instanceof ApiError) throw parseError
          console.warn('Failed to parse SSE event:', dataMatch[1])
        }
      }
    }
  } finally {
    reader.releaseLock()
  }

  if (!finalResult) {
    throw new ApiError('Stream ended without completing', 0)
  }

  return finalResult
}

// API Client
export const api = {
  // Inspire - generate content from a tweet (non-streaming)
  inspire: (data: InspireRequest): Promise<InspireResponse> =>
    request('/inspire', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Inspire with progress - streaming version
  inspireWithProgress,

  // Regenerate - regenerate content with different settings
  regenerate: (data: RegenerateRequest): Promise<RegenerateResponse> =>
    request('/inspire/regenerate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}
