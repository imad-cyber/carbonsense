import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/store/authStore'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

// Request interceptor — attach JWT token to every request automatically
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor — handle 401 globally (token expired)
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token expired or invalid — clear auth and redirect to login
      const { isAuthenticated, clearAuth } = useAuthStore.getState()
      if (isAuthenticated) {
        clearAuth()
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// Helper to extract error message from API error responses
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { detail?: string | Array<{ msg?: string }> }
      | undefined
    if (typeof data?.detail === 'string') return data.detail
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d) => d.msg).filter(Boolean).join('; ') || error.message
    }
    return error.message
  }
  if (error instanceof Error) return error.message
  return 'An unexpected error occurred'
}

export { BASE_URL }
