import { useMemo, useState } from "react"
import { AlertTriangle, ChevronLeft, ChevronRight } from "lucide-react"
import { useTransactions } from "@/hooks/use-transactions"
import { useAccounts } from "@/hooks/use-accounts"
import { useCategories } from "@/hooks/use-categories"
import FilterBar from "@/components/transactions/FilterBar"
import ActionPanel from "@/components/transactions/ActionPanel"
import CategoryCell from "@/components/transactions/CategoryCell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { formatCurrency, formatDate } from "@/lib/utils"
import type { Transaction, TransactionFilters } from "@/types"

const PAGE_SIZE = 25

function defaultFilters(): TransactionFilters {
  const today = new Date()
  const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1)
  const lastOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0)
  return {
    start: firstOfMonth.toISOString().slice(0, 10),
    end: lastOfMonth.toISOString().slice(0, 10),
    limit: PAGE_SIZE,
    offset: 0,
  }
}

function TypeBadge({ tx }: { tx: Transaction }) {
  if (tx.is_transfer) return <Badge variant="transfer">↔ Transfer</Badge>
  if (tx.type === "income") return <Badge variant="income">↑ Income</Badge>
  return <Badge variant="expense">↓ Expense</Badge>
}

export default function TransactionsPage() {
  const [filters, setFilters] = useState<TransactionFilters>(defaultFilters)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const { data, isLoading } = useTransactions(filters)
  const { data: accounts } = useAccounts()
  const { data: categories } = useCategories()

  const accountMap = useMemo(
    () => Object.fromEntries((accounts ?? []).map((a) => [a.id, { name: a.name, currency: a.currency }])),
    [accounts]
  )

  const catMap = useMemo(
    () => Object.fromEntries((categories ?? []).map((c) => [c.id, c.name])),
    [categories]
  )

  // Build transfer pair map for direction display
  const pairMap = useMemo(() => {
    const m: Record<string, Transaction[]> = {}
    data?.items.forEach((tx) => {
      if (tx.transfer_pair_id) {
        m[tx.transfer_pair_id] ??= []
        m[tx.transfer_pair_id].push(tx)
      }
    })
    return m
  }, [data?.items])

  function transferDir(tx: Transaction): string {
    if (!tx.is_transfer || !tx.transfer_pair_id) return ""
    const legs = pairMap[tx.transfer_pair_id] ?? []
    const src = legs.find((l) => l.type === "expense")
    const dst = legs.find((l) => l.type === "income")
    const srcName = accountMap[src?.bank_account_id ?? ""]?.name ?? "?"
    const dstName = accountMap[dst?.bank_account_id ?? ""]?.name ?? "?"
    return `${srcName} → ${dstName}`
  }

  function patchFilters(patch: Partial<TransactionFilters>) {
    setFilters((f) => ({ ...f, ...patch }))
  }

  function toggleRow(id: string) {
    setSelected((s) => {
      const next = new Set(s)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleAll() {
    const ids = data?.items.map((t) => t.id) ?? []
    setSelected((s) => s.size === ids.length ? new Set() : new Set(ids))
  }

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const offset = filters.offset ?? 0
  const page = Math.floor(offset / PAGE_SIZE) + 1
  const pageCount = Math.ceil(total / PAGE_SIZE)

  const selectedTxs = items.filter((t) => selected.has(t.id))

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Transactions</h2>

      <FilterBar
        filters={filters}
        accounts={accounts ?? []}
        categories={categories ?? []}
        onChange={patchFilters}
      />

      {selectedTxs.length > 0 && (
        <ActionPanel
          selected={selectedTxs}
          accountMap={accountMap}
          onClear={() => setSelected(new Set())}
        />
      )}

      {isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}

      <div className="border rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-muted-foreground">
            <tr>
              <th className="px-3 py-2 w-8">
                <Checkbox
                  checked={items.length > 0 && selected.size === items.length}
                  onCheckedChange={toggleAll}
                />
              </th>
              <th className="px-3 py-2 text-left font-medium">Date</th>
              <th className="px-3 py-2 text-left font-medium">Account</th>
              <th className="px-3 py-2 text-left font-medium">Description</th>
              <th className="px-3 py-2 text-right font-medium">Amount</th>
              <th className="px-3 py-2 text-left font-medium">Type</th>
              <th className="px-3 py-2 text-left font-medium">Category</th>
              <th className="px-3 py-2 text-left font-medium">Transfer</th>
              <th className="px-3 py-2 w-6" />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !isLoading && (
              <tr><td colSpan={9} className="text-center py-8 text-muted-foreground">No transactions found.</td></tr>
            )}
            {items.map((tx) => {
              const acc = accountMap[tx.bank_account_id]
              const isSelected = selected.has(tx.id)
              return (
                <tr
                  key={tx.id}
                  className={`border-t cursor-pointer transition-colors ${isSelected ? "bg-primary/5" : "hover:bg-muted/30"}`}
                  onClick={() => toggleRow(tx.id)}
                >
                  <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                    <Checkbox checked={isSelected} onCheckedChange={() => toggleRow(tx.id)} />
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatDate(tx.date)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{acc?.name ?? "?"}</td>
                  <td className="px-3 py-2 max-w-xs truncate">{tx.description}</td>
                  <td className="px-3 py-2 text-right whitespace-nowrap font-mono">
                    {formatCurrency(tx.amount, acc?.currency ?? "BRL")}
                  </td>
                  <td className="px-3 py-2"><TypeBadge tx={tx} /></td>
                  <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                    <CategoryCell
                      txId={tx.id}
                      txType={tx.type}
                      categoryId={tx.category_id}
                      categories={categories ?? []}
                    />
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">
                    {transferDir(tx)}
                  </td>
                  <td className="px-3 py-2">
                    {tx.is_anomaly && (
                      <AlertTriangle className="h-3.5 w-3.5 text-amber-500" aria-label="Anomaly detected" />
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination + count */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <p>{total} transaction{total !== 1 ? "s" : ""}</p>
        {pageCount > 1 && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline" size="icon"
              disabled={page <= 1}
              onClick={() => patchFilters({ offset: Math.max(0, offset - PAGE_SIZE) })}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span>Page {page} of {pageCount}</span>
            <Button
              variant="outline" size="icon"
              disabled={page >= pageCount}
              onClick={() => patchFilters({ offset: offset + PAGE_SIZE })}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
