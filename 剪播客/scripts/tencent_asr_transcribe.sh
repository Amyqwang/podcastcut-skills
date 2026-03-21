#!/bin/bash
#
# 腾讯云 ASR 录音文件识别脚本（薄包装，调用 Python 实现）
# 用法: bash tencent_asr_transcribe.sh <音频URL> <说话人数量>
#
# 需要环境变量:
#   TENCENT_SECRET_ID  — 腾讯云 SecretId
#   TENCENT_SECRET_KEY — 腾讯云 SecretKey
#
# 输出格式与阿里云 FunASR 兼容（通过 adapter 转换）
#

set -e

# 加载配置（自动加载 .env 中的 API Key）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../../scripts/config_loader.sh"

# 检查参数
if [ -z "$1" ]; then
    echo "❌ 错误：请提供音频URL"
    echo ""
    echo "用法: bash tencent_asr_transcribe.sh <音频URL> <说话人数量>"
    exit 1
fi

# 检查 API Key
if [ -z "$TENCENT_SECRET_ID" ] || [ -z "$TENCENT_SECRET_KEY" ]; then
    echo "❌ 错误：未设置腾讯云 API Key"
    echo ""
    echo "请在 .env 中配置:"
    echo "  TENCENT_SECRET_ID=your-secret-id"
    echo "  TENCENT_SECRET_KEY=your-secret-key"
    echo ""
    echo "获取地址: https://console.cloud.tencent.com/cam/capi"
    exit 1
fi

# 调用 Python 实现（签名更可靠、无跨平台兼容问题）
exec python3 "$SCRIPT_DIR/tencent_asr_py.py" "$@"
