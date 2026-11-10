# Statistical Methods

Each method lists the problem it solves, the formula, the intuition, references, where it lives in the code, and how it is tested. Implementations must match this document; any deviation goes into `DECISIONS.md` first.

## Conventions

- $r_t$, $t = 1, \dots, T$: daily simple returns of a strategy, **net of transaction costs and slippage**. Every metric and test below is computed on net returns.
- $A = 252$: trading days per year, used for all annualization.
- $\widehat{SR}$ without a subscript is the **non-annualized** (daily) Sharpe ratio $\bar r / s$, with $s$ the sample standard deviation (`ddof=1`). $\widehat{SR}_{\text{ann}} = \sqrt{A}\,\widehat{SR}$. PSR, MinTRL and DSR take the non-annualized value; MinBTL takes the annualized value.
- $\hat\gamma_3$: sample skewness; $\hat\gamma_4$: sample **raw** kurtosis (3 for a normal distribution, not excess kurtosis). Both are the population-moment estimators, i.e. `scipy.stats.skew(x)` and `scipy.stats.kurtosis(x, fisher=False)`.
- $Z$ is the standard normal CDF and $Z^{-1}$ its inverse; $\gamma \approx 0.5772156649$ is the Euler–Mascheroni constant.
- A *trial* is one parameter configuration of one strategy, backtested over the full sample. The parameter search records the daily net returns of every trial, giving a $T \times N$ matrix $X$ aligned on dates where all trials are live (after the longest warm-up). $N$ always counts recorded trials; $\hat N$ (Section 5) is the estimated number of independent trials. All statistics in Sections 4–6 that involve several trials are computed on the aligned rows of $X$.
- Degenerate series: a standard deviation (or downside deviation) below $10^{-12}$ is treated as zero, and any ratio with a zero denominator is NaN. In rankings, the trial-variance $\mathbb V$ and the sensitivity surface, a trial with NaN Sharpe counts as Sharpe 0 (it was tried, so it stays in $N$); pairs involving it are skipped when averaging correlations.
- Every random process takes an explicit seed; simulations use `numpy.random.default_rng(seed)` and draw the full $T \times N$ matrix with one `standard_normal((T, N))` call.
- Page numbers cited for the Bailey and López de Prado papers refer to the authors' SSRN versions listed in the references, not to journal pagination.

---

## 1. Performance metrics

**Problem.** One unambiguous definition per metric, so that results are reproducible and comparable with standard libraries.

**Formulas.** Wealth starts at $W_0 = 1$ and $W_t = \prod_{s \le t} (1 + r_s)$.

| Metric | Definition |
|---|---|
| Annualized return (CAGR) | $W_T^{A/T} - 1$; NaN if $W_T \le 0$ |
| Annualized volatility | $s \sqrt{A}$, with $s$ the sample std of $r_t$ (`ddof=1`) |
| Sharpe ratio | $\sqrt{A}\,\dfrac{\overline{r - r_f}}{s(r - r_f)}$, $r_f$ a daily rate, 0 by default |
| Downside deviation | $DD = \sqrt{A}\,\sqrt{\dfrac{1}{T}\sum_{t=1}^{T} \min(r_t - \tau, 0)^2}$, target $\tau = 0$ |
| Sortino ratio | $\dfrac{A\,\overline{(r - \tau)}}{DD}$ |
| Maximum drawdown | $MDD = \min_{t \ge 0} \left( \dfrac{W_t}{\max_{0 \le u \le t} W_u} - 1 \right) \le 0$ |
| Calmar ratio | $\dfrac{\text{CAGR}}{\lvert MDD \rvert}$; undefined (NaN) when $MDD = 0$ |

Details that are easy to get wrong:

- The downside deviation divides by $T$, the number of **all** observations, with non-negative excess returns contributing zero (Sortino & Price, 1994). Taking the standard deviation of only the negative returns is a different and incorrect quantity.
- The Sortino numerator is the annualized arithmetic mean excess return, not CAGR. This matches empyrical.
- Maximum drawdown is computed on compounded wealth of net returns, not on prices or on summed returns. $W_0 = 1$ is included as a peak, so a loss on the first day counts as a drawdown.
- $r_f = 0$ matches the engine, which credits uninvested cash with zero return. Every Sharpe ratio in the report uses this convention, so it measures total return per unit of risk, not excess return over Treasury bills; in periods of high short rates it overstates performance relative to cash. PSR, MinTRL and DSR inherit the same convention.
- Calmar uses the full sample, as in empyrical.
- Annualizing short samples extrapolates heavily: CAGR over a few weeks is not meaningful. The report's headline metrics require at least one year of data; walk-forward and cross-validation internals apply the same formulas to shorter windows.
- Degenerate cases return NaN (see Conventions), including Sortino when no return falls below the target. empyrical returns `inf` or a float-noise value in some of these cases; this is a deliberate difference.

**Intuition.** Sharpe measures return per unit of total risk; Sortino penalizes only returns below the target; maximum drawdown is the worst peak-to-trough loss an investor would have lived through; Calmar trades growth against that loss.

**References.** Sharpe (1994); Sortino & Price (1994). Implementation conventions follow empyrical-reloaded 0.7.2 (`annual_return`, `annual_volatility`, `sharpe_ratio`, `downside_risk`, `sortino_ratio`, `max_drawdown`, `calmar_ratio`), see D008.

**Code.** `src/backtest_lab/engine/metrics.py`

