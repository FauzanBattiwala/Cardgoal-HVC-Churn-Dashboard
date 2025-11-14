import pandas as pd
import streamlit as st

# Step 1: Load and Clean the Data (updated path)
df = pd.read_excel('Master_Raw_Data(Sept-Oct).xlsx', sheet_name='Sept- Oct')
df['Creation Time'] = pd.to_datetime(df['Creation Time'])
df['Completion Time'] = pd.to_datetime(df['Completion Time'])
df['Is_Completed'] = (df['Actual Value'] > 0).astype(int)
df = df.dropna()
df = df[(df['Order Value'] >= 0) & (df['Actual Value'] >= 0)]

# Step 2: Assign Periods
df['Period'] = 'Other'
sept_start = pd.to_datetime('2025-09-11')
sept_end = pd.to_datetime('2025-10-11')
oct_start = pd.to_datetime('2025-10-12')
oct_end = pd.to_datetime('2025-11-11')
df.loc[(df['Creation Time'] >= sept_start) & (df['Creation Time'] <= sept_end), 'Period'] = 'September'
df.loc[(df['Creation Time'] >= oct_start) & (df['Creation Time'] <= oct_end), 'Period'] = 'October'
df = df[df['Period'] != 'Other']

# Step 3: User-Level Aggregation per Period
agg_df = df.groupby(['userId', 'Period']).agg(
    Num_Orders=('Order Number', 'count'),
    Total_Actual_Value=('Actual Value', 'sum'),
    Success_Rate=('Is_Completed', 'mean')
)
agg_df = agg_df.reset_index()

# Step 4: Identify HVCs per Period
platform_totals = agg_df.groupby('Period')['Total_Actual_Value'].sum().reset_index()
platform_totals.columns = ['Period', 'Platform_Total_Actual_Value']
agg_df = agg_df.merge(platform_totals, on='Period')
agg_df['Is_HVC'] = 0
for period in ['September', 'October']:
    period_df = agg_df[agg_df['Period'] == period].sort_values('Total_Actual_Value', ascending=False)
    num_users_period = len(period_df)
    top_20_cutoff = int(num_users_period * 0.2)
    hvc_users = period_df.iloc[:top_20_cutoff]['userId']
    agg_df.loc[(agg_df['Period'] == period) & agg_df['userId'].isin(hvc_users), 'Is_HVC'] = 1

# Step 5: Churn Flagging for September HVCs
sep_hvc = agg_df[(agg_df['Period'] == 'September') & (agg_df['Is_HVC'] == 1)][['userId', 'Total_Actual_Value', 'Success_Rate', 'Platform_Total_Actual_Value']]
sep_hvc.columns = ['userId', 'Total_Actual_Value_Sep', 'Success_Rate_Sep', 'Platform_Total_Sep']
oct_data = agg_df[agg_df['Period'] == 'October'][['userId', 'Total_Actual_Value', 'Success_Rate', 'Is_HVC', 'Platform_Total_Actual_Value']]
oct_data.columns = ['userId', 'Total_Actual_Value_Oct', 'Success_Rate_Oct', 'Is_HVC_Oct', 'Platform_Total_Oct']
hvc_df = sep_hvc.merge(oct_data, on='userId', how='left')
hvc_df[['Total_Actual_Value_Oct', 'Success_Rate_Oct', 'Is_HVC_Oct']] = hvc_df[['Total_Actual_Value_Oct', 'Success_Rate_Oct', 'Is_HVC_Oct']].fillna(0)
hvc_df['Platform_Total_Oct'] = hvc_df['Platform_Total_Oct'].fillna(hvc_df['Platform_Total_Sep'])
hvc_df['Pct_Contribution_Sep'] = hvc_df['Total_Actual_Value_Sep'] / hvc_df['Platform_Total_Sep'] * 100
hvc_df['Pct_Contribution_Oct'] = hvc_df['Total_Actual_Value_Oct'] / hvc_df['Platform_Total_Oct'] * 100
hvc_df['Churn_Flag_Contribution'] = (hvc_df['Pct_Contribution_Oct'] < (hvc_df['Pct_Contribution_Sep'] - 5)).astype(int)
hvc_df['Churn_Flag_Success'] = (hvc_df['Success_Rate_Oct'] < hvc_df['Success_Rate_Sep']).astype(int)
hvc_df['Churn_Flag_HVC_Drop'] = (hvc_df['Is_HVC_Oct'] == 0).astype(int)
hvc_df['Is_Churn'] = ((hvc_df['Churn_Flag_Contribution'] == 1) | (hvc_df['Churn_Flag_Success'] == 1) | (hvc_df['Churn_Flag_HVC_Drop'] == 1)).astype(int)

# Step 6: Analysis and Insights
stats = {
    'Churn_Rate': hvc_df['Is_Churn'].mean(),
    'Avg_Success_Rate_Change': (hvc_df['Success_Rate_Oct'] - hvc_df['Success_Rate_Sep']).mean(),
    'Avg_Pct_Contribution_Change': (hvc_df['Pct_Contribution_Oct'] - hvc_df['Pct_Contribution_Sep']).mean()
}
stats_df = pd.DataFrame([stats]).T.reset_index()
stats_df.columns = ['Metric', 'Value']
flag_breakdown = hvc_df[['Churn_Flag_Contribution', 'Churn_Flag_Success', 'Churn_Flag_HVC_Drop']].sum().reset_index()
flag_breakdown.columns = ['Flag', 'Count']
insights = [
    f"Churn rate among September HVCs: {stats['Churn_Rate']:.2%}",
    f"Average success rate change: {stats['Avg_Success_Rate_Change']:.2f}",
    f"Average contribution % change: {stats['Avg_Pct_Contribution_Change']:.2f}%",
    f"Top churn flag: {flag_breakdown.loc[flag_breakdown['Count'].idxmax(), 'Flag']} with {flag_breakdown['Count'].max()} users"
]

# Dashboard
st.title('Cardgoal HVC Churn Dashboard')

# Overview KPIs
st.header('Overview Metrics')
col1, col2, col3 = st.columns(3)
col1.metric("September HVCs", len(hvc_df))
col2.metric("Churn Rate", f"{stats['Churn_Rate']:.2%}")
col3.metric("Top Flag Count", flag_breakdown['Count'].max())

# Flagged Users Table with Filters
st.header('Flagged Churn Users')
flag_filter = st.multiselect('Filter by Flag', ['Churn_Flag_Contribution', 'Churn_Flag_Success', 'Churn_Flag_HVC_Drop'])
filtered_df = hvc_df[hvc_df['Is_Churn'] == 1]
if flag_filter:
    filtered_df = filtered_df[filtered_df[flag_filter].any(axis=1)]
st.dataframe(filtered_df)

# Stats Table
st.header('Stats for September HVCs')
st.dataframe(stats_df)

# Insights Panel
st.header('Key Insights')
for insight in insights:
    st.markdown(f"- {insight}")

# Export Churned Users CSV
st.header('Export')
csv = hvc_df[hvc_df['Is_Churn'] == 1].to_csv(index=False).encode('utf-8')

st.download_button(label="Download Churned HVCs CSV", data=csv, file_name='churned_hvcs.csv')
