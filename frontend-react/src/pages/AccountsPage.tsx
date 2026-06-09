import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { ChevronDown, ChevronRight, Trash2, Plus } from "lucide-react"
import { useAccounts, useAccountImports, useCreateAccount, useDeleteAccount, useDeleteImport } from "@/hooks/use-accounts"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { formatDate } from "@/lib/utils"
import { toast } from "@/hooks/use-toast"
import type { Account } from "@/types"

const schema = z.object({
  name: z.string().min(1, "Required"),
  bank_name: z.string().optional(),
  currency: z.string(),
})
type FormValues = z.infer<typeof schema>

function AccountRow({ account }: { account: Account }) {
  const [open, setOpen] = useState(false)
  const { data: imports } = useAccountImports(open ? account.id : "")
  const deleteAccount = useDeleteAccount()
  const deleteImport = useDeleteImport()

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <button className="flex items-center gap-2 text-left" onClick={() => setOpen((o) => !o)}>
            {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            <div>
              <p className="font-medium">{account.name}</p>
              {account.bank_name && <p className="text-xs text-muted-foreground">{account.bank_name}</p>}
            </div>
          </button>
          <div className="flex items-center gap-2">
            <Badge variant="outline">{account.currency}</Badge>
            <Button
              variant="ghost" size="icon"
              onClick={() => {
                if (confirm(`Delete account "${account.name}"? All its transactions will be removed.`)) {
                  deleteAccount.mutate(account.id, {
                    onSuccess: () => toast({ title: "Account deleted" }),
                    onError: () => toast({ title: "Failed to delete account", variant: "destructive" }),
                  })
                }
              }}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        </div>
      </CardHeader>

      {open && (
        <CardContent>
          {!imports ? (
            <p className="text-xs text-muted-foreground">Loading…</p>
          ) : imports.length === 0 ? (
            <p className="text-xs text-muted-foreground">No imports yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="pb-1 font-medium">File</th>
                  <th className="pb-1 font-medium">Rows</th>
                  <th className="pb-1 font-medium">Uploaded</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {imports.map((imp) => (
                  <tr key={imp.id} className="border-t">
                    <td className="py-1.5 pr-4">{imp.filename}</td>
                    <td className="py-1.5 pr-4">{imp.row_count}</td>
                    <td className="py-1.5 pr-4">{formatDate(imp.created_at.slice(0, 10))}</td>
                    <td className="py-1.5">
                      <Button
                        variant="ghost" size="icon"
                        onClick={() => {
                          if (confirm(`Delete import "${imp.filename}"?`)) {
                            deleteImport.mutate(imp.id, {
                              onSuccess: () => toast({ title: "Import deleted" }),
                              onError: () => toast({ title: "Failed", variant: "destructive" }),
                            })
                          }
                        }}
                      >
                        <Trash2 className="h-3 w-3 text-destructive" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      )}
    </Card>
  )
}

function NewAccountDialog() {
  const [open, setOpen] = useState(false)
  const createAccount = useCreateAccount()
  const { register, handleSubmit, setValue, watch, reset, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { currency: "BRL" },
  })

  async function onSubmit(values: FormValues) {
    await createAccount.mutateAsync(values, {
      onSuccess: () => {
        toast({ title: "Account created" })
        reset()
        setOpen(false)
      },
      onError: () => toast({ title: "Failed to create account", variant: "destructive" }),
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button><Plus className="h-4 w-4 mr-1" /> New account</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New bank account</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 mt-2">
          <div className="space-y-1">
            <Label>Account name *</Label>
            <Input placeholder="e.g. Itaú Checking" {...register("name")} />
            {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
          </div>
          <div className="space-y-1">
            <Label>Bank name</Label>
            <Input placeholder="e.g. Itaú" {...register("bank_name")} />
          </div>
          <div className="space-y-1">
            <Label>Currency</Label>
            <Select value={watch("currency")} onValueChange={(v) => setValue("currency", v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {["BRL", "USD", "EUR", "GBP", "ARS"].map((c) => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Creating…" : "Create account"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function AccountsPage() {
  const { data: accounts, isLoading } = useAccounts()

  return (
    <div className="max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Accounts</h2>
        <NewAccountDialog />
      </div>
      {isLoading && <p className="text-muted-foreground">Loading…</p>}
      {accounts?.length === 0 && <p className="text-muted-foreground">No accounts yet.</p>}
      {accounts?.map((acc) => <AccountRow key={acc.id} account={acc} />)}
    </div>
  )
}
