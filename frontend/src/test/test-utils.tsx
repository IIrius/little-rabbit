import type { PropsWithChildren, ReactElement } from 'react'
import { configureStore, type PreloadedState } from '@reduxjs/toolkit'
import { render, type RenderOptions } from '@testing-library/react'
import { Provider } from 'react-redux'

import type { RootState } from '@/app/store'
import authReducer from '@/features/auth/authSlice'
import { api } from '@/services/api'

export const setupTestStore = (preloadedState?: PreloadedState<RootState>) => {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
      auth: authReducer,
    },
    preloadedState,
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(api.middleware),
  })
}

type AppTestStore = ReturnType<typeof setupTestStore>

interface ExtendedRenderOptions extends Omit<RenderOptions, 'queries'> {
  preloadedState?: PreloadedState<RootState>
  store?: AppTestStore
}

export const renderWithProviders = (
  ui: ReactElement,
  {
    preloadedState,
    store = setupTestStore(preloadedState),
    ...renderOptions
  }: ExtendedRenderOptions = {},
) => {
  const Wrapper = ({ children }: PropsWithChildren): JSX.Element => (
    <Provider store={store}>{children}</Provider>
  )

  return { store, ...render(ui, { wrapper: Wrapper, ...renderOptions }) }
}
