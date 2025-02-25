from decimal import Decimal, getcontext
import random

# TypeScript の Decimal.js での精度設定に対応（必要に応じて調整）
getcontext().prec = 10_000_000

def divmod_decimal(a, b, n):
    """
    拡張ユークリッド互除法を用いて (a * b^(-1)) mod n を計算する関数です。
    b の逆元が存在しない場合は 0 を返します。
    """
    a = Decimal(a)
    b = Decimal(b)
    n = Decimal(n)
    t = Decimal(0)
    nt = Decimal(1)
    r = n
    nr = b % n
    while nr != 0:
        quot = r // nr
        t, nt = nt, t - quot * nt
        r, nr = nr, r - quot * nr
    if r > 1:
        return Decimal(0)
    if t < 0:
        t = t + n
    return (a * t) % n

def expmod(x, n, mod):
    """
    二分累乗法を用いて (x ** n) mod mod を計算する関数です。
    """
    x = Decimal(x)
    n = Decimal(n)
    mod = Decimal(mod)
    ret = Decimal(1)
    while n > 0:
        if n % 2 != 0:
            ret = (ret * x) % mod
        x = (x * x) % mod
        n = n // 2
    return ret

def power(x, n):
    """
    二分累乗法による単純な累乗計算 (x ** n) を行う関数です。
    """
    x = Decimal(x)
    n = Decimal(n)
    ret = Decimal(1)
    while n > 0:
        if n % 2 != 0:
            ret = ret * x
        x = x * x
        n = n // 2
    return ret

def random_decimal(lower, upper):
    """
    lower 以上 upper 未満のランダムな整数（Decimal）を返します。
    """
    lower = Decimal(lower)
    upper = Decimal(upper)
    if lower > upper:
        lower, upper = upper, lower
    return Decimal(random.randrange(int(lower), int(upper)))

def polynomial(x, a, q):
    """
    係数リスト a を持つ多項式を、x において q で割った余りを返します。
    a[0] が秘密となり、残りはランダム係数です。
    """
    value = a[0]
    for i in range(1, len(a)):
        # x^i mod q を expmod で計算し、その後係数をかけたものを加算
        value = (value + expmod(x, Decimal(i), q) * a[i]) % q
    return value

def split(secret, total_shares, threshold, modulus_p, modulus_q, generator):
    """
    Feldman の VSS による秘密分散を行う関数
    
    Parameters:
      secret: 分散する秘密（整数または16進数文字列）
      total_shares: 生成するシェアの総数
      threshold: 復元に必要な最小シェア数
      modulus_p: コミットメント用の素数
      modulus_q: 秘密分散用の素数（秘密はこの値未満である必要あり）
      generator: 生成元の値
    """
    # 秘密を整数に変換
    if isinstance(secret, str) and secret.startswith("0x"):
        secret_int = Decimal(int(secret, 16))
    else:
        secret_int = Decimal(int(secret))
    
    if secret_int > modulus_q:
        raise ValueError(f"秘密の整数値({secret_int})は modulus_q({modulus_q}) より小さい必要があります")

    coefficients = [secret_int]
    shares_list = []
    commitments = [{"index": Decimal(0), "value": expmod(generator, secret_int, modulus_p)}]

    for i in range(1, threshold):
        random_coeff = random_decimal(Decimal(1), modulus_q - Decimal(1))
        coefficients.append(random_coeff)
        commitments.append({"index": Decimal(i), "value": expmod(generator, random_coeff, modulus_p)})

    for share_index in range(total_shares):
        x_value = Decimal(share_index + 1)
        share = {"x": x_value, "y": polynomial(x_value, coefficients, modulus_q)}
        shares_list.append(share)

    return {"shares": shares_list, "commitments": commitments}



def lagrange_basis(data, j, q):
    """
    シェアリスト data からインデックス j のシェアに対するラグランジュ基底多項式の
    分子と分母を計算します。
    """
    numerator = Decimal(1)
    denominator = Decimal(1)
    x_j = data[j]["x"]
    
    for i in range(len(data)):
        if i != j:  # 自分自身は除外
            x_i = data[i]["x"]
            numerator = (numerator * x_i) % q
            denominator = (denominator * (x_i - x_j)) % q
    
    return numerator, denominator

def lagrange_interpolate(data, q):
    """
    ラグランジュ補間を用いてシェアから秘密を再構成します。
    f(0) = ∑(y_j * ∏(x_i/(x_i-x_j))) を計算します。
    """
    secret = Decimal(0)
    
    for j in range(len(data)):
        num, den = lagrange_basis(data, j, q)
        # L_j(0) = ∏(x_i)/(∏(x_i-x_j))
        L_j_0 = divmod_decimal(num, den, q)
        term = (data[j]["y"] * L_j_0) % q
        secret = (secret + term) % q
    
    return secret

def combine(shares, modulus_q, return_string=True):
    """
    シェアから秘密を復元します。
    
    Parameters:
      shares: シェアのリスト
      modulus_q: 秘密分散で使用した素数
      return_string: 文字列として返すかどうか
                     (True の場合、元の秘密が 10 進数文字列であればその形に合わせて返します)
    """
    decimal_shares = [{"x": Decimal(share["x"]), "y": Decimal(share["y"])} for share in shares]
    recovered_secret_int = lagrange_interpolate(decimal_shares, modulus_q)
    
    if return_string:
        # 10進数文字列として返す（hex() ではなく単に文字列化する）
        return str(int(recovered_secret_int))
    else:
        return int(recovered_secret_int)

def verify(share, C, prime, generator, q):
    """
    与えられたシェアがコミットメント C と整合するか検証します。
    
    シェア (x, y) に対して、検証すべき等式は  
      g^y ≡ ∏_{i=0}^{k-1} (C_i)^(x^i mod q) (mod prime)
    となります。
    
    Parameters:
      share: {'x': Decimal, 'y': Decimal}
      C: コミットメントのリスト。各要素は {'index': Decimal, 'value': Decimal}
      prime: p（Decimal）
      generator: g（Decimal）
      q: シークレット分散で用いた素数（Decimal）
    """
    p = Decimal(prime)
    g = Decimal(generator)
    lG = expmod(g, share["y"], p)
    rG = Decimal(1)
    for i in range(len(C)):
        commitment = C[i]
        e = power(share["x"], Decimal(i)) % q
        basis = expmod(commitment["value"], e, p)
        rG = (rG * basis) % p
    return rG == lG

# --- 以下は動作確認用のテストコード ---
if __name__ == "__main__":
    from parameters import KEY_1024_PARAMS

    # 高精度計算のための設定（テスト用に精度を調整）
    getcontext().prec = 1000

    # 暗号パラメータの読み込み
    MODULUS_P = Decimal(KEY_1024_PARAMS["p"])
    MODULUS_Q = Decimal(KEY_1024_PARAMS["q"])
    GENERATOR = Decimal(KEY_1024_PARAMS["g"])

    # テスト設定
    TOTAL_SHARES = 5
    THRESHOLD = 3

    print("\n=== 秘密分散テスト ===")
    secret_int = "123"  # テスト用秘密（10進数として扱う）
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

    # 各シェアのコミットメント検証
    for i, share in enumerate(shares):
        valid = verify(share, commitments, MODULUS_P, GENERATOR, MODULUS_Q)
        print(f"シェア {i+1} の検証結果: {valid}")