**Tests.** `tests/engine/test_metrics.py`

- Test vector: $r = (0.01, 0.10, -0.04, 0.02, 0.03, 0.02, 0.01, -0.10)$, $A = 252$, $r_f = \tau = 0$. Expected: $W_T = 1.0389310917$, CAGR $= 2.3302927973$, volatility $= 0.9136465400$, Sharpe $= 1.7238613962$, downside deviation $= 0.6044832504$, Sortino $= 2.6055312517$, $MDD = -0.10$, Calmar $= 23.302927973$. Volatility, Sharpe, downside deviation and Sortino equal the values in empyrical-reloaded's own test suite for its `mixed_returns` fixture (the same returns with a leading NaN); all seven match empyrical-reloaded 0.7.2 to 1e-10.
- First-day loss: $r = (-0.05, 0.02)$ gives $MDD = -0.05$.
- Constant returns $(0.01, \dots, 0.01)$: volatility 0, Sharpe and Sortino NaN, no division warning.
- Property test on random non-degenerate series (fixed seed): every metric equals empyrical-reloaded within 1e-10.

---

## 2. Holdout split and walk-forward analysis

### 2.1 Holdout split

**Problem.** The most basic check: choose parameters on the earlier part of the sample and see whether they keep working on the later part, which the choice never saw.

**Procedure.** Split the aligned rows of $X$ at $T_{IS} = \lfloor f T \rfloor$, default $f = 0.7$: $IS = [0, T_{IS})$, $OOS = [T_{IS}, T)$.

1. On $IS$, select $\theta^* = \arg\max_\theta \widehat{SR}_{IS}(\theta)$ (ties: first in grid order).
2. The OOS returns are rows $OOS$ of $\theta^*$'s full-sample backtest. The parameters do not change at the split, so no extra trading cost arises there.
3. Report the annualized IS and OOS Sharpe ratios of $\theta^*$ and the retention $\widehat{SR}_{OOS} / \widehat{SR}_{IS}$, given only when $\widehat{SR}_{IS} > 0$.

**Intuition.** A setting that captured real structure keeps a good part of its Sharpe ratio after the split; one that fit noise in the IS period falls toward zero.

**Pitfalls.**

- One cut gives one OOS path: the result depends on where the cut falls, and with $f = 0.7$ the OOS period is short relative to the sample.
- The OOS period can be used once. Revising the grid after looking at it turns it into IS data.
- The split ignores how many configurations were searched; Sections 4 and 5 address that.

**References.** A basic method with no single source; walk-forward analysis (Section 2.2) generalizes it to many cuts.

**Code.** `src/backtest_lab/validation/walk_forward.py`

**Tests.** `tests/validation/test_walk_forward.py`

- Boundaries: $T = 10$, $f = 0.7$ gives $IS = [0, 7)$ and $OOS = [7, 10)$.
- No look-ahead: changing OOS rows of $X$ leaves $\theta^*$ unchanged.
- Synthetic planted edge (fixed seed): $\theta^*$ is the configuration with the drift and its OOS Sharpe is positive.
- Random signals (fixed seed): the OOS annualized Sharpe of $\theta^*$ is within two standard errors of zero, $SE \approx \sqrt{A/n}$ for $n$ OOS days.

### 2.2 Walk-forward analysis

**Problem.** A single in-sample/out-of-sample split uses one arbitrary cut. Walk-forward analysis re-optimizes on a moving window and trades the chosen parameters on the next, unseen window, which is how the strategy would actually be run.

**Procedure.** Given in-sample length $L_{IS}$ and out-of-sample length $L_{OOS}$ (in trading days), window $k = 0, 1, \dots$ uses

$$
IS_k = [\,s_k,\; e_k), \qquad OOS_k = [\,e_k,\; e_k + L_{OOS}), \qquad e_k = L_{IS} + k L_{OOS},
$$

with $s_k = e_k - L_{IS}$ for a rolling window and $s_k = 0$ for an anchored window. Windows stop when $OOS_k$ would run past $T$; the incomplete tail is dropped.

1. On $IS_k$, select $\theta_k^* = \arg\max_\theta \widehat{SR}_{IS_k}(\theta)$ (ties: first in grid order). IS returns are the rows $IS_k$ of $X$, i.e. slices of each trial's full-sample backtest, so indicators are warmed up and no entry cost is charged at $s_k$.
2. Build one position series by taking the positions of $\theta_k^*$ on $OOS_k$ for every $k$, and run it through the engine once. Indicators may use any prices before the OOS window (they are in the past), and parameter switches at window boundaries pay trading costs.
3. Compute Section 1 metrics on the resulting OOS return series.

Walk-forward efficiency compares annualized rates of return, after Pardo (2008). Both sides use the arithmetic rate $A\,\bar r$, so compounding does not bias the ratio:

$$
WFE = \frac{A\,\bar r_{OOS}}{\frac{1}{K}\sum_{k=1}^{K} A\,\bar r_{IS_k}(\theta_k^*)},
$$

where $\bar r_{OOS}$ is the mean of the whole OOS series and $K$ the number of windows. The report also shows IS and OOS Sharpe per window.

**Intuition.** If the optimizer finds real structure, parameters chosen on the past keep working on the next period and WFE is high. If it fits noise, OOS performance collapses toward zero no matter how good each IS optimum looks.

**Pitfalls.**

