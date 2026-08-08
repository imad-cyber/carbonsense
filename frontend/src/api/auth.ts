import { apiClient } from './client'
import type { LoginRequest, RegisterRequest, TokenResponse, User } from '@/types/auth'

export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<TokenResponse>('/auth/login', data).then(r => r.data),

  register: (data: RegisterRequest) =>
    apiClient.post<User>('/auth/register', data).then(r => r.data),

  getMe: () =>
    apiClient.get<User>('/auth/me').then(r => r.data),
}
