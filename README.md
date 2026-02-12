# FundPilot-AI 基金智能定投决策系统 (v6.0)

<p align="center">
  <b>量化策略 + AI 深度推理的双轨制智能投顾系统</b><br>
  结合多周期分位估值与 DeepSeek 推理大模型，生成专业投资决策报告<br>
  <b>支持 ETF / 黄金 / 周期 / 固收+ / 美股 QDII 五类资产</b>
</p>

---

## 核心特性

| 特性 | 说明 |
|-----|-----|
| **双轨决策引擎** | 量化策略（分位/均线/波动率）+ AI 专家（持仓穿透/宏观逻辑）双重验证 |
| **智能合成仲裁** | 基于资产属性动态计算权重；极端分歧时检测量化信号强度，避免机械折中 |
| **多周期分位** | 60/250/500 日**极值分位 + 排名分位**双指标交叉验证，识别真假低估 |
| **资产感知共识** | 不同资产使用专属共识阈值（如周期 30/70、美股 25/75），拒绝一刀切 |
| **AI 信心度校准** | AI 自评信心度施加折扣系数（×0.85），让策略与 AI 在合成时公平博弈 |
| **美股 QDII 支持** | NQ=F 纳指期货实时注入、美股长牛高估温和化处理、跨市场分析 Prompt |
| **双向熔断机制** | ETF / 债券均支持暴跌 + 暴涨双向熔断，极端行情自动冷静期 |
| **动态风控** | 针对黄金/周期/固收+/纯债/美股自动匹配波动率阈值 |
| **双轨回测验证** | T+1 方向验证 + T+5 收益验证，决策效果闭环反馈 |
| **专业邮件报告** | 暗色主题、回测表格、置信度百分比、结构化 AI 分析 |

---

## 项目结构

```
fund_pilot/
├── ai/                        # AI 决策模块
│   ├── ai_decision.py         # AI 决策主逻辑 + 上下文构建
│   ├── deepseek_client.py     # DeepSeek API 客户端
│   ├── specialized_prompts.py # 7 种资产专用 Prompt
│   └── prompt_builder.py      # 盘中预警上下文构建
├── strategy/                  # 量化策略引擎
│   ├── decision_synthesizer.py # 双轨决策合成器
│   ├── etf_strategy.py        # ETF/黄金/周期/美股策略
│   ├── bond_strategy.py       # 债券/固收+策略
│   ├── asset_config.py        # 资产阈值配置中心
│   └── indicators.py          # 量化指标（含排名分位值）
├── data/                      # 数据采集与配置
│   ├── funds.json             # 基金配置（代码/类型/资产类别）
│   ├── fund_history.py        # 历史净值 (AkShare)
│   ├── fund_valuation.py      # 实时估值
│   ├── holdings.py            # 持仓穿透 + 实时行情
│   ├── market.py              # A 股大盘行情
│   └── us_market.py           # NQ=F 纳指期货（QDII 专用）
├── notification/              # 邮件通知
│   ├── email_template.py      # 决策报告模板
│   ├── alert_template.py      # 盘中快报模板
│   └── sender.py              # 邮件发送
├── scheduler/                 # 任务调度
│   ├── jobs.py                # 定时任务（决策/预警）
│   └── calendar.py            # 交易日历
├── core/                      # 核心配置
│   ├── config.py              # 配置加载（从 funds.json）
│   └── logger.py              # 日志系统
├── visualization/             # 图表生成
│   └── chart.py               # 趋势图（10日K线 + 均线）
└── main.py                    # 启动入口
```

---

## 双轨决策架构

```
┌──────────────────────────────────────────────────────────────┐
│                     FundPilot 决策流程                        │
├──────────────────────────────────────────────────────────────┤
│  1. 数据采集     净值/估值/持仓/大盘/NQ期货                    │
│       ↓                                                       │
│  2. 指标计算     多周期分位(极值+排名) / 均线 / 波动率           │
│       ↓                                                       │
│  3. 双轨决策                                                   │
│     ├─ 策略决策   规则引擎(资产感知阈值 + 动态共识)              │
│     └─ AI 决策   DeepSeek(专业Prompt + 策略参考 + 资产阈值)     │
│       ↓                                                       │
│  4. 决策合成     一致性加成 / 权重仲裁 / 极端分歧智能处理        │
│       ↓                                                       │
│  5. 报告推送     邮件(含图表/回测/AI分析/风险提示)               │
│       ↓                                                       │
│  6. 效果验证     T+1 方向校验 / T+5 收益校验                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 1. 环境准备
```bash
git clone <your-repo-url> fund_pilot
cd fund_pilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置

**API 与邮件配置**：
```bash
cp .env.example .env
```

