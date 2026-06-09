// ── Auth ─────────────────────────────────────────────────────────────────────

export interface UserRead {
  id: string
  email: string
  is_active: boolean
  is_superuser: boolean
  full_name: string | null
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface AccessToken {
  access_token: string
  token_type: string
}

// ── Accounts ─────────────────────────────────────────────────────────────────

export interface Account {
  id: string
  name: string
  bank_name: string | null
  currency: string
  created_at: string
}

export interface AccountImport {
  id: string
  filename: string
  row_count: number
  created_at: string
}

export interface AccountCreate {
  name: string
  bank_name?: string
  currency?: string
}

// ── Uploads ───────────────────────────────────────────────────────────────────

export interface UploadResult {
  import_id: string
  rows_imported: number
  transfers_detected: number
  account_currency: string
}

// ── Transactions ──────────────────────────────────────────────────────────────

export interface Transaction {
  id: string
  bank_account_id: string
  date: string
  description: string
  amount: number
  type: "income" | "expense"
  category_id: string | null
  is_anomaly: boolean
  is_transfer: boolean
  transfer_pair_id: string | null
  notes: string | null
  created_at: string
}

export interface TransactionPage {
  items: Transaction[]
  total: number
  offset: number
  limit: number
}

export interface TransactionPatch {
  category_id?: string | null
  notes?: string | null
  is_transfer?: boolean
}

export interface BulkCategoryPatch {
  transaction_ids: string[]
  category_id: string | null
}

export interface TransferLinkRequest {
  expense_ids: string[]
  income_id: string
}

export interface TransactionFilters {
  account_ids?: string[]
  start?: string
  end?: string
  type?: "income" | "expense"
  is_transfer?: boolean
  category_id?: string
  search?: string
  is_anomaly?: boolean
  limit?: number
  offset?: number
}

// ── Categories ────────────────────────────────────────────────────────────────

export interface Category {
  id: string
  user_id: string | null
  name: string
  type: "income" | "expense"
  exclude_from_insights: boolean
  created_at: string
}

export interface CategoryCreate {
  name: string
  type: "income" | "expense"
}

export interface RetrainResult {
  samples_used: number
  classes: string[]
}

// ── Insights ──────────────────────────────────────────────────────────────────

export interface PeriodSummary {
  period: string
  total_income: number
  total_expenses: number
  net: number
}

export interface InsightResponse {
  summaries: PeriodSummary[]
  score: number
  narrative: string
  main_currency: string
  has_unconverted: boolean
}

// ── Preferences ───────────────────────────────────────────────────────────────

export interface Preferences {
  main_currency: string
}

// ── FX ────────────────────────────────────────────────────────────────────────

export interface SyncResult {
  rates_fetched: number
  error: string | null
}
