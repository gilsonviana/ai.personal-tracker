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


# ── Preferences ──────────────────────────────────────────────────────────────

def preferences_page():
    st.header("Preferences")

    resp = api("get", "/preferences/")
    current = resp.json().get("main_currency", "BRL") if resp.status_code == 200 else "BRL"

    _CURRENCIES = ["BRL", "USD", "EUR", "GBP", "ARS"]
    idx = _CURRENCIES.index(current) if current in _CURRENCIES else 0
    selected = st.selectbox("Main display currency", _CURRENCIES, index=idx)
    st.caption("All charts and reports convert foreign-currency transactions to this currency.")

    if st.button("Save", type="primary"):
        patch = api("patch", "/preferences/", json={"main_currency": selected})
        if patch.status_code == 200:
            st.success(f"Main currency set to {selected}.")
        else:
            st.error("Failed to save preferences.")


# ── Insight ───────────────────────────────────────────────────────────────────

def insight_page():
    st.header("Insight")

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

    # ── Time-range selector ───────────────────────────────────────────────────
    time_range = st.radio(
        "Period", ["Last 12 months", "Last year", "Last month"],
        horizontal=True, label_visibility="collapsed",
    )

    today = datetime.date.today()
    params = ""
    period_label = "last 12 months"

    if time_range == "Last year":
        year = st.number_input(
            "Year", min_value=2000, max_value=today.year, value=today.year - 1, step=1,
        )
        params = f"?year={int(year)}"
        period_label = str(int(year))
    elif time_range == "Last month":
        prev = today.replace(day=1) - datetime.timedelta(days=1)
        c1, c2 = st.columns(2)
        month = c1.number_input("MM", min_value=1, max_value=12, value=prev.month, step=1)
        year  = c2.number_input("YYYY", min_value=2000, max_value=today.year, value=prev.year, step=1)
        params = f"?year={int(year)}&month={int(month)}"
        period_label = f"{int(month):02d}/{int(year)}"

    # ── Fetch & render ────────────────────────────────────────────────────────
    resp = api("get", f"/insights/monthly{params}")
    if resp.status_code != 200:
        st.warning("Could not load insights.")
        return

    data          = resp.json()
    summaries     = data["summaries"]
    score         = data["score"]
    narrative     = data["narrative"]
    main_currency = data.get("main_currency", "BRL")
    has_unconverted = data.get("has_unconverted", False)

    _SYMBOLS = {"BRL": "R$", "USD": "US$", "EUR": "€", "GBP": "£", "ARS": "ARS$"}
    currency_symbol = _SYMBOLS.get(main_currency, main_currency)

    st.metric("Financial Health Score", f"{score}/100")
    st.info(narrative)

    if has_unconverted:
        st.warning(
            "Some transactions are missing a conversion rate and are excluded from totals. "
            "Click below to fetch the missing rates."
        )
        if st.button("Convert currency values", key="insight_convert"):
            fx_resp = api("post", "/fx/sync")
            if fx_resp.status_code == 200:
                fx_data = fx_resp.json()
                if fx_data.get("error"):
                    st.error(f"Could not fetch exchange rates: {fx_data['error']}")
                else:
                    st.rerun()
            else:
                st.error("Failed to fetch exchange rates.")

    if summaries:
        import pandas as pd
        import plotly.graph_objects as go

        _COLOR_INCOME  = "rgb(34, 197, 94)"
        _COLOR_EXPENSE = "rgb(239, 68, 68)"
        _COLOR_NET     = "rgb(234, 179, 8)"

        col_income   = f"Income ({main_currency})"
        col_expenses = f"Expenses ({main_currency})"
        col_net      = f"Net ({main_currency})"

        df = pd.DataFrame(summaries).sort_values("period")
        df[col_income]   = df["total_income"]   / 100
        df[col_expenses] = df["total_expenses"] / 100
        df[col_net]      = df[col_income] - df[col_expenses]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Income",
            x=df["period"], y=df[col_income],
            marker_color=_COLOR_INCOME,
        ))
        fig.add_trace(go.Bar(
            name="Expenses",
            x=df["period"], y=df[col_expenses],
            marker_color=_COLOR_EXPENSE,
        ))
        fig.add_trace(go.Scatter(
            name="Net",
            x=df["period"], y=df[col_net],
            mode="lines+markers",
            line=dict(color=_COLOR_NET, width=2),
            marker=dict(size=6),
        ))
        fig.update_layout(
            barmode="group",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=30, b=0),
            yaxis_tickprefix=f"{currency_symbol} ",
        )
        st.subheader(f"Income vs Expenses — {period_label}")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No transactions found for the selected period.")


