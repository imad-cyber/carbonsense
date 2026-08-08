import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppLayout } from '@/components/layout/AppLayout'
import { ToastContainer } from '@/components/ui/Toast'
import { LoginPage } from '@/pages/LoginPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { CompaniesPage } from '@/pages/CompaniesPage'
import { EmissionsPage } from '@/pages/EmissionsPage'
import { PredictionsPage } from '@/pages/PredictionsPage'
import { ChatPage } from '@/pages/ChatPage'
import { ReportsPage } from '@/pages/ReportsPage'
import { AdminPage } from '@/pages/AdminPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { useAuthStore } from '@/store/authStore'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

/** Guards routes that only specific roles may access. */
function RoleGuard({ roles, children }: { roles: string[]; children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  if (!user || !roles.includes(user.role)) return <Navigate to="/dashboard" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route
              path="/companies"
              element={
                <RoleGuard roles={['admin', 'analyst', 'auditor']}>
                  <CompaniesPage />
                </RoleGuard>
              }
            />
            <Route path="/emissions" element={<EmissionsPage />} />
            <Route
              path="/predictions"
              element={
                <RoleGuard roles={['admin', 'analyst', 'auditor']}>
                  <PredictionsPage />
                </RoleGuard>
              }
            />
            <Route
              path="/chat"
              element={
                <RoleGuard roles={['admin', 'analyst', 'auditor']}>
                  <ChatPage />
                </RoleGuard>
              }
            />
            <Route
              path="/reports"
              element={
                <RoleGuard roles={['admin', 'analyst', 'auditor']}>
                  <ReportsPage />
                </RoleGuard>
              }
            />
            <Route
              path="/admin"
              element={
                <RoleGuard roles={['admin']}>
                  <AdminPage />
                </RoleGuard>
              }
            />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
      <ToastContainer />
    </QueryClientProvider>
  )
}
