import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px
import io
import os
import gc
import json
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from github import Github

# =====================================================================
# 1. PAGE CONFIGURATION (Must be the absolute first Streamlit command)
# =====================================================================
st.set_page_config(page_title="AP HMIS Anomaly Engine", page_icon="🏥", layout="wide", initial_sidebar_state="expanded")

# --- UNIFIED CUSTOM CSS: THE LOOKER STUDIO THEME & LAYOUT HACKS ---
st.markdown("""
    <style>
        .block-container {
            padding-top: 3rem !important; 
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            padding-bottom: 1rem !important;
            max-width: 100% !important;
        }
        .stAppDeployButton { display: none !important; }
        div.stMarkdown { margin-bottom: -15px !important; }
        div[data-testid="stVerticalBlock"] > div { gap: 0.5rem !important; }

        /* COLORS & THEME */
        .stApp { background-color: #fdfbed; }
        [data-testid="stSidebar"] { background-color: #f5f3e9; }
        [data-testid="stTabs"] { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0px 4px 6px rgba(0,0,0,0.05); }
        
        /* PROFESSIONAL LOOKER STUDIO TAB STYLING */
        .stTabs [data-baseweb="tab-list"] { gap: 12px; background-color: #ffffff; padding: 10px 15px; border-radius: 12px; box-shadow: 0px 2px 8px rgba(0,0,0,0.06); border-bottom: 4px solid #4285F4; }
        .stTabs [data-baseweb="tab"] { background-color: #f1f3f4 !important; border-radius: 8px !important; padding: 10px 20px !important; color: #3c4043 !important; font-size: 15px !important; font-weight: 800 !important; border: 1px solid #dadce0 !important; transition: all 0.2s ease-in-out; }
        .stTabs [data-baseweb="tab"]:hover { background-color: #e8f0fe !important; color: #1a73e8 !important; border-color: #8ab4f8 !important; }
        .stTabs [aria-selected="true"] { background-color: #1a73e8 !important; color: white !important; border: 1px solid #1a73e8 !important; box-shadow: 0px 4px 10px rgba(26, 115, 232, 0.3); }
        .stTabs [data-baseweb="tab-highlight"] { display: none; }

        /* EXECUTIVE SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #e0e0e0; padding-top: 1rem; }
        [data-testid="stSidebar"] h2, [data-testid="stSidebar"] label { color: #202124 !important; font-weight: 700 !important; }
        [data-testid="stSidebar"] div[data-baseweb="select"] > div, [data-testid="stSidebar"] input { background-color: #ffffff !important; border-radius: 8px !important; border: 1px solid #ced4da !important; }
        [data-testid="stSidebar"] button[kind="secondary"] { background-color: #1a73e8 !important; color: white !important; border-radius: 8px !important; font-weight: bold !important; border: none !important; }
        [data-testid="stSidebar"] button[kind="secondary"]:hover { background-color: #1557b0 !important; }
        
        /* CUSTOM HEADER & TILE STYLING */
        .ds-yellow-header { background-color: #e5ff4c; padding: 10px; border-radius: 20px; text-align: center; border: 1px solid #000; color: #0000bb; font-weight: bold; font-size: 24px; margin-bottom: 10px; }
        .kpi-tile { background-color: #ffffff; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0px 4px 10px rgba(0,0,0,0.1); border-top: 5px solid #4285F4; }
        .kpi-title { font-size: 20px; font-weight: 800; color: #333; margin-bottom: 10px; }
        .kpi-value { font-size: 38px; font-weight: bold; color: #000; }
        .chart-title { background-color: #cce5ff; padding: 10px; border-radius: 8px; text-align: center; font-size: 18px; font-weight: 800; color: #004085; margin-bottom: 15px; border: 1px solid #b8daff; }
        
        /* DOWNLOAD BUTTONS */
        div[data-testid="stDownloadButton"] > button { background-color: #198754 !important; color: white !important; border: none !important; font-weight: bold !important; }
        div[data-testid="stDownloadButton"] > button:hover { background-color: #146c43 !important; }
    </style>
""", unsafe_allow_html=True)

# =====================================================================
# 2. UTILITY FUNCTIONS & DATABASE
# =====================================================================
@st.cache_data
def load_indicator_list():
    with open("metrics.txt", "r", encoding="utf-8") as file:
        return [line.strip() for line in file.readlines() if line.strip()]

ALL_METRICS_LIST = load_indicator_list()

def sync_rules_to_github():
    """Exports DuckDB rules to Excel and pushes a commit to GitHub."""
    try:
        df = con_rules.execute("SELECT * FROM rules_metadata_v3").fetchdf()
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        file_content = excel_buffer.getvalue()
        
        g = Github(st.secrets["github_token"])
        repo = g.get_repo("nimmi555/hmis-dashboard")
        file_path = "rules_backup.xlsx"
        
        try:
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, "Auto-sync: Rules updated from dashboard", file_content, contents.sha)
        except:
            repo.create_file(file_path, "Auto-sync: Initial rules backup created", file_content)
    except Exception as e:
        st.error(f"GitHub Sync Failed: {e}")

def get_gdrive_service():
    creds_json = st.secrets["google_credentials"]
    creds_dict = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build('drive', 'v3', credentials=creds)

@st.cache_resource
def init_rules_db():
    con_rules = duckdb.connect("hmis_rules.duckdb")  
    
    con_rules.execute("""
        CREATE TABLE IF NOT EXISTS rules_metadata_v3 (
            Category_Code VARCHAR, Rule_ID VARCHAR, Rule_Description VARCHAR,
            Target_Format VARCHAR, Rule_Type VARCHAR, Logic_LHS VARCHAR, 
            Operator VARCHAR, Logic_RHS VARCHAR, Show_Difference BOOLEAN
        )
    """)
    
    try:
        existing_cols = [row[1] for row in con_rules.execute("PRAGMA table_info('rules_metadata_v3')").fetchall()]
        schema_additions = {
            "Rule_Category": "VARCHAR DEFAULT 'Single Month'",
            "Trend_Pattern": "VARCHAR DEFAULT 'None'",
            "PHC_Area_Scope": "VARCHAR DEFAULT 'All'",
            "Non_PHC_Ownership": "VARCHAR DEFAULT 'All'",
            "Trend_Window_Months": "INTEGER DEFAULT 3",
            "Trend_Threshold": "FLOAT DEFAULT 3.0"
        }
        for col_name, col_def in schema_additions.items():
            if col_name not in existing_cols:
                con_rules.execute(f"ALTER TABLE rules_metadata_v3 ADD COLUMN {col_name} {col_def}")
    except Exception:
        pass
        
    count = con_rules.execute("SELECT COUNT(*) FROM rules_metadata_v3").fetchone()[0]
    if count == 0 and os.path.exists("rules_backup.xlsx"):
        try:
            df_backup = pd.read_excel("rules_backup.xlsx", engine="openpyxl")
            expected_cols = {
                "Category_Code": "M1", "Rule_ID": "0", "Rule_Description": "", "Target_Format": "All Formats", 
                "Rule_Type": "Math", "Logic_LHS": "", "Operator": "=", "Logic_RHS": "", "Show_Difference": True,
                "Rule_Category": "Single Month", "Trend_Pattern": "None", "PHC_Area_Scope": "All",
                "Non_PHC_Ownership": "All", "Trend_Window_Months": 3, "Trend_Threshold": 3.0
            }
            
            for col, default_val in expected_cols.items():
                if col not in df_backup.columns:
                    df_backup[col] = default_val
                    
            df_backup = df_backup[list(expected_cols.keys())]
            con_rules.execute("INSERT INTO rules_metadata_v3 SELECT * FROM df_backup")
        except Exception:
            pass 
            
    con_rules.execute("""
        CREATE TABLE IF NOT EXISTS admin_settings (
            setting_name VARCHAR, setting_value VARCHAR
        )
    """)

    pw_exists = con_rules.execute("SELECT * FROM admin_settings WHERE setting_name = 'admin_password'").fetchone()
    if not pw_exists:
        con_rules.execute("INSERT INTO admin_settings VALUES ('admin_password', 'Chirush@2023')")
        
    return con_rules

con_rules = init_rules_db()

@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_rules():
    try:
        return con_rules.execute("SELECT * FROM rules_metadata_v3").fetchdf()
    except:
        return pd.DataFrame()

