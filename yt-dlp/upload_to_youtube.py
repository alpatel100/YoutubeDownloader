#!/usr/bin/env python3
"""
Upload a video file to YouTube as a Private video.
Uses YouTube Data API v3 with OAuth 2.0.

Usage:
  python upload_to_youtube.py --file "C:\path\to\video.mp4"
  python upload_to_youtube.py --file "C:\path\to\video.mp4" --title "My Title" --description "My desc"
  python upload_to_youtube.py --file "C:\path\to\video.mp4" --playlist "My Playlist Name"
"""

import argparse
import os
import sys
import pickle

# ── force UTF-8 output so filenames with non-ASCII chars don't crash on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Scopes required for uploading and playlist management
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]

SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS  = os.path.join(SCRIPT_DIR, "client_secrets.json")
TOKEN_FILE      = os.path.join(SCRIPT_DIR, "token.pickle")


def get_authenticated_service():
    """Authenticate and return a YouTube API service object."""
    creds = None

    # Load cached token if it exists
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    # Refresh or re-authenticate if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("  Refreshing access token...")
            creds.refresh(Request())
        else:
            print("  Opening browser for Google login (first time only)...")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next run
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
        print("  Token saved -- future runs will not require browser login.")

    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, file_path, title, description):
    """Upload a video as Private and return the video ID."""

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "22"   # People & Blogs
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(
        file_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024   # 10 MB chunks
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    print("  Uploading", os.path.basename(file_path), "...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  Progress: {pct}%", end="\r")

    video_id = response["id"]
    print(f"  Progress: 100%")
    print(f"")
    print(f"  Upload complete!")
    print(f"  Video ID  : {video_id}")
    print(f"  Watch URL : https://www.youtube.com/watch?v={video_id}")
    print(f"  Studio    : https://studio.youtube.com/video/{video_id}/edit")
    return video_id


def get_or_create_playlist(youtube, playlist_name):
    """
    Find an existing playlist by name (case-insensitive), or create a new one.
    Returns the playlist ID.
    """
    print(f"  Looking for playlist: '{playlist_name}' ...")

    # Search through all channel playlists (paginated)
    next_page_token = None
    while True:
        request = youtube.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50,
            pageToken=next_page_token
        )
        response = request.execute()

        for item in response.get("items", []):
            if item["snippet"]["title"].lower() == playlist_name.lower():
                playlist_id = item["id"]
                print(f"  Found existing playlist: '{item['snippet']['title']}' (ID: {playlist_id})")
                return playlist_id

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    # Playlist not found -- create it
    print(f"  Playlist not found. Creating new playlist: '{playlist_name}' ...")
    create_response = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": playlist_name,
                "description": ""
            },
            "status": {
                "privacyStatus": "private"
            }
        }
    ).execute()

    playlist_id = create_response["id"]
    print(f"  Created playlist: '{playlist_name}' (ID: {playlist_id})")
    return playlist_id


def add_video_to_playlist(youtube, video_id, playlist_id):
    """Add a video to a playlist."""
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
    ).execute()
    print(f"  Added to playlist successfully.")


def main():
    parser = argparse.ArgumentParser(description="Upload video to YouTube as Private")
    parser.add_argument("--file",        required=True, help="Path to the .mp4 file")
    parser.add_argument("--title",       default="",    help="YouTube video title (defaults to filename)")
    parser.add_argument("--description", default="",    help="YouTube video description")
    parser.add_argument("--playlist",    default="",    help="Playlist name to add the video to (creates if not found)")
    args = parser.parse_args()

    # Validate file
    if not os.path.exists(args.file):
        print(f"  ERROR: File not found: {args.file}")
        sys.exit(1)

    # Validate credentials
    if not os.path.exists(CLIENT_SECRETS):
        print(f"  ERROR: client_secrets.json not found in {SCRIPT_DIR}")
        print(f"  Download it from Google Cloud Console -> APIs & Services -> Credentials")
        sys.exit(1)

    # Default title = filename without extension
    title = args.title or os.path.splitext(os.path.basename(args.file))[0]

    print("")
    print("  ======================================")
    print("    YouTube Upload")
    print("  ======================================")
    print(f"  File     : {args.file}")
    print(f"  Title    : {title}")
    if args.playlist:
        print(f"  Playlist : {args.playlist}")
    print("")

    try:
        youtube = get_authenticated_service()
        video_id = upload_video(youtube, args.file, title, args.description)

        # Add to playlist if specified
        if args.playlist:
            print("")
            playlist_id = get_or_create_playlist(youtube, args.playlist)
            add_video_to_playlist(youtube, video_id, playlist_id)
            print(f"  Playlist  : https://www.youtube.com/playlist?list={playlist_id}")

    except HttpError as e:
        print(f"  ERROR: YouTube API error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
