import re, sys
sys.path.insert(0,'.')
from slug import slugify
def exp(t):
    out=[];pend=False
    for ch in t.lower():
        if ch in 'abcdefghijklmnopqrstuvwxyz0123456789':
            if pend and out: out.append('-')
            pend=False; out.append(ch)
        else: pend=True
    return ''.join(out)
for t in ['  Multiple   spaces ','a_b-c.d','--x--','123 ABC','!@#','Ünïcode','a\nb\tc','XXX - y','İ','Hello,World']:
    a=slugify(t);e=exp(t);print(repr(t),'|',repr(e),'|',repr(a),'|','OK' if a==e else 'DIFF')
cases=[("Hello World","hello-world"),("  Hello,   World!!  ","hello-world"),("a---b___c","a-b-c"),("---abc---","abc"),("",""),("!!!",""),("Python 3.12 Release","python-3-12-release"),("Café Münch","caf-m-nch"),("ALLCAPS","allcaps"),("already-a-slug","already-a-slug")]
muts={'nostrip':lambda t:re.sub(r'[^a-z0-9]+','-',t.lower()),
'nocollapse':lambda t:re.sub(r'[^a-z0-9]','-',t.lower()).strip('-'),
'nolower':lambda t:re.sub(r'[^a-z0-9]+','-',t).strip('-'),
'nolower_AZ':lambda t:re.sub(r'[^a-zA-Z0-9]+','-',t).strip('-')}
for n,f in muts.items():
    print(n,'failures:',[c[0] for c in cases if f(c[0])!=c[1]])
