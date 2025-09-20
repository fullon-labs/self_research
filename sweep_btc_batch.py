import yaml
from bitcoinlib.wallets import Wallet
from bitcoinlib.keys import KeyError
import os

# 读取YAML配置文件
def load_config(file_path='config.yaml'):
    try:
        with open(file_path, 'r') as file:
            config = yaml.safe_load(file)
        return config
    except FileNotFoundError:
        print(f"配置文件 {file_path} 不存在")
        exit(1)
    except yaml.YAMLError as e:
        print(f"解析YAML文件失败: {e}")
        exit(1)

# 主程序
def main():
    # 加载配置
    config = load_config()
    private_keys = config.get('private_keys', [])
    target_address = config.get('target_address')
    network = config.get('network', 'bitcoin')  # 默认主网

    if not private_keys or len(private_keys) != 31:
        print(f"错误：配置文件必须包含31个私钥，当前找到 {len(private_keys)} 个")
        exit(1)
    if not target_address:
        print("错误：目标地址未提供")
        exit(1)

    # 创建临时钱包
    wallet_name = 'consolidation_wallet'
    try:
        w = Wallet.create(wallet_name, network=network)
    except Exception as e:
        print(f"钱包创建失败: {e}")
        exit(1)

    # 导入私钥
    imported_count = 0
    for pk in private_keys:
        try:
            w.import_key(pk)
            imported_count += 1
            print(f"成功导入私钥: {pk[:10]}...")
        except KeyError as e:
            print(f"导入私钥失败 {pk[:10]}...: {e}")
        except Exception as e:
            print(f"未知错误导入 {pk[:10]}...: {e}")

    print(f"总共导入 {imported_count} 个私钥。")

    # 更新UTXO
    try:
        w.utxos_update()
        utxos = w.utxos(min_confirms=0)
        total_sats = sum(utxo['value'] for utxo in utxos)
        print(f"找到 {len(utxos)} 个UTXO，总金额: {total_sats / 1e8} BTC")
    except Exception as e:
        print(f"UTXO更新失败: {e}")
        exit(1)

    if not utxos:
        print("没有可用的UTXO，无法转账。")
        exit(0)

    # 归集资金
    try:
        transaction = w.sweep(target_address, min_confirms=0, fee=None, broadcast=True)
        print(f"交易成功广播！TXID: {transaction.txid}")
        print(f"查看交易: https://blockchair.com/bitcoin/transaction/{transaction.txid}")
    except Exception as e:
        print(f"转账失败: {e}")
        print("尝试手动创建交易（不广播）以检查...")
        try:
            transaction = w.sweep(target_address, broadcast=False)
            transaction.sign()
            print(f"交易已签名但未广播，请手动广播: {transaction.raw_hex()}")
        except Exception as e:
            print(f"手动创建交易失败: {e}")

    # 可选：删除钱包
    # Wallet.delete(wallet_name)

if __name__ == "__main__":
    main()
