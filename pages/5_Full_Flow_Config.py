# signup-bot-frontend/pages/5_Full_Flow_Config.py 
import streamlit as st
import requests
import json
import time
import logging
from collections import OrderedDict # Keep just in case

# --- Configuration ---
SIGNUP_API_URL = st.secrets.get("SIGNUP_API_URL", None)
SIGNUP_API_KEY = st.secrets.get("SIGNUP_API_KEY", None)
HEADERS = {'X-API-Key': SIGNUP_API_KEY} if SIGNUP_API_KEY else {}
MAX_THREADS = 4
MAX_PROFILES_CREATE = 10

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- API Helper Functions ---
# (Copy/Paste or import from shared utility - adapt endpoint URLs)
@st.cache_data(ttl=30) # Cache less aggressively than summary data
def fetch_full_flow_settings_from_api():
    """Fetches full_flow_settings.yaml from the backend API."""
    if not SIGNUP_API_URL: return None, "SIGNUP_API_URL missing."
    api_endpoint = f"{SIGNUP_API_URL}/settings/full_flow" # Specific endpoint
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=15)
        response.raise_for_status()
        # Try parsing JSON first
        settings_data = response.json()
        logging.info("Full flow settings fetched successfully.")
        return settings_data, None
    # Specific exceptions first
    except json.JSONDecodeError:
        logging.error("API FF Settings Fetch Error: Invalid JSON response")
        return None, "Invalid JSON response from API."
    except requests.exceptions.RequestException as e:
        # General request exception last
        error_detail = f"{type(e).__name__}"
        if e.response is not None:
            try: error_detail += f" ({e.response.status_code}): {e.response.json().get('error', e.response.text)}"
            except json.JSONDecodeError: error_detail += f" ({e.response.status_code}): {e.response.text}"
            except Exception: pass # Keep basic error type
        logging.error(f"API FF Settings Fetch Error: {e}")
        return None, f"API Error: {error_detail}"
    except Exception as e: # Catch any other unexpected error
         logging.error(f"Unexpected error fetch FF settings: {e}", exc_info=True)
         return None, f"Unexpected error: {e}"


def save_full_flow_settings_via_api(settings_data):
    """Saves full_flow_settings.yaml via the backend API."""
    if not SIGNUP_API_URL: return False, "SIGNUP_API_URL missing."
    api_endpoint = f"{SIGNUP_API_URL}/settings/full_flow" # Specific endpoint
    try:
        response = requests.post(api_endpoint, headers=HEADERS, json=settings_data, timeout=20)
        response.raise_for_status()
        # Try parsing JSON from success response
        message = response.json().get("message", "Saved successfully.")
        return True, message
    # Specific exceptions first
    except json.JSONDecodeError:
         logging.error("API FF Settings Save Error: Invalid JSON response after save.")
         return False, "Invalid JSON response received after saving (but save might have worked)."
    except requests.exceptions.RequestException as e:
        # General request exception last
        error_detail = f"{type(e).__name__}"
        if e.response is not None:
            try: error_detail += f" ({e.response.status_code}): {e.response.json().get('error', e.response.text)}"
            except json.JSONDecodeError: error_detail += f" ({e.response.status_code}): {e.response.text}"
            except Exception: pass
        logging.error(f"API FF Settings Save Error: {e}")
        return False, f"API Error: {error_detail}"
    except Exception as e: # Catch any other unexpected error
         logging.error(f"Unexpected error save FF settings: {e}", exc_info=True)
         return False, f"Unexpected error: {e}"

