import { apiClient } from "./client"
import type { Preferences } from "@/types"

export const preferencesApi = {
  get: () => apiClient.get<Preferences>("/preferences/").then((r) => r.data),
  patch: (payload: Preferences) =>
    apiClient.patch<Preferences>("/preferences/", payload).then((r) => r.data),
}
