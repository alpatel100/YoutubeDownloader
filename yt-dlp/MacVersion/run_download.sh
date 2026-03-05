#!/usr/bin/env bash
# ============================================================
#  YouTube Clip Downloader (Mac)
#  Reads download_config.txt and processes all listed jobs
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/download_config.txt"
CONF_FILE="$SCRIPT_DIR/yt-dlp.conf"

# -- pre-flight checks ---------------------------------------
if ! command -v yt-dlp &>/dev/null; then
    echo "  ERROR: yt-dlp not found. Install with: brew install yt-dlp"
    exit 1
fi
if ! command -v ffmpeg &>/dev/null; then
    echo "  ERROR: ffmpeg not found. Install with: brew install ffmpeg"
    exit 1
fi
if [ ! -f "$CONFIG_FILE" ]; then
    echo "  ERROR: download_config.txt not found in $SCRIPT_DIR"
    exit 1
fi

# -- split config into job blocks separated by "---" ---------
jobs=()
current_block=""

while IFS= read -r line || [ -n "$line" ]; do
    trimmed="${line#"${line%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    if [ "$trimmed" = "---" ]; then
        if [ -n "$current_block" ]; then
            jobs+=("$current_block")
            current_block=""
        fi
    else
        if [ -n "$current_block" ]; then
            current_block="$current_block"$'\n'"$line"
        else
            current_block="$line"
        fi
    fi
done < "$CONFIG_FILE"
if [ -n "$current_block" ]; then
    jobs+=("$current_block")
fi

# -- parse a block for a key ---------------------------------
get_value() {
    local block="$1"
    local key="$2"
    echo "$block" | grep -E "^[[:space:]]*${key}[[:space:]]*=" | head -1 | sed "s/^[^=]*=//" | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//'
}

# -- filter out placeholder/empty jobs -----------------------
valid_jobs=()
for block in "${jobs[@]}"; do
    url=$(get_value "$block" "URL")
    if [ -n "$url" ] && [[ "$url" != *"REPLACE_WITH"* ]]; then
        valid_jobs+=("$block")
    fi
done

if [ ${#valid_jobs[@]} -eq 0 ]; then
    echo ""
    echo "  ERROR: No valid jobs found in download_config.txt"
    echo "  Make sure at least one URL= line is filled in."
    exit 1
fi

echo ""
echo "  ======================================"
echo "    YouTube Clip Downloader (Mac)"
echo "  ======================================"
echo "  Jobs found: ${#valid_jobs[@]}"
echo ""

success_count=0
fail_count=0
job_num=0

for block in "${valid_jobs[@]}"; do
    job_num=$((job_num + 1))

    URL=$(get_value "$block" "URL")
    START=$(get_value "$block" "START")
    END=$(get_value "$block" "END")
    OUTDIR=$(get_value "$block" "OUTPUT_DIR")
    FILENAME=$(get_value "$block" "FILENAME")
    QUALITY=$(get_value "$block" "QUALITY")
    UPLOAD=$(get_value "$block" "UPLOAD")
    YT_TITLE=$(get_value "$block" "YT_TITLE")
    YT_DESC=$(get_value "$block" "YT_DESCRIPTION")
    YT_PLAYLIST=$(get_value "$block" "YT_PLAYLIST")

    # Quality mapping
    case "${QUALITY,,}" in
        "720p")  FORMAT="bv[height=720]+ba[ext=m4a]";  QLABEL="720p" ;;
        "1440p") FORMAT="bv[height=1440]+ba[ext=m4a]"; QLABEL="1440p" ;;
        "2160p") FORMAT="bv[height=2160]+ba[ext=m4a]"; QLABEL="2160p (4K)" ;;
        "best")  FORMAT="bv+ba[ext=m4a]";              QLABEL="Best available" ;;
        *)       FORMAT="bv[height=1080]+ba[ext=m4a]"; QLABEL="1080p" ;;
    esac

    echo "  Job $job_num of ${#valid_jobs[@]}"
    echo "  URL     : $URL"
    echo "  Quality : $QLABEL"

    if [ -z "$OUTDIR" ]; then
        echo "  ERROR: OUTPUT_DIR is missing or blank"
        fail_count=$((fail_count + 1))
        echo ""
        continue
    fi

    # Clip range
    if [ -n "$START" ] && [ -n "$END" ]; then
        echo "  Clip    : $START -> $END"
        HAS_SECTION=1
    else
        echo "  Clip    : Full video"
        HAS_SECTION=0
    fi

    # Output path
    if [ -n "$FILENAME" ]; then
        BASENAME="${FILENAME%.*}"
        OUTPUT_ARG="$OUTDIR/$BASENAME.mp4"
    else
        OUTPUT_ARG="$OUTDIR/%(title)s.mp4"
    fi
    echo "  Output  : $OUTPUT_ARG"
    echo ""
    echo "  Starting download..."

    # Build yt-dlp args
    YTDLP_ARGS=(
        "--config-locations" "$CONF_FILE"
        "-f" "$FORMAT"
        "-o" "$OUTPUT_ARG"
    )
    if [ "$HAS_SECTION" -eq 1 ]; then
        YTDLP_ARGS+=("--download-sections" "*$START-$END")
    fi
    YTDLP_ARGS+=("$URL")

    yt-dlp "${YTDLP_ARGS[@]}"
    EXIT_CODE=$?

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "  OK - Saved to: $OUTPUT_ARG"
        success_count=$((success_count + 1))

        # Upload if requested
        if [ "${UPLOAD,,}" = "yes" ]; then
            echo ""
            echo "  Upload requested -- finding downloaded file..."

            if [ -n "$FILENAME" ]; then
                UPLOAD_FILE="$OUTPUT_ARG"
            else
                UPLOAD_FILE=$(ls -t "$OUTDIR"/*.mp4 2>/dev/null | head -1)
            fi

            if [ -n "$UPLOAD_FILE" ] && [ -f "$UPLOAD_FILE" ]; then
                echo "  Uploading: $UPLOAD_FILE"

                UPLOAD_SCRIPT="$(dirname "$SCRIPT_DIR")/upload_to_youtube.py"
                PY_ARGS=("$UPLOAD_SCRIPT" "--file" "$UPLOAD_FILE")
                [ -n "$YT_TITLE" ]    && PY_ARGS+=("--title"       "$YT_TITLE")
                [ -n "$YT_DESC" ]     && PY_ARGS+=("--description" "$YT_DESC")
                [ -n "$YT_PLAYLIST" ] && PY_ARGS+=("--playlist"    "$YT_PLAYLIST")

                python3 "${PY_ARGS[@]}"
                if [ $? -eq 0 ]; then
                    echo "  Upload OK"
                else
                    echo "  Upload FAILED -- check output above"
                fi
            else
                echo "  ERROR: Could not find downloaded file in $OUTDIR"
            fi
        fi
    else
        echo "  FAILED - yt-dlp exited with code $EXIT_CODE"
        fail_count=$((fail_count + 1))
    fi
    echo ""
done

echo "  ======================================"
echo "  Done: $success_count succeeded, $fail_count failed."
echo "  ======================================"
echo ""
