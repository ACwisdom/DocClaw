import { useEffect, useMemo, useRef, useState } from 'react'

import { Link, useSearchParams } from 'react-router-dom'

import { api } from '../api'

import ConfirmDialog from '../components/ConfirmDialog'

import Modal from '../components/Modal'

import PageTopbar from '../components/PageTopbar'

import type { FollowUpPlan, FollowUpTask, Patient } from '../types'



const PLAN_STATUS_LABEL: Record<string, string> = {

  active: '进行中',

  paused: '已暂停',

  completed: '已完成',

  cancelled: '已取消',

}



const TASK_STATUS_LABEL: Record<string, string> = {

  pending: '待执行',

  running: '执行中',

  completed: '已完成',

  failed: '失败',

  cancelled: '已取消',

}



type TaskFilter = 'all' | 'today' | 'overdue' | 'week'

type ModalKind =

  | 'create-plan'

  | 'edit-plan'

  | 'add-task'

  | 'edit-task'

  | 'reschedule'

  | 'record-result'

  | null



type ConfirmState = {

  title: string

  message: string

  detail?: string

  danger?: boolean

  confirmLabel?: string

  onConfirm: () => void | Promise<void>

} | null



function toDatetimeLocal(iso: string) {

  const d = new Date(iso)

  const pad = (n: number) => String(n).padStart(2, '0')

  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`

}



function defaultScheduleLocal(days = 7) {

  const d = new Date()

  d.setDate(d.getDate() + days)

  d.setHours(9 + Math.floor(Math.random() * 8), Math.floor(Math.random() * 60), 0, 0)

  return toDatetimeLocal(d.toISOString())

}



function startOfDay(d: Date) {

  const x = new Date(d)

  x.setHours(0, 0, 0, 0)

  return x

}



function endOfWeek(d: Date) {

  const x = startOfDay(d)

  const day = x.getDay() || 7

  x.setDate(x.getDate() + (7 - day))

  x.setHours(23, 59, 59, 999)

  return x

}



function taskDueMeta(scheduledAt: string, status: string) {

  if (status !== 'pending') return null

  const when = new Date(scheduledAt)

  const now = new Date()

  if (when < now) return { label: '已逾期', className: 'due-overdue' }

  if (startOfDay(when).getTime() === startOfDay(now).getTime()) {

    return { label: '今日', className: 'due-today' }

  }

  const diffDays = Math.ceil((startOfDay(when).getTime() - startOfDay(now).getTime()) / 86400000)

  if (diffDays <= 7) return { label: `${diffDays} 天后`, className: 'due-soon' }

  return null

}



function matchTaskFilter(task: FollowUpTask, filter: TaskFilter) {

  if (filter === 'all') return true

  const when = new Date(task.scheduled_at)

  const now = new Date()

  if (filter === 'overdue') return task.status === 'pending' && when < now

  if (filter === 'today') return startOfDay(when).getTime() === startOfDay(now).getTime()

  if (filter === 'week') return when >= startOfDay(now) && when <= endOfWeek(now)

  return true

}



function ActionMenu({

  id,

  openId,

  setOpenId,

  items,

}: {

  id: string

  openId: string | null

  setOpenId: (id: string | null) => void

  items: { label: string; danger?: boolean; onClick: () => void }[]

}) {

  const ref = useRef<HTMLDivElement>(null)



  useEffect(() => {

    if (openId !== id) return

    const close = (e: MouseEvent) => {

      if (ref.current && !ref.current.contains(e.target as Node)) setOpenId(null)

    }

    document.addEventListener('mousedown', close)

    return () => document.removeEventListener('mousedown', close)

  }, [id, openId, setOpenId])



  return (

    <div className="action-menu-wrap" ref={ref}>

      <button

        type="button"

        className="icon-button"

        aria-label="更多操作"

        onClick={() => setOpenId(openId === id ? null : id)}

      >

        <span className="material-symbols-outlined">more_vert</span>

      </button>

      {openId === id && (

        <div className="action-menu">

          {items.map((item) => (

            <button

              key={item.label}

              type="button"

              className={item.danger ? 'action-menu-item danger' : 'action-menu-item'}

              onClick={() => {

                setOpenId(null)

                item.onClick()

              }}

            >

              {item.label}

            </button>

          ))}

        </div>

      )}

    </div>

  )

}



export default function FollowUpPage() {

  const [searchParams] = useSearchParams()

  const patientId = searchParams.get('patient')

  const [plans, setPlans] = useState<FollowUpPlan[]>([])

  const [pendingTasks, setPendingTasks] = useState<FollowUpTask[]>([])

  const [patients, setPatients] = useState<Patient[]>([])

  const [taskFilter, setTaskFilter] = useState<TaskFilter>('all')

  const [patientSearch, setPatientSearch] = useState('')

  const [modal, setModal] = useState<ModalKind>(null)

  const [confirm, setConfirm] = useState<ConfirmState>(null)

  const [openMenuId, setOpenMenuId] = useState<string | null>(null)

  const [activePlanId, setActivePlanId] = useState<string | null>(null)

  const [activeTask, setActiveTask] = useState<FollowUpTask | null>(null)

  const [recordNote, setRecordNote] = useState('')

  const [recordResult, setRecordResult] = useState<string | null>(null)

  const [submitting, setSubmitting] = useState(false)



  const [createForm, setCreateForm] = useState({

    patient_id: patientId || '',

    title: '',

    description: '',

    task_title: '',

    scheduled_at: defaultScheduleLocal(7),

  })

  const [planForm, setPlanForm] = useState({ title: '', description: '' })

  const [taskForm, setTaskForm] = useState({

    title: '',

    description: '',

    scheduled_at: defaultScheduleLocal(7),

  })



  const load = () => {

    Promise.all([

      api.getFollowUpPlans(patientId || undefined),

      api.getPendingTasks(),

      api.getPatients(),

    ]).then(([p, t, pts]) => {

      setPlans(p)

      setPendingTasks(t)

      setPatients(pts)

    }).catch(console.error)

  }



  useEffect(load, [patientId])



  useEffect(() => {

    if (patientId) setCreateForm((f) => ({ ...f, patient_id: patientId }))

  }, [patientId])



  const patientMap = useMemo(() => new Map(patients.map((p) => [p.id, p])), [patients])



  const getPatientName = (id: string) => patientMap.get(id)?.name || id

  const getPatientSlug = (id: string) => patientMap.get(id)?.slug



  const filteredPatients = useMemo(() => {

    const q = patientSearch.trim().toLowerCase()

    if (!q) return patients.slice(0, 50)

    return patients.filter(

      (p) => p.name.includes(q) || p.chief_complaint.toLowerCase().includes(q),

    ).slice(0, 50)

  }, [patients, patientSearch])



  const filteredPending = useMemo(

    () => pendingTasks.filter((t) => matchTaskFilter(t, taskFilter)),

    [pendingTasks, taskFilter],

  )



  const activePlans = useMemo(

    () => plans.filter((p) => p.status === 'active' || p.status === 'paused'),

    [plans],

  )

  const archivedPlans = useMemo(

    () => plans.filter((p) => p.status === 'completed' || p.status === 'cancelled'),

    [plans],

  )



  const filterCounts = useMemo(() => ({

    all: pendingTasks.length,

    today: pendingTasks.filter((t) => matchTaskFilter(t, 'today')).length,

    overdue: pendingTasks.filter((t) => matchTaskFilter(t, 'overdue')).length,

    week: pendingTasks.filter((t) => matchTaskFilter(t, 'week')).length,

  }), [pendingTasks])



  const closeModal = () => {

    setModal(null)

    setActivePlanId(null)

    setActiveTask(null)

    setRecordNote('')

    setRecordResult(null)

  }



  const askConfirm = (state: ConfirmState) => setConfirm(state)



  const handleCreate = async () => {

    if (!createForm.patient_id || !createForm.title) return askConfirm({

      title: '无法创建',

      message: '请选择患者并填写计划标题。',

      confirmLabel: '知道了',

      onConfirm: () => setConfirm(null),

    })

    setSubmitting(true)

    try {

      await api.createFollowUpPlan({

        patient_id: createForm.patient_id,

        title: createForm.title,

        description: createForm.description,

        skill_id: 'skill-followup',

        tasks: [{

          title: createForm.task_title || createForm.title,

          description: createForm.description,

          scheduled_at: new Date(createForm.scheduled_at).toISOString(),

        }],

      })

      closeModal()

      load()

    } finally {

      setSubmitting(false)

    }

  }



  const openEditPlan = (plan: FollowUpPlan) => {

    setActivePlanId(plan.id)

    setPlanForm({ title: plan.title, description: plan.description })

    setModal('edit-plan')

  }



  const savePlan = async () => {

    if (!activePlanId || !planForm.title.trim()) return

    setSubmitting(true)

    try {

      await api.updateFollowUpPlan(activePlanId, planForm)

      closeModal()

      load()

    } finally {

      setSubmitting(false)

    }

  }



  const deletePlan = (plan: FollowUpPlan) => {

    const pendingCount = plan.tasks.filter((t) => t.status === 'pending').length

    askConfirm({

      title: '删除随访计划',

      message: `确定删除「${plan.title}」？`,

      detail: pendingCount > 0

        ? `将永久删除该计划及 ${pendingCount} 个待执行任务，此操作不可恢复。`

        : '将永久删除该计划及全部任务记录。',

      danger: true,

      confirmLabel: '删除',

      onConfirm: async () => {

        await api.deleteFollowUpPlan(plan.id)

        setConfirm(null)

        load()

      },

    })

  }



  const togglePlanPause = async (plan: FollowUpPlan) => {

    const next = plan.status === 'paused' ? 'active' : 'paused'

    await api.updateFollowUpPlan(plan.id, { status: next })

    load()

  }



  const completePlan = (plan: FollowUpPlan) => {

    const pendingCount = plan.tasks.filter((t) => t.status === 'pending').length

    askConfirm({

      title: '标记计划完成',

      message: `将「${plan.title}」标记为已完成。`,

      detail: pendingCount > 0

        ? `仍有 ${pendingCount} 个任务未执行，标记后任务仍保留为待执行状态。`

        : undefined,

      confirmLabel: '标记完成',

      onConfirm: async () => {

        await api.updateFollowUpPlan(plan.id, { status: 'completed' })

        setConfirm(null)

        load()

      },

    })

  }



  const cancelPlan = (plan: FollowUpPlan) => {

    const pendingCount = plan.tasks.filter((t) => t.status === 'pending').length

    askConfirm({

      title: '取消随访计划',

      message: `确定取消「${plan.title}」？`,

      detail: pendingCount > 0 ? `将同时取消 ${pendingCount} 个待执行任务。` : undefined,

      danger: true,

      confirmLabel: '取消计划',

      onConfirm: async () => {

        await api.updateFollowUpPlan(plan.id, { status: 'cancelled' })

        setConfirm(null)

        load()

      },

    })

  }



  const openAddTask = (planId: string) => {

    setActivePlanId(planId)

    setTaskForm({ title: '', description: '', scheduled_at: defaultScheduleLocal(14) })

    setModal('add-task')

  }



  const openEditTask = (task: FollowUpTask) => {

    setActiveTask(task)

    setActivePlanId(task.plan_id)

    setTaskForm({

      title: task.title,

      description: task.description,

      scheduled_at: toDatetimeLocal(task.scheduled_at),

    })

    setModal('edit-task')

  }



  const openReschedule = (task: FollowUpTask) => {

    setActiveTask(task)

    setTaskForm((f) => ({ ...f, scheduled_at: toDatetimeLocal(task.scheduled_at) }))

    setModal('reschedule')

  }



  const bumpSchedule = (days: number) => {

    const d = new Date()

    d.setDate(d.getDate() + days)

    d.setHours(10, 0, 0, 0)

    setTaskForm((f) => ({ ...f, scheduled_at: toDatetimeLocal(d.toISOString()) }))

  }



  const saveReschedule = async () => {

    if (!activeTask) return

    setSubmitting(true)

    try {

      await api.updateFollowUpTask(activeTask.id, {

        scheduled_at: new Date(taskForm.scheduled_at).toISOString(),

      })

      closeModal()

      load()

    } finally {

      setSubmitting(false)

    }

  }



  const saveNewTask = async () => {

    if (!activePlanId || !taskForm.title.trim()) return

    setSubmitting(true)

    try {

      await api.addFollowUpTask(activePlanId, {

        title: taskForm.title,

        description: taskForm.description,

        scheduled_at: new Date(taskForm.scheduled_at).toISOString(),

      })

      closeModal()

      load()

    } finally {

      setSubmitting(false)

    }

  }



  const saveTask = async () => {

    if (!activeTask || !taskForm.title.trim()) return

    setSubmitting(true)

    try {

      await api.updateFollowUpTask(activeTask.id, {

        title: taskForm.title,

        description: taskForm.description,

        scheduled_at: new Date(taskForm.scheduled_at).toISOString(),

      })

      closeModal()

      load()

    } finally {

      setSubmitting(false)

    }

  }



  const deleteTask = (task: FollowUpTask) => {

    askConfirm({

      title: '删除任务',

      message: `确定删除「${task.title}」？`,

      detail: '删除后无法恢复。',

      danger: true,

      confirmLabel: '删除',

      onConfirm: async () => {

        await api.deleteFollowUpTask(task.id)

        setConfirm(null)

        load()

      },

    })

  }



  const cancelTask = (task: FollowUpTask) => {

    askConfirm({

      title: '取消任务',

      message: `确定取消「${task.title}」？`,

      detail: '取消后任务将不再出现在待执行列表。',

      confirmLabel: '取消任务',

      onConfirm: async () => {

        await api.cancelFollowUpTask(task.id)

        setConfirm(null)

        load()

      },

    })

  }



  const openRecordResult = (task: FollowUpTask) => {

    setActiveTask(task)

    setRecordNote('')

    setRecordResult(null)

    setModal('record-result')

  }



  const submitRecordResult = async () => {

    if (!activeTask) return

    setSubmitting(true)

    try {

      const res = await api.executeTask(activeTask.id, recordNote)

      setRecordResult(res.result)

      load()

    } finally {

      setSubmitting(false)

    }

  }



  const renderQueueActions = (task: FollowUpTask) => {

    const slug = task.patient_id ? getPatientSlug(task.patient_id) : null

    return (

      <div className="task-actions task-actions-primary">

        {slug && (

          <Link to={`/consult/${slug}`} className="primary-button small">

            <span className="material-symbols-outlined">person</span>

            进入患者

          </Link>

        )}

        <button type="button" className="secondary-button small" onClick={() => openReschedule(task)}>

          改期

        </button>

        <button type="button" className="secondary-button small" onClick={() => openRecordResult(task)}>

          记录结果

        </button>

        <ActionMenu

          id={`queue-${task.id}`}

          openId={openMenuId}

          setOpenId={setOpenMenuId}

          items={[

            { label: '编辑详情', onClick: () => openEditTask(task) },

            { label: '取消任务', onClick: () => cancelTask(task) },

            { label: '删除任务', danger: true, onClick: () => deleteTask(task) },

          ]}

        />

      </div>

    )

  }



  const renderPlanTaskActions = (task: FollowUpTask, plan: FollowUpPlan) => {

    const planLocked = plan.status === 'cancelled' || plan.status === 'completed'

    if (task.status === 'pending' && !planLocked) {

      return (

        <div className="task-actions task-actions-compact">

          <button type="button" className="text-button small" onClick={() => openReschedule(task)}>改期</button>

          <button type="button" className="text-button small" onClick={() => openRecordResult(task)}>记录结果</button>

          <ActionMenu

            id={`plan-task-${task.id}`}

            openId={openMenuId}

            setOpenId={setOpenMenuId}

            items={[

              { label: '编辑详情', onClick: () => openEditTask(task) },

              { label: '取消任务', onClick: () => cancelTask(task) },

              { label: '删除任务', danger: true, onClick: () => deleteTask(task) },

            ]}

          />

        </div>

      )

    }

    if (task.status === 'completed') {

      return (

        <div className="task-actions task-actions-compact">

          <button type="button" className="text-button small" onClick={() => openEditTask(task)}>查看详情</button>

          <ActionMenu

            id={`plan-done-${task.id}`}

            openId={openMenuId}

            setOpenId={setOpenMenuId}

            items={[{ label: '删除记录', danger: true, onClick: () => deleteTask(task) }]}

          />

        </div>

      )

    }

    return null

  }



  const renderPlanToolbar = (plan: FollowUpPlan) => {

    const slug = getPatientSlug(plan.patient_id)

    const isLocked = plan.status === 'cancelled' || plan.status === 'completed'

    const menuItems: { label: string; danger?: boolean; onClick: () => void }[] = []



    if (plan.status === 'active') menuItems.push({ label: '暂停计划', onClick: () => togglePlanPause(plan) })

    if (plan.status === 'paused') menuItems.push({ label: '恢复计划', onClick: () => togglePlanPause(plan) })

    if (!isLocked) menuItems.push({ label: '标记完成', onClick: () => completePlan(plan) })

    if (plan.status !== 'cancelled') menuItems.push({ label: '取消计划', danger: true, onClick: () => cancelPlan(plan) })

    menuItems.push({ label: '删除计划', danger: true, onClick: () => deletePlan(plan) })



    return (

      <div className="plan-toolbar">

        {slug && (

          <Link to={`/consult/${slug}`} className="secondary-button small">

            <span className="material-symbols-outlined">open_in_new</span>

            患者档案

          </Link>

        )}

        {!isLocked && (

          <button type="button" className="primary-button small" onClick={() => openAddTask(plan.id)}>

            添加任务

          </button>

        )}

        <button type="button" className="secondary-button small" onClick={() => openEditPlan(plan)}>

          编辑计划

        </button>

        <ActionMenu

          id={`plan-${plan.id}`}

          openId={openMenuId}

          setOpenId={setOpenMenuId}

          items={menuItems}

        />

      </div>

    )

  }



  return (

    <div className="med-page">

      <PageTopbar />

      <div className="page-body">

        <div className="page-header-row">

          <div>

            <span className="page-kicker">随访计划</span>

            <h1 className="page-title">随访计划</h1>

            <p className="page-subtitle">按待办优先级处理随访，计划管理收纳在「更多」菜单。</p>

          </div>

          <button

            type="button"

            className="primary-button"

            onClick={() => {

              setCreateForm({

                patient_id: patientId || '',

                title: '',

                description: '',

                task_title: '',

                scheduled_at: defaultScheduleLocal(7),

              })

              setPatientSearch('')

              setModal('create-plan')

            }}

          >

            创建随访计划

          </button>

        </div>



        <section className="followup-section">

          <div className="followup-section-head">

            <h2>待办队列</h2>

            <div className="filter-chips">

              {([

                ['all', '全部'],

                ['today', '今日'],

                ['overdue', '逾期'],

                ['week', '本周'],

              ] as const).map(([key, label]) => (

                <button

                  key={key}

                  type="button"

                  className={`filter-chip${taskFilter === key ? ' active' : ''}`}

                  onClick={() => setTaskFilter(key)}

                >

                  {label}

                  <span className="chip-count">{filterCounts[key]}</span>

                </button>

              ))}

            </div>

          </div>

          <div className="task-list">

            {filteredPending.map((task) => {

              const due = taskDueMeta(task.scheduled_at, task.status)

              return (

                <article key={task.id} className="task-card task-card-rich">

                  <div className="task-card-body">

                    <div className="task-title-row">

                      <h4>{task.title}</h4>

                      {due && <span className={`due-badge ${due.className}`}>{due.label}</span>}

                    </div>

                    <p>{task.description}</p>

                    <div className="task-meta">

                      {task.patient_name && <span className="tag">{task.patient_name}</span>}

                      {task.plan_title && <span className="tag tag-muted">{task.plan_title}</span>}

                      <span className="task-date">

                        计划：{new Date(task.scheduled_at).toLocaleString('zh-CN')}

                      </span>

                    </div>

                  </div>

                  {renderQueueActions(task)}

                </article>

              )

            })}

            {filteredPending.length === 0 && (

              <p className="empty-hint">

                {pendingTasks.length === 0 ? '暂无待执行任务' : '当前筛选条件下没有待办'}

              </p>

            )}

          </div>

        </section>



        <section className="followup-section">

          <h2>进行中的计划 ({activePlans.length})</h2>

          <div className="plan-list">

            {activePlans.map((plan) => (

              <article key={plan.id} className="plan-card">

                <div className="plan-header">

                  <h3>{plan.title}</h3>

                  <span className="tag">{getPatientName(plan.patient_id)}</span>

                  <span className={`tag tag-${plan.status}`}>{PLAN_STATUS_LABEL[plan.status] || plan.status}</span>

                  <span className="plan-created">创建于 {new Date(plan.created_at).toLocaleString('zh-CN')}</span>

                </div>

                <p>{plan.description}</p>

                {renderPlanToolbar(plan)}

                <div className="plan-tasks">

                  {plan.tasks.map((task) => {

                    const due = taskDueMeta(task.scheduled_at, task.status)

                    return (

                      <div key={task.id} className={`task-item task-${task.status}`}>

                        <div className="task-item-main">

                          <span className="task-item-title">{task.title}</span>

                          <span className="task-item-time">{new Date(task.scheduled_at).toLocaleString('zh-CN')}</span>

                          {due && <span className={`due-badge ${due.className}`}>{due.label}</span>}

                          <span className={`status-badge status-${task.status}`}>

                            {TASK_STATUS_LABEL[task.status] || task.status}

                          </span>

                        </div>

                        {task.result && <p className="task-result">{task.result}</p>}

                        {renderPlanTaskActions(task, plan)}

                      </div>

                    )

                  })}

                  {plan.tasks.length === 0 && <p className="empty-hint">暂无任务，点击「添加任务」</p>}

                </div>

              </article>

            ))}

            {activePlans.length === 0 && <p className="empty-hint">暂无进行中的计划</p>}

          </div>

        </section>



        {archivedPlans.length > 0 && (

          <section className="followup-section followup-archived">

            <h2>已归档计划 ({archivedPlans.length})</h2>

            <div className="plan-list">

              {archivedPlans.map((plan) => (

                <article key={plan.id} className="plan-card plan-card-muted">

                  <div className="plan-header">

                    <h3>{plan.title}</h3>

                    <span className="tag">{getPatientName(plan.patient_id)}</span>

                    <span className={`tag tag-${plan.status}`}>{PLAN_STATUS_LABEL[plan.status] || plan.status}</span>

                  </div>

                  <p>{plan.description}</p>

                  <div className="plan-toolbar">

                    <button type="button" className="secondary-button small" onClick={() => openEditPlan(plan)}>查看计划</button>

                    <ActionMenu

                      id={`archived-${plan.id}`}

                      openId={openMenuId}

                      setOpenId={setOpenMenuId}

                      items={[{ label: '删除计划', danger: true, onClick: () => deletePlan(plan) }]}

                    />

                  </div>

                </article>

              ))}

            </div>

          </section>

        )}

      </div>



      {modal === 'create-plan' && (

        <Modal

          title="新建随访计划"

          subtitle="创建后可继续添加多个随访任务"

          onClose={closeModal}

          footer={(

            <>

              <button type="button" className="secondary-button" onClick={closeModal}>取消</button>

              <button type="button" className="primary-button" disabled={submitting} onClick={handleCreate}>创建</button>

            </>

          )}

        >

          <div className="form-grid">

            <label className="full-width">

              <span>搜索患者 *</span>

              <input

                value={patientSearch}

                onChange={(e) => setPatientSearch(e.target.value)}

                placeholder="输入姓名或主诉搜索"

              />

            </label>

            <label className="full-width">

              <span>选择患者 *</span>

              <select

                value={createForm.patient_id}

                onChange={(e) => setCreateForm({ ...createForm, patient_id: e.target.value })}

              >

                <option value="">请选择</option>

                {filteredPatients.map((p) => (

                  <option key={p.id} value={p.id}>{p.name} · {p.chief_complaint.slice(0, 24)}</option>

                ))}

              </select>

            </label>

            <label>

              <span>计划标题 *</span>

              <input value={createForm.title} onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })} />

            </label>

            <label>

              <span>首个任务</span>

              <input value={createForm.task_title} onChange={(e) => setCreateForm({ ...createForm, task_title: e.target.value })} placeholder="如：电话随访" />

            </label>

            <label className="full-width">

              <span>计划描述</span>

              <textarea value={createForm.description} onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })} rows={2} />

            </label>

            <label>

              <span>首次执行时间</span>

              <input type="datetime-local" value={createForm.scheduled_at} onChange={(e) => setCreateForm({ ...createForm, scheduled_at: e.target.value })} />

            </label>

          </div>

        </Modal>

      )}



      {modal === 'edit-plan' && (

        <Modal

          title="编辑随访计划"

          onClose={closeModal}

          footer={(

            <>

              <button type="button" className="secondary-button" onClick={closeModal}>取消</button>

              <button type="button" className="primary-button" disabled={submitting} onClick={savePlan}>保存</button>

            </>

          )}

        >

          <div className="form-grid">

            <label className="full-width">

              <span>计划标题 *</span>

              <input value={planForm.title} onChange={(e) => setPlanForm({ ...planForm, title: e.target.value })} />

            </label>

            <label className="full-width">

              <span>计划描述</span>

              <textarea value={planForm.description} onChange={(e) => setPlanForm({ ...planForm, description: e.target.value })} rows={3} />

            </label>

          </div>

        </Modal>

      )}



      {(modal === 'add-task' || modal === 'edit-task') && (

        <Modal

          title={modal === 'add-task' ? '添加随访任务' : '编辑任务详情'}

          onClose={closeModal}

          footer={(

            <>

              <button type="button" className="secondary-button" onClick={closeModal}>取消</button>

              <button type="button" className="primary-button" disabled={submitting} onClick={modal === 'add-task' ? saveNewTask : saveTask}>保存</button>

            </>

          )}

        >

          <div className="form-grid">

            <label className="full-width">

              <span>任务标题 *</span>

              <input value={taskForm.title} onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })} />

            </label>

            <label className="full-width">

              <span>计划执行时间</span>

              <input type="datetime-local" value={taskForm.scheduled_at} onChange={(e) => setTaskForm({ ...taskForm, scheduled_at: e.target.value })} />

            </label>

            <label className="full-width">

              <span>任务描述</span>

              <textarea value={taskForm.description} onChange={(e) => setTaskForm({ ...taskForm, description: e.target.value })} rows={2} />

            </label>

          </div>

        </Modal>

      )}



      {modal === 'reschedule' && activeTask && (

        <Modal

          title="改期"

          subtitle={activeTask.title}

          onClose={closeModal}

          footer={(

            <>

              <button type="button" className="secondary-button" onClick={closeModal}>取消</button>

              <button type="button" className="primary-button" disabled={submitting} onClick={saveReschedule}>确认改期</button>

            </>

          )}

        >

          <div className="reschedule-quick">

            <span>快捷：</span>

            <button type="button" className="secondary-button small" onClick={() => bumpSchedule(3)}>3 天后</button>

            <button type="button" className="secondary-button small" onClick={() => bumpSchedule(7)}>7 天后</button>

            <button type="button" className="secondary-button small" onClick={() => bumpSchedule(14)}>14 天后</button>

          </div>

          <label className="full-width reschedule-picker">

            <span>新的执行时间</span>

            <input type="datetime-local" value={taskForm.scheduled_at} onChange={(e) => setTaskForm({ ...taskForm, scheduled_at: e.target.value })} />

          </label>

        </Modal>

      )}



      {modal === 'record-result' && activeTask && (

        <Modal

          title="记录随访结果"

          subtitle={`${activeTask.patient_name || ''} · ${activeTask.title}`}

          wide

          onClose={closeModal}

          footer={recordResult ? (

            <button type="button" className="primary-button" onClick={closeModal}>完成</button>

          ) : (

            <>

              <button type="button" className="secondary-button" onClick={closeModal}>取消</button>

              <button type="button" className="primary-button" disabled={submitting} onClick={submitRecordResult}>确认完成</button>

            </>

          )}

        >

          {!recordResult ? (

            <>

              <p className="record-hint">确认后将标记任务为已完成，并生成 AI 摘要；您可补充临床记录。</p>

              <label className="full-width">

                <span>医生补充记录（可选）</span>

                <textarea

                  value={recordNote}

                  onChange={(e) => setRecordNote(e.target.value)}

                  rows={4}

                  placeholder="如：已电话随访，患者咳嗽减轻，建议继续用药…"

                />

              </label>

            </>

          ) : (

            <div className="record-result-box">

              <h4>随访已完成</h4>

              <pre>{recordResult}</pre>

            </div>

          )}

        </Modal>

      )}



      {confirm && (

        <ConfirmDialog

          title={confirm.title}

          message={confirm.message}

          detail={confirm.detail}

          danger={confirm.danger}

          confirmLabel={confirm.confirmLabel}

          onConfirm={confirm.onConfirm}

          onCancel={() => setConfirm(null)}

        />

      )}

    </div>

  )

}


