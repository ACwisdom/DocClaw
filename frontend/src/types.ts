export interface Doctor {
  id: string
  name: string
  title: string
  department: string
  avatar: string
}

export interface Patient {
  id: string
  slug: string
  name: string
  gender: string
  age: number
  chief_complaint: string
  visit_type: 'first' | 'followup'
  status: 'waiting' | 'consulting' | 'completed'
  priority: 'urgent' | 'normal' | 'chronic'
  queue_order: number
  completed_exams: string
  key_notes: string
  first_visit_note: string
}

export interface PatientSummary {
  waiting: number
  consulting: number
  completed: number
  first_visit: number
  followup: number
}

export interface Skill {
  id: string
  doctor_id: string
  name: string
  description: string
  version: string
  mode: string
  input_desc: string
  output_desc: string
  system_prompt: string
  tags: string
  status: string
  task_type: 'realtime' | 'scheduled'
  enabled: boolean
  is_default: boolean
  rating: number
  usage_count: number
  review_count: number
  icon: string
  created_at: string
  published_to_store: boolean
  doctor_name: string
}

export interface SkillStats {
  enabled: number
  draft: number
  published: number
  default: number
}

export interface StoreSkill {
  id: string
  name: string
  author: string
  description: string
  category: string
  version: string
  tags: string
  install_count: number
  rating: number
  scenarios: string
  compatibility: string
  highlights: string
  publisher: string
  updated_at: string
  is_featured: boolean
  is_editors_choice: boolean
  clawhub_slug?: string | null
  source?: string
}

export interface MedicalRecordData {
  patient_name: string
  gender: string
  age: number
  chief_complaint: string
  present_illness: string
  past_history: string
  allergy_history: string
  physical_exam: string
  auxiliary_exams: string
  preliminary_diagnosis: string
  treatment_plan: string
  missing_fields?: string[]
  confidence_notes?: string
}

export type AgentTraceStepKind = 'tool_call' | 'tool_result' | 'subagent' | 'status' | 'context'

export interface AgentTraceStep {
  id: string
  kind: AgentTraceStepKind
  content: string
  tool_name?: string
  agent_source?: string
  detail?: string
  created_at: string
}

export interface Message {
  id: string
  patient_id: string
  role: string
  content: string
  message_type: string
  meta_json?: string
  structured_data?: MedicalRecordData
  validation_warnings?: string[]
  field_diffs?: FieldDiff[]
  streaming?: boolean
  status_text?: string
  agent_source?: string
  tool_name?: string
  agent_trace?: AgentTraceStep[]
  created_at: string
}

export interface FieldDiff {
  field: string
  label: string
  generated: string
  source_value: string
  status: 'matched' | 'inferred' | 'missing' | 'conflict'
  note?: string
}

export interface FollowUpTask {
  id: string
  plan_id: string
  title: string
  description: string
  scheduled_at: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  result: string
  executed_at: string | null
  patient_id?: string | null
  patient_name?: string | null
  plan_title?: string | null
}

export interface FollowUpPlan {
  id: string
  patient_id: string
  doctor_id: string
  title: string
  description: string
  skill_id: string | null
  status: string
  created_at: string
  tasks: FollowUpTask[]
}

export interface Notification {
  id: string
  title: string
  content: string
  is_read: boolean
  created_at: string
}

export type ConsultMode = 'skill' | 'agent'

export interface AgentInterrupt {
  interrupt_type: string
  thread_id: string
  patient_slug?: string
  draft_content?: string
  structured_data?: MedicalRecordData
  patient_id?: string
  title?: string
  description?: string
  tasks?: Array<{ title: string; description?: string; scheduled_at?: string }>
  action_requests?: unknown[]
  review_configs?: unknown[]
  interrupt_value?: unknown
}

export interface AgentStreamCallbacks {
  onToken?: (content: string, source: string) => void
  onToolCall?: (data: { tool_call_id: string; tool_name: string; source: string }) => void
  onToolResult?: (data: { tool_name: string; tool_call_id: string; text: string; source: string }) => void
  onSubagent?: (data: { tool_call_id: string; source: string }) => void
  onTraceStep?: (data: {
    kind: AgentTraceStepKind
    content: string
    detail?: string
    source?: string
  }) => void
  onInterrupt?: (data: AgentInterrupt) => void
  onDone?: (data: { thread_id: string; content: string; interrupted?: boolean }) => void
  onError?: (message: string) => void
  onThreadId?: (threadId: string) => void
}
