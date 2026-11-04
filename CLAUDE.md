# CLAUDE.md

本仓库是 Aaron 的作品集项目：一个专门检验策略是否过拟合的回测平台。核心卖点是统计严谨性，不是收益率。

## 开工前必读

1. `docs/SPEC.md`
2. `docs/TASKS.md`：从第一个未勾选的里程碑开始
3. `docs/DECISIONS.md`
4. `docs/METHODS.md`：每个统计方法的公式和参考文献，实现时必须与它一致

## 目录结构

```
src/backtest_lab/
  data/        数据抓取、清洗、存储
  engine/      回测引擎
  strategies/  示例策略
  validation/  防过拟合方法（项目重点）
  api/         FastAPI 服务
tests/
web/           React + TypeScript 看板
notebooks/     演示用 Jupyter 笔记本
```

## 工作方式

- 每个里程碑先出计划，等 Aaron 确认
- 一个任务一次提交，Conventional Commits 英文格式
- 完成后打勾，新决定写入 DECISIONS.md
- 实现统计方法时，在 METHODS.md 写公式、直观解释和论文出处

## 常用命令

```bash
uv sync
uv run pytest
uv run ruff check . && uv run mypy src
uv run python -m backtest_lab.data.update     # 更新数据
uv run uvicorn backtest_lab.api.main:app --reload
cd web && npm run dev
```

## 硬性规则

- 杜绝未来函数：信号在 t 日收盘后产生，最早在 t+1 日成交。引擎层强制执行，并有专门测试
- 所有随机过程固定随机种子
- 统计方法必须有单元测试，并用论文中的数值例子或已知结果验证
- 交易成本和滑点默认开启，不允许展示零成本结果作为主结论
- 原始行情数据不提交到仓库，只提交抓取脚本；演示用的预计算结果可以提交
- 函数要有类型标注，mypy 严格模式通过
