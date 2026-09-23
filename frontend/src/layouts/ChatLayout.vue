<template>
  <div class="chat-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <SessionList
        :sessions="sessionStore.sessions"
        :current-id="sessionStore.currentId"
        @new="handleNewSession"
        @select="handleSelectSession"
        @delete="handleDeleteSession"
      />
    </aside>

    <!-- 主区 -->
    <main class="main">
      <header class="topbar">
        <span class="app-title">智能运维 Agent 平台</span>
        <div class="user-area">
          <el-dropdown @command="onCommand">
            <span class="username">
              {{ userStore.user?.username }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 实时设备状态 -->
      <ServerStatusPanel />

      <!-- 消息区 -->
      <div class="messages" ref="messagesEl">
        <div v-if="!sessionStore.currentId" class="welcome">
          <h2>欢迎使用智能运维 Agent</h2>
          <p>点击左侧「新对话」开始，支持天气查询、运维数据查询、故障诊断</p>
        </div>
        <ChatBubble
          v-for="(m, i) in chatStore.messages"
          :key="i"
          :role="m.role"
          :content="m.content"
          :tools="m.tools"
        />
        <div v-if="chatStore.loading" class="typing">AI 正在思考...</div>
      </div>

      <!-- 输入区 -->
      <ChatInput :loading="chatStore.loading" @send="handleSend" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useSessionStore } from '@/stores/session'
import { useChatStore } from '@/stores/chat'
import SessionList from '@/components/SessionList.vue'
import ChatBubble from '@/components/ChatBubble.vue'
import ChatInput from '@/components/ChatInput.vue'
import ServerStatusPanel from '@/components/ServerStatusPanel.vue'

const router = useRouter()
const userStore = useUserStore()
const sessionStore = useSessionStore()
const chatStore = useChatStore()

const messagesEl = ref<HTMLElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight
    }
  })
}

async function handleNewSession() {
  await sessionStore.newSession()
  chatStore.clear()
  scrollToBottom()
}

async function handleSelectSession(id: string) {
  sessionStore.selectSession(id)
  chatStore.clear()
  await chatStore.loadHistory(id)
  scrollToBottom()
}

async function handleDeleteSession(id: string) {
  const isCurrent = sessionStore.currentId === id
  await sessionStore.remove(id)
  if (isCurrent) {
    chatStore.clear()
  }
}

async function handleSend(text: string) {
  if (!sessionStore.currentId) {
    await handleNewSession()
  }
  await chatStore.send(sessionStore.currentId, text)
  scrollToBottom()
}

function onCommand(cmd: string) {
  if (cmd === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped lang="scss">
.chat-layout {
  display: flex;
  height: 100vh;
}
.sidebar {
  width: 260px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
  flex-shrink: 0;
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.topbar {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-color);
  background: #fff;
}
.app-title {
  font-size: 16px;
  font-weight: 600;
}
.username {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-secondary);
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #fff;
}
.welcome {
  text-align: center;
  margin-top: 100px;
  color: var(--text-secondary);
}
.typing {
  color: var(--text-secondary);
  font-size: 14px;
  padding: 8px 0;
}
</style>
