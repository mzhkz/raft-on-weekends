from VSS import split, combine, verify
from parameters import KEY_1024_PARAMS
from decimal import Decimal, getcontext

# 高精度計算のための設定
getcontext().prec = 1000

# --- 以下は動作確認用の例 ---
if __name__ == "__main__":
    # 暗号パラメータ
    MODULUS_P = Decimal(KEY_1024_PARAMS["p"])
    MODULUS_Q = Decimal(KEY_1024_PARAMS["q"])
    GENERATOR = Decimal(KEY_1024_PARAMS["g"])

    # テスト設定
    TOTAL_SHARES = 5
    THRESHOLD = 3

    print("\n=== 秘密分散テスト ===")
    # 小さい値でテスト
    secret_int = "123"
    print(f"元の秘密: {secret_int}")
    
    # 秘密を分散
    vss_result = split(secret_int, TOTAL_SHARES, THRESHOLD, MODULUS_P, MODULUS_Q, GENERATOR)
    shares = vss_result["shares"]
    commitments = vss_result["commitments"]

    print("\nShares:")
    for i, share in enumerate(shares):
        print(f"Share {i+1}: x={share['x']}, y={share['y']}")
    
    print("\nCommitments:")
    for i, commitment in enumerate(commitments):
        print(f"C_{i}: {commitment['value']}")

    # 最初の threshold 個のシェアから秘密を再構成
    test_shares = shares[:THRESHOLD]
    recovered_secret = combine(test_shares, MODULUS_Q, return_string=True)
    print(f"\n最初の{THRESHOLD}個のシェアから復元した秘密: {recovered_secret}")
    print(f"元の秘密と一致: {recovered_secret == secret_int}")

    # 別の threshold 個のシェアから秘密を再構成
    test_shares2 = [shares[0], shares[2], shares[4]]
    recovered_secret2 = combine(test_shares2, MODULUS_Q, return_string=True)
    print(f"\n別の{THRESHOLD}個のシェアから復元した秘密: {recovered_secret2}")
    print(f"元の秘密と一致: {recovered_secret2 == secret_int}")

    # シェアの検証
    for i, share in enumerate(shares):
        valid = verify(share, commitments, MODULUS_P, GENERATOR, MODULUS_Q)
        print(f"シェア {i+1} の検証結果: {valid}")