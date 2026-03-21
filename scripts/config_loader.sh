#!/bin/bash
#
# Shell 脚本用的配置加载器（兼容 bash + zsh）
# 用法: source "$(dirname "$0")/../scripts/config_loader.sh"
#
# 加载后可用变量:
#   $PODCASTCUT_DIR   - 项目根目录
#   $ASR_PROVIDER     - ASR 服务商 (aliyun|tencent|local)
#   $UPLOAD_STRATEGY  - 上传策略 (local_server|public|aliyun_oss|tencent_cos)
#   $DASHSCOPE_API_KEY - 阿里云 API Key (如已配置)
#

# 自动检测项目根目录
_find_project_root() {
  local dir="$1"
  local i
  for i in 1 2 3 4 5; do
    if [ -f "$dir/config.yaml" ]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  # fallback: 环境变量
  if [ -n "$PODCASTCUT_DIR" ]; then
    echo "$PODCASTCUT_DIR"
    return 0
  fi
  echo "❌ 错误：找不到 config.yaml，请设置环境变量 PODCASTCUT_DIR" >&2
  return 1
}

# 确定脚本所在目录（兼容 bash + zsh）
_get_script_dir() {
  if [ -n "${BASH_SOURCE[0]}" ]; then
    cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
  elif [ -n "${(%):-%x}" ] 2>/dev/null; then
    cd "$(dirname "${(%):-%x}")" && pwd
  else
    pwd
  fi
}

# 如果 PODCASTCUT_DIR 未设置，自动检测
if [ -z "$PODCASTCUT_DIR" ]; then
  _script_dir=$(_get_script_dir 2>/dev/null || pwd)
  PODCASTCUT_DIR=$(_find_project_root "$_script_dir")
  if [ $? -ne 0 ]; then
    return 1 2>/dev/null || exit 1
  fi
fi

export PODCASTCUT_DIR

# 加载 .env（如果存在）— 安全方式，不用 eval
ENV_FILE="$PODCASTCUT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  while IFS='=' read -r key value; do
    # 跳过注释和空行
    key=$(echo "$key" | sed 's/^[[:space:]]*//')
    case "$key" in
      ''|\#*) continue ;;
    esac
    # 只允许合法变量名（字母/数字/下划线）
    case "$key" in
      *[!A-Za-z0-9_]*) continue ;;
    esac
    value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    # 只设置未定义的变量（用 printenv 安全检查，不用 eval）
    if [ -z "$(printenv "$key" 2>/dev/null)" ]; then
      export "$key=$value"
    fi
  done < "$ENV_FILE"
fi

# 解析 config.yaml — 优先用 node（精确），fallback 用 grep（兼容）
_CONFIG_YAML="$PODCASTCUT_DIR/config.yaml"

_read_yaml_via_node() {
  # 用 js-yaml（已安装的依赖）精确解析嵌套字段
  # 参数: 点分路径，如 "asr.provider"
  node -e "
    const yaml = require('js-yaml');
    const fs = require('fs');
    const cfg = yaml.load(fs.readFileSync('$_CONFIG_YAML', 'utf8'));
    const keys = '$1'.split('.');
    let v = cfg;
    for (const k of keys) { v = v && v[k]; }
    if (v !== undefined && v !== null) process.stdout.write(String(v));
  " 2>/dev/null
}

# 读取 ASR provider
ASR_PROVIDER=$(_read_yaml_via_node "asr.provider")
ASR_PROVIDER=${ASR_PROVIDER:-aliyun}
export ASR_PROVIDER

# 读取上传策略
UPLOAD_STRATEGY=$(_read_yaml_via_node "upload.strategy")
UPLOAD_STRATEGY=${UPLOAD_STRATEGY:-local_server}
export UPLOAD_STRATEGY
