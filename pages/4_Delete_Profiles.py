# signup-bot-frontend/pages/4_Delete_Profiles.py
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
STATUS_REFRESH_INTERVAL_ACTIVE = 3
STATUS_REFRESH_INTERVAL_IDLE = 30

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- API Helper Functions ---
# (Copy/Paste or import from a shared utility file if you create one)
def send_control_command(action, task_type=None):
    if not SIGNUP_API_URL: return None, "SIGNUP_API_URL not set."
    api_endpoint = f"{SIGNUP_API_URL}/control"; payload = {"action": action}
    if action == "start" and task_type: payload["task_type"] = task_type
    try:
        response = requests.post(api_endpoint, headers=HEADERS, json=payload, timeout=15)
        response.raise_for_status(); return response.json(), None
    except requests.exceptions.RequestException as e:
        error_detail = f"{type(e).__name__}"; 
        try: error_detail += f": {e.response.json().get('error', e.response.text)}"
        except: pass; logging.error(f"API Control Error ({task_type or action}): {e}"); return None, f"API Error: {error_detail}"
    except json.JSONDecodeError: logging.error(f"API Control Error ({task_type or action}): Invalid JSON"); return None, "Invalid JSON response."

def fetch_status_from_api():
    if 'api_status' not in st.session_state: st.session_state.api_status = {"state": "unknown", "task": None, "details": "Connecting...", "last_update": None}
    if 'last_fetch_time' not in st.session_state: st.session_state.last_fetch_time = 0
    if not SIGNUP_API_URL: st.session_state.api_status = {"state": "error", "details": "API URL missing"}; return False
    api_endpoint = f"{SIGNUP_API_URL}/status"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=10); response.raise_for_status()
        new_status = response.json()
        if isinstance(new_status, dict) and 'state' in new_status: st.session_state.api_status = new_status; st.session_state.last_fetch_time = time.time(); return True
        else: st.session_state.api_status = {"state": "error", "details": f"Invalid status format: {new_status}"}; logging.error(f"Invalid API status: {new_status}"); return False
    except requests.exceptions.RequestException as e:
        error_msg = f"({time.strftime('%H:%M:%S')}) Status Fetch Fail: {type(e).__name__}"; logging.warning(f"Status Fetch Fail: {e}"); st.session_state.api_status["details"] = error_msg; st.session_state.api_status["state"] = "error"; st.session_state.last_fetch_time = time.time(); return False
    except json.JSONDecodeError: st.session_state.api_status = {"state": "error", "details": "Invalid JSON status."}; logging.error("Invalid JSON status."); return False

def fetch_logs_from_api():
    if 'api_logs' not in st.session_state: st.session_state.api_logs = ["--- Waiting for task ---"]
    if not SIGNUP_API_URL: logging.error("Cannot fetch logs: API URL missing."); return False
    api_endpoint = f"{SIGNUP_API_URL}/logs"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=10); response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and 'logs' in data and isinstance(data['logs'], list): st.session_state.api_logs = data['logs']; logging.debug(f"Fetched {len(data['logs'])} logs."); return True
        else: logging.error(f"Invalid logs format: {data}"); st.session_state.api_logs = ["--- Error: Invalid log format ---"]; return False
    except requests.exceptions.RequestException as e: logging.warning(f"Logs Fetch Fail: {e}"); return False
    except json.JSONDecodeError: logging.error("Invalid JSON logs."); st.session_state.api_logs = ["--- Error: Invalid JSON logs ---"]; return False

@st.cache_data(ttl=60)
def fetch_main_settings_from_api():
    if not SIGNUP_API_URL: return None, "SIGNUP_API_URL missing."
    api_endpoint = f"{SIGNUP_API_URL}/settings/main"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=15); response.raise_for_status()
        settings_data = response.json(); logging.info("Main settings fetched."); return settings_data, None
    except json.JSONDecodeError: logging.error("API Main Settings Fetch Error: Invalid JSON"); return None, "Invalid JSON response."
    except requests.exceptions.RequestException as e:
        error_detail = f"{type(e).__name__}";
        if e.response is not None: 
            try: error_detail += f" ({e.response.status_code}): {e.response.json().get('error', e.response.text)}"
            except: pass
        logging.error(f"API Main Settings Fetch Error: {e}"); return None, f"API Error: {error_detail}"
    except Exception as e: logging.error(f"Unexpected error fetch settings: {e}", exc_info=True); return None, f"Unexpected error: {e}"

