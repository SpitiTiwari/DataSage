import streamlit as st
import pandas as pd
import plotly.express as px
import re
from euriai import EuriaiClient

# -------------------- Euriai Client Setup --------------------
client = EuriaiClient(
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJmMjcwNGRkMS1jOGY0LTQyMTYtYjFhZC01NjU4ZmU3NGYxYTUiLCJlbWFpbCI6InNqc3VrdW5hQGdtYWlsLmNvbSIsImlhdCI6MTc0NTI1MTEwMywiZXhwIjoxNzc2Nzg3MTAzfQ.x455yqe33Oh4Yif-Qiw2w_VBmbaCoW3oLCcG6lAmV4Y",
    model="gpt-4.1-nano"
)

# -------------------- App UI --------------------
st.title("📊 DataSage")

# File upload
uploaded_file = st.sidebar.file_uploader("📤 Upload Excel File", type=["xlsx", "xls"])

# -------------------- Data Cleaning --------------------
def clean_data(file):
    df = pd.read_excel(file)
    if 'Invoice Date' in df.columns:
        df['Invoice Date'] = pd.to_datetime(df['Invoice Date'], errors='coerce')

    columns_to_clean = {
        'Price per Unit': r'[\$,]',
        'Total Sales': r'[\$,]',
        'Operating Profit': r'[\$,]',
        'Units Sold': r'[,]',
        'Operating Margin': r'[\%]'
    }

    for col, pattern in columns_to_clean.items():
        if col in df.columns:
            df[col] = df[col].replace(pattern, '', regex=True).astype(float)
            if col == 'Operating Margin':
                df[col] = df[col] / 100.0

    return df

# -------------------- Data-based Direct Answers --------------------
def try_direct_answer(df, question):
    question = question.lower()

    # 1. Total Sales for a Region (like "Northeast")
    region_match = re.search(r"total sales.*region\s+([\w\s]+)", question)
    if region_match and 'Region' in df.columns and 'Total Sales' in df.columns:
        region = region_match.group(1).strip().title()
        filtered_df = df[df['Region'].str.lower() == region.lower()]
        if not filtered_df.empty:
            total = filtered_df['Total Sales'].sum()
            return f"💰 Total sales for region **{region}**: ${total:,.2f}"
        else:
            return f"⚠️ No data found for region: {region}"

    # 2. Units Sold for Region
    region_units_match = re.search(r"units sold.*region\s+([\w\s]+)", question)
    if region_units_match and 'Region' in df.columns and 'Units Sold' in df.columns:
        region = region_units_match.group(1).strip().title()
        filtered_df = df[df['Region'].str.lower() == region.lower()]
        if not filtered_df.empty:
            units = filtered_df['Units Sold'].sum()
            return f"📦 Units sold in region **{region}**: {units:,.0f}"
        else:
            return f"⚠️ No data found for region: {region}"

    # 3. Average Margin for Product
    product_match = re.search(r"average.*margin.*product\s+([\w\s]+)", question)
    if product_match and 'Product' in df.columns and 'Operating Margin' in df.columns:
        product = product_match.group(1).strip().title()
        filtered_df = df[df['Product'].str.lower() == product.lower()]
        if not filtered_df.empty:
            avg_margin = filtered_df['Operating Margin'].mean()
            return f"📊 Average operating margin for product **{product}**: {avg_margin:.2%}"
        else:
            return f"⚠️ No data found for product: {product}"

    return None  # fallback to AI if pattern not recognized


# -------------------- AI Prompt Helpers --------------------
def extract_response_content(response):
    if "content" in response:
        return response["content"]
    elif "choices" in response and response["choices"]:
        return response["choices"][0].get("message", {}).get("content", "❌ No content found in response.")
    else:
        return "❌ Unexpected response format: " + str(response)

def prepare_data_context(df, max_chars=10000):
    relevant_columns = ['City', 'Region', 'Product', 'Total Sales', 'Units Sold',
                        'Operating Profit', 'Operating Margin', 'Invoice Date', 'Retailer', 'Retailer ID']
    df_subset = df[[col for col in relevant_columns if col in df.columns]].copy()
    df_subset = df_subset.applymap(lambda x: str(x)[:50] if pd.notnull(x) else "")
    csv_data = df_subset.to_csv(index=False)

    if len(csv_data) > max_chars:
        csv_data = csv_data[:max_chars]
        csv_data += "\n(Note: Data truncated for size.)"

    return csv_data

def query_excel_data_with_ai(data_csv, question):
    prompt = f"""
You are a data assistant that ONLY answers questions based on the provided sales data.
Below is the data from an Excel file in CSV format:

{data_csv}

Now answer the following question based strictly on the above data:

{question}

If the answer cannot be determined from the data, respond: "The data does not provide enough information."
"""
    try:
        response = client.generate_completion(
            prompt=prompt,
            temperature=0.3,
            max_tokens=500
        )
        return extract_response_content(response)
    except Exception as e:
        return f"❌ Error: {e}"

# -------------------- Main App Logic --------------------
if uploaded_file:
    try:
        df = clean_data(uploaded_file)
        st.session_state.df = df
        st.sidebar.success("✅ File uploaded and processed.")
    except Exception as e:
        st.sidebar.error(f"❌ Error: {e}")

if 'df' in st.session_state:
    df = st.session_state.df

    st.header("📋 Data Preview")
    st.dataframe(df)

    # Key metrics
    st.subheader("📌 Key Metrics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Sales", f"${df['Total Sales'].sum():,.2f}")
    col2.metric("Units Sold", f"{df['Units Sold'].sum():,.0f}")
    col3.metric("Avg Margin", f"{df['Operating Margin'].mean():.2%}")

    # Charts
    st.subheader("📈 Visual Insights")

    if 'Region' in df.columns:
        fig1 = px.bar(df.groupby("Region")["Total Sales"].sum().reset_index(),
                      x="Region", y="Total Sales", title="Sales by Region")
        st.plotly_chart(fig1, use_container_width=True)

    if 'Product' in df.columns:
        fig2 = px.pie(df.groupby("Product")["Total Sales"].sum().reset_index(),
                      names="Product", values="Total Sales", title="Product Sales Share")
        st.plotly_chart(fig2, use_container_width=True)

    if 'Invoice Date' in df.columns:
        df['Month'] = df['Invoice Date'].dt.to_period('M').astype(str)
        monthly = df.groupby('Month')['Total Sales'].sum().reset_index()
        fig3 = px.line(monthly, x="Month", y="Total Sales", title="Monthly Sales Trend")
        st.plotly_chart(fig3, use_container_width=True)

    # Chat Assistant
    st.sidebar.header("🤖 DataSage")
    user_input = st.sidebar.text_input("You:", "")

    if user_input:
        direct = try_direct_answer(df, user_input)
        if direct:
            answer = direct
        else:
            data_csv = prepare_data_context(df)
            answer = query_excel_data_with_ai(data_csv, user_input)

        st.sidebar.text_area("Assistant:", value=answer, height=200)

else:
    st.info("📥 Please upload an Excel file to view the dashboard and use the assistant.")
