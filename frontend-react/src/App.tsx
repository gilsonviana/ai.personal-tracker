import { Navigate, Route, Routes } from "react-router-dom"
import { useAuth } from "@/lib/auth-context"
import AppLayout from "@/components/layout/AppLayout"
import LoginPage from "@/pages/LoginPage"
import RegisterPage from "@/pages/RegisterPage"
import AccountsPage from "@/pages/AccountsPage"
import UploadPage from "@/pages/UploadPage"
import TransactionsPage from "@/pages/TransactionsPage"
import CategoriesPage from "@/pages/CategoriesPage"
import InsightsPage from "@/pages/InsightsPage"
import PreferencesPage from "@/pages/PreferencesPage"

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  if (isLoading) return <div className="min-h-screen flex items-center justify-center text-muted-foreground">Loading…</div>
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/transactions" replace />} />
        <Route path="/accounts" element={<AccountsPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/transactions" element={<TransactionsPage />} />
        <Route path="/categories" element={<CategoriesPage />} />
        <Route path="/insights" element={<InsightsPage />} />
        <Route path="/preferences" element={<PreferencesPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
