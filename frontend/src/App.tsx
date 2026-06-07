import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import QueuePage from './pages/QueuePage'
import SkillsPage from './pages/SkillsPage'
import SkillCreatePage from './pages/SkillCreatePage'
import SkillEditPage from './pages/SkillEditPage'
import StorePage from './pages/StorePage'
import StoreDetailPage from './pages/StoreDetailPage'
import ConsultPage from './pages/ConsultPage'
import FollowUpPage from './pages/FollowUpPage'
import NotificationsPage from './pages/NotificationsPage'
import SettingsPage from './pages/SettingsPage'
import HelpPage from './pages/HelpPage'
import NotFoundPage from './pages/NotFoundPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/queue" replace />} />
        <Route path="/queue" element={<QueuePage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/skills/new" element={<SkillCreatePage />} />
        <Route path="/skills/:id/edit" element={<SkillEditPage />} />
        <Route path="/store" element={<StorePage />} />
        <Route path="/store/:id" element={<StoreDetailPage />} />
        <Route path="/consult/:slug" element={<ConsultPage />} />
        <Route path="/followup" element={<FollowUpPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/help" element={<HelpPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
