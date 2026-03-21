#!/usr/bin/env python3
"""
步骤 5.2: 播客音质增强

三步处理流程：
  Step A: 全链处理（highpass → denoise → EQ → compress → limiter）→ 临时文件
  Step B: 测量临时文件的 LUFS/TP/LRA
  Step C: 对临时文件应用 loudnorm（线性模式，正确 measured 值）→ 最终输出

用法:
  python3 enhance_audio.py input.mp3 [output.mp3] \
    --preset podcast|interview|minimal \
    --config config.yaml \
    --no-denoise / --no-eq / --no-compress \
    --deess                # 启用去齿音（实验性，默认关闭）
    --deepfilter / --no-deepfilter \
    --preview              # 只处理前 30 秒预览
    --dry-run              # 只分析不处理

预设:
  podcast   — 标准播客：降噪（有 DeepFilterNet 时）、轻度 EQ、3:1 压缩
  interview — 远程连线：更强降噪、更多清晰度提升、4:1 压缩
  minimal   — 专业录制：不降噪、轻度压缩、保持原始动态
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ──────────────────────────────────────────────
# 预设定义
# ──────────────────────────────────────────────

PRESETS = {
    "podcast": {
        "highpass_freq": 80,
        "denoise": True,
        "deess": False,
        "eq": [
            {"f": 300,  "w": 1.5, "g": -2},    # 削浑浊
            {"f": 3000, "w": 1.5, "g": 2},      # 提清晰度
            {"f": 5000, "w": 2.0, "g": 1.5},    # 提气感
        ],
        "compressor": {
            "threshold": -20, "ratio": 3, "attack": 10,
            "release": 200, "knee": 6, "makeup": 2,
        },
        "limiter": {"limit": -1, "attack": 5, "release": 50},
        "loudnorm": {"target_lufs": -16, "true_peak": -1.5, "lra": 11},
    },
    "interview": {
        "highpass_freq": 100,
        "denoise": True,
        "deess": False,
        "eq": [
            {"f": 250,  "w": 1.5, "g": -3},    # 更强削浑浊
            {"f": 3000, "w": 1.5, "g": 3},      # 更多清晰度
            {"f": 5000, "w": 2.0, "g": 2},      # 更多气感
        ],
        "compressor": {
            "threshold": -18, "ratio": 4, "attack": 5,
            "release": 150, "knee": 4, "makeup": 3,
        },
        "limiter": {"limit": -1, "attack": 5, "release": 50},
        "loudnorm": {"target_lufs": -16, "true_peak": -1.5, "lra": 9},
    },
    "minimal": {
        "highpass_freq": 60,
        "denoise": False,
        "deess": False,
        "eq": [
            {"f": 300,  "w": 1.5, "g": -1},
        ],
        "compressor": {
            "threshold": -24, "ratio": 2, "attack": 20,
            "release": 300, "knee": 8, "makeup": 1,
        },
        "limiter": {"limit": -1, "attack": 5, "release": 50},
        "loudnorm": {"target_lufs": -16, "true_peak": -1.5, "lra": 14},
    },
}


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def run(cmd, capture=False, check=True):
    """运行外部命令，统一错误处理。"""
    print(f"  → {' '.join(cmd[:6])}{'...' if len(cmd) > 6 else ''}")
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True if capture else None,
        check=check,
    )
    return result


def check_deepfilter():
    """检测 DeepFilterNet 是否可用。"""
    return shutil.which("deep-filter") is not None


def get_audio_duration(path):
    """获取音频时长（秒）。"""
    r = run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", path],
        capture=True,
    )
    info = json.loads(r.stdout)
    return float(info["format"]["duration"])


def measure_loudness(path):
    """测量音频的 LUFS/TP/LRA（用 ffmpeg loudnorm 的 stats 输出）。"""
    r = run(
        ["ffmpeg", "-hide_banner", "-i", path,
         "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture=True, check=True,
    )
    # loudnorm 的 JSON 输出在 stderr
    stderr = r.stderr
    # 提取最后一个 JSON 块
    matches = list(re.finditer(r'\{[^{}]+\}', stderr, re.DOTALL))
    if not matches:
        print("  ⚠️  无法解析 loudnorm 测量输出，使用默认值")
        return {
            "input_i": "-24.0", "input_tp": "-2.0",
            "input_lra": "10.0", "input_thresh": "-34.0",
        }
    stats = json.loads(matches[-1].group())
    return stats


def load_config(config_path):
    """加载 config.yaml 中的 audio_enhancement 段。"""
    if not config_path or not os.path.exists(config_path):
        return {}
    try:
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("audio_enhancement", {})
    except ImportError:
        # 无 PyYAML 时简单解析
        return _parse_yaml_simple(config_path)


def _parse_yaml_simple(path):
    """简易 YAML 解析（仅处理 audio_enhancement 段）。"""
    result = {}
    in_section = False
    current_subsection = None
    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            if stripped == "audio_enhancement:":
                in_section = True
                continue
            if in_section:
                # 检查是否离开了 audio_enhancement 段（顶层 key）
                if not line.startswith(" ") and not line.startswith("\t"):
                    break
                # 解析 key: value
                if ":" in stripped:
                    key, _, val = stripped.partition(":")
                    key = key.strip()
                    val = val.strip()
                    # 检查是否是子段
                    if not val or val == "":
                        current_subsection = key
                        result[key] = {}
                        continue
                    # 布尔/数值
                    if val == "true":
                        val = True
                    elif val == "false":
                        val = False
                    else:
                        try:
                            val = float(val) if "." in val else int(val)
                        except ValueError:
                            pass

                    if current_subsection and line.startswith("    "):
                        result.setdefault(current_subsection, {})[key] = val
                    else:
                        current_subsection = None
                        result[key] = val
    return result


# ──────────────────────────────────────────────
# 处理链构建
# ──────────────────────────────────────────────

def build_filter_chain(preset_cfg, steps_override):
    """根据预设和覆盖参数构建 ffmpeg -af 链（Step A 部分）。"""
    filters = []

    # 1. 高通滤波
    if steps_override.get("highpass", True):
        freq = preset_cfg["highpass_freq"]
        filters.append(f"highpass=f={freq}")

    # 2. EQ 均衡（降噪在链外处理，此处不含）
    if steps_override.get("eq", True):
        for eq in preset_cfg["eq"]:
            filters.append(
                f"equalizer=f={eq['f']}:t=q:w={eq['w']}:g={eq['g']}"
            )

    # 3. 去齿音（实验性，默认关闭）
    if steps_override.get("deess", preset_cfg.get("deess", False)):
        # 静态频率衰减 — 6-8kHz -4dB
        filters.append("equalizer=f=7000:t=q:w=2.0:g=-4")

    # 4. 压缩
    if steps_override.get("compress", True):
        c = preset_cfg["compressor"]
        filters.append(
            f"acompressor=threshold={c['threshold']}dB"
            f":ratio={c['ratio']}"
            f":attack={c['attack']}"
            f":release={c['release']}"
            f":knee={c['knee']}"
            f":makeup={c['makeup']}"
        )

    # 5. 限幅
    if steps_override.get("limiter", True):
        lim = preset_cfg["limiter"]
        filters.append(
            f"alimiter=limit={lim['limit']}dB"
            f":level=false"
            f":attack={lim['attack']}"
            f":release={lim['release']}"
        )

    return ",".join(filters)


def build_loudnorm_filter(preset_cfg, measured):
    """构建 Step C 的 loudnorm 滤镜（线性模式 + 精确测量值）。"""
    ln = preset_cfg["loudnorm"]
    return (
        f"loudnorm=I={ln['target_lufs']}"
        f":TP={ln['true_peak']}"
        f":LRA={ln['lra']}"
        f":linear=true"
        f":measured_I={measured['input_i']}"
        f":measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}"
        f":measured_thresh={measured['input_thresh']}"
    )


# ──────────────────────────────────────────────
# 降噪
# ──────────────────────────────────────────────

def run_deepfilter(input_path, output_path):
    """使用 DeepFilterNet 降噪。"""
    print("\n🔇 降噪: DeepFilterNet")
    run(["deep-filter", input_path, "-o", output_path])
    if not os.path.exists(output_path):
        # deep-filter 默认输出到同目录，文件名可能不同
        base = os.path.basename(input_path)
        name, _ = os.path.splitext(base)
        candidate = os.path.join(
            os.path.dirname(output_path) or ".", f"{name}_DeepFilterNet3.wav"
        )
        if os.path.exists(candidate):
            os.rename(candidate, output_path)
        else:
            # 搜索输出目录
            out_dir = os.path.dirname(output_path) or "."
            for f in os.listdir(out_dir):
                if f.startswith(name) and "DeepFilter" in f:
                    os.rename(os.path.join(out_dir, f), output_path)
                    break


def run_afftdn(input_path, output_path):
    """使用 ffmpeg afftdn 降噪（用户显式选择时）。"""
    print("\n🔇 降噪: ffmpeg afftdn（注意：可能产生伪影）")
    run([
        "ffmpeg", "-hide_banner", "-y",
        "-i", input_path,
        "-af", "afftdn=nf=-25:tn=1",
        output_path,
    ])


# ──────────────────────────────────────────────
# 主处理流程
# ──────────────────────────────────────────────

def process_audio(
    input_path, output_path, preset_name, steps_override,
    denoise_strategy, preview, dry_run, config_enhancement,
):
    """三步处理主流程。"""
    preset_cfg = PRESETS[preset_name].copy()

    # 合并 config.yaml 中的覆盖（loudnorm 参数）
    if config_enhancement:
        cfg_ln = config_enhancement.get("loudnorm", {})
        if cfg_ln:
            preset_cfg["loudnorm"] = {
                "target_lufs": cfg_ln.get("target_lufs", preset_cfg["loudnorm"]["target_lufs"]),
                "true_peak": cfg_ln.get("true_peak", preset_cfg["loudnorm"]["true_peak"]),
                "lra": cfg_ln.get("lra", preset_cfg["loudnorm"]["lra"]),
            }

    duration = get_audio_duration(input_path)
    print(f"\n📊 输入: {input_path}")
    print(f"   时长: {duration:.1f}s ({duration/60:.1f}min)")
    print(f"   预设: {preset_name}")

    # Dry-run: 只测量不处理
    if dry_run:
        print("\n📏 测量当前音频指标...")
        stats = measure_loudness(input_path)
        print(f"\n   Integrated Loudness: {stats.get('input_i', 'N/A')} LUFS")
        print(f"   True Peak:           {stats.get('input_tp', 'N/A')} dBTP")
        print(f"   LRA:                 {stats.get('input_lra', 'N/A')} LU")
        print(f"   Threshold:           {stats.get('input_thresh', 'N/A')} LUFS")
        target = preset_cfg["loudnorm"]
        print(f"\n   目标: {target['target_lufs']} LUFS / {target['true_peak']} dBTP / LRA {target['lra']}")
        print("\n✅ Dry-run 完成（未处理音频）")
        return

    tmpdir = tempfile.mkdtemp(prefix="enhance_")
    try:
        current_input = input_path

        # Preview: 截取前 30 秒
        if preview:
            print("\n🎧 预览模式: 只处理前 30 秒")
            preview_input = os.path.join(tmpdir, "preview_input.wav")
            run([
                "ffmpeg", "-hide_banner", "-y",
                "-i", input_path, "-t", "30",
                "-acodec", "pcm_s16le", "-ar", "44100",
                preview_input,
            ])
            current_input = preview_input

        # ── Step A: 降噪（可选，链外处理） ──
        do_denoise = steps_override.get("denoise", preset_cfg.get("denoise", True))
        if do_denoise and denoise_strategy != "off":
            has_deepfilter = check_deepfilter()

            if denoise_strategy == "auto":
                if has_deepfilter:
                    denoised = os.path.join(tmpdir, "denoised.wav")
                    run_deepfilter(current_input, denoised)
                    if os.path.exists(denoised):
                        current_input = denoised
                    else:
                        print("  ⚠️  DeepFilterNet 输出未找到，跳过降噪")
                else:
                    print("  ℹ️  DeepFilterNet 未安装，跳过降噪（denoise_strategy=auto）")
            elif denoise_strategy == "deepfilter":
                if has_deepfilter:
                    denoised = os.path.join(tmpdir, "denoised.wav")
                    run_deepfilter(current_input, denoised)
                    if os.path.exists(denoised):
                        current_input = denoised
                    else:
                        print("  ❌ DeepFilterNet 输出未找到")
                        sys.exit(1)
                else:
                    print("  ❌ DeepFilterNet 未安装但 denoise_strategy=deepfilter")
                    sys.exit(1)
            elif denoise_strategy == "ffmpeg":
                denoised = os.path.join(tmpdir, "denoised.wav")
                run_afftdn(current_input, denoised)
                current_input = denoised

        # ── Step A: 全链处理 ──
        af_chain = build_filter_chain(preset_cfg, steps_override)
        step_a_output = os.path.join(tmpdir, "step_a.wav")

        if af_chain:
            print(f"\n🔧 Step A: 全链处理")
            print(f"   滤镜: {af_chain[:100]}{'...' if len(af_chain) > 100 else ''}")
            run([
                "ffmpeg", "-hide_banner", "-y",
                "-i", current_input,
                "-af", af_chain,
                "-acodec", "pcm_s16le", "-ar", "44100",
                step_a_output,
            ])
        else:
            # 无滤镜，直接转 WAV
            print("\n🔧 Step A: 无滤镜，直接通过")
            run([
                "ffmpeg", "-hide_banner", "-y",
                "-i", current_input,
                "-acodec", "pcm_s16le", "-ar", "44100",
                step_a_output,
            ])

        # ── Step B: 测量 ──
        if steps_override.get("loudnorm", True):
            print("\n📏 Step B: 测量 LUFS/TP/LRA")
            measured = measure_loudness(step_a_output)
            print(f"   Measured I:   {measured.get('input_i', 'N/A')} LUFS")
            print(f"   Measured TP:  {measured.get('input_tp', 'N/A')} dBTP")
            print(f"   Measured LRA: {measured.get('input_lra', 'N/A')} LU")

            # ── Step C: loudnorm ──
            print(f"\n🎚️  Step C: 响度归一化 → {preset_cfg['loudnorm']['target_lufs']} LUFS")
            loudnorm_filter = build_loudnorm_filter(preset_cfg, measured)
            run([
                "ffmpeg", "-hide_banner", "-y",
                "-i", step_a_output,
                "-af", loudnorm_filter,
                "-ar", "44100",
                "-codec:a", "libmp3lame", "-q:a", "2",
                output_path,
            ])
        else:
            # 跳过 loudnorm，直接编码
            print("\n🎚️  跳过 loudnorm，直接编码输出")
            run([
                "ffmpeg", "-hide_banner", "-y",
                "-i", step_a_output,
                "-ar", "44100",
                "-codec:a", "libmp3lame", "-q:a", "2",
                output_path,
            ])

        # 最终测量
        print("\n📊 最终指标:")
        final_stats = measure_loudness(output_path)
        print(f"   Integrated Loudness: {final_stats.get('input_i', 'N/A')} LUFS")
        print(f"   True Peak:           {final_stats.get('input_tp', 'N/A')} dBTP")
        print(f"   LRA:                 {final_stats.get('input_lra', 'N/A')} LU")

        out_duration = get_audio_duration(output_path)
        out_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"\n✅ 输出: {output_path}")
        print(f"   时长: {out_duration:.1f}s ({out_duration/60:.1f}min)")
        print(f"   大小: {out_size:.1f}MB")

    finally:
        # 清理临时目录
        shutil.rmtree(tmpdir, ignore_errors=True)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def resolve_output_path(input_path, output_arg):
    """生成默认输出文件名: xxx_enhanced.mp3"""
    if output_arg:
        return output_arg
    base, ext = os.path.splitext(input_path)
    return f"{base}_enhanced{ext or '.mp3'}"


def find_config():
    """向上搜索 config.yaml。"""
    # 从脚本所在目录向上搜索
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search = script_dir
    for _ in range(5):
        candidate = os.path.join(search, "config.yaml")
        if os.path.exists(candidate):
            return candidate
        search = os.path.dirname(search)
    return None


def main():
    parser = argparse.ArgumentParser(
        description="播客音质增强 — 清晰、干净、标准响度",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="输入音频文件")
    parser.add_argument("output", nargs="?", default=None, help="输出文件（默认: *_enhanced.mp3）")
    parser.add_argument("--preset", choices=["podcast", "interview", "minimal"],
                        default=None, help="处理预设（默认: podcast）")
    parser.add_argument("--config", default=None, help="config.yaml 路径")

    # 步骤开关
    parser.add_argument("--no-denoise", action="store_true", help="跳过降噪")
    parser.add_argument("--no-eq", action="store_true", help="跳过 EQ")
    parser.add_argument("--no-compress", action="store_true", help="跳过压缩")
    parser.add_argument("--deess", action="store_true", help="启用去齿音（实验性）")
    parser.add_argument("--deepfilter", action="store_true", help="强制使用 DeepFilterNet")
    parser.add_argument("--no-deepfilter", action="store_true", help="禁用 DeepFilterNet")

    # 模式
    parser.add_argument("--preview", action="store_true", help="只处理前 30 秒预览")
    parser.add_argument("--dry-run", action="store_true", help="只分析不处理")

    args = parser.parse_args()

    # 验证输入
    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    # 加载 config
    config_path = args.config or find_config()
    config_enhancement = {}
    if config_path and os.path.exists(config_path):
        print(f"📋 配置: {config_path}")
        config_enhancement = load_config(config_path)

    # 检查 enabled
    if config_enhancement and config_enhancement.get("enabled") is False:
        print("ℹ️  音质增强已在 config.yaml 中禁用（audio_enhancement.enabled: false）")
        print("   跳过处理。")
        sys.exit(0)

    # 确定预设
    preset_name = args.preset
    if not preset_name:
        preset_name = config_enhancement.get("preset", "podcast")
    if preset_name not in PRESETS:
        print(f"❌ 未知预设: {preset_name}")
        sys.exit(1)

    # 确定降噪策略
    denoise_strategy = config_enhancement.get("denoise_strategy", "auto")
    if args.deepfilter:
        denoise_strategy = "deepfilter"
    elif args.no_deepfilter:
        denoise_strategy = "off"

    # 构建步骤覆盖
    config_steps = config_enhancement.get("steps", {})
    steps_override = {
        "highpass": config_steps.get("highpass", True),
        "denoise": not args.no_denoise and config_steps.get("denoise", True),
        "deess": args.deess or config_steps.get("deess", False),
        "eq": not args.no_eq and config_steps.get("eq", True),
        "compress": not args.no_compress and config_steps.get("compress", True),
        "limiter": config_steps.get("limiter", True),
        "loudnorm": config_steps.get("loudnorm", True),
    }

    # 输出路径
    output_path = resolve_output_path(args.input, args.output)

    print("=" * 50)
    print("🎙️  播客音质增强")
    print("=" * 50)

    process_audio(
        input_path=args.input,
        output_path=output_path,
        preset_name=preset_name,
        steps_override=steps_override,
        denoise_strategy=denoise_strategy,
        preview=args.preview,
        dry_run=args.dry_run,
        config_enhancement=config_enhancement,
    )


if __name__ == "__main__":
    main()
