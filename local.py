"""
Простой HTTP сервер для капчи
Запуск: python captcha_server.py
"""
import http.server
import socketserver
import os
from pathlib import Path

PORT = 8765  # Локальный порт

# Переходим в папку captcha
captcha_dir = Path(__file__).parent / "captcha"
os.chdir(captcha_dir)

Handler = http.server.SimpleHTTPRequestHandler

print(f"🌐 Запуск сервера на http://localhost:{PORT}")
print(f"📁 Директория: {captcha_dir}")
print(f"🔗 Капча будет доступна на: http://localhost:{PORT}/captcha_runtime.html")
print("\nНажми Ctrl+C для остановки\n")

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✅ Сервер остановлен")