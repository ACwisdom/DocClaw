import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'

import { Link, useParams } from 'react-router-dom'

import { api } from '../api'

import InterruptBanner from '../components/InterruptBanner'

import AgentTracePanel from '../components/AgentTracePanel'

import CopyMessageButton from '../components/CopyMessageButton'

import {
  friendlyAgentError,
  subagentLabel,
  SUBAGENT_LABELS,
  toolCallLabel,
  toolResultLabel,
} from '../utils/agentLabels'
import { formatMarkdown } from '../utils/markdownFormat'
import { appendAgentContent, getAgentVisibleContent } from '../utils/agentContentFilter'
import { appendAgentTraceStep, finalizeAgentTrace } from '../utils/agentTrace'

import type {

  AgentInterrupt,

  AgentTraceStep,

  ConsultMode,

  Doctor,

  FieldDiff,

  MedicalRecordData,

  Message,

  Patient,

  Skill,

} from '../types'



const TYPE_LABEL: Record<string, string> = { first: '初诊', followup: '复诊' }

const PRIORITY_LABEL: Record<string, string> = { urgent: '急需评估', normal: '普通门诊', chronic: '慢病复诊' }



function threadStorageKey(slug: string) {

  return `docclaw-agent-thread-${slug}`

}



function agentPatientPayload(patient: Patient | null, slug: string | undefined) {
  if (!slug) return {}
  if (!patient) return { patient_slug: slug }
  return {
    patient_slug: slug,
    patient_name: patient.name,
    patient_gender: patient.gender,
    patient_age: patient.age,
    patient_chief_complaint: patient.chief_complaint,
  }
}



function alignMedicalRecordIdentity(
  data: MedicalRecordData,
  patient: Patient,
): MedicalRecordData {
  return {
    ...data,
    patient_name: patient.name,
    gender: patient.gender,
    age: patient.age,
  }
}