# --- Widget Rendering ---
# (Keep render_setting function exactly as before - it works on dicts)
def render_setting(key_path, value, level=0):
    """Renders appropriate widget based on value type for full_flow_settings."""
    key = key_path[-1]; label = key.replace('_', ' ').title(); unique_key = 'setting_' + '_'.join(map(str, key_path))
    # Use columns for layout, except for dicts
    if not isinstance(value, dict):
        col1, col2 = st.columns([0.4, 0.6])
        with col1: st.markdown(f"{label}:", unsafe_allow_html=False) # No indent needed with columns
    else:
        st.markdown(f"**{label}:**") # Header for dict section
        col2 = st.container() # Widgets go inside container
    with col2:
        if isinstance(value, bool): st.checkbox("", value=value, key=unique_key, label_visibility="collapsed")
        elif key == 'threads' and isinstance(value, int): st.number_input("", value=value, min_value=1, max_value=MAX_THREADS, step=1, key=unique_key, label_visibility="collapsed", help=f"Parallel threads (1-{MAX_THREADS})")
        elif key == 'num_profiles' and isinstance(value, int): st.number_input("", value=value, min_value=1, max_value=MAX_PROFILES_CREATE, step=1, key=unique_key, label_visibility="collapsed", help=f"Profiles to create (1-{MAX_PROFILES_CREATE})")
        elif isinstance(value, int): st.number_input("", value=value, step=1, key=unique_key, label_visibility="collapsed")
        elif isinstance(value, float): st.number_input("", value=value, step=0.01, key=unique_key, label_visibility="collapsed")
        elif key == 'profile_ids' and isinstance(value, list): st.text_area("(one ID per line, optional)", value="\n".join(map(str, value)), height=100, key=unique_key, label_visibility="visible", help="Overrides creation if not empty.")
        elif key == 'proxies' and isinstance(value, list): st.text_area("(one proxy per line)", value="\n".join(map(str, value)), height=150, key=unique_key, label_visibility="visible")
        elif key == 'recovery_emails' and isinstance(value, list): st.text_area("(one email per line)", value="\n".join(map(str, value)), height=100, key=unique_key, label_visibility="visible")
        elif isinstance(value, str): st.text_input("", value=value, key=unique_key, label_visibility="collapsed")
        elif isinstance(value, list): st.text_input("(List - Read Only)", value=str(value), disabled=True, key=unique_key, label_visibility="visible")
        elif isinstance(value, dict):
             st.markdown("---"); # Separator before nested dict items
             for sub_key, sub_value in value.items(): render_setting(key_path + [sub_key], sub_value, level + 1) # Recurse
        else: st.text_input("(Unknown Type)", value=str(value), disabled=True, key=unique_key, label_visibility="visible")

# --- Update Logic (Build dictionary from state) ---
def build_updated_settings(original_data_structure, key_path):
    """Recursively builds the updated settings dict from st.session_state."""
    # (Keep this function exactly as before - it reconstructs dict from widget state)
    if isinstance(original_data_structure, dict):
        updated_dict = {}
        for key, original_value in original_data_structure.items():
            current_key_path = key_path + [key]
            if isinstance(original_value, dict):
                updated_dict[key] = build_updated_settings(original_value, current_key_path)
            else:
                 widget_key = 'setting_' + '_'.join(map(str, current_key_path)) # Match widget key prefix
                 if widget_key in st.session_state:
                     widget_value = st.session_state[widget_key]
                     try: # Apply type conversions based on ORIGINAL type
                         if isinstance(original_value, bool): updated_dict[key] = bool(widget_value)
                         elif isinstance(original_value, int): updated_dict[key] = int(widget_value)
                         elif isinstance(original_value, float): updated_dict[key] = float(widget_value)
                         elif isinstance(original_value, list) and key in ['profile_ids', 'proxies', 'recovery_emails']: updated_dict[key] = [line.strip() for line in widget_value.splitlines() if line.strip()]
                         elif isinstance(original_value, str): updated_dict[key] = str(widget_value)
                         else: updated_dict[key] = widget_value # Fallback
                     except Exception as e: st.warning(f"Error processing widget '{widget_key}'. Keeping original."); logging.warning(f"Error processing {widget_key}: {e}"); updated_dict[key] = original_value
                 else: updated_dict[key] = original_value # Keep original if no widget
        return updated_dict
    else: return original_data_structure


# --- Streamlit Page ---
st.set_page_config(layout="wide", page_title="Full Flow Config (Remote)")
st.title("⚙️ Signup Bot - Full Flow Settings (Remote)")
st.caption("Edit settings for the full signup workflow (`config/full_flow_settings.yaml`) via API.")

# --- Check API Config ---
if not SIGNUP_API_URL: st.error("🚨 Critical Error: SIGNUP_API_URL secret is not set."); st.stop()
if not SIGNUP_API_KEY: st.warning("⚠️ Warning: SIGNUP_API_KEY secret not set.")

