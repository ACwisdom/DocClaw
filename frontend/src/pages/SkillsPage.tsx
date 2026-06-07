import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import ConfirmDialog from '../components/ConfirmDialog'
import PageTopbar from '../components/PageTopbar'
import type { Skill, SkillStats } from '../types'

const STATUS_BADGE: Record<string, string> = {
  default: '默认技能',
  enabled: '已启用',
  published: '已发布',
  draft: '草稿',
}

type DeleteConfirm = {
  skill: Skill
} | null

function deleteSkillDetail(skill: Skill): string {
  const parts: string[] = ['删除后该技能的配置与说明将永久丢失，且无法恢复。']
  if (skill.enabled) {
    parts.push('当前技能已启用，删除后将不再出现在问诊与任务执行的技能列表中。')
  }
  if (skill.published_to_store) {
    parts.push('该技能曾发布到广场，删除仅影响您个人技能库，不影响已安装该技能的其他医生。')
  }
  if (skill.task_type === 'scheduled') {
    parts.push('若已有随访计划关联此技能，删除后相关计划将无法再调用该技能。')
  }
  if (skill.usage_count > 0) {
    parts.push(`该技能累计使用 ${skill.usage_count} 次，删除后使用统计一并清除。`)
  }
  return parts.join('')
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [stats, setStats] = useState<SkillStats | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<DeleteConfirm>(null)
  const [deleting, setDeleting] = useState(false)

  const load = () => {
    Promise.all([api.getSkills(), api.getSkillStats()])
      .then(([s, st]) => { setSkills(s); setStats(st) })
      .catch(console.error)
  }

  useEffect(load, [])

  const handleToggle = async (id: string) => {
    await api.toggleSkill(id)
    load()
  }

  const handleDelete = (skill: Skill) => {
    setDeleteConfirm({ skill })
  }

  const confirmDelete = async () => {
    if (!deleteConfirm) return
    setDeleting(true)
    try {
      await api.deleteSkill(deleteConfirm.skill.id)
      setDeleteConfirm(null)
      load()
    } catch (err) {
      console.error(err)
    } finally {
      setDeleting(false)
    }
  }

  const handlePublish = async (id: string) => {
    await api.publishSkill(id)
    load()
  }

  return (
    <div className="med-page">
      <PageTopbar />
      <div className="page-body">
        <div className="page-header-row">
          <div>
            <span className="page-kicker">个人技能</span>
            <h1 className="page-title">我的技能</h1>
            <p className="page-subtitle">管理您的个性化 AI 医疗助理，提升临床工作效率。</p>
          </div>
          <Link to="/skills/new" className="primary-button">创建技能</Link>
        </div>

        {stats && (
          <div className="stat-cards-row">
            <div className="mini-stat-card"><span>已启用技能</span><strong>{stats.enabled + stats.default}</strong></div>
            <div className="mini-stat-card"><span>草稿中</span><strong>{stats.draft}</strong></div>
            <div className="mini-stat-card"><span>已发布</span><strong>{stats.published}</strong></div>
            <div className="mini-stat-card"><span>默认技能</span><strong>{stats.default}</strong></div>
          </div>
        )}

        <div className="skill-grid">
          {skills.map((skill) => (
            <article key={skill.id} className="skill-card">
              <div className="skill-card-header">
                <div className={`skill-icon skill-icon-${skill.icon}`}>
                  <span className="material-symbols-outlined">{skill.icon}</span>
                </div>
                <div className="skill-card-title">
                  <Link to={skill.is_default ? '#' : `/skills/${skill.id}/edit`}>
                    <h3>{skill.name}</h3>
                  </Link>
                  <span className="skill-author">{skill.doctor_name}</span>
                </div>
                <div className="skill-card-badges">
                  <span className={`badge badge-${skill.status}`}>{STATUS_BADGE[skill.status] || skill.status}</span>
                  {skill.is_default ? (
                    <span className="badge badge-fixed">固定启用</span>
                  ) : (
                    <label className="toggle-switch">
                      <input type="checkbox" checked={skill.enabled} onChange={() => handleToggle(skill.id)} />
                      <span className="toggle-slider" />
                    </label>
                  )}
                </div>
              </div>

              <p className="skill-version">{skill.version} {skill.mode}</p>
              <p className="skill-desc">{skill.description}</p>

              <div className="skill-tags">
                {skill.tags.split(',').filter(Boolean).map((t) => (
                  <span key={t} className="tag tag-skill">{t.trim()}</span>
                ))}
                {skill.task_type === 'scheduled' && <span className="tag tag-scheduled">计划性</span>}
              </div>

              <div className="skill-meta">
                <span>★ {skill.rating}</span>
                <span>{skill.usage_count} 次使用</span>
                <span>{skill.review_count} 条评价</span>
                <span>{new Date(skill.created_at).toLocaleDateString('zh-CN')}</span>
              </div>

              <div className="skill-actions">
                {skill.is_default ? (
                  <Link to={`/skills/${skill.id}/edit`} className="text-link">查看配置</Link>
                ) : (
                  <Link to={`/skills/${skill.id}/edit`} className="text-link">编辑</Link>
                )}
                {!skill.published_to_store && (
                  <button className="text-link" onClick={() => handlePublish(skill.id)}>发布到广场</button>
                )}
                {!skill.is_default && (
                  <button className="text-link danger" onClick={() => handleDelete(skill)}>删除技能</button>
                )}
              </div>
            </article>
          ))}
        </div>
      </div>

      {deleteConfirm && (
        <ConfirmDialog
          title="删除技能"
          message={`确定删除「${deleteConfirm.skill.name}」？`}
          detail={deleteSkillDetail(deleteConfirm.skill)}
          confirmLabel={deleting ? '删除中…' : '确认删除'}
          danger
          onConfirm={confirmDelete}
          onCancel={() => !deleting && setDeleteConfirm(null)}
        />
      )}
    </div>
  )
}