export default function ConsultPage() {

  const { slug } = useParams<{ slug: string }>()

  const [patient, setPatient] = useState<Patient | null>(null)

  const [doctor, setDoctor] = useState<Doctor | null>(null)

  const [messages, setMessages] = useState<Message[]>([])

  const [agentMessages, setAgentMessages] = useState<Message[]>([])

  const [skills, setSkills] = useState<Skill[]>([])

  const [input, setInput] = useState('')

  const [sending, setSending] = useState(false)

  const [resuming, setResuming] = useState(false)

  const [activeSkillId, setActiveSkillId] = useState<string | undefined>()

  const [consultMode, setConsultMode] = useState<ConsultMode>('skill')

  const [threadId, setThreadId] = useState<string | undefined>()

  const [pendingInterrupt, setPendingInterrupt] = useState<AgentInterrupt | null>(null)

  const [expandedTraces, setExpandedTraces] = useState<Set<string>>(new Set())

  const chatMessagesRef = useRef<HTMLDivElement>(null)



  useEffect(() => {

    if (!slug) return

    const storedThread = sessionStorage.getItem(threadStorageKey(slug)) ?? undefined

    setThreadId(storedThread || undefined)



    Promise.all([

      api.getPatient(slug),

      api.getMessages(slug),

      api.getSkills(),

      api.getDoctor(),

      api.startConsultation(slug),

    ]).then(([p, m, s, d]) => {

      setPatient(p)

      setMessages(

        m.map((msg) =>

          msg.message_type === 'medical_record' && msg.structured_data

            ? { ...msg, structured_data: alignMedicalRecordIdentity(msg.structured_data, p) }

            : msg,

        ),

      )

      setDoctor(d)

      setSkills(s.filter((sk) => sk.enabled))

      const defaultSkill = s.find((sk) => sk.is_default)

      if (defaultSkill) setActiveSkillId(defaultSkill.id)

    }).catch(console.error)

  }, [slug])



  const toggleTrace = useCallback((messageId: string) => {

    setExpandedTraces((prev) => {

      const next = new Set(prev)

      if (next.has(messageId)) next.delete(messageId)

      else next.add(messageId)

      return next

    })

  }, [])



  useLayoutEffect(() => {

    const el = chatMessagesRef.current

    if (!el) return

    el.scrollTop = el.scrollHeight

  }, [messages, agentMessages, pendingInterrupt, consultMode])



  const persistThreadId = useCallback((id: string) => {

    setThreadId(id)

    if (slug) sessionStorage.setItem(threadStorageKey(slug), id)

  }, [slug])



  const switchMode = (mode: ConsultMode) => {

    if (mode === consultMode) return

    setConsultMode(mode)

    setPendingInterrupt(null)

    if (mode === 'skill' && slug) {

      api.getMessages(slug).then(setMessages).catch(console.error)

    }

  }



  const handleSend = async () => {

    if (!slug || !input.trim() || sending) return

    if (consultMode === 'agent') {

      await handleAgentSend()

      return

    }

    await handleSkillSend()

  }



  const handleSkillSend = async () => {

    if (!slug || !input.trim() || sending) return

    const content = input.trim()

    setSending(true)

    setInput('')



    const tempDoctorId = `temp-doctor-${Date.now()}`

    const tempAssistantId = `temp-assistant-${Date.now()}`

    const optimisticDoctor: Message = {

      id: tempDoctorId,

      patient_id: patient?.id ?? '',

      role: 'doctor',

      content,

      message_type: 'text',

      created_at: new Date().toISOString(),

    }

    const assistantPlaceholder: Message = {

      id: tempAssistantId,

      patient_id: patient?.id ?? '',

      role: 'assistant',

      content: '',

      message_type: 'text',

      streaming: true,

      created_at: new Date().toISOString(),

    }

    setMessages((prev) => [...prev, optimisticDoctor, assistantPlaceholder])



    let resolvedDoctor: Message | null = null



    const updateAssistant = (patch: Partial<Message>) => {

      setMessages((prev) =>

        prev.map((msg) => (msg.id === tempAssistantId ? { ...msg, ...patch } : msg)),

      )

    }



    const finalizeMessages = (doctorMsg: Message, aiMsg: Message) => {

      setMessages((prev) =>

        prev.map((msg) => {

          if (msg.id === tempDoctorId || (resolvedDoctor && msg.id === resolvedDoctor.id)) {

            return doctorMsg

          }

          if (msg.id === tempAssistantId) {

            return { ...aiMsg, streaming: false }

          }

          return msg

        }),

      )

    }



    try {

      await api.sendMessageStream(slug!, content, activeSkillId, {

        onDoctorMessage: (doctorMsg) => {

          resolvedDoctor = doctorMsg

          setMessages((prev) =>

            prev.map((msg) => (msg.id === tempDoctorId ? doctorMsg : msg)),

          )

        },

        onStatus: (text) => {

          updateAssistant({ status_text: text, content: text })

        },

        onChunk: (delta) => {

          setMessages((prev) =>

            prev.map((msg) =>

              msg.id === tempAssistantId

                ? { ...msg, content: `${msg.content}${delta}`, status_text: undefined }

                : msg,

            ),

          )

        },

        onStructured: ({ structured_data, validation_warnings, field_diffs }) => {

          updateAssistant({

            message_type: 'medical_record',

            structured_data: patient

              ? alignMedicalRecordIdentity(structured_data, patient)

              : structured_data,

            validation_warnings,

            field_diffs,

            content: '正在整理病历...',

          })

        },

        onDone: (aiMsg) => {

          const doctorMsg =

            resolvedDoctor ??

            ({

              ...optimisticDoctor,

              id: tempDoctorId,

            } as Message)

          const normalizedAiMsg =

            aiMsg.structured_data && patient

              ? {

                  ...aiMsg,

                  structured_data: alignMedicalRecordIdentity(aiMsg.structured_data, patient),

                }

              : aiMsg

          finalizeMessages(doctorMsg, normalizedAiMsg)

        },

        onError: (message, fallback) => {

          console.error(message)

          if (fallback) throw new Error(message)

        },

      })

    } catch (e) {

      console.error(e)

      setMessages((prev) => prev.filter((m) => m.id !== tempDoctorId && m.id !== tempAssistantId))

      try {

        const newMsgs = await api.sendMessage(slug!, content, activeSkillId)

        setMessages((prev) => [...prev, ...newMsgs])

      } catch (fallbackErr) {

        console.error(fallbackErr)

      }

    } finally {

      setSending(false)

    }

  }



  const handleAgentSend = async () => {

    if (!slug || !input.trim() || sending) return

    const content = input.trim()

    setSending(true)

    setInput('')

    setPendingInterrupt(null)



    const tempDoctorId = `agent-doctor-${Date.now()}`

    const tempAssistantId = `agent-assistant-${Date.now()}`

    const optimisticDoctor: Message = {

      id: tempDoctorId,

      patient_id: patient?.id ?? '',

      role: 'doctor',

      content,

      message_type: 'text',

      created_at: new Date().toISOString(),

    }

    const assistantPlaceholder: Message = {

      id: tempAssistantId,

      patient_id: patient?.id ?? '',

      role: 'assistant',

      content: '',

      message_type: 'text',

      streaming: true,

      created_at: new Date().toISOString(),

    }

    flushSync(() => {
      setAgentMessages((prev) => [...prev, optimisticDoctor, assistantPlaceholder])
    })

    const updateAssistant = (patch: Partial<Message>) => {

      setAgentMessages((prev) =>

        prev.map((msg) => (msg.id === tempAssistantId ? { ...msg, ...patch } : msg)),

      )

    }

    const appendTrace = (step: Omit<AgentTraceStep, 'id' | 'created_at'>) => {
      appendAgentTraceStep(setAgentMessages, tempAssistantId, step)
    }



    const patientCtx = agentPatientPayload(patient, slug)



    try {

      await api.agentChatStream(

        {

          message: content,

          threadId,

          patientSlug: patientCtx.patient_slug as string | undefined,

          patientName: patientCtx.patient_name as string | undefined,

          patientGender: patientCtx.patient_gender as string | undefined,

          patientAge: patientCtx.patient_age as number | undefined,

          patientChiefComplaint: patientCtx.patient_chief_complaint as string | undefined,

          doctorId: doctor?.id,

          doctorName: doctor?.name,

          department: doctor?.department,

        },

        {

          onThreadId: persistThreadId,

          onToken: (token, source) => {

            setAgentMessages((prev) =>

              prev.map((msg) =>

                msg.id === tempAssistantId

                  ? {

                      ...msg,

                      content: appendAgentContent(msg.content, token),

                      status_text: undefined,

                      agent_source: source,

                    }

                  : msg,

              ),

            )

          },

          onTraceStep: ({ kind, content, detail, source }) => {

            appendTrace({

              kind,

              content,

              detail,

              agent_source: source,

            })

          },

          onToolCall: ({ tool_name, source }) => {

            updateAssistant({

              status_text: toolCallLabel(tool_name),

              agent_source: source,

            })

            appendTrace({

              kind: 'tool_call',

              content: toolCallLabel(tool_name),

              tool_name,

              agent_source: source,

            })

          },

          onToolResult: ({ tool_name, text, source }) => {

            updateAssistant({ status_text: undefined })

            appendTrace({

              kind: 'tool_result',

              content: toolResultLabel(tool_name),

              tool_name,

              agent_source: source,

              detail: text,

            })

          },

          onSubagent: ({ source }) => {

            appendTrace({

              kind: 'subagent',

              content: subagentLabel(source),

              agent_source: source,

            })

          },

          onInterrupt: (interrupt) => {

            setPendingInterrupt(interrupt)

            setAgentMessages((prev) =>

              prev.map((msg) =>

                msg.id === tempAssistantId

                  ? {

                      ...msg,

                      streaming: false,

                      status_text: undefined,

                      content: msg.content || '等待医生确认...',

                    }

                  : msg,

              ),

            )

          },

          onDone: ({ thread_id, interrupted }) => {

            if (thread_id) persistThreadId(thread_id)

            if (!interrupted) {
              finalizeAgentTrace(setAgentMessages, tempAssistantId)
            }

          },

          onError: (message) => {

            updateAssistant({

              streaming: false,

              content: friendlyAgentError(message),

              status_text: undefined,

            })

          },

        },

      )

    } catch (e) {

      console.error(e)

      updateAssistant({

        streaming: false,

        content: friendlyAgentError(e instanceof Error ? e.message : '未知错误'),

        status_text: undefined,

      })

    } finally {

      setSending(false)

    }

  }



  const handleAgentResume = async (

    action: 'approve' | 'reject' | 'edit',

    payload?: Record<string, unknown>,

  ) => {

    const activeThread = pendingInterrupt?.thread_id ?? threadId

    if (!activeThread || resuming) return



    setResuming(true)

    setPendingInterrupt(null)



    const tempAssistantId = `agent-resume-${Date.now()}`

    const assistantPlaceholder: Message = {

      id: tempAssistantId,

      patient_id: patient?.id ?? '',

      role: 'assistant',

      content: '',

      message_type: 'text',

      streaming: true,

      status_text: action === 'reject' ? '已拒绝，继续处理…' : '已确认，继续执行…',

      created_at: new Date().toISOString(),

    }

    flushSync(() => {
      setAgentMessages((prev) => [...prev, assistantPlaceholder])
    })

    const updateAssistant = (patch: Partial<Message>) => {

      setAgentMessages((prev) =>

        prev.map((msg) => (msg.id === tempAssistantId ? { ...msg, ...patch } : msg)),

      )

    }

    const appendTrace = (step: Omit<AgentTraceStep, 'id' | 'created_at'>) => {
      appendAgentTraceStep(setAgentMessages, tempAssistantId, step)
    }



    const resumePayload: Record<string, unknown> = {

      ...payload,

      ...agentPatientPayload(patient, slug),

      doctor_id: doctor?.id,

      doctor_name: doctor?.name,

      department: doctor?.department,

    }



    try {

      await api.agentResume(

        { threadId: activeThread, action, payload: resumePayload },

        {

          onThreadId: persistThreadId,

          onToken: (token, source) => {

            setAgentMessages((prev) =>

              prev.map((msg) =>

                msg.id === tempAssistantId

                  ? {

                      ...msg,

                      content: appendAgentContent(msg.content, token),

                      status_text: undefined,

                      agent_source: source,

                    }

                  : msg,

              ),

            )

          },

          onTraceStep: ({ kind, content, detail, source }) => {

            appendTrace({

              kind,

              content,

              detail,

              agent_source: source,

            })

          },

          onToolCall: ({ tool_name, source }) => {

            updateAssistant({ status_text: toolCallLabel(tool_name), agent_source: source })

            appendTrace({

              kind: 'tool_call',

              content: toolCallLabel(tool_name),

              tool_name,

              agent_source: source,

            })

          },

          onToolResult: ({ tool_name, text, source }) => {

            updateAssistant({ status_text: undefined })

            appendTrace({

              kind: 'tool_result',

              content: toolResultLabel(tool_name),

              tool_name,

              agent_source: source,

              detail: text,

            })

          },

          onSubagent: ({ source }) => {

            appendTrace({

              kind: 'subagent',

              content: subagentLabel(source),

              agent_source: source,

            })

          },

          onInterrupt: (interrupt) => {

            setPendingInterrupt(interrupt)

            updateAssistant({ streaming: false, status_text: undefined })

          },

          onDone: ({ thread_id, interrupted }) => {

            if (thread_id) persistThreadId(thread_id)

            if (!interrupted) {
              finalizeAgentTrace(setAgentMessages, tempAssistantId, { status_text: undefined })
            }

          },

          onError: (message) => {

            updateAssistant({

              streaming: false,

              content: friendlyAgentError(message),

              status_text: undefined,

            })

          },

        },

      )

    } catch (e) {

      console.error(e)

      updateAssistant({

        streaming: false,

        content: friendlyAgentError(e instanceof Error ? e.message : '未知错误'),

        status_text: undefined,

      })

    } finally {

      setResuming(false)

    }

  }



  const handleComplete = async () => {

    if (!slug) return

    await api.completeConsultation(slug)

    window.location.href = '/queue'

  }



  if (!patient) return <div className="med-page"><div className="page-body loading">加载中...</div></div>



  const displayMessages = consultMode === 'skill'

    ? messages

    : agentMessages.filter((m) => m.message_type !== 'agent_tool')



  return (

    <div className="med-page consult-page">

      <header className="consult-header">

        <Link to="/queue" className="back-link">

          <span className="material-symbols-outlined">arrow_back_ios_new</span>

          返回队列

        </Link>

        <div className="consult-title-block">

          <h1>{patient.name} 的门诊问诊</h1>

          <div className="consult-tags">

            <span className={`tag tag-${patient.visit_type}`}>{TYPE_LABEL[patient.visit_type]}</span>

            <span className="tag tag-consulting">问诊中</span>

            <span className={`tag tag-priority-${patient.priority}`}>{PRIORITY_LABEL[patient.priority]}</span>

          </div>

          <span className="consult-meta">{patient.gender} · {patient.age} 岁</span>

        </div>

        <div className="consult-header-actions">

          <Link to={`/followup?patient=${patient.id}`} className="secondary-button">

            <span className="material-symbols-outlined">event_note</span>

            随访计划

          </Link>

          <button className="danger-button" onClick={handleComplete}>结束问诊</button>

        </div>

      </header>



      <div className="consult-layout">

        <div className="consult-chat">

          <div className="consult-mode-bar">

            <div className="consult-mode-toggle">

              <button

                type="button"

                className={consultMode === 'skill' ? 'active' : ''}

                onClick={() => switchMode('skill')}

              >

                <span className="material-symbols-outlined">bolt</span>

                看诊辅助

              </button>

              <button

                type="button"

                className={consultMode === 'agent' ? 'active' : ''}

                onClick={() => switchMode('agent')}

              >

                <span className="material-symbols-outlined">smart_toy</span>

                智能助理

              </button>

            </div>

          </div>



          {pendingInterrupt && consultMode === 'agent' && (

            <InterruptBanner

              interrupt={pendingInterrupt}

              patient={patient}

              loading={resuming}

              onApprove={(payload) => handleAgentResume('approve', payload)}

              onReject={() => handleAgentResume('reject')}

              onEdit={(payload) => handleAgentResume('edit', payload)}

            />

          )}



          <div className="chat-messages" ref={chatMessagesRef}>

            {displayMessages.map((msg) => {

              const isAgentAssistant = consultMode === 'agent' && msg.role === 'assistant'

              const visibleContent = isAgentAssistant

                ? getAgentVisibleContent(msg.content)

                : msg.content

              const showTrace = isAgentAssistant && (
                (msg.agent_trace?.length ?? 0) > 0 ||
                !!msg.status_text ||
                !!msg.streaming
              )

              const showAnswerBubble = !isAgentAssistant || !!visibleContent.trim()

              const copyText = isAgentAssistant

                ? visibleContent

                : getMessageCopyText(msg, patient)



              return (

              <div

                key={msg.id}

                className={`chat-turn${isAgentAssistant ? ' chat-turn-agent' : ''}`}

              >

                {showTrace && (

                  <AgentTracePanel

                    steps={msg.agent_trace ?? []}

                    streaming={msg.streaming}

                    statusText={msg.status_text}

                    expanded={expandedTraces.has(msg.id)}

                    onToggle={() => toggleTrace(msg.id)}

                  />

                )}

                {showAnswerBubble && (

              <div

                className={`chat-bubble chat-${msg.role} chat-type-${msg.message_type}${msg.streaming ? ' chat-streaming' : ''}`}

              >

                {msg.message_type === 'medical_record' && msg.structured_data ? (

                  <MedicalRecordCard

                    data={msg.structured_data}

                    patient={patient}

                    warnings={msg.validation_warnings}

                    fieldDiffs={msg.field_diffs}

                  />

                ) : msg.streaming && msg.status_text && !isAgentAssistant ? (

                  <div className="streaming-status">

                    <span className="streaming-spinner" />

                    {msg.status_text}

                    {msg.agent_source && msg.agent_source !== 'main' && (

                      <span className="agent-source-badge inline">

                        {SUBAGENT_LABELS[msg.agent_source] ?? msg.agent_source}

                      </span>

                    )}

                  </div>

                ) : msg.message_type === 'analysis' ? (

                  <div className="analysis-card" dangerouslySetInnerHTML={{ __html: formatMarkdown(msg.content) }} />

                ) : (

                  <>

                    {msg.agent_source && msg.agent_source !== 'main' && consultMode === 'agent' && !showTrace && (

                      <span className="agent-source-badge">

                        {SUBAGENT_LABELS[msg.agent_source] ?? msg.agent_source}

                      </span>

                    )}

                    <div className={msg.streaming ? 'streaming-text' : undefined} dangerouslySetInnerHTML={{ __html: formatMarkdown(visibleContent) }} />

                  </>

                )}

                {msg.streaming && !msg.status_text && msg.message_type !== 'medical_record' && (

                  <span className="streaming-cursor" />

                )}

                {msg.role !== 'system' && copyText.trim() && (

                  <CopyMessageButton text={copyText} />

                )}

              </div>

                )}

              </div>

            )})}

          </div>



          {consultMode === 'skill' && (

            <div className="skill-selector">

              {skills.map((s) => (

                <button

                  key={s.id}

                  className={`skill-chip${activeSkillId === s.id ? ' active' : ''}`}

                  onClick={() => setActiveSkillId(s.id)}

                >

                  <span className="material-symbols-outlined">{s.icon}</span>

                  {s.name}

                </button>

              ))}

            </div>

          )}



          <div className="chat-input-bar">

            <button className="icon-btn" title="上传附件">

              <span className="material-symbols-outlined">add_circle</span>

            </button>

            <textarea

              placeholder={

                consultMode === 'skill'

                  ? '输入本轮问诊内容或医生追问...'

                  : '可下达复杂分析、随访编排等任务…'

              }

              value={input}

              onChange={(e) => setInput(e.target.value)}

              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}

              rows={2}

            />

            <button className="icon-btn" title="开始录音">

              <span className="material-symbols-outlined">mic</span>

            </button>

            <button

              className="primary-button"

              onClick={handleSend}

              disabled={sending || resuming || !!pendingInterrupt || !input.trim()}

            >

              {consultMode === 'agent' ? '发送' : '发送消息'}

            </button>

          </div>

        </div>



        <aside className="consult-summary">

          <h2>接诊摘要</h2>

          <section>

            <h4>患者情况</h4>

            <p>{patient.name}，{patient.gender}，{patient.age}岁。主诉：{patient.chief_complaint}</p>

          </section>

          {patient.completed_exams && (

            <section>

              <h4>已完成检查</h4>

              <p>{patient.completed_exams}</p>

            </section>

          )}

          {patient.key_notes && (

            <section>

              <h4>重点提示</h4>

              <p>{patient.key_notes}</p>

            </section>

          )}

          {patient.first_visit_note && (

            <section>

              <h4>初诊说明</h4>

              <p>{patient.first_visit_note}</p>

            </section>

          )}

        </aside>

      </div>

    </div>

  )

}



