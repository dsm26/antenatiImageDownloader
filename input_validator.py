import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from api_helpers import track_ga_event, log_to_gsheets

def validate_antenati_url(user_input, url_id, get_canvas_id_url, app_name, headers):
    image_id = ""
    ark_unit = ""
    original_input = user_input.strip()
    processing_url = original_input

    if processing_url:
        # --- FAMILYSEARCH CHECK ---
        if "familysearch.org" in processing_url.lower():
            track_ga_event("familysearch_url_error", {"input_value": processing_url[:50]})
            st.warning("""
            **FamilySearch URL detected.**
            
            This tool only works with links from the official [Antenati portal](https://antenati.cultura.gov.it/). 
            Please find the record on the Antenati website and use the **'Copia link del bookmark'** button.
            """)
            return "", "", original_input, processing_url

        # --- detail-nominative INTERCEPTOR (Must happen before stripping query parameters) ---
        if "detail-nominative" in processing_url:
            with st.spinner("🔍 Person index detected (detail-nominative). Extracting record link from page..."):
                try:
                    response = requests.get(processing_url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        # Look for links containing the ARK prefix
                        ark_link = soup.find('a', href=lambda x: x and '/ark:/12657/an_ud' in x)
                        if ark_link:
                            # Reconstruct full URL (Antenati links are often relative)
                            found_name = ark_link.get_text(strip=True)
                            found_path = ark_link['href']
                            processing_url = f"https://antenati.cultura.gov.it{found_path}"
                            st.info(f"""
                            📍 **Record Found:** {found_name}  
                            🔗 **Resolved to:** `{processing_url}`
                            """)


                        else:
                            st.warning("⚠️ Scraper reached the page but couldn't find the 'Atto di nascita' link.")
                    else:
                        st.error(f"🚫 Antenati server returned an error: {response.status_code}")


                except Exception as e:
                    st.error(f"Could not parse the nominative page: {e}")

        # --- STRIP QUERY PARAMETERS (Repeated after transformations to keep inputs clean) ---
        if "?" in processing_url and "detail-nominative" not in processing_url:
            processing_url = processing_url.split("?")[0]

        # --- an_ud INTERCEPTOR ---
        if "/an_ud" in processing_url:
            with st.spinner(f"🔍 Document unit detected ({processing_url}). Finding specific record link..."):
                redirected = get_canvas_id_url(processing_url)
                if redirected:
                    processing_url = redirected
            
            # Re-strip in case the redirected URL contains new query parameters
            if "?" in processing_url:
                processing_url = processing_url.split("?")[0]

            # Notify user of URL switching
            if processing_url != original_input:
                st.info(f"**Note:** Using link: `{processing_url}`. Links with an_ud or detail-nominative in them are not directly downloadable.")

        # Ensure URL has a scheme for parsing
        parse_url = processing_url
        if not parse_url.startswith(('http://', 'https://')) and "." in parse_url:
            parse_url = "https://" + parse_url

        # Check if it's a valid official ARK URL
        if "ark:/12657/" in processing_url:
            parsed_path = urlparse(parse_url).path.rstrip('/')
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

        elif any(domain in processing_url for domain in ["beniculturali.it", "dam-antenati"]):
            # Handle IIIF and Manifest patterns
            path_parts = urlparse(parse_url).path.rstrip('/').split('/')
            if '2' in path_parts: # Typical for /iiif/2/ID/...
                image_id = path_parts[path_parts.index('2') + 1]
            elif 'containers' in path_parts: # Typical for /containers/ID/manifest
                image_id = path_parts[path_parts.index('containers') + 1]
            else:
                image_id = path_parts[-1]

            ark_unit = "IIIF_EXTRACT" # Placeholder to avoid empty unit errors

        # "Hidden" feature: Check if it's just a raw ID (no slashes, no dots)
        elif "/" not in processing_url and "." not in processing_url and len(processing_url) > 0:
            image_id = processing_url
        else:
        # --- 3. INVALID VALUE TRACKING ---
            track_ga_event("invalid_input_error", {"input_value": processing_url[:50]})
            
            log_to_gsheets("error_logs", [app_name, "N/A", original_input, "User Input Error", "Invalid URL format"])
            
            st.error(f"""
            **Invalid URL format.** Please use a valid Antenati ARK URL.

            **Current processed URL:** `{processing_url}`

            **How to find it:**
            On the Antenati portal, click the **'Copia link del bookmark'** button to get the correct link.

            **Format should look like:**
            `https://antenati.cultura.gov.it/ark:/12657/an_ua.../XYZ123`
            """)
            
    return image_id, ark_unit, original_input, processing_url
