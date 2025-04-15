# signup-bot-frontend/1_Summary_Dashboard.py

import streamlit as st
import pandas as pd
import requests             
import logging
from datetime import datetime
import traceback
from collections import Counter

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# ACCOUNTS_SHEET_NAME = 'Accounts Data' # Sheet name is now handled by backend

# --- API Configuration ---      # <<<--- NEW SECTION --- >>>
SIGNUP_API_URL = st.secrets.get("SIGNUP_API_URL", None)
SIGNUP_API_KEY = st.secrets.get("SIGNUP_API_KEY", None)
HEADERS = {'X-API-Key': SIGNUP_API_KEY} if SIGNUP_API_KEY else {}

# --- Helper Functions ---
# Keep safe_get and format_boolean as they are used for displaying the DataFrame
def safe_get(data, key, default='N/A'):
    if key not in data.index: return default
    val = data.get(key)
    return default if pd.isna(val) or val == '' else val

def format_boolean(value):
    if isinstance(value, str):
        val_upper = value.strip().upper()
        if val_upper == 'TRUE': return "✅ Yes"
        elif val_upper == 'FALSE': return "❌ No"
    elif isinstance(value, bool): return "✅ Yes" if value else "❌ No"
    if value == '' or value == 'N/A' or pd.isna(value): return "⚪ Not Set"
    return f"❓ Unknown ({value})"

# --- Caching Data Loading ---   # <<<--- MODIFIED FUNCTION --- >>>
@st.cache_data(ttl=600) # Cache API response for 10 minutes
def fetch_summary_data_from_api():
    """Fetches profile summary data from the backend API's /profiles/summary endpoint."""
    if not SIGNUP_API_URL: return pd.DataFrame(), "SIGNUP_API_URL secret not configured."
    api_endpoint = f"{SIGNUP_API_URL}/profiles/summary"
    logging.info(f"Attempting to fetch summary data from: {api_endpoint}")
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=35) # Slightly longer timeout
        response.raise_for_status()
        data = response.json()

        # Expect API to return {"profiles": [ {...}, {...} ]}
        if isinstance(data, dict) and 'profiles' in data and isinstance(data['profiles'], list):
            if not data['profiles']: # Handle empty list case
                logging.info("API returned empty profile list for summary.")
                return pd.DataFrame(), "No profile data found in the backend/sheet." # Informative message

            # Convert list of dicts to DataFrame
            df = pd.DataFrame(data['profiles'])
            logging.info(f"Fetched and created DataFrame with {len(df)} profiles.")

            # --- Perform Type Conversions (Crucial after loading from JSON) ---
            # Numeric columns
            numeric_cols = ['Number'] # Add other known numeric cols if any
            for col in numeric_cols:
                if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')

            # Trust score (handle percentage string potentially returned as string)
            if 'Trust score' in df.columns:
                # Apply conversion safely, handling potential None values from JSON
                df['Trust score_numeric'] = df['Trust score'].astype(str).str.replace('%', '', regex=False).str.strip()
                df['Trust score_numeric'] = pd.to_numeric(df['Trust score_numeric'], errors='coerce')

            # Datetime columns (JSON often transfers dates as ISO strings)
            datetime_cols = ['date of modification', 'Created Time', 'Last Open Time']
            for col in datetime_cols:
                if col in df.columns:
                     # pd.to_datetime handles ISO strings well, coerce errors to NaT
                     df[col] = pd.to_datetime(df[col], errors='coerce')

            logging.info("Performed data type conversions on fetched data.")
            # logging.info(f"DataFrame dtypes after API load & conversion:\n{df.dtypes}")

            return df, None # Return DataFrame and no error
        else:
            # Handle unexpected JSON structure from API
            logging.error(f"API Error: Invalid summary data format received: {data}")
            return pd.DataFrame(), "API Error: Invalid summary data format received from backend."

    except requests.exceptions.ConnectionError:
         logging.error(f"API Connection Error: Could not connect to {SIGNUP_API_URL}")
         return pd.DataFrame(), f"Connection Error: Could not connect to backend API at `{SIGNUP_API_URL}`."
    except requests.exceptions.Timeout:
         logging.error(f"API Timeout Error fetching summary from {api_endpoint}")
         return pd.DataFrame(), f"Timeout Error: Request to `{api_endpoint}` timed out."
    except requests.exceptions.HTTPError as e:
         error_detail = ""; 
         try: error_detail = response.json().get("error", response.text)
         except: error_detail = response.text
         logging.error(f"API HTTP Error {response.status_code} fetching summary: {error_detail}")
         return pd.DataFrame(), f"HTTP Error {response.status_code}: Failed to fetch summary. API Message: {error_detail}"
    except requests.exceptions.RequestException as e:
         logging.error(f"API Request Error fetching summary: {e}")
         return pd.DataFrame(), f"Request Error: An unexpected error occurred fetching summary: {e}"
    except Exception as e: # Catch pandas errors or other processing errors
         logging.error(f"Error processing summary data after fetch: {e}", exc_info=True)
         return pd.DataFrame(), f"Error processing data after fetching: {e}"

