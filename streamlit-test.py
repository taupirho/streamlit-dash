#
# Streamlit equivalent of final Gradio app
#
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import psycopg2
from psycopg2 import sql
from psycopg2 import pool
import os

# Initialize connection pool
try:
    dsn = os.environ.get("DATABASE_URL")
    connection_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=5,
        maxconn=20,
        dsn=dsn
    )
except psycopg2.Error as e:
    st.error(f"Error creating connection pool: {e}")

# To run this app, set the DATABASE_URL environment variable:
# For example:
# export DATABASE_URL="postgresql://user:password@host:port/database"

def get_connection():
    try:
        conn = connection_pool.getconn()
        if conn:
            return conn
        else:
            st.error("Failed to get a connection from the pool")
            return None
    except psycopg2.Error as e:
        st.error(f"Error getting connection from pool: {e}")
        return None

def release_connection(conn):
    try:
        connection_pool.putconn(conn)
    except psycopg2.Error as e:
        st.error(f"Error releasing connection back to pool: {e}")

def get_date_range():
    conn = get_connection()
    if conn is None:
        return None, None
    try:
        with conn.cursor() as cur:
            query = sql.SQL("SELECT MIN(order_date), MAX(order_date) FROM public.sales_data")
            cur.execute(query)
            return cur.fetchone()
    finally:
        release_connection(conn)

def get_unique_categories():
    conn = get_connection()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            query = sql.SQL("SELECT DISTINCT categories FROM public.sales_data ORDER BY categories")
            cur.execute(query)
            return [row[0].capitalize() for row in cur.fetchall()]
    finally:
        release_connection(conn)

def get_dashboard_stats(start_date, end_date, category):
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            query = sql.SQL("""
                WITH category_totals AS (
                    SELECT 
                        categories,
                        SUM(price * quantity) as category_revenue
                    FROM public.sales_data
                    WHERE order_date BETWEEN %s AND %s
                    AND (%s = 'All Categories' OR categories = %s)
                    GROUP BY categories
                ),
                top_category AS (
                    SELECT categories
                    FROM category_totals
                    ORDER BY category_revenue DESC
                    LIMIT 1
                ),
                overall_stats AS (
                    SELECT 
                        SUM(price * quantity) as total_revenue,
                        COUNT(DISTINCT order_id) as total_orders,
                        SUM(price * quantity) / COUNT(DISTINCT order_id) as avg_order_value
                    FROM public.sales_data
                    WHERE order_date BETWEEN %s AND %s
                    AND (%s = 'All Categories' OR categories = %s)
                )
                SELECT 
                    total_revenue,
                    total_orders,
                    avg_order_value,
                    (SELECT categories FROM top_category) as top_category
                FROM overall_stats
            """)
            cur.execute(query, [start_date, end_date, category, category, 
                                start_date, end_date, category, category])
            return cur.fetchone()
    finally:
        release_connection(conn)

    
def get_plot_data(start_date, end_date, category):
    conn = get_connection()
    if conn is None:
        return pd.DataFrame()
    try:
        with conn.cursor() as cur:
            query = sql.SQL("""
                SELECT DATE(order_date) as date,
                       SUM(price * quantity) as revenue
                FROM public.sales_data
                WHERE order_date BETWEEN %s AND %s
                  AND (%s = 'All Categories' OR categories = %s)
                GROUP BY DATE(order_date)
                ORDER BY date
            """)
            cur.execute(query, [start_date, end_date, category, category])
            return pd.DataFrame(cur.fetchall(), columns=['date', 'revenue'])
    finally:
        release_connection(conn)

def get_revenue_by_category(start_date, end_date, category):
    conn = get_connection()
    if conn is None:
        return pd.DataFrame()
    try:
        with conn.cursor() as cur:
            query = sql.SQL("""
                SELECT categories,
                       SUM(price * quantity) as revenue
                FROM public.sales_data
                WHERE order_date BETWEEN %s AND %s
                  AND (%s = 'All Categories' OR categories = %s)
                GROUP BY categories
                ORDER BY revenue DESC
            """)
            cur.execute(query, [start_date, end_date, category, category])
            return pd.DataFrame(cur.fetchall(), columns=['categories', 'revenue'])
    finally:
        release_connection(conn)

def get_top_products(start_date, end_date, category):
    conn = get_connection()
    if conn is None:
        return pd.DataFrame()
    try:
        with conn.cursor() as cur:
            query = sql.SQL("""
                SELECT product_names,
                       SUM(price * quantity) as revenue
                FROM public.sales_data
                WHERE order_date BETWEEN %s AND %s
                  AND (%s = 'All Categories' OR categories = %s)
                GROUP BY product_names
                ORDER BY revenue DESC
                LIMIT 10
            """)
            cur.execute(query, [start_date, end_date, category, category])
            return pd.DataFrame(cur.fetchall(), columns=['product_names', 'revenue'])
    finally:
        release_connection(conn)

