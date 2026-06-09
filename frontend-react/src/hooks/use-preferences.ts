import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { preferencesApi } from "@/api/preferences"
import type { Preferences } from "@/types"

export const PREFS_KEY = ["preferences"] as const

export function usePreferences() {
  return useQuery({ queryKey: PREFS_KEY, queryFn: preferencesApi.get })
}

export function useUpdatePreferences() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Preferences) => preferencesApi.patch(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: PREFS_KEY }),
  })
}
