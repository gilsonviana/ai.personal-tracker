import axios from "axios"
import { BASE_URL } from "./client"
import type { TokenPair, AccessToken, UserRead } from "@/types"

// Uses bare axios (no auth header) for auth endpoints
const authAxios = axios.create({ baseURL: BASE_URL })

export async function login(email: string, password: string): Promise<TokenPair> {
  const form = new URLSearchParams({ username: email, password })
  const { data } = await authAxios.post<TokenPair>("/auth/jwt/token", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  })
  return data
}

export async function register(email: string, password: string, full_name?: string): Promise<UserRead> {
  const { data } = await authAxios.post<UserRead>("/auth/register", { email, password, full_name })
  return data
}

export async function refreshToken(refresh_token: string): Promise<AccessToken> {
  const { data } = await authAxios.post<AccessToken>("/auth/jwt/refresh", { refresh_token })
  return data
}

export async function getMe(token: string): Promise<UserRead> {
  const { data } = await authAxios.get<UserRead>("/users/me", {
    headers: { Authorization: `Bearer ${token}` },
  })
  return data
}