# --- Load Initial Settings ---
# Use unique state keys for this page's settings
if 'full_flow_current_settings' not in st.session_state: st.session_state.full_flow_current_settings = None
if 'full_flow_fetch_error' not in st.session_state: st.session_state.full_flow_fetch_error = None

if st.session_state.full_flow_current_settings is None:
    with st.spinner("Loading full flow settings from backend..."):
        settings_data, error = fetch_full_flow_settings_from_api()
        if error: st.session_state.full_flow_fetch_error = error
        else: st.session_state.full_flow_current_settings = settings_data; st.session_state.full_flow_fetch_error = None
        st.rerun()

if st.session_state.full_flow_fetch_error:
    st.error(f"Failed to load full flow settings: {st.session_state.full_flow_fetch_error}")
    if st.button("🔄 Retry Loading"): st.session_state.full_flow_current_settings = None; st.rerun()
    st.stop()

settings_data = st.session_state.full_flow_current_settings
if not settings_data: st.error("Full flow settings data unavailable."); st.stop()

# --- Render Form ---
with st.form("full_flow_settings_form"):
    # Define the structure based on your YAML file keys
    st.subheader("General Flow Control")
    render_setting(['full_flow_enabled'], settings_data.get('full_flow_enabled', False))
    render_setting(['threads'], settings_data.get('threads', 1))
    render_setting(['resume'], settings_data.get('resume', False))
    render_setting(['dev_mode'], settings_data.get('dev_mode', False))
    render_setting(['profile_ids'], settings_data.get('profile_ids', []))
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Step 1: Profile Creation")
        render_setting(['create_profiles'], settings_data.get('create_profiles', False))
        render_setting(['num_profiles'], settings_data.get('num_profiles', 1))
        render_setting(['group_id'], settings_data.get('group_id', ''))
        render_setting(['name_prefix'], settings_data.get('name_prefix', ''))
        render_setting(['proxies'], settings_data.get('proxies', []))
        st.markdown("---")
        st.subheader("Step 3: Gmail Creation")
        render_setting(['create_gmail'], settings_data.get('create_gmail', False))
        render_setting(['recovery_emails'], settings_data.get('recovery_emails', [])) # Ensure this key exists in YAML/settings_data
        st.markdown("---")
        st.subheader("Step 5: Newsletter")
        render_setting(['subscribe_newsletter'], settings_data.get('subscribe_newsletter', False))
        render_setting(['newsletter_url'], settings_data.get('newsletter_url', ''))
    with col2:
        st.subheader("Step 2: Consistency Check")
        render_setting(['check_consistency'], settings_data.get('check_consistency', False))
        render_setting(['pixelscan_check'], settings_data.get('pixelscan_check', False))
        render_setting(['trust_score_check'], settings_data.get('trust_score_check', False))
        st.markdown("---")
        st.subheader("Step 4: Gmail Status Check")
        render_setting(['check_gmail_status'], settings_data.get('check_gmail_status', False))
        st.markdown("---")
        st.subheader("Common Settings")
        render_setting(['sheet_name'], settings_data.get('sheet_name', 'Accounts Data'))

    st.divider()
    submitted = st.form_submit_button("💾 Save Full Flow Settings", use_container_width=True, type="primary")

    if submitted:
        logging.info("Save clicked. Building updated full flow settings...")
        # Build the updated dictionary from session state widgets
        updated_settings = build_updated_settings(settings_data, [])
        # st.json(updated_settings) # Debug: view payload if needed

        with st.spinner("Saving full flow settings via API..."):
             saved, save_msg = save_full_flow_settings_via_api(updated_settings)
        if saved:
            st.success(f"✅ Settings saved: {save_msg}")
            st.cache_data.clear() # Clear fetch cache
            st.session_state.full_flow_current_settings = None # Force reload
            time.sleep(1); st.rerun()
        else: st.error(f"❌ Failed to save settings: {save_msg}")

# Manual Reload Button
st.divider()
if st.button("🔄 Reload Full Flow Settings"):
     st.cache_data.clear()
     st.session_state.full_flow_current_settings = None
     st.rerun()