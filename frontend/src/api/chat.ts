import request from './request'
import type { ChatReq, ChatResp } from '@/types/api'
import type { ToolCallInfo } from '@/types/models'

export const sendChat = (data: ChatReq) =>
  request.post<unknown, ChatResp>('/api/chat', data)

export interface StreamHandlers {
  onMeta?: (data: { intent: string }) => void
  onToolCall?: (data: { name: string; args: Record<string, unknown> }) => void
  onToolResult?: (data: { name: string; result: string; ms: number }) => void
  onToken?: (data: { text: string }) => void
  onReset?: () => void
  onDone?: (data: { reply: string; tools: ToolCallInfo[] }) => void
  onError?: (data: { detail: string }) => void
}

export async function streamChat(data: ChatReq, handlers: StreamHandlers) {
  const token = localStorage.getItem('token')
  const resp = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(data),
  })
  if (!resp.ok || !resp.body) {
    throw new Error(`HTTP ${resp.status}`)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop() ?? ''
    for (const part of parts) {
      const lines = part.split('\n')
      const event = lines.find((l) => l.startsWith('event: '))?.slice(7)
      const dataLine = lines.find((l) => l.startsWith('data: '))?.slice(6)
      if (!event) continue
      const payload = dataLine ? JSON.parse(dataLine) : {}
      if (event === 'meta') handlers.onMeta?.(payload)
      else if (event === 'tool_call') handlers.onToolCall?.(payload)
      else if (event === 'tool_result') handlers.onToolResult?.(payload)
      else if (event === 'token') handlers.onToken?.(payload)
      else if (event === 'reset') handlers.onReset?.()
      else if (event === 'done') handlers.onDone?.(payload)
      else if (event === 'error') handlers.onError?.(payload)
    }
  }
}