# =====================================================================
# 3. ENTERPRISE CACHING LAYER & DATA LOADING
# =====================================================================
@st.cache_data(ttl=600, show_spinner="Fetching data from Google Drive...")
def get_cached_hmis_data(sel_fy):
    """Downloads HMIS files using dynamic PyArrow column pruning to prevent OOM."""
    from googleapiclient.http import MediaIoBaseDownload
    
    # 1. DYNAMIC COLUMN PRUNING: Only load columns needed by active rules
    rules_df = get_cached_rules()
    required_cols = {"Month", "District Name", "Format Type", "Facility Code", "Facility Name", "Rural/Urban", "Ownership"}
    
    if not rules_df.empty:
        for _, row in rules_df.iterrows():
            metrics = re.findall(r'\[(.*?)\]', str(row.get('Logic_LHS', '')) + " " + str(row.get('Logic_RHS', '')))
            required_cols.update(metrics)
            
    try:
        service = get_gdrive_service()
        folder_id = "1TK3CsZc_9xday99mBbYoLQCMBuVLrznQ"
        query = f"'{folder_id}' in parents and name contains 'HMIS_Data_{sel_fy}' and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)", includeItemsFromAllDrives=True, supportsAllDrives=True).execute()
        items = results.get('files', [])
        
        if not items:
            return pd.DataFrame() 
            
        all_dataframes = []
        for item in items:
            file_id = item['id']
            request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            file_buffer.seek(0)
            
            # 2. PYARROW BACKEND + USECOLS LIMITER
            try:
                df = pd.read_csv(
                    file_buffer, 
                    engine="pyarrow", 
                    dtype_backend="pyarrow", 
                    usecols=lambda c: c in required_cols # Safely skips unused columns
                )
                if not df.empty:
                    all_dataframes.append(df)
            except Exception:
                pass 
                
        if all_dataframes:
            master_df = pd.concat(all_dataframes, ignore_index=True)
            return master_df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"☁️ Failed to load data from Google Drive: {e}")
        return pd.DataFrame()

def get_filtered_hmis_data(sel_fy):
    """Gets cached Drive data and slices out excluded months. NO .copy() memory duplication."""
    raw_df = get_cached_hmis_data(sel_fy)
    if raw_df.empty:
        return raw_df
        
    try:
        disabled_row = con_rules.execute("SELECT setting_value FROM admin_settings WHERE setting_name = 'disabled_months'").fetchone()
        if disabled_row and disabled_row[0]:
            disabled_list = [m.strip() for m in disabled_row[0].split(',')]
            raw_df = raw_df[~raw_df['Month'].isin(disabled_list)]
    except Exception:
        pass 
        
    return raw_df

# =====================================================================
# 4. SIDEBAR & SECURE ADMIN ACCESS
# =====================================================================
st.sidebar.header("🔍 Global Filters")
financial_year = st.sidebar.selectbox("Financial Year", ["2026-27"])

try:
    master_df = get_filtered_hmis_data(financial_year)
    if not master_df.empty:
        db_months = master_df['Month'].dropna().unique().tolist()
        dist_col = 'District Name' if 'District Name' in master_df.columns else 'District_Name'
        if dist_col in master_df.columns:
            db_districts = master_df[dist_col].dropna().unique().tolist()
        else:
            db_districts = []
    else:
        db_months, db_districts = [], []
except Exception as e:
    st.sidebar.error(f"Filter Error: {e}")
    db_months, db_districts = [], []

month_list = ["All Months"] + db_months if db_months else ["All Months"]
district_list = ["All Districts"] + sorted(db_districts) if db_districts else ["All Districts"]

selected_month = st.sidebar.selectbox("Reporting Month", month_list)
selected_district = st.sidebar.selectbox("District Name", district_list)
facility_code = st.sidebar.text_input("Facility Code", placeholder="e.g., 44151234")

col_empty, col_btn = st.sidebar.columns([2, 1.5])
with col_btn:
    search_triggered = st.button("🔍 Search", use_container_width=True)

if search_triggered:
    st.sidebar.success("Filters applied globally!")

st.sidebar.markdown("---")

# The Backdoor: Only show the password box if the URL contains "?mode=admin"
if st.query_params.get("mode") == "admin":
    admin_password = st.sidebar.text_input("🔒 Admin Access", type="password", help="Enter master password to unlock")
    try:
        current_db_password = con_rules.execute("SELECT setting_value FROM admin_settings WHERE setting_name = 'admin_password'").fetchone()[0]
    except:
        current_db_password = "admin"

    is_admin = (admin_password == current_db_password)
    
    if is_admin:
        if st.sidebar.button("🔄 Force Refresh Drive Data", use_container_width=True):
            st.cache_data.clear()
            st.sidebar.success("✅ Cache wiped! Next search will pull fresh files.")
else:
    is_admin = False

# =====================================================================
# 5. MASTER EXECUTION ENGINES
# =====================================================================
def run_anomaly_engine(sel_fy, sel_month, sel_dist, fac_code):
    gc.collect() # 🧹 FORCE PYTHON TO DUMP OLD MEMORY BEFORE RUNNING
    
    full_fy_df = get_filtered_hmis_data(sel_fy)
    rules_df = get_cached_rules()
    
    if full_fy_df.empty or rules_df.empty:
        return pd.DataFrame()
        
    # Zero-copy slicing to preserve memory
    raw_df = full_fy_df
    if sel_month != "All Months":
        raw_df = raw_df[raw_df['Month'] == sel_month]
    if sel_dist != "All Districts":
        raw_df = raw_df[raw_df['District Name'] == sel_dist]
    if fac_code:
        raw_df = raw_df[raw_df['Facility Code'].astype(str) == str(fac_code)]
        
    anomalies = []
    
    for _, rule in rules_df.iterrows():
        r_id = rule['Rule_ID']
        r_desc = rule['Rule_Description']
        r_type = rule.get('Rule_Category', rule.get('Rule_Type', 'Math')) 
        t_format = str(rule['Target_Format'])
        lhs_raw = str(rule['Logic_LHS'])
        op = str(rule['Operator'])
        rhs_raw = str(rule['Logic_RHS'])
        
        if r_type == 'Math' or r_type == 'Single Month':
            df_eval = raw_df
            
            if "All Formats" not in t_format:
                formats = [f.strip() for f in t_format.split(',')]
                df_eval = df_eval[df_eval['Format Type'].isin(formats)]
                
            phc_scope = str(rule.get('PHC_Area_Scope', 'All'))
            non_phc_own = str(rule.get('Non_PHC_Ownership', 'All'))
            
            if phc_scope in ['Rural', 'Urban']:
                phc_mask = df_eval['Format Type'] == 'PHC Format'
                if 'Rural/Urban' in df_eval.columns:
                    ru_match = df_eval['Rural/Urban'].astype(str).str.strip().str.upper() == phc_scope.upper()
                    df_eval = df_eval[(~phc_mask) | (phc_mask & ru_match)]
                    
            if non_phc_own in ['Public', 'Private']:
                non_phc_mask = df_eval['Format Type'] != 'PHC Format'
                if 'Ownership' in df_eval.columns:
                    own_match = df_eval['Ownership'].astype(str).str.strip().str.upper() == non_phc_own.upper()
                    df_eval = df_eval[(~non_phc_mask) | (non_phc_mask & own_match)]
                elif 'Facility Name' in df_eval.columns:
                    is_pvt = df_eval['Facility Name'].str.contains('Private|Pvt|Trust|NGO', case=False, na=False)
                    target_match = is_pvt if non_phc_own == 'Private' else ~is_pvt
                    df_eval = df_eval[(~non_phc_mask) | (non_phc_mask & target_match)]
            
            if df_eval.empty:
                continue
            
            metrics = list(set(re.findall(r'\[(.*?)\]', lhs_raw + " " + rhs_raw)))
            
            # Convert ONLY the required metrics to numbers safely (uses .loc to avoid SettingWithCopy warnings)
            df_eval = df_eval.copy() # Safe localized copy for math manipulation
            for m in metrics:
                if m in df_eval.columns:
                    df_eval.loc[:, m] = pd.to_numeric(df_eval[m], errors='coerce').fillna(0)
            
            missing = [m for m in metrics if m not in df_eval.columns]
            
            if not missing:
                eval_lhs, eval_rhs = lhs_raw, rhs_raw
                for m in metrics:
                    eval_lhs = eval_lhs.replace(f"[{m}]", f"`{m}`")
                    eval_rhs = eval_rhs.replace(f"[{m}]", f"`{m}`")
                
                try:
                    eval_op = "==" if op == "=" else ("!=" if op == "<>" else op)
                    eval_str = f"({eval_lhs}) {eval_op} ({eval_rhs})"
                    
                    mask = df_eval.eval(eval_str)
                    failed_rows = df_eval[mask]
                    
                    for _, row in failed_rows.iterrows():
                        anomalies.append({
                            "Month": row['Month'], "District Name": row['District Name'],
                            "Format Type": row['Format Type'], "Facility Code": row['Facility Code'],
                            "Facility Name": row['Facility Name'], "Rule_ID": r_id,
                            "Anomaly Type": r_desc, "Error Count": 1
                        })
                except Exception:
                    pass
                    
    return pd.DataFrame(anomalies)

