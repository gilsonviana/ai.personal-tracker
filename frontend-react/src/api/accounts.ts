import { apiClient } from "./client"
import type { Account, AccountCreate, AccountImport } from "@/types"

export const accountsApi = {
  list: () => apiClient.get<Account[]>("/accounts/").then((r) => r.data),

  create: (payload: AccountCreate) =>
    apiClient.post<Account>("/accounts/", payload).then((r) => r.data),

  delete: (id: string) => apiClient.delete(`/accounts/${id}`),

  listImports: (accountId: string) =>
    apiClient.get<AccountImport[]>(`/accounts/${accountId}/imports`).then((r) => r.data),
}
