import { useState } from "react"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useBulkCategory, useLinkTransfer, usePatchTransaction, useDetectTransfers } from "@/hooks/use-transactions"
import { useCategories } from "@/hooks/use-categories"
import { toast } from "@/hooks/use-toast"
import type { Transaction } from "@/types"

interface ActionPanelProps {
  selected: Transaction[]
  accountMap: Record<string, { name: string; currency: string }>
  onClear: () => void
}

export default function ActionPanel({ selected, accountMap, onClear }: ActionPanelProps) {
  const { data: categories } = useCategories()
  const bulkCategory = useBulkCategory()
  const linkTransfer = useLinkTransfer()
  const patchTx = usePatchTransaction()
  const detectTransfers = useDetectTransfers()
  const [bulkCatId, setBulkCatId] = useState<string>("_none")

  const n = selected.length
  if (n === 0) return null

  const transfers = selected.filter((t) => t.is_transfer)
  const nonTransfers = selected.filter((t) => !t.is_transfer)
  const expenses = nonTransfers.filter((t) => t.type === "expense")
  const incomes = nonTransfers.filter((t) => t.type === "income")

  const canLink = n >= 2 && transfers.length === 0 && expenses.length >= 1 && incomes.length === 1
  const canUnlink = n === 1 && transfers.length === 1

  async function handleBulkCategory() {
    if (!bulkCatId || bulkCatId === "_none") return
    const ids = nonTransfers.map((t) => t.id)
    await bulkCategory.mutateAsync({ transaction_ids: ids, category_id: bulkCatId === "__none" ? null : bulkCatId }, {
      onSuccess: () => { toast({ title: `Category applied to ${ids.length} transaction(s)` }); onClear() },
      onError: () => toast({ title: "Failed", variant: "destructive" }),
    })
  }

  async function handleLink() {
    await linkTransfer.mutateAsync(
      { expense_ids: expenses.map((t) => t.id), income_id: incomes[0].id },
      {
        onSuccess: () => { toast({ title: "Linked as transfer" }); onClear() },
        onError: (err: unknown) => {
          const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed"
          toast({ title: msg, variant: "destructive" })
        },
      }
    )
  }

  async function handleUnlink() {
    await patchTx.mutateAsync(
      { id: selected[0].id, payload: { is_transfer: false } },
      {
        onSuccess: () => { toast({ title: "Transfer unlinked" }); onClear() },
        onError: () => toast({ title: "Failed", variant: "destructive" }),
      }
    )
  }

  const catOptions = categories ?? []
  const mixedTypes = new Set(nonTransfers.map((t) => t.type)).size > 1
  const filteredCats = mixedTypes ? catOptions : catOptions.filter((c) => !nonTransfers[0] || c.type === nonTransfers[0].type)

  return (
    <div className="border rounded-lg p-4 bg-muted/30 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">{n} row{n !== 1 ? "s" : ""} selected</p>
        <Button variant="ghost" size="icon" onClick={onClear}><X className="h-4 w-4" /></Button>
      </div>

      {/* Selected row summary */}
      <div className="space-y-1 max-h-24 overflow-y-auto">
        {selected.map((tx) => {
          const acc = accountMap[tx.bank_account_id]
          return (
            <p key={tx.id} className="text-xs text-muted-foreground">
              {tx.date} · {acc?.name ?? "?"} · {tx.type === "income" ? "↑" : "↓"} {(tx.amount / 100).toFixed(2)} · {tx.description.slice(0, 40)}
            </p>
          )
        })}
      </div>

      <div className="flex flex-wrap gap-2 items-end pt-1 border-t">
        {/* Link as Transfer */}
        {canLink && (
          <Button size="sm" onClick={handleLink} disabled={linkTransfer.isPending}>
            {linkTransfer.isPending ? "Linking…" : "Link as Transfer"}
          </Button>
        )}
        {n >= 2 && !canLink && transfers.length === 0 && (
          <p className="text-xs text-muted-foreground">
            {incomes.length !== 1 ? "Select exactly 1 income" : "Select at least 1 expense"}
          </p>
        )}

        {/* Unlink */}
        {canUnlink && (
          <Button variant="outline" size="sm" onClick={handleUnlink} disabled={patchTx.isPending}>
            Unlink transfer
          </Button>
        )}

        {/* Bulk category */}
        {nonTransfers.length > 0 && (
          <div className="flex gap-2 items-center">
            <Select value={bulkCatId} onValueChange={setBulkCatId}>
              <SelectTrigger className="h-8 text-sm w-44"><SelectValue placeholder="Assign category…" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— remove category —</SelectItem>
                {filteredCats.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button size="sm" variant="secondary" onClick={handleBulkCategory} disabled={bulkCategory.isPending || bulkCatId === "_none"}>
              Apply
            </Button>
          </div>
        )}

        {/* Detect transfers */}
        <Button
          variant="ghost" size="sm"
          onClick={() => detectTransfers.mutate(undefined, {
            onSuccess: (r) => toast({ title: `${r.pairs_found} transfer pair(s) detected` }),
          })}
          disabled={detectTransfers.isPending}
        >
          Auto-detect transfers
        </Button>
      </div>
    </div>
  )
}
