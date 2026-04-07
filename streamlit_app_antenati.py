import streamlit as st
import math
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from urllib.parse import urlparse  # Added for robust URL parsing
import json
import uuid
import subprocess
from datetime import datetime
import traceback
import re

# --- CONFIGURATION ---
APP_NAME = "Antenati Image Downloader"

# --- GOOGLE ANALYTICS VIA SECRETS ---
# These pull from .streamlit/secrets.toml or Streamlit Cloud Secrets
GA_MEASUREMENT_ID = st.secrets.get("GA_MEASUREMENT_ID")
GA_API_SECRET = st.secrets.get("GA_API_SECRET")

def get_git_info():
    try:
        # Get short hash
        sha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        # Get commit date
        commit_date = subprocess.check_output(['git', 'log', '-1', '--format=%cd', '--date=format:%Y-%m-%d %H:%M']).decode('ascii').strip()
        return f"Build: {sha} | {commit_date}"
    except:
        # Fallback if git is not available
        from datetime import datetime
        return f"Last Refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

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

# --- Google Sheets LOGGING FUNCTION ---
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

# --- 1. PAGE LOAD TRACKING ---
if "page_loaded" not in st.session_state:
    track_ga_event("page_load")
    st.session_state.page_loaded = True

# 1. Look for ?image_id=XYZ in the URL
query_params = st.query_params
url_id = query_params.get("image_id", "")

st.set_page_config(page_title=APP_NAME, page_icon="🏛️")
st.title(f"🏛️ {APP_NAME}")

with st.expander("📖 Instructions & Related Tools"):
    st.write("""
    This tool is designed for use with the official [Antenati portal](https://antenati.cultura.gov.it/), 
    not the copies found on FamilySearch.

    **Need Translation?**
    Check out the [Antenati Image Translator](https://antenati-image-translator.streamlit.app/) to help read your discovered records.

    **How to use:**
    1. Find the record image you want to download on the Antenati website.
    2. Look for the link labeled **"Copia link del bookmark"** on that page and click it to copy the address.
    3. Paste that link into the box below.

    **Example URLs:**
    * https://antenati.cultura.gov.it/ark:/12657/an_ua264421/LzPr8VJ
    * https://antenati.cultura.gov.it/ark:/12657/an_ua264421/LzPr8x9


    **📥 Best Way to Save**
    For the best results, always use the **"Download" button** rather than right-clicking the image. The button automatically names your file using the **Image ID** and will embed the **original Antenati URL** in the file's internal metadata.
    """)

    st.divider() # Adds a thin line
    st.caption(get_git_info())

def get_canvas_id_url(url):
    """Parses the Antenati HTML to extract the hidden canvasId URL."""
    try:
        HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://antenati.cultura.gov.it/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        resp = requests.get(url, headers=HEADERS, timeout=5)

        if resp.status_code == 200:
            match = re.search(r"canvasId:\s*'([^']+)'", resp.text)
            if match:
                return match.group(1)
        elif resp.status_code == 403:
             st.write(f"DEBUG: 403 Forbidden received for {url}")

    except:
        pass
    return None

# 2. Input Field (Auto-filled if ID is in URL)
user_input = st.text_input("Enter Antenati Image URL:", value=url_id)

# Logic to extract ID from URL if necessary
image_id = ""
ark_unit = ""
original_input = user_input.strip()
processing_url = original_input

if processing_url:
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
        st.error("""
        **Invalid URL format.** Please use a valid Antenati ARK URL.

        **How to find it:**
        On the Antenati portal, click the **'Copia link del bookmark'** button to get the correct link.

        **Format should look like:**
        `https://antenati.cultura.gov.it/ark:/12657/an_ua.../XYZ123`
        """)

