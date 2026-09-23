import request from './request'
import type { ServerStatus } from '@/types/models'

export const getServerStatus = () =>
  request.get<unknown, ServerStatus>('/api/server/status')
