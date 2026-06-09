import { apiClient } from "./client"
import type {
  Transaction,
  TransactionPage,
  TransactionFilters,
  TransactionPatch,
  BulkCategoryPatch,
  TransferLinkRequest,
} from "@/types"

function buildParams(filters: TransactionFilters): URLSearchParams {
  const p = new URLSearchParams()
  if (filters.start) p.append("start", filters.start)
  if (filters.end) p.append("end", filters.end)
  if (filters.type) p.append("type", filters.type)
  if (filters.is_transfer !== undefined) p.append("is_transfer", String(filters.is_transfer))
  if (filters.category_id) p.append("category_id", filters.category_id)
  if (filters.search) p.append("search", filters.search)
  if (filters.is_anomaly !== undefined) p.append("is_anomaly", String(filters.is_anomaly))
  if (filters.limit !== undefined) p.append("limit", String(filters.limit))
  if (filters.offset !== undefined) p.append("offset", String(filters.offset))
  filters.account_ids?.forEach((id) => p.append("account_ids", id))
  return p
}

export const transactionsApi = {
  list: (filters: TransactionFilters = {}) =>
    apiClient
      .get<TransactionPage>("/transactions/", { params: buildParams(filters) })
      .then((r) => r.data),

  patch: (id: string, payload: TransactionPatch) =>
    apiClient.patch<Transaction>(`/transactions/${id}`, payload).then((r) => r.data),

  bulkCategory: (payload: BulkCategoryPatch) =>
    apiClient.patch<Transaction[]>("/transactions/bulk-category", payload).then((r) => r.data),

  linkTransfer: (payload: TransferLinkRequest) =>
    apiClient.post<Transaction[]>("/transactions/link-transfer", payload).then((r) => r.data),

  detectTransfers: () =>
    apiClient.post<{ pairs_found: number }>("/transactions/detect-transfers").then((r) => r.data),
}