def get_raw_data(start_date, end_date, category):
    conn = get_connection()
    if conn is None:
        return pd.DataFrame()
    try:
        with conn.cursor() as cur:
            query = sql.SQL("""
                SELECT 
                    order_id, order_date, customer_id, customer_name, 
                    product_id, product_names, categories, quantity, price, 
                    (price * quantity) as revenue
                FROM public.sales_data
                WHERE order_date BETWEEN %s AND %s
                  AND (%s = 'All Categories' OR categories = %s)
                ORDER BY order_date, order_id
            """)
            cur.execute(query, [start_date, end_date, category, category])
            return pd.DataFrame(cur.fetchall(), columns=[desc[0] for desc in cur.description])
    finally:
        release_connection(conn)

def plot_data(data, x_col, y_col, title, xlabel, ylabel, orientation='v'):
    fig, ax = plt.subplots(figsize=(10, 6))
    if not data.empty:
        if orientation == 'v':
            ax.bar(data[x_col], data[y_col])
        else:
            ax.barh(data[x_col], data[y_col])
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        plt.xticks(rotation=45)
    else:
        ax.text(0.5, 0.5, "No data available", ha='center', va='center')
    return fig

# Streamlit App
st.title("Sales Performance Dashboard")

# Filters
with st.container():
    col1, col2, col3 = st.columns([1, 1, 2])
    min_date, max_date = get_date_range()
    start_date = col1.date_input("Start Date", min_date)
    end_date = col2.date_input("End Date", max_date)
    categories = get_unique_categories()
    category = col3.selectbox("Category", ["All Categories"] + categories)

# Custom CSS for metrics
st.markdown("""
    <style>
    .metric-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 20px;
    }
    .metric-container {
        flex: 1;
        padding: 10px;
        text-align: center;
        background-color: #f0f2f6;
        border-radius: 5px;
        margin: 0 5px;
    }
    .metric-label {
        font-size: 14px;
        color: #555;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 18px;
        font-weight: bold;
        color: #0e1117;
    }
    </style>
""", unsafe_allow_html=True)

# Metrics
st.header("Key Metrics")
stats = get_dashboard_stats(start_date, end_date, category)
if stats:
    total_revenue, total_orders, avg_order_value, top_category = stats
else:
    total_revenue, total_orders, avg_order_value, top_category = 0, 0, 0, "N/A"

# Custom metrics display
metrics_html = f"""
<div class="metric-row">
    <div class="metric-container">
        <div class="metric-label">Total Revenue</div>
        <div class="metric-value">${total_revenue:,.2f}</div>
    </div>
    <div class="metric-container">
        <div class="metric-label">Total Orders</div>
        <div class="metric-value">{total_orders:,}</div>
    </div>
    <div class="metric-container">
        <div class="metric-label">Average Order Value</div>
        <div class="metric-value">${avg_order_value:,.2f}</div>
    </div>
    <div class="metric-container">
        <div class="metric-label">Top Category</div>
        <div class="metric-value">{top_category}</div>
    </div>
</div>
"""
st.markdown(metrics_html, unsafe_allow_html=True)

# Visualization Tabs
st.header("Visualizations")
tabs = st.tabs(["Revenue Over Time", "Revenue by Category", "Top Products"])

# Revenue Over Time Tab
with tabs[0]:
    st.subheader("Revenue Over Time")
    revenue_data = get_plot_data(start_date, end_date, category)
    st.pyplot(plot_data(revenue_data, 'date', 'revenue', "Revenue Over Time", "Date", "Revenue"))

# Revenue by Category Tab
with tabs[1]:
    st.subheader("Revenue by Category")
    category_data = get_revenue_by_category(start_date, end_date, category)
    st.pyplot(plot_data(category_data, 'categories', 'revenue', "Revenue by Category", "Category", "Revenue"))

# Top Products Tab
with tabs[2]:
    st.subheader("Top Products")
    top_products_data = get_top_products(start_date, end_date, category)
    st.pyplot(plot_data(top_products_data, 'product_names', 'revenue', "Top Products", "Revenue", "Product Name", orientation='h'))

st.header("Raw Data")

raw_data = get_raw_data(
    start_date=start_date,
    end_date=end_date,
    category=category
)

# Remove the index by resetting it and dropping the old index
raw_data = raw_data.reset_index(drop=True)

st.dataframe(raw_data,hide_index=True)

# Add spacing
st.write("")