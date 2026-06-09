import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { accountsApi } from "@/api/accounts"
import { uploadsApi } from "@/api/uploads"
import type { AccountCreate } from "@/types"

export const ACCOUNTS_KEY = ["accounts"] as const

export function useAccounts() {
  return useQuery({ queryKey: ACCOUNTS_KEY, queryFn: accountsApi.list })
}

export function useAccountImports(accountId: string) {
  return useQuery({
    queryKey: [...ACCOUNTS_KEY, accountId, "imports"],
    queryFn: () => accountsApi.listImports(accountId),
  })
}

export function useCreateAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: AccountCreate) => accountsApi.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ACCOUNTS_KEY }),
  })
}

export function useDeleteAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => accountsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ACCOUNTS_KEY }),
  })
}

export function useDeleteImport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (importId: string) => uploadsApi.deleteImport(importId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ACCOUNTS_KEY }),
  })
}
