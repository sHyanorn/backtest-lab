# 任务清单

## M0 初始化
- [ ] 用 uv 初始化 Python 3.12 项目，配置 ruff、mypy 严格模式、pytest
- [ ] 包结构 `src/backtest_lab/{data,engine,strategies,validation,api}`
- [ ] CI：lint、类型检查、测试
- [ ] `.env.example`（FRED_API_KEY）

## M1 数据层
- [ ] 行情抓取（yfinance 或 Stooq），带重试和缓存
- [ ] FRED 宏观数据抓取
- [ ] Parquet 存储与 DuckDB 查询封装
- [ ] 数据质量检查并输出报告
- [ ] GitHub Actions 每周更新

## M2 回测引擎
- [ ] 向量化引擎：信号延后一日成交
- [ ] 交易成本与滑点
- [ ] 绩效指标，与现成库交叉验证
- [ ] 未来函数检测测试
- [ ] 四个示例策略

## M3 防过拟合方法
- [ ] 补全 METHODS.md
- [ ] 参数网格搜索（多进程），记录全部试验
- [ ] 样本内外切分与滚动前推检验
- [ ] 清洗加禁区 K 折
- [ ] 组合清洗交叉验证与 PBO
- [ ] 修正夏普比率、概率夏普比率、最低回测长度
- [ ] 参数敏感性分析
- [ ] 随机信号策略的对照测试
- [ ] 可信度报告生成（JSON）

## M4 API
- [ ] FastAPI 接口
- [ ] 参数搜索后台任务与进度查询
- [ ] 接口测试

## M5 看板
- [ ] Vite + React + TypeScript 初始化
- [ ] 策略选择与参数设置
- [ ] 净值与回撤图、热力图、可信度报告卡片
- [ ] 静态模式：读取预计算 JSON
- [ ] 部署到 GitHub Pages

## M6 展示
- [ ] 演示笔记本讲完核心故事
- [ ] 英文 README 与截图
- [ ] 整理 DECISIONS.md
