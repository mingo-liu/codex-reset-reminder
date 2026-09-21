# Codex 重置卡邮件提醒

通过 SMTP 发送 HTML 邮件，汇总可用重置卡并提醒即将到期的卡片。只使用 Python 标准库，不自动兑换重置卡。

## 提醒规则

- 每周一、周四北京时间 **09:00** 发送汇总，允许在 09:00–09:59 内延迟执行，之后不补发。
- 每小时整点检查；进入**到期前 2 小时**窗口时提醒一次，已使用或已过期的卡不提醒。
- 本地保存发送记录，避免重复邮件。邮件同时包含 HTML 和纯文本版本。

## 快速开始

需要 **Python 3.9+、macOS 或 Linux**，可用的系统时区数据，以及支持 SSL 的 SMTP 服务。

### 1. 预览

```bash
python3 mailer.py --input examples/usage.example.json --preview
```

用浏览器打开生成的 `daily.html` 和 `expiry.html`。示例数据全部虚构，仅用于预览。

### 2. 配置邮箱

在邮箱服务商处开启 SMTP、获取授权码，然后运行：

```bash
python3 setup_smtp.py
```

按提示输入登录邮箱、收件邮箱和授权码。默认使用 `smtp.qq.com:465`，支持修改服务器和端口，仅支持 SSL，不支持 STARTTLS。

配置保存在本地 `smtp.local.json`，权限为 `0600`，不会加入 Git。授权码不显示在终端中，但在该文件中是明文。旧配置未指定收件人时，默认使用登录邮箱。

### 3. 获取数据并测试

让 Codex 调用 `mcp__codex_app__get_usage_limits`，将最新返回的 JSON 对象保存为 `usage.json`。必需的数据结构见 [虚构示例](examples/usage.example.json)，`expiresAt` 为 Unix 秒级时间戳。

```bash
# 向配置的收件人发送真实测试邮件
python3 mailer.py --input usage.json --test

# 正式运行：根据时间和发送记录决定是否发送
python3 mailer.py --input usage.json
```

`--test` 忽略发送时段，不占用正式汇总的去重标记；不能与 `--preview` 同时使用。正式运行前必须刷新账户数据，程序不会自行查询账户或判断快照是否陈旧。

## 配置定时任务

本仓库只提供邮件程序，不会安装定时任务。在 Codex 中为项目设置**每小时整点**执行，使用以下指令：

```text
在当前项目目录执行重置卡邮件提醒：
1. 仅检查 smtp.local.json 是否存在，不读取或输出凭据；缺失则报告需要配置。
2. 调用 mcp__codex_app__get_usage_limits 获取最新数据，保存为 usage.json。
   查询失败或缺少 rateLimitResetCredits.credits 时停止，不使用旧数据或发送零张汇总。
3. 运行 python3 mailer.py --input usage.json，使用本地配置的 SMTP 和收件人。
4. 保留 state.json，由程序处理发送时段和去重；失败后下次重试。
5. 禁止兑换重置卡，不修改收件人、提醒规则或邮件程序。
6. 无需处理时保持安静；重复失败或需要用户处理时报告。
```

本地定时执行需要电脑和 Codex 正常运行，并具备 SMTP 网络权限。每次唤醒 Codex 会调用模型，邮件程序本身不调用模型。正常情况下提前 1–2 小时提醒；电脑睡眠、调度延迟和网络故障仍可能导致遗漏。
