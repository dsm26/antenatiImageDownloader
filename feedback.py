import streamlit as st
import uuid
from datetime import datetime
from api_helpers import track_ga_event, log_to_gsheets

def show_feedback_form(app_name, headers):
    st.divider()
    with st.expander("💬 Help improve this tool: Send Feedback or Suggestions"):
        with st.form("feedback_form", clear_on_submit=True):
            f_email = st.text_input("Email (Optional):", placeholder="your@email.com")
            f_message = st.text_area("Message / Suggestion (Required):", placeholder="What's on your mind?")
            
            submitted = st.form_submit_button("Submit Feedback")
            
            if submitted:
                if not f_message.strip():
                    st.error("Please enter a message before submitting.")
                else:
                    try:
                        # Generate metadata for the feedback
                        session_id = st.session_state.get("session_id", str(uuid.uuid4()))
                        if "session_id" not in st.session_state:
                            st.session_state.session_id = session_id
                        
                        feedback_row = [
                            f_email.strip() if f_email else "Anonymous",
                            f_message.strip(),
                            headers.get("User-Agent", "Unknown"), # Browser context
                            app_name
                        ]
                        
                        log_to_gsheets("feedback", feedback_row)
                        track_ga_event("feedback_submitted")
                        
                        st.success("Thank you! Your feedback has been sent to the developer.")
                    except Exception as e:
                        st.error(f"Error sending feedback. Please try again later. ({e})")
