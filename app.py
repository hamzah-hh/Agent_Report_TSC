import streamlit as st
import pandas as pd

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Agent Performance Automator", layout="wide")
st.title("📊 AI-Powered Report Automator")
st.markdown("Upload your 3 CSV files below to generate the consolidated performance database.")

# --- HELPER FUNCTIONS ---
def hms_to_sec(t):
    if pd.isna(t) or t == '0' or t == 0: return 0
    try:
        t_clean = str(t).split('.')[0] # Ignore milliseconds
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
    # 1. Load Data
    prod = pd.read_csv(prod_file)
    sess = pd.read_csv(sess_file)
    sales = pd.read_csv(sales_file)

    # 2. Cleaning
    for df in [prod, sess, sales]:
        df.dropna(subset=['User ID'], inplace=True)
        df['User ID'] = df['User ID'].str.lower().str.strip()

    # Process Dates
    prod['Date'] = pd.to_datetime(prod['Interval Start'], dayfirst=True).dt.date
    sess['Date'] = pd.to_datetime(sess['Login Time'], dayfirst=True).dt.date
    sales['Date'] = pd.to_datetime(sales['Start Time'], dayfirst=True).dt.date

    # 3. Process Individual Breaks (Pivoting Session Details)
    sess['Break_Sec'] = sess['Break Duration'].apply(hms_to_sec)
    break_pivot = sess.pivot_table(
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

    # 7. Convert Sec to HMS
    dynamic_breaks = [c for c in break_pivot.columns if c not in ['Date', 'User ID']]
    time_cols_to_convert = ['Total Staffed Duration_sec', 'Total Ready Duration_sec', 
                            'Total Break Duration_sec', 'Total Idle Time_sec', 
                            'Total Talk Time in Interval_sec', 'Total ACW Duration in Interval_sec'] + dynamic_breaks
    
    for col in time_cols_to_convert:
        new_col_name = col.replace('_sec', '').replace('Total ', '')
        final_df[new_col_name] = final_df[col].apply(sec_to_hms)

    # Final Column Selection
    perf_cols = ['Idle Time', 'Talk Time', 'ACW Duration', 'Total_OB_Calls', 'Connected_OB_Calls', 'Unq_OB_Calls', 'Unq_CC_Calls']
    final_order = ['Date', 'User Name', 'User ID', 'Staffed Duration', 'Ready Duration', 'Break Duration'] + \
                  [b.replace('Total ', '') for b in dynamic_breaks] + perf_cols
    
    result = final_df[final_order].copy()
    
    # Show Results
    st.success("Analysis Complete!")
    st.dataframe(result)

    # Download Button
    csv = result.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Final Database", data=csv, file_name="Agent_Performance_Database.csv", mime="text/csv")