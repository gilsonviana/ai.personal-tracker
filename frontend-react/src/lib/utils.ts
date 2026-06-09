import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  BRL: "R$",
  USD: "US$",
  EUR: "€",
  GBP: "£",
  ARS: "AR$",
}

export function formatCurrency(cents: number, currency = "BRL"): string {
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency
  const value = cents / 100
  return `${symbol} ${value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function formatDate(dateStr: string): string {
  const [y, m, d] = dateStr.split("-")
  return `${d}/${m}/${y}`
}