def run_trend_engine(sel_fy, sel_dist, fac_code):
    gc.collect() # 🧹 FORCE PYTHON TO DUMP OLD MEMORY BEFORE RUNNING
    
    full_fy_df = get_filtered_hmis_data(sel_fy)
    rules_df = get_cached_rules()
    
    if full_fy_df.empty or rules_df.empty:
        return pd.DataFrame()
        
    mom_rules = rules_df[rules_df['Rule_Category'] == 'MoM Trend']
    if mom_rules.empty:
        return pd.DataFrame()
        
    # Slicing without full copy
    df_series = full_fy_df
    if sel_dist != "All Districts":
        df_series = df_series[df_series['District Name'] == sel_dist]
    if fac_code:
        df_series = df_series[df_series['Facility Code'].astype(str) == str(fac_code)]
        
    # Safe localized copy for time-series prep
    df_series = df_series.copy()
    df_series['Date_Parsed'] = pd.to_datetime(df_series['Month'], format='%b-%Y', errors='coerce')
    df_series = df_series.sort_values(by=['Facility Code', 'Date_Parsed'])
        
    trend_anomalies = []
    
    for _, rule in mom_rules.iterrows():
        r_id = rule['Rule_ID']
        r_desc = rule['Rule_Description']
        pattern = str(rule['Trend_Pattern'])
        t_format = str(rule['Target_Format'])
        window = int(rule.get('Trend_Window_Months', 1))
        threshold = float(rule.get('Trend_Threshold', 0.0))
        
        df_eval = df_series.copy()
        
        phc_scope = str(rule.get('PHC_Area_Scope', 'All'))
        non_phc_own = str(rule.get('Non_PHC_Ownership', 'All'))
        
        if "All Formats" not in t_format:
            formats = [f.strip() for f in t_format.split(',')]
            df_eval = df_eval[df_eval['Format Type'].isin(formats)]
            
        if phc_scope in ['Rural', 'Urban']:
            phc_mask = df_eval['Format Type'] == 'PHC Format'
            if 'Rural/Urban' in df_eval.columns:
                ru_match = df_eval['Rural/Urban'].astype(str).str.strip().str.upper() == phc_scope.upper()
                df_eval = df_eval[(~phc_mask) | (phc_mask & ru_match)]
                
        if non_phc_own in ['Public', 'Private']:
            non_phc_mask = df_eval['Format Type'] != 'PHC Format'
            if 'Ownership' in df_eval.columns:
                own_match = df_eval['Ownership'].astype(str).str.strip().str.upper() == non_phc_own.upper()
                df_eval = df_eval[(~non_phc_mask) | (non_phc_mask & own_match)]
            elif 'Facility Name' in df_eval.columns:
                is_pvt = df_eval['Facility Name'].str.contains('Private|Pvt|Trust|NGO', case=False, na=False)
                target_match = is_pvt if non_phc_own == 'Private' else ~is_pvt
                df_eval = df_eval[(~non_phc_mask) | (non_phc_mask & target_match)]
                
        if df_eval.empty: continue

        if "Sudden Spike" in pattern:
            target_metric = str(rule['Logic_LHS']).strip('[]')
            if target_metric in df_eval.columns:
                df_eval[target_metric] = pd.to_numeric(df_eval[target_metric], errors='coerce').fillna(0)
                df_eval['Historical_Avg'] = df_eval.groupby('Facility Code')[target_metric].transform(lambda x: x.shift(1).rolling(window, min_periods=1).mean())
                mask = (df_eval[target_metric] > (df_eval['Historical_Avg'] * threshold)) & (df_eval['Historical_Avg'] > 0)
                failed_rows = df_eval[mask]
                for _, row in failed_rows.iterrows():
                    trend_anomalies.append({
                        "Month": row['Month'], "District Name": row['District Name'], "Format Type": row['Format Type'],
                        "Facility Code": row['Facility Code'], "Facility Name": row['Facility Name'],
                        "Rule_ID": r_id, "Anomaly Type": r_desc, "Pattern": "Spike", 
                        "Details": f"Value {row[target_metric]} is {threshold}x higher than historical avg {round(row['Historical_Avg'], 1)}"
                    })
                    
        elif "Repeated Constant" in pattern:
            target_metric = str(rule['Logic_LHS']).strip('[]')
            if target_metric in df_eval.columns:
                df_eval[target_metric] = pd.to_numeric(df_eval[target_metric], errors='coerce').fillna(0)
                df_eval['Rolling_Min'] = df_eval.groupby('Facility Code')[target_metric].transform(lambda x: x.rolling(window).min())
                df_eval['Rolling_Max'] = df_eval.groupby('Facility Code')[target_metric].transform(lambda x: x.rolling(window).max())
                mask = (df_eval['Rolling_Min'] == df_eval['Rolling_Max']) & (df_eval[target_metric] > 0)
                failed_rows = df_eval[mask]
                for _, row in failed_rows.iterrows():
                    trend_anomalies.append({
                        "Month": row['Month'], "District Name": row['District Name'], "Format Type": row['Format Type'],
                        "Facility Code": row['Facility Code'], "Facility Name": row['Facility Name'],
                        "Rule_ID": r_id, "Anomaly Type": r_desc, "Pattern": "Flatline", 
                        "Details": f"Value {row[target_metric]} copy-pasted for {window} consecutive months"
                    })

        elif "Category Shift" in pattern:
            metrics = re.findall(r'\[(.*?)\]', str(rule['Logic_LHS']))
            if len(metrics) == 2:
                sub_metric, tot_metric = metrics[0], metrics[1]
                if sub_metric in df_eval.columns and tot_metric in df_eval.columns:
                    df_eval[sub_metric] = pd.to_numeric(df_eval[sub_metric], errors='coerce').fillna(0)
                    df_eval[tot_metric] = pd.to_numeric(df_eval[tot_metric], errors='coerce').fillna(0)
                    df_eval['Hist_Max'] = df_eval.groupby('Facility Code')[sub_metric].transform(lambda x: x.shift(1).rolling(window, min_periods=1).max())
                    df_eval['Current_Share'] = (df_eval[sub_metric] / df_eval[tot_metric].replace(0, 1)) * 100
                    mask = (df_eval['Hist_Max'] == 0) & (df_eval['Current_Share'] >= threshold) & (df_eval[tot_metric] > 0)
                    failed_rows = df_eval[mask]
                    for _, row in failed_rows.iterrows():
                        trend_anomalies.append({
                            "Month": row['Month'], "District Name": row['District Name'], "Format Type": row['Format Type'],
                            "Facility Code": row['Facility Code'], "Facility Name": row['Facility Name'],
                            "Rule_ID": r_id, "Anomaly Type": r_desc, "Pattern": "Category Shift",
                            "Details": f"Historically 0, but suddenly jumped to {round(row['Current_Share'], 1)}% of total ({row[sub_metric]}/{row[tot_metric]})"
                        })

        elif "Copy-Paste" in pattern:
            metrics = list(set(re.findall(r'\[(.*?)\]', str(rule['Logic_LHS']))))
            valid_metrics = [m for m in metrics if m in df_eval.columns]
            if len(valid_metrics) > 1:
                for m in valid_metrics:
                    df_eval[m] = pd.to_numeric(df_eval[m], errors='coerce').fillna(0)
                df_eval['Min_Val'] = df_eval[valid_metrics].min(axis=1)
                df_eval['Max_Val'] = df_eval[valid_metrics].max(axis=1)
                mask = (df_eval['Min_Val'] == df_eval['Max_Val']) & (df_eval['Max_Val'] > 0)
                failed_rows = df_eval[mask]
                for _, row in failed_rows.iterrows():
                    val = row['Max_Val']
                    trend_anomalies.append({
                        "Month": row['Month'], "District Name": row['District Name'], "Format Type": row['Format Type'],
                        "Facility Code": row['Facility Code'], "Facility Name": row['Facility Name'],
                        "Rule_ID": r_id, "Anomaly Type": r_desc, "Pattern": "Copy-Paste",
                        "Details": f"Value {val} was copy-pasted across {len(valid_metrics)} different indicators"
                    })

    return pd.DataFrame(trend_anomalies)

# Run Engine Instantly
df_anomalies = run_anomaly_engine(financial_year, selected_month, selected_district, facility_code)

if not df_anomalies.empty:
    df_dist_filtered = df_anomalies.groupby('District Name')['Error Count'].sum().reset_index().sort_values(by="Error Count", ascending=True)
    facilities_count = df_anomalies['Facility Code'].nunique()
    anomaly_types_count = df_anomalies['Anomaly Type'].nunique()
    total_anomalies_calc = df_anomalies['Error Count'].sum()
    df_top_rules = df_anomalies.groupby('Anomaly Type')['Error Count'].sum().reset_index().sort_values(by='Error Count', ascending=False)
    
    df_abstract_final = df_top_rules.rename(columns={'Error Count': 'Anomaly Count'})
    df_fac_final = df_anomalies.copy()
else:
    df_dist_filtered = pd.DataFrame(columns=["District Name", "Error Count"])
    df_top_rules = pd.DataFrame(columns=["Anomaly Type", "Error Count"])
    df_abstract_final = pd.DataFrame(columns=["Anomaly Type", "Anomaly Count"])
    df_fac_final = pd.DataFrame(columns=["Month", "District Name", "Format Type", "Facility Code", "Facility Name", "Anomaly Type", "Error Count"])
    facilities_count = anomaly_types_count = total_anomalies_calc = 0
    
pub_val, priv_val = 95.4, 4.6 

st.markdown('<div class="ds-yellow-header">HMIS DATA VALIDATION DASHBOARD, ANDHRA PRADESH</div>', unsafe_allow_html=True)
st.write("") 