const RECORD_FIELDS: { key: keyof MedicalRecordData; label: string }[] = [

  { key: 'chief_complaint', label: '主诉' },

  { key: 'present_illness', label: '现病史' },

  { key: 'past_history', label: '既往史' },

  { key: 'allergy_history', label: '过敏史' },

  { key: 'physical_exam', label: '查体' },

  { key: 'auxiliary_exams', label: '辅助检查' },

  { key: 'preliminary_diagnosis', label: '初步诊断' },

  { key: 'treatment_plan', label: '处理意见' },

]



function getMessageCopyText(msg: Message, patient?: Patient | null): string {
  if (msg.message_type === 'medical_record' && msg.structured_data) {
    return formatMedicalRecordPlainText(msg.structured_data, patient)
  }
  return msg.content
}



function formatMedicalRecordPlainText(data: MedicalRecordData, patient?: Patient | null): string {
  const displayName = patient?.name ?? data.patient_name
  const displayGender = patient?.gender ?? data.gender
  const displayAge = patient?.age ?? data.age
  const lines = [
    '门诊病历',
    `${displayName} · ${displayGender} · ${displayAge}岁`,
    '',
    ...RECORD_FIELDS.map(({ key, label }) => `${label}：${String(data[key] ?? '待补充')}`),
  ]
  if (data.missing_fields?.length) {
    lines.push('', `缺项字段：${data.missing_fields.join('、')}`)
  }
  if (data.confidence_notes) {
    lines.push('', data.confidence_notes)
  }
  return lines.join('\n')
}



