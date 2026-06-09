import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { usePreferences, useUpdatePreferences } from "@/hooks/use-preferences"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { toast } from "@/hooks/use-toast"

const CURRENCIES = ["BRL", "USD", "EUR", "GBP", "ARS"]

const schema = z.object({ main_currency: z.string() })
type FormValues = z.infer<typeof schema>

export default function PreferencesPage() {
  const { data, isLoading } = usePreferences()
  const update = useUpdatePreferences()
  const { handleSubmit, setValue, watch } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { main_currency: "BRL" },
  })

  useEffect(() => {
    if (data) setValue("main_currency", data.main_currency)
  }, [data, setValue])

  async function onSubmit(values: FormValues) {
    await update.mutateAsync(values)
    toast({ title: "Preferences saved" })
  }

  if (isLoading) return <p className="text-muted-foreground">Loading…</p>

  return (
    <div className="max-w-sm">
      <h2 className="text-xl font-semibold mb-4">Preferences</h2>
      <Card>
        <CardHeader><CardTitle className="text-base">Display Currency</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1">
              <Label>Main currency</Label>
              <Select value={watch("main_currency")} onValueChange={(v) => setValue("main_currency", v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CURRENCIES.map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Save"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
