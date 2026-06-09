import { NavLink, useNavigate } from "react-router-dom"
import {
  LayoutDashboard,
  CreditCard,
  Upload,
  ArrowLeftRight,
  Tags,
  Settings,
  LogOut,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { Button } from "@/components/ui/button"

const NAV = [
  { to: "/insights", label: "Insights", icon: LayoutDashboard },
  { to: "/accounts", label: "Accounts", icon: CreditCard },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/transactions", label: "Transactions", icon: ArrowLeftRight },
  { to: "/categories", label: "Categories", icon: Tags },
  { to: "/preferences", label: "Preferences", icon: Settings },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate("/login", { replace: true })
  }

  return (
    <aside className="flex flex-col w-56 min-h-screen border-r bg-card px-3 py-4">
      <div className="mb-6 px-3">
        <h1 className="text-lg font-semibold text-foreground">FInSight</h1>
        {user?.email && (
          <p className="text-xs text-muted-foreground truncate">{user.email}</p>
        )}
      </div>

      <nav className="flex flex-col gap-1 flex-1">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      <Button variant="ghost" size="sm" className="justify-start gap-3 text-muted-foreground" onClick={handleLogout}>
        <LogOut className="h-4 w-4" />
        Sign out
      </Button>
    </aside>
  )
}
