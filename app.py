import streamlit as st
import google.generativeai as genai
from PIL import Image
from gtts import gTTS
import io
import os
import tempfile
from pathlib import Path
from elevenlabs.client import ElevenLabs  # Import the Client class
# Import the specific response object type for voices
from elevenlabs.types.get_voices_response import GetVoicesResponse
# Import the specific object type for voice settings
from elevenlabs.types.voice_settings import VoiceSettings


# --- Configuration ---
st.set_page_config(layout="wide", page_title="AI Image to Story & Human-like Speech")

# --- API Keys Configuration ---
try:
    # Configure the Gemini API key from Streamlit secrets
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=gemini_api_key)
    # Initialize the Gemini 1.5 Flash model (recommended for vision tasks now)
    vision_model = genai.GenerativeModel('gemini-1.5-flash-latest')
    text_model = genai.GenerativeModel('gemini-1.5-flash-latest') # Keep text model just in case, though vision handles both
    gemini_api_configured = True
except KeyError:
    st.error("🚨 Gemini API Key not found. Please add it to your Streamlit secrets (.streamlit/secrets.toml).")
    gemini_api_configured = False
except Exception as e:
    st.error(f"🚨 An error occurred during Gemini API configuration: {e}")
    gemini_api_configured = False

# Configure ElevenLabs API (for human-like voice)
elevenlabs_client = None # Initialize client to None
elevenlabs_configured = False
try:
    elevenlabs_api_key = st.secrets.get("ELEVENLABS_API_KEY", "")
    if elevenlabs_api_key:
        try:
            # Create an instance of the ElevenLabs client
            elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)
            # Test by fetching voices (using the instance)
            # This call might raise an exception if the key is invalid or network error
            # We don't need the result here, just testing the connection/auth
            test_voices_fetch = elevenlabs_client.voices.get_all()
            elevenlabs_configured = True
        except Exception as e:
             st.error(f"🚨 ElevenLabs client initialization or test voice fetch failed: {e}")
             elevenlabs_configured = False
    else:
        elevenlabs_configured = False
except Exception as e:
    st.error(f"🚨 An error occurred during ElevenLabs API key retrieval: {e}")
    elevenlabs_configured = False


# --- Helper Functions ---
def generate_story_from_image(image_data, prompt):
    """Generates a story from an image and a prompt using Gemini."""
    if not gemini_api_configured:
        return "Story generation unavailable due to API configuration issues."
    try:
        # Ensure image_data is bytes
        if hasattr(image_data, 'getvalue'):
            img_bytes = image_data.getvalue()
        elif isinstance(image_data, bytes):
            img_bytes = image_data
        else:
            # Fallback for PIL Image objects if not passed as BytesIO
            with io.BytesIO() as output:
                image_data.save(output, format="PNG")
                img_bytes = output.getvalue()

        image_parts = [
            {
                "mime_type": "image/png",
                "data": img_bytes
            }
        ]
        prompt_parts = [
            image_parts[0],
            f"\n\n{prompt}",
        ]
        response = vision_model.generate_content(prompt_parts)

        # Check if the response has candidates and parts
        if response.candidates and response.candidates[0].content.parts:
            return response.candidates[0].content.parts[0].text
        else:
            # Log the full response for debugging if it's not as expected
            st.warning(f"Unexpected response structure from Gemini: {response}")
            return "Could not generate a story from the image. The response was empty or malformed."

    except Exception as e:
        # Log the specific error
        st.error(f"Gemini API Error: {e}")
        return f"An error occurred during story generation: {e}"

# Modified to accept voice_settings and use the client instance
def convert_text_to_speech_elevenlabs(text, voice="Rachel", voice_settings=None):
    """Converts text to speech using ElevenLabs API for more human-like voice."""
    # Ensure client is initialized and text is provided
    if not text or not elevenlabs_client:
        return None
    try:
        # --- Prepare parameters for client.generate ---
        generate_params = {
            "text": text,
            "voice": voice, # Pass the voice name or voice_id
            "model": "eleven_multilingual_v2", # Using a common model name
            # Add other potential parameters here as needed by the API/client
            # For example, you might add a pronunciation_dictionary_locators list
        }

        if voice_settings:
             # Create a VoiceSettings object from the slider values
             # Note: ElevenLabs API parameter is typically 'similarity_boost', not 'clarity'
             settings_object = VoiceSettings(
                 stability=voice_settings.get("stability", 0.5),
                 similarity_boost=voice_settings.get("clarity", 0.75) # Map 'clarity' slider value to 'similarity_boost'
             )
             # Add the created VoiceSettings object under the 'voice_settings' key
             generate_params["voice_settings"] = settings_object

        # Call the generate method on the client instance using the prepared parameters
        # The client's generate method expects the VoiceSettings object via the 'voice_settings' parameter
        audio_stream = elevenlabs_client.generate(**generate_params)


        # audio_stream is typically an iterator/generator, so read it into bytes
        # Ensure audio_stream is iterable
        if not hasattr(audio_stream, '__iter__'):
             st.error("ElevenLabs generate did not return an iterable stream.")
             return None

        audio_bytes = b"".join(list(audio_stream))

        # Save to a temporary file and return the data
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        # Clean up
        Path(temp_path).unlink(missing_ok=True)

        return audio_bytes # Return the gathered bytes
    except Exception as e:
        st.error(f"An error occurred during ElevenLabs speech conversion: {e}")
        return None

