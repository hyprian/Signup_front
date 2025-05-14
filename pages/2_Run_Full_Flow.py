import streamlit as st
import requests
import time
import json
import logging

# --- Configuration ---
SIGNUP_API_URL = st.secrets.get("SIGNUP_API_URL", None)
SIGNUP_API_KEY = st.secrets.get("SIGNUP_API_KEY", None)
HEADERS = {'X-API-Key': SIGNUP_API_KEY} if SIGNUP_API_KEY else {}
STATUS_REFRESH_INTERVAL_ACTIVE = 1 # MODIFIED: Refresh every 1 second when active
STATUS_REFRESH_INTERVAL_IDLE = 10 # MODIFIED: Refresh every 10 seconds when idle (adjust as preferred)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- API Helper Functions ---
# (Copy/Paste or import from a shared utility file)
def send_control_command(action, task_type=None):
    if not SIGNUP_API_URL: return None, "SIGNUP_API_URL not set."
    api_endpoint = f"{SIGNUP_API_URL}/control"; payload = {"action": action}
    if action == "start" and task_type: payload["task_type"] = task_type
    try:
        response = requests.post(api_endpoint, headers=HEADERS, json=payload, timeout=15); response.raise_for_status(); return response.json(), None
    except requests.exceptions.RequestException as e:
        error_detail = f"{type(e).__name__}";
        try: error_detail += f": {e.response.json().get('error', e.response.text)}"
        except: pass
        logging.error(f"API Control Error ({task_type or action}): {e}"); return None, f"API Error: {error_detail}"
    except json.JSONDecodeError: logging.error(f"API Control Error ({task_type or action}): Invalid JSON"); return None, "Invalid JSON response."

def fetch_status_from_api():
    if 'api_status' not in st.session_state: st.session_state.api_status = {"state": "unknown", "task": None, "details": "Connecting...", "last_update": None}
    # Removed last_fetch_time from here as it's not used by this function directly for its internal logic
    if not SIGNUP_API_URL: st.session_state.api_status = {"state": "error", "details": "API URL missing"}; return False
    api_endpoint = f"{SIGNUP_API_URL}/status"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=10); response.raise_for_status()
        new_status = response.json()
        if isinstance(new_status, dict) and 'state' in new_status:
            st.session_state.api_status = new_status
            # st.session_state.last_fetch_time = time.time() # We can set this here if needed elsewhere, but the main refresh is driven by st.rerun()
            return True
        else: st.session_state.api_status = {"state": "error", "details": f"Invalid status format: {new_status}"}; logging.error(f"Invalid API status: {new_status}"); return False
    except requests.exceptions.RequestException as e:
        error_msg = f"({time.strftime('%H:%M:%S')}) Status Fetch Fail: {type(e).__name__}"; logging.warning(f"Status Fetch Fail: {e}"); st.session_state.api_status["details"] = error_msg; st.session_state.api_status["state"] = "error"; return False # Don't update last_fetch_time on error
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

# --- Initialize Session State (if not done by fetch functions) ---
if 'api_status' not in st.session_state:
    st.session_state.api_status = {"state": "unknown", "task": None, "details": "Initializing...", "last_update": None}
if 'api_logs' not in st.session_state:
    st.session_state.api_logs = ["--- Initializing logs ---"]


# --- Streamlit Page Layout ---
st.set_page_config(layout="wide", page_title="Run Full Flow (Remote)")
st.title("🚀 Run Signup Bot Full Flow (Remote)")
st.caption("Start, stop, and monitor the full signup workflow via the API.")
st.warning("Ensure settings are configured and saved before running.", icon="⚠️")

# --- Check API Config ---
if not SIGNUP_API_URL: st.error("🚨 Critical Error: SIGNUP_API_URL secret is not set."); st.stop()
if not SIGNUP_API_KEY: st.warning("⚠️ Warning: SIGNUP_API_KEY secret not set.")

# --- Fetch Status and Logs (MODIFIED LOGIC) ---
fetch_status_from_api() # Always fetch status first
current_status = st.session_state.api_status
current_state = current_status.get("state", "unknown")
current_task = current_status.get("task")

# Determine if any task is active (for log fetching and refresh interval)
is_any_task_running = current_state in ["running", "starting", "stopping"]

# Determine if *this specific page's* task is running (for UI elements)
is_this_task_running = is_any_task_running and current_task == "full_flow"

# Fetch logs if any task is running/transitional
if is_any_task_running:
    fetch_logs_from_api()