if image_id:
    # Check if we have this specific image already in the session cache
    if "cached_img_bytes" in st.session_state and st.session_state.cached_id == image_id:
        img_bytes = st.session_state.cached_img_bytes
        ark_unit = st.session_state.cached_ark_unit
    else:
        # --- TRACK IMAGE VIEW (only once per ID) ---
        if "last_stitched_id" not in st.session_state or st.session_state.last_stitched_id != image_id:
            # Add original URL to logs if a swap occurred
            log_params = {"image_id": image_id}
            usage_row = [APP_NAME, ark_unit, processing_url]
            
            if processing_url != original_input:
                log_params["original_input"] = original_input
                usage_row.append(f"{original_input}")

            track_ga_event("image_stitched", log_params)
            log_to_gsheets("usage_logs", usage_row)
            st.session_state.last_stitched_id = image_id

        st.info(f"Processing ID: {image_id}...")

        HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://antenati.cultura.gov.it/"}
        base_url = f"https://iiif-antenati.cultura.gov.it/iiif/2/{image_id}"

        try:
            # Fetch Metadata
            status_msg = st.empty()
            status_msg.text("Getting the original information for the page...")
            try:
                response = requests.get(f"{base_url}/info.json", headers=HEADERS)
                response.raise_for_status() # Ensure we got a 200 OK
                info = response.json()
            except Exception as e:
                err_row = [APP_NAME, ark_unit, processing_url, "Stitching Error (Info JSON)", str(e), traceback.format_exc()]
                if processing_url != original_input:
                    err_row.append(original_input)
                
                track_ga_event("antenati_error", {"error_type": "info_json", "image_id": image_id})
                log_to_gsheets("error_logs", err_row)
                raise e

            w, h = info["width"], info["height"]
            tw = info["tiles"][0]["width"]
            th = info["tiles"][0].get("height", tw)

            final_img = Image.new("RGB", (w, h))
            cols, rows = math.ceil(w / tw), math.ceil(h / th)
            total_tiles = cols * rows

            progress_bar = st.progress(0)

            # Download and Stitch
            tile_count = 0
            for r in range(rows):
                for c in range(cols):
                    tile_count += 1
                    x, y = c * tw, r * th
                    tile_w, tile_h = min(tw, w - x), min(th, h - y)
                    tile_url = f"{base_url}/{x},{y},{tile_w},{tile_h}/full/0/default.jpg"

                    status_msg.text(f"Downloading tile {tile_count} of {total_tiles}...")

                    try:
                        tile_res = requests.get(tile_url, headers=HEADERS)
                        tile_res.raise_for_status()
                        tile_data = Image.open(BytesIO(tile_res.content))

                        status_msg.text(f"Stitching tile {tile_count} of {total_tiles}...")
                        final_img.paste(tile_data, (x, y))
                    except Exception as e:
                        # Logic for tile error logging
                        tile_err_row = [APP_NAME, ark_unit, processing_url, "Stitching Error (Tile)", str(e), traceback.format_exc()]
                        if processing_url != original_input:
                            tile_err_row.append(original_input)
                            
                        track_ga_event("antenati_error", {"error_type": "tile_download", "image_id": image_id})
                        log_to_gsheets("error_logs", tile_err_row)
                        raise e

                    progress_bar.progress(tile_count / total_tiles)

            # --- ADD FOOTER AND METADATA ---
            status_msg.text("Finalizing image and metadata...")
            footer_height = 60
            final_with_footer = Image.new("RGB", (w, h + footer_height), (255, 255, 255))
            final_with_footer.paste(final_img, (0, 0))

            draw = ImageDraw.Draw(final_with_footer)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 35)
            except:
                font = ImageFont.load_default()

            footer_text = f"Source: {processing_url}"
            draw.text((20, h + 10), footer_text, fill=(0, 0, 0), font=font)

            # Embed EXIF metadata
            exif = final_with_footer.getexif()
            exif[270] = f"Source: {processing_url}"
            exif[37510] = f"Source: {processing_url}"

            # Prepare for download
            buf = BytesIO()
            final_with_footer.save(buf, format="JPEG", quality=95, subsampling=0, exif=exif)
            img_bytes = buf.getvalue()

            # Cache the result in session state
            st.session_state.cached_img_bytes = img_bytes
            st.session_state.cached_id = image_id
            st.session_state.cached_ark_unit = ark_unit

            status_msg.empty()
            if processing_url != original_input:
                successMessage = f"✅ Ready! Used {processing_url} instead of {original_input}."
            else:
                successMessage = "✅ Ready!"
            st.success(successMessage)
            progress_bar.empty()

        except Exception as e:
            st.error(f"Could not retrieve image data. Please ensure the link is correct. (Technical Error: {e})")
            # don't log to gsheets here, logging happens earlier.
            st.stop()

    # Determine descriptive filename
    save_name = f"{ark_unit}_{image_id}.jpg" if ark_unit else f"{image_id}.jpg"

    # --- 2. DOWNLOAD BUTTON TRACKING ---
    download_clicked = st.download_button(
            label="📥 Download Image",
            data=img_bytes,
            file_name=save_name,
            mime="image/jpeg"
            )
    if download_clicked:
        track_ga_event("download_button_pushed", {"image_id": image_id})
        #log_to_gsheets("usage_logs", [f"{APP_NAME} (Download)", ark_unit, processing_url])

    # Also show a preview
    st.image(img_bytes, caption="Preview", use_container_width=True)