def save_main_settings_via_api(settings_data):
    if not SIGNUP_API_URL: return False, "SIGNUP_API_URL missing."
    api_endpoint = f"{SIGNUP_API_URL}/settings/main"
    try:
        response = requests.post(api_endpoint, headers=HEADERS, json=settings_data, timeout=20); response.raise_for_status()
        message = response.json().get("message", "Saved.")
        return True, message
    except json.JSONDecodeError: logging.error("API Main Settings Save Error: Invalid JSON response"); return False, "Invalid JSON response after save."
    except requests.exceptions.RequestException as e:
        error_detail = f"{type(e).__name__}";
        if e.response is not None: 
            try: error_detail += f" ({e.response.status_code}): {e.response.json().get('error', e.response.text)}"
            except: pass
        logging.error(f"API Main Settings Save Error: {e}"); return False, f"API Error: {error_detail}"
    except Exception as e: logging.error(f"Unexpected error save settings: {e}", exc_info=True); return False, f"Unexpected error: {e}"

# --- Initialize Session State ---
# State specific to this page's operation
if 'delete_current_settings' not in st.session_state: st.session_state.delete_current_settings = None
if 'delete_fetch_error' not in st.session_state: st.session_state.delete_fetch_error = None
# We reuse 'api_status' and 'api_logs' assuming only one task runs globally

# --- Streamlit Page Layout ---
st.set_page_config(layout="wide", page_title="Delete Profiles (Remote)")
st.title("🗑️ Delete AdsPower Profiles (Remote)")
st.caption(f"Manage profile IDs via API: `{SIGNUP_API_URL}`")

# --- Check API Config ---
if not SIGNUP_API_URL: st.error("🚨 Critical Error: SIGNUP_API_URL secret is not set."); st.stop()
if not SIGNUP_API_KEY: st.warning("⚠️ Warning: SIGNUP_API_KEY secret not set.")

# --- Load Settings ---
if st.session_state.delete_current_settings is None:
    with st.spinner("Loading settings from backend..."):
        settings_data, error = fetch_main_settings_from_api()
        if error: st.session_state.delete_fetch_error = error
        else: st.session_state.delete_current_settings = settings_data; st.session_state.delete_fetch_error = None
        st.rerun()

if st.session_state.delete_fetch_error:
    st.error(f"Failed to load settings: {st.session_state.delete_fetch_error}")
    if st.button("🔄 Retry Loading"): st.session_state.delete_current_settings = None; st.rerun()
    st.stop()

settings_data = st.session_state.delete_current_settings
if not settings_data: st.error("Settings data unavailable."); st.stop()

# --- Display and Edit Profile IDs ---
st.subheader("Profile IDs to Delete")
st.markdown("Enter AdsPower Profile IDs (one per line) to delete. Saving updates `profiles_to_delete` in the backend's `config/settings.yaml`.")

default_ids_list = settings_data.get('profiles_to_delete', [])
default_ids_text = "\n".join(map(str, default_ids_list))

# Use a unique key for the text area on this page
profile_ids_text = st.text_area(
    "Profile IDs (one per line):",
    value=default_ids_text, # Initialize with loaded value
    height=150,
    key="delete_profile_ids_widget", # Unique widget key
    help="These IDs will be targeted by the deletion script."
)

# --- Control Buttons ---
col1, col2 = st.columns(2)

with col1:
    if st.button("💾 Save IDs to Settings", use_container_width=True):
        # Build updated settings payload
        updated_settings = settings_data.copy() # Start with current settings
        ids_from_textarea = [line.strip() for line in st.session_state.delete_profile_ids_widget.splitlines() if line.strip()]
        updated_settings['profiles_to_delete'] = ids_from_textarea

        # Save via API
        with st.spinner("Saving profile IDs via API..."):
            saved, save_msg = save_main_settings_via_api(updated_settings)
        if saved:
            st.success(f"Saved IDs: {save_msg}")
            st.cache_data.clear() # Clear settings cache
            st.session_state.delete_current_settings = None # Force reload
            time.sleep(1); st.rerun()
        else: st.error(f"Failed to save IDs: {save_msg}")

