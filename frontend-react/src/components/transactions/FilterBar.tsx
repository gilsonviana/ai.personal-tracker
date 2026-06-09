import { useCallback } from "react"
import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { Account, Category, TransactionFilters } from "@/types"

interface FilterBarProps {
  filters: TransactionFilters
  accounts: Account[]
  categories: Category[]
  onChange: (patch: Partial<TransactionFilters>) => void
}

const TYPE_OPTIONS = [
  { value: "_all", label: "All types" },
  { value: "income", label: "↑ Income" },
  { value: "expense", label: "↓ Expense" },
  { value: "_transfer", label: "↔ Transfers only" },
  { value: "_no_transfer", label: "Non-transfers" },
]

export default function FilterBar({ filters, accounts, categories, onChange }: FilterBarProps) {
  const handleSearch = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onChange({ search: e.target.value || undefined, offset: 0 })
    },
    [onChange]
  )

  function handleType(value: string) {
    if (value === "_all") onChange({ type: undefined, is_transfer: undefined, offset: 0 })
    else if (value === "_transfer") onChange({ type: undefined, is_transfer: true, offset: 0 })
    else if (value === "_no_transfer") onChange({ type: undefined, is_transfer: false, offset: 0 })
    else onChange({ type: value as "income" | "expense", is_transfer: undefined, offset: 0 })
  }

  function currentTypeValue(): string {
    if (filters.is_transfer === true) return "_transfer"
    if (filters.is_transfer === false) return "_no_transfer"
    return filters.type ?? "_all"
  }

  const catOptions = categories.filter((c) => !filters.type || c.type === filters.type)

  return (
    <div className="flex flex-wrap gap-3 items-end pb-4 border-b">
      <div className="space-y-1">
        <Label className="text-xs">From</Label>
        <Input
          type="date"
          className="h-8 text-sm w-36"
          value={filters.start ?? ""}
          onChange={(e) => onChange({ start: e.target.value || undefined, offset: 0 })}
        />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">To</Label>
        <Input
          type="date"
          className="h-8 text-sm w-36"
          value={filters.end ?? ""}
          onChange={(e) => onChange({ end: e.target.value || undefined, offset: 0 })}
        />
      </div>

      <div className="space-y-1">
        <Label className="text-xs">Accounts</Label>
        <Select
          value={filters.account_ids?.[0] ?? "_all"}
          onValueChange={(v) => onChange({ account_ids: v === "_all" ? undefined : [v], offset: 0 })}
        >
          <SelectTrigger className="h-8 text-sm w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">All accounts</SelectItem>
            {accounts.map((a) => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <Label className="text-xs">Type</Label>
        <Select value={currentTypeValue()} onValueChange={handleType}>
          <SelectTrigger className="h-8 text-sm w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            {TYPE_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <Label className="text-xs">Category</Label>
        <Select
          value={filters.category_id ?? "_all"}
          onValueChange={(v) => onChange({ category_id: v === "_all" ? undefined : v, offset: 0 })}
        >
          <SelectTrigger className="h-8 text-sm w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">All categories</SelectItem>
            <SelectItem value="_none">— none —</SelectItem>
            {catOptions.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1 flex-1 min-w-40">
        <Label className="text-xs">Search</Label>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            className="h-8 text-sm pl-7"
            placeholder="Description…"
            defaultValue={filters.search ?? ""}
            onChange={handleSearch}
          />
        </div>
      </div>
    </div>
  )
}
