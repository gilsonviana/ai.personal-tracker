import { apiClient } from "./client"
import type { SyncResult } from "@/types"

export const fxApi = {
  sync: (importId?: string) =>
    apiClient
      .post<SyncResult>("/fx/sync", null, { params: importId ? { import_id: importId } : {} })
      .then((r) => r.data),
}
