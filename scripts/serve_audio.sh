#!/bin/bash
#
# 统一音频中转脚本 — 根据 config.yaml 的 upload.strategy 选择策略
#
# 用法: bash serve_audio.sh <音频文件路径> [url输出文件]
#
# 策略:
#   local_server — 启动本地 HTTP 服务（隐私优先，音频不离开本机）
#   public       — 上传到免费公共托管（原有行为）
#   aliyun_oss   — 上传到阿里云 OSS
#   tencent_cos  — 上传到腾讯云 COS
#

set -e

# 加载配置
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config_loader.sh"

AUDIO_FILE="$1"
URL_OUTPUT="${2:-audio_url.txt}"

if [ -z "$AUDIO_FILE" ]; then
    echo "用法: bash serve_audio.sh <音频文件路径> [url输出文件]"
    exit 1
fi

if [ ! -f "$AUDIO_FILE" ]; then
    echo "❌ 文件不存在: $AUDIO_FILE"
    exit 1
fi

FILE_SIZE=$(du -h "$AUDIO_FILE" | cut -f1)
echo "📤 音频中转 (策略: $UPLOAD_STRATEGY)"
echo "   文件: $AUDIO_FILE ($FILE_SIZE)"
echo ""

case "$UPLOAD_STRATEGY" in
  local_server)
    echo "🔒 使用本地服务器（音频不离开本机）"

    # 清理同端口的残留服务进程
    OLD_PID_FILE="${URL_OUTPUT}.pid"
    if [ -f "$OLD_PID_FILE" ]; then
      OLD_PID=$(cat "$OLD_PID_FILE" 2>/dev/null)
      if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "   🧹 清理残留服务进程 (PID: $OLD_PID)"
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
      fi
      rm -f "$OLD_PID_FILE"
    fi

    PORT=$(grep "port:" "$PODCASTCUT_DIR/config.yaml" 2>/dev/null | head -1 | sed 's/.*: *//' | tr -d ' ')
    PORT=${PORT:-8765}

    USE_NGROK=$(grep "use_ngrok:" "$PODCASTCUT_DIR/config.yaml" 2>/dev/null | head -1 | sed 's/.*: *//' | tr -d ' ')

    NGROK_FLAG=""
    if [ "$USE_NGROK" = "true" ]; then
      NGROK_FLAG="--ngrok"
    fi

    # 后台启动本地服务器
    python3 "$SCRIPT_DIR/local_audio_server.py" "$AUDIO_FILE" \
      --port "$PORT" \
      --url-file "$URL_OUTPUT" \
      $NGROK_FLAG &
    SERVER_PID=$!

    # 等待服务器启动
    sleep 2

    if kill -0 $SERVER_PID 2>/dev/null; then
      AUDIO_URL=$(cat "$URL_OUTPUT" 2>/dev/null)
      echo ""
      echo "✅ 本地服务器已启动 (PID: $SERVER_PID)"
      echo "   URL: $AUDIO_URL"
      echo ""
      echo "   ⚠️ 转录完成后停止: kill $SERVER_PID"
      echo "   💡 或下次运行时自动清理"
      echo "$SERVER_PID" > "${URL_OUTPUT}.pid"
    else
      echo "❌ 本地服务器启动失败"
      exit 1
    fi
    ;;

  public)
    echo "⚠️ 使用公共文件托管（音频会上传到公网）"
    bash "$PODCASTCUT_DIR/剪播客/scripts/upload_audio.sh" "$AUDIO_FILE"
    if [ -f "audio_url.txt" ] && [ "$URL_OUTPUT" != "audio_url.txt" ]; then
      cp audio_url.txt "$URL_OUTPUT"
    fi
    ;;

  aliyun_oss)
    echo "☁️ 使用阿里云 OSS"
    if [ -f "$PODCASTCUT_DIR/剪播客/scripts/archive/upload_to_oss.py" ]; then
      python3 "$PODCASTCUT_DIR/剪播客/scripts/archive/upload_to_oss.py" "$AUDIO_FILE"
    else
      echo "❌ OSS 上传脚本未找到"
      exit 1
    fi
    ;;

  tencent_cos)
    echo "☁️ 使用腾讯云 COS"
    echo "❌ 腾讯云 COS 上传暂未实现，请先安装 coscmd 并配置"
    echo "   pip install coscmd"
    echo "   参考: https://cloud.tencent.com/document/product/436/10976"
    exit 1
    ;;

  *)
    echo "❌ 未知的上传策略: $UPLOAD_STRATEGY"
    echo "   支持: local_server | public | aliyun_oss | tencent_cos"
    exit 1
    ;;
esac
