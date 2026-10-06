import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# ----------------- DATABASE SETUP -----------------
conn = sqlite3.connect("store.db", check_same_thread=False)
c = conn.cursor()

# Create tables
c.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER NOT NULL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    credit_limit REAL DEFAULT 2000.0,
    current_debt REAL DEFAULT 0.0
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    item_name TEXT,
    quantity INTEGER,
    total_amount REAL,
    payment_type TEXT,
    customer_name TEXT
)
""")
conn.commit()

# ----------------- UI NAVIGATION -----------------
st.set_page_config(page_title="Store Manager", layout="wide")
st.title("🛒 Store Accountability & Credit Tracker")

menu = st.sidebar.radio("Navigation", ["1. Billing Counter", "2. Inventory Management", "3. Credit (Udhar) Ledger", "4. Sales History"])

# ----------------- 1. BILLING COUNTER -----------------
if menu == "1. Billing Counter":
    st.header("Point of Sale")

    products = pd.read_sql_query("SELECT * FROM products WHERE stock > 0", conn)
    customers = pd.read_sql_query("SELECT * FROM customers", conn)

    if products.empty:
        st.warning("No products available. Please add items in the Inventory section first.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            selected_product_name = st.selectbox("Select Product", products["name"].tolist())
            product_row = products[products["name"] == selected_product_name].iloc[0]
            st.info(f"Available Stock: {product_row['stock']} | Unit Price: ₹{product_row['price']}")

            quantity = st.number_input("Quantity", min_value=1, max_value=int(product_row["stock"]), value=1)
            total_bill = quantity * product_row["price"]
            st.metric(label="Total Bill", value=f"₹{total_bill}")

        with col2:
            payment_type = st.radio("Payment Method", ["Cash", "UPI", "Credit (Borrow)"])

            customer_id = None
            customer_name = "Walk-in"

            if payment_type == "Credit (Borrow)":
                if customers.empty:
                    st.error("No registered customers found. Add them in the Credit Ledger tab.")
                else:
                    customer_display = st.selectbox(
                        "Select Customer",
                        customers.apply(lambda r: f"{r['name']} ({r['phone']}) - Debt: ₹{r['current_debt']}", axis=1)
                    )
                    selected_idx = customers.index[customers.apply(lambda r: f"{r['name']} ({r['phone']}) - Debt: ₹{r['current_debt']}", axis=1) == customer_display][0]
                    cust_row = customers.iloc[selected_idx]
                    customer_name = cust_row["name"]
                    customer_id = cust_row["id"]

                    if (cust_row["current_debt"] + total_bill) > cust_row["credit_limit"]:
                        st.error(f"Cannot sell on credit! Limit is ₹{cust_row['credit_limit']}. Current debt is ₹{cust_row['current_debt']}.")
                        st.stop()

            if st.button("Complete Transaction", use_container_width=True):
                c.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, int(product_row["id"])))
                
                if payment_type == "Credit (Borrow)" and customer_id:
                    c.execute("UPDATE customers SET current_debt = current_debt + ? WHERE id = ?", (total_bill, customer_id))

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute(
                    "INSERT INTO transactions (timestamp, item_name, quantity, total_amount, payment_type, customer_name) VALUES (?, ?, ?, ?, ?, ?)",
                    (now, selected_product_name, quantity, total_bill, payment_type, customer_name)
                )
                conn.commit()
                st.success("Sale recorded and inventory updated successfully!")
                st.rerun()

# ----------------- 2. INVENTORY MANAGEMENT -----------------
elif menu == "2. Inventory Management":
    st.header("Stock & Shelf Tracker")

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Add / Restock Product")
        p_name = st.text_input("Product Name")
        p_price = st.number_input("Selling Price (₹)", min_value=1.0, value=10.0)
        p_stock = st.number_input("Stock Quantity", min_value=1, value=20)

        if st.button("Save to Inventory"):
            if p_name.strip():
                c.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", (p_name.strip(), p_price, p_stock))
                conn.commit()
                st.success(f"Added {p_name} to shelves!")
                st.rerun()
            else:
                st.error("Please provide a product name.")

    with col2:
        st.subheader("Current Shelf Items")
        df_stock = pd.read_sql_query("SELECT id, name, price, stock FROM products", conn)
        st.dataframe(df_stock, use_container_width=True)

# ----------------- 3. CREDIT (UDHAR) LEDGER -----------------
elif menu == "3. Credit (Udhar) Ledger":
    st.header("Customer Borrowing & Repayment")

    tab1, tab2 = st.tabs(["Register Customer", "Collect Repayment"])

    with tab1:
        c_name = st.text_input("Customer Name")
        c_phone = st.text_input("Phone Number")
        c_limit = st.number_input("Max Credit Limit Allowed (₹)", min_value=100.0, value=2000.0)

        if st.button("Register Customer"):
            if c_name and c_phone:
                try:
                    c.execute("INSERT INTO customers (name, phone, credit_limit, current_debt) VALUES (?, ?, ?, 0.0)", (c_name, c_phone, c_limit))
                    conn.commit()
                    st.success(f"Customer {c_name} registered!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("A customer with this phone number already exists.")
            else:
                st.error("Fill in name and phone number.")

    with tab2:
        st.subheader("Collect Customer Repayment")
        cust_list = pd.read_sql_query("SELECT * FROM customers WHERE current_debt > 0", conn)

        if cust_list.empty:
            st.info("No outstanding debts at the moment!")
        else:
            cust_choice = st.selectbox(
                "Choose customer settling dues",
                cust_list.apply(lambda r: f"{r['name']} ({r['phone']}) - Owes: ₹{r['current_debt']}", axis=1)
            )
            selected_idx = cust_list.index[cust_list.apply(lambda r: f"{r['name']} ({r['phone']}) - Owes: ₹{r['current_debt']}", axis=1) == cust_choice][0]
            active_customer = cust_list.iloc[selected_idx]

            repay_amount = st.number_input("Repayment Amount (₹)", min_value=1.0, max_value=float(active_customer["current_debt"]), value=float(active_customer["current_debt"]))

            if st.button("Record Payment"):
                new_debt = active_customer["current_debt"] - repay_amount
                c.execute("UPDATE customers SET current_debt = ? WHERE id = ?", (new_debt, int(active_customer["id"])))

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute(
                    "INSERT INTO transactions (timestamp, item_name, quantity, total_amount, payment_type, customer_name) VALUES (?, 'Credit Repayment', 1, ?, 'Cash Repayment', ?)",
                    (now, repay_amount, active_customer["name"])
                )
                conn.commit()
                st.success(f"Payment received! New debt balance: ₹{new_debt}")
                st.rerun()

    st.divider()
    st.subheader("All Customer Ledgers")
    df_customers = pd.read_sql_query("SELECT name, phone, credit_limit, current_debt FROM customers", conn)
    st.dataframe(df_customers, use_container_width=True)

# ----------------- 4. SALES HISTORY & AUDIT -----------------
elif menu == "4. Sales History":
    st.header("Daily Audit & Transaction Records")

    df_txns = pd.read_sql_query("SELECT * FROM transactions ORDER BY id DESC", conn)

    if not df_txns.empty:
        total_cash = df_txns[df_txns["payment_type"].isin(["Cash", "Cash Repayment"])]["total_amount"].sum()
        total_upi = df_txns[df_txns["payment_type"] == "UPI"]["total_amount"].sum()
        total_credit = df_txns[df_txns["payment_type"] == "Credit (Borrow)"]["total_amount"].sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("Cash Collected", f"₹{total_cash}")
        m2.metric("UPI / Online Received", f"₹{total_upi}")
        m3.metric("Outstanding Unpaid (Credit)", f"₹{total_credit}")

        st.dataframe(df_txns, use_container_width=True)
    else:
        st.info("No transactions logged yet.")