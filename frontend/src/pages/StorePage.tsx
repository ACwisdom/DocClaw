import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import PageTopbar from '../components/PageTopbar'
import type { StoreSkill } from '../types'

const CATEGORIES = [
  { key: 'all', label: '全部' },
  { key: 'clinical', label: '临床诊断' },
  { key: 'research', label: '文献科研' },
  { key: 'record', label: '病历协作' },
  { key: 'education', label: '患者教育' },
]

export default function StorePage() {
  const [skills, setSkills] = useState<StoreSkill[]>([])
  const [featured, setFeatured] = useState<StoreSkill | null>(null)
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')

  useEffect(() => {
    Promise.all([
      api.getStoreSkills({ category: category === 'all' ? undefined : category, search: search || undefined }),
      api.getFeaturedSkill().catch(() => null),
    ]).then(([s, f]) => {
      setSkills(s)
      setFeatured(f)
    }).catch(console.error)
  }, [category, search])

  const [syncing, setSyncing] = useState(false)

  const handleInstall = async (id: string) => {
    await api.installSkill(id)
    alert('技能已添加到个人技能库')
  }

  const handleSyncClawHub = async () => {
    setSyncing(true)
    try {
      const result = await api.syncClawHubSkills()
      const [skillsList, featuredSkill] = await Promise.all([
        api.getStoreSkills({ category: category === 'all' ? undefined : category, search: search || undefined }),
        api.getFeaturedSkill().catch(() => null),
      ])
      setSkills(skillsList)
      setFeatured(featuredSkill)
      alert(`已更新 ${result.imported} 个开放技能`)
    } catch (err) {
      console.error(err)
      alert('技能更新失败，请稍后重试')
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="med-page">
      <PageTopbar />
      <div className="page-body">
        {featured && (
          <section className="hero-grid">
            <article className="hero-card">
              <div className="hero-card-main">
                <div className="hero-primary-column">
                  <div className="hero-topline">
                    <span className="hero-kicker">今日推荐</span>
                    <span className="hero-verified">
                      {featured.source === 'clawhub' ? '平台开放' : '机构认证'}
                    </span>
                  </div>
                  <h1 className="hero-title">{featured.name}</h1>
                  <p className="hero-copy">{featured.description}</p>
                  <div className="hero-stat-row">
                    <article className="hero-stat-card"><span>发布机构</span><strong>{featured.publisher || featured.author}</strong></article>
                    <article className="hero-stat-card"><span>安装量</span><strong>{featured.install_count.toLocaleString()}</strong></article>
                    <article className="hero-stat-card"><span>最近更新</span><strong>{featured.updated_at}</strong></article>
                  </div>
                  <div className="hero-actions">
                    <button className="secondary-button light" onClick={() => handleInstall(featured.id)}>立即获取</button>
                    <Link to={`/store/${featured.id}`} className="hero-text-link">查看详情</Link>
                  </div>
                </div>
                <aside className="hero-info-panel">
                  {featured.scenarios && (
                    <div className="hero-info-section">
                      <span className="hero-panel-label">适用场景</span>
                      <p>{featured.scenarios}</p>
                    </div>
                  )}
                  {featured.compatibility && (
                    <div className="hero-info-section">
                      <span className="hero-panel-label">兼容能力</span>
                      <p>{featured.compatibility}</p>
                    </div>
                  )}
                  {featured.highlights && (
                    <div className="hero-info-section">
                      <span className="hero-panel-label">推荐理由</span>
                      <ul className="hero-note-list">
                        {featured.highlights.split('\n').map((h) => <li key={h}>{h}</li>)}
                      </ul>
                    </div>
                  )}
                </aside>
              </div>
            </article>
          </section>
        )}

        <label className="store-search">
          <span className="material-symbols-outlined">search</span>
          <input
            placeholder="搜索技能、诊断工具..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>

        <div className="store-section-header">
          <div>
            <span className="page-kicker">技能广场</span>
            <h2 className="store-section-title">共 {skills.length} 个可用技能</h2>
          </div>
        </div>

        <div className="category-row">
          <button
            className="category-chip"
            onClick={handleSyncClawHub}
            disabled={syncing}
            title="从平台拉取最新医疗技能"
          >
            {syncing ? '更新中…' : '更新技能库'}
          </button>
          {CATEGORIES.map((c) => (
            <button
              key={c.key}
              className={`category-chip${category === c.key ? ' active' : ''}`}
              onClick={() => setCategory(c.key)}
            >
              {c.label}
            </button>
          ))}
          <Link to="/skills/new" className="category-chip new-skill">新建技能</Link>
        </div>

        <div className="store-grid">
          {skills.length === 0 && (
            <p className="store-empty">暂无技能，请点击「更新技能库」获取最新内容。</p>
          )}
          {skills.map((skill) => (
            <article key={skill.id} className="store-card">
              <div className="store-card-icon">
                <span className="material-symbols-outlined">medication</span>
              </div>
              <div className="store-card-body">
                <Link to={`/store/${skill.id}`}>
                  <h3>
                    {skill.name}
                    {skill.source === 'clawhub' && <span className="source-badge">平台开放</span>}
                  </h3>
                </Link>
                <p>{skill.description}</p>
                <div className="store-card-meta">
                  <span>{skill.author}</span>
                  <span>★ {skill.rating}</span>
                  <span>{skill.install_count} 安装</span>
                </div>
              </div>
              <button className="primary-button small" onClick={() => handleInstall(skill.id)}>获取</button>
            </article>
          ))}
        </div>

        <section className="editors-choice">
          <span className="page-kicker">编辑精选</span>
          <h2>主编精选</h2>
          <p>为您精挑细选的专业医疗辅助能力。</p>
          <div className="store-grid compact">
            {skills.filter((s) => s.is_editors_choice).map((skill) => (
              <article key={skill.id} className="store-card featured">
                <h3>{skill.name}</h3>
                <p>{skill.description}</p>
                <button className="primary-button small" onClick={() => handleInstall(skill.id)}>获取技能</button>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
