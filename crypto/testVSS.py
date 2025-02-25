from VSS import split, combine, verify
from parameters import KEY_1024_PARAMS
from decimal import Decimal

# --- 以下は動作確認用の例 ---
if __name__ == "__main__":
    # 暗号パラメータ
    MODULUS_P = KEY_1024_PARAMS["p"]
    MODULUS_Q = KEY_1024_PARAMS["q"]
    GENERATOR = KEY_1024_PARAMS["g"]

    # テスト設定
    TOTAL_SHARES = 5
    THRESHOLD = 3

    print("\n=== 16進数秘密テスト ===")
    hex_secret = "0x1d2b7"
    secret_int = int(hex_secret, 16)  # 16進数を整数に変換
    print(f"元の秘密（整数）: {secret_int}")
    print(f"元の秘密（16進数）: {hex(secret_int)}")
    
    # 整数値を渡す
    vss_result = split(secret_int, TOTAL_SHARES, THRESHOLD, MODULUS_P, MODULUS_Q, GENERATOR)
    shares = vss_result["shares"]
    commitments = vss_result["commitments"]

    print("Shares:")
    for share in shares:
        print(share)
    
    print("\nCommitments:")
    for commitment in commitments:
        print(commitment)

    # 最初の k 個のシェアから秘密を再構成
    recovered_secret = combine(shares[:THRESHOLD], MODULUS_Q, return_string=False)
    print("\nRecovered Secret (整数):", recovered_secret)
    print("Recovered Secret (16進数):", hex(recovered_secret))
    print("元の秘密と一致:", recovered_secret == secret_int)

    # 最初のシェアの検証
    valid = verify(shares[0], commitments, MODULUS_P, GENERATOR, MODULUS_Q)
    print("Verification of first share:", valid)