def convert_text_to_speech_gtts(text):
    """Fallback to gTTS if ElevenLabs is not configured."""
    if not text:
        return None
    try:
        tts = gTTS(text=text, lang='en', slow=False)
        audio_fp = io.BytesIO() # Corrected typo BytesBytes to BytesIO
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)
        return audio_fp.getvalue()
    except Exception as e:
        st.error(f"An error occurred during gTTS conversion: {e}")
        return None

# --- Streamlit App Interface ---
st.title("🖼️✍️🎙️ AI Image-to-Story with Human-like Voice")
st.markdown("Upload an image, provide a story prompt, and let AI create a narrative and read it aloud with a natural human voice!")

col1, col2 = st.columns(2)

with col1:
    st.header("1. Upload Your Image")
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
    image_display_slot = st.empty() # Placeholder for the image

    uploaded_image_bytes = None # Initialize outside the if block

    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            image_display_slot.image(image, caption="Uploaded Image.", use_container_width=True)
            # Re-open the file to get bytes for the API call later
            uploaded_file.seek(0) # Reset file pointer to the beginning
            uploaded_image_bytes = io.BytesIO(uploaded_file.getvalue())
        except Exception as e:
            st.error(f"Error opening image: {e}")
            uploaded_file = None # Reset uploaded file on error
            uploaded_image_bytes = None # Ensure bytes are None if file failed


