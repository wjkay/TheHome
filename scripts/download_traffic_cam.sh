#!/bin/bash

# --------------------------
# CONFIGURATION
# --------------------------

CAM_IDS=("802" "801" "722" "278" "232" "230" "828")
BASE_DIR="/homeassistant/www/traffic_cams"
RAW_DIR="raw"
URL_ROOT="https://www.trafficnz.info/camera"
MAX_IMAGE_AGE_MINUTES=240
TARGET_DURATION=30
DELAY_PER_FRAME=200  # 200ms = 5 FPS
TARGET_FRAMES=$(( (TARGET_DURATION * 100) / DELAY_PER_FRAME ))

declare -A PERIOD_MINUTES=( ["15min"]=15 ["1hr"]=60 ["4hr"]=240 )

# --------------------------
# MODE HANDLING
# --------------------------

MODE=""
PERIOD=""

# Parse CLI args
while [[ $# -gt 0 ]]; do
  case $1 in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --period)
      PERIOD="$2"
      shift 2
      ;;
    *)
      echo "❌ Unknown argument: $1"
      exit 1
      ;;
  esac
done

# --------------------------
# DOWNLOAD MODE
# --------------------------

if [[ "$MODE" == "download" ]]; then
  echo "📥 [Download Mode] Starting image capture at $(date)"
  for CAM_ID in "${CAM_IDS[@]}"; do
    CAM_DIR="${BASE_DIR}/${CAM_ID}"
    IMG_DIR="${CAM_DIR}/${RAW_DIR}"
    mkdir -p "$IMG_DIR"

    TIMESTAMP=$(date +%s)
    IMAGE_PATH="${IMG_DIR}/img_${TIMESTAMP}.jpg"
    IMAGE_URL="${URL_ROOT}/${CAM_ID}.jpg"

    echo "📸 Downloading $CAM_ID..."
    curl -s "$IMAGE_URL" -o "$IMAGE_PATH"

    # Validate JPEG
    if ! head -c 3 "$IMAGE_PATH" | grep -qF $'\xff\xd8\xff'; then
      echo "❌ Invalid image for $CAM_ID. Skipping."
      rm -f "$IMAGE_PATH"
      continue
    fi

    # Clean up old images
    find "$IMG_DIR" -type f -name "img_*.jpg" -mmin +$MAX_IMAGE_AGE_MINUTES -delete
  done
  echo "✅ Download completed at $(date)"
  exit 0
fi

# --------------------------
# ANIMATION MODE
# --------------------------

if [[ "$MODE" == "animate" && -n "$PERIOD" ]]; then
  echo "🌀 [Animation Mode] Generating $PERIOD animations at $(date)"
  START_TIME=$(date +%s)
  TOTAL_ANIMATIONS=0

  for CAM_ID in "${CAM_IDS[@]}"; do
    CAM_DIR="${BASE_DIR}/${CAM_ID}"
    IMG_DIR="${CAM_DIR}/${RAW_DIR}"
    mkdir -p "$IMG_DIR"

    mapfile -t ALL_IMAGES < <(find "$IMG_DIR" -type f -name "img_*.jpg" | sort)
    MAX_AGE_MINUTES=${PERIOD_MINUTES[$PERIOD]}
    NOW_TS=$(date +%s)
    CUTOFF_TS=$((NOW_TS - MAX_AGE_MINUTES * 60))

    PERIOD_DIR="${CAM_DIR}/${PERIOD}"
    mkdir -p "$PERIOD_DIR"
    TS_LABEL=$(date "+%Y%m%d_%H%M")
    OUT_PATH="${PERIOD_DIR}/animation_${PERIOD}_${TS_LABEL}.webp"

    SELECTED_IMAGES=()
    for img in "${ALL_IMAGES[@]}"; do
      FILENAME=$(basename "$img")
      IMG_TS="${FILENAME//[!0-9]/}"
      if [[ "$IMG_TS" =~ ^[0-9]+$ ]] && (( IMG_TS >= CUTOFF_TS )); then
        SELECTED_IMAGES+=("$img")
      fi
    done

    TOTAL_AVAILABLE=${#SELECTED_IMAGES[@]}
    if (( TOTAL_AVAILABLE < 2 )); then
      echo "[$CAM_ID - $PERIOD] ⏭ Not enough frames. Found $TOTAL_AVAILABLE."
      continue
    fi

    INTERVAL=$(( TOTAL_AVAILABLE / TARGET_FRAMES ))
    (( INTERVAL < 1 )) && INTERVAL=1
    FRAME_COUNT=$(( TOTAL_AVAILABLE / INTERVAL ))
    (( FRAME_COUNT > TARGET_FRAMES )) && FRAME_COUNT=$TARGET_FRAMES

    FINAL_IMAGES=()
    for ((i = 0; i < TOTAL_AVAILABLE && ${#FINAL_IMAGES[@]} < FRAME_COUNT; i++)); do
      (( i % INTERVAL == 0 )) && FINAL_IMAGES+=("${SELECTED_IMAGES[$i]}")
    done

    if (( ${#FINAL_IMAGES[@]} > 1 )); then
      echo "🎞️  [$CAM_ID - $PERIOD] Generating animation (${#FINAL_IMAGES[@]} frames)..."
      nice -n 15 magick -limit thread 1 "${FINAL_IMAGES[@]}" \
        -set dispose background -loop 0 -delay "$DELAY_PER_FRAME" \
        -define webp:lossless=false "$OUT_PATH" 2>> "$CAM_DIR/animation_errors.log"
      ((TOTAL_ANIMATIONS++))
    fi
  done

  END_TIME=$(date +%s)
  DURATION=$((END_TIME - START_TIME))
  echo "✅ $PERIOD animation complete: $TOTAL_ANIMATIONS created in ${DURATION}s"
  exit 0
fi

# --------------------------
# INVALID MODE
# --------------------------

echo "❌ Invalid usage. Use:"
echo "   --mode download"
echo "   --mode animate --period 15min|1hr|4hr"
exit 1
