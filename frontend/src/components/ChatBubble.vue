<template>
  <div class="bubble-wrap" :class="role">
    <div class="avatar">{{ role === 'human' ? '我' : 'AI' }}</div>
    <div class="bubble">
      <div class="content">
        <template v-for="(block, idx) in blocks" :key="idx">
          <!-- 文本块：保留换行，行内支持加粗/代码 -->
          <p v-if="block.type === 'text'" class="text-block">
            <template v-for="(seg, sIdx) in block.segments" :key="sIdx">
              <strong v-if="seg.type === 'bold'">{{ seg.content }}</strong>
              <code v-else-if="seg.type === 'code'" class="inline-code">{{ seg.content }}</code>
              <span v-else>{{ seg.content }}</span>
            </template>
          </p>
          <!-- 表格块 -->
          <div v-else-if="block.type === 'table'" class="table-wrap">
            <table class="md-table">
              <thead>
                <tr>
                  <th
                    v-for="(h, hi) in block.headers"
                    :key="hi"
                    :style="{ textAlign: block.align[hi] }"
                  >{{ h }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in block.rows" :key="ri">
                  <td
                    v-for="(cell, ci) in row"
                    :key="ci"
                    :style="{ textAlign: block.align[ci] }"
                  >{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>
      <ToolLogPanel v-if="tools && tools.length" :tools="tools" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCallInfo } from '@/types/models'
import ToolLogPanel from './ToolLogPanel.vue'
import { parseMarkdown } from '@/utils/markdown'

const props = defineProps<{
  role: 'human' | 'ai'
  content: string
  tools?: ToolCallInfo[]
}>()

const blocks = computed(() => parseMarkdown(props.content))
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
  max-width: 75%;
  padding: 12px 16px;
  border-radius: var(--radius);
  line-height: 1.6;
  word-break: break-word;
}
.content {
  white-space: normal;
}

/* 文本块：段落间距 + 保留换行 */
.text-block {
  margin: 0 0 8px;
  white-space: pre-wrap;
  &:last-child {
    margin-bottom: 0;
  }
}

/* 行内代码 */
.inline-code {
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}
.human .inline-code {
  background: rgba(255, 255, 255, 0.2);
}

/* 表格容器：支持横向滚动 */
.table-wrap {
  overflow-x: auto;
  margin: 8px 0;
  border-radius: 6px;
  border: 1px solid var(--border-color);
}
.md-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 100%;
  background: #fff;

  th,
  td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-color);
    text-align: left;
    white-space: nowrap;
  }
  thead th {
    background: var(--brand-primary-light);
    color: var(--brand-primary);
    font-weight: 600;
    border-bottom: 2px solid var(--brand-primary);
  }
  tbody tr:last-child td {
    border-bottom: none;
  }
  tbody tr:hover {
    background: var(--brand-primary-light);
  }
}
</style>
