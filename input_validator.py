import streamlit as st
from urllib.parse import urlparse
from api_helpers import track_ga_event

def validate_antenati_url(user_input, url_id, get_canvas_id_url):
    image_id = ""
    ark_unit = ""
    original_input = user_input.strip()
    processing_url = original_input

    if processing_url:
        # --- FAMILYSEARCH CHECK ---
        if "familysearch.org" in processing_url.lower():
            st.warning("""
            **FamilySearch URL detected.**
            
            This tool only works with links from the official [Antenati portal](https://antenati.cultura.gov.it/). 
            Please find the record on the Antenati website and use the **'Copia link del bookmark'** button.
            """)
            return "", "", original_input, processing_url

        # --- STRIP QUERY PARAMETERS ---
        if "?" in processing_url:
            processing_url = processing_url.split("?")[0]

        # --- an_ud INTERCEPTOR ---
        if "/an_ud" in processing_url:
            with st.spinner("🔍 Document unit detected. Finding specific record link..."):
                redirected = get_canvas_id_url(processing_url)
                if redirected:
                    processing_url = redirected
            
            # Notify user of URL switching
            if processing_url != original_input:
                st.info(f"**Note:** Using link: `{processing_url}`. Links with an_ud in them are not directly downloadable.")

        # Check if it's a valid official ARK URL
        if "ark:/12657/" in processing_url:
            parsed_path = urlparse(processing_url).path.rstrip('/')
            path_parts = parsed_path.split('/')
            image_id = path_parts[-1]

            # --- 5. TRACK ARK COMPONENTS ---
            # Extracting the 'an_ua...' part and the unique ID
            if len(path_parts) >= 2:
                ark_unit = path_parts[-2]
                track_ga_event("ark_components_tracked", {"ark_unit": ark_unit, "ark_id": image_id})

                # TRACK FULL RECONSTRUCTED PATH
                ark_path = f"{ark_unit}/{image_id}"
                track_ga_event("record_path_logged", {"ark_path": ark_path})

        # "Hidden" feature: Check if it's just a raw ID (no slashes, no dots)
        elif "/" not in processing_url and "." not in processing_url and len(processing_url) > 0:
            image_id = processing_url
        else:
        # --- 3. INVALID VALUE TRACKING ---
            track_ga_event("invalid_input_error", {"input_value": processing_url[:50]})
            log_to_gsheets("error_logs", [APP_NAME, "N/A", original_input, "User Input Error", "Invalid URL format"])
            st.error("""
            **Invalid URL format.** Please use a valid Antenati ARK URL.

            **How to find it:**
            On the Antenati portal, click the **'Copia link del bookmark'** button to get the correct link.

            **Format should look like:**
            `https://antenati.cultura.gov.it/ark:/12657/an_ua.../XYZ123`
            """)
            
    return image_id, ark_unit, original_input, processing_url

