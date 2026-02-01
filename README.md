# FundPilot-AI 基金智能定投决策系统 (v4.1)

<p align="center">
  <b>量化策略 + AI 深度推理的双轨制智能投顾系统</b><br>
  结合传统量化指标与 DeepSeek V3 大模型，生成专业的"类研报"级定投决策
</p>

---

## ✨ 核心特性

| 特性 | 说明 |
|-----|-----|
| **🧠 双轨决策引擎** | **量化模型**（捕捉周期/分位）+ **AI 专家**（宏观与深度逻辑）双重验证 |
| **⚖️ 智能合成仲裁** | 当策略与 AI 产生分歧时，基于资产属性自动计算权重，生成最优决策 |
| **🛡️ 逻辑全透明** | "白盒化" 决策过程，完整展示分歧处理逻辑（Synthesis Reasoning） |
| **📊 专业研报 UI** | v4.1 全新设计的"分析师报告"风格邮件，全中文界面，含"决策总览"表 |
| **📈 多周期分位** | 60/250/500 日分位交叉验证，避免短期锚定偏误 |
| **⚡️ 动态风控** | 针对不同资产（黄金/红利/固收+）自动匹配不同的波动率阈值 |
| **🚨 双重触达** | 12:30 盘中异动预警 + 14:45 最终决策报告 |

---

## 📁 项目结构

```
fund_pilot/
├── core/             # 核心配置与日志
├── data/             # 多源数据采集（AkShare/Sina）
├── strategy/         # 量化策略引擎
│   ├── indicators.py # 核心指标计算
│   ├── decision_synthesizer.py # 决策合成器 (Core Logic)
│   └── ...           # 各类资产（ETF/债）具体策略
├── ai/               # AI 智能体模块
│   ├── deepseek_client.py # DeepSeek V3 接入
│   └── specialized_prompts.py # 资产专用 Prompt 库
├── notification/     # 消息触达
│   └── email_template.py # v4.1 专业研报模板
├── scheduler/        # 任务调度中心
└── main.py           # 启动入口
```

---

## 🚀 决策流程

该系统采用独特的 **"双轨并行 + 动态合成"** 架构：

1.  **量化感知 (Track A)**: 
    *   计算估值分位、均线偏离、波动率。
    *   基于硬规则生成基础信号 (Buy/Sell/Hold)。
2.  **AI 深度思考 (Track B)**: 
    *   DeepSeek V3 读取包含持仓结构、市场情绪的完整上下文。
    *   输出包含宏观逻辑的深度建议 (Reasoning)。
3.  **智能合成 (Synthesis)**:
    *   **一致性加成**: 两者观点一致 -> 提升置信度。
    *   **分歧仲裁**: 
        *   黄金/周期品 -> 策略主导 (避免 AI 追涨杀跌)。
        *   主动权益 ->  AI 权重提升 (通过持仓穿透分析)。
    *   **极端分歧**: 自动触发"观望"保护机制。

---

## 🚀 快速开始

### 1. 环境准备
```bash
git clone <your-repo-url> fund_pilot
cd fund_pilot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 (`.env`)
```bash
cp .env.example .env
```
编辑 `.env` 填入 DeepSeek API Key 与邮箱配置：
```env
DEEPSEEK_API_KEY=sk-xxxxxx
SMTP_USER=your_email@163.com
SMTP_PASSWORD=xxxxxx
```

### 3. 运行
```bash
# 启动常驻进程（自动根据交易日运行）
python main.py
```

---

## 🧪 调试与测试

由于系统严格遵循 A 股交易时间（仅交易日 14:45 运行），开发调试时可强制触发：

```bash
# 强制运行一次完整决策流程
export FUND_PILOT_FORCE_RUN=true
python -c "from scheduler.jobs import run_decision_task; run_decision_task()"
```

---

## 🔧 常见配置

### 资产类型映射
系统会自动识别基金名称，也可在 `core/config.py` 强制指定 `asset_class`:

*   `GOLD_ETF`: 黄金/贵金属 (高波动阈值，看跌幅)
*   `BOND_PURE` / `BOND_ENHANCED`: 纯债/固收+ (均线保护，看回撤)
*   `COMMODITY_CYCLE`: 有色/资源 (分位值主导)

---

## 📜 许可证

MIT License

---

## 🙏 致谢

- [DeepSeek](https://deepseek.com)
- [AkShare](https://github.com/akfamily/akshare)
