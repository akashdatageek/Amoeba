import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import os
items = [("pens", 10, 1.50), ("pads", 4, 3.25), ("clips", 100, 0.02)]
labels = [n for n, q, p in items]
totals = [round(q * p, 2) for n, q, p in items]
print(labels, totals)
assert totals == [15, 13, 2]
def draw(dpi):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(labels, totals, color=["#4472C4", "#ED7D31", "#A5A5A5"])
    ax.set_title("Total by item")
    ax.set_ylabel("Total")
    ax.set_ylim(0, max(totals) * 1.15)
    for b, v in zip(bars, totals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig("totals.png", dpi=dpi)
    plt.close(fig)
    print("bars:", len(bars))
def size():
    im = mpimg.imread("totals.png")
    h, w = im.shape[:2]
    return w, h
draw(120)
w, h = size(); print("dpi120", f"{w}x{h}")
if w < 600 or h < 600:
    draw(150)
    w, h = size(); print("dpi150", f"{w}x{h}")
print("exists", os.path.exists("totals.png"), os.path.getsize("totals.png"), "bytes")
