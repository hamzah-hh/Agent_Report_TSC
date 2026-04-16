import streamlit as st
import pandas as pd
import numpy as np

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Agent Performance Automator", layout="wide")
st.title("📊 AI-Powered Report Automator")
st.markdown("Upload your 3 CSV files. This version is 'Error-Proof' and won't crash if a break category is missing.")

# --- HELPER FUNCTIONS ---
def hms_to_sec(t):
    if pd.isna(t) or t == '0' or t == 0: return 0
    try:
        t_clean = str(t).split('.')[0].strip() 
        parts = t_clean.split(':')
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0
    except:
        return 0

def sec_to_hms(seconds):
    if pd.isna(seconds) or seconds <= 0: return "00:00:00"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# --- FILE UPLOADS ---
col1, col2, col3 = st.columns(3)
with col1:
    prod_file = st.file_uploader("1. Productivity Summary", type="csv")
with col2:
    sess_file = st.file_uploader("2. Session Details", type="csv")
with col3:
    sales_file = st.file_uploader("3. Custom Sales Report", type="csv")

if prod_file and sess_file and sales_file:
    try:
        # 1. Load Data
        prod = pd.read_csv(prod_file)
        sess = pd.read_csv(sess_file)
        sales = pd.read_csv(sales_file)

        # Clean Column Names
        for df in [prod, sess, sales]:
            df.columns = df.columns.str.strip()

        # 2. Cleaning Data Rows
        for df in [prod, sess, sales]:
            df.dropna(subset=['User ID'], inplace=True)
            df['User ID'] = df['User ID'].astype(str).str.lower().str.strip()

        # Process Dates
        prod['Date'] = pd.to_datetime(prod['Interval Start'], dayfirst=True, errors='coerce').dt.date
        sess['Date'] = pd.to_datetime(sess['Login Time'], dayfirst=True, errors='coerce').dt.date
        sales['Date'] = pd.to_datetime(sales['Start Time'], dayfirst=True, errors='coerce').dt.date

        # 3. Process Individual Breaks
        sess['Break_Sec'] = sess['Break Duration'].apply(hms_to_sec)
        
        # Filter out empty break reasons before pivoting
        sess_breaks = sess.dropna(subset=['Break Reason']).copy()
        break_pivot = sess_breaks.pivot_table(
            index=['Date', 'User ID'], 
            columns='Break Reason', 
            values='Break_Sec', 
            aggfunc='sum', 
            fill_value=0
        ).reset_index()

        # 4. Process Sales Metrics (Talk Time >= 1s)
        sales['Talk_Sec'] = sales['Talk Time'].apply(hms_to_sec)
        sales['Is_Connected'] = sales['Talk_Sec'] >= 1
        
        sales_agg = sales.groupby(['Date', 'User ID']).agg(
            Total_OB_Calls=('call Id', 'count'),
            Unq_OB_Calls=('dstPhone', 'nunique')
        ).reset_index()

        conn_agg = sales[sales['Is_Connected']].groupby(['Date', 'User ID']).agg(
            Connected_OB_Calls=('call Id', 'count'),
            Unq_CC_Calls=('dstPhone', 'nunique')
        ).reset_index()
        sales_final = pd.merge(sales_agg, conn_agg, on=['Date', 'User ID'], how='left').fillna(0)

        # 5. Process Productivity Summary
        prod_time_cols = ['Total Staffed Duration', 'Total Ready Duration', 'Total Break Duration', 
                          'Total Idle Time', 'Total Talk Time in Interval', 'Total ACW Duration in Interval']
        
        for col in prod_time_cols:
            prod[col + '_sec'] = prod[col].apply(hms_to_sec)

        prod_final = prod.groupby(['Date', 'User ID', 'User Name']).agg({
            'Total Staffed Duration_sec': 'sum',
            'Total Ready Duration_sec': 'sum',
            'Total Break Duration_sec': 'sum',
            'Total Idle Time_sec': 'sum',
            'Total Talk Time in Interval_sec': 'sum',
            'Total ACW Duration in Interval_sec': 'sum'
        }).reset_index()

        # 6. Final Merge
        final_df = pd.merge(prod_final, sales_final, on=['Date', 'User ID'], how='left')
        final_df = pd.merge(final_df, break_pivot, on=['Date', 'User ID'], how='left').fillna(0)

        # 7. Convert Sec to HH:MM:SS
        # Identify all time-based columns (Base + Dynamic Breaks)
        base_sec_cols = [c for c in final_df.columns if c.endswith('_sec')]
        break_cols = [c for c in break_pivot.columns if c not in ['Date', 'User ID']]
        
        for col in base_sec_cols + break_cols:
            new_name = col.replace('_sec', '').replace('Total ', '')
            final_df[new_name] = final_df[col].apply(sec_to_hms)

        # 8. SAFE COLUMN SELECTION
        # We define what we WANT to see, but the code will only pick what actually EXISTS
        desired_order = [
            'Date', 'User Name', 'User ID', 'Staffed Duration', 'Ready Duration', 'Break Duration',
            'After Call Work', 'Lunch', 'First Break', 'Last Break', 'Meeting', 'Miscellaneous',
            'Idle Time', 'Talk Time', 'ACW Duration', 
            'Total_OB_Calls', 'Connected_OB_Calls', 'Unq_OB_Calls', 'Unq_CC_Calls'
        ]
        
        # This line prevents the KeyError: it only takes columns that exist in the final_df
        final_columns = [col for col in desired_order if col in final_df.columns]
        
        result = final_df[final_columns].copy()
        
        # Convert numeric counts to integers for clean display
        count_cols = ['Total_OB_Calls', 'Connected_OB_Calls', 'Unq_OB_Calls', 'Unq_CC_Calls']
        for col in count_cols:
            if col in result.columns:
                result[col] = result[col].astype(int)

        # Show Results
        st.success("Success! Report generated below.")
        st.dataframe(result)

        # Download Button
        csv = result.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Final Database", data=csv, file_name="Agent_Performance_Database.csv", mime="text/csv")

    except Exception as e:
        st.error(f"Error: {e}")
        st.info("Check if you uploaded the files in the correct boxes.")
