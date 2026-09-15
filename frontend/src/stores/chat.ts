import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MessageItem, ToolCallInfo } from '@/types/models'
import { getSessionMessages } from '@/api/session'
import { streamChat } from '@/api/chat'

export interface ChatMessage {
  role: 'human' | 'ai'
  content: string
  ts: string
  tools?: ToolCallInfo[]
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)

  async function loadHistory(sessionId: string) {
    const list = await getSessionMessages(sessionId)
    // 只展示 human 和 ai 消息，tool 消息合并到对应 ai 的 tools 里
    messages.value = list
      .filter((m): m is MessageItem & { role: 'human' | 'ai' } => m.role === 'human' || m.role === 'ai')
      // 过滤掉 AI 空内容消息（工具决策轮产生的中间消息），避免出现空白气泡
      .filter((m) => m.role !== 'ai' || (m.content && m.content.trim()))
      .map((m) => ({ ...m }))
  }

  async function send(sessionId: string, text: string) {
    loading.value = true
    // 先追加用户消息与空白 ai 气泡，流式期间逐字填充
    messages.value.push({ role: 'human', content: text, ts: new Date().toLocaleString() })
    messages.value.push({ role: 'ai', content: '', ts: new Date().toLocaleString(), tools: [] })
    const aiMsg = messages.value[messages.value.length - 1]
    try {
      await streamChat({ session_id: sessionId, message: text }, {
        onToken: ({ text: t }) => {
          aiMsg.content += t
        },
        onReset: () => {
          aiMsg.content = ''
        },
        onToolCall: ({ name, args }) => {
          aiMsg.tools = [...(aiMsg.tools ?? []), { name, args, result: '', ms: 0 }]
        },
        onToolResult: ({ name, result, ms }) => {
          const list = aiMsg.tools ?? []
          const idx = list.findIndex((t) => t.name === name && !t.result)
          if (idx >= 0) list[idx] = { ...list[idx], result, ms }
          else list.push({ name, args: {}, result, ms })
          aiMsg.tools = [...list]
        },
        onDone: ({ reply, tools }) => {
          aiMsg.content = reply || aiMsg.content
          aiMsg.tools = tools
        },
        onError: ({ detail }) => {
          aiMsg.content = aiMsg.content || `请求失败：${detail}`
        },
      })
      if (!aiMsg.content.trim()) {
        aiMsg.content = '（AI 未返回有效内容，请重试）'
      }
      return null
    } catch (e) {
      aiMsg.content = aiMsg.content || '请求失败，请检查网络或稍后重试。'
      return null
    } finally {
      loading.value = false
    }
  }

  function clear() {
    messages.value = []
  }

  return { messages, loading, loadHistory, send, clear }
})
