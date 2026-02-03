# FundPilot-AI 基金智能定投决策系统 (v5.5)

<p align="center">
  <b>量化策略 + AI 深度推理的双轨制智能投顾系统</b><br>
  结合多周期分位估值与 DeepSeek V3 大模型，生成专业投资决策报告<br>
  <b>新增：T+1/T+5 双轨回测验证系统</b>
</p>

---

## 核心特性

| 特性 | 说明 |
|-----|-----|
| **双轨决策引擎** | 量化模型（分位/均线/波动率）+ AI 专家（持仓穿透/宏观逻辑）双重验证 |
| **智能合成仲裁** | 基于资产属性动态计算权重，策略与 AI 分歧时自动生成最优决策 |
| **双轨回测验证** | **T+1 方向验证**（验证短期择时准确性） + **T+5 收益验证**（验证中期定投收益） |
| **多周期分位** | 60/250/500 日估值分位交叉验证，识别真假低估 |
| **动态风控** | 针对黄金/周期/固收+等不同资产自动匹配波动率阈值与熔断机制 |
| **专业邮件报告** | 暗色主题、5列表格回测展示、置信度百分比、结构化 AI 分析 |

---

## 项目结构

```
fund_pilot/
├── ai/               # AI 决策模块
│   ├── ai_decision.py         # AI 决策主逻辑
│   ├── deepseek_client.py     # DeepSeek V3 API
│   ├── specialized_prompts.py # 资产专用 Prompt
│   └── prompt_builder.py      # 上下文构建器
├── strategy/         # 量化策略引擎
│   ├── decision_synthesizer.py # 双轨决策合成器
│   ├── etf_strategy.py        # ETF/黄金/周期策略
│   ├── bond_strategy.py       # 债券/固收+策略
│   └── indicators.py          # 技术指标计算
├── data/             # 数据采集
│   ├── fund_history.py        # 历史净值 (AkShare)
│   ├── fund_valuation.py      # 实时估值
│   ├── holdings.py            # 持仓穿透
│   └── market.py              # 大盘行情
├── notification/     # 邮件通知
│   ├── email_template.py      # 决策报告模板 (v5.5)
│   └── alert_template.py      # 盘中快报模板
├── scheduler/        # 任务调度
│   ├── jobs.py                # 定时任务 (决策/预警)
│   ├── validation_job.py      # 回测验证任务 (T+1/T+5)
│   └── calendar.py            # 交易日历
├── core/             # 核心配置
├── visualization/    # 图表生成
└── main.py           # 启动入口
```

---

## 决策与验证流程

```
┌─────────────────────────────────────────────────────────┐
│                    FundPilot 闭环系统                    │
├─────────────────────────────────────────────────────────┤
│  1. 数据采集    净值/估值/持仓/大盘                       │
│       ↓                                                  │
│  2. 双轨决策    量化策略(资产感知) + AI推理(DeepSeek)      │
│       ↓                                                  │
│  3. 决策合成    一致性检测 → 权重计算 → 最终决策           │
│       ↓                                                  │
│  4. 执行检查    倍数一致性校验 (定投/双倍/暂停)            │
│       ↓                                                  │
│  5. 报告生成    邮件推送 (含回测数据表格)                  │
│       ↓                                                  │
│  6. 效果验证    每日 T+1 方向校验 / 每周 T+5 收益校验       │
│       └───→ 反馈至数据库 (Decision Log)                   │
└─────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 1. 环境准备
```bash
git clone <your-repo-url> fund_pilot
cd fund_pilot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置
```bash
cp .env.example .env
```

编辑 `.env`：
```env
DEEPSEEK_API_KEY=sk-xxxxxx
SMTP_USER=your_email@163.com
SMTP_PASSWORD=xxxxxx
EMAIL_TO=recipient@example.com
```

### 3. 运行
```bash
# 启动常驻进程（自动按交易日运行）
python main.py
```

---

## Linux 部署 (systemd)

### 1. 上传项目
```bash
scp -r fund_pilot user@your-server:/opt/
```

### 2. 服务器配置
```bash
cd /opt/fund_pilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入配置
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
WorkingDirectory=/opt/fund_pilot
Environment="PATH=/opt/fund_pilot/.venv/bin"
ExecStart=/opt/fund_pilot/.venv/bin/python main.py
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
tail -f logs/fundpilot.log        # 查看日志文件 (推荐)
```

---

## 调试命令

```bash
# 强制运行决策任务
FUND_PILOT_FORCE_RUN=true python -c "
from scheduler import calendar
calendar.is_trading_day = lambda d=None: True
calendar.should_run_task = lambda d=None: True
from scheduler.jobs import run_decision_task
run_decision_task()
"

# 强制运行盘中快报
FUND_PILOT_FORCE_RUN=true python -c "
from scheduler import calendar
calendar.is_trading_day = lambda d=None: True
calendar.should_run_task = lambda d=None: True
from scheduler.jobs import run_alert_task
run_alert_task()
"
```

---

## 双轨回测系统

系统内置了自动化的效果验证机制，无需人工干预。

### 1. T+1 方向验证
- **目标**: 验证决策对次日涨跌判断的准确性。
- **逻辑**:
  - `双倍补仓`: 次日上涨 = 正确
  - `暂停定投`: 次日下跌 = 正确
  - `正常定投`: 次日上涨或微跌(>-1%) = 正确

### 2. T+5 收益验证
- **目标**: 验证决策执行 5 个交易日后的实际收益表现。
- **逻辑**:
  - `双倍补仓`: 5日累计收益 > 0
  - `正常定投`: 5日累计收益 > -3% (优于大盘或由于定投平摊成本)
  - `暂停定投`: 5日累计收益 < 1% (成功避险)

所有验证结果会自动展示在每日的决策邮件中。

---

## 资产类型支持

| 类型 | 代码 | 策略特点 | AI 权重 |
|-----|------|---------|--------|
| **黄金避险** | `GOLD_ETF` | 关注避险属性，高估不一定暂停 | 60% (策略主导) |
| **周期资源** | `COMMODITY_CYCLE` | 逆向思维，分批建仓，宽阈值 | 50% (均衡) |
| **固收+** | `BOND_ENHANCED` | 关注股债平衡，熔断敏感 | 40% (AI辅助) |
| **纯债** | `BOND_PURE` | 极低波动，严格估值纪律 | 30% (AI辅助) |

---

## 许可证

MIT License

---

## 致谢

- [DeepSeek](https://deepseek.com)
- [AkShare](https://github.com/akfamily/akshare)
