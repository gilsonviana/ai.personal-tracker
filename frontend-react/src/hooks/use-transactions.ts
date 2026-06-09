import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { transactionsApi } from "@/api/transactions"
import type { BulkCategoryPatch, TransactionFilters, TransactionPatch, TransferLinkRequest } from "@/types"

export const TX_KEY = "transactions"

export function useTransactions(filters: TransactionFilters) {
  return useQuery({
    queryKey: [TX_KEY, filters],
    queryFn: () => transactionsApi.list(filters),
  })
}

export function usePatchTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TransactionPatch }) =>
      transactionsApi.patch(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [TX_KEY] }),
  })
}

export function useBulkCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: BulkCategoryPatch) => transactionsApi.bulkCategory(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [TX_KEY] }),
  })
}

export function useLinkTransfer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: TransferLinkRequest) => transactionsApi.linkTransfer(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [TX_KEY] }),
  })
}

export function useDetectTransfers() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: transactionsApi.detectTransfers,
    onSuccess: () => qc.invalidateQueries({ queryKey: [TX_KEY] }),
  })
}