function MedicalRecordCard({

  data,

  patient,

  warnings = [],

  fieldDiffs = [],

}: {

  data: MedicalRecordData

  patient?: Patient | null

  warnings?: string[]

  fieldDiffs?: FieldDiff[]

}) {

  const missing = data.missing_fields ?? []

  const diffByField = new Map(fieldDiffs.map((d) => [d.field, d]))

  const displayName = patient?.name ?? data.patient_name

  const displayGender = patient?.gender ?? data.gender

  const displayAge = patient?.age ?? data.age



  const renderDiffBadge = (fieldKey: string) => {

    const diff = diffByField.get(fieldKey)

    if (!diff) return null

    const badgeClass = `diff-badge diff-${diff.status}`

    const labels: Record<FieldDiff['status'], string> = {

      matched: '已匹配',

      inferred: '待核实',

      missing: '待补充',

      conflict: '冲突',

    }

    return (

      <span

        className={badgeClass}

        title={[diff.source_value, diff.note].filter(Boolean).join(' · ')}

      >

        {labels[diff.status]}

      </span>

    )

  }



  return (

    <div className="medical-record-card">

      <div className="medical-record-header">

        <span className="material-symbols-outlined">clinical_notes</span>

        <div>

          <h3>门诊病历</h3>

        </div>

      </div>

      <div className="medical-record-meta">

        {displayName} · {displayGender} · {displayAge}岁

      </div>

      <div className="medical-record-fields">

        {RECORD_FIELDS.map(({ key, label }) => {

          const value = String(data[key] ?? '待补充')

          const isPending = !value || value === '待补充' || missing.includes(label)

          const diff = diffByField.get(key)

          return (

            <div key={key} className={`record-field${isPending ? ' pending' : ''}${diff ? ` diff-status-${diff.status}` : ''}`}>

              <span className="record-label">

                {label}

                {renderDiffBadge(key)}

              </span>

              <span className="record-value" title={diff?.source_value}>{value}</span>

            </div>

          )

        })}

      </div>

      {missing.length > 0 && (

        <div className="record-missing">

          <strong>缺项字段：</strong>{missing.join('、')}

        </div>

      )}

      {warnings.length > 0 && (

        <div className="record-warnings">

          {warnings.map((w) => <p key={w}>⚠ {w}</p>)}

        </div>

      )}

      {data.confidence_notes && (

        <div className="record-notes">{data.confidence_notes}</div>

      )}

    </div>

  )

}

