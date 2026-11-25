#!/bin/bash

# Универсальный приём текста
if [ -t 0 ]; then
    # Вызвали напрямую → текст в $1, скорость опционально в $2
    TEXT="$1"
    SD_RATE="${2:-0}"
else
    # Вызвали через pipe (Speech Dispatcher / Foliate)
    SD_RATE="${1:-0}"
    TEXT=$(cat)
fi

if [ -z "$TEXT" ]; then
    exit 0
fi

# Проверка, что SD_RATE — число
if ! [[ "$SD_RATE" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
    SD_RATE=0
fi

# === ОЧИСТКА ТЕКСТА ===
TEXT=$(printf "%s" "$TEXT" | sed -E 's/<[^>]*>//g')
TEXT="${TEXT//‽/?!}"
TEXT="${TEXT//⁈/?!}"

if [ -z "${TEXT// }" ]; then
    exit 0
fi

OUTPUT="/tmp/speechd_$(date +%s%N).wav"

curl -s -G "http://127.0.0.1:5555/" \
  --data-urlencode "text=$TEXT" \
  --data-urlencode "output=$OUTPUT" \
  --data-urlencode "sd_rate=$SD_RATE" > /dev/null 2>&1

if [ -f "$OUTPUT" ] && [ -s "$OUTPUT" ]; then
    aplay -q "$OUTPUT" 2>/dev/null
    rm -f "$OUTPUT"
fi

exit 0