# --- DYNAMIC MULTI-TAB ARCHITECTURE ---
public_tab_names = ["📊 HMIS Dash Board", "📑 Single Month Anomalies", "📈 MoM Trend Anomalies", "📜 Rules Dictionary", "📖 Indicators List"]
admin_tab_names = ["🏥 Facility wise anomalies", "🎯 Detailed Anomalies", "⚙️ Admin"]

tab_names = public_tab_names.copy()
if is_admin: tab_names.extend(admin_tab_names)
tabs = st.tabs(tab_names)

tab1, tab2, tab_mom, tab5, tab6 = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4]
if is_admin: tab3, tab4, tab7 = tabs[5], tabs[6], tabs[7]
master_anomalies_df = df_anomalies

# --- THE NATIVE POPUP DRILL-DOWN MODAL ---
@st.dialog("🔍 Deep-Dive Analysis Mode", width="large")
def show_drilldown_modal(selected_anomaly, raw_df, financial_year, selected_month, selected_district, facility_code):
    st.markdown(f"<h4 style='color: #d32f2f; margin-top: -10px; margin-bottom: 20px;'>{selected_anomaly}</h4>", unsafe_allow_html=True)
    
    try:
        rule_info_df = con_rules.execute("SELECT * FROM rules_metadata_v3 WHERE Rule_Description = ?", [selected_anomaly]).fetchdf()
        if rule_info_df.empty:
            st.error("Rule metadata missing.")
            return
            
        rule_info = rule_info_df.iloc[0]
        lhs_raw, rhs_raw, op, t_format = str(rule_info['Logic_LHS']), str(rule_info['Logic_RHS']), str(rule_info['Operator']), str(rule_info['Target_Format'])
        all_metrics_raw = re.findall(r'\[(.*?)\]', lhs_raw) + re.findall(r'\[(.*?)\]', rhs_raw)
        metrics_in_rule = list(dict.fromkeys(all_metrics_raw))
        
        if not raw_df.empty:
            raw_df = raw_df.copy() # Safe manipulation copy
            for m in metrics_in_rule:
                if m in raw_df.columns:
                    raw_df[m] = pd.to_numeric(raw_df[m], errors='coerce').fillna(0)
            
            phc_scope = str(rule_info.get('PHC_Area_Scope', 'All'))
            non_phc_own = str(rule_info.get('Non_PHC_Ownership', 'All'))
            
            if "All Formats" not in t_format:
                formats = [f.strip() for f in t_format.split(',')]
                raw_df = raw_df[raw_df['Format Type'].isin(formats)]
                
            if phc_scope in ['Rural', 'Urban']:
                phc_mask = raw_df['Format Type'] == 'PHC Format'
                if 'Rural/Urban' in raw_df.columns:
                    ru_match = raw_df['Rural/Urban'].astype(str).str.strip().str.upper() == phc_scope.upper()
                    raw_df = raw_df[(~phc_mask) | (phc_mask & ru_match)]
                    
            if non_phc_own in ['Public', 'Private']:
                non_phc_mask = raw_df['Format Type'] != 'PHC Format'
                if 'Ownership' in raw_df.columns:
                    own_match = raw_df['Ownership'].astype(str).str.strip().str.upper() == non_phc_own.upper()
                    raw_df = raw_df[(~non_phc_mask) | (non_phc_mask & own_match)]
                elif 'Facility Name' in raw_df.columns:
                    is_pvt = raw_df['Facility Name'].str.contains('Private|Pvt|Trust|NGO', case=False, na=False)
                    target_match = is_pvt if non_phc_own == 'Private' else ~is_pvt
                    raw_df = raw_df[(~non_phc_mask) | (non_phc_mask & target_match)]

            eval_lhs, eval_rhs = lhs_raw, rhs_raw
            for m in metrics_in_rule:
                eval_lhs, eval_rhs = eval_lhs.replace(f"[{m}]", f"`{m}`"), eval_rhs.replace(f"[{m}]", f"`{m}`")
            
            eval_op = "==" if op == "=" else ("!=" if op == "<>" else op)
            eval_str = f"({eval_lhs}) {eval_op} ({eval_rhs})"
            
            mask = raw_df.eval(eval_str)
            detailed_df = raw_df[mask].copy()
            
            if not detailed_df.empty:
                detailed_df['LHS Value'] = detailed_df.eval(eval_lhs)
                detailed_df['RHS Value'] = detailed_df.eval(eval_rhs)
                detailed_df['Difference (LHS - RHS)'] = detailed_df['LHS Value'] - detailed_df['RHS Value']
                
                base_cols = ["Month", "District Name", "Sub-District / ULB Name", "Format Type", "Facility Code", "Facility Name"]
                display_cols = [c for c in base_cols if c in detailed_df.columns] + metrics_in_rule + ['Difference (LHS - RHS)']
                
                drill_final = detailed_df[display_cols].copy()
                drill_final.insert(0, 'S.No', range(1, len(drill_final) + 1))
                
                mk1, mk2, mk3 = st.columns(3)
                mk_style = "background-color: #f8f9fa; border-left: 4px solid #ff5722; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 15px;"
                with mk1: st.markdown(f'<div style="{mk_style}"><div style="font-size:12px; color:#555;">Total Errors</div><div style="font-size:22px; font-weight:bold; color:#d32f2f;">{len(drill_final):,}</div></div>', unsafe_allow_html=True)
                with mk2: st.markdown(f'<div style="{mk_style}"><div style="font-size:12px; color:#555;">Affected Facilities</div><div style="font-size:22px; font-weight:bold; color:#1976d2;">{drill_final["Facility Code"].nunique():,}</div></div>', unsafe_allow_html=True)
                with mk3: st.markdown(f'<div style="{mk_style}"><div style="font-size:12px; color:#555;">Affected Districts</div><div style="font-size:22px; font-weight:bold; color:#388e3c;">{drill_final["District Name"].nunique():,}</div></div>', unsafe_allow_html=True)

                # NATIVE STREAMLIT TABLE (No AgGrid)
                st.dataframe(drill_final, hide_index=True, use_container_width=True)
                
                clean_drill = drill_final.drop(columns=['Difference (LHS - RHS)', '::auto_unique_id::'], errors='ignore')
                name_parts = selected_anomaly.split(" ", 1)
                file_prefix = name_parts[0] if len(name_parts) == 2 else "Anomaly_Data"
                
                num_blank_columns = len(clean_drill.columns) - 1
                trailing_commas = "," * num_blank_columns
                csv_body = clean_drill.to_csv(index=False)
                final_csv = f'"{selected_anomaly}"{trailing_commas}\n{csv_body}'

                st.download_button(
                    label="📥 Download Detailed Report",
                    data=final_csv.encode('utf-8'),
                    file_name=f"{file_prefix}.csv", mime="text/csv", type="primary", use_container_width=True
                )
            else:
                st.info("No detailed data found for this rule under current filters.")
    except Exception as e:
        st.error(f"Error generating detailed view: {e}")

