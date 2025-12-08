### Polymarket 代码实现示例

以下是基于 Polymarket 开源仓库和文档的关键组件代码实现示例。这些示例聚焦于核心功能：**Conditional Tokens Framework (CTF) 的智能合约（Solidity）**、**minting 条件代币（TypeScript，使用 Ethers.js）** 和 **CLOB 订单放置（Python 客户端）**。代码来源于 GitHub 仓库（如 gnosis/conditional-tokens-contracts 和 Polymarket/py-clob-client），并添加注释以适应 Polymarket 上下文。注意：这些是简化示例，实际部署需审计和测试。运行环境：Hardhat for Solidity，Node.js for TS，Python 3.9+ for 客户端。

#### 1. **Solidity 示例：Conditional Tokens Framework (CTF) 核心函数**
Polymarket 使用 Gnosis 的 CTF 合约管理 Shares 的 mint/split/merge/redeem。以下是关键函数（从 `ConditionalTokens.sol` 提取），用于创建市场位置和处理 Shares。

```solidity
// SPDX-License-Identifier: LGPL-3.0-only
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import "./CTHelpers.sol";

contract ConditionalTokens is ERC1155 {
    mapping(bytes32 => uint[]) public payoutNumerators;
    mapping(bytes32 => uint) public payoutDenominator;
    mapping(address => bool) public fixedAmountMinting;

    // Prepares a condition for a market on Polymarket. Sets up the outcome slots
    // (e.g., "Yes"/"No" or multiple outcomes) before trading can begin.
    function prepareCondition(address oracle, bytes32 questionId, uint outcomeSlotCount) external {
        require(outcomeSlotCount <= 256, "too many outcome slots");
        require(outcomeSlotCount > 1, "there should be more than one outcome slot");
        bytes32 conditionId = CTHelpers.getConditionId(oracle, questionId, outcomeSlotCount);
        require(payoutNumerators[conditionId].length == 0, "condition already prepared");
        payoutNumerators[conditionId] = new uint[](outcomeSlotCount);
        emit ConditionPreparation(conditionId, oracle, questionId, outcomeSlotCount);
    }

    // Splits a position into smaller outcome-specific positions (e.g., split a Yes/No
    // position into pure Yes and pure No). Used by traders to adjust exposure.
    function splitPosition(
        IERC20 collateralToken,
        bytes32 parentCollectionId,
        bytes32 conditionId,
        uint[] calldata partition,
        uint amount
    ) external {
        require(partition.length > 1, "got empty or singleton partition");
        uint outcomeSlotCount = payoutNumerators[conditionId].length;
        require(outcomeSlotCount > 0, "condition not prepared yet");

        uint fullIndexSet = (1 << outcomeSlotCount) - 1;
        uint freeIndexSet = fullIndexSet;
        uint[] memory positionIds = new uint[](partition.length);
        uint[] memory amounts = new uint[](partition.length);
        for (uint i = 0; i < partition.length; i++) {
            uint indexSet = partition[i];
            require(indexSet > 0 && indexSet < fullIndexSet, "got invalid index set");
            require((indexSet & freeIndexSet) == indexSet, "partition not disjoint");
            freeIndexSet ^= indexSet;
            positionIds[i] = CTHelpers.getPositionId(collateralToken, CTHelpers.getCollectionId(parentCollectionId, conditionId, indexSet));
            amounts[i] = amount;
        }

        if (freeIndexSet == 0) {
            if (parentCollectionId == bytes32(0)) {
                require(collateralToken.transferFrom(msg.sender, address(this), amount), "could not receive collateral tokens");
            } else {
                _burn(
                    msg.sender,
                    CTHelpers.getPositionId(collateralToken, parentCollectionId),
                    amount
                );
            }
        } else {
            _burn(
                msg.sender,
                CTHelpers.getPositionId(collateralToken,
                    CTHelpers.getCollectionId(parentCollectionId, conditionId, fullIndexSet ^ freeIndexSet)),
                amount
            );
        }

        _batchMint(
            msg.sender,
            positionIds,
            amounts,
            ""
        );
        emit PositionSplit(msg.sender, collateralToken, parentCollectionId, conditionId, partition, amount);
    }

    // Merges multiple outcome-specific positions back into a single position.
    // Allows users to close out or consolidate their market exposure.
    function mergePositions(
        IERC20 collateralToken,
        bytes32 parentCollectionId,
        bytes32 conditionId,
        uint[] calldata partition,
        uint amount
    ) external {
        require(partition.length > 1, "got empty or singleton partition");
        uint outcomeSlotCount = payoutNumerators[conditionId].length;
        require(outcomeSlotCount > 0, "condition not prepared yet");

        uint fullIndexSet = (1 << outcomeSlotCount) - 1;
        uint freeIndexSet = fullIndexSet;
        uint[] memory positionIds = new uint[](partition.length);
        uint[] memory amounts = new uint[](partition.length);
        for (uint i = 0; i < partition.length; i++) {
            uint indexSet = partition[i];
            require(indexSet > 0 && indexSet < fullIndexSet, "got invalid index set");
            require((indexSet & freeIndexSet) == indexSet, "partition not disjoint");
            freeIndexSet ^= indexSet;
            positionIds[i] = CTHelpers.getPositionId(collateralToken, CTHelpers.getCollectionId(parentCollectionId, conditionId, indexSet));
            amounts[i] = amount;
        }
        _batchBurn(
            msg.sender,
            positionIds,
            amounts
        );

        if (freeIndexSet == 0) {
            if (parentCollectionId == bytes32(0)) {
                require(collateralToken.transfer(msg.sender, amount), "could not send collateral tokens");
            } else {
                _mint(
                    msg.sender,
                    CTHelpers.getPositionId(collateralToken, parentCollectionId),
                    amount,
                    ""
                );
            }
        } else {
            _mint(
                msg.sender,
                CTHelpers.getPositionId(collateralToken,
                    CTHelpers.getCollectionId(parentCollectionId, conditionId, fullIndexSet ^ freeIndexSet)),
                amount,
                ""
            );
        }

        emit PositionsMerge(msg.sender, collateralToken, parentCollectionId, conditionId, partition, amount);
    }

    // Redeems winning positions after the market resolves. Users provide index sets
    // (winning outcomes) and receive proportional payouts based on the reported result.
    function redeemPositions(IERC20 collateralToken, bytes32 parentCollectionId, bytes32 conditionId, uint[] calldata indexSets) external {
        uint den = payoutDenominator[conditionId];
        require(den > 0, "result for condition not received yet");
        uint outcomeSlotCount = payoutNumerators[conditionId].length;
        require(outcomeSlotCount > 0, "condition not prepared yet");

        uint totalPayout = 0;

        uint fullIndexSet = (1 << outcomeSlotCount) - 1;
        for (uint i = 0; i < indexSets.length; i++) {
            uint indexSet = indexSets[i];
            require(indexSet > 0 && indexSet < fullIndexSet, "got invalid index set");
            uint positionId = CTHelpers.getPositionId(collateralToken,
                CTHelpers.getCollectionId(parentCollectionId, conditionId, indexSet));

            uint payoutNumerator = 0;
            for (uint j = 0; j < outcomeSlotCount; j++) {
                if (indexSet & (1 << j) != 0) {
                    payoutNumerator = payoutNumerator.add(payoutNumerators[conditionId][j]);
                }
            }

            uint payoutStake = balanceOf(msg.sender, positionId);
            if (payoutStake > 0) {
                totalPayout = totalPayout.add(payoutStake.mul(payoutNumerator).div(den));
                _burn(msg.sender, positionId, payoutStake);
            }
        }

        if (totalPayout > 0) {
            if (parentCollectionId == bytes32(0)) {
                require(collateralToken.transfer(msg.sender, totalPayout), "could not transfer payout to message sender");
            } else {
                _mint(msg.sender, CTHelpers.getPositionId(collateralToken, parentCollectionId), totalPayout, "");
            }
        }
        emit PayoutRedemption(msg.sender, collateralToken, parentCollectionId, conditionId, indexSets, totalPayout);
    }
}
```

