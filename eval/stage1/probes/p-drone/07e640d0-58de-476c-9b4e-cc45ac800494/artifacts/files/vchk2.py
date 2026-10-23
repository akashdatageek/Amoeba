import struct, zlib, numpy as np
def dec(p):
    d=open(p,'rb').read(); pos=8; idat=b''; 
    while pos<len(d):
        n,=struct.unpack('>I',d[pos:pos+4]); t=d[pos+4:pos+8]; c=d[pos+8:pos+8+n]; pos+=12+n
        if t==b'IHDR': w,h,bd,ct=struct.unpack('>IIBB',c[:10])
        if t==b'IDAT': idat+=c
    bpp={0:1,2:3,6:4}[ct]; raw=zlib.decompress(idat); st=w*bpp; prev=bytearray(st); out=[]; i=0
    for r in range(h):
        f=raw[i]; line=bytearray(raw[i+1:i+1+st]); i+=1+st
        for x in range(st):
            a=line[x-bpp] if x>=bpp else 0; b=prev[x]; c=prev[x-bpp] if x>=bpp else 0
            if f==1: line[x]=(line[x]+a)&255
            elif f==2: line[x]=(line[x]+b)&255
            elif f==3: line[x]=(line[x]+((a+b)>>1))&255
            elif f==4:
                pa=abs(b-c);pb=abs(a-c);pc=abs(a+b-2*c)
                pr=a if pa<=pb and pa<=pc else (b if pb<=pc else c)
                line[x]=(line[x]+pr)&255
        out.append(list(line)); prev=line
    return w,h,bd,ct,np.array(out,dtype=np.int64).reshape(h,w,bpp)
w,h,_,_,R=dec('inputs/probe_red.png'); _,_,_,_,N=dec('inputs/probe_nir.png')
R=R[:,:,0].astype(float);N=N[:,:,0].astype(float)
nd=(N-R)/(N+R)
print(w,h,np.unique(R),np.unique(N))
we=nd[:,:20].mean();ea=nd[:,20:].mean();print('west',we,'east',ea,'flags',we<0.3,ea<0.3)
c=np.loadtxt('ndvi_values.csv',delimiter=',');print('csv',c.shape,abs(c-nd).max(),c[:,:20].mean(),c[:,20:].mean())
W,H,bd,ct,P=dec('ndvi.png');print('png',W,H,bd,ct,'max|R-G|',abs(P[:,:,0]-P[:,:,1]).max())
import matplotlib;matplotlib.use('Agg');from matplotlib import cm
for v in (0.6,0.1):
    exp=np.array(cm.RdYlGn((v+1)/2))*255
    print(v,'expected rgb',exp.round(0))
# find pixels near expected
for v in (0.6,0.1):
    exp=np.array(cm.RdYlGn((v+1)/2))[:3]*255
    d=np.abs(P[:,:,:3]-exp).sum(2); print(v,'pixels within 3 of expected:',(d<=3).sum())
# the axes region: sample left & right image centre approx
print(open('render.py').read())
