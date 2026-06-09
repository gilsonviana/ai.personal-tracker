import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { categoriesApi } from "@/api/categories"
import type { CategoryCreate } from "@/types"

export const CATEGORIES_KEY = ["categories"] as const

export function useCategories() {
  return useQuery({ queryKey: CATEGORIES_KEY, queryFn: categoriesApi.list })
}

export function useCreateCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CategoryCreate) => categoriesApi.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: CATEGORIES_KEY }),
  })
}

export function usePatchCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, exclude_from_insights }: { id: string; exclude_from_insights: boolean }) =>
      categoriesApi.patch(id, { exclude_from_insights }),
    onSuccess: () => qc.invalidateQueries({ queryKey: CATEGORIES_KEY }),
  })
}

export function useDeleteCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => categoriesApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: CATEGORIES_KEY }),
  })
}

export function useRetrainCategoriser() {
  return useMutation({ mutationFn: categoriesApi.retrain })
}
