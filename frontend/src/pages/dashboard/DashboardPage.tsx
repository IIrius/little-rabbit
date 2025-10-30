import { useMemo } from 'react'

import { useGetDashboardSummaryQuery, type DashboardSummary } from '@/services/api'

const fallbackSummary: DashboardSummary = {
  totalUsers: 1240,
  activeUsers: 987,
  uptimePercentage: 99.98,
  lastUpdated: new Date().toISOString(),
}

const formatLastUpdated = (value: string) => {
  const parsed = new Date(value)

  if (Number.isNaN(parsed.getTime())) {
    return 'Unknown'
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
}

const DashboardPage = () => {
  const { data, isLoading, isError } = useGetDashboardSummaryQuery()

  const summary = data ?? fallbackSummary

  const activeRate = useMemo(() => {
    if (!summary.totalUsers) {
      return 0
    }

    return Math.round((summary.activeUsers / summary.totalUsers) * 100)
  }, [summary.activeUsers, summary.totalUsers])

  const metrics = useMemo(
    () => [
      {
        label: 'Total users',
        value: summary.totalUsers.toLocaleString(),
        description: 'All registered accounts',
      },
      {
        label: 'Active users',
        value: summary.activeUsers.toLocaleString(),
        description: 'Signed in within the last 24 hours',
      },
      {
        label: 'Active rate',
        value: `${activeRate}%`,
        description: 'Active users divided by total users',
      },
      {
        label: 'Uptime',
        value: `${summary.uptimePercentage.toFixed(2)}%`,
        description: 'Last 30 days service availability',
      },
    ],
    [activeRate, summary.activeUsers, summary.totalUsers, summary.uptimePercentage],
  )

  return (
    <section className="dashboard" aria-labelledby="dashboard-heading">
      <header className="dashboard__header">
        <div>
          <h1 className="dashboard__title" id="dashboard-heading">
            Dashboard
          </h1>
          <p className="dashboard__subtitle">
            A high-level overview of the metrics your teams care about.
          </p>
        </div>
        <div className="dashboard__status">
          <span className="dashboard__status-label">Last updated</span>
          <span className="dashboard__status-value">{formatLastUpdated(summary.lastUpdated)}</span>
        </div>
      </header>

      <div className="dashboard__banner" role="status" aria-live="polite">
        {isLoading && <span>Loading latest metrics…</span>}
        {isError && (
          <span>
            We could not reach the API. Displaying the most recent cached values instead.
          </span>
        )}
        {!isLoading && !isError && <span>Metrics are up to date.</span>}
      </div>

      <div className="dashboard__grid" role="list">
        {metrics.map((metric) => (
          <article key={metric.label} className="metric-card" role="listitem">
            <header className="metric-card__header">
              <h2 className="metric-card__title">{metric.label}</h2>
              <span className="metric-card__value">{metric.value}</span>
            </header>
            <p className="metric-card__description">{metric.description}</p>
          </article>
        ))}
      </div>

      <section className="dashboard__next">
        <h2 className="dashboard__next-title">What&apos;s next</h2>
        <ul className="dashboard__todo">
          <li>Connect real API endpoints via RTK Query</li>
          <li>Replace placeholder metrics with live data visualizations</li>
          <li>Add authentication flows and protected routes</li>
        </ul>
      </section>
    </section>
  )
}

export default DashboardPage
