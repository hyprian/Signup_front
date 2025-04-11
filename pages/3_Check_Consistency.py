# signup-bot-frontend/pages/3_Check_Consistency.py
import streamlit as st
import requests
import json
import time
import logging
from collections import OrderedDict # Keep for potential use in build_updated_settings

# --- Configuration ---
SIGNUP_API_URL = st.secrets.get("SIGNUP_API_URL", None)
SIGNUP_API_KEY = st.secrets.get("SIGNUP_API_KEY", None)
HEADERS = {'X-API-Key': SIGNUP_API_KEY} if SIGNUP_API_KEY else {}
STATUS_REFRESH_INTERVAL_ACTIVE = 3 # Check status/logs more often when running
STATUS_REFRESH_INTERVAL_IDLE = 30
MAX_THREADS_CONSISTENCY = 10 # Keep this for UI limit if needed

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- API Helper Functions ---
# (Adapted from previous frontend page, using SIGNUP_ constants)
def send_control_command(action, task_type=None):
    """Sends start/stop command to the backend API."""
    if not SIGNUP_API_URL: return None, "SIGNUP_API_URL not set."
    api_endpoint = f"{SIGNUP_API_URL}/control"
    payload = {"action": action}
    if action == "start" and task_type: payload["task_type"] = task_type
    try:
        response = requests.post(api_endpoint, headers=HEADERS, json=payload, timeout=15)
        response.raise_for_status(); return response.json(), None
    except requests.exceptions.RequestException as e:
        error_detail = f"{type(e).__name__}"; 
        try: error_detail += f": {e.response.json().get('error', e.response.text)}" 
        except: pass
        logging.error(f"API Control Error ({task_type or action}): {e}"); return None, f"API Error: {error_detail}"
    except json.JSONDecodeError: logging.error(f"API Control Error ({task_type or action}): Invalid JSON"); return None, "Invalid JSON response."

def fetch_status_from_api():
    """Fetches the current bot status from the backend API."""
    # Reusing state key 'api_status' for simplicity, assuming only one task runs
    if 'api_status' not in st.session_state:
         st.session_state.api_status = {"state": "unknown", "task": None, "details": "Connecting...", "last_update": None}
    if 'last_fetch_time' not in st.session_state: st.session_state.last_fetch_time = 0

    if not SIGNUP_API_URL: st.session_state.api_status = {"state": "error", "details": "API URL missing"}; return False
    api_endpoint = f"{SIGNUP_API_URL}/status"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=10); response.raise_for_status()
        new_status = response.json()
        if isinstance(new_status, dict) and 'state' in new_status:
             st.session_state.api_status = new_status; st.session_state.last_fetch_time = time.time(); return True
        else: st.session_state.api_status = {"state": "error", "details": f"Invalid status format: {new_status}"}; logging.error(f"Invalid API status: {new_status}"); return False
    except requests.exceptions.RequestException as e:
        error_msg = f"({time.strftime('%H:%M:%S')}) Status Fetch Fail: {type(e).__name__}"
        logging.warning(f"Status Fetch Fail: {e}"); st.session_state.api_status["details"] = error_msg
        st.session_state.api_status["state"] = "error"; st.session_state.last_fetch_time = time.time(); return False
    except json.JSONDecodeError: st.session_state.api_status = {"state": "error", "details": "Invalid JSON status."}; logging.error("Invalid JSON status."); return False

def fetch_logs_from_api():
    """Fetches recent logs from the backend API."""
    if 'api_logs' not in st.session_state: st.session_state.api_logs = ["--- Waiting for task ---"]
    if not SIGNUP_API_URL: logging.error("Cannot fetch logs: API URL missing."); return False
    api_endpoint = f"{SIGNUP_API_URL}/logs"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=10); response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and 'logs' in data and isinstance(data['logs'], list):
             st.session_state.api_logs = data['logs']; logging.debug(f"Fetched {len(data['logs'])} logs."); return True
        else: logging.error(f"Invalid logs format: {data}"); st.session_state.api_logs = ["--- Error: Invalid log format ---"]; return False
    except requests.exceptions.RequestException as e: logging.warning(f"Logs Fetch Fail: {e}"); return False # Keep old logs on error
    except json.JSONDecodeError: logging.error("Invalid JSON logs."); st.session_state.api_logs = ["--- Error: Invalid JSON logs ---"]; return False

