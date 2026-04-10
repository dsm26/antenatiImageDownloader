import streamlit as st
from git_utils import get_git_info

def show_instructions():
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

