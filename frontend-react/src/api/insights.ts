import { apiClient } from "./client"
import type { InsightResponse } from "@/types"

export interface InsightParams {
  account_id?: string
  year?: number
  month?: number
}

export const insightsApi = {
  monthly: (params: InsightParams = {}) =>
    apiClient.get<InsightResponse>("/insights/monthly", { params }).then((r) => r.data),
}
