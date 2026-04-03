import streamlit as st
import math
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from urllib.parse import urlparse  # Added for robust URL parsing
import json
import uuid

# --- GOOGLE ANALYTICS VIA SECRETS ---
# These pull from .streamlit/secrets.toml or Streamlit Cloud Secrets
GA_MEASUREMENT_ID = st.secrets["GA_MEASUREMENT_ID"]
GA_API_SECRET = st.secrets["GA_API_SECRET"]

def track_ga_event(event_name, extra_params=None):
    """Sends a server-side event to GA4 using Streamlit Secrets."""
    try:
        # Get real user info for better reporting (Matches Program 2)
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

# --- 1. PAGE LOAD TRACKING ---
if "page_loaded" not in st.session_state:
    track_ga_event("page_load")
    st.session_state.page_loaded = True

# 1. Look for ?image_id=XYZ in the URL
query_params = st.query_params
url_id = query_params.get("image_id", "")

st.set_page_config(page_title="Antenati Image Downloader", page_icon="🏛️")
st.title("🏛️ Antenati Image Downloader")

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

    ### **📥 Best Way to Save**
    For the best results, always use the **"Download" button** rather than right-clicking the image:

    * **Automatic Naming:** The button automatically names your file using the **Image ID** so your records stay organized.
    * **Source Tracking:** The app "tags" the image file by embedding the **original Antenati URL** directly into the file's data (metadata).
    * **Why avoid right-clicking?** If you "Save Image As" from the preview, your computer will give it a **random name** and the link to the original record will not be embedded in the image.
    """)

# 2. Input Field (Auto-filled if ID is in URL)
user_input = st.text_input("Enter Antenati Image URL:", value=url_id)

# Logic to extract ID from URL if necessary
image_id = ""
if user_input:
    cleaned_input = user_input.strip()
    
    # Check if it's a valid official ARK URL
    if "ark:/12657/" in cleaned_input:
        parsed_path = urlparse(cleaned_input).path.rstrip('/')
        path_parts = parsed_path.split('/')
        image_id = path_parts[-1]
        
        # --- 5. TRACK ARK COMPONENTS ---
        # Extracting the 'an_ua...' part and the unique ID
        if len(path_parts) >= 2:
            ark_unit = path_parts[-2]
            track_ga_event("ark_components_tracked", {"ark_unit": ark_unit, "ark_id": image_id})

    # "Hidden" feature: Check if it's just a raw ID (no slashes, no dots)
    elif "/" not in cleaned_input and "." not in cleaned_input and len(cleaned_input) > 0:
        image_id = cleaned_input
    else:
        # --- 3. INVALID VALUE TRACKING ---
        track_ga_event("invalid_input_error", {"input_value": cleaned_input[:50]})
        st.error("""
        **Invalid URL format.** Please use a valid Antenati ARK URL.
        
        **How to find it:**
        On the Antenati portal, click the **'Copia link del bookmark'** button to get the correct link.
        
        **Format should look like:**
        `https://antenati.cultura.gov.it/ark:/12657/an_ua.../XYZ123`
        """)

if image_id:
    st.info(f"Processing ID: {image_id}...")
    
    HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://antenati.cultura.gov.it/"}
    base_url = f"https://iiif-antenati.cultura.gov.it/iiif/2/{image_id}"
    
    try:
        # Fetch Metadata
        status_msg = st.empty()
        status_msg.text("Getting the original information for the page...")
        response = requests.get(f"{base_url}/info.json", headers=HEADERS)
        response.raise_for_status() # Ensure we got a 200 OK
        info = response.json()
        
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
                res = requests.get(tile_url, headers=HEADERS)
                tile_data = Image.open(BytesIO(res.content))
                
                status_msg.text(f"Stitching tile {tile_count} of {total_tiles}...")
                final_img.paste(tile_data, (x, y))
                progress_bar.progress(tile_count / total_tiles)

        # --- ADD FOOTER AND METADATA ---
        status_msg.text("Finalizing image and metadata...")
        footer_height = 60
        final_with_footer = Image.new("RGB", (w, h + footer_height), (255, 255, 255))
        final_with_footer.paste(final_img, (0, 0))
        
        draw = ImageDraw.Draw(final_with_footer)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 35)
        except:
            font = ImageFont.load_default()

        footer_text = f"Source: {user_input}"
        draw.text((20, h + 10), footer_text, fill=(0, 0, 0), font=font)

        # Embed EXIF metadata
        exif = final_with_footer.getexif()
        exif[270] = f"Source: {user_input}"
        exif[37510] = f"Source: {user_input}"

        # Prepare for download
        buf = BytesIO()
        final_with_footer.save(buf, format="JPEG", quality=95, exif=exif)
        
        # --- TRACKING CALL ---
        track_ga_event("image_stitched", {"image_id": image_id})

        status_msg.empty()
        st.success("✅ Ready!")
        
        # --- 2. DOWNLOAD BUTTON TRACKING ---
        download_clicked = st.download_button(
            label="📥 Download Image",
            data=buf.getvalue(),
            file_name=f"{image_id}.jpg",
            mime="image/jpeg"
        )
        if download_clicked:
            track_ga_event("download_button_pushed", {"image_id": image_id})
        
        # Also show a preview
        st.image(buf.getvalue(), caption="Preview", use_container_width=True)

    except Exception as e:
        # --- 4. ANTENATI ERROR TRACKING ---
        track_ga_event("antenati_error", {"image_id": image_id, "error_type": "download_fail"})
        st.error(f"Could not retrieve image data. Please ensure the link is correct. (Technical Error: {e})")
