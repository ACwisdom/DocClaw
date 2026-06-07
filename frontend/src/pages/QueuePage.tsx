import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import PageTopbar from '../components/PageTopbar'
import type { Patient, PatientSummary } from '../types'

const STATUS_LABEL: Record<string, string> = {
  waiting: '待接诊',
  consulting: '问诊中',
  completed: '已完成',
}

const TYPE_LABEL: Record<string, string> = {
  first: '初诊',
  followup: '复诊',
}

const PRIORITY_LABEL: Record<string, string> = {
  urgent: '急需评估',
  normal: '普通门诊',
  chronic: '慢病复诊',
}

export default function QueuePage() {
  const [patients, setPatients] = useState<Patient[]>([])
  const [summary, setSummary] = useState<PatientSummary | null>(null)
  const [statusFilter, setStatusFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [search, setSearch] = useState('')

  useEffect(() => {
    Promise.all([
      api.getPatients({ status: statusFilter, visit_type: typeFilter, search: search || undefined }),
      api.getPatientSummary(),
    ]).then(([p, s]) => {
      setPatients(p)
      setSummary(s)
    }).catch(console.error)
  }, [statusFilter, typeFilter, search])

  return (
    <div className="med-page">
      <PageTopbar
        searchPlaceholder="搜索患者或主诉..."
        searchValue={search}
        onSearchChange={setSearch}
      />
      <div className="page-body">
        <div className="page-header-row">
          <div>
            <span className="page-kicker">患者队列</span>
            <h1 className="page-title">今日问诊</h1>
            {summary && (
              <p className="page-subtitle">
                待接诊 {summary.waiting} | 问诊中 {summary.consulting} | 已完成 {summary.completed}
              </p>
            )}
          </div>
          <div className="stat-cards-row">
            {summary && (
              <>
                <div className="mini-stat-card"><span>待接诊</span><strong>{summary.waiting}</strong></div>
                <div className="mini-stat-card"><span>问诊中</span><strong>{summary.consulting}</strong></div>
                <div className="mini-stat-card"><span>初诊</span><strong>{summary.first_visit}</strong></div>
                <div className="mini-stat-card"><span>复诊</span><strong>{summary.followup}</strong></div>
              </>
            )}
          </div>
        </div>

        <div className="filter-row">
          <div className="filter-group">
            {['all', 'waiting', 'consulting', 'completed'].map((s) => (
              <button
                key={s}
                className={`filter-chip${statusFilter === s ? ' active' : ''}`}
                onClick={() => setStatusFilter(s)}
              >
                {s === 'all' ? '全部状态' : STATUS_LABEL[s]}
              </button>
            ))}
          </div>
          <div className="filter-group">
            {['all', 'first', 'followup'].map((t) => (
              <button
                key={t}
                className={`filter-chip${typeFilter === t ? ' active' : ''}`}
                onClick={() => setTypeFilter(t)}
              >
                {t === 'all' ? '全部类型' : TYPE_LABEL[t]}
              </button>
            ))}
          </div>
        </div>

        <div className="patient-list">
          {patients.map((p, i) => (
            <article key={p.id} className="patient-card">
              <div className="patient-index">{String(i + 1).padStart(2, '0')}</div>
              <div className="patient-info">
                <div className="patient-header">
                  <h3>{p.name}</h3>
                  <span className="patient-meta">{p.gender} · {p.age}岁</span>
                  <span className={`tag tag-${p.visit_type}`}>{TYPE_LABEL[p.visit_type]}</span>
                  <span className={`tag tag-priority-${p.priority}`}>{PRIORITY_LABEL[p.priority]}</span>
                  {p.status === 'consulting' && <span className="tag tag-consulting">问诊中</span>}
                </div>
                <p className="patient-complaint"><strong>主诉：</strong>{p.chief_complaint}</p>
              </div>
              <div className="patient-actions">
                {p.visit_type === 'first' ? (
                  <Link to={`/consult/${p.slug}`} className="text-link">查看初诊资料</Link>
                ) : (
                  <Link to={`/consult/${p.slug}`} className="text-link">查看既往病历</Link>
                )}
                <Link to={`/consult/${p.slug}`} className="primary-button small">
                  {p.status === 'consulting' ? '继续问诊' : '开始问诊'}
                </Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  )
}
