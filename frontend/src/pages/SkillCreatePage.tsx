import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import PageTopbar from '../components/PageTopbar'

export default function SkillCreatePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    name: '',
    description: '',
    input_desc: '',
    output_desc: '',
    system_prompt: '',
    task_type: 'realtime',
  })
  const [saving, setSaving] = useState(false)

  const handleSave = async (publish = false) => {
    if (!form.name.trim()) return alert('请填写技能名称')
    setSaving(true)
    try {
      const skill = await api.createSkill({ ...form, task_type: form.task_type as 'realtime' | 'scheduled' })
      if (publish) await api.publishSkill(skill.id)
      navigate('/skills')
    } catch (e) {
      alert('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const set = (key: string, value: string) => setForm((f) => ({ ...f, [key]: value }))

  return (
    <div className="med-page">
      <PageTopbar />
      <div className="page-body">
        <Link to="/skills" className="back-link">← 返回技能列表</Link>
        <div className="form-card">
          <span className="page-kicker">新建技能</span>
          <h1 className="page-title">创建新医疗技能</h1>
          <p className="page-subtitle">定义 AI 医疗助理的能力与调用约束。</p>

          <div className="form-grid">
            <label>
              <span>技能名称</span>
              <input placeholder="例如：慢病管理建议" value={form.name} onChange={(e) => set('name', e.target.value)} />
            </label>
            <label>
              <span>任务类型</span>
              <select value={form.task_type} onChange={(e) => set('task_type', e.target.value)}>
                <option value="realtime">实时性任务（如门诊病历结构化）</option>
                <option value="scheduled">计划性任务（如随访计划执行）</option>
              </select>
            </label>
            <label className="full-width">
              <span>技能简介</span>
              <textarea placeholder="一句话描述该技能的功能..." value={form.description} onChange={(e) => set('description', e.target.value)} rows={2} />
            </label>
            <label className="full-width">
              <span>输入说明</span>
              <textarea placeholder="技能期望接收什么样的输入" value={form.input_desc} onChange={(e) => set('input_desc', e.target.value)} rows={2} />
            </label>
            <label className="full-width">
              <span>输出说明</span>
              <textarea placeholder="技能应该输出什么内容" value={form.output_desc} onChange={(e) => set('output_desc', e.target.value)} rows={2} />
            </label>
            <label className="full-width">
              <span>助理行为说明</span>
              <textarea placeholder="定义助理的角色、语气及输出规范…" value={form.system_prompt} onChange={(e) => set('system_prompt', e.target.value)} rows={6} />
            </label>
          </div>

          <div className="form-actions">
            <button className="secondary-button" onClick={() => handleSave(false)} disabled={saving}>保存</button>
            <button className="primary-button" onClick={() => handleSave(true)} disabled={saving}>保存并发布</button>
          </div>
        </div>
      </div>
    </div>
  )
}