# =====================================================================
# TAB 1: HMIS DASHBOARD (Advanced State-Level Metrics)
# =====================================================================
with tab1:
    if not master_anomalies_df.empty:
        anomaly_types_count = master_anomalies_df['Rule_ID'].nunique()
        facilities_count = master_anomalies_df['Facility Code'].nunique()
        total_anomalies_calc = len(master_anomalies_df)
        df_dist_filtered = master_anomalies_df.groupby('District Name').size().reset_index(name='Error Count')
        df_top_rules = master_anomalies_df.groupby('Anomaly Type').size().reset_index(name='Error Count').sort_values(by='Error Count', ascending=False)
        
        if 'Facility Name' in master_anomalies_df.columns:
            priv_val = int(master_anomalies_df['Facility Name'].str.contains('Private|Pvt|Trust|NGO', case=False, na=False).sum())
            pub_val = total_anomalies_calc - priv_val
        else:
            pub_val, priv_val = total_anomalies_calc, 0
    else:
        anomaly_types_count = facilities_count = total_anomalies_calc = 0
        df_dist_filtered = pd.DataFrame({"District Name": ["No Data"], "Error Count": [0]})
        df_top_rules = pd.DataFrame({"Anomaly Type": ["No Errors"], "Error Count": [0]})
        pub_val, priv_val = 1, 0

    error_density = round(total_anomalies_calc / facilities_count, 1) if facilities_count > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(f'<div class="kpi-tile" style="border-top: 5px solid #d32f2f;"><div class="kpi-title">Total Anomalies</div><div class="kpi-value">{total_anomalies_calc:,}</div><div style="color: #d32f2f; font-size: 14px; font-weight: bold;">🔼 Live Engine Count</div></div>', unsafe_allow_html=True)
    with k2: st.markdown(f'<div class="kpi-tile" style="border-top: 5px solid #ff9800;"><div class="kpi-title">Facilities With Errors</div><div class="kpi-value">{facilities_count:,}</div><div style="color: #6c757d; font-size: 14px;">Requiring Intervention</div></div>', unsafe_allow_html=True)
    with k3: st.markdown(f'<div class="kpi-tile" style="border-top: 5px solid #1976d2;"><div class="kpi-title">Error Density</div><div class="kpi-value">{error_density}</div><div style="color: #6c757d; font-size: 14px;">Avg Errors per Facility</div></div>', unsafe_allow_html=True)
    with k4: st.markdown(f'<div class="kpi-tile" style="border-top: 5px solid #9c27b0;"><div class="kpi-title">Rules Triggered</div><div class="kpi-value">{anomaly_types_count}</div><div style="color: #6c757d; font-size: 14px;">Unique Logic Failures</div></div>', unsafe_allow_html=True)
        
    st.divider()
    col_chart1, col_chart2 = st.columns([1.5, 1])
    
    with col_chart1:
        st.markdown('<div class="chart-title">DISTRICT WISE ANOMALIES HEAT MAP</div>', unsafe_allow_html=True)
        fig_bar = px.bar(df_dist_filtered, x="Error Count", y="District Name", orientation='h', color_discrete_sequence=['#4285F4'], text="Error Count")
        fig_bar.update_traces(textposition='inside', insidetextanchor='middle', textangle=0, textfont=dict(size=18, color='white', family="Arial Black"))
        chart_height = max(380, len(df_dist_filtered) * 35) 
        fig_bar.update_layout(yaxis=dict(categoryorder='total ascending', tickfont=dict(size=14, color='black', family="Arial Black")), height=chart_height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        
        with st.container(height=400):
            st.plotly_chart(fig_bar, use_container_width=True)
        st.markdown(f'<div style="background-color: #ff9800; color: #000; font-weight: 900; font-size: 16px; padding: 12px; border-radius: 5px; display: flex; justify-content: space-between; margin-top: 10px;"><span>Grand total</span><span>{total_anomalies_calc:,}</span></div>', unsafe_allow_html=True)

    with col_chart2:
        st.markdown('<div class="chart-title">PUBLIC / PRIVATE %</div>', unsafe_allow_html=True)
        fig_pie = px.pie(pd.DataFrame({"Sector": ["Public", "Private"], "Value": [pub_val, priv_val]}), values='Value', names='Sector', color_discrete_sequence=['#4285F4', '#FF9900'])
        fig_pie.update_layout(height=160, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)', legend=dict(font=dict(size=14, color="#333", family="Arial Black")))
        fig_pie.update_traces(textposition='inside', textinfo='percent', textfont=dict(size=15, color='white', family="Arial Black"))
        st.plotly_chart(fig_pie, use_container_width=True)
        
        st.markdown('<div class="chart-title" style="margin-top: 10px;">TOP 10 ANOMALIES</div>', unsafe_allow_html=True)
        if total_anomalies_calc > 0 and not df_top_rules.empty:
            import textwrap
            top_10 = df_top_rules.head(10).copy()
            top_10['Short Rule'] = top_10['Anomaly Type'].apply(lambda x: str(x).split(" ")[0] if "-" in str(x) else str(x)[:15])
            top_10['Wrapped_Anomaly'] = top_10['Anomaly Type'].apply(lambda x: '<br>'.join(textwrap.wrap(str(x), width=45)))
            fig_donut = px.pie(top_10, values='Error Count', names='Short Rule', hole=0.5, custom_data=['Wrapped_Anomaly'])
            fig_donut.update_traces(
                hovertemplate="<b style='font-size:13px;'>%{customdata[0]}</b><br><br><b>Errors:</b> %{value}<br><b>Share:</b> %{percent}<extra></extra>",
                hoverlabel=dict(align="left", font=dict(size=13)),
                textposition='inside', textinfo='percent', textfont=dict(size=13, color='white', family="Arial Black")
            )
        else:
            fig_donut = px.pie(pd.DataFrame({"Anomaly Type": ["No Errors"], "Error Count": [1]}), values='Error Count', names='Anomaly Type', hole=0.5)
            fig_donut.update_traces(textinfo='none')
            
        fig_donut.update_layout(height=210, margin=dict(l=0, r=0, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)', showlegend=True, legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.0, font=dict(size=12, color="#333", family="Arial Black")))
        st.plotly_chart(fig_donut, use_container_width=True)

# =====================================================================
# TAB 2: ANOMALIES ABSTRACT & POPUP DRILL-DOWN (AgGrid Removed)
# =====================================================================
with tab2:
    @st.fragment
    def render_tab2_abstract():
        st.markdown("""
            <style>
            @keyframes sparkle-animation { 0% { color: #D32F2F; text-shadow: 0 0 4px rgba(211, 47, 47, 0.6); transform: scale(1); } 50% { color: #00B0FF; text-shadow: 0 0 10px #00B0FF, 0 0 20px #40C4FF; transform: scale(1.02); } 100% { color: #D32F2F; text-shadow: 0 0 4px rgba(211, 47, 47, 0.6); transform: scale(1); } }
            .animated-instruction { font-size: 24px; font-weight: 900; animation: sparkle-animation 1.5s ease-in-out infinite; margin-left: 15px; }
            .header-wrapper { font-size: 26px; font-weight: bold; margin-bottom: 20px; display: flex; align-items: center; border-bottom: 2px solid #eeeeee; padding-bottom: 10px; }
            </style>
            <div class="header-wrapper">📄 Anomalies Abstract Table: <span class="animated-instruction">👉 Click On Required Anomaly to get Detailed Report</span></div>
        """, unsafe_allow_html=True)
        
        if not master_anomalies_df.empty:
            abstract_df = master_anomalies_df.groupby('Anomaly Type').size().reset_index(name='Anomaly Count').sort_values(by='Anomaly Count', ascending=False)
            abstract_df.insert(0, 'Sl No', range(1, len(abstract_df) + 1))
            
            csv_data = abstract_df.to_csv(index=False).encode('utf-8')
            col_spacer, col_dl = st.columns([5, 1.5])
            with col_dl:
                st.download_button("📥 Download Abstract to CSV", data=csv_data, file_name="Abstract_Anomalies.csv", mime="text/csv", type="primary", use_container_width=True, key="dl_abs")
            
            # THE FIX: Streamlit Native Table replaces heavy AgGrid
            response = st.dataframe(
                abstract_df, 
                height=450, 
                use_container_width=True, 
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="abstract_main_grid"
            )
            
            tab2_total = abstract_df['Anomaly Count'].sum()
            st.markdown(f'<div style="background-color: #ff9800; color: #000; font-weight: 900; font-size: 16px; padding: 12px; border-radius: 5px; display: flex; justify-content: flex-start; gap: 15px; margin-top: 10px;"><span>Grand Total Anomalies:</span><span style="background-color: white; padding: 0px 10px; border-radius: 3px; color: red;">{tab2_total:,}</span></div>', unsafe_allow_html=True)
            
            # SELECTION HANDLING (Native Array Mapping)
            selected_indices = response.selection.rows
            if len(selected_indices) > 0:
                clicked_row_data = abstract_df.iloc[selected_indices[0]]
                sel_rows = [clicked_row_data.to_dict()]
            else:
                sel_rows = None
            
            if sel_rows is not None and len(sel_rows) > 0:
                selected_val = sel_rows[0]['Anomaly Type']
                
                if st.session_state.get('modal_anomaly_lock') != selected_val:
                    st.session_state['modal_anomaly_lock'] = selected_val
                    
                    raw_df_modal = get_filtered_hmis_data(financial_year) # Zero-copy fetch
                    
                    if not raw_df_modal.empty:
                        if selected_month != "All Months": 
                            raw_df_modal = raw_df_modal[raw_df_modal['Month'] == selected_month]
                        if selected_district != "All Districts": 
                            raw_df_modal = raw_df_modal[raw_df_modal['District Name'] == selected_district]
                        if facility_code: 
                            raw_df_modal = raw_df_modal[raw_df_modal['Facility Code'].astype(str) == str(facility_code)]
                    
                    show_drilldown_modal(selected_val, raw_df_modal, financial_year, selected_month, selected_district, facility_code)
            else:
                st.session_state['modal_anomaly_lock'] = None
        else:
            st.success("✅ No anomalies found for the selected criteria. The Abstract is clear.")
    render_tab2_abstract()        

# =====================================================================
# TAB 3: MoM TREND ANOMALIES (AgGrid Removed)
# =====================================================================
with tab_mom:
    @st.fragment
    def render_mom_anomalies():
        st.markdown("## 📈 Month-over-Month (MoM) Trend Anomalies")
        st.markdown("Detects historical time-series issues: Sudden Spikes, Flatlining Data, Category Shifts, and Multi-Indicator Copy-Paste errors.")
        
        mom_anomalies_df = run_trend_engine(financial_year, selected_district, facility_code)
        
        if not mom_anomalies_df.empty:
            st.error(f"🚨 Detected {len(mom_anomalies_df)} Trend Anomalies in {selected_district}")
            
            mom_abstract = mom_anomalies_df.groupby(['Anomaly Type', 'Pattern']).size().reset_index(name='Error Count').sort_values(by='Error Count', ascending=False)
            mom_abstract.insert(0, 'S.No', range(1, len(mom_abstract) + 1))
            
            st.markdown("### 📊 Trend Abstract")
            st.dataframe(mom_abstract, use_container_width=True, hide_index=True)
            
            st.markdown("### 🎯 Detailed Facility Trend Log")
            mom_details = mom_anomalies_df.copy()
            mom_details.insert(0, 'S.No', range(1, len(mom_details) + 1))
            
            st.dataframe(mom_details, height=500, use_container_width=True, hide_index=True)
            
            csv_mom = mom_details.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Trend Data", data=csv_mom, file_name="MoM_Trend_Anomalies.csv", mime="text/csv", type="primary")
        else:
            st.success("✅ No historical trend anomalies detected under the current filters.")
    render_mom_anomalies()

# =====================================================================
# TAB 3/4/5/6/7: ADMIN TABS (AgGrid Removed)
# =====================================================================
if is_admin:
    with tab3:
        @st.fragment
        def render_facility_anomalies():
            st.subheader("🏢 Facility Wise Anomalies Table")
            if not master_anomalies_df.empty:
                df_facility = master_anomalies_df.drop(columns=['Rule_ID'], errors='ignore')
                df_facility.insert(0, 'S.No', range(1, len(df_facility) + 1))
                
                csv_data = df_facility.to_csv(index=False).encode('utf-8')
                col_spacer, col_dl = st.columns([4, 1])
                with col_dl: st.download_button("📥 Download to CSV", data=csv_data, file_name="Facility_Wise_Anomalies.csv", mime="text/csv", type="primary", use_container_width=True)
                    
                st.dataframe(df_facility, height=500, use_container_width=True, hide_index=True)
            else:
                st.success("✅ No anomalies found for the selected criteria.")
        render_facility_anomalies()

    with tab4:
        @st.fragment
        def render_rule_viewer():
            st.subheader("🎯 Interactive Anomaly Rule Execution Viewer")
            active_cat_t4 = st.selectbox("📌 Select Anomaly Category:", [f"M{i}" for i in range(1, 18)], key="cat_tab4")
            rules_df = con_rules.execute("SELECT Rule_ID, Rule_Description, Target_Format, Logic_LHS, Operator, Logic_RHS FROM rules_metadata_v3 WHERE Category_Code = ?", [active_cat_t4]).fetchdf()
            
            if not rules_df.empty:
                rule_options = rules_df['Rule_ID'].tolist()
                col_label, col_radio = st.columns([1.5, 8.5])
                with col_label: st.markdown("<div style='margin-top: 14px; font-size: 16px; font-weight: bold;'>🎯 Select Rule No:</div>", unsafe_allow_html=True)
                with col_radio: selected_rule_id = st.radio("Select Rule", rule_options, horizontal=True, label_visibility="collapsed")
                
                rule_details = rules_df[rules_df['Rule_ID'] == selected_rule_id].iloc[0]
                st.markdown(f"<div class='chart-title' style='background-color:#ffeeba; border-color:#ffdf7e; color:#856404; margin-top: 5px; margin-bottom: 5px;'>{rule_details['Rule_Description']}</div>", unsafe_allow_html=True)
                
                lhs_raw, rhs_raw, op, t_format = str(rule_details['Logic_LHS']), str(rule_details['Logic_RHS']), str(rule_details['Operator']), str(rule_details['Target_Format'])
                all_metrics_raw = re.findall(r'\[(.*?)\]', lhs_raw) + re.findall(r'\[(.*?)\]', rhs_raw)
                metrics_in_rule = list(dict.fromkeys(all_metrics_raw))
                
                query = "SELECT * FROM hmis_master_data WHERE Financial_Year = ?"
                params = [financial_year]
                
                if selected_month != "All Months": query += " AND Month = ?"; params.append(selected_month)
                if selected_district != "All Districts": query += ' AND "District Name" = ?'; params.append(selected_district)
                if facility_code: query += ' AND "Facility Code" = ?'; params.append(facility_code)
                    
                try: df_rule_raw = con_rules.execute(query, params).fetchdf()
                except: df_rule_raw = pd.DataFrame()
                    
                if not df_rule_raw.empty:
                    for m in metrics_in_rule:
                        if m in df_rule_raw.columns: df_rule_raw[m] = pd.to_numeric(df_rule_raw[m], errors='coerce').fillna(0)
                    
                    if "All Formats" not in t_format:
                        formats = [f.strip() for f in t_format.split(',')]
                        df_rule_raw = df_rule_raw[df_rule_raw['Format Type'].isin(formats)]
                    
                    missing = [m for m in metrics_in_rule if m not in df_rule_raw.columns]
                    if missing:
                        st.error(f"Missing columns in uploaded data: {missing}")
                        df_rule_output = pd.DataFrame()
                    elif df_rule_raw.empty:
                        df_rule_output = pd.DataFrame()
                    else:
                        eval_lhs, eval_rhs = lhs_raw, rhs_raw
                        for m in metrics_in_rule:
                            eval_lhs = eval_lhs.replace(f"[{m}]", f"`{m}`")
                            eval_rhs = eval_rhs.replace(f"[{m}]", f"`{m}`")
                        
                        eval_op = "==" if op == "=" else ("!=" if op == "<>" else op)
                        eval_str = f"({eval_lhs}) {eval_op} ({eval_rhs})"
                        
                        try:
                            mask = df_rule_raw.eval(eval_str)
                            df_rule_output = df_rule_raw[mask].copy()
                            
                            if not df_rule_output.empty:
                                df_rule_output['LHS Value'] = df_rule_output.eval(eval_lhs)
                                df_rule_output['RHS Value'] = df_rule_output.eval(eval_rhs)
                                df_rule_output['Difference (LHS - RHS)'] = df_rule_output['LHS Value'] - df_rule_output['RHS Value']
                                base_cols = ["Month", "District Name", "Format Type", "Facility Code", "Facility Name"]
                                display_cols = [c for c in base_cols if c in df_rule_output.columns] + metrics_in_rule + ['Difference (LHS - RHS)']
                                df_rule_output = df_rule_output[display_cols]
                        except Exception as e:
                            st.error(f"Rule Evaluation Error: {e}")
                            df_rule_output = pd.DataFrame()
                else: df_rule_output = pd.DataFrame()

                if not df_rule_output.empty:
                    csv_data = df_rule_output.to_csv(index=False).encode('utf-8')
                    col_spacer, col_dl = st.columns([4, 1])
                    with col_dl: st.download_button("📥 Download to CSV", data=csv_data, file_name="Detailed_Anomalies.csv", mime="text/csv", type="primary", use_container_width=True)
                    df_rule_output.insert(0, 'S.No', range(1, len(df_rule_output) + 1))
                    
                    st.dataframe(df_rule_output, height=500, use_container_width=True, hide_index=True)
                else: st.success("✅ No anomalies found for this specific rule and filter combination.")
        render_rule_viewer()

with tab5:
    @st.fragment
    def render_rules_dictionary():
        st.subheader("📜 Dictionary of Active Anomaly Rules")
        try:
            rules_df = con_rules.execute("""
                SELECT Category_Code, Rule_ID, Rule_Description, Target_Format, Logic_LHS, Operator, Logic_RHS 
                FROM rules_metadata_v3 
                WHERE Rule_Category = 'Single Month' OR Rule_Category IS NULL OR Rule_Type = 'Math'
            """).fetchdf()
            
            if not rules_df.empty:
                csv = rules_df.to_csv(index=False).encode('utf-8')
                col_spacer, col_dl = st.columns([4, 1])
                with col_dl: st.download_button(label="📥 Download to CSV", data=csv, file_name="rules_dictionary.csv", mime="text/csv", type="primary", use_container_width=True)
                
                st.dataframe(rules_df, height=600, use_container_width=True, hide_index=True)
            else: st.info("No single-month rules found in the database.")
        except Exception as e: st.error(f"Error loading rules: {e}")
    render_rules_dictionary()

with tab6:
    @st.fragment
    def render_indicator_mapping():
        st.subheader("📖 Monthly Service Delivery Indicators Mapping")
        try:
            df_indicators = pd.read_excel("indicators_list.xlsx", header=1)
            csv_data = df_indicators.to_csv(index=False).encode('utf-8')
            col_spacer, col_dl = st.columns([4, 1])
            with col_dl: st.download_button("📥 Download to CSV", data=csv_data, file_name="Indicators_List.csv", mime="text/csv", type="primary", use_container_width=True)
            
            df_indicators = df_indicators.dropna(how='all', axis=1).fillna("").astype(str)
            if 'S.No' not in df_indicators.columns: df_indicators.insert(0, 'S.No', range(1, len(df_indicators) + 1))
                
            st.dataframe(df_indicators, height=600, use_container_width=True, hide_index=True)
            
        except FileNotFoundError: st.info("ℹ️ Please place your Excel file in the same folder as 'app.py' and name it exactly **indicators_list.xlsx**.")
        except Exception as e: st.error(f"Error loading the Excel file: {e}")
    render_indicator_mapping()

if is_admin:
    with tabs[7]:
        st.subheader("🔒 State Admin & Database Access")
        admin_action = st.radio("Select Action", ["🧮 Add New Rule", "✏️ Edit/Delete Rule", "📤 Upload HMIS Data", "🛑 Data Exclusions"], horizontal=True)
        st.divider()
        
        if admin_action == "📤 Upload HMIS Data":
            def force_drive_sync(file_buffer, file_name, mime_type):
                service = get_gdrive_service()
                folder_id = "1TK3CsZc_9xday99mBbYoLQCMBuVLrznQ"
                query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
                results = service.files().list(q=query, fields="files(id)", includeItemsFromAllDrives=True, supportsAllDrives=True).execute()
                items = results.get('files', [])
                if not items: raise Exception(f"⚠️ QUOTA LOCK: Please create a blank file named exactly '{file_name}' and drop it into your Drive folder first. Then upload again!")
                
                file_id = items[0]['id']
                media = MediaIoBaseUpload(file_buffer, mimetype=mime_type, resumable=True)
                uploaded_file = service.files().update(fileId=file_id, media_body=media, supportsAllDrives=True, fields='id').execute()
                return uploaded_file.get('id')

            @st.fragment
            def render_upload_data():
                st.markdown("### ☁️ Smart Cloud Data Uploader")
                upload_fy = st.selectbox("Select Financial Year to apply:", ["2026-27"])
                uploaded_files = st.file_uploader("Upload HMIS Data File(s)", type=["xlsx", "csv"], accept_multiple_files=True)
                
                if uploaded_files:
                    if st.button("🚀 Process & Sync to Google Drive", type="primary"):
                        with st.spinner("Splitting data and forcing sync to Google Drive..."):
                            for file in uploaded_files:
                                try:
                                    if file.name.endswith('.csv'): df = pd.read_csv(file)
                                    else: df = pd.read_excel(file)
                                        
                                    def clean_header(c): return re.sub(r'\s+', ' ', str(c).replace('\xa0', ' ').strip())
                                    df.columns = [clean_header(c) for c in df.columns]
                                    
                                    if 'Month' not in df.columns: st.error(f"❌ Upload aborted for {file.name}: No 'Month' column found."); continue
                                        
                                    month_names = df['Month'].astype(str).str.extract(r'([A-Za-z]{3})')[0].str.capitalize()
                                    fy_start = int(upload_fy.split('-')[0])
                                    month_to_num = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
                                    years = month_names.map(month_to_num).apply(lambda m: fy_start + 1 if m <= 3 else fy_start)
                                    df['Month'] = month_names + '-' + years.astype(str)
                                    df['Financial_Year'] = upload_fy
                                    if 'Facility Code' in df.columns: df['Facility Code'] = df['Facility Code'].astype(str)
                                        
                                    unique_months = df['Month'].dropna().unique()
                                    for month in unique_months:
                                        df_month = df[df['Month'] == month]
                                        target_filename = f"HMIS_Data_{upload_fy}_{month}.csv"
                                        df_month.to_csv(target_filename, index=False)
                                        with open(target_filename, "rb") as f: file_id = force_drive_sync(f, target_filename, "text/csv")
                                        os.remove(target_filename)
                                        st.success(f"✅ {month} data synced to Drive! (ID: {file_id})")
                                except Exception as e: st.error(f"❌ Failed processing {file.name}: {e}")
            render_upload_data()
            
        elif admin_action == "🧮 Add New Rule":
            @st.fragment
            def render_add_rule():
                st.markdown("### 🛠️ Advanced Formula Engine")
                if 'admin_success' in st.session_state: st.success(st.session_state.admin_success); del st.session_state.admin_success
                if st.session_state.get("clear_math_form"): st.session_state.update({"new_desc": "", "lhs_input": "", "rhs_input": "", "clear_math_form": False})
                if st.session_state.get("clear_trend_form"): st.session_state.update({"new_desc": "", "trend_val": "", "clear_trend_form": False})

                def add_metric_lhs():
                    m = st.session_state.get("helper_add")
                    if m and m != "-- Select a metric --": st.session_state.lhs_input = st.session_state.get("lhs_input", "") + f"[{m}] "
                def add_metric_rhs():
                    m = st.session_state.get("helper_add")
                    if m and m != "-- Select a metric --": st.session_state.rhs_input = st.session_state.get("rhs_input", "") + f"[{m}] "

                col_cat, col_id = st.columns([1, 1])
                with col_cat: new_rule_cat = st.selectbox("Assign to Category", [f"M{i}" for i in range(1, 18)], key="new_cat")
                try:
                    cat_rules = con_rules.execute("SELECT Rule_ID FROM rules_metadata_v3 WHERE Category_Code = ?", [new_rule_cat]).fetchdf()
                    if not cat_rules.empty:
                        max_num = max([int(re.search(r'\d+$', str(r)).group()) for r in cat_rules['Rule_ID'] if re.search(r'\d+$', str(r))] + [0])
                        next_num = max_num + 1
                    else: next_num = 1
                except: next_num = 1
                    
                with col_id: new_rule_id = st.text_input("Rule ID (Number)", value=str(next_num))

                format_options = ["All Formats", "SC Format", "PHC Format", "CHC Format", "SDH Format", "DH Format", "Ayush Format", "Medical College"]
                target_format_list = st.multiselect("Applies to Format Type(s)", format_options, default=["All Formats"], key="new_fmt")
                target_format = ", ".join(target_format_list) 
                
                has_phc = "PHC Format" in target_format_list or "All Formats" in target_format_list
                has_non_phc = any(f in target_format_list for f in ["SC Format", "CHC Format", "SDH Format", "DH Format", "Ayush Format", "Medical College", "All Formats"])
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    if has_phc: phc_area_scope = st.selectbox("🏡 PHC Area Scope", ["All", "Rural", "Urban"])
                    else: phc_area_scope = "All"
                with col_d2:
                    if has_non_phc: non_phc_ownership = st.selectbox("🏥 Ownership", ["All", "Public", "Private"])
                    else: non_phc_ownership = "All"

                new_rule_desc = st.text_input("Rule Description", key="new_desc", placeholder="Briefly describe the anomaly...")
                rule_type = st.radio("Rule Type", ["Single Month Validation", "Month-over-Month Trend Validation"], horizontal=True, key="new_type")
                
                if rule_type == "Single Month Validation":
                    helper_metric = st.selectbox("🔍 Search & Select Metric Name (Type to search)", ["-- Select a metric --"] + ALL_METRICS_LIST, key="helper_add")
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1: st.button("➕ Add to LHS Box", key="btn_add_lhs", on_click=add_metric_lhs, use_container_width=True)
                    with col_btn2: st.button("➕ Add to RHS Box", key="btn_add_rhs", on_click=add_metric_rhs, use_container_width=True)
                        
                    col_lhs, col_op, col_rhs = st.columns([4, 1, 4])
                    with col_lhs: lhs_expr = st.text_area("Left Hand Side (LHS)", key="lhs_input")
                    with col_op: operator = st.selectbox("Operator", [">", "<", ">=", "<=", "==", "!=", "<>"])
                    with col_rhs: rhs_expr = st.text_area("Right Hand Side (RHS)", key="rhs_input")
                        
                    if st.button("💾 Save Mathematical Rule", type="primary"):
                        check_dup = con_rules.execute("SELECT COUNT(*) FROM rules_metadata_v3 WHERE Category_Code = ? AND Rule_ID = ?", [new_rule_cat, new_rule_id]).fetchone()[0]
                        if not new_rule_id or not new_rule_desc: st.markdown("<p style='color:red'>❌ Fields cannot be empty.</p>", unsafe_allow_html=True)
                        elif check_dup > 0: st.markdown(f"<p style='color:red'>❌ ERROR: Rule '{new_rule_id}' exists!</p>", unsafe_allow_html=True)
                        else:
                            try:
                                con_rules.execute("INSERT INTO rules_metadata_v3 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [new_rule_cat, new_rule_id, new_rule_desc, target_format, 'Math', lhs_expr, operator, rhs_expr, True, "Single Month", "None", phc_area_scope, non_phc_ownership, 1, 0.0])
                                st.session_state.clear_math_form = True; st.session_state.admin_success = f"✅ Saved successfully!"; st.cache_data.clear(); sync_rules_to_github(); st.rerun()
                            except Exception as e: st.error(f"Database error: {e}")
                else:
                    trend_pattern = st.selectbox("Select Trend Pattern", ["⚡ Sudden Spike / Extreme Outlier", "🔄 Repeated Constant Values / Flatline", "⚠️ Category Shift / Zero-to-Max Anomaly", "📋 Multi-Indicator Copy-Paste"])
                    if "Sudden Spike" in trend_pattern:
                        target_raw = st.selectbox("🔍 Target Indicator", ["-- Select a metric --"] + ALL_METRICS_LIST, key="spike_metric")
                        target_metric = f"[{target_raw}]" if target_raw != "-- Select a metric --" else ""
                        c_w, c_t = st.columns(2)
                        with c_w: trend_window = st.slider("Lookback Window (Months)", 2, 12, 6)
                        with c_t: trend_threshold = st.number_input("Spike Multiplier", 1.5, 20.0, 3.0, 0.5)
                        lhs_expr, operator, rhs_expr = target_metric, ">", f"Avg({trend_window}M) * {trend_threshold}"
                    elif "Repeated Constant" in trend_pattern:
                        target_raw = st.selectbox("🔍 Target Indicator", ["-- Select a metric --"] + ALL_METRICS_LIST, key="flat_metric")
                        target_metric = f"[{target_raw}]" if target_raw != "-- Select a metric --" else ""
                        trend_window, trend_threshold = st.slider("Consecutive Months Identical", 2, 12, 4), 0.0
                        lhs_expr, operator, rhs_expr = target_metric, "==", f"LAG({trend_window}M)"
                    elif "Category Shift" in trend_pattern:
                        c_s, c_p = st.columns(2)
                        with c_s: sub_raw = st.selectbox("🔍 Sub-Indicator", ["-- Select a metric --"] + ALL_METRICS_LIST, key="cat_sub")
                        with c_p: tot_raw = st.selectbox("🔍 Total Indicator", ["-- Select a metric --"] + ALL_METRICS_LIST, key="cat_tot")
                        trend_window = st.slider("Lookback Zero Window (Months)", 3, 12, 6)
                        trend_threshold = st.slider("Current Share (%)", 50, 100, 90)
                        lhs_expr, operator, rhs_expr = f"([{sub_raw}] / [{tot_raw}]) * 100", ">=", f"{trend_threshold}%"
                    elif "Copy-Paste" in trend_pattern:
                        lhs_expr = st.text_area("Indicators Expected to Differ", "[1.1.2], [1.2.4]")
                        trend_window, trend_threshold, operator, rhs_expr = 1, 0.0, "==", "All Values Identical"
                    
                    if st.button("💾 Save Trend Rule", type="primary"):
                        check_dup = con_rules.execute("SELECT COUNT(*) FROM rules_metadata_v3 WHERE Category_Code = ? AND Rule_ID = ?", [new_rule_cat, new_rule_id]).fetchone()[0]
                        if not new_rule_id or not new_rule_desc: st.markdown("<p style='color:red'>❌ Fields required.</p>", unsafe_allow_html=True)
                        elif check_dup > 0: st.markdown(f"<p style='color:red'>❌ ERROR: Rule exists!</p>", unsafe_allow_html=True)
                        else:
                            try:
                                con_rules.execute("INSERT INTO rules_metadata_v3 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [new_rule_cat, new_rule_id, new_rule_desc, target_format, 'Trend', lhs_expr, operator, rhs_expr, True, "MoM Trend", trend_pattern, phc_area_scope, non_phc_ownership, int(trend_window), float(trend_threshold)])
                                st.session_state.clear_trend_form = True; st.session_state.admin_success = f"✅ Saved successfully!"; st.cache_data.clear(); sync_rules_to_github(); st.rerun()
                            except Exception as e: st.error(f"Database error: {e}")
            render_add_rule()

        elif admin_action == "✏️ Edit/Delete Rule":
            @st.fragment
            def render_edit_rule():
                st.markdown("### ✏️ Edit or Delete Existing Rules")
                if 'admin_success' in st.session_state: st.success(st.session_state.admin_success); del st.session_state.admin_success
                
                edit_cat = st.selectbox("📌 Select Category to Edit", [f"M{i}" for i in range(1, 18)], key="edit_cat_select")
                try: all_rules = ["-- Select a Rule --"] + con_rules.execute("SELECT Rule_ID FROM rules_metadata_v3 WHERE Category_Code = ?", [edit_cat]).fetchdf()['Rule_ID'].astype(str).tolist()
                except: all_rules = ["-- Select a Rule --"]
                    
                if len(all_rules) > 1:
                    rule_to_edit = st.selectbox("📌 Select Rule", all_rules)
                    if rule_to_edit != "-- Select a Rule --":
                        rule_details = con_rules.execute("SELECT * FROM rules_metadata_v3 WHERE Category_Code = ? AND Rule_ID = ?", [edit_cat, rule_to_edit]).fetchdf().iloc[0]
                        
                        edit_desc = st.text_input("Rule Description", value=str(rule_details['Rule_Description']))
                        format_options = ["All Formats", "SC Format", "PHC Format", "CHC Format", "SDH Format", "DH Format", "Ayush Format", "Medical College"]
                        pre_selected_formats = [f.strip() for f in str(rule_details['Target_Format']).split(',')] if ',' in str(rule_details['Target_Format']) else [str(rule_details['Target_Format'])]
                        edit_fmt = st.multiselect("Applies to Format Type(s)", format_options, default=pre_selected_formats)
                        new_formats_string = ", ".join(edit_fmt)
                        
                        has_phc = "PHC Format" in edit_fmt or "All Formats" in edit_fmt
                        has_non_phc = any(f in edit_fmt for f in ["SC Format", "CHC Format", "SDH Format", "DH Format", "Ayush Format", "Medical College", "All Formats"])
                        curr_phc, curr_non = str(rule_details.get('PHC_Area_Scope', 'All')), str(rule_details.get('Non_PHC_Ownership', 'All'))
                        
                        col_d1, col_d2 = st.columns(2)
                        with col_d1: edit_phc = st.selectbox("🏡 PHC Area Scope", ["All", "Rural", "Urban"], index=["All", "Rural", "Urban"].index(curr_phc) if has_phc and curr_phc in ["All", "Rural", "Urban"] else 0) if has_phc else "All"
                        with col_d2: edit_non_phc = st.selectbox("🏥 Ownership", ["All", "Public", "Private"], index=["All", "Public", "Private"].index(curr_non) if has_non_phc and curr_non in ["All", "Public", "Private"] else 0) if has_non_phc else "All"

                        col_lhs, col_op, col_rhs = st.columns([4, 1, 4])
                        with col_lhs: edit_lhs = st.text_area("Left Hand Side (LHS)", value=str(rule_details['Logic_LHS']))
                        with col_op:
                            ops = [">", "<", ">=", "<=", "==", "!=", "<>"]
                            edit_op = st.selectbox("Operator", ops, index=ops.index(str(rule_details['Operator'])) if str(rule_details['Operator']) in ops else 0)
                        with col_rhs: edit_rhs = st.text_area("Right Hand Side (RHS)", value=str(rule_details['Logic_RHS']))
                        
                        col_save, col_del = st.columns(2)
                        if col_save.button("💾 Save Changes", type="primary", use_container_width=True):
                            try:
                                con_rules.execute("UPDATE rules_metadata_v3 SET Rule_Description = ?, Target_Format = ?, Logic_LHS = ?, Operator = ?, Logic_RHS = ?, PHC_Area_Scope = ?, Non_PHC_Ownership = ? WHERE Category_Code = ? AND Rule_ID = ?", [edit_desc, new_formats_string, edit_lhs, edit_op, edit_rhs, edit_phc, edit_non_phc, edit_cat, rule_to_edit])
                                st.session_state.admin_success = f"✅ Rule {rule_to_edit} updated successfully!"; st.cache_data.clear(); sync_rules_to_github(); st.rerun()
                            except Exception as e: st.error(f"Error: {e}")
                                
                        if col_del.button("🗑️ Permanently Delete Rule", use_container_width=True):
                            try:
                                con_rules.execute("DELETE FROM rules_metadata_v3 WHERE Category_Code = ? AND Rule_ID = ?", [edit_cat, rule_to_edit])
                                st.session_state.admin_success = f"🗑️ Rule {rule_to_edit} deleted!"; st.cache_data.clear(); sync_rules_to_github(); st.rerun()
                            except Exception as e: st.error(f"Error: {e}")
            render_edit_rule()

        elif admin_action == "🛑 Data Exclusions":
            @st.fragment
            def render_data_exclusions():
                st.markdown("### 🛑 Data Exclusions (Admin Only)")
                raw_admin_df = get_cached_hmis_data(financial_year)
                all_raw_months = raw_admin_df['Month'].dropna().unique().tolist() if not raw_admin_df.empty else []
                
                try:
                    current_disabled_row = con_rules.execute("SELECT setting_value FROM admin_settings WHERE setting_name = 'disabled_months'").fetchone()
                    current_disabled = [m.strip() for m in current_disabled_row[0].split(',')] if current_disabled_row and current_disabled_row[0] else []
                except: current_disabled = []
                    
                valid_disabled = [m for m in current_disabled if m in all_raw_months]
                disabled_selection = st.multiselect("Select months to hide from the dashboard:", options=all_raw_months, default=valid_disabled)
                
                if st.button("💾 Save Exclusion Settings", type="primary"):
                    new_disabled_str = ",".join(disabled_selection)
                    exists = con_rules.execute("SELECT * FROM admin_settings WHERE setting_name = 'disabled_months'").fetchone()
                    if exists: con_rules.execute("UPDATE admin_settings SET setting_value = ? WHERE setting_name = 'disabled_months'", [new_disabled_str])
                    else: con_rules.execute("INSERT INTO admin_settings (setting_name, setting_value) VALUES ('disabled_months', ?)", [new_disabled_str])
                    st.success("✅ Settings saved! The dashboard will now hide those months.")
            render_data_exclusions()
