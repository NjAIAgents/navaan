"""Windowed Whisper ASR on isolated vocals, direct ONNX decode (keeps Hindi UTF-8 byte tokens).
usage: python3 asr.py <tag> <small|medium> <hi|en> <out.json>
env: NAVAAN_WORK, NAVAAN_WHISPER_DIR (dir holding sherpa-onnx-whisper-<model>)
"""
import os
WORK=os.environ.get('NAVAAN_WORK','/tmp'); WD=os.environ.get('NAVAAN_WHISPER_DIR','/tmp')
import numpy as np, onnxruntime as ort, base64, librosa, json, sys
from scipy.signal import resample_poly
class W:
    def __init__(s,M,lang="hi",threads=1):
        o=ort.SessionOptions(); o.intra_op_num_threads=threads
        s.e=ort.InferenceSession(f"{M}-encoder.int8.onnx",o,providers=["CPUExecutionProvider"])
        s.d=ort.InferenceSession(f"{M}-decoder.int8.onnx",o,providers=["CPUExecutionProvider"])
        md=s.e.get_modelmeta().custom_metadata_map
        s.nl=int(md["n_text_layer"]); s.ts=int(md["n_text_state"]); s.ctx=int(md["n_text_ctx"])
        codes=md["all_language_codes"].split(","); ids=[int(x) for x in md["all_language_tokens"].split(",")]
        s.lang=ids[codes.index(lang)]
        s.sot=int(md["sot"]); s.tr=int(md["transcribe"]); s.nots=int(md["no_timestamps"]); s.eot=int(md["eot"])
        s.supp=set(int(x) for x in md["non_speech_tokens"].split(","))
        s.nm=int(md["n_mels"])
        s.tok=[base64.b64decode(l.split()[0]) for l in open(f"{M}-tokens.txt")]
        s.fb=librosa.filters.mel(sr=16000,n_fft=400,n_mels=s.nm)
        s.win=np.hanning(401)[:-1].astype(np.float32)
    def mel(s,x):
        x=np.pad(x,(0,480000-len(x)))[:480000]
        st=librosa.stft(x,n_fft=400,hop_length=160,window=s.win,center=True,pad_mode="reflect")
        m=s.fb@(np.abs(st[:,:-1])**2)
        l=np.log10(np.maximum(m,1e-10)); l=np.maximum(l,l.max()-8.0); return ((l+4)/4).astype(np.float32)
    def run(s,x):
        mel=s.mel(x)[None]
        ck,cv=s.e.run(None,{"mel":mel})
        sk=np.zeros((s.nl,1,s.ctx,s.ts),np.float32); sv=np.zeros_like(sk)
        toks=[s.sot,s.lang,s.tr,s.nots]; out=[]; off=0; cur=np.array([toks],np.int64)
        for _ in range(100):
            lg,sk,sv=s.d.run(None,{"tokens":cur,"in_n_layer_self_k_cache":sk,"in_n_layer_self_v_cache":sv,"n_layer_cross_k":ck,"n_layer_cross_v":cv,"offset":np.array([off],np.int64)})
            off+=cur.shape[1]
            l=lg[0,-1].copy()
            l[50364:]=-1e9; 
            for t in s.supp: l[t]=-1e9
            t=int(l.argmax())
            if t==s.eot: break
            out.append(t); cur=np.array([[t]],np.int64)
            if len(out)>16 and out[-8:]==out[-16:-8]: break
        b=b"".join(s.tok[t] for t in out if t<len(s.tok))
        return b.decode("utf-8",errors="ignore")
def vox(tag):
    v=np.load(f"{WORK}/{tag}_voc.npy"); v=resample_poly(v,160,441).astype(np.float32); return v/np.abs(v).max()
if __name__=="__main__":
    tag,model,lang,outp=sys.argv[1:5]; M=f"{WD}/sherpa-onnx-whisper-{model}/{model}"
    w=W(M,lang); v=vox(tag); out=[]; WN,ST=6,3
    for a in range(0,int(len(v)/16000)-WN+1,ST):
        seg=v[a*16000:(a+WN)*16000]
        if np.sqrt((seg**2).mean())<0.01: continue
        t=w.run(seg); out.append([a,a+WN,t]); print(a,t,flush=True)
        json.dump(out,open(outp,"w"),ensure_ascii=False)
