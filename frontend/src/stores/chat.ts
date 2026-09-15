import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MessageItem, ToolCallInfo } from '@/types/models'
import { getSessionMessages } from '@/api/session'
import { sendChat } from '@/api/chat'

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
    // 先追加用户消息
    messages.value.push({ role: 'human', content: text, ts: new Date().toLocaleString() })
    try {
      const resp = await sendChat({ session_id: sessionId, message: text })
      const reply = resp.reply && resp.reply.trim() ? resp.reply : '（AI 未返回有效内容，请重试）'
      messages.value.push({
        role: 'ai',
        content: reply,
        ts: new Date().toLocaleString(),
        tools: resp.tools,
      })
      return resp
    } catch (e) {
      // 请求失败时也推送一条 AI 错误消息，避免用户只看到"无响应"
      messages.value.push({
        role: 'ai',
        content: '请求失败，请检查网络或稍后重试。',
        ts: new Date().toLocaleString(),
      })
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
