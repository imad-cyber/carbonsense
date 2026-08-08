import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { User } from '@/types/auth'

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  setAuth: (token: string, user: User) => void
  clearAuth: () => void
  hasRole: (roles: string[]) => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,

      setAuth: (token, user) =>
        set({ token, user, isAuthenticated: true }),

      clearAuth: () =>
        set({ token: null, user: null, isAuthenticated: false }),

      hasRole: (roles) => {
        const user = get().user
        return user ? roles.includes(user.role) : false
      },
    }),
    {
      name: 'carbonsense-auth',
      // Only persist the data — not the methods
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
      storage: createJSONStorage(() => localStorage),
    }
  )
)
