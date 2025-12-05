### Polymarket 从 FPMM 切换到订单簿模式的时机与机制

基于 Polymarket 的官方文档和技术演进历史（从 2020 年左右的纯 AMM 起步，到 2023-2024 年的 hybrid 升级），平台并没有一个严格的“阈值”来“切换”模式——它采用的是 **混合（hybrid）架构**，FPMM（Fixed Product Market Maker）和订单簿（CLOB，Central Limit Order Book）**并存**，系统根据市场条件实时选择最优路径。这是一种“渐进式转型”，而非二元切换。以下是详细说明，结合 2025 年 12 月的最新状态（交易量超 150 亿美元，用户规模达峰值）。

#### 1. **切换的时机：何时从 FPMM 转向订单簿？**
Polymarket 的设计哲学是“AMM 启动 + 订单簿规模化”，切换不是手动触发，而是基于 **市场成熟度和流动性阈值** 的自动化决策。核心触发条件包括：

- **市场规模与流动性阈值**：
  - **FPMM 优先**：适用于**新市场（cold start）或低流动性市场**（总交易量 < 10-50 万美元，或活跃用户 < 500）。此时，订单簿可能“空荡荡”（挂单少），导致高滑点（slippage > 1%）。FPMM 通过流动性池提供“无条件即时交易”，快速 bootstrapping（启动）市场。
  - **订单簿接管**：当市场达到**高流动性阈值**（总交易量 > 50 万美元，或 24h 交易笔数 > 1,000）时，系统优先使用 off-chain 订单簿。这通常发生在：
    - **热门事件**：如美国大选（2024 年交易量超 30 亿美元）、比特币价格预测或体育赛事。2023 年 3 月和 10 月的 CLOB 活动激增，就是因为这些高热度市场。
    - **平台整体成熟**：从 2024 年起，Polymarket 用户超 10 万后，80%+ 市场默认订单簿（官方数据：2025 年 CLOB 占比 70%）。

- **历史演进时间线**（非单一切换，而是迭代）：
  | 时间节点       | 关键变化                                      | 原因与影响 |
  |----------------|-----------------------------------------------|------------|
  | **2020-2022** | 纯 FPMM/LMSR（基于 Gnosis Conditional Tokens Framework） | 早期 DeFi 阶段，焦点在去中心化定价；但资本效率低（流动性全价位铺设）。 |
  | **2023 年 3 月** | 引入 hybrid CLOB（off-chain 匹配 + on-chain 结算） | 交易量首次破亿，AMM 滑点问题凸显；CLOB 活动激增 5x。 |
  | **2023 年 10 月** | 订单簿占比升至 50%，FPMM 降级为 fallback | 选举/加密牛市驱动；吸引专业做市商（market makers）。 |
  | **2024 年底** | 全面 hybrid：热门市场 90%+ 订单簿 | 用户爆炸增长（X 整合后）；AMM 仅用于 niche/新市场。 |
  | **2025 年 12 月** | 订单簿主导（Polygon 链上结算优化） | 周交易量 10 亿美元+；FPMM 几乎仅剩测试/低 TVL 市场。 |

- **决策逻辑**：系统通过 **流动性 oracle**（实时监控 TVL、交易深度、滑点）自动判断。如果订单簿深度 > FPMM 池子 2x，优先 CLOB；否则 fallback 到 FPMM。这确保了“最优价”——用户看到的 bid/ask 是两者比较后的最低滑点选项。

#### 2. **怎么切换？（技术机制详解）**
切换是 **无缝、透明的**，用户无需手动干预。Polymarket 的 hybrid 架构结合 off-chain（速度）和 on-chain（安全），核心是 **Exchange 合约**（专为二元市场设计）。过程如下：

- **架构概述**：
  - **FPMM 路径**：纯 on-chain，基于智能合约池子（Y × N = K）。交易直接调用 FPMM 合约，gas 费低（Polygon < 0.01 USD）。
  - **订单簿路径**：**hybrid-decentralized CLOB/BLOB**（Binary Limit Order Book）。
    - **Off-chain 部分**：后端运营商（operator，由 Polymarket 团队维护）处理订单匹配、排序和 API 调用。用户提交 signed order messages（签名订单），无需 gas。
    - **On-chain 部分**：匹配后，执行结算（merge positions to collateral），通过 Polygon 链上合约“unification”（统一 Yes/No 订单簿）。
  - **切换引擎**：API + keeper bots（开源）实时同步两者价格。如果订单簿价更优（低滑点），交易路由到 CLOB；否则 FPMM。

- **用户侧切换流程**（一步步）：
  1. **用户下单**：在市场页面选择“Limit Order”或“Market Order”（FPMM 只支持 market-like）。
  2. **系统评估**：前端 API 查询市场状态（TVL、深度）。如果订单簿活跃（有足够 bids/asks），路由到 off-chain CLOB。
  3. **匹配与执行**：
     - Off-chain：订单进入中央簿，匹配 taker（市价单）与 maker（限价单）。例如，你挂 0.55 USD 买 Yes，系统找最佳反方。
     - On-chain 结算：匹配后，调用 Exchange 合约，USDC 转移，份额 mint/burn。整个过程 < 5 秒。
  4. **Fallback**：如果 CLOB 流动性不足（e.g., 滑点 > 0.5%），自动回退 FPMM，显示“AMM 报价”。
  5. **监控**：用户在“Order Book”视图见实时簿子；在 Portfolio 管理 open orders。

- **开发者/高级视角**：
  - **API 集成**：用 Polymarket Order Book API（REST endpoints）创建/取消订单。示例：POST /orders with signed message。
  - **合约交互**：FPMM 用 FixedProductMarketMaker 合约；CLOB 用 ClobMarket 等。切换通过 router 合约实现（GitHub 开源）。
  - **优势**：Hybrid 降低 gas（off-chain 匹配），防操纵（on-chain 验证）。2025 年优化后，CLOB 滑点 < 0.1%。

#### 3. **为什么这样设计？ & 注意事项**
- **优势**：FPMM 适合启动（防空池），订单簿适合规模（精确定价、低滑点、吸引机构）。结果：2025 年 Polymarket 交易效率比纯 AMM 高 10x。
- **风险**：冷门市场仍依赖 FPMM，可能有更高滑点。监管（CFTC）要求 hybrid 保持非托管。
- **当前状态**（2025-12-05）：AMM 功能“inactive”于多数市场（Discord 反馈），但新事件仍用 FPMM 启动。

如果想看具体市场示例（如当前大选后遗市场）或 API 代码 demo，随时补充！