**使用说明**：部署到 Polygon 链。在 Polymarket 中，`prepareCondition` 用于创建市场（如二元 YES/NO），`splitPosition` 用于 mint Shares（注入 USDC 作为 collateral）。

#### 2. **TypeScript 示例：Minting 条件代币（使用 Ethers.js）**
基于 Polymarket/conditional-token-examples 仓库的 `mint.ts` 示例。用于 split collateral into YES/NO positions。

```typescript
import { ethers } from 'ethers';
import { ConditionalTokens, FixedProductMarketMaker } from '@gnosis.pm/conditional-tokens-contracts';

// ABI for ConditionalTokens (from artifacts)
const CT_ABI = [ /* Paste full ABI here from Hardhat */ ];
const FPMM_ABI = [ /* FixedProductMarketMaker ABI */ ];

// Provider and wallet setup (connect to Polygon)
const provider = new ethers.providers.JsonRpcProvider('https://polygon-rpc.com');
const wallet = new ethers.Wallet('YOUR_PRIVATE_KEY', provider);

// Contract addresses on Polygon (from Polymarket docs)
const CT_ADDRESS = '0xC59b870E47dd6E745E83E2D7fA1e0D59b5d4E4f3'; // Example CTF address
const FPMM_ADDRESS = '0x...'; // Market Maker address

async function mintPositions() {
  const ct = new ethers.Contract(CT_ADDRESS, CT_ABI, wallet);
  const fpmm = new ethers.Contract(FPMM_ADDRESS, FPMM_ABI, wallet);

  // Market details (e.g., for a binary market)
  const collateralToken = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'; // USDC on Polygon
  const parentCollectionId = ethers.constants.HashZero;
  const conditionId = '0x...'; // From prepareCondition
  const partition = [1, 2]; // [YES (0b01), NO (0b10)] for binary
  const amount = ethers.utils.parseEther('100'); // 100 USDC

  // Approve collateral to CT contract
  const usdc = new ethers.Contract(collateralToken, ['function approve(address,uint256)'], wallet);
  await usdc.approve(CT_ADDRESS, amount);

  // Split position (mint YES/NO shares)
  const tx = await ct.splitPosition(
    collateralToken,
    parentCollectionId,
    conditionId,
    partition,
    amount
  );
  await tx.wait();
  console.log('Minted positions:', tx.hash);

  // Optional: Add liquidity to FPMM (market maker)
  await fpmm.addLiquidity(collateralToken, parentCollectionId, conditionId, partition, amount, 0, 0);
}

mintPositions().catch(console.error);
```

