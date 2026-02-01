# FundPilot-AI 基金智能定投决策系统

<p align="center">
  <b>轻量级云端自动化辅助决策系统</b><br>
  在 A 股交易日通过量化指标 + DeepSeek AI 联合分析，推送定投操作建议
</p>

---

## ✨ 核心特性

| 特性 | 说明 |
|-----|-----|
| **双策略体系** | ETF 联接基金网格交易 + 债券基金防守型策略 |
| **多周期分位** | 60/250/500 日分位交叉验证，避免锚定偏误 |
| **动态阈值** | 根据品种波动率自动调整判断标准 |
| **熔断机制** | 极端行情（ETF ±7%、债券 -2%）自动暂停决策 |
| **AI 决策** | DeepSeek 模型结合量化指标生成投资建议 |
| **双邮件通知** | 12:30 盘中预警 + 14:45 决策报告 |
| **新手友好** | 邮件末尾包含 9 项术语解释 |

---

## 📁 项目结构

```
fund_pilot/
├── core/           # 核心模块（配置、日志、数据库）
├── data/           # 数据获取（估值、历史、持仓）
├── strategy/       # 策略逻辑（指标计算、ETF/债券策略）
├── ai/             # AI 集成（DeepSeek 客户端、提示词）
├── visualization/  # 图表生成
├── notification/   # 邮件模板和发送
├── scheduler/      # 定时任务调度
├── tests/          # 单元测试
├── main.py         # 入口文件
└── requirements.txt
```

---

## 🚀 快速开始（本地开发）

### 1. 克隆项目
```bash
git clone <your-repo-url> fund_pilot
cd fund_pilot
```

### 2. 创建虚拟环境
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置环境变量
```bash
cp .env.example .env
```

编辑 `.env` 文件，填入以下配置：

```env
# DeepSeek API
DEEPSEEK_API_KEY=sk-xxxxxxxx

# 邮件配置 (163 邮箱示例)
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USER=your_email@163.com
SMTP_PASSWORD=xxxxx  # 授权码，非登录密码
EMAIL_RECEIVER=your_email@163.com

# 可选：飞书通知
FEISHU_WEBHOOK=https://open.feishu.cn/...
```

### 5. 运行测试
```bash
python -m pytest tests/ -v
```

### 6. 本地运行
```bash
python main.py
```

---

## ☁️ 生产环境部署

### 方式一：云服务器直接部署

#### 1. 服务器准备
- 推荐系统：Ubuntu 22.04 / CentOS 8
- 最低配置：1 核 1G 内存
- 开放端口：无需开放（仅出站 SMTP/HTTPS）

#### 2. 安装 Python 环境
```bash
# Ubuntu
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip

# CentOS
sudo yum install -y python3.11 python3.11-devel
```

#### 3. 部署代码
```bash
# 创建应用目录
sudo mkdir -p /opt/fundpilot
cd /opt/fundpilot

# 上传代码（或使用 git clone）
git clone <your-repo-url> .

# 创建虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 4. 配置环境变量
```bash
cp .env.example .env
nano .env  # 编辑配置
chmod 600 .env  # 保护敏感信息
```

#### 5. 创建 Systemd 服务
```bash
sudo nano /etc/systemd/system/fundpilot.service
```

内容：
```ini
[Unit]
Description=FundPilot-AI Fund Investment Decision System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/fundpilot
EnvironmentFile=/opt/fundpilot/.env
ExecStart=/opt/fundpilot/.venv/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 6. 启动服务
```bash
sudo systemctl daemon-reload
sudo systemctl enable fundpilot
sudo systemctl start fundpilot

# 查看状态
sudo systemctl status fundpilot

# 查看日志
sudo journalctl -u fundpilot -f
```

---

## ⏰ 定时任务说明

| 时间 | 任务 | 说明 |
|-----|-----|-----|
| 12:30 | 盘中预警 | 发送估值快照和量化指标（无决策） |
| 14:45 | 辅助决策 | 发送 AI 决策建议和趋势图 |

> 系统会自动检测 A 股交易日，非交易日（周末、节假日）不执行任务。

---

## 🧪 验证部署

### 手动触发测试（绕过交易日检查）
```bash
cd /opt/fundpilot
source .venv/bin/activate
python -c "
import scheduler.calendar as cal
cal.should_run_task = lambda: True
from scheduler.jobs import run_alert_task, run_decision_task
run_alert_task()
run_decision_task()
"
```

### 检查日志
```bash
# Systemd
sudo journalctl -u fundpilot -n 100

# 应用日志
cat /opt/fundpilot/logs/fundpilot.log
```

---

## 📊 量化指标说明

| 指标 | 计算方式 | 用途 |
|-----|---------|-----|
| 多周期分位 | 60/250/500 日内的价格位置 | 判断估值高低 |
| 多周期共识 | 各周期分位是否一致 | 验证信号可靠性 |
| 60日均线偏离 | (当前价 - MA60) / MA60 | 判断趋势强弱 |
| 60日年化波动率 | 日收益率标准差 × √252 | 动态调整阈值 |
| 60日最大回撤 | 期间最大跌幅 | 评估下行风险 |

---

## 🔧 配置项说明

### 基金池配置 (`core/config.py`)
```python
FUND_POOL = [
    {"code": "110017", "name": "易方达增强回报债券A", "type": "Bond"},
    {"code": "000307", "name": "易方达黄金ETF联接A", "type": "ETF_Feeder"},
    # 添加更多基金...
]
```

### 策略阈值 (`strategy/indicators.py`)
```python
PERCENTILE_WINDOW_SHORT = 60   # 短期分位窗口
PERCENTILE_WINDOW_MID = 250    # 中期分位窗口
PERCENTILE_WINDOW_LONG = 500   # 长期分位窗口
MA_WINDOW = 60                 # 均线窗口
CIRCUIT_BREAKER_ETF = 7.0      # ETF 熔断阈值 (%)
CIRCUIT_BREAKER_BOND = 2.0     # 债券熔断阈值 (%)
```

---

## 🛠 常见问题

### Q: 估值数据显示"已过期"？
A: 非交易时段或数据源延迟，不影响使用（系统使用最近一个交易日数据）。

### Q: 邮件发送失败？
A: 检查 SMTP 配置，163 邮箱需要使用"授权码"而非登录密码。

### Q: 如何添加新基金？
A: 在 `core/config.py` 的 `FUND_POOL` 中添加，类型支持 `Bond` 和 `ETF_Feeder`。

---

## 📜 许可证

MIT License

---

## 🙏 致谢

- [AkShare](https://github.com/akfamily/akshare) - 金融数据接口
- [DeepSeek](https://deepseek.com) - AI 大模型
- [APScheduler](https://apscheduler.readthedocs.io/) - 定时任务框架
