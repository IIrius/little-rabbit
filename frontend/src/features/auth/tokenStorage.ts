const isBrowser = () => typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'

const tokenStorageKey = import.meta.env.VITE_STORAGE_TOKEN_KEY || 'auth_token'

export const loadToken = (): string | null => {
  if (!isBrowser()) {
    return null
  }

  return window.localStorage.getItem(tokenStorageKey)
}

export const persistToken = (token: string) => {
  if (!isBrowser()) {
    return
  }

  window.localStorage.setItem(tokenStorageKey, token)
}

export const clearPersistedToken = () => {
  if (!isBrowser()) {
    return
  }

  window.localStorage.removeItem(tokenStorageKey)
}