with col2:
    st.header("2. Story Prompt")
    story_prompt = st.text_area(
        "Enter a prompt for the story (e.g., 'Tell a mysterious tale about this place', 'What adventures await here?', 'Describe the emotions in this scene'):",
        "Tell a short, imaginative story based on this image."
    )

    # Voice selection
    st.header("3. Voice Options")

    selected_voice = None # Initialize selected_voice
    voice_settings = None # Initialize voice_settings

    # If ElevenLabs client is configured, show voice options
    if elevenlabs_client is not None: # Use the client instance existence check
        st.text("Using ElevenLabs for human-like voice.")
        try:
            # Get available voices using the client instance
            voices_result = elevenlabs_client.voices.get_all() # Fetch the data

            # --- Extract the list of voice objects from the result ---
            voices_list_objects = []
            # Check if it's the expected GetVoicesResponse object with a 'voices' list attribute
            if isinstance(voices_result, GetVoicesResponse) and hasattr(voices_result, 'voices') and isinstance(voices_result.voices, list):
                voices_list_objects = voices_result.voices # Extract the list from the 'voices' attribute
            elif isinstance(voices_result, tuple) and len(voices_result) > 1 and isinstance(voices_result[1], list):
                 # Keep the older ('voices', [...]) structure check for robustness
                 voices_list_objects = voices_result[1]
                 st.info("Handled older ElevenLabs voices response tuple structure.") # Add a note if this path is hit
            elif isinstance(voices_result, list):
                 # Keep the direct list check for robustness
                 voices_list_objects = voices_result
                 st.info("Handled ElevenLabs voices response as a direct list.") # Add a note if this path is hit
            else:
                 st.warning(f"Unexpected structure from elevenlabs_client.voices.get_all(): {type(voices_result)}. Cannot list voices.")
                 voices_list_objects = [] # Ensure it's an empty list if structure is unknown


            voice_names = []
            if voices_list_objects: # Check if the extracted list is not empty
                # --- Robustly extract voice names from the list ---
                for voice in voices_list_objects:
                    try:
                        # Check if the item in the list has a .name attribute (like Voice objects do)
                        if hasattr(voice, 'name'):
                            voice_names.append(voice.name)
                        # Add checks for other structures if necessary (e.g., dict)
                        # elif isinstance(voice, dict) and 'name' in voice:
                        #     voice_names.append(voice['name'])
                        else:
                             # Fallback if the object doesn't have a .name attribute
                             st.warning(f"Item in voice list has unexpected structure (no .name): {voice}. Skipping.")
                             # Decide whether to append str(voice) or just skip
                             pass # Skipping unexpected items
                    except Exception as e:
                        st.warning(f"Error processing item in voice list {voice}: {e}. Skipping.")
                        pass # Skipping problematic items


            # Ensure unique names and sort
            voice_names = list(set(voice_names))
            voice_names.sort()

            if voice_names:
                selected_voice = st.selectbox("Choose a voice:", voice_names, index=0)
            else:
                st.warning("No usable ElevenLabs voices found via API or extraction failed. Using default 'Rachel' (may fail if not available).")
                selected_voice = "Rachel"  # Default voice (ensure this voice exists or handle error)
        except Exception as e:
            # Catch any error during the get_all() call or subsequent processing
            st.error(f"Could not fetch or process ElevenLabs voices using client: {e}")
            selected_voice = "Rachel"  # Default voice (ensure this voice exists or handle error)

        st.markdown("Voice emotion settings (ElevenLabs):")
        # Note: ElevenLabs often uses 'similarity_boost' instead of 'clarity'
        # Double-check ElevenLabs API docs for exact parameter names for your client version
        stability = st.slider("Stability (lower for more emotional variation)", 0.0, 1.0, 0.5, 0.01, key="eleven_stability")
        clarity = st.slider("Clarity / Similarity Boost", 0.0, 1.0, 0.75, 0.01, key="eleven_clarity")
        # Store voice settings to be used later
        voice_settings = {"stability": stability, "clarity": clarity} # Store with keys matching how you'll use them

    else:
        st.text("Using Google TTS (Standard voice) as ElevenLabs client is not configured.")
        selected_voice = None # No specific voice selection for gTTS
        voice_settings = None # No settings for gTTS


    st.header("4. Generate Story & Speech")
    # Check if uploaded_file and uploaded_image_bytes exist before enabling
    # Note: uploaded_file might be None after a failed upload in the try/except block
    button_disabled = not gemini_api_configured or uploaded_file is None

    if st.button("✨ Create Story and Speech", disabled=button_disabled):
        if uploaded_file and story_prompt:
            # Ensure uploaded_image_bytes is created again as st.file_uploader re-runs on interaction
            # The file pointer needs to be reset if the file was successfully uploaded initially
            try:
                uploaded_file.seek(0)
                uploaded_image_bytes = io.BytesIO(uploaded_file.getvalue())
            except Exception as e:
                 st.error(f"Could not re-read uploaded file: {e}")
                 uploaded_image_bytes = None # Ensure it's None if re-reading fails

            if uploaded_image_bytes: # Proceed only if image bytes are available
                with st.spinner("Letting the AI craft a story... ✍️"):
                    # Pass the BytesIO object or bytes to the generator
                    generated_story = generate_story_from_image(uploaded_image_bytes, story_prompt)

                if generated_story and not generated_story.startswith("An error occurred") and not generated_story.startswith("Story generation unavailable") and not generated_story.startswith("Could not generate"):
                    st.subheader("📜 Generated Story:")
                    st.write(generated_story)

                    with st.spinner("Converting story to speech... 🎙️"):
                        # Use the client instance existence check
                        if elevenlabs_client and selected_voice: # Check if client exists and a voice was selected
                            # Pass voice settings if ElevenLabs is used
                            audio_bytes = convert_text_to_speech_elevenlabs(generated_story, voice=selected_voice, voice_settings=voice_settings)
                        else:
                            # Use gTTS if ElevenLabs is not configured or voice selection failed
                            audio_bytes = convert_text_to_speech_gtts(generated_story)

                if audio_bytes:
                    st.subheader("🗣️ Listen to the Story:")
                    st.audio(audio_bytes, format="audio/mp3")
                else:
                    st.warning("Could not generate audio for the story.")
            else: # Handle case where uploaded_image_bytes is None after trying to re-read
                st.warning("Could not process the uploaded image.")

        elif not uploaded_file:
            st.warning("Please upload an image first.")
        elif not story_prompt:
            st.warning("Please enter a story prompt.")
    elif not gemini_api_configured:
        st.warning("Cannot generate story. Please ensure the Gemini API key is correctly configured.")
    elif uploaded_file is None: # Check if uploaded_file is None for disabling message
         st.warning("Please upload an image to enable the button.")


st.markdown("---")
st.markdown("Powered by [Streamlit](https://streamlit.io), [Google Gemini](https://ai.google.dev/gemini-api), and [ElevenLabs](https://elevenlabs.io/) / [gTTS](https://pypi.org/project/gTTS/) for speech.")

# Add a section explaining how to set up ElevenLabs
with st.expander("How to enable human-like voices"):
    st.markdown("""
    To enable the human-like voice feature:

    1. Sign up for an account at [ElevenLabs](https://elevenlabs.io/)
    2. Get your API key from the ElevenLabs dashboard
    3. Add it to your Streamlit secrets file (.streamlit/secrets.toml) as:
    ```
    ELEVENLABS_API_KEY = "your-api-key-here"
    ```
    4. Restart your Streamlit app

    The free tier of ElevenLabs provides limited character conversions per month.
    """)