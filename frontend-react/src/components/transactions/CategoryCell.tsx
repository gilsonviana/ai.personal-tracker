import { useState } from "react"
import * as PopoverPrimitive from "@radix-ui/react-popover"
import { Check, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import { usePatchTransaction } from "@/hooks/use-transactions"
import { toast } from "@/hooks/use-toast"
import type { Category } from "@/types"

interface CategoryCellProps {
  txId: string
  txType: "income" | "expense"
  categoryId: string | null
  categories: Category[]
}

export default function CategoryCell({ txId, txType, categoryId, categories }: CategoryCellProps) {
  const [open, setOpen] = useState(false)
  const patch = usePatchTransaction()
  const filtered = categories.filter((c) => c.type === txType)
  const current = categories.find((c) => c.id === categoryId)

  function handleSelect(id: string | null) {
    setOpen(false)
    patch.mutate({ id: txId, payload: { category_id: id } }, {
      onError: () => toast({ title: "Failed to update category", variant: "destructive" }),
    })
  }

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <PopoverPrimitive.Trigger asChild>
        <button
          className={cn(
            "flex items-center gap-1 text-xs rounded px-1.5 py-0.5 border transition-colors",
            current ? "border-border hover:bg-accent" : "border-dashed border-muted-foreground/40 text-muted-foreground hover:border-border"
          )}
        >
          {current?.name ?? "— none —"}
          <ChevronDown className="h-3 w-3 opacity-50" />
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          className="z-50 w-48 rounded-md border bg-popover shadow-md p-1 text-sm"
          align="start"
          sideOffset={4}
        >
          <button
            className="flex w-full items-center rounded-sm px-2 py-1.5 text-xs text-muted-foreground hover:bg-accent"
            onClick={() => handleSelect(null)}
          >
            <Check className={cn("mr-2 h-3 w-3", categoryId ? "opacity-0" : "opacity-100")} />
            — none —
          </button>
          {filtered.map((c) => (
            <button
              key={c.id}
              className="flex w-full items-center rounded-sm px-2 py-1.5 text-xs hover:bg-accent"
              onClick={() => handleSelect(c.id)}
            >
              <Check className={cn("mr-2 h-3 w-3", c.id === categoryId ? "opacity-100" : "opacity-0")} />
              {c.name}
            </button>
          ))}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
}
