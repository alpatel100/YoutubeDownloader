import streamlit as st
import yt_dlp
from moviepy import VideoFileClip
import os
import tempfile
import re
from datetime import timedelta

# Set page config
st.set_page_config(page_title="ClipMaster Pro", page_icon="✂️", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e0e0e; color: #ffffff; }
    .video-stage { max-width: 700px; margin: auto; border-radius: 10px; overflow: hidden; }
    
    /* Input Box Styling */
    div[data-baseweb="input"] { background-color: #1a1a1a !important; border: 1px solid #333 !important; color: white !important; }
    
    /* Red Sliders */
    .stSlider > div [data-baseweb="slider"] > div > div { background-color: #ff4b4b !important; }
    
    /* FORCE BUTTONS: Same size, bigger, and red */
    div.stButton > button, div.stDownloadButton > button {
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
        border-radius: 5px !important;
        font-weight: bold !important;
        height: 70px !important;
        width: 100% !important;
        font-size: 20px !important;
        text-transform: uppercase;
    }
    </style>
    """, unsafe_allow_html=True)

# --- HELPERS ---
def format_time(s):
    return str(timedelta(seconds=int(s)))

def time_to_seconds(t, max_val):
    try:
        parts = list(map(int, t.split(':')))
        if len(parts) == 3: s = parts[0]*3600 + parts[1]*60 + parts[2]
        elif len(parts) == 2: s = parts[0]*60 + parts[1]
        else: s = parts[0]
        return min(max(0, s), max_val)
    except: return 0

# --- SYNC CALLBACKS ---
def update_slider():
    max_d = st.session_state.get('current_duration', 3600)
    st.session_state.start_s = time_to_seconds(st.session_state.start_text, max_d)
    st.session_state.end_s = time_to_seconds(st.session_state.end_text, max_d)
    st.session_state.start_text = format_time(st.session_state.start_s)
    st.session_state.end_text = format_time(st.session_state.end_s)

def update_text():
    st.session_state.start_text = format_time(st.session_state.start_s)
    st.session_state.end_text = format_time(st.session_state.end_s)

@st.cache_resource
def get_video_info(url):
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            return ydl.extract_info(url, download=False)
    except: return None

def process_video_task(url, start, end):
    temp_dir = tempfile.gettempdir()
    ydl_opts = {'format': 'bestvideo+bestaudio/best', 'outtmpl': f'{temp_dir}/%(id)s.%(ext)s', 'merge_output_format': 'mp4', 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        in_path = ydl.prepare_filename(info)
        out_path = os.path.join(temp_dir, f"export_{info['id']}.mp4")
        with VideoFileClip(in_path) as video:
            clip = video.subclipped(start, min(end, video.duration))
            clip.write_videofile(out_path, codec="libx264", audio_codec="aac", preset="ultrafast", logger=None)
        
        with open(out_path, "rb") as f:
            return f.read(), info.get('title', 'clip')

# --- UI ---
st.markdown("## ClipMaster <span style='color:#ff4b4b;'>Pro</span>", unsafe_allow_html=True)
url = st.text_input("🔗 SOURCE VIDEO URL", placeholder="Paste YouTube link...")

if url:
    info = get_video_info(url)
    if info:
        duration = int(info.get('duration', 0))
        st.session_state.current_duration = duration 
        
        # Reset out-of-bounds on new video
        if 'start_s' in st.session_state and st.session_state.start_s > duration:
            st.session_state.start_s = 0
            st.session_state.start_text = "0:00:00"
        if 'end_s' in st.session_state and st.session_state.end_s > duration:
            st.session_state.end_s = duration
            st.session_state.end_text = format_time(duration)

        if 'start_text' not in st.session_state: st.session_state.start_text = "0:00:00"
        if 'end_text' not in st.session_state: st.session_state.end_text = format_time(min(10, duration))
        if 'start_s' not in st.session_state: st.session_state.start_s = 0
        if 'end_s' not in st.session_state: st.session_state.end_s = min(10, duration)

        st.markdown('<div class="video-stage">', unsafe_allow_html=True)
        st.video(url)
        st.markdown('</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.text_input("START", key="start_text", on_change=update_slider)
            st.slider("S1", 0, duration, key="start_s", on_change=update_text, label_visibility="collapsed")
        with col2:
            st.text_input("END", key="end_text", on_change=update_slider)
            st.slider("E1", 0, duration, key="end_s", on_change=update_text, label_visibility="collapsed")

        is_valid = st.session_state.start_s < st.session_state.end_s
        clip_duration = st.session_state.end_s - st.session_state.start_s

        # Control Row
        c_left, c_right = st.columns([1, 1.2]) 
        with c_left:
            if is_valid:
                # Caption moved above the <h1>
                st.caption("TOTAL CLIP DURATION")
                st.markdown(f"<h1 style='color:#ff4b4b; margin:0;'>{clip_duration}s</h1>", unsafe_allow_html=True)
            else:
                st.error("⚠️ End time must be > Start time")
        
        with c_right:
            b1, b2 = st.columns(2)
            with b1:
                review_clicked = st.button("Review", disabled=not is_valid)
            with b2:
                download_clicked = st.button("Download", disabled=not is_valid)

        # --- ACTION LOGIC ---
        if is_valid:
            if review_clicked:
                with st.spinner("Rendering..."):
                    data, _ = process_video_task(url, st.session_state.start_s, st.session_state.end_s)
                    st.session_state.preview_data = data
                    st.rerun()

            if download_clicked:
                with st.spinner("Processing MP4..."):
                    file_bytes, file_title = process_video_task(url, st.session_state.start_s, st.session_state.end_s)
                    st.session_state.ready_file = file_bytes
                    st.session_state.ready_name = f"{file_title}.mp4"

        # Show the "Save" button if processing is done
        if 'ready_file' in st.session_state and is_valid:
            st.download_button(
                label="📁 Confirm Save to Disk",
                data=st.session_state.ready_file,
                file_name=st.session_state.ready_name,
                mime="video/mp4"
            )

        if 'preview_data' in st.session_state and is_valid:
            st.video(st.session_state.preview_data)
else:
    st.info("Awaiting source signal...")