import { Navigate, Route, Routes } from 'react-router-dom'

import AppLayout from '@/components/layout/AppLayout'
import DashboardPage from '@/pages/dashboard/DashboardPage'

const App = () => {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