else:
    # Task is not running, starting, or stopping.
    # If current state is definitively idle or stopped, and logs are not already the idle message, set them.
    if current_state in ["idle", "stopped"] and \
       st.session_state.get('api_logs', [""])[0] != "--- Bot is idle ---": # Check first element
        st.session_state.api_logs = ["--- Bot is idle ---"]
    # If state is "error" or "unknown" (and not transitional), previous logs are preserved.
    # This ensures that if a task errors out, its logs remain visible until the next explicit action or state change.

# --- Control Buttons ---
st.subheader("Flow Control")
col1, col2 = st.columns(2)
with col1:
    # Disable run button if *any* task is running
    run_disabled = is_any_task_running
    if st.button("▶️ Run Full Flow", disabled=run_disabled, use_container_width=True, type="primary" if not run_disabled else "secondary"):
        st.session_state.api_logs = [f"--- Sending 'start full_flow' command: {time.strftime('%H:%M:%S')} ---"]
        with st.spinner("Sending 'start full_flow' command..."): result, error = send_control_command("start", task_type="full_flow")
        if error: st.error(f"Failed start: {error}")
        else: st.success(result.get("message", "Start sent.")); time.sleep(0.2) # MODIFIED: Shorter sleep
        fetch_status_from_api(); fetch_logs_from_api(); st.rerun() # Force refresh

with col2:
    # Enable stop button if *any* task is running (API stop handles the current task)
    stop_disabled = not is_any_task_running
    if st.button("⏹️ Stop Current Task", disabled=stop_disabled, use_container_width=True):
        st.session_state.api_logs.append(f"--- Sending 'stop' command: {time.strftime('%H:%M:%S')} ---")
        with st.spinner("Sending 'stop' command..."): result, error = send_control_command("stop")
        if error: st.error(f"Failed stop: {error}")
        else: st.warning(result.get("message", "Stop sent.")); time.sleep(0.2) # MODIFIED: Shorter sleep
        fetch_status_from_api(); fetch_logs_from_api(); st.rerun() # Force refresh


# --- Display Bot Output ---
st.subheader("🤖 Bot Output Log")
status_placeholder = st.container()
log_placeholder = st.empty()

with status_placeholder:
    state_display = current_state.upper() # Use current_state directly
    details_display = current_status.get('details', 'N/A')
    task_display = current_task if current_task else 'None' # Use current_task directly
    last_update_ts = current_status.get('last_update')
    update_str = f"(Updated: {time.strftime('%H:%M:%S', time.localtime(last_update_ts))})" if last_update_ts else ""
    status_line = f"**Bot Status:** `{state_display}` {update_str}"

    # Highlight if it's this specific task running, or show other task if applicable
    if is_this_task_running: # This variable is already correctly defined above
        status_line += f" (Task: **{task_display}**)"
    elif task_display != 'None' and is_any_task_running : # Some other task is running
        status_line += f" (Task: {task_display})"
    elif task_display != 'None': # No task running, but there was a last known task
         status_line += f" (Last Task: {task_display})"


    if state_display == "RUNNING": st.info(status_line)
    elif state_display in ["IDLE", "STOPPED"]: st.success(status_line)
    elif state_display == "ERROR": st.error(status_line)
    elif state_display in ["STARTING", "STOPPING"]: st.warning(status_line)
    else: st.info(status_line) # For "UNKNOWN" etc.
    st.caption(f"Latest Detail: {details_display}")

# Display Logs
log_text = "\n".join(st.session_state.get('api_logs', ["--- No logs available ---"]))
log_placeholder.code(log_text, language='log')

# Refresh button
if st.button("🔄 Refresh Status & Logs"):
     with st.spinner("Refreshing..."):
          fetch_status_from_api() # Fetch new status first
          # Re-evaluate based on new status before deciding to fetch logs
          if st.session_state.api_status.get("state") in ["running", "starting", "stopping"]:
              fetch_logs_from_api()
          # If stopped/idle, the main logic at the top of the script will handle setting "Bot is idle" on the rerun
          st.rerun()

# --- Auto-refresh Logic ---
# Refresh based on whether *any* task is running
page_refresh_interval = STATUS_REFRESH_INTERVAL_ACTIVE if is_any_task_running else STATUS_REFRESH_INTERVAL_IDLE
st.caption(f"Auto-refreshing every {page_refresh_interval}s...")
time.sleep(page_refresh_interval)
st.rerun()