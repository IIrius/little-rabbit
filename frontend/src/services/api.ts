import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'

import type { RootState } from '@/app/store'
import { clearToken } from '@/features/auth/authSlice'
import { loadToken } from '@/features/auth/tokenStorage'

const baseQuery = fetchBaseQuery({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? '/api',
  credentials: 'include',
  prepareHeaders: (headers, { getState }) => {
    const state = getState() as RootState
    const token = state.auth.token ?? loadToken()

    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }

    return headers
  },
})

const baseQueryWithAuth: typeof baseQuery = async (args, api, extraOptions) => {
  const result = await baseQuery(args, api, extraOptions)

  if (result.error && result.error.status === 401) {
    api.dispatch(clearToken())
  }

  return result
}

export interface DashboardSummary {
  totalUsers: number
  activeUsers: number
  uptimePercentage: number
  lastUpdated: string
}

export const api = createApi({
  reducerPath: 'api',
  baseQuery: baseQueryWithAuth,
  tagTypes: ['Dashboard'],
  endpoints: (builder) => ({
    getDashboardSummary: builder.query<DashboardSummary, void>({
      query: () => ({ url: '/dashboard/summary' }),
      providesTags: ['Dashboard'],
    }),
  }),
})

export const { useGetDashboardSummaryQuery } = api
