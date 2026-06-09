import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Trash2, BrainCircuit } from "lucide-react"
import { useCategories, useCreateCategory, useDeleteCategory, usePatchCategory, useRetrainCategoriser } from "@/hooks/use-categories"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { toast } from "@/hooks/use-toast"

const schema = z.object({
  name: z.string().min(1, "Required"),
  type: z.enum(["income", "expense"]),
})
type FormValues = z.infer<typeof schema>

export default function CategoriesPage() {
  const { data: categories, isLoading } = useCategories()
  const create = useCreateCategory()
  const deleteCategory = useDeleteCategory()
  const patchCategory = usePatchCategory()
  const retrain = useRetrainCategoriser()
  const [showForm, setShowForm] = useState(false)

  const { register, handleSubmit, setValue, watch, reset, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { type: "expense" },
  })

  async function onSubmit(values: FormValues) {
    await create.mutateAsync(values, {
      onSuccess: () => { toast({ title: "Category created" }); reset(); setShowForm(false) },
      onError: (err: unknown) => {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed"
        toast({ title: msg, variant: "destructive" })
      },
    })
  }

  async function handleRetrain() {
    await retrain.mutateAsync(undefined, {
      onSuccess: (r) => toast({ title: `Model trained on ${r.samples_used} transactions`, description: r.classes.join(", ") }),
      onError: (err: unknown) => {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Retrain failed"
        toast({ title: msg, variant: "destructive" })
      },
    })
  }

  return (
    <div className="max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Categories</h2>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleRetrain} disabled={retrain.isPending}>
            <BrainCircuit className="h-4 w-4 mr-1" />
            {retrain.isPending ? "Training…" : "Retrain model"}
          </Button>
          <Button size="sm" onClick={() => setShowForm((s) => !s)}>
            <Plus className="h-4 w-4 mr-1" /> New
          </Button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit(onSubmit)} className="flex gap-2 items-end border rounded-lg p-4">
          <div className="flex-1 space-y-1">
            <Label>Name</Label>
            <Input placeholder="e.g. Groceries" {...register("name")} />
            {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
          </div>
          <div className="w-36 space-y-1">
            <Label>Type</Label>
            <Select value={watch("type")} onValueChange={(v) => setValue("type", v as "income" | "expense")}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="expense">Expense</SelectItem>
                <SelectItem value="income">Income</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" disabled={isSubmitting}>Add</Button>
          <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
        </form>
      )}

      {isLoading && <p className="text-muted-foreground">Loading…</p>}

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr className="text-left text-muted-foreground">
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Type</th>
              <th className="px-4 py-2 font-medium">Source</th>
              <th className="px-4 py-2 font-medium">In insights</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {categories?.map((cat) => (
              <tr key={cat.id} className="border-t hover:bg-muted/30">
                <td className="px-4 py-2">{cat.name}</td>
                <td className="px-4 py-2">
                  <Badge variant={cat.type === "income" ? "income" : "expense"}>{cat.type}</Badge>
                </td>
                <td className="px-4 py-2">
                  <Badge variant="outline">{cat.user_id ? "Custom" : "System"}</Badge>
                </td>
                <td className="px-4 py-2">
                  <Checkbox
                    checked={!cat.exclude_from_insights}
                    onCheckedChange={(checked) =>
                      patchCategory.mutate({ id: cat.id, exclude_from_insights: !checked })
                    }
                  />
                </td>
                <td className="px-4 py-2">
                  {cat.user_id && (
                    <Button
                      variant="ghost" size="icon"
                      onClick={() => {
                        if (confirm(`Delete category "${cat.name}"?`)) {
                          deleteCategory.mutate(cat.id, {
                            onSuccess: () => toast({ title: "Category deleted" }),
                            onError: () => toast({ title: "Failed", variant: "destructive" }),
                          })
                        }
                      }}
                    >
                      <Trash2 className="h-3 w-3 text-destructive" />
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
