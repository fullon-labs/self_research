from bitcoinlib.wallets import Wallet
from bitcoinlib.keys import KeyError  # 用于错误处理

# 您的31个WIF私钥列表（替换为实际值）
private_keys = [
    '5Jxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',  # 示例WIF私钥1
    'Kwxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',     # 示例WIF私钥2
    # ... 添加剩余29个私钥
    # 总共31个
]

# 目标地址（替换为您的地址）
target_address = '1YourTargetBitcoinAddressHere'

# 创建一个新钱包（单签名，非多签名）
wallet_name = 'consolidation_wallet'
try:
    w = Wallet.create(wallet_name, network='bitcoin')  # 主网比特币
except Exception as e:
    print(f"钱包创建失败: {e}")
    exit(1)

# 导入每个私钥到钱包
imported_count = 0
for pk in private_keys:
    try:
        w.import_key(pk)
        imported_count += 1
        print(f"成功导入私钥: {pk[:10]}...")  # 只打印前10字符以保护隐私
    except KeyError as e:
        print(f"导入私钥失败 {pk[:10]}...: {e}")
    except Exception as e:
        print(f"未知错误导入 {pk[:10]}...: {e}")

print(f"总共导入 {imported_count} 个私钥。")

# 更新并扫描UTXO（从区块链服务提供商获取）
try:
    w.utxos_update()  # 更新UTXO列表
    utxos = w.utxos(min_confirms=0)  # 获取所有UTXO，包括未确认的
    total_sats = sum(utxo['value'] for utxo in utxos)
    print(f"找到 {len(utxos)} 个UTXO，总金额: {total_sats / 1e8} BTC")
except Exception as e:
    print(f"UTXO更新失败: {e}")
    exit(1)

if not utxos:
    print("没有可用的UTXO，无法转账。")
    exit(0)

# 归集资金到目标地址（sweep操作会自动计算手续费）
try:
    transaction = w.sweep(target_address, min_confirms=0, fee=None, broadcast=True)  # broadcast=True 直接广播
    print(f"交易成功广播！TXID: {transaction.txid}")
    print(f"查看交易: https://blockchair.com/bitcoin/transaction/{transaction.txid}")
except Exception as e:
    print(f"转账失败: {e}")
    # 如果失败，可以设置broadcast=False，先创建交易，然后手动签名/广播
    # transaction = w.sweep(target_address, broadcast=False)
    # transaction.sign()
    # transaction.send()

# 可选：删除钱包以清理（生产环境中谨慎）
# Wallet.delete(wallet_name)
