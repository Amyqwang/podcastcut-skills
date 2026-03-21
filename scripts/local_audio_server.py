#!/usr/bin/env python3
"""
本地音频 HTTP 服务器 — 替代公网上传，保护隐私

用法:
  python3 local_audio_server.py <音频文件路径> [--port 8765] [--ngrok]

启动后:
  - 本地访问: http://localhost:8765/audio.mp3
  - 如需公网访问（给云端 ASR 用），加 --ngrok 参数

按 Ctrl+C 停止服务器
"""

import http.server
import os
import sys
import signal
import json
import threading
import argparse
import shutil
from pathlib import Path

class AudioHandler(http.server.SimpleHTTPRequestHandler):
    """只服务指定的音频文件"""

    audio_path = None
    audio_filename = None

    def do_GET(self):
        if self.path == f'/{self.audio_filename}' or self.path == '/audio':
            self.send_response(200)
            ext = Path(self.audio_path).suffix.lower()
            content_types = {
                '.mp3': 'audio/mpeg',
                '.wav': 'audio/wav',
                '.m4a': 'audio/mp4',
                '.flac': 'audio/flac',
            }
            self.send_header('Content-Type', content_types.get(ext, 'application/octet-stream'))
            file_size = os.path.getsize(self.audio_path)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
            with open(self.audio_path, 'rb') as f:
                shutil.copyfileobj(f, self.wfile)
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # 静默日志，只打印关键信息
        if '200' in str(args):
            sys.stderr.write(f"   📥 音频被请求下载\n")


def start_ngrok(port):
    """尝试启动 ngrok 隧道"""
    try:
        import subprocess
        proc = subprocess.Popen(
            ['ngrok', 'http', str(port), '--log=stdout', '--log-format=json'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # 等待 ngrok 启动并获取公网 URL
        import time
        time.sleep(3)
        result = subprocess.run(
            ['curl', '-s', 'http://localhost:4040/api/tunnels'],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            tunnels = json.loads(result.stdout)
            for tunnel in tunnels.get('tunnels', []):
                if tunnel.get('proto') == 'https':
                    return tunnel['public_url'], proc
        return None, proc
    except FileNotFoundError:
        print("   ⚠️ ngrok 未安装，无法创建公网隧道")
        print("   安装: brew install ngrok")
        return None, None
    except Exception as e:
        print(f"   ⚠️ ngrok 启动失败: {e}")
        return None, None


def main():
    parser = argparse.ArgumentParser(description='本地音频 HTTP 服务器')
    parser.add_argument('audio_file', help='音频文件路径')
    parser.add_argument('--port', type=int, default=8765, help='服务端口 (默认 8765)')
    parser.add_argument('--ngrok', action='store_true', help='启动 ngrok 公网隧道')
    parser.add_argument('--url-file', help='将 URL 写入此文件')
    args = parser.parse_args()

    audio_path = os.path.abspath(args.audio_file)
    if not os.path.exists(audio_path):
        print(f"❌ 文件不存在: {audio_path}")
        sys.exit(1)

    audio_filename = os.path.basename(audio_path)
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)

    AudioHandler.audio_path = audio_path
    AudioHandler.audio_filename = audio_filename

    bind_addr = '0.0.0.0' if args.ngrok else '127.0.0.1'
    server = http.server.HTTPServer((bind_addr, args.port), AudioHandler)

    local_url = f'http://localhost:{args.port}/{audio_filename}'
    print(f"🎧 本地音频服务器已启动")
    print(f"   文件: {audio_filename} ({file_size_mb:.1f} MB)")
    print(f"   本地 URL: {local_url}")

    ngrok_proc = None
    final_url = local_url

    if args.ngrok:
        print(f"   🌐 正在启动 ngrok 隧道...")
        ngrok_url, ngrok_proc = start_ngrok(args.port)
        if ngrok_url:
            final_url = f'{ngrok_url}/{audio_filename}'
            print(f"   公网 URL: {final_url}")
        else:
            print(f"   ⚠️ ngrok 失败，使用本地 URL")

    # 写入 URL 文件
    if args.url_file:
        with open(args.url_file, 'w') as f:
            f.write(final_url)
        print(f"   URL 已保存到: {args.url_file}")

    print(f"\n   按 Ctrl+C 停止服务器")

    def shutdown(signum, frame):
        print(f"\n🛑 服务器已停止")
        if ngrok_proc:
            ngrok_proc.terminate()
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    server.serve_forever()


if __name__ == '__main__':
    main()
