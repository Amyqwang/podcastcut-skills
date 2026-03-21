---
name: podcastcut:修订skill
description: 多终端并行修订 skill 的标准流程。worktree 隔离、监控审查、分批提交、验证合并。触发词：修订skill、修订、skill修订
---

<!--
input: 修订目标（要改哪些 skill、几条工作线）
output: 审查通过的分批 commit + push/PR
pos: 流程 skill，用于规范多终端协作修订

架构守护者：一旦我被修改，请同步更新：
1. ../README.md 的 Skill 清单
2. /CLAUDE.md 路由表
-->

# 修订 Skill

> 多终端并行修订 podcastcut 各 skill 的标准流程，确保隔离、安全、可追溯。

## 快速使用

```
用户: 修订skill，这次要改剪播客的静音逻辑和后期的时间戳功能
用户: 修订一下质检和剪播客
用户: 我要并行修改3个模块
```

## 流程总览

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  1.规划  │ →  │  2.开发  │ →  │  3.审查  │ →  │  4.合并  │
│  隔离准备 │    │  并行执行 │    │  质量把关 │    │  提交清理 │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
```

---

## Phase 1: 规划与隔离准备

### 1.1 明确工作线

与用户确认：
- 要修订哪些模块/skill
- 几条工作线可以并行
- 每条线的目标和范围

### 1.2 创建 worktree + 分支

每条工作线一个 worktree，**禁止多终端在同一目录同一分支工作**。

```bash
cd /Users/hhvan/AI/DC/podcastcut-skills

# 示例：两条并行线
git worktree add ../podcastcut-wt-A feat/工作线A描述
git worktree add ../podcastcut-wt-B feat/工作线B描述
```

### 1.3 打开新终端

用 osascript 为每条工作线打开独立终端窗口：

```bash
# 终端 A
osascript -e 'tell application "Terminal" to do script "cd /Users/hhvan/AI/DC/podcastcut-wt-A && echo \"请输入: claude\""'

# 终端 B
osascript -e 'tell application "Terminal" to do script "cd /Users/hhvan/AI/DC/podcastcut-wt-B && echo \"请输入: claude\""'
```

提醒用户：
- 在新窗口中输入 `claude` 启动（日常用标准模式）
- 仅在确认需要大批量自动操作时才加 `--dangerously-skip-permissions`

### 1.4 本终端作为监控角色

当前终端留在主仓库，负责：
- 定期扫描各 worktree 进度
- 最终做代码审查和合并

---

## Phase 2: 并行开发

### 2.1 各终端独立工作

每个终端在自己的 worktree 目录中工作，互不干扰。

### 2.2 监控终端定期扫描

每隔一段时间（或用户要求时）检查进度：

```bash
# 扫描各 worktree 的变更
for wt in ../podcastcut-wt-*; do
  echo "=== $(basename $wt) ==="
  git -C "$wt" diff --stat HEAD
  echo ""