- No extra purge is needed for daily returns with daily rebalancing. With $e$ the first OOS row, the last IS return and the first OOS return share the target set at close $e - 2$, which is fixed before the selection at close $e - 1$ and leaks nothing (see D036).
- WFE is unstable when IS returns are near zero or negative; it is reported only when the mean IS annualized return is positive.
- Walk-forward is itself a single path through history: its OOS sample is small and it does not account for how many configurations were searched. Sections 4 and 5 address that.

**References.** Pardo (2008), Ch. 11 (walk-forward analysis, pp. 237–261; walk-forward efficiency, pp. 238–239, 254, 260–261). The book text was not available; the WFE definition follows its common statement as the ratio of annualized OOS to IS rates of return.

**Code.** `src/backtest_lab/validation/walk_forward.py`

**Tests.** `tests/validation/test_walk_forward.py`

- Window boundaries, $T = 10$, $L_{IS} = 4$, $L_{OOS} = 2$. Rolling: IS $[0,4), [2,6), [4,8)$ with OOS $[4,6), [6,8), [8,10)$. Anchored: IS $[0,4), [0,6), [0,8)$ with the same OOS windows.
- Invariants: OOS windows are disjoint and contiguous, and no IS window overlaps its own OOS window.
- No look-ahead: changing prices after the end of $OOS_k$ leaves $\theta_0^*, \dots, \theta_k^*$ and the OOS returns up to $OOS_k$ unchanged.
- Synthetic planted edge (fixed seed): a grid where one configuration has a positive drift and the rest are noise; walk-forward selects it in most windows and OOS Sharpe is positive.
- Random signals (fixed seed): OOS annualized Sharpe of the OOS series is within two standard errors of zero, with $SE \approx \sqrt{A/n}$ for $n$ OOS days (Section 6, Eq. 8 at $SR = 0$).

---

## 3. Purged and embargoed K-fold cross-validation

**Problem.** Standard K-fold assumes independent observations. In finance an observation's outcome spans time, and features use trailing windows, so training observations adjacent to a test fold carry information about it. That leaks test information into training and inflates CV scores.

**Definitions.** Observation $i$ has an information interval $[t_{0,i}, t_{1,i}]$ in trading days: $t_{0,i}$ is the first close of its return interval and $t_{1,i}$ is the last date whose price enters its return. The engine's daily return of row $t$ spans close $t - 1$ to close $t$, so $t_{1,i} - t_{0,i} = 1$; the implementation reads that span from the engine's constant `INFORMATION_SPAN`, which a test pins, and does not derive it from engine settings. The target set at close $t - 2$, which earns the overnight leg of the same return, is a feature of the observation, like a trailing indicator window, and the embargo is what covers features (see D036).

The data are split into $K$ contiguous folds without shuffling (sizes as in `numpy.array_split`). For a test fold with $t_0^{\min} = \min_{i \in \text{test}} t_{0,i}$ and $t_1^{\max} = \max_{i \in \text{test}} t_{1,i}$, a non-test observation $j$ stays in the training set only if

$$
t_{1,j} < t_0^{\min} \qquad \text{or} \qquad t_{0,j} > t_1^{\max} + h,
$$

where $h$ is the embargo length in trading days. The first condition is **purging**: it removes training observations whose intervals overlap the test fold. The second adds the **embargo**: it also drops the $h$ observations right after the test fold, whose trailing features were computed from test-period data. The embargo applies only after the test fold, since information flows forward in time.

