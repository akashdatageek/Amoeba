import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
items=[("Pens",10,1.50),("Pads",4,3.25),("Clips",100,0.02)]
names=[n for n,_,_ in items]
totals=[round(q*p,2) for _,q,p in items]
print("values:",dict(zip(names,totals)))
fig,ax=plt.subplots(figsize=(8,5),dpi=100)
bars=ax.bar(names,totals,color=["#4472C4","#ED7D31","#70AD47"])
ax.set_title("Item totals"); ax.set_xlabel("Item"); ax.set_ylabel("Total")
for b,v in zip(bars,totals):
    ax.text(b.get_x()+b.get_width()/2,v,f"{v:.2f}",ha="center",va="bottom")
ax.set_ylim(0,max(totals)*1.15)
fig.tight_layout(); fig.savefig("totals.png",dpi=100)
print("title:",ax.get_title(),"| xlabel:",ax.get_xlabel(),"| ylabel:",ax.get_ylabel())
print("ticks:",[t.get_text() for t in ax.get_xticklabels()])
print("bar labels:",[t.get_text() for t in ax.texts],"bars:",len(ax.patches))
plt.close(fig)