done
```

### 2.3 小步提交原则

**⚠️ 关键规则**：每条工作线完成一个阶段就在自己的分支上 commit，不要积累大量未提交变更。

---

## Phase 3: 审查与质量把关

### 3.1 代码审查清单

当工作线完成后，在监控终端逐项检查：

**安全性**
- [ ] 无 SSL 验证禁用（`CERT_NONE`、`verify=False`）
- [ ] 无 `eval` 处理外部输入
- [ ] API Key 通过环境变量传递，不硬编码
- [ ] 网络服务默认绑定 `127.0.0.1`
- [ ] 无 JSON/命令拼接注入

**冗余度**
- [ ] 无重复实现的逻辑（应抽共享模块）
- [ ] 无功能完全重叠的脚本
- [ ] 两个文件共享逻辑时参数一致

**质量**
- [ ] 新文件语法检查通过（`node -c` / `python3 -c "import ast; ast.parse(...)"` / `bash -n`）
- [ ] config 解析使用可靠方式（node+yaml 优于 grep）
- [ ] 错误处理完整（参数校验、文件存在检查）
- [ ] 未实现的功能有明确提示而非静默失败

**风险**
- [ ] 核心算法改动有对比验证（用已有项目数据跑新旧对比）
- [ ] 用户偏好配置未被新逻辑绕过
- [ ] 多层处理的参数保持一致

### 3.2 修复问题

按优先级修复发现的问题：
- P0: 安全漏洞 → 立即修复
- P1: 逻辑缺陷/冗余 → 本次修复
- P2: 改进建议 → 本次或后续

### 3.3 验证测试

核心逻辑改动**必须**跑验证：

```bash
# 示例：用已有项目数据对比
cd output/2026-03-15_公园路/剪播客/2_分析
# 备份旧输出
cp fine_analysis_rules.json fine_analysis_rules_OLD.json
# 跑新逻辑
node ../../剪播客/scripts/run_fine_analysis.js --analysis-dir .
# 对比
diff fine_analysis_rules_OLD.json fine_analysis_rules.json | head -50
```

### 3.4 A/B 对比页面

当核心算法改动涉及**听感差异**（如静音处理、音质增强）时，生成 HTML 对比页面供人工试听验证。

**页面功能：**
- 左右并排加载旧版/新版音频，支持同步播放和独立播放
- 顶部统计卡片：时长差异、编辑数变化、保留量对比
- 差异列表：列出新版保留/旧版裁掉的所有位置，点击可跳转到该处试听
- 详情表格：每条编辑的上下文类型、原时长、阈值、保留量

**生成步骤：**

1. 用旧逻辑跑一遍，保存旧版音频和 fine_analysis_rules_OLD.json
2. 用新逻辑跑一遍，保存新版音频和 fine_analysis_rules.json
3. 生成 A/B 对比 HTML：

```bash
# 在项目的剪播客输出目录下
BASE_DIR="output/${DATE}_${AUDIO_NAME}/剪播客"

# 生成对比页面（需提供新旧两版音频和分析 JSON）
# 页面结构：
#   - 旧版音频: 3_成品/xxx_v1_trimmed.mp3
#   - 新版音频: 3_成品/xxx_新版_trimmed.mp3
#   - 旧分析:   2_分析/fine_analysis_rules_OLD.json
#   - 新分析:   2_分析/fine_analysis_rules.json
#   - 输出:     ab_compare.html
```

4. 用浏览器打开对比页面：

```bash
open "$BASE_DIR/ab_compare.html"
```

**对比页面模板要点：**
- 音频使用相对路径引用（`3_成品/xxx.mp3`），确保本地能播放
- 同步播放按钮：点击后两个 audio 元素同步 seek 和 play/pause
- 差异点跳转：根据新旧版本的时间偏移分别计算跳转位置
- 统计数据从两份 JSON 中提取对比

**参考实例：** `output/2026-03-15_公园路/剪播客/ab_compare.html`

---

## Phase 4: 合并与清理

### 4.1 分批提交

按功能拆分 commit，不做大杂烩：

```bash
# 在各 worktree 的分支上确保已 commit
git -C ../podcastcut-wt-A log --oneline -5
git -C ../podcastcut-wt-B log --oneline -5
```

### 4.2 合并回 main

```bash
cd /Users/hhvan/AI/DC/podcastcut-skills

# 方式 A: 直接合并（小改动）
git merge feat/工作线A描述
git merge feat/工作线B描述

# 方式 B: 走 PR（大改动，推荐）
git push origin feat/工作线A描述
gh pr create --title "feat: 工作线A描述" --body "..."
```

### 4.3 清理 worktree

```bash
git worktree remove ../podcastcut-wt-A
git worktree remove ../podcastcut-wt-B
git branch -d feat/工作线A描述
git branch -d feat/工作线B描述
```

### 4.4 Push

```bash
git push origin main
```

---

## 注意事项

1. **禁止多终端在同一目录同一分支工作** — 用 worktree 隔离
2. **小步提交** — 每完成一个阶段就 commit
3. **`--dangerously-skip-permissions` 仅限临时使用** — 日常用标准 `claude`，任务结束 `exit` 退出
4. **核心改动必须验证** — 不验证不合并
5. **大变更走 PR** — 不直接 push main
