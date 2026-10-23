import numpy as np, matplotlib.image as mi
from PIL import Image
for n in ['red','nir']:
    im=Image.open('inputs/probe_%s.png'%n); a=np.array(im)
    r=mi.imread('inputs/probe_%s.png'%n)
    print(n,'PIL mode',im.mode,'size',im.size,'np shape',a.shape,'dtype',a.dtype,'min',a.min(),'max',a.max(),'unique',np.unique(a)[:10],'nuniq',len(np.unique(a)))
    print(' imread dtype',r.dtype,r.shape,r.min(),r.max())
red=np.array(Image.open('inputs/probe_red.png')); nir=np.array(Image.open('inputs/probe_nir.png'))
if red.ndim>2:
    red=red[:,:,0]; nir=nir[:,:,0]
print('same dtype',red.dtype==nir.dtype,'same shape',red.shape==nir.shape)
r=red.astype(np.float64); n=nir.astype(np.float64)
s=n+r
with np.errstate(divide='ignore',invalid='ignore'):
    nd=(n-r)/s
nd[s==0]=np.nan
print('NaN count',int(np.isnan(nd).sum()), 'shape',nd.shape)
np.savetxt('ndvi_values.csv',nd,delimiter=',',fmt='%.10f')
w=np.nanmean(nd[:,0:20]); e=np.nanmean(nd[:,20:40])
for k,v,sl in [('west',w,nd[:,0:20]),('east',e,nd[:,20:40])]:
    print(k,'full',repr(float(v)),'3dp','%.3f'%v,'stressed',bool(v<0.3),'near0.3',abs(v-0.3)<=0.0005,'min',np.nanmin(sl),'max',np.nanmax(sl))
print('unique red',np.unique(red),'unique nir',np.unique(nir))
print('csv rows',sum(1 for _ in open('ndvi_values.csv')))
