from __future__ import annotations

import datetime
from decimal import Decimal

import requests
import streamlit as st

API = "http://localhost:8000"


def format_amount(cents: int) -> str:
    return f"R$ {Decimal(cents) / 100:,.2f}"


def api(method: str, path: str, **kwargs):
    headers = {}
    if token := st.session_state.get("token"):
        headers["Authorization"] = f"Bearer {token}"
    return getattr(requests, method)(f"{API}{path}", headers=headers, **kwargs)


# ── Auth ─────────────────────────────────────────────────────────────────────

def login_page():
    st.title("FInSight — Personal Finance")
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            resp = requests.post(
                f"{API}/auth/jwt/login",
                data={"username": email, "password": password},
            )
            if resp.status_code == 200:
                st.session_state["token"] = resp.json()["access_token"]
                st.session_state["email"] = email
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab_register:
        full_name = st.text_input("Full name", key="reg_name")
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_pass")
        if st.button("Register"):
            resp = requests.post(
                f"{API}/auth/register",
                json={"email": email, "password": password, "full_name": full_name},
            )
            if resp.status_code == 201:
                st.success("Registered! Please log in.")
            else:
                try:
                    detail = resp.json().get("detail", resp.text or "Registration failed")
                except Exception:
                    detail = resp.text or f"HTTP {resp.status_code}"
                st.error(detail)


# ── Dashboard ─────────────────────────────────────────────────────────────────

def dashboard_page():
    st.header("Dashboard")

    # ── BETA: clear all transactions ──────────────────────────────────────────
    with st.expander("BETA tools", expanded=False):
        st.warning("These options will be removed after the beta phase.")
        confirm = st.checkbox("I understand this will permanently delete all my transactions")
        if st.button("Clear all transactions", disabled=not confirm, type="primary"):
            resp = api("delete", "/transactions/")
            if resp.status_code == 204:
                st.success("All transactions deleted.")
                st.rerun()
            else:
                st.error(f"Failed: {resp.text}")

    # ── Insights ──────────────────────────────────────────────────────────────
    year  = st.session_state.get("insight_year")
    month = st.session_state.get("insight_month")

    params = ""
    if year and month:
        params = f"?year={year}&month={month}"
        period_label = f"{month:02d}/{year}"
    elif year:
        params = f"?year={year}"
        period_label = str(year)
    else:
        period_label = "last 12 months"

    resp = api("get", f"/insights/monthly{params}")
    if resp.status_code != 200:
        st.warning("Could not load insights.")
        return

    data      = resp.json()
    summaries = data["summaries"]
    score     = data["score"]
    narrative = data["narrative"]

    st.metric("Financial Health Score", f"{score}/100")
    st.info(narrative)

    if summaries:
        import pandas as pd

        df = pd.DataFrame(summaries).sort_values("period")
        df["Income (R$)"]   = df["total_income"]   / 100
        df["Expenses (R$)"] = df["total_expenses"] / 100
        st.subheader(f"Income vs Expenses — {period_label}")
        st.bar_chart(df.set_index("period")[["Income (R$)", "Expenses (R$)"]])
    else:
        st.info("No transactions found for the selected period.")


# ── Accounts ──────────────────────────────────────────────────────────────────

def accounts_page():
    st.header("Bank Accounts")
    resp = api("get", "/accounts/")
    accounts = resp.json() if resp.status_code == 200 else []

    for acc in accounts:
        col1, col2 = st.columns([4, 1])
        col1.write(f"**{acc['name']}** — {acc['bank_name'] or 'N/A'} ({acc['currency']})")
        if col2.button("Delete", key=f"del_{acc['id']}"):
            api("delete", f"/accounts/{acc['id']}")
            st.rerun()

    st.subheader("New Account")
    with st.form("new_account"):
        name     = st.text_input("Account name")
        bank     = st.text_input("Bank name")
        currency = st.selectbox("Currency", ["BRL", "USD", "EUR"])
        if st.form_submit_button("Create"):
            api("post", "/accounts/", json={"name": name, "bank_name": bank, "currency": currency})
            st.rerun()


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_page():
    st.header("Upload Statement")
    resp = api("get", "/accounts/")
    accounts = resp.json() if resp.status_code == 200 else []
    if not accounts:
        st.info("Create an account first.")
        return
    options  = {acc["name"]: acc["id"] for acc in accounts}
    selected = st.selectbox("Account", list(options.keys()))
    uploaded = st.file_uploader("CSV or PDF statement", type=["csv", "pdf"])
    if uploaded and st.button("Upload"):
        resp = api(
            "post",
            f"/uploads/{options[selected]}",
            files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
        )
        if resp.status_code == 200:
            data = resp.json()
            msg = f"Imported {data['rows_imported']} transactions."
            if data.get("transfers_detected", 0):
                msg += f" {data['transfers_detected']} inter-account transfer(s) detected and excluded from insights."
            st.success(msg)
        else:
            st.error(resp.text)


