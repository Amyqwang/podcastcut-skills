#!/usr/bin/env python3
"""
时间戳偏移同步脚本

读取基准时间戳（相对于正文起点）+ 片头时间线 JSON → 计算偏移 → 输出最终时间戳。

用法:
  # 正向：base + timeline → 偏移后时间戳
  python3 sync_timestamps.py \
    --base podcast_时间戳_base.txt \
    --timeline intro_complete_timeline.json \
    --crossfade 5 \
    --output podcast_时间戳.txt

  # 反向：从已偏移的时间戳反推 base（一次性）
  python3 sync_timestamps.py --reverse \
    --input podcast_时间戳.txt \
    --timeline intro_complete_timeline.json \
    --crossfade 5 \
    --output podcast_时间戳_base.txt

偏移公式:
  offset = intro_total_duration - crossfade_duration
"""

import argparse
import json
import os
import re
import sys


def parse_timestamp(ts_str):
    """解析 MM:SS 或 H:MM:SS，返回总秒数。"""
    parts = ts_str.split(':')
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    raise ValueError(f"无法解析时间戳: {ts_str}")


def format_timestamp(total_seconds):
    """总秒数 → MM:SS 或 H:MM:SS。"""
    if total_seconds < 0:
        raise ValueError(f"时间戳不能为负数: {total_seconds}秒")
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def read_timestamps(filepath):
    """读取时间戳文件，返回 list of (seconds, label) 或 None（空行）。"""
    lines = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, raw_line in enumerate(f, 1):
            line = raw_line.rstrip('\n')
            if line.strip() == '':
                lines.append(None)
                continue
            match = re.match(r'^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$', line.strip())
            if not match:
                print(f"⚠️ 第{line_num}行格式不符，跳过: {line}", file=sys.stderr)
                continue
            lines.append((parse_timestamp(match.group(1)), match.group(2)))
    return lines


def forward(args, offset_seconds):
    """正向：base → 偏移后时间戳。"""
    base_lines = read_timestamps(args.base)
    if not base_lines:
        print("错误: 基准时间戳文件为空", file=sys.stderr)
        sys.exit(1)

    output_lines = [f"00:00 {args.intro_label}"]
    for item in base_lines:
        if item is None:
            output_lines.append('')
        else:
            output_lines.append(f"{format_timestamp(item[0] + offset_seconds)} {item[1]}")

    return '\n'.join(output_lines) + '\n'


def reverse(args, offset_seconds):
    """反向：已偏移时间戳 → base。"""
    if not args.input:
        print("错误: --reverse 模式需要 --input 参数", file=sys.stderr)
        sys.exit(1)

    offset_lines = read_timestamps(args.input)
    output_lines = []
    skipped_intro = False

    for item in offset_lines:
        if item is None:
            output_lines.append('')
            continue
        seconds, label = item
        # 跳过 "00:00 片头精彩预览"
        if not skipped_intro and seconds == 0:
            skipped_intro = True
            continue
        new_seconds = seconds - offset_seconds
        if new_seconds < 0:
            print(f"⚠️ 反推后时间为负数，跳过: {label}", file=sys.stderr)
            continue
        output_lines.append(f"{format_timestamp(new_seconds)} {label}")

    return '\n'.join(output_lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description='时间戳偏移同步')
    parser.add_argument('--base', help='基准时间戳文件（正向模式）')
    parser.add_argument('--timeline', required=True, help='片头时间线 JSON')
    parser.add_argument('--crossfade', type=float, default=5.0, help='交叉淡入淡出时长(s)，默认5')
    parser.add_argument('--output', default='podcast_时间戳.txt', help='输出文件路径')
    parser.add_argument('--intro-label', default='片头精彩预览', help='片头行标签')
    parser.add_argument('--reverse', action='store_true', help='反向：从偏移后时间戳反推 base')
    parser.add_argument('--input', help='（仅 --reverse）已偏移的时间戳文件')
    parser.add_argument('--dry-run', action='store_true', help='只打印不写入')
    args = parser.parse_args()

    if not os.path.exists(args.timeline):
        print(f"错误: 找不到时间线 JSON: {args.timeline}", file=sys.stderr)
        sys.exit(1)

    with open(args.timeline, 'r', encoding='utf-8') as f:
        timeline = json.load(f)

    intro_duration = timeline['total_duration']
    offset_seconds = int(round(intro_duration - args.crossfade))

    print(f"片头: {intro_duration:.1f}s | crossfade: {args.crossfade:.1f}s | 偏移: {offset_seconds}s")

    if args.reverse:
        result = reverse(args, offset_seconds)
    else:
        if not args.base:
            print("错误: 正向模式需要 --base 参数", file=sys.stderr)
            sys.exit(1)
        if not os.path.exists(args.base):
            print(f"错误: 找不到基准文件: {args.base}", file=sys.stderr)
            sys.exit(1)
        result = forward(args, offset_seconds)

    if args.dry_run:
        print("\n--- 预览 ---")
        print(result)
    else:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"✅ 已写入: {args.output}\n")
        print(result)


if __name__ == '__main__':
    main()
