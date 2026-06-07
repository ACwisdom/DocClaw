import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import PageTopbar from '../components/PageTopbar'
import type { Skill } from '../types'

export default function SkillEditPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [skill, setSkill] = useState<Skill | null>(null)
  const [form, setForm] = useState({ name: '', description: '', input_desc: '', output_desc: '', system_prompt: '' })

  useEffect(() => {
    if (!id) return
    api.getSkill(id).then((s) => {
      setSkill(s)
      setForm({
        name: s.name,
        description: s.description,
        input_desc: s.input_desc,
        output_desc: s.output_desc,
        system_prompt: s.system_prompt,
      })
    }).catch(() => navigate('/skills'))
  }, [id, navigate])

  const handleSave = async () => {
    if (!id) return
    await api.updateSkill(id, form)
    navigate('/skills')
  }

  if (!skill) return <div className="med-page"><div className="page-body loading">加载中...</div></div>

  return (
    <div className="med-page">
      <PageTopbar />
      <div className="page-body">
        <Link to="/skills" className="back-link">← 返回技能列表</Link>
        <div className="form-card">
          <span className="page-kicker">编辑技能</span>
          <h1 className="page-title">{skill.is_default ? '查看技能配置' : '编辑技能'}</h1>

          <div className="form-grid">
            <label className="full-width">
              <span>技能名称</span>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} disabled={skill.is_default} />
            </label>
            <label className="full-width">
              <span>技能简介</span>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} disabled={skill.is_default} />
            </label>
            <label className="full-width">
              <span>输入说明</span>
              <textarea value={form.input_desc} onChange={(e) => setForm({ ...form, input_desc: e.target.value })} rows={2} disabled={skill.is_default} />
            </label>
            <label className="full-width">
              <span>输出说明</span>
              <textarea value={form.output_desc} onChange={(e) => setForm({ ...form, output_desc: e.target.value })} rows={2} disabled={skill.is_default} />
            </label>
            <label className="full-width">
              <span>助理行为说明</span>
              <textarea value={form.system_prompt} onChange={(e) => setForm({ ...form, system_prompt: e.target.value })} rows={8} disabled={skill.is_default} />
            </label>
          </div>

          {!skill.is_default && (
            <div className="form-actions">
              <button className="primary-button" onClick={handleSave}>保存修改</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
