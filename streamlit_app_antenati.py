import streamlit as st
import math
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# --- GOOGLE ANALYTICS VIA SECRETS ---
# These pull from .streamlit/secrets.toml or Streamlit Cloud Secrets
GA_MEASUREMENT_ID = st.secrets["GA_MEASUREMENT_ID"]
GA_API_SECRET = st.secrets["GA_API_SECRET"]

def send_analytics_event(event_name, image_id=None):
    """Sends a server-side event to GA4 using Streamlit Secrets."""
    url = f"https://www.google-analytics.com/mp/collect?measurement_id={GA_MEASUREMENT_ID}&api_secret={GA_API_SECRET}"
    
    # Get the Session ID for unique user tracking
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    ctx = get_script_run_ctx()
    session_id = ctx.session_id if ctx else "anonymous"

    payload = {
        "client_id": session_id,
        "events": [{
            "name": event_name,
            "params": {
                "image_id": image_id,
                "session_id": session_id,
                "engagement_time_msec": "1"
            }
        }]
    }
    
    try:
        requests.post(url, json=payload, timeout=2)
    except:
        pass

# 1. Look for ?image_id=XYZ in the URL
query_params = st.query_params
url_id = query_params.get("image_id", "")

st.set_page_config(page_title="Antenati Tool", page_icon="🏛️")
st.title("🏛️ Antenati Image Downloader")

with st.expander("📖 Instructions & Related Tools"):
    st.write("""
    This tool is designed for use with the official [Antenati portal](https://antenati.cultura.gov.it/), 
    not the copies found on FamilySearch.

    **How to use:**
    1. Find the record image you want to download on the Antenati website.
    2. Look for the link labeled **"Copia link del bookmark"** on that page and click it to copy the address.
    3. Paste that link into the box below.

    **Example URLs:**
    * https://antenati.cultura.gov.it/ark:/12657/an_ua264421/LzPr8VJ
    * https://antenati.cultura.gov.it/ark:/12657/an_ua264421/LzPr8x9

    **Need Translation?**
    Check out the [Antenati Image Translator](https://antenati-image-translator.streamlit.app/) to help read your discovered records.
    """)

# 2. Input Field (Auto-filled if ID is in URL)
user_input = st.text_input("Enter Antenati Image URL:", value=url_id)

# Logic to extract ID from URL if necessary
image_id = user_input.strip().split('/')[-1] if user_input else ""

if image_id:
    st.info(f"Processing ID: {image_id}...")
    
    HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://antenati.cultura.gov.it/"}
    base_url = f"https://iiif-antenati.cultura.gov.it/iiif/2/{image_id}"
    
    try:
        # Fetch Metadata
        info = requests.get(f"{base_url}/info.json", headers=HEADERS).json()
        w, h = info["width"], info["height"]
        tw = info["tiles"][0]["width"]
        th = info["tiles"][0].get("height", tw)
        
        final_img = Image.new("RGB", (w, h))
        cols, rows = math.ceil(w / tw), math.ceil(h / th)
        
        progress_bar = st.progress(0)
        
        # Download and Stitch
        for r in range(rows):
            for c in range(cols):
                x, y = c * tw, r * th
                tile_w, tile_h = min(tw, w - x), min(th, h - y)
                tile_url = f"{base_url}/{x},{y},{tile_w},{tile_h}/full/0/default.jpg"
                
                res = requests.get(tile_url, headers=HEADERS)
                tile_data = Image.open(BytesIO(res.content))
                final_img.paste(tile_data, (x, y))
            progress_bar.progress((r + 1) / rows)

        # --- ADD FOOTER AND METADATA ---
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
        send_analytics_event("image_stitched", image_id=image_id)

        st.success("✅ Ready!")
        st.download_button(
            label="📥 Download Stitched Image",
            data=buf.getvalue(),
            file_name=f"{image_id}.jpg",
            mime="image/jpeg"
        )
        
        # Also show a preview
        st.image(buf.getvalue(), caption="Preview", use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
