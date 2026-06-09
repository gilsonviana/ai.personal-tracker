import { useState } from "react"
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts"
import { RefreshCw, AlertTriangle } from "lucide-react"
import { useInsights } from "@/hooks/use-insights"
import { fxApi } from "@/api/fx"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { formatCurrency } from "@/lib/utils"
import { toast } from "@/hooks/use-toast"

type Mode = "last12" | "year" | "month"

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
const YEARS = Array.from({ length: 5 }, (_, i) => String(new Date().getFullYear() - i))

function ScoreCard({ score }: { score: number }) {
  const color = score >= 70 ? "text-green-600" : score >= 40 ? "text-amber-500" : "text-red-600"
  const label = score >= 70 ? "Healthy" : score >= 40 ? "Fair" : "Needs attention"
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-muted-foreground">Financial Health Score</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={`text-5xl font-bold ${color}`}>{Math.round(score)}</div>
        <p className={`text-sm mt-1 ${color}`}>{label}</p>
        <div className="w-full bg-muted rounded-full h-2 mt-3">
          <div className="h-2 rounded-full bg-current transition-all" style={{ width: `${score}%` }} />
        </div>
      </CardContent>
    </Card>
  )
}

function parseNarrative(text: string): { analysis: string; nextSteps: string[] } {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean)
  const stepIdx = lines.findIndex((l) => /next.?step/i.test(l))
  const analysis = stepIdx > 0 ? lines.slice(0, stepIdx).join(" ") : text
  const steps = stepIdx >= 0 ? lines.slice(stepIdx + 1).filter((l) => /^\d+\./.test(l)).map((l) => l.replace(/^\d+\.\s*/, "")) : []
  return { analysis, nextSteps: steps }
}

export default function InsightsPage() {
  const [mode, setMode] = useState<Mode>("last12")
  const [year, setYear] = useState(String(new Date().getFullYear()))
  const [month, setMonth] = useState(String(new Date().getMonth() + 1))
  const [syncingFx, setSyncingFx] = useState(false)

  const params = mode === "last12" ? {} : mode === "year" ? { year: Number(year) } : { year: Number(year), month: Number(month) }
  const { data, isLoading, error } = useInsights(params)

  async function syncFx() {
    setSyncingFx(true)
    try {
      const r = await fxApi.sync()
      toast({ title: `Synced ${r.rates_fetched} exchange rate(s)` })
    } catch {
      toast({ title: "FX sync failed", variant: "destructive" })
    } finally {
      setSyncingFx(false)
    }
  }

  const chartData = data?.summaries.map((s) => ({
    period: s.period,
    Income: s.total_income / 100,
    Expenses: s.total_expenses / 100,
    Net: s.net / 100,
  })) ?? []

  const currency = data?.main_currency ?? "BRL"
  const narrative = data?.narrative ? parseNarrative(data.narrative) : null

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Insights</h2>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-4 items-end">
        <div className="space-y-1">
          <Label>Period</Label>
          <Select value={mode} onValueChange={(v) => setMode(v as Mode)}>
            <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="last12">Last 12 months</SelectItem>
              <SelectItem value="year">Full year</SelectItem>
              <SelectItem value="month">Specific month</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {(mode === "year" || mode === "month") && (
          <div className="space-y-1">
            <Label>Year</Label>
            <Select value={year} onValueChange={setYear}>
              <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
              <SelectContent>
                {YEARS.map((y) => <SelectItem key={y} value={y}>{y}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}
        {mode === "month" && (
          <div className="space-y-1">
            <Label>Month</Label>
            <Select value={month} onValueChange={setMonth}>
              <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
              <SelectContent>
                {MONTHS.map((m, i) => <SelectItem key={i + 1} value={String(i + 1)}>{m}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      {data?.has_unconverted && (
        <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>Some transactions could not be converted — exchange rates may be missing.</span>
          <Button variant="outline" size="sm" className="ml-auto" onClick={syncFx} disabled={syncingFx}>
            <RefreshCw className={`h-4 w-4 mr-1 ${syncingFx ? "animate-spin" : ""}`} />
            Fetch rates
          </Button>
        </div>
      )}

      {isLoading && <p className="text-muted-foreground">Loading…</p>}
      {error && <p className="text-destructive">Failed to load insights.</p>}

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <ScoreCard score={data.score} />

          {/* Period totals */}
          {data.summaries.length === 1 && (
            <>
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Total Income</CardTitle></CardHeader>
                <CardContent><p className="text-2xl font-semibold text-green-600">{formatCurrency(data.summaries[0].total_income, currency)}</p></CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Total Expenses</CardTitle></CardHeader>
                <CardContent><p className="text-2xl font-semibold text-red-600">{formatCurrency(data.summaries[0].total_expenses, currency)}</p></CardContent>
              </Card>
            </>
          )}
        </div>
      )}

      {/* Bar chart */}
      {chartData.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Income vs Expenses</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                <Tooltip formatter={(value) => formatCurrency((Number(value) ?? 0) * 100, currency)} />
                <Legend />
                <Bar dataKey="Income" fill="#22c55e" radius={[2, 2, 0, 0]} />
                <Bar dataKey="Expenses" fill="#ef4444" radius={[2, 2, 0, 0]} />
                <Line type="monotone" dataKey="Net" stroke="#f59e0b" strokeWidth={2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* LLM narrative */}
      {narrative && (
        <Card>
          <CardHeader><CardTitle>Analysis</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground leading-relaxed">{narrative.analysis}</p>
            {narrative.nextSteps.length > 0 && (
              <div>
                <p className="text-sm font-medium mb-2">Next Steps</p>
                <ol className="list-decimal list-inside space-y-1">
                  {narrative.nextSteps.map((step, i) => (
                    <li key={i} className="text-sm text-muted-foreground">{step}</li>
                  ))}
                </ol>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
