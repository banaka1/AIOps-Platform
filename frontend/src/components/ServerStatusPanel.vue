<template>
  <div class="status-panel">
    <div class="panel-header" @click="expanded = !expanded">
      <div class="title">
        <el-icon><Monitor /></el-icon>
        <span>实时设备状态</span>
        <span class="live-dot" />
        <span v-if="updatedAt" class="refresh-time">更新于 {{ updatedAt }}</span>
      </div>
      <el-icon class="arrow" :class="{ expanded }">
        <ArrowDown />
      </el-icon>
    </div>

    <transition name="slide">
      <div v-show="expanded" class="panel-body">
        <div v-if="error" class="state error">{{ error }}</div>
        <div v-else-if="!status" class="state">采集中...</div>
        <div v-else class="cards">
          <!-- 主机信息 -->
          <div class="card host-card">
            <div class="card-title">主机</div>
            <div class="host-name">{{ status.hostname }}</div>
            <div class="host-meta">{{ status.ip }}</div>
            <div class="host-meta">{{ status.os }}</div>
          </div>

          <!-- CPU -->
          <div class="card">
            <div class="card-title">
              CPU
              <span class="sub">{{ status.cpu_count }} 逻辑核</span>
            </div>
            <div class="metric-value" :style="{ color: levelColor(status.cpu_percent) }">
              {{ status.cpu_percent }}%
            </div>
            <div class="device-name" :title="status.cpu_model">{{ status.cpu_model }}</div>
            <el-progress
              class="bar"
              :percentage="status.cpu_percent"
              :color="levelColor(status.cpu_percent)"
              :stroke-width="6"
              :show-text="false"
            />
          </div>

          <!-- 内存 -->
          <div class="card">
            <div class="card-title">
              内存
              <span class="sub">{{ status.memory_used_gb }}GB / {{ status.memory_total_gb }}GB</span>
            </div>
            <div class="metric-value" :style="{ color: levelColor(status.memory_percent) }">
              {{ status.memory_percent }}%
            </div>
            <el-progress
              class="bar"
              :percentage="status.memory_percent"
              :color="levelColor(status.memory_percent)"
              :stroke-width="6"
              :show-text="false"
            />
          </div>

          <!-- 磁盘 -->
          <div class="card">
            <div class="card-title">
              磁盘
              <span class="sub">{{ status.disk_used_gb }}GB / {{ status.disk_total_gb }}GB</span>
            </div>
            <div class="metric-value" :style="{ color: levelColor(status.disk_percent) }">
              {{ status.disk_percent }}%
            </div>
            <el-progress
              class="bar"
              :percentage="status.disk_percent"
              :color="levelColor(status.disk_percent)"
              :stroke-width="6"
              :show-text="false"
            />
          </div>

          <!-- GPU（可能多块） -->
          <div v-for="(gpu, i) in status.gpus" :key="i" class="card gpu-card">
            <div class="card-title">
              GPU {{ i + 1 }}
              <span v-if="gpu.temp !== null" class="sub">{{ gpu.temp }}℃</span>
            </div>
            <div class="device-name" :title="gpu.name">{{ gpu.name }}</div>
            <template v-if="gpu.util !== null">
              <div class="metric-value" :style="{ color: levelColor(gpu.util) }">
                {{ gpu.util }}%
              </div>
              <div v-if="gpu.mem_total_bytes" class="host-meta">
                显存 {{ fmtGb(gpu.mem_used_bytes) }} / {{ fmtGb(gpu.mem_total_bytes) }}GB
              </div>
              <el-progress
                class="bar"
                :percentage="gpu.util"
                :color="levelColor(gpu.util)"
                :stroke-width="6"
                :show-text="false"
              />
            </template>
            <div v-else-if="gpu.mem_total_bytes" class="host-meta">
              显存 {{ fmtGb(gpu.mem_used_bytes) }} / {{ fmtGb(gpu.mem_total_bytes) }}GB（驱动不支持利用率查询）
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Monitor, ArrowDown } from '@element-plus/icons-vue'
import { getServerStatus } from '@/api/server'
import type { ServerStatus } from '@/types/models'

const expanded = ref(true)
const status = ref<ServerStatus | null>(null)
const error = ref('')
const updatedAt = ref('')
let timer: number | undefined

// 使用率分级配色：<70 正常绿，70~85 警告橙，>=85 危险红
function levelColor(p: number): string {
  if (p >= 85) return '#f56c6c'
  if (p >= 70) return '#e6a23c'
  return '#67c23a'
}

function fmtGb(bytes: number | null): string {
  return bytes === null ? '-' : (bytes / 1024 ** 3).toFixed(1)
}

async function refresh() {
  try {
    status.value = await getServerStatus()
    error.value = ''
    updatedAt.value = new Date().toLocaleTimeString()
  } catch {
    error.value = '实时状态采集失败，请检查后端服务'
  }
}

onMounted(() => {
  refresh()
  timer = window.setInterval(refresh, 5000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style scoped lang="scss">
.status-panel {
  background: #fafbfc;
  border-bottom: 1px solid var(--border-color);
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;

  &:hover {
    background: #f0f2f5;
  }
  .title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--text-primary);
    font-weight: 500;

    .el-icon {
      color: var(--brand-primary);
    }
    .live-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #67c23a;
      animation: blink 1.5s infinite;
    }
    .refresh-time {
      font-size: 11px;
      color: var(--text-secondary);
      font-weight: normal;
    }
  }
  .arrow {
    color: var(--text-secondary);
    transition: transform 0.2s;
    font-size: 14px;

    &.expanded {
      transform: rotate(180deg);
    }
  }
}
@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}
.panel-body {
  padding: 0 20px 12px;
}
.state {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 4px 0 8px;

  &.error {
    color: #f56c6c;
  }
}
.cards {
  display: flex;
  gap: 12px;
  overflow-x: auto;
}
.card {
  flex: 1;
  min-width: 170px;
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  transition: border-color 0.2s, box-shadow 0.2s;

  &:hover {
    border-color: var(--brand-primary);
    box-shadow: 0 2px 8px rgba(79, 124, 255, 0.12);
  }
  // 进度条统一锚定到卡片底部，保证各卡片进度条高度一致
  .bar {
    margin-top: auto;
  }
}
.host-card {
  min-width: 200px;
}
.card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-primary);
  margin-bottom: 4px;

  .sub {
    font-size: 11px;
    font-weight: normal;
    color: var(--text-secondary);
  }
}
.host-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.host-meta {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}
.device-name {
  font-size: 12px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}
.metric-value {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 6px;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 300px;
}
</style>
