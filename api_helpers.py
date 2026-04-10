import streamlit as st
import requests
import uuid
from datetime import datetime

# --- GOOGLE ANALYTICS VIA SECRETS ---
GA_MEASUREMENT_ID = st.secrets.get("GA_MEASUREMENT_ID")
GA_API_SECRET = st.secrets.get("GA_API_SECRET")

def track_ga_event(event_name, extra_params=None):
    """Sends a server-side event to GA4 using Streamlit Secrets."""
    try:
        if not GA_API_SECRET or not GA_MEASUREMENT_ID:
            return

        # Get real user info for better reporting
        user_ip = st.context.headers.get("X-Forwarded-For", "0.0.0.0").split(",")[0]
        user_agent = st.context.headers.get("User-Agent", "Unknown")

        if "ga_client_id" not in st.session_state:
            st.session_state.ga_client_id = str(uuid.uuid4())

        url = f"https://www.google-analytics.com/mp/collect?measurement_id={GA_MEASUREMENT_ID}&api_secret={GA_API_SECRET}"

        payload = {
                "client_id": st.session_state.ga_client_id,
                "events": [{
                    "name": event_name,
                    "params": {
                        "ip_override": user_ip,
                        "user_agent": user_agent,
                        "engagement_time_msec": "1",
                        **(extra_params or {})
                        }
                    }]
                }
        requests.post(url, json=payload, timeout=2)
    except:
        pass

# --- GOOGLE SHEETS ---
def log_to_gsheets(sheet_name, row_data):
    """Targeted logging for usage, error, and ai tabs."""
    script_url = st.secrets.get("GSHEET_WEBAPP_URL")
    if not script_url:
        return

    client_id = st.session_state.get("ga_client_id", "unknown_session")

    payload = {
            "sheetName": sheet_name,
            "rowData": [datetime.now().strftime('%Y-%m-%d %H:%M:%S'), client_id] + row_data
            }

    try:
        requests.post(script_url, json=payload, timeout=5)
    except:
        pass

