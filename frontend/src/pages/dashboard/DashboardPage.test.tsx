import { screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import App from '@/App'
import { renderWithProviders } from '@/test/test-utils'

describe('DashboardPage', () => {
  it('renders the placeholder dashboard content', () => {
    renderWithProviders(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    )

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /dashboard/i,
      }),
    ).toBeInTheDocument()

    expect(screen.getByText(/total users/i)).toBeInTheDocument()
    expect(screen.getByText(/active users/i)).toBeInTheDocument()
  })
})
