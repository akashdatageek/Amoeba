import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
items=[("Pens",10,1.50),("Pads",4,3.25),("Clips",100,0.02)]
names=[n for n,_,_ in items]; totals=[round(q*p,2) for _,q,p in items]
fig,ax=plt.subplots(figsize=(8,5),dpi=100)
bars=ax.bar(names,totals)
ax.set_title("Item totals"); ax.set_xlabel("Item"); ax.set_ylabel("Total")
for b,v in zip(bars,totals): ax.text(b.get_x()+b.get_width()/2,v,f"{v:.2f}",ha="center",va="bottom")
ax.set_ylim(0,max(totals)*1.15); fig.tight_layout(); fig.canvas.draw()
r=fig.canvas.get_renderer()
W,H=fig.canvas.get_width_height()
els=[ax.title,ax.xaxis.label,ax.yaxis.label]+list(ax.get_xticklabels())+list(ax.texts)
for t in els:
    bb=t.get_window_extent(r); print(repr(t.get_text()),[round(x) for x in (bb.x0,bb.y0,bb.x1,bb.y1)],"inside" if bb.x0>=0 and bb.y0>=0 and bb.x1<=W and bb.y1<=H else "OUTSIDE")
