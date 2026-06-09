import * as React from "react"
import { login as apiLogin, register as apiRegister, refreshToken, getMe } from "@/api/auth"
import { setAccessToken, getAccessToken } from "@/api/client"
import type { UserRead } from "@/types"

interface AuthContextValue {
  user: UserRead | null
  isAuthenticated: boolean
  isLoading: boolean
  login(email: string, password: string): Promise<void>
  register(email: string, password: string, full_name?: string): Promise<void>
  logout(): void
}

const AuthContext = React.createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<UserRead | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)

  // On mount: attempt to restore session from refresh token
  React.useEffect(() => {
    const stored = localStorage.getItem("refresh_token")
    if (!stored) {
      setIsLoading(false)
      return
    }
    refreshToken(stored)
      .then(async ({ access_token }) => {
        setAccessToken(access_token)
        const me = await getMe(access_token)
        setUser(me)
      })
      .catch(() => {
        localStorage.removeItem("refresh_token")
      })
      .finally(() => setIsLoading(false))
  }, [])

  async function login(email: string, password: string) {
    const tokens = await apiLogin(email, password)
    setAccessToken(tokens.access_token)
    localStorage.setItem("refresh_token", tokens.refresh_token)
    const me = await getMe(tokens.access_token)
    setUser(me)
  }

  async function register(email: string, password: string, full_name?: string) {
    await apiRegister(email, password, full_name)
    await login(email, password)
  }

  function logout() {
    setAccessToken(null)
    localStorage.removeItem("refresh_token")
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!getAccessToken() && !!user,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = React.useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider")
  return ctx
}
