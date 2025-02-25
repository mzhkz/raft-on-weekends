import random

def extended_gcd(a, b):
    """
    拡張ユークリッドの互除法により、gcd(a,b) と係数 x, y を返します。
    すなわち、g = gcd(a,b) かつ a*x + b*y = g となる。
    """
    if b == 0:
        return a, 1, 0
    else:
        g, x, y = extended_gcd(b, a % b)
        return g, y, x - (a // b) * y

def mod_div(a, b, n):
    """
    (a * b^(-1)) mod n を計算する関数です。
    もし b の逆元が存在しなければ 0 を返します。
    """
    g, x, _ = extended_gcd(b, n)
    if g != 1:
        return 0
    else:
        inv_b = x % n
        return (a * inv_b) % n

def expmod(x, n, mod):
    """
    二分累乗法による (x^n) mod mod の計算です。
    """
    return pow(x, n, mod)

def power(x, n):
    """
    二分累乗法による単純な累乗計算 (x^n) です。
    """
    return pow(x, n)

def random_int(lower, upper):
    """
    lower 以上 upper 未満のランダムな整数を返します。
    """
    return random.randrange(lower, upper)

def polynomial(x, coefficients, q):
    """
    係数リスト coefficients を持つ多項式を評価し、q で割った余りを返します。
    coefficients[0] が秘密で、残りはランダムな係数となります。
    """
    value = coefficients[0]
    for i in range(1, len(coefficients)):
        value = (value + expmod(x, i, q) * coefficients[i]) % q
    return value

def split(secret, total_shares, threshold, modulus_p, modulus_q, generator):
    """
    Feldman の VSS による秘密分散を行います。
    
    Parameters:
      secret: 分散する秘密（整数または "0x" で始まる16進数文字列）
      total_shares: 生成するシェアの総数
      threshold: 復元に必要な最小シェア数
      modulus_p: コミットメント用の素数
      modulus_q: 秘密分散用の素数（秘密はこの値未満でなければなりません）
      generator: コミットメント生成用の生成元 g
    """
    # 秘密を整数に変換
    if isinstance(secret, str) and secret.startswith("0x"):
        secret_int = int(secret, 16)
    else:
        secret_int = int(secret)
    
    if secret_int >= modulus_q:
        raise ValueError(f"秘密 {secret_int} は modulus_q {modulus_q} 未満である必要があります")
    
    coefficients = [secret_int]
    commitments = [{"index": 0, "value": expmod(generator, secret_int, modulus_p)}]
    
    for i in range(1, threshold):
        random_coeff = random_int(1, modulus_q)
        coefficients.append(random_coeff)
        commitments.append({"index": i, "value": expmod(generator, random_coeff, modulus_p)})
    
    shares_list = []
    for share_index in range(total_shares):
        x_value = share_index + 1
        y_value = polynomial(x_value, coefficients, modulus_q)
        shares_list.append({"x": x_value, "y": y_value})
    
    return {"shares": shares_list, "commitments": commitments}

def lagrange_basis(data, j, q):
    """
    シェアリスト data からインデックス j のシェアに対する
    ラグランジュ基底多項式の分子と分母を計算します。
    """
    numerator = 1
    denominator = 1
    x_j = data[j]["x"]
    for i in range(len(data)):
        if i != j:
            x_i = data[i]["x"]
            numerator = (numerator * x_i) % q
            denominator = (denominator * (x_i - x_j)) % q
    return numerator, denominator

def lagrange_interpolate(data, q):
    """
    ラグランジュ補間を用いてシェアから秘密を再構成します。
    f(0) = ∑ (y_j * L_j(0)) mod q を計算します。
    """
    secret = 0
    for j in range(len(data)):
        num, den = lagrange_basis(data, j, q)
        L_j0 = mod_div(num, den, q)
        term = (data[j]["y"] * L_j0) % q
        secret = (secret + term) % q
    return secret

def combine(shares, modulus_q, return_string=True):
    """
    シェアから秘密を復元します。
    
    Parameters:
      shares: シェアのリスト（各シェアは {'x': int, 'y': int} の形式）
      modulus_q: 秘密分散に用いた素数
      return_string: True の場合は文字列として、False の場合は整数として返します。
    """
    recovered_secret = lagrange_interpolate(shares, modulus_q)
    if return_string:
        return str(recovered_secret)
    else:
        return recovered_secret

def verify(share, commitments, prime, generator, q):
    """
    与えられたシェアがコミットメントと整合しているかを検証します。
    
    シェア (x, y) に対して検証すべき等式は  
      g^y ≡ ∏_{i=0}^{k-1} (C_i)^(x^i mod q) (mod prime)
    となります。
    """
    p = prime
    g = generator
    left = expmod(g, share["y"], p)
    right = 1
    for i in range(len(commitments)):
        exponent = pow(share["x"], i, q)  # x^i mod q
        term = expmod(commitments[i]["value"], exponent, p)
        right = (right * term) % p
    return left == right

if __name__ == "__main__":
    from parameters import KEY_2048_PARAMS

    # パラメータを整数に変換
    MODULUS_P = int(KEY_2048_PARAMS["p"])
    MODULUS_Q = int(KEY_2048_PARAMS["q"])
    GENERATOR = int(KEY_2048_PARAMS["g"])
    
    TOTAL_SHARES = 5
    THRESHOLD = 3
    
    print("\n=== 秘密分散テスト ===")
    secret = "hello sfc! student~!!!"  # テスト用の秘密
    secret_int = int(secret.encode('ascii').hex(), 16)
    print(f"元の秘密: {secret_int}")
    
    # 秘密を分散
    vss_result = split(secret_int, TOTAL_SHARES, THRESHOLD, MODULUS_P, MODULUS_Q, GENERATOR)
    shares = vss_result["shares"]
    commitments = vss_result["commitments"]
    
    print("\nShares:")
    for i, share in enumerate(shares):
        print(f"Share {i+1}: x={share['x']}, y={share['y']}")
    
    print("\nCommitments:")
    for i, commit in enumerate(commitments):
        print(f"C_{i}: {commit['value']}")
    
    # 最初の threshold 個のシェアから秘密を復元
    test_shares = shares[:THRESHOLD]
    recovered_secret = combine(test_shares, MODULUS_Q, return_string=True)
    print(f"\n最初の{THRESHOLD}個のシェアから復元した秘密: {recovered_secret}")
    print(f"元の秘密と一致: {int(recovered_secret) == secret_int}")
    
    # 別の threshold 個のシェアから秘密を復元
    test_shares2 = [shares[0], shares[2], shares[4]]
    recovered_secret2 = combine(test_shares2, MODULUS_Q, return_string=True)
    print(f"\n別の{THRESHOLD}個のシェアから復元した秘密: {recovered_secret2}")
    print(f"元の秘密と一致: {int(recovered_secret2) == secret_int}")
    
    # 各シェアのコミットメント検証
    for i, share in enumerate(shares):
        valid = verify(share, commitments, MODULUS_P, GENERATOR, MODULUS_Q)
        print(f"シェア {i+1} の検証結果: {valid}")
