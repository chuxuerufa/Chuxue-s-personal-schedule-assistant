# 🎓 专升本 AI 备考助手

基于 DeepSeek V4 + 飞书机器人的智能备考系统。

## 功能

- 🤖 **AI 生成备考计划**：输入考试日期和当前水平，DeepSeek 生成高数+英语的分阶段备考计划
- 📅 **双阶段推送**：每晚 22:00 飞书推送次日计划预览 → 确认 → 次日早上正式推送
- ✅ **打卡追踪**：手机浏览器打开即可打卡，统计完成率和连续打卡天数
- 🔄 **每周 AI 调整**：根据实际进度，AI 自动调整后续计划

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API

编辑 `config.py`，填入：

- **DeepSeek API Key**：[platform.deepseek.com](https://platform.deepseek.com) 注册获取
- **飞书 Webhook URL**：飞书群 → 设置 → 群机器人 → 添加自定义机器人 → 复制 Webhook 地址

### 3. 启动服务

```bash
python app.py
```

浏览器打开 `http://localhost:5000`，手机访问 `http://<你的电脑IP>:5000`

### 4. 配置定时推送

**方式 A — Windows 任务计划程序（推荐）：**

```powershell
# 每晚 22:00 预览推送
schtasks /create /tn "StudyPreview" /tr "python C:\Users\陈帅\study-planner\daily_preview.py" /sc daily /st 22:00

# 每天早上 7:00 早安推送
schtasks /create /tn "StudyMorning" /tr "python C:\Users\陈帅\study-planner\morning_push.py" /sc daily /st 07:00
```

**方式 B — 内置调度器（需常驻运行）：**

```bash
python scheduler.py
```

## 使用流程

1. 打开网页 → 创建计划 → 填写考试信息和当前水平
2. AI 生成完整备考计划（10-30秒）
3. 每晚 22:00 飞书收到明日计划预览，点击确认
4. 次日早上飞书收到正式推送，开始学习
5. 网页打卡，追踪进度
6. 每个周末 AI 根据完成情况自动调整下周计划

## 技术栈

Python + Flask + SQLite + DeepSeek V4 + 飞书 Webhook
