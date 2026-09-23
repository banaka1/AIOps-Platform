// 用户/会话/消息实体类型

export interface UserInfo {
  user_id: number
  username: string
}

export interface SessionItem {
  id: string
  title: string
  updated_at: string
}

export interface MessageItem {
  role: 'human' | 'ai' | 'tool' | 'system'
  content: string
  ts: string
}

export interface ToolCallInfo {
  name: string
  args: Record<string, unknown>
  result: string
  ms: number
}

// 实时设备状态（GET /api/server/status）
export interface GpuStatus {
  name: string
  util: number | null
  mem_used_bytes: number | null
  mem_total_bytes: number | null
  temp: number | null
}

export interface ServerStatus {
  hostname: string
  ip: string
  os: string
  cpu_percent: number
  cpu_count: number
  cpu_model: string
  memory_percent: number
  memory_used_gb: number
  memory_total_gb: number
  disk_percent: number
  disk_used_gb: number
  disk_total_gb: number
  gpus: GpuStatus[]
}
