<template>
  <div class="bubble-wrap" :class="role">
    <div class="avatar">{{ role === 'human' ? '我' : 'AI' }}</div>
    <div class="bubble">
      <div class="content">{{ content }}</div>
      <ToolLogPanel v-if="tools && tools.length" :tools="tools" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ToolCallInfo } from '@/types/models'
import ToolLogPanel from './ToolLogPanel.vue'

defineProps<{
  role: 'human' | 'ai'
  content: string
  tools?: ToolCallInfo[]
}>()
</script>

<style scoped lang="scss">
.bubble-wrap {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  align-items: flex-start;

  &.human {
    flex-direction: row-reverse;
    .bubble {
      background: var(--brand-primary);
      color: #fff;
    }
  }
  &.ai {
    .bubble {
      background: #f5f6f7;
      color: var(--text-primary);
    }
  }
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--brand-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
}
.bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: var(--radius);
  line-height: 1.6;
  word-break: break-word;
}
.content {
  white-space: pre-wrap;
}
</style>
