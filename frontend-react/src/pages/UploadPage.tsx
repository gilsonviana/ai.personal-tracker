import { useRef, useState } from "react"
import { useAccounts } from "@/hooks/use-accounts"
import { uploadsApi } from "@/api/uploads"
import { fxApi } from "@/api/fx"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Card, CardContent } from "@/components/ui/card"
import { Upload, RefreshCw } from "lucide-react"
import { toast } from "@/hooks/use-toast"
import type { UploadResult } from "@/types"

export default function UploadPage() {
  const { data: accounts } = useAccounts()
  const [accountId, setAccountId] = useState("")
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [syncingFx, setSyncingFx] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    if (!accountId) { toast({ title: "Select an account first", variant: "destructive" }); return }
    setUploading(true)
    setResult(null)
    try {
      const data = await uploadsApi.upload(accountId, file)
      setResult(data)
      toast({ title: `Imported ${data.rows_imported} rows`, description: `${data.transfers_detected} transfer(s) auto-detected` })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Upload failed"
      toast({ title: msg, variant: "destructive" })
    } finally {
      setUploading(false)
    }
  }

  async function syncFx() {
    setSyncingFx(true)
    try {
      const data = await fxApi.sync(result?.import_id)
      toast({ title: `Synced ${data.rates_fetched} exchange rate(s)` })
    } catch {
      toast({ title: "FX sync failed", variant: "destructive" })
    } finally {
      setSyncingFx(false)
    }
  }

  const selectedAccount = accounts?.find((a) => a.id === accountId)

  return (
    <div className="max-w-lg space-y-6">
      <h2 className="text-xl font-semibold">Upload Statement</h2>

      <div className="space-y-4">
        <div className="space-y-1">
          <Label>Account *</Label>
          <Select value={accountId} onValueChange={setAccountId}>
            <SelectTrigger>
              <SelectValue placeholder="Select account…" />
            </SelectTrigger>
            <SelectContent>
              {accounts?.map((a) => (
                <SelectItem key={a.id} value={a.id}>
                  {a.name} {a.bank_name ? `— ${a.bank_name}` : ""} ({a.currency})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Drop zone */}
        <div
          className="border-2 border-dashed rounded-lg p-10 text-center cursor-pointer hover:bg-muted/30 transition-colors"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleFile(f) }}
        >
          <Upload className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">
            Drag & drop a CSV, PDF or TXT file here, or click to browse
          </p>
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept=".csv,.pdf,.txt"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
          />
        </div>

        {uploading && <p className="text-sm text-muted-foreground">Uploading…</p>}

        {result && (
          <Card>
            <CardContent className="pt-4 space-y-2">
              <p className="text-sm"><strong>{result.rows_imported}</strong> transactions imported</p>
              <p className="text-sm"><strong>{result.transfers_detected}</strong> transfer pair(s) auto-detected</p>
              {selectedAccount && selectedAccount.currency !== "BRL" && (
                <div className="pt-2 border-t">
                  <p className="text-xs text-muted-foreground mb-2">
                    Account currency is {selectedAccount.currency}. Sync exchange rates to enable BRL conversion in insights.
                  </p>
                  <Button variant="outline" size="sm" onClick={syncFx} disabled={syncingFx}>
                    <RefreshCw className={`h-4 w-4 mr-2 ${syncingFx ? "animate-spin" : ""}`} />
                    {syncingFx ? "Syncing…" : "Sync exchange rates"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