@st.cache_data(ttl=60) # Cache settings briefly
def fetch_main_settings_from_api():
    """Fetches main settings (settings.yaml) from the backend API."""
    if not SIGNUP_API_URL: return None, "SIGNUP_API_URL missing."
    api_endpoint = f"{SIGNUP_API_URL}/settings/main"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=15)
        response.raise_for_status()
        # Try parsing JSON first
        settings_data = response.json()
        logging.info("Main settings fetched successfully.")
        return settings_data, None
    # Specific exceptions first
    except json.JSONDecodeError:
        logging.error("API Main Settings Fetch Error: Invalid JSON response")
        return None, "Invalid JSON response from API."
    except requests.exceptions.RequestException as e:
        # General request exception last
        error_detail = f"{type(e).__name__}"
        # Attempt to get more detail from response if available
        if e.response is not None:
            try:
                error_detail += f" ({e.response.status_code}): {e.response.json().get('error', e.response.text)}"
            except json.JSONDecodeError: # Handle case where error response itself isn't valid JSON
                error_detail += f" ({e.response.status_code}): {e.response.text}"
            except Exception: # Catch other potential errors reading response
                pass # Keep the basic error type if details can't be extracted
        logging.error(f"API Main Settings Fetch Error: {e}")
        return None, f"API Error: {error_detail}"
    except Exception as e: # Catch any other unexpected error
         logging.error(f"Unexpected error fetching main settings: {e}", exc_info=True)
         return None, f"Unexpected error: {e}"

def save_main_settings_via_api(settings_data):
    """Saves main settings (settings.yaml) via the backend API."""
    if not SIGNUP_API_URL: return False, "SIGNUP_API_URL missing."
    api_endpoint = f"{SIGNUP_API_URL}/settings/main"
    try:
        response = requests.post(api_endpoint, headers=HEADERS, json=settings_data, timeout=20)
        response.raise_for_status()
        # Try parsing JSON first from the success response
        message = response.json().get("message", "Saved successfully.")
        return True, message
    # Specific exceptions first
    except json.JSONDecodeError:
         # Error if the SUCCESS response wasn't valid JSON (less likely but possible)
         logging.error("API Main Settings Save Error: Invalid JSON response after save.")
         # Consider returning True but with a warning? Or False? Let's say False for clarity.
         return False, "Invalid JSON response received after saving (but save might have worked)."
    except requests.exceptions.RequestException as e:
        # General request exception last
        error_detail = f"{type(e).__name__}"
        if e.response is not None:
            try:
                error_detail += f" ({e.response.status_code}): {e.response.json().get('error', e.response.text)}"
            except json.JSONDecodeError:
                error_detail += f" ({e.response.status_code}): {e.response.text}"
            except Exception:
                pass
        logging.error(f"API Main Settings Save Error: {e}")
        return False, f"API Error: {error_detail}"
    except Exception as e: # Catch any other unexpected error
         logging.error(f"Unexpected error saving main settings: {e}", exc_info=True)
         return False, f"Unexpected error: {e}"


# --- Initialize Session State ---
# Define keys specific to this page's widgets/state
if 'consistency_current_settings' not in st.session_state: st.session_state.consistency_current_settings = None
if 'consistency_fetch_error' not in st.session_state: st.session_state.consistency_fetch_error = None
# Widget keys will be created by the form widgets themselves (e.g., 'consistency_profile_ids_text_area')

# --- Streamlit Page Layout ---
st.set_page_config(layout="wide", page_title="Check Consistency (Remote)")
st.title("📊 Check Profile Consistency (Remote)")
st.caption(f"Manage consistency settings via API: `{SIGNUP_API_URL}`")

# --- Check API Config ---
if not SIGNUP_API_URL: st.error("🚨 Critical Error: SIGNUP_API_URL secret is not set."); st.stop()
if not SIGNUP_API_KEY: st.warning("⚠️ Warning: SIGNUP_API_KEY secret not set.")

# --- Load Settings ---
# Fetch only if not already loaded or forced reload
if st.session_state.consistency_current_settings is None:
    with st.spinner("Loading consistency settings from backend..."):
        settings_data, error = fetch_main_settings_from_api()
        if error: st.session_state.consistency_fetch_error = error
        else: st.session_state.consistency_current_settings = settings_data; st.session_state.consistency_fetch_error = None
        st.rerun() # Rerun to display fetched data or error

# Display error if fetch failed
if st.session_state.consistency_fetch_error:
    st.error(f"Failed to load settings: {st.session_state.consistency_fetch_error}")
    if st.button("🔄 Retry Loading"): st.session_state.consistency_current_settings = None; st.rerun()
    st.stop()

settings_data = st.session_state.consistency_current_settings
if not settings_data: st.error("Settings data unavailable."); st.stop() # Should be caught above

# --- Display and Edit Settings Form ---
st.subheader("Settings for Consistency Check")
st.markdown("Edit consistency-related settings (saved to backend's `config/settings.yaml`).")

# Define default values from loaded settings for widgets
default_ids_list = settings_data.get('profiles_score_check', [])
default_ids_text = "\n".join(map(str, default_ids_list))
default_threads = settings_data.get('score_check_threads', 1)
default_pixelscan = settings_data.get('pixelscan_check', False)
default_trustscore = settings_data.get('trust_score_check', False)