编辑 `.env`：
```env
DEEPSEEK_API_KEY=sk-xxxxxx
SMTP_SERVER=smtp.163.com
EMAIL_SENDER=your_email@163.com
EMAIL_PASSWORD=xxxxxx
EMAIL_RECEIVERS=recipient@example.com
```

**基金配置**（创建 `data/funds.json`）：
```json
[
    {
        "code": "110017",
        "name": "易方达增强回报债券A",
        "type": "Bond",
        "asset_class": "BOND_ENHANCED"
    },
    {
        "code": "000307",
        "name": "易方达黄金ETF联接A",
        "type": "ETF_Feeder",
        "underlying_etf": "159934",
        "asset_class": "GOLD_ETF"
    },
    {
        "code": "021778",
        "name": "广发纳指100ETF联接F",
        "type": "QDII",
        "asset_class": "US_EQUITY_INDEX"
    }
]
```

> **字段说明**：`type` 可选 `Bond` / `ETF_Feeder` / `QDII`；`asset_class` 可选 `BOND_ENHANCED` / `BOND_PURE` / `GOLD_ETF` / `COMMODITY_CYCLE` / `US_EQUITY_INDEX`。`underlying_etf` 仅 ETF 联接基金需要。

### 3. 运行
```bash
# 启动常驻进程（自动按交易日运行）
python3 main.py
```

---

## Linux 部署 (systemd)

### 1. 上传项目
```bash
# 假设本地项目在 fund_pilot 目录
scp -r fund_pilot user@your-server:/root/app/
```

### 2. 服务器配置
```bash
cd /root/app/fund_pilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 API Key 和邮件配置
# 创建 data/funds.json 填入基金列表
```

### 3. 创建 systemd 服务
```bash
sudo vim /etc/systemd/system/fundpilot.service
```

```ini
[Unit]
Description=FundPilot AI Investment Decision System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/app/fund_pilot
Environment="PATH=/root/app/fund_pilot/.venv/bin"
ExecStart=/root/app/fund_pilot/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4. 启用服务
```bash
sudo systemctl daemon-reload
sudo systemctl enable fundpilot
sudo systemctl start fundpilot
```

### 5. 常用命令
```bash
sudo systemctl status fundpilot   # 查看状态
sudo systemctl restart fundpilot  # 重启服务
sudo journalctl -u fundpilot -f   # 查看实时日志
tail -f logs/fundpilot.log        # 查看日志文件
```

---

## 调试命令

```bash
# 强制运行决策任务（跳过交易日判断）
FUND_PILOT_FORCE_RUN=true python3 -c "
from scheduler import calendar
calendar.is_trading_day = lambda d=None: True
calendar.should_run_task = lambda d=None: True
from scheduler.jobs import run_decision_task
run_decision_task()
"

# 强制运行盘中快报
FUND_PILOT_FORCE_RUN=true python3 -c "
from scheduler import calendar
calendar.is_trading_day = lambda d=None: True
calendar.should_run_task = lambda d=None: True
from scheduler.jobs import run_alert_task
run_alert_task()
"
```

---

## 资产类型与策略配置

| 资产类型 | 代码 | 策略路径 | AI 权重 | 共识阈值 | 策略特点 |
|---------|------|---------|--------|---------|---------|
| **黄金避险** | `GOLD_ETF` | ETF策略 | 60% | 35/65 | 高估不暂停，大盘暴跌时正常定投（对冲） |
| **周期资源** | `COMMODITY_CYCLE` | ETF策略 | 50% | 30/70 | 逆向思维，分批建仓，宽阈值 |
| **美股指数** | `US_EQUITY_INDEX` | ETF策略 | 55% | 25/75 | 长牛高估常态化，仅>95%+强高估才暂停 |
| **固收+** | `BOND_ENHANCED` | 债券策略 | 40% | 40/60 | 默认保持定投，信号触发加仓 |
| **纯债** | `BOND_PURE` | 债券策略 | 30% | 45/55 | 极低波动，严格估值纪律 |

---

## 双轨回测验证

系统内置自动化效果验证机制，无需人工干预。

### T+1 方向验证
- **目标**: 验证决策对次日涨跌判断的准确性
- `双倍补仓` → 次日上涨 = 正确
- `暂停定投` → 次日下跌 = 正确
- `正常定投` → 次日上涨或微跌(>-1%) = 正确

### T+5 收益验证
- **目标**: 验证决策执行 5 个交易日后的实际收益
- `双倍补仓` → 5日收益 > 0
- `正常定投` → 5日收益 > -3%
- `暂停定投` → 5日收益 < 1%（成功避险）

验证结果自动展示在每日决策邮件中。

---

## 许可证

MIT License

---

## 致谢

- [DeepSeek](https://deepseek.com)
- [AkShare](https://github.com/akfamily/akshare)
