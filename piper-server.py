#!/usr/bin/env python3  # или в ##!/home/username/.venvs/piper-env/bin/python если python в дистрибутиве оказался прогрессивнее, чем было нужно для piper
import gc
import sys
import threading
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from piper import PiperVoice
    from piper.config import SynthesisConfig
except ImportError:
    print("Ошибка: выполните 'pip install piper-tts'", file=sys.stderr)
    sys.exit(1)
# пути к модели MODEL_PATH = "/home/username/.local/share/piper-voices/ru/ru_RU-irina-medium.onnx" и её конфигу #CONFIG_PATH = "/home/username/.local/share/piper-voices/ru/ru_RU-irina-medium.onnx.json"
VOICES_DIR = Path.home() / ".local" / "share" / "piper-voices" / "ru"

# ===== НАСТРОЙКИ РЕЧИ =====
LENGTH_SCALE = 1.320      # Базовая скорость: < 1.0 быстрее, > 1.0 медленнее
NOISE_SCALE = 0.567       # "Волнистость" голоса
NOISE_W_SCALE = 0.8       # Вариативность ширины фонем
VOLUME = 1.1              # Громкость
SENTENCE_SILENCE = 0.3    # Пауза между предложениями, секунды

# Глобальное состояние текущей модели и блокировка потоков
current_voice = None
current_sample_rate = 22050
current_voice_name = ""
voice_lock = threading.Lock()


def get_available_voices():
    """Сканирует каталог и возвращает отсортированный список доступных голосов."""
    if not VOICES_DIR.exists():
        return []
    voices = []
    for onnx_file in sorted(VOICES_DIR.glob("*.onnx")):
        json_file = onnx_file.with_suffix(".onnx.json")
        if json_file.exists():
            voices.append(onnx_file.stem)
    return voices


def load_voice_model(voice_name):
    """Выгружает предыдущую модель из памяти и загружает новую."""
    global current_voice, current_sample_rate, current_voice_name

    model_path = str(VOICES_DIR / f"{voice_name}.onnx")
    config_path = str(VOICES_DIR / f"{voice_name}.onnx.json")

    print(f"\n⏳ Загрузка модели '{voice_name}'...")
    try:
        new_voice = PiperVoice.load(model_path, config_path=config_path)
        new_sample_rate = getattr(new_voice.config, "sample_rate", 22050)
    except Exception as e:
        print(f"❌ Ошибка загрузки модели '{voice_name}': {e}", file=sys.stderr)
        return False

    # Потокобезопасная замена модели и очистка памяти
    with voice_lock:
        if current_voice is not None:
            del current_voice
            gc.collect()  # Принудительно освобождаем память от старой модели
        current_voice = new_voice
        current_sample_rate = new_sample_rate
        current_voice_name = voice_name

    print(f"✅ Модель '{voice_name}' загружена! (Sample rate: {current_sample_rate} Hz)")
    return True


def print_voices_menu(voices):
    """Выводит пронумерованный список голосов в консоль."""
    print("\n=== Доступные голоса ===")
    for idx, name in enumerate(voices, start=1):
        marker = " [АКТИВЕН]" if name == current_voice_name else ""
        print(f"  {idx}. {name}{marker}")
    print("========================")


def select_voice_from_list(voices, prompt_text="Введите номер голоса: "):
    """Запрашивает у пользователя номер и загружает выбранный голос."""
    while True:
        try:
            choice = input(prompt_text).strip()
            if not choice:
                continue
            if choice.lower() in ("q", "exit", "quit"):
                return False

            idx = int(choice)
            if 1 <= idx <= len(voices):
                selected = voices[idx - 1]
                if selected == current_voice_name:
                    print(f"ℹ️ Голос '{selected}' уже активен.")
                    return True
                return load_voice_model(selected)
            else:
                print(f"⚠️ Введите число от 1 до {len(voices)}.")
        except ValueError:
            print("⚠️ Некорректный ввод. Введите номер из списка.")
        except (EOFError, KeyboardInterrupt):
            return False


