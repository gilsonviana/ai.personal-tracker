import { apiClient } from "./client"
import type { UploadResult } from "@/types"

export const uploadsApi = {
  upload: (accountId: string, file: File) => {
    const form = new FormData()
    form.append("file", file)
    return apiClient.post<UploadResult>(`/uploads/${accountId}`, form).then((r) => r.data)
  },

  deleteImport: (importId: string) => apiClient.delete(`/uploads/${importId}`),
}
