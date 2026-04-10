import streamlit as st
import math
import requests
import re
import json
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import subprocess
from datetime import datetime
import uuid
import traceback
from urllib.parse import urlparse  # Added for robust URL parsing
from git_utils import get_git_info
from api_helpers import track_ga_event, log_to_gsheets
from instructions import show_instructions
from input_validator import validate_antenati_url
from feedback import show_feedback_form

# --- CONFIGURATION ---
APP_NAME = "Antenati Image Downloader"
APP_ICON = "🏛️"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://antenati.cultura.gov.it/"
}

# --- 1. PAGE LOAD TRACKING ---
if "page_loaded" not in st.session_state:
    track_ga_event("page_load")
    st.session_state.page_loaded = True

# 1. Look for ?image_id=XYZ in the URL
query_params = st.query_params
url_id = query_params.get("image_id", "")

st.set_page_config(page_title=APP_NAME, page_icon=APP_ICON)
st.title(f"{APP_ICON} {APP_NAME}")

show_instructions()

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

# --- URL VALIDATION LOGIC ---
image_id, ark_unit, original_input, processing_url = validate_antenati_url(user_input, url_id, get_canvas_id_url, APP_NAME)

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
            successMessage = f"✅ Ready! Need translation? Use the [Antenati Image AI Translator](https://antenati-image-translator.streamlit.app/)."
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

# --- FINAL UI ELEMENTS ---
show_feedback_form(APP_NAME, HEADERS)
