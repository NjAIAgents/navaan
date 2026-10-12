"""Align lyric lines to sung audio. Needs <WORK>/<tag>_voc.npy, <tag>_hi.json (Hindi ASR) and optionally <tag>_asren.json.
usage: python3 align.py <tag> <lyrics.txt> <out_caption_cues.json> '{"28":[139.5,141.5],"35:e":[165.0,167.8]}'
The last argument pins line start (N) or end (N:e) windows in seconds; use {} for none.
"""
import os
WORK=os.environ.get('NAVAAN_WORK','/tmp'); WD=os.environ.get('NAVAAN_WHISPER_DIR','/tmp')
import numpy as np, re, json, sys, difflib
sr=44100; FR=20
def parse(path):
    lines=[];sec=[];cur="x"
    for l in open(path,encoding="utf-8").read().splitlines():
        s=l.strip()
        if not s: continue
        if s.startswith("["):
            m=s.lower()
            if "chorus" in m and "pre" not in m: cur="chorus"
            elif "pre-chorus" in m: cur="pre"
            elif "verse" in m and "rap" not in m: cur="verse"
            elif "rap" in m: cur="rap"
            elif "bridge" in m: cur="bridge"
            elif m in("[male]","[female]","[both]"): pass
            continue
        lines.append(s); sec.append(cur)
    return lines,sec
def sk(s): return "".join(c for c in s if "ऄ"<=c<="ह" or "क़"<=c<="य़")
def wt(s): return max(3,len(re.sub(r"[\s,.\-!?]","",s)))
def isdev(s): return bool(re.search("[ऀ-ॿ]",s))
PINS={}
def run(tag,lyr,outp):
    asr=json.load(open(f"{WORK}/{tag}_hi.json"))
    import os
    aen=json.load(open(f"{WORK}/{tag}_asren.json")) if os.path.exists(f"{WORK}/{tag}_asren.json") else []
    v=np.load(f"{WORK}/{tag}_voc.npy"); hop=sr//FR; n=len(v)//hop
    e=np.sqrt((v[:n*hop].reshape(n,hop)**2).mean(1)); e/=np.percentile(e,99)
    es=np.convolve(e,np.ones(3)/3,"same"); act=es>0.05
    B=[0]
    for i in range(1,n-1):
        lo=max(0,i-8);hi=min(n,i+9)
        if es[i]==es[lo:hi].min():
            mx=es[max(0,i-30):i+31].max()
            if es[i]<0.55*mx and i-B[-1]>=8: B.append(i)
    B.append(n)
    segs=[]
    for a,b in zip(B[:-1],B[1:]):
        if act[a:b].sum()>=4:
            ii=np.where(act[a:b])[0]; segs.append((a+ii[0],a+ii[-1]+1))
    lines,sec=parse(lyr); N=len(lines); M=len(segs)
    W=np.array([wt(s) for s in lines],float); LS=[sk(l) for l in lines]
    S=np.array([s[0]/FR for s in segs]); E=np.array([s[1]/FR for s in segs])
    cen=np.array([(a+b)/2 for a,b,_ in asr]); txt=[sk(t) for _,_,t in asr]
    cen_en=np.array([(a+b)/2 for a,b,_ in aen]); txt_en=[set(re.findall("[a-z]+",t.lower())) for _,_,t in aen]
    ec={}
    def emis(i,s,e2):
        k=(i,round(s,2),round(e2,2))
        if k in ec: return ec[k]
        if not isdev(lines[i]):
            ws=set(re.findall("[a-z]+",lines[i].lower()))
            idx=[q for q,c in enumerate(cen_en) if s-1.5<=c<=e2+1.5]
            r_=1.0 if not idx else 1-min(1.0,max(len(ws&txt_en[q])/len(ws) for q in idx)*1.2)
        elif len(LS[i])<4: r_=0.0
        else:
            idx=[q for q,c in enumerate(cen) if s-1.5<=c<=e2+1.5]
            if not idx: r_=1.0
            else:
                best=0
                for q in idx:
                    m=difflib.SequenceMatcher(None,LS[i],txt[q],autojunk=False)
                    best=max(best,sum(b.size for b in m.get_matching_blocks())/len(LS[i]))
                r_=1-min(1.0,best*1.4)
        ec[k]=r_; return r_
    g=(E-S).sum()/W.sum()
    rs={"verse":g,"pre":g,"chorus":g*1.5,"rap":g,"bridge":g,"x":g}
    INF=1e18;K=8
    for it in range(4):
        dp=np.full((N+1,M+1),INF);bk={};dp[0][0]=0
        for i in range(N+1):
            for j in range(M+1):
                c=dp[i][j]
                if c>=INF: continue
                if j<M:
                    cs=c+0.6+1.2*(E[j]-S[j])
                    if cs<dp[i][j+1]: dp[i][j+1]=cs; bk[(i,j+1)]=("s",j)
                if i<N:
                    for k2 in range(1,K+1):
                        jj=j+k2
                        if jj>M: break
                        d=E[jj-1]-S[j]
                        if d>10: break
                        gaps=sum(max(0,S[q+1]-E[q]-0.8) for q in range(j,jj-1))
                        exp=rs[sec[i]]*W[i]
                        pen=0.0
                        if i in PINS and not (PINS[i][0]<=S[j]<=PINS[i][1]): pen+=60
                        if (i,'e') in PINS and not (PINS[(i,'e')][0]<=E[jj-1]<=PINS[(i,'e')][1]): pen+=60
                        cc=c+((d-exp)/(exp+2.0))**2*1.5+gaps*3+emis(i,S[j],E[jj-1])*5+pen
                        if cc<dp[i+1][jj]: dp[i+1][jj]=cc; bk[(i+1,jj)]=("g",j)
        bj=int(np.argmin(dp[N])); i,j=N,bj;res=[None]*N
        while (i,j)!=(0,0):
            t,pj=bk[(i,j)]
            if t=="g": res[i-1]=(pj,j);i-=1;j=pj
            else: j=pj
        for sname in set(sec):
            ds=[(E[b-1]-S[a])/W[q] for q,(a,b) in enumerate(res) if sec[q]==sname]
            if ds: rs[sname]=float(np.median(ds))
    cues=[[round(float(S[a]),2),round(float(E[b-1]),2),lines[q]] for q,(a,b) in enumerate(res)]
    json.dump(cues,open(outp,"w"),ensure_ascii=False,indent=0)
    for q,c in enumerate(cues): print(f"{c[0]:7.2f} {c[1]:7.2f} {c[1]-c[0]:5.2f} {emis(q,c[0],c[1]):.2f} {sec[q][:3]} {c[2]}")
    print(rs)
PINS.update({(int(k[:-2]),'e') if k.endswith(':e') else int(k):tuple(v) for k,v in json.loads(sys.argv[4]).items()})
run(sys.argv[1],sys.argv[2],sys.argv[3])
