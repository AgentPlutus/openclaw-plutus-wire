# Plutus Wire

打通自己的时间线，突破算法信息茧房。

[English README](README.md)

Plutus Wire 是一个 OpenClaw-first 的本地 skill。它通过 OpenCLI 复用用户自己浏览器里的登录态，读取用户本来就能看到的 X 时间线，把 Following、For You、可选 Home tabs、Likes、Bookmarks 等来源保存到本地 SQLite，再生成可以审阅的情报卡片。

它不是 OpenCLI 的 fork，也不是通用爬虫框架。OpenCLI 负责浏览器桥接；Plutus Wire 负责 X adapters、source 选择、本地存储、离线 cron 契约、processor、review 页面和可选的云端 handoff。

## 一键本地安装

前提：

- 已安装 OpenCLI。
- 已安装 OpenClaw，后续要跑 cron 时需要。
- 本机浏览器已经登录 X。

```bash
npm install -g @jackwener/opencli
git clone https://github.com/AgentPlutus/openclaw-plutus-wire.git
cd openclaw-plutus-wire
./install.sh
```

`./install.sh` 会做这些事：

- 把仓库里的 OpenCLI adapters 安装到 `~/.opencli/clis/plutus-wire`。
- 运行 `opencli validate plutus-wire`。
- 探测账号可见的 X Home tabs。
- 写入 `~/.openclaw/state/plutus-wire/config.json`。
- 写入一次 dry-run manifest，确认本地状态目录可用。

如果想安装后立刻跑一轮真实 ingest 和 processing：

```bash
./install.sh --run-now
```

然后打开本地 review 页面：

```bash
python3 scripts/serve_review.py
```

浏览器访问：

```text
http://127.0.0.1:8787
```

## Adapters 在哪里

Adapters 已经在仓库中：

```text
opencli-clis/plutus-wire/
  health.js
  home-tabs.js
  timeline.js
  likes.js
  bookmarks.js
  _shared/
```

安装脚本默认使用 copy 模式，把这些 adapters 复制到 OpenCLI 的本地目录。开发者可以改用 symlink：

```bash
./install.sh --adapter-mode symlink
```

## 默认来源

默认启用：

- Following
- For You

可选启用：

- AI Home tab，如果该账号探测到这个 tab。
- Bookmarks。
- Likes，需要用户提供自己的 X handle。

示例：

```bash
python3 scripts/plutus_wire_setup.py --enable ai
python3 scripts/plutus_wire_setup.py --enable bookmarks
python3 scripts/plutus_wire_setup.py --likes-handle your_handle --enable likes
```

Notifications 不在 v0.1 默认范围内。Lists 和 Communities 也不是默认来源。

## 本地运行链路

手动跑一轮：

```bash
python3 scripts/plutus_wire_tick.py --execute-adapters --process
python3 scripts/plutus_wire_db_status.py
python3 scripts/serve_review.py
```

这会写入：

```text
~/.openclaw/state/plutus-wire/runs/
~/.openclaw/state/plutus-wire/raw/
~/.openclaw/state/plutus-wire/db/plutus_wire.sqlite
~/.openclaw/state/plutus-wire/review/latest-cards.json
```

## Cron

先确认本地 smoke 能跑：

```bash
./install.sh --run-now
```

再查看将要创建的 OpenClaw cron：

```bash
python3 scripts/install_openclaw_cron.py --every 5m
```

确认后再安装：

```bash
python3 scripts/install_openclaw_cron.py --every 5m --apply
```

默认 cron 只做本地 ingest 和 processor，不上传云端。

## 云端 Handoff

默认不上传任何 feed 数据。

如果用户明确要接入服务器平台，可以打开 redacted daily handoff：

```bash
python3 scripts/plutus_wire_setup.py \
  --cloud-enable \
  --cloud-mode redacted-daily \
  --cloud-endpoint https://example.com/plutus-wire/ingest

python3 scripts/plutus_wire_cloud_handoff.py
```

上传需要显式 `--apply`：

```bash
python3 scripts/plutus_wire_cloud_handoff.py --apply
```

`full-visible-feed` 会保留用户可见的公开帖子文本，必须额外确认：

```bash
python3 scripts/plutus_wire_setup.py \
  --cloud-enable \
  --cloud-mode full-visible-feed \
  --cloud-endpoint https://example.com/plutus-wire/ingest \
  --cloud-allow-full-visible-feed
```

## 隐私边界

- 不要求用户粘贴 cookies、tokens 或密码。
- 只读取用户自己的浏览器登录态本来可见的页面。
- Raw artifacts 和 SQLite 默认留在本机。
- 网络中断、登出、captcha、rate limit 都按可恢复状态记录，不让 cron 整体崩掉。
- 云端 handoff 必须显式启用，并先在本地写 redacted manifest/package。
