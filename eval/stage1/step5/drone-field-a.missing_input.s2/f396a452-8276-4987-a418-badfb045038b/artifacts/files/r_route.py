import numpy as np, math, itertools
from PIL import Image
r=np.array(Image.open('inputs/red.png')).astype(float); n=np.array(Image.open('inputs/nir.png')).astype(float)
print(r.shape)
nd=(n-r)/(n+r)
st=[]
for z in range(1,7):
    row=(z-1)//3; col=(z-1)%3
    m=nd[row*30:(row+1)*30, col*30:(col+1)*30].mean()
    print(z, round(m,4), m<0.35)
    if m<0.35: st.append(z)
print('stressed',st, 'field',round(nd.mean(),4))
C={1:(15,15),2:(45,15),3:(75,15),4:(15,45),5:(45,45),6:(75,45)}
def tour(p):
    pts=[(0,0)]+[C[z] for z in p]+[(0,0)]
    return sum(math.hypot(a[0]-b[0],a[1]-b[1]) for a,b in zip(pts,pts[1:])),pts
if len(st)>=2:
    res=sorted((tour(p)[0],p) for p in itertools.permutations(st))
    best=res[0][0]
    print('ties',[p for t,p in res if t-best<1e-9])
    t,pts=tour(res[0][1]); print(res[0][1])
    for a,b in zip(pts,pts[1:]): print(a,b,round(math.hypot(a[0]-b[0],a[1]-b[1]),3))
    print(t, 260-t)
