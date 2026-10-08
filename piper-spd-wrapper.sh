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

# Проверка, что SD_RATE — число (целое или дробное, возможно отрицательное)
if ! [[ "$SD_RATE" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
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

# ВАЖНО: НЕ перезаписываем SD_RATE переменными окружения.
# Speech Dispatcher передаёт скорость как $1, а не через env.
# Если хотите дать возможность переопределить через env — используйте:
# SD_RATE="${SD_RATE:-${SPEECHD_RATE:-${RATE:-0}}}"
# но обычно это не нужно.

# Отправляем запрос на сервер, передавая sd_rate (может быть дробным)
curl -s -G "http://127.0.0.1:5555/" \
  --data-urlencode "text=$TEXT" \
  --data-urlencode "output=$OUTPUT" \
  --data-urlencode "sd_rate=$SD_RATE" > /dev/null 2>&1

if [ -f "$OUTPUT" ] && [ -s "$OUTPUT" ]; then
    aplay -q "$OUTPUT" 2>/dev/null
    rm -f "$OUTPUT"
fi

exit 0
