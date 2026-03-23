import streamlit as st
import math
import requests
from io import BytesIO
from PIL import Image

# 1. Look for ?image_id=XYZ in the URL
query_params = st.query_params
url_id = query_params.get("image_id", "")

st.set_page_config(page_title="Antenati Tool", page_icon="🏛️")
st.title("🏛️ Antenati IIIF Downloader")

# 2. Input Field (Auto-filled if ID is in URL)
image_id = st.text_input("Enter IIIF Image ID", value=url_id)

if image_id:
    st.info(f"Processing: {image_id}...")
    
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

        # Prepare for download
        buf = BytesIO()
        final_img.save(buf, format="JPEG", quality=95)
        
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
