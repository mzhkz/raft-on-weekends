from decimal import Decimal, getcontext
import random

# TypeScript の Decimal.js での精度設定に対応
getcontext().prec = 10_000_000  # 必要に応じて調整してください

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

def split(secret, n, k, p, q, generator):
    """
    Feldman の VSS による秘密分散を行う関数です。
    
    Parameters:
      secret: "0x" で始まる 16 進数文字列（秘密）
      n: 発行するシェアの総数
      k: 秘密復元に必要なシェア数（しきい値）
      p, q, generator: Decimal 型のパラメータ（p, q は素数、generator は p 未満の生成元）
    
    戻り値は辞書で、キー "D" にシェアのリスト、"C" に各係数に対するコミットメントのリストが入ります。
    """
    if not isinstance(secret, str):
        raise TypeError("The secret must be a string.")
    if not secret.startswith("0x"):
        raise TypeError("The secret must be a hex string starting with '0x'.")
    if not (isinstance(p, Decimal) and isinstance(q, Decimal) and isinstance(generator, Decimal)):
        raise TypeError("p, q, and generator must be Decimal instances.")

    S = Decimal(int(secret, 16))
    g = generator

    if S > q:
        raise ValueError("The secret must be less than q.")
    if g > p:
        raise ValueError("The generator must be less than p.")

    # a[0] が秘密、a[1..k-1] がランダム係数
    a = [S]
    D = []  # シェアのリスト
    # コミットメント C[0] は g^S mod p となる
    C = [{"i": Decimal(0), "c": expmod(g, S, p)}]
    
    for i in range(1, k):
        coeff = random_decimal(Decimal(1), q - Decimal(1))
        a.append(coeff)
        C.append({"i": Decimal(i), "c": expmod(g, coeff, p)})
    
    # シェア (x, y) を計算（x = 1, 2, …, n）
    for i in range(n):
        x = Decimal(i + 1)
        share = {"x": x, "y": polynomial(x, a, q)}
        D.append(share)
    
    return {"D": D, "C": C}

def lagrange_basis(data, j, q):
    """
    シェアリスト data からインデックス j のシェアに対するラグランジュ基底の
    分子と分母（0 での評価）を計算します。
    """
    numerator = Decimal(1)
    denominator = Decimal(1)
    x_j = data[j]["x"]
    for i in range(len(data)):
        if data[i]["x"] != x_j:
            denominator = (denominator * (data[i]["x"] - x_j)) % q
    for i in range(len(data)):
        if data[i]["x"] != x_j:
            numerator = (numerator * data[i]["x"]) % q
    return numerator, denominator

def lagrange_interpolate(data, q):
    """
    ラグランジュ補間を用いてシェアから秘密を再構成します。
    """
    S = Decimal(0)
    for i in range(len(data)):
        num, den = lagrange_basis(data, i, q)
        S = (S + data[i]["y"] * divmod_decimal(num, den, q)) % q
    return S

def combine(shares, prime):
    """
    複数のシェアから秘密を再構成します。
    
    Parameters:
      shares: シェアのリスト（各シェアは {'x': Decimal, 'y': Decimal} で表される）
      prime: q の値（Decimal）
    """
    # 各シェアを Decimal 型に整形してからラグランジュ補間を実行
    decimal_shares = [{"x": Decimal(share["x"]), "y": Decimal(share["y"])} for share in shares]
    return lagrange_interpolate(decimal_shares, prime)

def verify(share, C, prime, generator, q):
    """
    与えられたシェアがコミットメント C と整合するか検証します。
    
    シェア (x, y) に対して、検証すべき等式は  
      g^y ≡ ∏_{i=0}^{k-1} (C_i)^(x^i mod q) (mod prime)
    となります。
    
    Parameters:
      share: {'x': Decimal, 'y': Decimal}
      C: コミットメントのリスト。各要素は {'i': Decimal, 'c': Decimal}
      prime: p（Decimal）
      generator: g（Decimal）
      q: シークレット分散で用いた素数（Decimal）
    """
    p = Decimal(prime)
    g = Decimal(generator)
    # 左辺: g^(y) mod p
    lG = expmod(g, share["y"], p)
    rG = Decimal(1)
    for i in range(len(C)):
        commitment = C[i]
        # x^i を計算し、q で割った余りに統一
        e = power(share["x"], Decimal(i)) % q
        # 各項は (C_i)^(x^i mod q) mod p
        basis = expmod(commitment["c"], e, p)
        rG = (rG * basis) % p
    return rG == lG