Default $h = \lceil 0.01\,T \rceil$. The size follows the suggestion $h \approx 0.01T$ in López de Prado (2018, Ch. 7); rounding up, so that any positive fraction gives at least one day, is a project choice (the book's code truncates). For strategies with long indicator windows a conservative setting is $h$ equal to the longest lookback.

**Use in this project.** In each fold, select $\theta^* = \arg\max_\theta \widehat{SR}_{\text{train}}(\theta)$ on the purged training set, then record its Sharpe on the test fold. The CV score is the mean test-fold Sharpe; the test folds together cover every observation exactly once.

**Intuition.** Purging deletes training points that saw part of the test answer; the embargo adds a buffer for the slower leaks through serial correlation and trailing features.

**Pitfalls.**

- Intervals are closed: an observation whose interval ends exactly at the test start overlaps it and is purged.
- With an embargo, the training set after a test fold starts at $t_1^{\max} + h + 1$, not at the end of the test fold.
- Shuffling the folds breaks the method.

**References.** López de Prado (2018), Ch. 7. The book text was not available for direct checking. The overlap rule uses closed intervals, as in the book's training-set purge (Snippet 7.1), and matches `CombPurgedKFoldCV(n_test_splits=1)` in `timeseriescv` 0.2 (MIT licence), whose embargo is a time span instead of a day count. The book's `PurgedKFold` class (Snippet 7.3) treats the fold endpoints as half-open and would keep observations 3 and 7 in the hand example below; the closed-interval rule here is deliberately more conservative.

**Code.** `src/backtest_lab/validation/purged_kfold.py`

**Tests.** `tests/validation/test_purged_kfold.py`

- Hand example: $T = 10$, $K = 5$, $t_{0,i} = i$, $t_{1,i} = i + 1$, $h = 1$. For test fold $\{4, 5\}$: $t_0^{\min} = 4$, $t_1^{\max} = 6$. Training set $= \{0, 1, 2, 8, 9\}$; 3 and 6 are purged and 7 is embargoed.
- With $h = 0$ and $t_{1,i} = t_{0,i}$, the split reduces to ordinary unshuffled K-fold.
- Invariants on random intervals (fixed seed): no training interval intersects $[t_0^{\min}, t_1^{\max}]$; no training $t_0$ lies in $(t_1^{\max}, t_1^{\max} + h]$; test folds partition the index.

---

## 4. Combinatorially symmetric cross-validation (CSCV) and the probability of backtest overfitting (PBO)

**Problem.** After trying $N$ configurations and picking the best in-sample, how likely is it that the pick is worse than the median configuration out of sample? That probability is the PBO. It measures the selection process, not one strategy.

**Definition.** PBO is the probability that the configuration with the best IS performance ranks below the median OOS (Bailey et al., 2017, Definition 2.2).

**CSCV procedure** (Bailey et al., 2017, Algorithm 2.3):

1. Take the $T \times N$ trial-return matrix $X$. Drop the earliest $T \bmod S$ rows and split the rest into $S$ contiguous blocks of equal length ($S$ even; default $S = 16$).
2. For each of the $\binom{S}{S/2}$ ways to choose $S/2$ blocks: the chosen blocks, joined in time order, form the IS set $J$; the other blocks form the OOS set $\bar J$.
3. Compute the performance vectors $R^c$ on $J$ and $\bar R^c$ on $\bar J$ (non-annualized Sharpe of each column).
4. $n^* = \arg\max_n R^c_n$ (ties: lowest column index). Let $\bar r^c_{n^*}$ be the rank of $\bar R^c_{n^*}$ among $\bar R^c$, ascending from 1 (worst) to $N$ (best), ties averaged.
5. Relative rank and logit:

$$
\bar\omega_c = \frac{\bar r^c_{n^*}}{N + 1}, \qquad \lambda_c = \ln \frac{\bar\omega_c}{1 - \bar\omega_c}.
$$

6. PBO is the share of combinations with a non-positive logit:

$$
\widehat{PBO} = \frac{1}{\binom{S}{S/2}} \sum_{c} \mathbf{1}[\lambda_c \le 0].
$$

$\lambda_c = 0$ means the pick ranks exactly at the median (odd $N$, or ties under averaged ranks). It counts as overfit, following the estimator $\int_{-\infty}^{0} f(\lambda)\,d\lambda$ of Section 3.1; the paper's Definition 2.2 is written with $\bar r < N/2$, which leaves this point out and, for even $N$, also the rank $N/2$ ($\lambda = \ln(N/(N+2)) < 0$) that the estimator counts (see D035). Under the null (no skill, no ties) the expected PBO is therefore $0.5$ for even $N$ and $(N+1)/(2N)$ for odd $N$.

The report also includes two by-products from Section 3.2 of the paper: the OLS slope of $\bar R^c_{n^*}$ on $R^c_{n^*}$ across combinations (performance degradation) and the probability of OOS loss, $\Pr[\bar R^c_{n^*} < 0]$. The slope is descriptive only: IS and OOS are complementary halves of one fixed series, so the slope tends to be negative even when the selection has real skill (it was between $-0.8$ and $-0.1$ in the planted-edge runs below, all with PBO under 0.1).

**Intuition.** Every half of the history takes a turn as the training set and its complement as the test set. If picking the IS winner carries real information, the winner keeps ranking in the top half OOS and logits are mostly positive. If the search only fits noise, the OOS rank of the winner is uniform, logits follow roughly a logistic distribution centred on 0, and PBO is near 0.5.

**Pitfalls.**

- $N$ is every configuration tried, including the bad ones. The paper (Section 5.2) warns that hiding trials underestimates overfitting and that adding trials doomed to fail, to make one configuration succeed, biases the result as well. The direction depends on which trials are left out: in the demo the long/short half of each grid is the weaker one, and dropping it raises PBO from 0.05 to 0.42 for the moving average (DEMO.md, post hoc). A PBO verdict therefore depends on the composition of the grid, not only on the selected configuration.
- Small $N$ makes ranks coarse; the paper notes that an investor sensitive to PBO values below 1/10 needs $N \gg 10$. The report gives PBO no verdict when fewer than 10 trials are effectively independent (Section 5, D041).
- PBO evaluates a selection process. It must not be used as the objective to choose a strategy.
- A high PBO does not mean every configuration is bad: if all configurations have similar real skill, PBO is high too.
- Sharpe ratios on unions of blocks can be computed exactly from per-block counts, sums and sums of squares, so all $\binom{16}{8}$ combinations are cheap.

**Naming.** The PBO paper's estimator is CSCV, which is what is implemented here. Combinatorial purged cross-validation (CPCV, López de Prado 2018, Ch. 12) is a different method that builds multiple backtest paths for one model; it is not in scope. CSCV does not purge: the trial returns are computed once on the full sample with fixed parameters, so selection on $J$ sees $\bar J$ only near block edges, through serial correlation of returns and through trailing indicator windows that straddle an edge. With $S = 16$ the blocks are $T/16$ days long, at least a year whenever the sample covers 16 years or more, so this edge effect is small next to the block length; the paper's procedure is kept unchanged.

**References.** Bailey, Borwein, López de Prado & Zhu (2017).

**Code.** `src/backtest_lab/validation/pbo.py`

**Tests.** `tests/validation/test_pbo.py`

- Ranking example from Section 2.1 of the paper: $R = (0.5, 1.1, 0.7)$ gives ranks $(1, 3, 2)$; $\bar R = (0.6, 0.7, 1.3)$ gives ranks $(1, 2, 3)$. So $n^* = 2$, $\bar\omega = 2/4$, $\lambda = 0$.
- Number of combinations, Eq. (2.3): $S = 12 \to 924$, $S = 16 \to 12{,}870$, $S = 24 \to 2{,}704{,}156$. (The paper's text prints 12,780 for $S = 16$; $\binom{16}{8} = 12{,}870$.)
- Constructed extremes, $N = 3$, $S = 2$, two blocks of two rows, column $n$ in a block equal to $(a_n, a_n + 0.02)$ so all columns share one standard deviation:
  - Persistent: $a = (0.01, 0.02, 0.03)$ in both blocks. Both combinations pick column 3, which ranks 3 OOS: $\lambda = \ln 3$, PBO $= 0$.
  - Reversed: $a = (0.01, 0.02, 0.03)$ in block 1 and $(0.03, 0.02, 0.01)$ in block 2. Each IS winner ranks 1 OOS: $\lambda = -\ln 3$, PBO $= 1$.
- Random-signal control (SPEC Section 8): $X = 0.01 \cdot$ `default_rng(seed).standard_normal((1000, 100))`, $S = 16$. With $N = 100$ (even) the expected PBO is 0.5. A single seed is noisy (PBO ranged from about 0.23 to 0.87 over seeds 0–19), so the test averages seeds 0–99 and requires the mean within $[0.42, 0.58]$. Observed means: 0.47 for seeds 0–99 and 0.50 for seeds 100–199, per-seed standard deviation about 0.14–0.16.
- Planted edge: the same $X$ plus `numpy.linspace(0, 0.002, 100)` added to every row (column $n$ gets a daily drift rising linearly from 0 to 0.002). For seeds 0–9 PBO was between 0.016 and 0.070; the test requires PBO $< 0.1$ for each of these seeds.

---

## 5. Deflated Sharpe ratio (DSR)

**Problem.** The best of $N$ backtests has an inflated Sharpe ratio even when every strategy has zero skill, and non-normal returns inflate it further. DSR asks whether the selected Sharpe ratio is significant after correcting for both.

**Formulas.** Expected maximum of $N$ independent Sharpe estimates with true value zero (Bailey & López de Prado, 2014, Eq. 1, with $\mathbb E[\{\widehat{SR}_n\}] = 0$):

$$
\widehat{SR}_0 = \sqrt{\mathbb V[\{\widehat{SR}_n\}]}\;\max(e_{\hat N}, 0), \qquad
e_N = (1-\gamma)\, Z^{-1}\!\left[1 - \frac{1}{N}\right] + \gamma\, Z^{-1}\!\left[1 - \frac{1}{N e}\right]
$$

The approximation is derived for $N \gg 1$. $e_N$ turns negative for $N < 1.2836$ and tends to $-\infty$ as $N \to 1$, so it is clipped at 0; this keeps $\widehat{SR}_0$ continuous in $\hat N$ and makes DSR equal $\widehat{PSR}(0)$ when there is effectively one trial.

Deflated Sharpe ratio (Eq. 2), the PSR of Section 6 evaluated at the threshold $\widehat{SR}_0$:

$$
\widehat{DSR} = Z\!\left[ \frac{(\widehat{SR} - \widehat{SR}_0)\sqrt{T - 1}}{\sqrt{1 - \hat\gamma_3 \widehat{SR} + \frac{\hat\gamma_4 - 1}{4}\widehat{SR}^2}} \right]
$$

Inputs:

- $\widehat{SR}$, $\hat\gamma_3$, $\hat\gamma_4$, $T$: non-annualized Sharpe, skewness, raw kurtosis and length of the selected trial's returns.
- $\mathbb V[\{\widehat{SR}_n\}]$: sample variance (`ddof=1`) of the non-annualized Sharpe ratios of **all** recorded trials.
- $\hat N$: number of **independent** trials. Grid trials are strongly correlated, so $\hat N$ is estimated from the $N$ recorded trials in two ways, and the larger estimate is used (D041). The first is the average-correlation rule of Appendix A.3 (Eq. 8–9; the paper writes $M$ for recorded and $N$ for independent trials):

$$
\hat\rho = \frac{2}{N(N-1)} \sum_{i<j} \rho_{ij}, \qquad \hat N_\rho = \hat\rho + (1 - \hat\rho) N,
$$

where $\rho_{ij}$ is the correlation of the daily returns of trials $i$ and $j$. $\hat\rho$ is clipped to $[0, 1]$, so $1 \le \hat N_\rho \le N$.

The second is the eigenvalue estimate of Nyholt (2004), with $\lambda_1, \dots, \lambda_N$ the eigenvalues of the correlation matrix $(\rho_{ij})$:

$$
\hat N_\lambda = 1 + (N - 1)\left(1 - \frac{\mathbb V[\lambda]}{N}\right), \qquad \mathbb V[\lambda] = \frac{1}{N-1} \sum_{i=1}^{N} (\lambda_i - 1)^2 .
$$

Uncorrelated trials have every $\lambda_i = 1$ and $\hat N_\lambda = N$; identical trials have $\lambda = (N, 0, \dots, 0)$, $\mathbb V[\lambda] = N$ and $\hat N_\lambda = 1$. Because $\sum_i \lambda_i^2 = \sum_{i,j} \rho_{ij}^2$, the ratio $\mathbb V[\lambda] / N$ is the mean squared pairwise correlation $\overline{\rho^2}$, so $\hat N_\lambda = \overline{\rho^2} + (1 - \overline{\rho^2}) N$: the same rule with squared correlations, which is how the code computes it. A negative correlation lowers $\hat N_\lambda$ and raises $\hat N_\rho$.

$\hat N = \max(\hat N_\rho, \hat N_\lambda)$ enters $\widehat{SR}_0$ here and MinBTL in Section 6; the larger count gives the higher threshold and the lower DSR. When $\min(\hat N_\rho, \hat N_\lambda) < 10$, with $N$ counting only the trials whose returns vary, the report gives DSR and PBO no verdict (D041).

The report flags the strategy as significant when $\widehat{DSR} \ge 0.95$.

**Intuition.** $\widehat{SR}_0$ is the Sharpe ratio you would expect from the luckiest of $N$ skill-less strategies. DSR is the probability that the true Sharpe ratio of the selected strategy beats that bar, with a wider error band for short, negatively skewed or fat-tailed samples.

**Pitfalls.**

- Every input is at the return frequency. Annualized Sharpe ratios or an annualized $\mathbb V$ give wrong answers; the paper's example converts an annual variance of $1/2$ to daily by dividing by the observations per year.
- $\hat\gamma_4$ is raw kurtosis. `scipy.stats.kurtosis` and `pandas.Series.kurt` return excess kurtosis by default; using those makes the term under the square root too small by $\frac{3}{4}\widehat{SR}^2$.
- The denominator uses the selected $\widehat{SR}$, not $\widehat{SR}_0$.
- Using $N$ instead of $\hat N$ overstates the threshold; using only the trials of the final grid when earlier grids were also run on the same data understates it. All trials ever run on the data count.
- Both estimates of $\hat N$ are crude: correlation is only linear dependence, and the correlation matrix is ill-conditioned when $T < N(N-1)/2$ (Appendix A.3). The paper points to dimension reduction or information-theoretic estimates as alternatives.
- The variance formula assumes iid returns; serial correlation (Lo, 2002) is not corrected.

**References.** Bailey & López de Prado (2014); Bailey & López de Prado (2012) for the PSR it builds on; Nyholt (2004) for $\hat N_\lambda$.

**Code.** `src/backtest_lab/validation/sharpe_stats.py` (`expected_max_sharpe`, `average_correlation`, `mean_squared_correlation`, `effective_trials`, `deflated_sharpe_ratio`)

**Tests.** `tests/validation/test_sharpe_stats.py`

- Paper example (pp. 9–10): $N = 100$, $\mathbb V = \frac{1}{2 \cdot 250}$, $T = 1250$, $\widehat{SR} = 2.5/\sqrt{250}$, $\hat\gamma_3 = -3$, $\hat\gamma_4 = 10$. Expected $\widehat{SR}_0 = 0.1132$ and $\widehat{DSR} = 0.9004$. Also from the same page: $N = 46$ gives $0.9505$; normal returns ($\hat\gamma_3 = 0$, $\hat\gamma_4 = 3$) with $N = 88$ give $0.9505$. Reproduced: 0.113172, 0.900397, 0.950502, 0.950491. Tolerance 1e-4. Note that this example uses 250 observations per year, not 252.
- $\hat N$: $\hat\rho = 0 \to \hat N = N$; $\hat\rho = 1 \to \hat N = 1$; $N = 100$, $\hat\rho = 0.5 \to \hat N = 50.5$.
- $\hat N_\lambda$: the mean squared correlation reproduces the eigenvalue formula on a random correlation matrix; two independent pairs of identical trials have $\lambda = (2, 2, 0, 0)$, $\mathbb V[\lambda] = 4/3$ and $\hat N_\lambda = 3$, above the true 2.
- Clipping: $e_{1.1} = -0.318 \to \widehat{SR}_0 = 0$; $e_2 = 0.5198$.
- Random-signal control (SPEC Section 8): $X$ as in the PBO control ($T = 1000$, $N = 100$), select the highest Sharpe, use $\hat N = N$ (the trials are independent by construction). Over 200 seeds, DSR of the selected trial was never $\ge 0.95$ (mean 0.49), while $\widehat{PSR}(0)$ was $\ge 0.95$ in all 200. The test runs 50 seeds and requires DSR $< 0.95$ in at least 48 and $\widehat{PSR}(0) \ge 0.95$ in at least 48.
- Sanity check, not a validation of the approximation: the mean annualized Sharpe of the selected trial over those 200 seeds was 1.271 (standard error 0.016), consistent with both the formula's $\sqrt{252/1000} \times 2.5306 = 1.2704$ and the exact expected maximum of 100 standard normals, which gives 1.259.

---

## 6. Probabilistic Sharpe ratio (PSR), minimum track record length (MinTRL) and minimum backtest length (MinBTL)

**Problem.** A Sharpe estimate has sampling error that grows with short samples, negative skew and fat tails. PSR is the probability that the true Sharpe exceeds a benchmark $SR^*$. MinTRL is the sample length needed for that probability to reach $1 - \alpha$. MinBTL asks how long a backtest must be before trying $N$ configurations stops producing a good-looking Sharpe ratio by chance.

**Formulas.** Asymptotic distribution of the Sharpe estimator under iid non-normal returns (Bailey & López de Prado, 2012, Eq. 8, who attribute it to a 2002 working paper by Mertens and note that Opdyke (2007) showed it coincides with Christie's (2005) result for stationary ergodic returns):

$$
\widehat{SR} \overset{a}{\sim} \mathcal N\!\left( SR,\; \frac{1 + \frac12 SR^2 - \gamma_3 SR + \frac{\gamma_4 - 3}{4} SR^2}{n} \right)
$$

Since $\frac12 + \frac{\gamma_4 - 3}{4} = \frac{\gamma_4 - 1}{4}$, this gives (Eq. 11, with $n$ the number of returns):

$$
\widehat{PSR}(SR^*) = Z\!\left[ \frac{(\widehat{SR} - SR^*)\sqrt{n - 1}}{\sqrt{1 - \hat\gamma_3 \widehat{SR} + \frac{\hat\gamma_4 - 1}{4}\widehat{SR}^2}} \right]
$$

Minimum track record length in observations (Eq. 13), with one-sided $Z_\alpha = Z^{-1}(1 - \alpha)$:

$$
MinTRL = 1 + \left( 1 - \hat\gamma_3 \widehat{SR} + \frac{\hat\gamma_4 - 1}{4}\widehat{SR}^2 \right) \left( \frac{Z_\alpha}{\widehat{SR} - SR^*} \right)^2
$$

MinTRL is defined only for $\widehat{SR} > SR^*$. Divide by $A$ for years.

Minimum backtest length in years (Bailey, Borwein, López de Prado & Zhu, 2014, Theorem 3.1). If $N$ independent zero-skill configurations each have an annualized Sharpe estimator with standard deviation about $y^{-1/2}$ after $y$ years, the expected best IS annualized Sharpe is $E[\max_N] \approx y^{-1/2}\, e_N$ with

$$
e_N = (1-\gamma)\, Z^{-1}\!\left[1 - \frac1N\right] + \gamma\, Z^{-1}\!\left[1 - \frac{1}{N e}\right],
$$

so the backtest length at which that expected best equals a target $\overline{E[\max_N]}$ is

$$
MinBTL \approx \left( \frac{e_N}{\overline{E[\max_N]}} \right)^2 < \frac{2 \ln N}{\overline{E[\max_N]}^2}.
$$

As in Section 5, $e_N$ is clipped at 0, so MinBTL is 0 when $\hat N < 1.2836$.

The report computes MinBTL with $N = \hat N$ from Section 5 and the target set to the selected trial's annualized Sharpe, and compares it with the actual sample length in years.

**Intuition.** PSR replaces a point estimate with a probability of skill; it rises with a longer record and positive skew and falls with fat tails. MinTRL inverts PSR to say how much data a given Sharpe needs. MinBTL turns the multiple-testing problem into a data requirement: with five years of data, trying more than about 45 independent configurations already makes an IS annualized Sharpe of 1 expected from pure noise.

**Pitfalls.**

- $\widehat{SR}$ and $SR^*$ are non-annualized and at the same frequency as the returns. MinBTL is the exception: it takes an annualized target and returns years.
- Raw kurtosis, as in Section 5.
- The formulas rely on the central limit theorem; the paper advises at least 30 observations and computing the moments on longer samples when possible.
- $e_N$ is a large-$N$ approximation. For $N = 10$ it gives 1.575, while the exact expected maximum of 10 standard normals is 1.539.
- MinBTL is a necessary condition, not a sufficient one: a backtest longer than MinBTL can still be overfit.
- MinTRL comes from the 2012 Journal of Risk paper; MinBTL comes from the 2014 Notices of the AMS paper.

**References.** Bailey & López de Prado (2012); Bailey, Borwein, López de Prado & Zhu (2014); Lo (2002) for the iid caveat.

**Code.** `src/backtest_lab/validation/sharpe_stats.py` (`probabilistic_sharpe_ratio`, `min_track_record_length`, `min_backtest_length`)

**Tests.** `tests/validation/test_sharpe_stats.py`

- PSR, 2012 paper p. 10: monthly track record, $n = 24$, $\widehat{SR} = 0.458$, $SR^* = 0$. Normal moments ($\hat\gamma_3 = 0$, $\hat\gamma_4 = 3$): 0.982. With $\hat\gamma_3 = -2.448$, $\hat\gamma_4 = 10.164$: 0.913. Same moments with $n = 36$: 0.953. Reproduced: 0.98167, 0.91336, 0.95351. Tolerance 1e-3.
- MinTRL, 2012 paper p. 11, $\alpha = 0.05$, annualized $\widehat{SR} = 2$ against $SR^* = 1$, normal returns: daily 2.73 years, weekly 2.83, monthly 3.24; monthly with $\hat\gamma_3 = -0.72$, $\hat\gamma_4 = 5.78$: 4.99. Reproduced with 252, 52 and 12 periods per year: 2.7310, 2.8288, 3.2398, 4.9913. Tolerance 0.01 years.
- MinBTL, 2014 paper p. 11: $N = 45$, target 1 gives $MinBTL = 4.998$ years (the paper's "5 years"); the upper bound $2\ln 45 = 7.613$ exceeds it.
- $e_N$, 2014 paper p. 9: $N = 10$ gives 1.5746 (the paper's 1.57).
- Consistency: $\widehat{DSR}$ with $\hat N = 1$ equals $\widehat{PSR}(0)$; $\widehat{PSR}(SR^*)$ at $n = MinTRL$ equals $1 - \alpha$.

---

## 7. Parameter sensitivity

**Problem.** An optimum on an isolated peak of the parameter surface is likely noise; an optimum on a broad plateau is more likely to persist. The check measures how much performance holds up around the chosen parameters.

**Definition.** Parameters lie on a grid indexed by integer coordinates $\mathbf i = (i_1, \dots, i_d)$, and $P(\mathbf i)$ is the annualized net Sharpe ratio of that configuration over the full sample. Let $\mathbf i^* = \arg\max P$ (ties: first in row-major grid order). The neighbourhood of radius $\rho$ (default 1) is

$$
\mathcal N_\rho = \{\, \mathbf i \ne \mathbf i^* : \max_k \lvert i_k - i^*_k \rvert \le \rho \,\},
$$

clipped at the grid edges ($3^d - 1$ points in the interior, fewer at edges). The report gives

$$
m = \frac{1}{\lvert \mathcal N_\rho \rvert} \sum_{\mathbf i \in \mathcal N_\rho} P(\mathbf i), \qquad
s = \sqrt{\frac{1}{\lvert \mathcal N_\rho \rvert} \sum_{\mathbf i \in \mathcal N_\rho} \big(P(\mathbf i) - m\big)^2}, \qquad
\text{retention} = \frac{m}{P(\mathbf i^*)}.
$$

$s$ uses the population form because the neighbourhood is the whole set of interest, not a sample. Retention is reported only when $P(\mathbf i^*) > 0$.

**Heatmap.** For two chosen parameters, plot $P$ over their grid with every other parameter fixed at its value in $\mathbf i^*$, and outline $\mathbf i^*$ and $\mathcal N_\rho$.

**Intuition.** Retention near 1 with small $s$ means neighbouring settings perform about as well, so the result does not hinge on one exact parameter value. Retention near 0 or a large $s$ means the optimum is a spike.

**Pitfalls.**

- This is a descriptive diagnostic with no sampling distribution; it complements PBO and DSR and does not replace them.
- Grid spacing matters: a neighbourhood on a very coarse grid is not local, and on a very fine grid it is trivially smooth. Spacing is fixed per strategy in its parameter definition.
- Categorical parameters have no neighbours: they stay fixed at their values in $\mathbf i^*$ and the neighbourhood moves only along ordered parameters.

**References.** No single source defines this statistic; it is a project convention. Pardo (2008) discusses the related idea of preferring robust parameter regions over isolated optima.

**Code.** `src/backtest_lab/validation/sensitivity.py`

**Tests.** `tests/validation/test_sensitivity.py`

- Constant surface $P \equiv 1$ on a $5 \times 5$ grid: $\mathbf i^* = (0, 0)$ by the tie rule, $\lvert \mathcal N_1 \rvert = 3$, $s = 0$, retention $= 1$.
- Spike: $5 \times 5$ grid with $P = 1$ at $(2, 2)$ and 0 elsewhere: $\lvert \mathcal N_1 \rvert = 8$, $m = 0$, retention $= 0$.
- Corner optimum on a 2-D grid: $\lvert \mathcal N_1 \rvert = 3$; on a 3-D grid: 7.
- Linear surface $P(i, j) = i + j$ on a $5 \times 5$ grid: $\mathbf i^* = (4, 4)$, neighbours $\{(3,3), (3,4), (4,3)\}$, $m = 20/3$, retention $= 5/6$.

---

## References

1. Bailey, D. H., & López de Prado, M. (2012). The Sharpe ratio efficient frontier. *Journal of Risk*, 15(2), 3–44. https://doi.org/10.21314/JOR.2012.255. SSRN 1821643.
2. Bailey, D. H., & López de Prado, M. (2014). The deflated Sharpe ratio: Correcting for selection bias, backtest overfitting, and non-normality. *Journal of Portfolio Management*, 40(5), 94–107. https://doi.org/10.3905/jpm.2014.40.5.094. SSRN 2460551.
3. Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014). Pseudo-mathematics and financial charlatanism: The effects of backtest overfitting on out-of-sample performance. *Notices of the American Mathematical Society*, 61(5), 458–471. https://doi.org/10.1090/noti1105. SSRN 2308659.
4. Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2017). The probability of backtest overfitting. *Journal of Computational Finance*, 20(4), 39–69. https://doi.org/10.21314/JCF.2016.322. SSRN 2326253.
5. Lo, A. W. (2002). The statistics of Sharpe ratios. *Financial Analysts Journal*, 58(4), 36–52. https://doi.org/10.2469/faj.v58.n4.2453.
6. López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. ISBN 978-1-119-48208-6.
7. Nyholt, D. R. (2004). A simple correction for multiple testing for single-nucleotide polymorphisms in linkage disequilibrium with each other. *American Journal of Human Genetics*, 74(4), 765–769. https://doi.org/10.1086/383251.
8. Pardo, R. (2008). *The Evaluation and Optimization of Trading Strategies* (2nd ed.). Wiley. ISBN 978-0-470-12801-5. https://doi.org/10.1002/9781119196969.
9. Sharpe, W. F. (1994). The Sharpe ratio. *Journal of Portfolio Management*, 21(1), 49–58. https://doi.org/10.3905/jpm.1994.409501.
10. Sortino, F. A., & Price, L. N. (1994). Performance measurement in a downside risk framework. *Journal of Investing*, 3(3), 59–64. https://doi.org/10.3905/joi.3.3.59.