# ── Accounts ──────────────────────────────────────────────────────────────────

def accounts_page():
    st.header("Bank Accounts")
    resp = api("get", "/accounts/")
    accounts = resp.json() if resp.status_code == 200 else []

    for acc in accounts:
        with st.expander(f"{acc['name']} — {acc['bank_name'] or 'N/A'} ({acc['currency']})"):
            imp_resp = api("get", f"/accounts/{acc['id']}/imports")
            imports  = imp_resp.json() if imp_resp.status_code == 200 else []
            if imports:
                for imp in imports:
                    c1, c2, c3, c4 = st.columns([4, 1, 2, 1])
                    c1.caption(imp["filename"])
                    c2.caption(f"{imp['row_count']} rows")
                    c3.caption(imp["created_at"][:10])
                    if c4.button("Delete", key=f"del_imp_{imp['id']}", type="secondary"):
                        del_resp = api("delete", f"/uploads/{imp['id']}")
                        if del_resp.status_code == 204:
                            st.rerun()
                        else:
                            st.error("Failed to delete import.")
            else:
                st.caption("No files uploaded yet.")
            if st.button("Delete Account", key=f"del_{acc['id']}", type="secondary"):
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

    prefs_resp = api("get", "/preferences/")
    main_currency = prefs_resp.json().get("main_currency", "BRL") if prefs_resp.status_code == 200 else "BRL"

    options  = {acc["name"]: acc["id"] for acc in accounts}
    selected = st.selectbox("Account", list(options.keys()))
    uploaded = st.file_uploader("CSV, PDF or TXT statement", type=["csv", "pdf", "txt"])
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
            account_currency = data.get("account_currency", "BRL")
            if account_currency != main_currency:
                st.session_state["pending_fx_import_id"] = str(data["import_id"])
                st.session_state["pending_fx_currency"] = account_currency

    if pending_import := st.session_state.get("pending_fx_import_id"):
        pending_currency = st.session_state.get("pending_fx_currency", "")
        st.info(
            f"This statement uses **{pending_currency}**, but your main currency is **{main_currency}**. "
            "Fetch historical exchange rates to include these transactions in your reports."
        )
        if st.button("Convert currency values", key="upload_convert"):
            fx_resp = api("post", f"/fx/sync?import_id={pending_import}")
            if fx_resp.status_code == 200:
                fx_data = fx_resp.json()
                if fx_data.get("error"):
                    st.error(f"Could not fetch exchange rates: {fx_data['error']}")
                else:
                    st.session_state.pop("pending_fx_import_id", None)
                    st.session_state.pop("pending_fx_currency", None)
                    st.rerun()
            else:
                st.error("Failed to fetch exchange rates. Please try again.")
        elif resp.status_code == 409:
            st.warning(resp.json().get("detail", "This file has already been uploaded."))
        else:
            try:
                st.error(resp.json().get("detail", resp.text))
            except Exception:
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

    if "selected_tx_ids" not in st.session_state:
        st.session_state["selected_tx_ids"] = set()

    accounts_resp = api("get", "/accounts/")
    account_info = {
        acc["id"]: {"name": acc["name"], "currency": acc["currency"]}
        for acc in (accounts_resp.json() if accounts_resp.status_code == 200 else [])
    }

    cats_resp = api("get", "/categories/")
    categories = cats_resp.json() if cats_resp.status_code == 200 else []
    cat_id_to_name = {c["id"]: c["name"] for c in categories}
    cat_names_by_type = {
        "income":  ["— none —"] + [c["name"] for c in categories if c["type"] == "income"],
        "expense": ["— none —"] + [c["name"] for c in categories if c["type"] == "expense"],
        "all":     ["— none —"] + [c["name"] for c in categories],
    }
    cat_name_to_id = {c["name"]: c["id"] for c in categories}

    today         = datetime.date.today()
    last_of_prev  = today.replace(day=1) - datetime.timedelta(days=1)
    first_of_prev = last_of_prev.replace(day=1)

    col1, col2, col3, col4, col5 = st.columns(5)
    start = col1.date_input("From", value=first_of_prev)
    end   = col2.date_input("To",   value=last_of_prev)

    name_to_id   = {a["name"]: aid for aid, a in account_info.items()}
    selected_ids = col3.multiselect("Accounts", list(name_to_id.keys()))

    sel_type = col4.selectbox("Type", ["All", "Income", "Expense", "Transfer"])

    if sel_type == "Income":
        cat_filter_options = ["All categories", "— none —"] + [c["name"] for c in categories if c["type"] == "income"]
    elif sel_type == "Expense":
        cat_filter_options = ["All categories", "— none —"] + [c["name"] for c in categories if c["type"] == "expense"]
    else:
        cat_filter_options = ["All categories", "— none —"] + [c["name"] for c in categories]
    sel_cat = col5.selectbox("Category", cat_filter_options)

    url = f"/transactions/?start={start}&end={end}&limit=2000"
    for name in selected_ids:
        url += f"&account_ids={name_to_id[name]}"
    resp = api("get", url)
    page = resp.json() if resp.status_code == 200 else {}
    txs  = page.get("items", [])

    if not txs:
        st.info("No transactions found for the selected period.")
        return

    # Build transfer-pair lookup so both legs are resolved in one pass
    pair_map: dict[str, list[dict]] = {}
    for tx in txs:
        pid = tx.get("transfer_pair_id")
        if pid:
            pair_map.setdefault(pid, []).append(tx)

    if sel_type == "Income":
        display_txs = [tx for tx in txs if tx["type"] == "income" and not tx["is_transfer"]]
    elif sel_type == "Expense":
        display_txs = [tx for tx in txs if tx["type"] == "expense" and not tx["is_transfer"]]
    elif sel_type == "Transfer":
        display_txs = [tx for tx in txs if tx["is_transfer"]]
    else:
        display_txs = txs

    if sel_cat != "All categories":
        if sel_cat == "— none —":
            display_txs = [tx for tx in display_txs if not tx.get("category_id")]
        else:
            target_cat_id = cat_name_to_id.get(sel_cat)
            display_txs = [tx for tx in display_txs if tx.get("category_id") == target_cat_id]

    if sel_type == "Transfer":
        display_txs = sorted(
            display_txs,
            key=lambda t: (
                str(t.get("transfer_pair_id") or ""),
                0 if t["type"] == "expense" else 1,
            ),
        )

    rows = []
    for tx in display_txs:
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

        cat_name = cat_id_to_name.get(tx.get("category_id") or "", "") or "— none —"

        rows.append({
            "Select":      tx["id"] in st.session_state["selected_tx_ids"],
            "ID":          tx["id"],
            "Date":        tx["date"],
            "Account":     acc.get("name", "Unknown"),
            "Currency":    currency,
            "Description": tx["description"],
            "Amount":      tx["amount"] / 100,
            "Type":        type_label,
            "Category":    cat_name,
            "Transfer":    transfer_dir,
            "Flags":       flags,
        })

    df = pd.DataFrame(rows)

    # Only show Transfer and Flags columns when they contain data
    if not df["Transfer"].any():
        df = df.drop(columns=["Transfer"])
    if not df["Flags"].any():
        df = df.drop(columns=["Flags"])

    df_original = df.copy()

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["ID", "Date", "Account", "Currency", "Description", "Amount", "Type", "Transfer", "Flags"],
        column_config={
            "Select":   st.column_config.CheckboxColumn("Select", default=False),
            "ID":       st.column_config.TextColumn("ID", width="small"),
            "Amount":   st.column_config.NumberColumn("Amount", format="%.2f"),
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=cat_names_by_type["all"],
                required=True,
            ),
        },
    )

    changed_rows = edited_df[edited_df["Category"] != df_original["Category"]]
    if not changed_rows.empty:
        errors, successes = [], []
        for _, row in changed_rows.iterrows():
            tx_id = row["ID"]
            new_cat = row["Category"]
            new_cat_id = cat_name_to_id.get(new_cat) if new_cat != "— none —" else None
            resp = api("patch", f"/transactions/{tx_id}", json={"category_id": str(new_cat_id) if new_cat_id else None})
            if resp.status_code == 200:
                successes.append(tx_id)
            else:
                errors.append(f"{tx_id}: {resp.json().get('detail', resp.text)}")
        if successes:
            st.success(f"Category updated for {len(successes)} transaction(s).")
        if errors:
            st.error("Failed to update:\n" + "\n".join(errors))
        if successes:
            st.rerun()

    st.caption(f"{len(display_txs)} of {len(txs)} transaction(s)")
    st.caption("↑ Income   ↓ Expense   ↔ Transfer")

    # ── Selection sync (no forced rerun — data_editor auto-reruns on checkbox click) ──
    newly_selected = set(edited_df.loc[edited_df["Select"] == True, "ID"].astype(str))
    st.session_state["selected_tx_ids"] = newly_selected

    selected_rows = edited_df[edited_df["Select"] == True]
    n_sel = len(selected_rows)
    sel_types = set(selected_rows["Type"].tolist()) if n_sel > 0 else set()

    st.divider()
    hdr_col, clr_col = st.columns([5, 1])
    hdr_col.markdown("**Actions**")
    if n_sel > 0 and clr_col.button("Clear selection", key="clear_sel"):
        st.session_state["selected_tx_ids"] = set()
        st.rerun()

    # ── Link as Transfer ──────────────────────────────────────────────────────
    link_expanded = n_sel >= 2 and "↔ Transfer" not in sel_types
    with st.expander("Link as Transfer", expanded=link_expanded):
        if n_sel < 2 or "↔ Transfer" in sel_types:
            st.info(
                "Check at least two rows in the table above — "
                "one ↓ Expense (or more) and exactly one ↑ Income — then link them as a transfer."
            )
        else:
            exp_rows  = selected_rows[selected_rows["Type"] == "↓ Expense"]
            inc_rows  = selected_rows[selected_rows["Type"] == "↑ Income"]
            valid_pair = len(exp_rows) >= 1 and len(inc_rows) == 1
            for _, row in selected_rows.iterrows():
                st.caption(
                    f"{row['Type']}  {row['Date']}  {row['Account']}  "
                    f"{row['Currency']} {row['Amount']:.2f}  —  {row['Description']}"
                )
            if not valid_pair:
                st.warning("Select at least one ↓ Expense and exactly one ↑ Income.")
            if st.button("Link as Transfer", type="primary", key="sel_link_transfer", disabled=not valid_pair):
                resp = api("post", "/transactions/link-transfer", json={
                    "expense_ids": exp_rows["ID"].tolist(),
                    "income_id":   inc_rows.iloc[0]["ID"],
                })
                if resp.status_code == 200:
                    st.success("Transactions linked as a transfer pair.")
                    st.session_state["selected_tx_ids"] = set()
                    st.rerun()
                else:
                    try:
                        st.error(resp.json().get("detail", resp.text))
                    except Exception:
                        st.error(resp.text)

    # ── Unlink (single transfer row selected) ────────────────────────────────
    if n_sel == 1 and "↔ Transfer" in sel_types:
        tx_id = selected_rows.iloc[0]["ID"]
        if st.button("Unlink this transfer pair", type="secondary", key="sel_unlink"):
            resp = api("patch", f"/transactions/{tx_id}", json={"is_transfer": False})
            if resp.status_code == 200:
                st.success("Transfer pair unlinked.")
                st.session_state["selected_tx_ids"] = set()
                st.rerun()
            else:
                try:
                    st.error(resp.json().get("detail", resp.text))
                except Exception:
                    st.error(resp.text)

    # ── Assign Category ───────────────────────────────────────────────────────
    non_transfer_sel = selected_rows[selected_rows["Type"] != "↔ Transfer"]
    if len(non_transfer_sel) > 0:
        sel_tx_types_raw = set()
        for _, row in non_transfer_sel.iterrows():
            if row["Type"] == "↑ Income":
                sel_tx_types_raw.add("income")
            elif row["Type"] == "↓ Expense":
                sel_tx_types_raw.add("expense")
        matched_type = sel_tx_types_raw.pop() if len(sel_tx_types_raw) == 1 else "all"
        cat_opts = cat_names_by_type.get(matched_type, cat_names_by_type["all"])
        sel_cat_bulk = st.selectbox("Assign category", cat_opts, key="bulk_cat_sel")
        if st.button("Apply Category", type="primary", key="bulk_cat_save"):
            bulk_ids = non_transfer_sel["ID"].astype(str).tolist()
            new_cat_id = cat_name_to_id.get(sel_cat_bulk) if sel_cat_bulk != "— none —" else None
            cat_payload = {"category_id": str(new_cat_id) if new_cat_id else None}
            resp = api("patch", "/transactions/bulk-category", json={"transaction_ids": bulk_ids, **cat_payload})
            if resp.status_code == 200:
                st.success(f"Category updated to '{sel_cat_bulk}' for {len(bulk_ids)} transaction(s).")
                st.session_state["selected_tx_ids"] = set()
                st.rerun()
            else:
                st.error(resp.json().get("detail", resp.text))

    # ── Retrain categoriser ───────────────────────────────────────────────────
    with st.expander("Retrain Categoriser"):
        st.caption(
            "Train a personal model using your own categorized transactions. "
            "The more transactions you have labeled, the better the model will perform on future imports."
        )
        if st.button("Retrain now", type="primary", key="retrain_cat"):
            rt_resp = api("post", "/categories/retrain")
            if rt_resp.status_code == 200:
                rt = rt_resp.json()
                st.success(
                    f"Model trained on {rt['samples_used']} transactions "
                    f"across {len(rt['classes'])} categories: {', '.join(rt['classes'])}."
                )
            else:
                try:
                    st.error(rt_resp.json().get("detail", rt_resp.text))
                except Exception:
                    st.error(rt_resp.text)

    with st.expander("Unlink Transfers"):
        st.caption("To link two transactions as a transfer, select the expense row and the income row in the table above — a Link button will appear. To unlink, select the transfer row and click Unlink, or use the dropdown below.")
        st.subheader("Unlink Transfer Pair")
        seen_pairs: set[str] = set()
        unlink_options: dict[str, str] = {}
        for tx in txs:
            if not tx["is_transfer"]:
                continue
            pid = tx.get("transfer_pair_id")
            if not pid or pid in seen_pairs:
                continue
            seen_pairs.add(pid)
            legs = pair_map.get(pid, [tx])
            src = dst = ""
            expense_leg = next((l for l in legs if l["type"] == "expense"), tx)
            for leg in legs:
                leg_name = account_info.get(leg["bank_account_id"], {}).get("name", "?")
                if leg["type"] == "expense":
                    src = leg_name
                else:
                    dst = leg_name
            exp_currency = account_info.get(expense_leg["bank_account_id"], {}).get("currency", "BRL")
            amt = _fmt_currency(expense_leg["amount"], exp_currency)
            label = f"{expense_leg['date']}  {src or '?'} → {dst or '?'}  ({amt})"
            unlink_options[label] = expense_leg["id"]

        if not unlink_options:
            st.info("No transfer pairs in the current date range to unlink.")
        else:
            sel_pair = st.selectbox("Pair to unlink", list(unlink_options.keys()), key="unlink_pair")
            if st.button("Unlink Transfer Pair"):
                resp = api("patch", f"/transactions/{unlink_options[sel_pair]}", json={"is_transfer": False})
                if resp.status_code == 200:
                    st.success("Transfer pair unlinked.")
                    st.rerun()
                else:
                    try:
                        st.error(resp.json().get("detail", resp.text))
                    except Exception:
                        st.error(resp.text)


