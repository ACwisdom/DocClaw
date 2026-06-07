import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import PageTopbar from '../components/PageTopbar'
import type { StoreSkill } from '../types'

export default function StoreDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [skill, setSkill] = useState<StoreSkill | null>(null)

  useEffect(() => {
    if (!id) return
    api.getStoreSkill(id).then(setSkill).catch(console.error)
  }, [id])

  const handleInstall = async () => {
    if (!id) return
    await api.installSkill(id)
    alert('技能已添加到个人技能库')
  }

  if (!skill) return <div className="med-page"><div className="page-body loading">加载中...</div></div>

  return (
    <div className="med-page">
      <PageTopbar />
      <div className="page-body">
        <Link to="/store" className="back-link">← 返回技能广场</Link>
        <div className="detail-card">
          <span className="page-kicker">技能详情</span>
          <h1 className="page-title">{skill.name}</h1>
          <p className="page-subtitle">{skill.description}</p>

          <div className="detail-meta">
            <span>作者：{skill.author}</span>
            {skill.source === 'clawhub' && (
              <span className="source-badge">平台开放技能</span>
            )}
            <span>★ {skill.rating}</span>
            <span>{skill.install_count} 次安装</span>
            <span>更新：{skill.updated_at}</span>
          </div>

          {skill.scenarios && <section><h4>适用场景</h4><p>{skill.scenarios}</p></section>}
          {skill.compatibility && <section><h4>兼容能力</h4><p>{skill.compatibility}</p></section>}
          {skill.highlights && (
            <section>
              <h4>更新亮点</h4>
              <ul>{skill.highlights.split('\n').map((h) => <li key={h}>{h}</li>)}</ul>
            </section>
          )}

          <button className="primary-button" onClick={handleInstall}>获取技能</button>
        </div>
      </div>
    </div>
  )
}
