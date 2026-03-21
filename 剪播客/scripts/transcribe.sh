#!/bin/bash
#
# 统一转录入口 — 根据 config.yaml 的 asr.provider 自动选择服务商
#
# 用法: bash transcribe.sh <音频URL> <说话人数量>
#
# 支持:
#   aliyun  — 阿里云 DashScope FunASR
#   tencent — 腾讯云 ASR
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../../scripts/config_loader.sh"

AUDIO_URL="$1"
SPEAKER_COUNT="${2:-2}"

if [ -z "$AUDIO_URL" ]; then
    echo "❌ 请提供音频URL"
    echo "用法: bash transcribe.sh <音频URL> <说话人数量>"
    exit 1
fi

echo "🎤 转录服务: $ASR_PROVIDER"
echo ""

case "$ASR_PROVIDER" in
  aliyun)
    bash "$SCRIPT_DIR/aliyun_funasr_transcribe.sh" "$AUDIO_URL" "$SPEAKER_COUNT"
    ;;
  tencent)
    bash "$SCRIPT_DIR/tencent_asr_transcribe.sh" "$AUDIO_URL" "$SPEAKER_COUNT"
    ;;
  local)
    echo "❌ 本地 ASR 暂未实现"
    echo "   计划支持: Qwen3-ASR, Whisper"
    exit 1
    ;;
  *)
    echo "❌ 未知的 ASR 服务商: $ASR_PROVIDER"
    echo "   支持: aliyun | tencent | local"
    exit 1
    ;;
esac
