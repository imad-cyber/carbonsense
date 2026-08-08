export type UserRole = 'admin' | 'analyst' | 'auditor' | 'supplier'

export interface User {
  id: number
  email: string
  full_name: string | null
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: User
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name?: string
  role: UserRole
}
