# piper-server.py
Локальный сервер для Piper TTS в OS Linux и скрипт обёртка для подключения к нему Repy и Speech Dispatcher (модуль для него piper.conf, обитающий по адресу ~/.config/speech-dispatcher/modules/piper.conf в Fedora, добавлен что бы был; user_name внутри него, если он будте использоватся, должен быть заменён на актуальное имя пользователя) с заменой нежелательных символов в тексте.

Тестировался на Fedora Linux с версией piper 1.8 из https://github.com/OHF-voice/piper1-gpl/tree/main которая не совместима по параметрам (к примеру используется NOISE_W_SCALE вместо noise_w) с более старыми версиями.

Сервер создаётся для повышения отзывчивости модели piper (в памяти занимает 300-400 мегабайт).

Сервер запускается из домашнего каталога командой python3 ~/piper-server.py Доступен по адресу 127.0.0.1 порт по умолчанию 5555
Голоса ожидаются в каталоге ~/.local/share/piper-voices/ru/ Голоса меняются раскометирование нужной строки VOICE в файле сервера piper-server.py. 

Стандартные русские голоса piper https://huggingface.co/rhasspy/piper-voices/tree/main/ru/ru_RU (голоса denis, ruslan, dmiri на очень большого любителя)

Кастомные русские голоса piper https://huggingface.co/rraaww/ru_piper/tree/main

Файл сервера piper-server.py и скрипта piper-spd-wrapper.sh нужно поместить в домашний каталог и сделать исполняемыми как программа.

В читалку repy https://github.com/newptcai/repy сервер подключается через скрипт обёртку piper-spd-wrapper.sh напрямую (Через Speech Dispatcher подключить не получилось -- почему то читаются только отдельные слова) через параметр в настройках "preferred_tts_engine": "/home/user_name/piper-spd-wrapper.sh"


