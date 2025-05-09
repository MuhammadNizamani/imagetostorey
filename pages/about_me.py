# pages/about_me.py
import streamlit as st
from PIL import Image # Import Image to open the local image file
import os # Import os to help with path
from pathlib import Path # Import Path for better path handling
st.set_page_config(page_title="About Me", layout="centered") # Optional: set page config for this page

st.title("About Muhammad Ishaque Nizamani")

# --- Load and display the image ---
# Assuming the image is in the same 'pages' directory
# Adjust the path if your image is elsewhere
current_dir = Path(__file__).parent
image_path = os.path.join(current_dir, "ishaque.jpg")

# image_path = "ishaque.jpg" # <-- Make sure this matches your image filename
try:
    st.image(image_path, caption="Muhammad Ishaque Nizamani", width=400)
except FileNotFoundError:
    st.error(f"Image not found at {image_path}. Please check the image location.")
except Exception as e:
    st.error(f"Error loading image: {e}")


st.header("My Details")

st.markdown("**Name:** Muhammad Ishaque Nizamani")
st.markdown("**Roll No:** 25MEIT007")

st.markdown(
    "**GitHub Profile:** "
    "[https://github.com/MuhammadNizamani](https://github.com/MuhammadNizamani)"
)

st.markdown(
    "**Twitter:** "
    "[@NizamaniIshaque](https://twitter.com/NizamaniIshaque)"
)

st.markdown("---")
st.write("This is a simple 'About Me' page added to the multi-page Streamlit app.")

# Optional: Add a link back to the main page if desired, though sidebar is the primary navigation
# st.markdown("[Go back to Image Storyteller](/)", unsafe_allow_html=True) # This works for Streamlit Cloud, sometimes locally