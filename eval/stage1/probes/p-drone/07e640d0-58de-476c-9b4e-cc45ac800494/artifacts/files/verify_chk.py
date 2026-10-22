import struct,zlib,itertools,csv
def dec(n):
    d=open(f'inputs/probe_{n}.png','rb').read()
    p=8;idat=b''
    while p<len(d):
        l,=struct.unpack('>I',d[p:p+4]);t=d[p+4:p+8];c=d[p+8:p+8+l];p+=12+l
        if t==b'IDAT':idat+=c
    raw=zlib.decompress(idat);W=40;rows=[];prev=[0]*W
    for y in range(40):
        o=y*41;f=raw[o];s=list(raw[o+1:o+41]);cur=[]
        for x in range(W):
            a=cur[x-1] if x else 0;b=prev[x];c=prev[x-1] if x else 0
            if f==0:v=s[x]
            elif f==1:v=s[x]+a
            elif f==2:v=s[x]+b
            elif f==3:v=s[x]+(a+b)//2
            else:
                pa=abs(b-c);pb=abs(a-c);pc=abs(a+b-2*c)
                pr=a if pa<=pb and pa<=pc else (b if pb<=pc else c)
                v=s[x]+pr
            cur.append(v&255)
        rows.append(cur);prev=cur
    return rows
R=dec('red');N=dec('nir')
print(min(map(min,R)),max(map(max,R)),min(map(min,N)),max(map(max,N)))
nan=0;vals=[[None]*40 for _ in range(40)]
for y in range(40):
    for x in range(40):
        s=N[y][x]+R[y][x]
        if s==0:nan+=1
        else:vals[y][x]=(N[y][x]-R[y][x])/s
def m(c0,c1):
    v=[vals[y][x] for y in range(40) for x in range(c0,c1) if vals[y][x] is not None];return sum(v)/len(v),len(v)
w=m(0,20);e=m(20,40);print('W',w,'E',e,'nan',nan,w[0]<.3,e[0]<.3)
rows=list(csv.reader(open('ndvi_values.csv')));print(len(rows),len(rows[0]),rows[0][:3])
import numpy as np
a=np.array([[float(c) if c not in('','nan','NaN') else np.nan for c in r] for r in rows[-40:]])
ref=np.array([[v if v is not None else np.nan for v in r] for r in vals])
print(a.shape,np.nanmean(a[:,:20]),np.nanmean(a[:,20:]),np.nanmax(abs(a-ref)))
d=open('ndvi.png','rb').read();print(struct.unpack('>IIBB',d[16:26]))
import matplotlib.image as mi
im=mi.imread('ndvi.png');print(im.shape,float(abs(im[:,:,0]-im[:,:,1]).max()))