**使用说明**：安装 `yarn add ethers @gnosis.pm/conditional-tokens-contracts`。运行 `ts-node mint.ts`。这 mint 100 USDC into 100 YES + 100 NO Shares。

#### 3. **Python 示例：CLOB 订单放置（使用 py-clob-client）**
基于 Polymarket/py-clob-client 仓库的示例，用于创建和放置 Limit Order。

```python
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.constants import BUY
import os

# Setup: Private key and host (from env vars)
private_key = os.getenv('PK')  # Your wallet private key
host = 'https://clob.polymarket.com'  # Mainnet CLOB endpoint
chain_id = 137  # Polygon

client = ClobClient(host, chain_id=chain_id, key=private_key)

# Market details (from /markets API)
token_id = '0x...'  # YES token ID for market
price = 0.55  # Price in USDC (0-1)
size = 10  # Number of shares

# Create order args
order_args = OrderArgs(
    token_id=token_id,
    price=price,
    size=size,
    side=BUY
)

# Place limit order (sign and submit)
signed_order = client.create_order(order_args)
order_id = client.post_order(signed_order)
print(f'Order placed: {order_id}')

# Optional: Cancel order
# client.cancel_order(order_id)
```

**使用说明**：安装 `pip install py-clob-client`。设置环境变量 `PK=your_private_key`。运行 `python place_order.py`。这放置一个买 10 YES Shares @ 0.55 的限价单。如果匹配互补 NO 订单，会触发 mint。

这些示例展示了 Polymarket 的混合架构：链上 CTF 处理 Shares，off-chain CLOB 处理订单。完整实现需集成 Relayer 和 Oracle。参考 [Polymarket Docs](https://docs.polymarket.com) 和 GitHub 仓库扩展。如果需测试特定代码或更多组件（如 WebSocket 实时数据），提供细节！
