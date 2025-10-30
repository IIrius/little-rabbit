import { createSlice, type PayloadAction } from '@reduxjs/toolkit'

import type { RootState } from '@/app/store'
import { clearPersistedToken, loadToken, persistToken } from './tokenStorage'

interface AuthState {
  token: string | null
}

const initialState: AuthState = {
  token: loadToken(),
}

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setToken: (state, action: PayloadAction<string>) => {
      state.token = action.payload
      persistToken(action.payload)
    },
    clearToken: (state) => {
      state.token = null
      clearPersistedToken()
    },
  },
})

export const { setToken, clearToken } = authSlice.actions

export const selectAuthToken = (state: RootState) => state.auth.token
export const selectIsAuthenticated = (state: RootState) => Boolean(state.auth.token)

export default authSlice.reducer