def interactive_console_loop():
    """Фоновый поток для смены голоса во время работы сервера."""
    while True:
        voices = get_available_voices()
        if not voices:
            print(f"❌ В каталоге {VOICES_DIR} больше нет моделей!", file=sys.stderr)
            break

        print_voices_menu(voices)
        print("Введите номер для смены голоса (или 'r' чтобы обновить список, Ctrl+C для выхода):")

        try:
            cmd = input("> ").strip()
            if not cmd:
                continue
            if cmd.lower() == "r":
                continue

            idx = int(cmd)
            if 1 <= idx <= len(voices):
                selected = voices[idx - 1]
                if selected == current_voice_name:
                    print(f"ℹ️ Голос '{selected}' уже активен.")
                else:
                    load_voice_model(selected)
            else:
                print(f"⚠️ Введите число от 1 до {len(voices)}.")
        except ValueError:
            print("⚠️ Введите корректный номер.")
        except (EOFError, KeyboardInterrupt):
            break


class TTSHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Отключаем спам в консоль

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        text = params.get("text", [""])[0]
        output = params.get("output", [""])[0]

        if not text or not output:
            self.send_response(400)
            self.end_headers()
            return

        try:
            sd_rate = float(params.get("sd_rate", ["0"])[0])
        except ValueError:
            sd_rate = 0

        final_length_scale = LENGTH_SCALE * (1.0 - (sd_rate / 200.0))

        try:
            # Блокируем замену модели на время генерации аудио
            with voice_lock:
                if current_voice is None:
                    raise Exception("Голосовая модель не загружена")

                with wave.open(output, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(current_sample_rate)

                    syn_config = SynthesisConfig(
                        length_scale=final_length_scale,
                        noise_scale=NOISE_SCALE,
                        noise_w_scale=NOISE_W_SCALE,
                        volume=VOLUME,
                    )
                    result = current_voice.synthesize(text, syn_config=syn_config)

                    if hasattr(result, "__iter__") and not isinstance(result, (str, bytes, bytearray)):
                        silence = b"\x00\x00" * int(current_sample_rate * SENTENCE_SILENCE)
                        first = True
                        for chunk in result:
                            if hasattr(chunk, "audio_int16_bytes"):
                                if not first:
                                    wav_file.writeframes(silence)
                                wav_file.writeframes(chunk.audio_int16_bytes)
                                first = False
                            elif hasattr(chunk, "audio_int16_array"):
                                import numpy as np
                                if not first:
                                    wav_file.writeframes(silence)
                                wav_file.writeframes(np.array(chunk.audio_int16_array, dtype=np.int16).tobytes())
                                first = False
                            else:
                                raise Exception(f"Неизвестная структура чанка: {type(chunk)}")
                    else:
                        raise Exception(f"Неожиданный тип результата: {type(result)}")

            try:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
            except (BrokenPipeError, ConnectionResetError):
                pass

        except (BrokenPipeError, ConnectionResetError):
            pass

        except Exception as e:
            error_msg = str(e)
            print(f"\n❌ Ошибка синтеза: {error_msg}", file=sys.stderr)
            try:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(error_msg.encode())
            except (BrokenPipeError, ConnectionResetError):
                pass


if __name__ == "__main__":
    available_voices = get_available_voices()
    if not available_voices:
        print(f"❌ В каталоге {VOICES_DIR} не найдены пары файлов (.onnx + .onnx.json).", file=sys.stderr)
        sys.exit(1)

    print_voices_menu(available_voices)
    if not select_voice_from_list(available_voices, "Выберите стартовый голос (номер): "):
        print("Выход.")
        sys.exit(0)

    server = HTTPServer(("127.0.0.1", 5555), TTSHandler)
    print("\n🚀 Сервер запущен на порту 5555...")

    # Запускаем интерактивное меню смены голоса в отдельном фоновом потоке
    console_thread = threading.Thread(target=interactive_console_loop, daemon=True)
    console_thread.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️ Остановка сервера...")
        server.server_close()
