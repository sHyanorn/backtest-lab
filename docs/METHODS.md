# 统计方法说明

每个方法包含：要解决的问题、公式、直观解释、参考文献、实现位置、测试方式。

下面是需要覆盖的条目和参考文献。

## 1. 绩效指标
年化收益、年化波动、夏普、索提诺、最大回撤、卡玛。注明年化因子 252。

## 2. 滚动前推检验
参考：Pardo, R. (2008). *The Evaluation and Optimization of Trading Strategies* (2nd ed.). Wiley.

## 3. 清洗加禁区 K 折交叉验证
参考：López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. 第 7 章。

## 4. 组合清洗交叉验证与过拟合概率 PBO
参考：Bailey, D. H., Borwein, J., López de Prado, M., & Zhu, Q. J. (2017). The probability of backtest overfitting. *Journal of Computational Finance*, 20(4), 39–69.

## 5. 修正夏普比率 DSR
参考：Bailey, D. H., & López de Prado, M. (2014). The deflated Sharpe ratio: Correcting for selection bias, backtest overfitting, and non-normality. *Journal of Portfolio Management*, 40(5), 94–107.

## 6. 概率夏普比率与最低回测长度
参考：Bailey, D. H., & López de Prado, M. (2012). The Sharpe ratio efficient frontier. *Journal of Risk*, 15(2), 3–44.

## 7. 参数敏感性
方法：最优参数邻域内表现的均值与离散程度，热力图展示。

注意：实现前请核对以上文献的卷期页码。