# ── Transactions ──────────────────────────────────────────────────────────────

def _fmt_currency(cents: int, currency: str) -> str:
    amount = cents / 100
    symbols = {"BRL": "R$", "USD": "US$", "EUR": "€"}
    symbol = symbols.get(currency, currency)
    return f"{symbol} {amount:,.2f}"


def transactions_page():
    import pandas as pd

    st.header("Transactions")

    accounts_resp = api("get", "/accounts/")
    account_info = {
        acc["id"]: {"name": acc["name"], "currency": acc["currency"]}
        for acc in (accounts_resp.json() if accounts_resp.status_code == 200 else [])
    }

    col1, col2 = st.columns(2)
    start = col1.date_input("From", value=datetime.date.today().replace(day=1))
    end   = col2.date_input("To",   value=datetime.date.today())

    resp = api("get", f"/transactions/?start={start}&end={end}&limit=500")
    txs  = resp.json() if resp.status_code == 200 else []

    if not txs:
        st.info("No transactions found for the selected period.")
        return

    # Build transfer-pair lookup so both legs are resolved in one pass
    pair_map: dict[str, list[dict]] = {}
    for tx in txs:
        pid = tx.get("transfer_pair_id")
        if pid:
            pair_map.setdefault(pid, []).append(tx)

    rows = []
    for tx in txs:
        acc      = account_info.get(tx["bank_account_id"], {})
        currency = acc.get("currency", "BRL")

        # Type label
        if tx.get("is_transfer"):
            type_label = "↔ Transfer"
        elif tx["type"] == "income":
            type_label = "↑ Income"
        else:
            type_label = "↓ Expense"

        # Transfer direction: "Account A → Account B"
        transfer_dir = ""
        pid = tx.get("transfer_pair_id")
        if tx.get("is_transfer") and pid:
            src = dst = ""
            for leg in pair_map.get(pid, []):
                leg_name = account_info.get(leg["bank_account_id"], {}).get("name", "?")
                if leg["type"] == "expense":
                    src = leg_name
                else:
                    dst = leg_name
            transfer_dir = f"{src or '?'} → {dst or '?'}"

        flags = "⚠" if tx.get("is_anomaly") else ""

        rows.append({
            "Date":        tx["date"],
            "Account":     acc.get("name", "Unknown"),
            "Currency":    currency,
            "Description": tx["description"],
            "Amount":      _fmt_currency(tx["amount"], currency),
            "Type":        type_label,
            "Transfer":    transfer_dir,
            "Flags":       flags,
        })

    df = pd.DataFrame(rows)

    # Only show Transfer and Flags columns when they contain data
    if not df["Transfer"].any():
        df = df.drop(columns=["Transfer"])
    if not df["Flags"].any():
        df = df.drop(columns=["Flags"])

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"{len(txs)} transaction(s)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="FInSight", layout="wide")

    if not st.session_state.get("token"):
        login_page()
        return

    with st.sidebar:
        st.write(f"Logged in as **{st.session_state.get('email', '')}**")
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

        page = st.radio("Navigate", ["Dashboard", "Accounts", "Upload", "Transactions"])

        # ── Generate Insight ─────────────────────────────────────────────────
        st.divider()
        st.subheader("Generate Insight")

        period_type = st.radio("Period", ["Whole year", "Month"], label_visibility="collapsed")

        current_year = datetime.date.today().year
        if period_type == "Whole year":
            year  = st.number_input("Year", min_value=2000, max_value=current_year + 1,
                                    value=current_year, step=1, key="si_year")
            month = None
        else:
            c1, c2 = st.columns(2)
            month = c1.number_input("MM", min_value=1, max_value=12,
                                    value=datetime.date.today().month, step=1, key="si_month")
            year  = c2.number_input("YYYY", min_value=2000, max_value=current_year + 1,
                                    value=current_year, step=1, key="si_year2")

        if st.button("Generate Insight", use_container_width=True):
            st.session_state["insight_year"]  = int(year)
            st.session_state["insight_month"] = int(month) if month else None
            st.session_state["_nav"] = "Dashboard"
            st.rerun()

        if st.button("Reset to last 12 months", use_container_width=True):
            st.session_state.pop("insight_year",  None)
            st.session_state.pop("insight_month", None)
            st.rerun()

    target = st.session_state.pop("_nav", None) or page
    if target == "Dashboard":
        dashboard_page()
    elif target == "Accounts":
        accounts_page()
    elif target == "Upload":
        upload_page()
    elif target == "Transactions":
        transactions_page()


if __name__ == "__main__":
    main()
