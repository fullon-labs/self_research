import yaml
from bitcoinlib.wallets import Wallet
from bitcoinlib.keys import BKeyError
import os

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

def create_wallet(wallet_name, network, private_keys):
    try:
        w = Wallet.create(wallet_name, network=network)
        imported_count = 0
        for pk in private_keys:
            try:
                w.import_key(pk)
                imported_count += 1
                print(f"[{network}] 成功导入私钥: {pk[:10]}...")
            except BKeyError as e:
                print(f"[{network}] 导入私钥失败 {pk[:10]}...: {e}")
            except Exception as e:
                print(f"[{network}] 未知错误导入 {pk[:10]}...: {e}")
        print(f"[{network}] 总共导入 {imported_count} 个私钥")
        return w
    except Exception as e:
        print(f"[{network}] 钱包创建失败: {e}")
        exit(1)

def get_available_amount(wallet, min_confirms=0):
    try:
        wallet.utxos_update()
        utxos = wallet.utxos(min_confirms=min_confirms)
        total_sats = sum(utxo['value'] for utxo in utxos)
        return total_sats / 1e8  # 转换为BTC/BCH单位
    except Exception as e:
        print(f"[{wallet.network}] UTXO更新失败: {e}")
        return 0

def main():
    # 加载配置
    config = load_config()
    private_keys = config.get('private_keys', [])
    targets = config.get('targets', {})
    amount = config.get('amount')  # 指定转账金额（BTC/BCH单位）

    if not private_keys or len(private_keys) != 31:
        print(f"错误：配置文件必须包含31个私钥，当前找到 {len(private_keys)} 个")
        exit(1)
    if 'bitcoin' not in targets or 'bitcoincash' not in targets:
        print("错误：必须提供BTC和BCH的目标地址")
        exit(1)

    # 创建BTC和BCH钱包
    btc_wallet = create_wallet('btc_wallet', 'bitcoin', private_keys)
    bch_wallet = create_wallet('bch_wallet', 'bitcoincash', private_keys)

    # 检查余额
    btc_balance = get_available_amount(btc_wallet)
    bch_balance = get_available_amount(bch_wallet)
    print(f"[BTC] 可用余额: {btc_balance:.8f} BTC")
    print(f"[BCH] 可用余额: {bch_balance:.8f} BCH")

    # 确定转账金额
    if amount is None:
        amount = min(btc_balance, bch_balance) * 0.9  # 取最小余额，留10%余地
        print(f"未指定金额，自动选择 {amount:.8f}（最小余额的90%）")
    elif amount > min(btc_balance, bch_balance):
        print(f"错误：指定金额 {amount} 超过最小余额 {min(btc_balance, bch_balance):.8f}")
        exit(1)

    # 执行转账
    for wallet, target in [(btc_wallet, targets['bitcoin']), (bch_wallet, targets['bitcoincash'])]:
        network = wallet.network
        target_address = target['address']
        try:
            # 创建交易，指定金额（转换为satoshis）
            transaction = wallet.send_to(target_address, int(amount * 1e8), fee=None, min_confirms=0, broadcast=True)
            print(f"[{network}] 交易成功广播！TXID: {transaction.txid}")
            print(f"[{network}] 查看交易: https://blockchair.com/{network}/transaction/{transaction.txid}")
        except Exception as e:
            print(f"[{network}] 转账失败: {e}")
            print(f"[{network}] 尝试手动创建交易（不广播）...")
            try:
                transaction = wallet.send_to(target_address, int(amount * 1e8), broadcast=False)
                transaction.sign()
                print(f"[{network}] 交易已签名但未广播，请手动广播: {transaction.raw_hex()}")
            except Exception as e:
                print(f"[{network}] 手动创建交易失败: {e}")

    # 可选：删除钱包
    # Wallet.delete('btc_wallet')
    # Wallet.delete('bch_wallet')

if __name__ == "__main__":
    main()
