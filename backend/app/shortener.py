ALPHABET = (
    "0123456789"
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
)

BASE = len(ALPHABET)  # 62
MIN_LEN = 4  # 0000 ... zZZZ


def encode(n: int) -> str:
    if n < 0:
        raise ValueError("negative id")

    out = []

    while n > 0:
        n, rem = divmod(n, BASE)
        out.append(ALPHABET[rem])

    code = "".join(reversed(out)) or "0"

    # pad so the first few codes are not "1", "2", ...
    return code.rjust(MIN_LEN, ALPHABET[0])