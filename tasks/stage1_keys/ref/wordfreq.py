"""Reference solution for wordfreq-cli (checks that the hidden tests can pass; never shown to the team)."""
import argparse, collections, re, sys

WORD = re.compile(r"[^\W_]+(?:'+[^\W_]+)*|'+", re.UNICODE)


def top_words(text, n=10, min_length=1):
    words = [w.strip("'").lower() for w in re.findall(r"[\w']+", text)]
    words = [x for w in words for x in w.split("_") if x]
    c = collections.Counter(w for w in words if w and len(w) >= min_length)
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("path"); p.add_argument("-n", type=int, default=10); p.add_argument("--min-length", type=int, default=1)
    a = p.parse_args(argv)
    if a.n < 1:
        print("N must be at least 1", file=sys.stderr); return 2
    try:
        text = open(a.path, encoding="utf-8").read()
    except OSError as e:
        print(f"cannot read {a.path}: {e}", file=sys.stderr); return 2
    for w, k in top_words(text, a.n, a.min_length):
        print(f"{w}\t{k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
