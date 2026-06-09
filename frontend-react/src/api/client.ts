import axios, { type InternalAxiosRequestConfig } from "axios"

export const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

// Shared in-memory access token — set by AuthContext after login / refresh
let accessToken: string | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

export const apiClient = axios.create({ baseURL: BASE_URL })

// Attach bearer token to every request
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

// On 401: try to refresh, then retry once; on second failure clear storage + reload
let refreshing: Promise<string> | null = null

apiClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error)
    }
    original._retry = true

    const storedRefresh = localStorage.getItem("refresh_token")
    if (!storedRefresh) {
      clearAuth()
      return Promise.reject(error)
    }

    try {
      // Deduplicate concurrent refresh calls
      if (!refreshing) {
        refreshing = axios
          .post<{ access_token: string }>(`${BASE_URL}/auth/jwt/refresh`, {
            refresh_token: storedRefresh,
          })
          .then((r) => r.data.access_token)
          .finally(() => {
            refreshing = null
          })
      }

      const newToken = await refreshing
      setAccessToken(newToken)
      original.headers.Authorization = `Bearer ${newToken}`
      return apiClient(original)
    } catch {
      clearAuth()
      return Promise.reject(error)
    }
  }
)

function clearAuth() {
  setAccessToken(null)
  localStorage.removeItem("refresh_token")
  window.location.href = "/login"
}
