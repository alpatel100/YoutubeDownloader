import os
import yt_dlp
from moviepy import VideoFileClip

def clip_youtube_video(url, start_time, end_time, output_name="clip.mp4"):
    """
    Downloads and trims a YouTube video segment with high precision.
    Requires: pip install yt-dlp moviepy
    """
    # Sanitize output name
    output_name = output_name.replace(" ", "_")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'temp_source.%(ext)s',
        'quiet': False,
        'noplaylist': True
    }

    print(f"\n[1/3] Fetching video source: {url}")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ext = info.get('ext', 'mp4')
            temp_file = f"temp_source.{ext}"

        print(f"\n[2/3] Trimming segment: {start_time}s to {end_time}s")
        
        with VideoFileClip(temp_file) as video:
            # Subclip works in seconds
            new_clip = video.subclipped(start_time, min(end_time, video.duration))

            new_clip.write_videofile(
                output_name, 
                codec="libx264", 
                audio_codec="aac",
                temp_audiofile='temp-audio.m4a', 
                remove_temp=True
            )

        # Cleanup source
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
        print(f"\n[3/3] Success! Video saved as: {output_name}")
        
    except Exception as e:
        print(f"\n[ERROR] An error occurred: {str(e)}")
        if 'temp_file' in locals() and os.path.exists(temp_file):
            os.remove(temp_file)

if __name__ == "__main__":
    YT_URL = "https://www.youtube.com/watch?v=uMPEIUMEloE"
    START = 324
    END = 737
    OUT_FILE = "youtube_clip_324_to_737.mp4"
    clip_youtube_video(YT_URL, START, END, OUT_FILE)