# ── Categories ────────────────────────────────────────────────────────────────

def categories_page():
    import pandas as pd

    st.title("Categories")

    resp = api("get", "/categories/")
    if resp.status_code != 200:
        st.error("Failed to load categories.")
        return
    categories = resp.json()

    user_cats = [c for c in categories if c.get("user_id") is not None]

    # ── Unified category table ─────────────────────────────────────────────────
    st.caption(
        "Toggle **In Insights** to include or exclude a category from the insight graphs and health score. "
        "System categories cannot be deleted, but can be excluded."
    )
    all_cats = sorted(categories, key=lambda c: (c["type"], c["name"]))
    rows = [
        {
            "Name": c["name"],
            "Type": c["type"].capitalize(),
            "Source": "System" if c["user_id"] is None else "Custom",
            "In Insights": not c["exclude_from_insights"],
        }
        for c in all_cats
    ]
    df = pd.DataFrame(rows)
    df_original = df.copy()

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["Name", "Type", "Source"],
        column_config={
            "In Insights": st.column_config.CheckboxColumn("In Insights", default=True),
        },
        key="cat_editor",
    )

    changed = edited_df[edited_df["In Insights"] != df_original["In Insights"]]
    if not changed.empty:
        errors, successes = [], []
        for idx in changed.index:
            cat = all_cats[idx]
            excluded = not bool(edited_df.at[idx, "In Insights"])
            resp = api("patch", f"/categories/{cat['id']}", json={"exclude_from_insights": excluded})
            if resp.status_code == 200:
                successes.append(cat["name"])
            else:
                errors.append(f"{cat['name']}: {resp.json().get('detail', resp.text)}")
        if successes:
            st.success(f"Updated: {', '.join(successes)}")
        if errors:
            st.error("Failed to update:\n" + "\n".join(errors))
        if successes:
            st.rerun()

    # ── Delete user category ───────────────────────────────────────────────────
    if user_cats:
        with st.expander("Delete a custom category"):
            cat_to_delete = st.selectbox(
                "Select category",
                [c["name"] for c in user_cats],
                key="cat_del_select",
            )
            if st.button("Delete", type="primary", key="cat_del_btn"):
                target = next(c for c in user_cats if c["name"] == cat_to_delete)
                del_resp = api("delete", f"/categories/{target['id']}")
                if del_resp.status_code == 204:
                    st.success(f"'{cat_to_delete}' deleted. Transactions assigned to it are now uncategorised.")
                    st.rerun()
                else:
                    st.error(del_resp.json().get("detail", del_resp.text))

    # ── Add a category ─────────────────────────────────────────────────────────
    st.subheader("Add a Category")
    with st.form("add_category_form"):
        col_a, col_b = st.columns([3, 1])
        new_name = col_a.text_input("Name", placeholder="e.g. Side Income")
        new_type = col_b.selectbox("Type", ["income", "expense"])
        submitted = st.form_submit_button("Add", type="primary")
    if submitted:
        if not new_name.strip():
            st.error("Category name cannot be empty.")
        else:
            add_resp = api("post", "/categories/", json={"name": new_name.strip(), "type": new_type})
            if add_resp.status_code == 201:
                st.success(f"'{new_name.strip()}' added.")
                st.rerun()
            else:
                st.error(add_resp.json().get("detail", add_resp.text))


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

        page = st.radio("Navigate", ["Preferences", "Accounts", "Upload", "Transactions", "Categories", "Insight"])

    if page == "Preferences":
        preferences_page()
    elif page == "Accounts":
        accounts_page()
    elif page == "Upload":
        upload_page()
    elif page == "Transactions":
        transactions_page()
    elif page == "Categories":
        categories_page()
    elif page == "Insight":
        insight_page()


if __name__ == "__main__":
    main()
