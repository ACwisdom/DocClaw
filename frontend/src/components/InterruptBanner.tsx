import { useState } from 'react'
import type { AgentInterrupt, MedicalRecordData, Patient } from '../types'

interface InterruptBannerProps {
  interrupt: AgentInterrupt
  patient?: Patient | null
  loading?: boolean
  onApprove: (payload?: Record<string, unknown>) => void
  onReject: () => void
  onEdit?: (payload: Record<string, unknown>) => void
}

const INTERRUPT_LABELS: Record<string, string> = {
  medical_record_confirm: '病历写入确认',
  followup_plan_confirm: '随访计划确认',
  hitl_approval: '操作审批',
}

export default function InterruptBanner({
  interrupt,
  patient,
  loading,
  onApprove,
  onReject,
  onEdit,
}: InterruptBannerProps) {
  const [editedDraft, setEditedDraft] = useState(interrupt.draft_content ?? '')
  const [editedTitle, setEditedTitle] = useState(interrupt.title ?? '')
  const [editedDescription, setEditedDescription] = useState(interrupt.description ?? '')

  const label = INTERRUPT_LABELS[interrupt.interrupt_type] ?? '待确认操作'

  const handleEditSubmit = () => {
    if (!onEdit) return
    if (interrupt.interrupt_type === 'medical_record_confirm') {
      onEdit({
        draft_content: editedDraft,
        structured_data: interrupt.structured_data,
        patient_slug: interrupt.patient_slug ?? patient?.slug,
      })
      return
    }
    if (interrupt.interrupt_type === 'followup_plan_confirm') {
      onEdit({
        title: editedTitle,
        description: editedDescription,
        tasks: interrupt.tasks,
        patient_id: interrupt.patient_id ?? patient?.id,
      })
    }
  }

  return (
    <div className="interrupt-banner" role="alert">
      <div className="interrupt-banner-header">
        <span className="material-symbols-outlined">verified_user</span>
        <div>
          <h3>{label}</h3>
          <p>智能助理已暂停，请审阅后确认或拒绝</p>
        </div>
      </div>

      {interrupt.interrupt_type === 'medical_record_confirm' && (
        <div className="interrupt-body">
          {interrupt.structured_data && Object.keys(interrupt.structured_data).length > 0 ? (
            <RecordPreview data={interrupt.structured_data} patient={patient} />
          ) : (
            <textarea
              className="interrupt-textarea"
              value={editedDraft}
              onChange={(e) => setEditedDraft(e.target.value)}
              rows={8}
              placeholder="门诊病历内容"
            />
          )}
        </div>
      )}

      {interrupt.interrupt_type === 'followup_plan_confirm' && (
        <div className="interrupt-body">
          <label className="interrupt-field">
            <span>计划标题</span>
            <input
              value={editedTitle}
              onChange={(e) => setEditedTitle(e.target.value)}
            />
          </label>
          <label className="interrupt-field">
            <span>计划说明</span>
            <textarea
              value={editedDescription}
              onChange={(e) => setEditedDescription(e.target.value)}
              rows={3}
            />
          </label>
          {interrupt.tasks && interrupt.tasks.length > 0 && (
            <ul className="interrupt-task-list">
              {interrupt.tasks.map((task, i) => (
                <li key={`${task.title}-${i}`}>
                  <strong>{task.title}</strong>
                  {task.scheduled_at && <span> · {task.scheduled_at}</span>}
                  {task.description && <p>{task.description}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {interrupt.interrupt_type === 'hitl_approval' && (
        <div className="interrupt-body">
          <p className="interrupt-generic">智能助理请求执行以下操作，请确认是否继续。</p>
        </div>
      )}

      {!['medical_record_confirm', 'followup_plan_confirm', 'hitl_approval'].includes(
        interrupt.interrupt_type,
      ) && (
        <div className="interrupt-body">
          <p className="interrupt-generic">请审阅以下内容后确认或拒绝。</p>
        </div>
      )}

      <div className="interrupt-actions">
        <button
          type="button"
          className="secondary-button"
          disabled={loading}
          onClick={onReject}
        >
          拒绝
        </button>
        {onEdit && interrupt.interrupt_type !== 'hitl_approval' && (
          <button
            type="button"
            className="secondary-button"
            disabled={loading}
            onClick={handleEditSubmit}
          >
            编辑后确认
          </button>
        )}
        <button
          type="button"
          className="primary-button"
          disabled={loading}
          onClick={() => onApprove()}
        >
          {loading ? '处理中...' : '确认'}
        </button>
      </div>
    </div>
  )
}

function RecordPreview({ data, patient }: { data: MedicalRecordData; patient?: Patient | null }) {
  const displayName = patient?.name ?? data.patient_name
  const displayGender = patient?.gender ?? data.gender
  const displayAge = patient?.age ?? data.age
  const fields = [
    ['主诉', data.chief_complaint],
    ['现病史', data.present_illness],
    ['既往史', data.past_history],
    ['过敏史', data.allergy_history],
    ['查体', data.physical_exam],
    ['辅助检查', data.auxiliary_exams],
    ['初步诊断', data.preliminary_diagnosis],
    ['处理意见', data.treatment_plan],
  ]
  return (
    <div className="interrupt-record-preview">
      <div className="interrupt-record-meta">
        {displayName} · {displayGender} · {displayAge}岁
      </div>
      {fields.map(([label, value]) => (
        <div key={label} className="interrupt-record-field">
          <span>{label}</span>
          <p>{value || '待补充'}</p>
        </div>
      ))}
    </div>
  )
}