with st.form("consistency_settings_form"):
    # Text area for Profile IDs
    profile_ids_text = st.text_area(
        "Profile IDs to Check (one per line):",
        value=default_ids_text, # Use loaded value as default for the form
        height=150,
        key="consistency_profile_ids_widget", # Unique key for THIS widget
        help="Enter AdsPower Profile IDs. Saved to 'profiles_score_check'."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        threads = st.number_input("Number of Threads", min_value=1, max_value=MAX_THREADS_CONSISTENCY, value=default_threads, step=1, key="consistency_threads_widget", help=f"Concurrent checks (1-{MAX_THREADS_CONSISTENCY}). Saved to 'score_check_threads'.")
    with col2:
        pixelscan_enabled = st.checkbox("Enable Pixelscan Check", value=default_pixelscan, key="consistency_pixelscan_widget", help="Check via pixelscan.net. Saved to 'pixelscan_check'.")
    with col3:
        trustscore_enabled = st.checkbox("Enable Trust Score Check", value=default_trustscore, key="consistency_trustscore_widget", help="Check via CreepJS. Saved to 'trust_score_check'.")

    submitted = st.form_submit_button("💾 Save Consistency Settings", use_container_width=True)

    if submitted:
        # --- Build Updated Settings Dictionary ---
        # Start with the currently loaded settings
        updated_settings_payload = settings_data.copy()
        # Get values directly from widgets using their keys
        ids_from_textarea = [line.strip() for line in st.session_state.consistency_profile_ids_widget.splitlines() if line.strip()]
        updated_settings_payload['profiles_score_check'] = ids_from_textarea
        updated_settings_payload['score_check_threads'] = st.session_state.consistency_threads_widget
        updated_settings_payload['pixelscan_check'] = st.session_state.consistency_pixelscan_widget
        updated_settings_payload['trust_score_check'] = st.session_state.consistency_trustscore_widget

        # --- Save via API ---
        with st.spinner("Saving settings via API..."):
            saved, save_msg = save_main_settings_via_api(updated_settings_payload)

        if saved:
            st.success(f"Settings saved: {save_msg}")
            st.cache_data.clear() # Clear settings cache
            st.session_state.consistency_current_settings = None # Force reload on next run
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"Failed to save settings: {save_msg}")

st.markdown("---")

# --- Control Buttons & Logic ---
# Fetch current status for button states
fetch_status_from_api()
current_status = st.session_state.api_status
current_state = current_status.get("state", "unknown")
current_task = current_status.get("task")
is_this_task_running = current_state in ["running", "starting", "stopping"] and current_task == "consistency"

col_run, col_stop = st.columns(2)
with col_run:
    # Disable if any task is running OR if required settings missing
    run_disabled = (current_state != "idle" and current_state != "error" and current_state != "stopped") \
                   or not settings_data.get('profiles_score_check') \
                   or not (settings_data.get('pixelscan_check') or settings_data.get('trust_score_check'))

    if st.button("▶️ Run Consistency Check", disabled=run_disabled, use_container_width=True, type="primary" if not run_disabled else "secondary"):
        # Check settings again before running
        ids_to_run = settings_data.get('profiles_score_check', [])
        checks_enabled = settings_data.get('pixelscan_check', False) or settings_data.get('trust_score_check', False)
        if not ids_to_run: st.warning("No Profile IDs saved in settings to check.")
        elif not checks_enabled: st.warning("Pixelscan and Trust Score checks are both disabled in settings.")
        else:
            st.session_state.api_logs = [f"--- Sending 'start consistency' command: {time.strftime('%H:%M:%S')} ---"] # Clear logs
            with st.spinner("Sending 'start consistency' command..."):
                 result, error = send_control_command("start", task_type="consistency")
            if error: st.error(f"Failed start: {error}")
            else: st.success(result.get("message", "Start sent.")); time.sleep(1)
            # Force immediate refresh
            fetch_status_from_api(); fetch_logs_from_api(); st.rerun()

with col_stop:
    stop_disabled = not is_this_task_running
    if st.button("⏹️ Stop Consistency Check", disabled=stop_disabled, use_container_width=True):
        st.session_state.api_logs.append(f"--- Sending 'stop' command: {time.strftime('%H:%M:%S')} ---")
        with st.spinner("Sending 'stop' command..."): result, error = send_control_command("stop")
        if error: st.error(f"Failed stop: {error}")
        else: st.warning(result.get("message", "Stop sent.")); time.sleep(1)
        # Force immediate refresh
        fetch_status_from_api(); fetch_logs_from_api(); st.rerun()

st.markdown("---")

# --- Display Script Output ---
st.subheader("📊 Consistency Check Output Log")
status_placeholder = st.container()
log_placeholder = st.empty()

with status_placeholder:
    # Display Status Line based on global status, highlighting if this task is running
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