# --- Streamlit App Layout ---
st.set_page_config(page_title="Signup Bot Dashboard (Remote)", layout="wide")

st.title("🤖 Signup Bot Dashboard (Remote)")
st.caption(f"Data fetched via API from backend: `{SIGNUP_API_URL}`") # Update caption

# --- Check API Config ---       # <<<--- ADDED CHECK --- >>>
if not SIGNUP_API_URL:
    st.error("🚨 Critical Error: SIGNUP_API_URL secret is not set."); st.stop()
if not SIGNUP_API_KEY:
    st.warning("⚠️ Warning: SIGNUP_API_KEY secret is not set.")

# --- Load Data ---              # <<<--- MODIFIED CALL --- >>>
error_placeholder = st.empty()
with st.spinner("Fetching latest profile data via API..."):
    profile_df, error_message = fetch_summary_data_from_api() # Call the new API function

if error_message and profile_df.empty: # Show error only if DF is empty too
    error_placeholder.error(error_message)
    st.info("Check backend API server logs and tunnel status.")
    st.stop()
elif error_message: # Show warning if DF has data but there was still an error message (e.g. empty sheet)
     error_placeholder.warning(error_message)
     # Continue if df has data

# Handle empty DataFrame case even if no explicit error message
if profile_df.empty:
    st.info("No profile data found in the backend/sheet to display.")
    # Optionally stop if you don't want to show the rest of the UI
    # st.stop()
else:
     st.success(f"Successfully loaded data for {len(profile_df)} profiles.")


# --- View Selection ---
st.markdown("---")
view_mode = st.radio(
    "Select View Mode:",
    ("📊 Summary & All Profiles", "👤 Single Profile Detail"),
    horizontal=True,
    key="view_mode_selection"
)
st.markdown("---")

# --- Display Logic (Should work with the profile_df loaded from API) ---

