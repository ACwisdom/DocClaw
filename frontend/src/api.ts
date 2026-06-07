import type {
  AgentInterrupt,
  AgentStreamCallbacks,
  AgentTraceStepKind,
  Doctor,
  FieldDiff,
  FollowUpPlan,
  FollowUpTask,
  MedicalRecordData,
  Message,
  Notification,
  Patient,
  PatientSummary,
  Skill,
  SkillStats,
  StoreSkill,
} from './types'

const BASE = '/api'
const AGENT_BASE = '/agent-api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '请求失败')
  }
  return res.json()
}

export const api = {
  getDoctor: () => request<Doctor>('/patients/doctor/me'),

  getPatients: (params?: { status?: string; visit_type?: string; search?: string }) => {
    const q = new URLSearchParams()
    if (params?.status) q.set('status', params.status)
    if (params?.visit_type) q.set('visit_type', params.visit_type)
    if (params?.search) q.set('search', params.search)
    const qs = q.toString()
    return request<Patient[]>(`/patients${qs ? `?${qs}` : ''}`)
  },

  getPatientSummary: () => request<PatientSummary>('/patients/summary'),
  getPatient: (slug: string) => request<Patient>(`/patients/${slug}`),
  startConsultation: (slug: string) => request<{ ok: boolean }>(`/patients/${slug}/start`, { method: 'POST' }),
  completeConsultation: (slug: string) => request<{ ok: boolean }>(`/patients/${slug}/complete`, { method: 'POST' }),

  getSkills: () => request<Skill[]>('/skills'),
  getSkillStats: () => request<SkillStats>('/skills/stats'),
  getSkill: (id: string) => request<Skill>(`/skills/${id}`),
  createSkill: (data: Partial<Skill>) => request<Skill>('/skills', { method: 'POST', body: JSON.stringify(data) }),
  updateSkill: (id: string, data: Partial<Skill>) => request<Skill>(`/skills/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  toggleSkill: (id: string) => request<{ enabled: boolean }>(`/skills/${id}/toggle`, { method: 'POST' }),
  publishSkill: (id: string) => request<{ ok: boolean }>(`/skills/${id}/publish`, { method: 'POST' }),
  deleteSkill: (id: string) => request<{ ok: boolean }>(`/skills/${id}`, { method: 'DELETE' }),

  getStoreSkills: (params?: { category?: string; search?: string }) => {
    const q = new URLSearchParams()
    if (params?.category) q.set('category', params.category)
    if (params?.search) q.set('search', params.search)
    const qs = q.toString()
    return request<StoreSkill[]>(`/store${qs ? `?${qs}` : ''}`)
  },
  getFeaturedSkill: () => request<StoreSkill>('/store/featured'),
  getStoreSkill: (id: string) => request<StoreSkill>(`/store/${id}`),
  installSkill: (id: string) => request<Skill>(`/store/${id}/install`, { method: 'POST' }),
  syncClawHubSkills: () =>
    request<{ imported: number; slugs: string[] }>('/store/sync-clawhub', { method: 'POST' }),

  getMessages: (slug: string) => request<Message[]>(`/consult/${slug}/messages`),
  sendMessage: (slug: string, content: string, skillId?: string) =>
    request<Message[]>(`/consult/${slug}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, skill_id: skillId }),
    }),

  sendMessageStream: async (
    slug: string,
    content: string,
    skillId: string | undefined,
    callbacks: {
      onDoctorMessage?: (msg: Message) => void
      onStatus?: (text: string) => void
      onChunk?: (delta: string) => void
      onStructured?: (data: {
        structured_data: MedicalRecordData
        validation_warnings?: string[]
        field_diffs?: FieldDiff[]
      }) => void
      onDone?: (msg: Message) => void
      onError?: (message: string, fallback?: boolean) => void
    },
  ) => {
    const res = await fetch(`${BASE}/consult/${slug}/messages/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, skill_id: skillId }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || '流式请求失败')
    }
    if (!res.body) {
      throw new Error('浏览器不支持流式响应')
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    const dispatchEvent = (event: string, dataStr: string) => {
      if (!dataStr) return
      const data = JSON.parse(dataStr)
      switch (event) {
        case 'doctor_message':
          callbacks.onDoctorMessage?.(data as Message)
          break
        case 'status':
          callbacks.onStatus?.(data.text as string)
          break
        case 'chunk':
          callbacks.onChunk?.(data.delta as string)
          break
        case 'structured':
          callbacks.onStructured?.(data as {
            structured_data: MedicalRecordData
            validation_warnings?: string[]
            field_diffs?: FieldDiff[]
          })
          break
        case 'done':
          callbacks.onDone?.(data as Message)
          break
        case 'error':
          callbacks.onError?.(data.message as string, data.fallback as boolean | undefined)
          break
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''
      for (const part of parts) {
        if (!part.trim()) continue
        let event = 'message'
        let dataStr = ''
        for (const line of part.split('\n')) {
          if (line.startsWith('event:')) {
            event = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            dataStr = line.slice(5).trim()
          }
        }
        if (dataStr) dispatchEvent(event, dataStr)
      }
    }
  },

  agentChatStream: async (
    params: {
      message: string
      threadId?: string
      patientSlug?: string
      patientName?: string
      patientGender?: string
      patientAge?: number
      patientChiefComplaint?: string
      doctorId?: string
      doctorName?: string
      department?: string
    },
    callbacks: AgentStreamCallbacks,
  ) => {
    const res = await fetch(`${AGENT_BASE}/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: params.message,
        thread_id: params.threadId,
        patient_slug: params.patientSlug,
        patient_name: params.patientName,
        patient_gender: params.patientGender,
        patient_age: params.patientAge,
        patient_chief_complaint: params.patientChiefComplaint,
        doctor_id: params.doctorId,
        doctor_name: params.doctorName,
        department: params.department,
      }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || '智能助理请求失败')
    }
    if (!res.body) {
      throw new Error('浏览器不支持流式响应')
    }
    await consumeAgentSseStream(res, callbacks)
  },

  agentResume: async (
    params: {
      threadId: string
      action: 'approve' | 'reject' | 'edit'
      payload?: Record<string, unknown>
    },
    callbacks: AgentStreamCallbacks,
  ) => {
    const res = await fetch(`${AGENT_BASE}/agent/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        thread_id: params.threadId,
        action: params.action,
        payload: params.payload,
      }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || '智能助理续接失败')
    }
    if (!res.body) {
      throw new Error('浏览器不支持流式响应')
    }
    await consumeAgentSseStream(res, callbacks)
  },

  getFollowUpPlans: (patientId?: string) => {
    const qs = patientId ? `?patient_id=${patientId}` : ''
    return request<FollowUpPlan[]>(`/followup${qs}`)
  },
  createFollowUpPlan: (data: object) =>
    request<FollowUpPlan>('/followup', { method: 'POST', body: JSON.stringify(data) }),
  updateFollowUpPlan: (planId: string, data: object) =>
    request<FollowUpPlan>(`/followup/plans/${planId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteFollowUpPlan: (planId: string) =>
    request<{ ok: boolean }>(`/followup/plans/${planId}`, { method: 'DELETE' }),
  addFollowUpTask: (planId: string, data: object) =>
    request<FollowUpTask>(`/followup/plans/${planId}/tasks`, { method: 'POST', body: JSON.stringify(data) }),
  updateFollowUpTask: (taskId: string, data: object) =>
    request<FollowUpTask>(`/followup/tasks/${taskId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteFollowUpTask: (taskId: string) =>
    request<{ ok: boolean }>(`/followup/tasks/${taskId}`, { method: 'DELETE' }),
  cancelFollowUpTask: (taskId: string) =>
    request<FollowUpTask>(`/followup/tasks/${taskId}/cancel`, { method: 'POST' }),
  getPendingTasks: () => request<FollowUpTask[]>('/followup/tasks/pending'),
  executeTask: (id: string, note?: string) =>
    request<{ ok: boolean; result: string }>(`/followup/tasks/${id}/execute`, {
      method: 'POST',
      body: JSON.stringify({ note: note || '' }),
    }),

  getNotifications: () => request<Notification[]>('/notifications'),
  markRead: (id: string) => request<{ ok: boolean }>(`/notifications/${id}/read`, { method: 'POST' }),
  markAllRead: () => request<{ ok: boolean }>('/notifications/read-all', { method: 'POST' }),
}

async function consumeAgentSseStream(res: Response, callbacks: AgentStreamCallbacks) {
  const threadHeader = res.headers.get('X-Thread-Id')
  if (threadHeader) {
    callbacks.onThreadId?.(threadHeader)
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (dataStr: string) => {
    if (!dataStr) return
    const data = JSON.parse(dataStr)
    switch (data.type) {
      case 'token':
        callbacks.onToken?.(data.content as string, (data.source as string) || 'main')
        break
      case 'tool_call':
        callbacks.onToolCall?.({
          tool_call_id: data.tool_call_id as string,
          tool_name: data.tool_name as string,
          source: (data.source as string) || 'main',
        })
        break
      case 'tool_result':
        callbacks.onToolResult?.({
          tool_name: data.tool_name as string,
          tool_call_id: data.tool_call_id as string,
          text: data.text as string,
          source: (data.source as string) || 'main',
        })
        break
      case 'subagent':
        callbacks.onSubagent?.({
          tool_call_id: data.tool_call_id as string,
          source: (data.source as string) || 'main',
        })
        break
      case 'trace_step':
        callbacks.onTraceStep?.({
          kind: (data.kind as AgentTraceStepKind) || 'context',
          content: (data.content as string) || '处理步骤',
          detail: data.detail as string | undefined,
          source: (data.source as string) || 'main',
        })
        break
      case 'interrupt':
        callbacks.onInterrupt?.(data as AgentInterrupt)
        break
      case 'done':
        callbacks.onDone?.({
          thread_id: data.thread_id as string,
          content: (data.content as string) || '',
          interrupted: data.interrupted as boolean | undefined,
        })
        if (data.thread_id) {
          callbacks.onThreadId?.(data.thread_id as string)
        }
        break
      case 'error':
        callbacks.onError?.(data.message as string)
        break
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      if (!part.trim()) continue
      let dataStr = ''
      for (const line of part.split('\n')) {
        if (line.startsWith('data:')) {
          dataStr = line.slice(5).trim()
        }
      }
      if (dataStr) dispatch(dataStr)
    }
  }
}
