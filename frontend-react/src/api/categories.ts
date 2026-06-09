import { apiClient } from "./client"
import type { Category, CategoryCreate, RetrainResult } from "@/types"

export const categoriesApi = {
  list: () => apiClient.get<Category[]>("/categories/").then((r) => r.data),

  create: (payload: CategoryCreate) =>
    apiClient.post<Category>("/categories/", payload).then((r) => r.data),

  patch: (id: string, payload: { exclude_from_insights: boolean }) =>
    apiClient.patch<Category>(`/categories/${id}`, payload).then((r) => r.data),

  delete: (id: string) => apiClient.delete(`/categories/${id}`),

  retrain: () => apiClient.post<RetrainResult>("/categories/retrain").then((r) => r.data),
}
