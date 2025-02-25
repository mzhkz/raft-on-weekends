from VSS import split, combine, verify
from parameters import KEY_1024_PARAMS
from decimal import Decimal

# --- 以下は動作確認用の例 ---
if __name__ == "__main__":
    # ※以下は例としてのパラメータです。実際の暗号用途では十分大きな素数などを用いる必要があります。
    p = Decimal("23")         # 素数（コミットメント計算用）
    q = Decimal("19")         # シークレット分散用の素数（シークレットは q 未満である必要があります）
    generator = Decimal("5")  # p 未満の生成元

    secret = "0x7"  # "0x" で始まる 16 進数文字列としての秘密
    n = 5           # 発行するシェア数
    k = 3           # 秘密復元に必要なシェア数（しきい値）

    result = split(secret, n, k, p, q, generator)
    shares = result["D"]
    commitments = result["C"]

    print("Shares:")
    for share in shares:
        print(share)
    
    print("\nCommitments:")
    for commitment in commitments:
        print(commitment)

    # 最初の k 個のシェアから秘密を再構成
    recovered_secret = combine(shares[:k], q)
    print("\nRecovered Secret:", recovered_secret)

    # 最初のシェアの検証
    valid = verify(shares[0], commitments, p, generator, q)
    print("\nVerification of first share:", valid)