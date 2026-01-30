# FundPilot-AI 基金智能定投决策系统

轻量级云端自动化辅助决策系统，在 A 股交易日通过量化指标 + DeepSeek AI 联合分析，推送定投操作建议。

## 快速开始

1. 复制配置文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 填入你的配置

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 运行：
```bash
python main.py
```

## 功能特性

- 🎯 **双策略体系**：ETF 联接基金网格交易 + 债券基金防守型策略
- 📊 **量化指标**：60 日分位值、均线偏离度、回撤幅度
- 🤖 **AI 决策**：DeepSeek 模型生成投资建议
- 📈 **可视化**：10+1 趋势图 + MA60 参考线
- 📧 **邮件通知**：HTML 格式决策报告

## 许可证

MIT