# ==============================================
# View 1: Summary & All Profiles
# ==============================================
if view_mode == "📊 Summary & All Profiles":
    st.header("📊 Summary & All Profiles")

    # Only show metrics/tables if DataFrame is not empty
    if not profile_df.empty:
        # --- Key Metrics ---
        st.subheader("📈 Overall Metrics")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Profiles", len(profile_df))
        # (Keep metric calculations as before, checking if columns exist)
        gmail_col='Gmail acc created'; active_col='is email active'; ip_col='IP Country'; proxy_col='Ads-power Proxy'
        if gmail_col in profile_df.columns: gmail_created_count = profile_df[profile_df[gmail_col].astype(str).str.strip().str.upper() == 'TRUE'].shape[0]; col2.metric("Gmail Acc Created", gmail_created_count)
        else: col2.metric("Gmail Acc Created", "N/A")
        if active_col in profile_df.columns: active_email_count = profile_df[profile_df[active_col].astype(str).str.strip().str.upper() == 'TRUE'].shape[0]; col3.metric("Active Emails", active_email_count)
        else: col3.metric("Active Emails", "N/A")
        if ip_col in profile_df.columns: valid_countries = profile_df[ip_col].dropna().astype(str).str.strip(); valid_countries = valid_countries[valid_countries != '']; unique_countries = valid_countries.nunique(); col4.metric("Unique IP Countries", unique_countries)
        else: col4.metric("Unique IP Countries", "N/A")

        # --- Proxy Usage Analysis ---
        st.subheader("🔗 Proxy Usage")
        if proxy_col in profile_df.columns:
            # (Keep proxy analysis logic as before)
            valid_proxies = profile_df[proxy_col].dropna().astype(str).str.strip(); valid_proxies = valid_proxies[valid_proxies != '']; proxy_counts = valid_proxies.value_counts(); duplicate_proxies = proxy_counts[proxy_counts > 1]
            if not duplicate_proxies.empty:
                st.warning(f"Found **{len(duplicate_proxies)}** duplicate proxies:");
                with st.expander("Show Duplicates"): st.dataframe(duplicate_proxies.reset_index().rename(columns={'index': 'Proxy', 'count': 'Count'}), use_container_width=True)
                show_duplicates_only = st.checkbox("Show only profiles using duplicate proxies", key="show_duplicates_cb"); display_df = profile_df[profile_df[proxy_col].isin(duplicate_proxies.index)] if show_duplicates_only else profile_df
            else: st.success("✅ No duplicate proxies found."); display_df = profile_df
        else: st.info(f"`{proxy_col}` column not found."); display_df = profile_df

        # --- Data Table (All Profiles) ---
        st.subheader("📋 All Profile Data")
        st.info("Scroll horizontally to see all columns.")
        cols_to_drop = ['Trust score_numeric'] # Remove helper column
        display_df_cleaned = display_df.drop(columns=[col for col in cols_to_drop if col in display_df.columns], errors='ignore')
        st.dataframe(display_df_cleaned, use_container_width=True)

        # --- Download Button ---
        st.markdown("---")
        @st.cache_data # Keep caching conversion
        def convert_df_to_csv(df_to_convert):
            df_copy = df_to_convert.copy()
            for col in ['date of modification', 'Created Time', 'Last Open Time']:
                 if col in df_copy.columns and pd.api.types.is_datetime64_any_dtype(df_copy[col]): df_copy[col] = df_copy[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('')
                 elif col in df_copy.columns: df_copy[col] = df_copy[col].astype(str).fillna('')
            return df_copy.to_csv(index=False).encode('utf-8')

        csv_data = convert_df_to_csv(display_df_cleaned)
        st.download_button(label="📥 Download Displayed Data as CSV", data=csv_data, file_name='signup_bot_profiles_view.csv', mime='text/csv', key="download_all_csv")
    else:
        # If profile_df was empty after fetch, show message here too
        st.info("No profile data available to display summary or table.")


# ==============================================
# View 2: Single Profile Detail
# ==============================================
elif view_mode == "👤 Single Profile Detail":
    st.header("👤 Single Profile Detail")

    # Only allow selection if DataFrame is not empty
    if not profile_df.empty:
        # --- Profile Selection ---
        id_col = 'ID'; profile_name_col = 'Profile' # Assuming these columns exist post-API load
        if id_col in profile_df.columns:
            # (Keep selection logic as before)
            sort_cols = [col for col in [profile_name_col, id_col] if col in profile_df.columns]
            try: sorted_df = profile_df.sort_values(by=sort_cols)
            except TypeError: logging.warning(f"Sort failed by {sort_cols}"); sorted_df = profile_df
            if profile_name_col in sorted_df.columns: profile_options = {row[id_col]: f"{safe_get(row, profile_name_col, 'No Name')} ({row[id_col]})" for index, row in sorted_df.iterrows()}
            else: profile_options = {row[id_col]: f"{row[id_col]}" for index, row in sorted_df.iterrows()}
            profile_options = {k: v for k, v in profile_options.items() if k is not None}

            if not profile_options: st.error("No valid profile IDs found."); st.stop()
            selected_id = st.selectbox("Select Profile:", options=list(profile_options.keys()), format_func=lambda x: profile_options.get(x, x), index=0, key="profile_select")
        else: st.error(f"Cannot select profile: '{id_col}' column missing."); st.stop()

        # --- Display Selected Profile Data ---
        if selected_id:
            # (Keep display logic as before, using safe_get and format_boolean)
            profile_data = profile_df[profile_df[id_col] == selected_id].iloc[0]
            display_name = safe_get(profile_data, profile_name_col, selected_id)
            st.subheader(f"Details for: {display_name}")
            st.markdown(f"**AdsPower ID:** `{selected_id}`")
            cols_status = st.columns(4)
            with cols_status[0]: st.markdown("**Gmail Created:**"); st.markdown(format_boolean(safe_get(profile_data, 'Gmail acc created', 'N/A')), unsafe_allow_html=True)
            with cols_status[1]: st.markdown("**Email Active:**"); st.markdown(format_boolean(safe_get(profile_data, 'is email active', 'N/A')), unsafe_allow_html=True)
            with cols_status[2]: st.markdown("**Consistency:**"); consistency_val = safe_get(profile_data, 'consistency', 'N/A'); st.write(consistency_val.capitalize() if isinstance(consistency_val, str) else consistency_val)
            with cols_status[3]: st.markdown("**Trust Score:**"); st.write(safe_get(profile_data, 'Trust score', 'N/A'))
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📧 Account Info"); st.markdown(f"**Email:** `{safe_get(profile_data, 'Email')}`"); st.markdown(f"**Password:** `{safe_get(profile_data, 'password')}`"); st.markdown(f"**Recovery Email:** `{safe_get(profile_data, 'recovery')}`"); st.markdown(f"**Recovery Number:** `{safe_get(profile_data, 'recovery number')}`")
                mod_date_col = 'date of modification'; mod_date_val = safe_get(profile_data, mod_date_col, None); display_mod_date = "N/A";
                if isinstance(mod_date_val, (datetime, pd.Timestamp)): 
                    try: display_mod_date = mod_date_val.strftime('%Y-%m-%d') 
                    except: display_mod_date = str(mod_date_val)
                elif mod_date_val is not None: display_mod_date = str(mod_date_val); st.markdown(f"**Gmail Mod Date:** {display_mod_date}")
            with col2:
                st.subheader("🔗 Proxy & IP"); st.markdown(f"**Ads-power Proxy:**"); st.code(safe_get(profile_data, 'Ads-power Proxy', 'N/A'), language=None); st.markdown(f"**Detected IP:** `{safe_get(profile_data, 'IP')}`"); ip_country = safe_get(profile_data, 'IP Country', 'N/A'); st.markdown(f"**IP Country:** `{ip_country.upper() if isinstance(ip_country, str) and ip_country not in ['N/A', ''] else ip_country}`")
            st.markdown("---")
            with st.expander("⚙️ AdsPower Details"):
                 adsp_col1, adsp_col2 = st.columns(2)
                 with adsp_col1: st.markdown(f"**Serial #:** `{safe_get(profile_data, 'Serial Number')}`"); adsp_profile_name = safe_get(profile_data, 'Profile Name', ''); 
                 if not adsp_profile_name: adsp_profile_name = safe_get(profile_data, 'Profile', 'N/A'); st.markdown(f"**Profile Name:** `{adsp_profile_name}`"); st.markdown(f"**Group ID:** `{safe_get(profile_data, 'Group ID')}`"); st.markdown(f"**Group Name:** `{safe_get(profile_data, 'Group Name')}`")
                 with adsp_col2:
                     created_time_col = 'Created Time'; created_time_val = safe_get(profile_data, created_time_col, None); display_created_time = "N/A";
                     if isinstance(created_time_val, (datetime, pd.Timestamp)): 
                         try: display_created_time = created_time_val.strftime('%Y-%m-%d %H:%M:%S') 
                         except: display_created_time = str(created_time_val)
                     elif created_time_val is not None: display_created_time = str(created_time_val); st.markdown(f"**Created Time:** {display_created_time}")
                     last_open_time_col = 'Last Open Time'; last_open_time_val = safe_get(profile_data, last_open_time_col, None); display_last_open_time = "N/A";
                     if isinstance(last_open_time_val, (datetime, pd.Timestamp)): 
                         try: display_last_open_time = last_open_time_val.strftime('%Y-%m-%d %H:%M:%S') 
                         except: display_last_open_time = str(last_open_time_val)
                     elif last_open_time_val is not None: display_last_open_time = str(last_open_time_val); st.markdown(f"**Last Open Time:** {display_last_open_time}")
                     st.markdown(f"**Internal #:** `{safe_get(profile_data, 'Number')}`")
        else:
             st.info("Select a profile ID above.")
    else:
         st.info("No profile data loaded from the backend to display details.")


# --- Footer Example ---
st.markdown("---")
st.caption("Signup Bot Remote Dashboard v0.5") 