import { useAppSelector } from '@/app/hooks'
import { selectIsAuthenticated } from '@/features/auth/authSlice'

const Header = () => {
  const isAuthenticated = useAppSelector(selectIsAuthenticated)
  const appName = import.meta.env.VITE_APP_NAME ?? 'Dashboard'

  return (
    <header className="app-header">
      <div className="app-container app-header__inner">
        <span className="app-logo" aria-label="Application name">
          {appName}
        </span>
        <span
          className="app-auth-status"
          data-state={isAuthenticated ? 'authenticated' : 'guest'}
          aria-live="polite"
        >
          {isAuthenticated ? 'Authenticated' : 'Guest'}
        </span>
      </div>
    </header>
  )
}

export default Header
