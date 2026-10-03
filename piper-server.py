#!/usr/bin/env python3
import sys
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

try:
    from piper import PiperVoice
    from piper.config import SynthesisConfig
except ImportError:
    print("Ошибка: pip install piper-tts", file=sys.stderr)
    sys.exit(1)

# путии к модели MODEL_PATH = "/home/username/.local/share/piper-voices/ru/ru_RU-irina-medium.onnx" и её конфигу #CONFIG_PATH = "/home/username/.local/share/piper-voices/ru/ru_RU-irina-medium.onnx.json"
# голос выберается раскоментированием нужной строки с сооствествущим VOICE
VOICES_DIR = Path.home() / ".local" / "share" / "piper-voices" / "ru"
VOICE = "ru_RU-igm3804-medium"
#VOICE = "ru_RU-irina-medium"
#VOICE = "ru_RU-sushkov_v4-medium"
#VOICE = "ru_RU-dict-medium_epoch3874"
#VOICE = "ru_RU-sova200-medium"
#VOICE = "ru_RU-pvo240-medium"
#VOICE = "ru_RU-april420-medium"
#VOICE = "ru_RU-fr6800-medium"
#VOICE = "ru_RU-igm3602-medium"
#VOICE = "ru_RU-igm3500-medium"
#VOICE = "ru_RU-kat580-medium"
#VOICE = "ru_RU-mari-medium_epoch5699"
#VOICE = "ru_RU-nara426-medium"
#VOICE = "ru_RU-terra5871-medium"
MODEL_PATH = str(VOICES_DIR / f"{VOICE}.onnx")
CONFIG_PATH = str(VOICES_DIR / f"{VOICE}.onnx.json")

# ===== НАСТРОЙКИ РЕЧИ =====
LENGTH_SCALE = 1.3      # < 1.0 — быстрее/выше тон, > 1.0 — медленнее/ниже тон (больше число — медленее)
NOISE_SCALE = 0.667     # "волнистость" голоса
NOISE_W_SCALE = 0.8     # вариативность ширины фонем (было ошибочно noise_w)
VOLUME = 1.0            # громкость
SENTENCE_SILENCE = 0.2   # пауза между предложениями, секунды

print("Загрузка модели Piper...")
try:
    voice = PiperVoice.load(MODEL_PATH, config_path=CONFIG_PATH)
    sample_rate = getattr(voice.config, 'sample_rate', 22050)
    print(f"✅ Модель загружена! (Sample rate: {sample_rate} Hz)")
except Exception as e:
    print(f"❌ Ошибка: {e}", file=sys.stderr)
    sys.exit(1)

class TTSHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        text = params.get('text', [''])[0]
        output = params.get('output', [''])[0]

        if not text or not output:
            self.send_response(400)
            self.end_headers()
            return

        # Необязательный параметр ?length_scale=1.2 — переопределяет LENGTH_SCALE
        try:
            length_scale = float(params.get('length_scale', [LENGTH_SCALE])[0])
        except ValueError:
            length_scale = LENGTH_SCALE

        try:
            with wave.open(output, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)

                syn_config = SynthesisConfig(
                    length_scale=LENGTH_SCALE,
                    noise_scale=NOISE_SCALE,
                    noise_w_scale=NOISE_W_SCALE,
                    volume=VOLUME,
                )
                result = voice.synthesize(text, syn_config=syn_config)

                if hasattr(result, '__iter__') and not isinstance(result, (str, bytes, bytearray)):
                    silence = b"\x00\x00" * int(sample_rate * SENTENCE_SILENCE)  # 16-bit mono
                    first = True
                    for chunk in result:
                        if hasattr(chunk, 'audio_int16_bytes'):
                            if not first:
                                wav_file.writeframes(silence)
                            wav_file.writeframes(chunk.audio_int16_bytes)
                            first = False
                        elif hasattr(chunk, 'audio_int16_array'):
                            import numpy as np
                            if not first:
                                wav_file.writeframes(silence)
                            wav_file.writeframes(np.array(chunk.audio_int16_array, dtype=np.int16).tobytes())
                            first = False
                        else:
                            raise Exception(f"Неизвестная структура чанка")
                else:
                    raise Exception(f"Неожиданный тип результата: {type(result)}")

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            error_msg = str(e)
            print(f"Ошибка синтеза: {error_msg}", file=sys.stderr)
            self.wfile.write(error_msg.encode())

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 5555), TTSHandler)
    print("Сервер запущен на порту 5555...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
