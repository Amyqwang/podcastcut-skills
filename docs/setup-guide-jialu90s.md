# Podcastcut Skills 安装指南

> 适用于 jialu90s — Manus 环境 (Linux)

## 第 1 步：接受仓库邀请

你会收到一封来自 GitHub 的邮件邀请，点击 **Accept invitation** 接受。

或直接访问：https://github.com/Amyqwang/podcastcut-skills/invitations

## 第 2 步：克隆仓库

```bash
# 选一个你喜欢的目录
cd ~
git clone https://github.com/Amyqwang/podcastcut-skills.git
```

> 你拥有只读权限，可以 clone 和 pull 更新，但无法 push。

## 第 3 步：安装依赖

```bash
# Manus (Linux/Ubuntu)
sudo apt update && sudo apt install -y nodejs npm ffmpeg python3 python3-pip curl

# Node.js 依赖
cd ~/podcastcut-skills
npm install

# Python 依赖（可选，用于后期和质检）
pip install deepfilternet librosa soundfile
```

如果系统自带的 Node.js 版本过低，可以用 nvm：

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 20
```

## 第 4 步：注册 Skills 到 Claude Code

```bash
# 创建 skills 目录（如果不存在）
mkdir -p ~/.claude/skills

# 设置项目路径
PODCASTCUT_DIR="$HOME/podcastcut-skills"

# 创建符号链接
ln -s "$PODCASTCUT_DIR/安装"    ~/.claude/skills/podcastcut-安装
ln -s "$PODCASTCUT_DIR/剪播客"  ~/.claude/skills/podcastcut-剪播客
ln -s "$PODCASTCUT_DIR/后期"    ~/.claude/skills/podcastcut-后期
ln -s "$PODCASTCUT_DIR/质检"    ~/.claude/skills/podcastcut-质检
```

验证：重启 Claude Code，输入 `/`，应该能看到 `podcastcut-剪播客` 等 skill。

## 第 5 步：配置 ASR API Key

你需要一个语音识别服务的 API Key。推荐阿里云 DashScope：

1. 注册阿里云：https://dashscope.console.aliyun.com/
2. 开通"模型服务灵积"，创建 API Key

```bash
cd ~/podcastcut-skills
cp .env.example .env
```

编辑 `.env` 文件，填入你的 Key：

```
DASHSCOPE_API_KEY=sk-你的API-Key
```

## 第 6 步：验证安装

```bash
node -v                                          # Node.js
ffmpeg -version                                  # FFmpeg
python3 --version                                # Python 3
cat ~/podcastcut-skills/.env | grep DASHSCOPE    # API Key
ls -la ~/.claude/skills/ | grep podcastcut       # Skills 注册
```

## 开始使用

在 Claude Code 中直接说：

```
剪播客 /path/to/你的音频.mp3，2个说话人
```

或者：

```
帮我剪这个播客：
- 音频：/path/to/podcast.mp3
- 说话人：3人（主持人A、嘉宾B、嘉宾C）
```

## 拉取更新

```bash
cd ~/podcastcut-skills
git pull
```

## 常见问题

**Q: 提示权限不足？**
确认你已接受 GitHub 仓库邀请。

**Q: Skills 注册后看不到？**
1. 确认 symlink 有效：`ls -la ~/.claude/skills/ | grep podcastcut`
2. 重启 Claude Code 会话

**Q: 没有 brew？**
Manus 是 Linux 环境，用 `apt` 代替 `brew`。
