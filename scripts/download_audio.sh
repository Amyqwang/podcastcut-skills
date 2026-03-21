#!/bin/bash
#
# 音频下载脚本 — 支持腾讯会议录制链接、直接媒体URL、本地文件
#
# 用法: bash download_audio.sh <URL或文件路径> <输出目录>
#
# 支持的输入:
#   - 本地文件路径: /path/to/audio.mp3
#   - 腾讯会议录制: https://meeting.tencent.com/v2/cloud-record/share?id=xxx
#   - 直接媒体URL:  https://example.com/audio.mp4
#   - 其他视频平台链接 (通过 yt-dlp)
#

set -e

INPUT="$1"
OUTPUT_DIR="$2"

if [ -z "$INPUT" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "用法: bash download_audio.sh <URL或文件路径> <输出目录>"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
OUTPUT_FILE="$OUTPUT_DIR/audio.mp3"

# --- 判断输入类型 ---

if [ -f "$INPUT" ]; then
    # 本地文件
    echo "📁 检测到本地文件: $INPUT"
    EXT="${INPUT##*.}"
    EXT=$(echo "$EXT" | tr '[:upper:]' '[:lower:]')

    if [ "$EXT" = "mp3" ]; then
        cp "$INPUT" "$OUTPUT_FILE"
        echo "✅ 已复制 → $OUTPUT_FILE"
    else
        echo "🔄 转换 $EXT → mp3..."
        ffmpeg -i "file:$INPUT" -vn -acodec libmp3lame -ar 16000 -ac 1 -y "$OUTPUT_FILE" 2>/dev/null
        echo "✅ 已转换 → $OUTPUT_FILE"
    fi
    exit 0
fi

if [[ ! "$INPUT" =~ ^https?:// ]]; then
    echo "❌ 无效输入: $INPUT"
    echo "   请提供本地文件路径或 URL"
    exit 1
fi

# --- URL 下载 ---

echo "🔗 检测到 URL: $INPUT"

# 检查 yt-dlp 是否可用
if command -v yt-dlp &>/dev/null; then
    HAS_YTDLP=true
else
    HAS_YTDLP=false
fi

# 策略1: 直接媒体URL (mp3/mp4/m4a/wav/flac/ogg/webm)
if [[ "$INPUT" =~ \.(mp3|mp4|m4a|wav|flac|ogg|webm)(\?.*)?$ ]]; then
    echo "📥 直接下载媒体文件..."
    TEMP_FILE="$OUTPUT_DIR/download_temp"
    if curl -L -f --max-time 600 -o "$TEMP_FILE" "$INPUT" 2>/dev/null; then
        echo "🔄 转换为 mp3..."
        ffmpeg -i "$TEMP_FILE" -vn -acodec libmp3lame -ar 16000 -ac 1 -y "$OUTPUT_FILE" 2>/dev/null
        rm -f "$TEMP_FILE"
        echo "✅ 下载完成 → $OUTPUT_FILE"
        exit 0
    fi
    rm -f "$TEMP_FILE"
    echo "   ❌ 直接下载失败"
fi

# 策略2: yt-dlp (腾讯会议、各视频平台)
if [ "$HAS_YTDLP" = true ]; then
    echo "📥 使用 yt-dlp 下载音频..."

    # 腾讯会议链接特殊处理
    if [[ "$INPUT" =~ meeting\.tencent\.com ]]; then
        echo "   检测到腾讯会议录制链接"
    fi

    if yt-dlp -x --audio-format mp3 --audio-quality 0 \
        -o "$OUTPUT_DIR/download_temp.%(ext)s" \
        --no-playlist \
        "$INPUT" 2>/dev/null; then

        # yt-dlp 输出文件可能有不同扩展名
        DL_FILE=$(ls "$OUTPUT_DIR"/download_temp.* 2>/dev/null | head -1)
        if [ -n "$DL_FILE" ]; then
            mv "$DL_FILE" "$OUTPUT_FILE"
            echo "✅ 下载完成 → $OUTPUT_FILE"
            exit 0
        fi
    fi
    echo "   ❌ yt-dlp 下载失败"
fi

# 策略3: 尝试 curl 直接下载 (可能是重定向后的直接链接)
echo "📥 尝试 curl 直接下载..."
TEMP_FILE="$OUTPUT_DIR/download_temp"
if curl -L -f --max-time 600 -o "$TEMP_FILE" "$INPUT" 2>/dev/null; then
    # 检查是否为有效的媒体文件
    FILE_TYPE=$(file -b "$TEMP_FILE" 2>/dev/null || echo "unknown")
    if echo "$FILE_TYPE" | grep -qiE "audio|video|MPEG|ISO Media|Matroska"; then
        echo "🔄 转换为 mp3..."
        if ffmpeg -i "$TEMP_FILE" -vn -acodec libmp3lame -ar 16000 -ac 1 -y "$OUTPUT_FILE" 2>/dev/null; then
            rm -f "$TEMP_FILE"
            echo "✅ 下载完成 → $OUTPUT_FILE"
            exit 0
        fi
    fi
    rm -f "$TEMP_FILE"
    echo "   ❌ 下载的内容不是有效的媒体文件（可能是登录页面）"
fi
rm -f "$TEMP_FILE" 2>/dev/null

# 全部失败
echo ""
echo "❌ 无法自动下载此链接"
echo ""
if [ "$HAS_YTDLP" = false ]; then
    echo "💡 建议安装 yt-dlp 以支持更多平台（包括腾讯会议）:"
    echo "   brew install yt-dlp"
    echo ""
fi
echo "💡 备选方案: 手动下载音频文件，然后传入本地路径"
exit 1
