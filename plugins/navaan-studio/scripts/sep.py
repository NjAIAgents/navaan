"""Isolate vocals with UVR MDX-NET Voc FT (ONNX).
usage: python3 sep.py <tag> <input_audio>
env: NAVAAN_VOC_MODEL (onnx path), NAVAAN_WORK (output dir). Writes <WORK>/<tag>_voc.npy (mono, 44.1 kHz).
"""
import numpy as np, subprocess, sys, os, onnxruntime as ort
from scipy.signal import stft, istft
N=6144;H=1024;F=3072;T=256;SR=44100
WORK=os.environ.get("NAVAAN_WORK","/tmp")
sess=ort.InferenceSession(os.environ.get("NAVAAN_VOC_MODEL","/tmp/voc.onnx"),providers=["CPUExecutionProvider"])
def load(p):
    raw=subprocess.check_output(["ffmpeg","-v","error","-i",p,"-f","f32le","-ac","1","-ar",str(SR),"-"]); return np.frombuffer(raw,dtype=np.float32)
def run(tag,src):
    x=load(src)
    C=H*(T-1)
    out=np.zeros_like(x)
    w=np.hanning(N+1)[:-1]; ws=w.sum()
    for i in range(0,len(x),C):
        seg=x[i:i+C]; L=len(seg)
        if L<C: seg=np.pad(seg,(0,C-L))
        _,_,Z=stft(seg,nperseg=N,noverlap=N-H,window=w,boundary="even",padded=False)
        Z=Z*ws  # (freq 3073, frames)
        Z=Z[:F,:T]
        if Z.shape[1]<T: Z=np.pad(Z,((0,0),(0,T-Z.shape[1])))
        inp=np.stack([Z.real,Z.imag,Z.real,Z.imag])[None].astype(np.float32)
        o=sess.run(None,{"input":inp})[0][0]
        Y=np.zeros((N//2+1,T),dtype=np.complex64); Y[:F]=(o[0]+1j*o[1])
        _,y=istft(Y/ws,nperseg=N,noverlap=N-H,window=w,boundary=True)
        y=y[:C]; 
        out[i:i+L]=y[:L]
        print(tag,i/SR,flush=True)
    np.save(f"{WORK}/{tag}_voc.npy",out)
run(sys.argv[1],sys.argv[2])
