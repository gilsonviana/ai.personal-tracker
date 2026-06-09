import { useQuery } from "@tanstack/react-query"
import { insightsApi, type InsightParams } from "@/api/insights"

export function useInsights(params: InsightParams = {}) {
  return useQuery({
    queryKey: ["insights", params],
    queryFn: () => insightsApi.monthly(params),
  })
}