# Fetch current status for button states
fetch_status_from_api()
current_status = st.session_state.api_status
current_state = current_status.get("state", "unknown")
current_task = current_status.get("task")
is_this_task_running = current_state in ["running", "starting", "stopping"] and current_task == "delete"

with col2:
    # Disable if any task running OR if no IDs are configured in settings
    run_disabled = (current_state != "idle" and current_state != "error" and current_state != "stopped") \
                   or not settings_data.get('profiles_to_delete')

    if st.button("▶️ Run Deletion Script", disabled=run_disabled, use_container_width=True, type="primary" if not run_disabled else "secondary"):
        ids_to_run = settings_data.get('profiles_to_delete', [])
        if not ids_to_run: st.warning("No Profile IDs saved in settings to delete.")
        else:
            # Confirmation Dialog
            confirm = st.checkbox(f"⚠️ Confirm: Delete {len(ids_to_run)} profiles listed in settings?", value=False, key="delete_confirm_cb")
            if confirm:
                st.session_state.api_logs = [f"--- Sending 'start delete' command: {time.strftime('%H:%M:%S')} ---"]
                with st.spinner("Sending 'start delete' command..."):
                     result, error = send_control_command("start", task_type="delete")
                if error: st.error(f"Failed start: {error}")
                else: st.success(result.get("message", "Start sent.")); time.sleep(1)
                # Force refresh
                fetch_status_from_api(); fetch_logs_from_api(); st.rerun()
            else:
                st.info("Deletion cancelled. Check the confirmation box to proceed.")

# Stop Button (appears below if running)
if is_this_task_running:
    if st.button("⏹️ Stop Deletion Script", use_container_width=True):
        st.session_state.api_logs.append(f"--- Sending 'stop' command: {time.strftime('%H:%M:%S')} ---")
        with st.spinner("Sending 'stop' command..."): result, error = send_control_command("stop")
        if error: st.error(f"Failed stop: {error}")
        else: st.warning(result.get("message", "Stop sent.")); time.sleep(1)
        # Force refresh
        fetch_status_from_api(); fetch_logs_from_api(); st.rerun()


st.markdown("---")

# --- Display Script Output ---
st.subheader("🗑️ Deletion Script Output Log")
status_placeholder = st.container()
log_placeholder = st.empty()

with status_placeholder:
    # Display Status Line
    state_display = current_status.get('state', 'N/A').upper()
    details_display = current_status.get('details', 'N/A')
    task_display = current_status.get('task', 'None')
    last_update_ts = current_status.get('last_update')
    update_str = f"(Updated: {time.strftime('%H:%M:%S', time.localtime(last_update_ts))})" if last_update_ts else ""
    status_line = f"**Bot Status:** `{state_display}` {update_str}"
    if is_this_task_running: status_line += " (This Task)"
    elif task_display and task_display != "None": status_line += f" (Task: {task_display})"

    if state_display == "RUNNING": st.info(status_line)
    elif state_display in ["IDLE", "STOPPED"]: st.success(status_line)
    elif state_display == "ERROR": st.error(status_line)
    elif state_display in ["STARTING", "STOPPING"]: st.warning(status_line)
    else: st.info(status_line)
    st.caption(f"Latest Detail: {details_display}")

# Display Logs
log_text = "\n".join(st.session_state.get('api_logs', []))
log_placeholder.code(log_text, language='log')

# Refresh button
if st.button("🔄 Refresh Status & Logs"):
     with st.spinner("Refreshing..."):
          fetch_status_from_api()
          if st.session_state.api_status.get("state") in ["running", "starting", "stopping"]: fetch_logs_from_api()
          st.rerun()

# --- Auto-refresh Logic ---
refresh_interval = STATUS_REFRESH_INTERVAL_ACTIVE if is_this_task_running else STATUS_REFRESH_INTERVAL_IDLE
st.caption(f"Auto-refreshing every {refresh_interval}s...")
time.sleep(refresh_interval)
st.rerun()