#!/bin/bash

# Универсальный приём текста
if [ -t 0 ]; then
    # Вызвали напрямую (repy) → текст в $1, скорость опционально в $2
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
if ! [[ "$SD_RATE" =~ ^-?[0-9]+(\.[0-9]+)?$ ]]; then
    SD_RATE=0
fi

# === ОЧИСТКА ТЕКСТА ===
TEXT="${TEXT//…/. ,}"
TEXT="${TEXT//.../. ,}"
#TEXT="${TEXT//##/}"
TEXT="${TEXT//#/}"
TEXT="${TEXT//\*/}"
TEXT="${TEXT//‽/?!}"
TEXT="${TEXT//⁈/?!}"
TEXT="${TEXT//«/\"}"
TEXT="${TEXT//»/\"}"
TEXT="${TEXT//“/\"}"
TEXT="${TEXT//”/\"}"
TEXT="${TEXT//‘/\'}"
TEXT="${TEXT//’/\'}"

# Безопасная обработка через printf
TEXT=$(printf "%s" "$TEXT" | sed -E 's/<[^>]*>//g')
TEXT=$(printf "%s" "$TEXT" | tr -d '\000-\010\013\014\016-\037')
TEXT=$(printf "%s" "$TEXT" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

if [ -z "$TEXT" ] || [ ${#TEXT} -lt 2 ]; then
    exit 0
fi

OUTPUT="/tmp/speechd_$(date +%s%N).wav"

# Получаем скорость от Speech Dispatcher (или 0, если её нет)
SD_RATE="${SPEECHD_RATE:-${RATE:-0}}"

# Проверка, что это число
if ! [[ "$SD_RATE" =~ ^-?[0-9]+$ ]]; then
    SD_RATE=0
fi

# Отправляем запрос на сервер, передавая sd_rate
curl -s -G "http://127.0.0.1:5555/" \
  --data-urlencode "text=$TEXT" \
  --data-urlencode "output=$OUTPUT" \
  --data-urlencode "sd_rate=$SD_RATE" > /dev/null 2>&1

if [ -f "$OUTPUT" ] && [ -s "$OUTPUT" ]; then
    aplay -q "$OUTPUT" 2>/dev/null
    rm -f "$OUTPUT"
fi

exit 0
