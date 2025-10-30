import { Outlet } from 'react-router-dom'

import Header from '@/components/layout/Header'

const AppLayout = () => {
  return (
    <div className="app-shell">
      <Header />
      <main className="app-content">
        <div className="app-container">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

export default AppLayout
