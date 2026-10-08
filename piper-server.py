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
    print("Ошибка: выполните 'pip install piper-tts'", file=sys.stderr)
    sys.exit(1)

# пути к модели MODEL_PATH = "/home/username/.local/share/piper-voices/ru/ru_RU-irina-medium.onnx" и её конфигу #CONFIG_PATH = "/home/username/.local/share/piper-voices/ru/ru_RU-irina-medium.onnx.json"
# голос выберается раскоментированием нужной строки с сооствествущим VOICE
VOICES_DIR = Path.home() / ".local" / "share" / "piper-voices" / "ru"
#VOICE = "ru_RU-igm3602-medium"
VOICE = "ru_RU-igm3804-medium"
#VOICE = "ru_RU-irina-medium"
#VOICE = "ru_RU-sushkov_v4-medium"
#VOICE = "ru_RU-dict-medium_epoch3874"
#VOICE = "ru_RU-sova200-medium"
#VOICE = "ru_RU-pvo240-medium"
#VOICE = "ru_RU-april420-medium"
#VOICE = "ru_RU-fr6800-medium"
#VOICE = "ru_RU-igm3500-medium"
#VOICE = "ru_RU-kat580-medium"
#VOICE = "ru_RU-mari-medium_epoch5699"
#VOICE = "ru_RU-nara426-medium"
#VOICE = "ru_RU-terra5871-medium"
MODEL_PATH = str(VOICES_DIR / f"{VOICE}.onnx")
CONFIG_PATH = str(VOICES_DIR / f"{VOICE}.onnx.json")

# ===== НАСТРОЙКИ РЕЧИ =====
LENGTH_SCALE = 1.320      # Базовая скорость: < 1.0 быстрее, > 1.0 медленнее
NOISE_SCALE = 0.567       # "Волнистость" голоса
NOISE_W_SCALE = 0.8       # Вариативность ширины фонем
VOLUME = 1.1              # Громкость
SENTENCE_SILENCE = 0.3    # Пауза между предложениями, секунды

print("Загрузка модели Piper...")
try:
    voice = PiperVoice.load(MODEL_PATH, config_path=CONFIG_PATH)
    sample_rate = getattr(voice.config, 'sample_rate', 22050)
    print(f"✅ Модель загружена! (Sample rate: {sample_rate} Hz)")
except Exception as e:
    print(f"❌ Ошибка загрузки модели: {e}", file=sys.stderr)
    sys.exit(1)

class TTSHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Отключаем спам в консоль

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        text = params.get('text', [''])[0]
        output = params.get('output', [''])[0]

        if not text or not output:
            self.send_response(400)
            self.end_headers()
            return

        # 1. Получаем "сырую" скорость от bash-скрипта (по умолчанию 0)
        try:
            sd_rate = float(params.get('sd_rate', ['0'])[0])
        except ValueError:
            sd_rate = 0

        # 2. Рассчитываем итоговую скорость на основе ваших настроек из начала файла
        # Если sd_rate > 0 (ускорение), множитель уменьшается. Если < 0, увеличивается.
        final_length_scale = LENGTH_SCALE * (1.0 - (sd_rate / 200.0))

        try:
            with wave.open(output, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)

                # 3. Используем переменные из верхнего блока настроек
                syn_config = SynthesisConfig(
                    length_scale=final_length_scale, # Расчетная скорость
                    noise_scale=NOISE_SCALE,         # Из верхнего блока
                    noise_w_scale=NOISE_W_SCALE,     # Из верхнего блока
                    volume=VOLUME,                   # Из верхнего блока
                )
                result = voice.synthesize(text, syn_config=syn_config)

                # 4. Запись аудио с паузами (SENTENCE_SILENCE тоже из верхнего блока)
                if hasattr(result, '__iter__') and not isinstance(result, (str, bytes, bytearray)):
                    silence = b"\x00\x00" * int(sample_rate * SENTENCE_SILENCE)
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
                            raise Exception(f"Неизвестная структура чанка: {type(chunk)}")
                else:
                    raise Exception(f"Неожиданный тип результата: {type(result)}")

            # Успешная отправка ответа
            try:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
            except (BrokenPipeError, ConnectionResetError):
                pass # Игнорируем разрыв соединения

        except (BrokenPipeError, ConnectionResetError):
            pass # Игнорируем разрыв соединения во время синтеза
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Ошибка синтеза: {error_msg}", file=sys.stderr)
            try:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(error_msg.encode())
            except (BrokenPipeError, ConnectionResetError):
                pass

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 5555), TTSHandler)
    print("🚀 Сервер запущен на порту 5555...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️ Остановка сервера...")
        server.server_close()
