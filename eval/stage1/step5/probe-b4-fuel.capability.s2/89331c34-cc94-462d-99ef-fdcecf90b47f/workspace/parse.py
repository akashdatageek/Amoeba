import re,json,glob,datetime as dt
rows={}
for f in sorted(glob.glob('sources/S3_*')+glob.glob('sources/S5_*')):
    t=open(f).read()
    pairs=re.findall(r'"period":"(\d{4}-\d{2}-\d{2})".*?"series":"([^"]*)".*?"value":"([\d.]+)"',t)
    print(f,len(t),len(pairs),t[:200].replace('\n',' '))
    for p,s,v in pairs:
        if 'R20' in t[:100000]: rows[p]=v
ds=sorted(rows)
print(len(ds),ds[:2],ds[-3:])
last=ds[-52:]
d=[dt.date.fromisoformat(x) for x in last]
print(len(last),all((b-a).days==7 for a,b in zip(d,d[1:])))
print([(x,rows[x]) for x in last[-3:]])
