#!/usr/bin/env python3
"""Ranged-HTTP zip reader: read members without downloading the whole archive.
     rzip.py URL                    list members
     rzip.py URL MEMBER OUT         extract one member to OUT
     rzip.py URL -x DIR REGEX       extract every member matching REGEX to DIR/<member path>"""
import os, re, sys, io, zipfile, urllib.request
class HF(io.RawIOBase):
    def __init__(s,u):
        s.u=u; r=urllib.request.urlopen(urllib.request.Request(u,method='HEAD')); s.u=r.geturl(); s.n=int(r.headers['Content-Length']); s.p=0
    def seekable(s): return True
    def readable(s): return True
    def tell(s): return s.p
    def seek(s,o,w=0):
        s.p = o if w==0 else (s.p+o if w==1 else s.n+o); return s.p
    def readinto(s,b):
        if s.p>=s.n: return 0
        e=min(s.p+len(b),s.n)-1
        d=urllib.request.urlopen(urllib.request.Request(s.u,headers={'Range':'bytes=%d-%d'%(s.p,e)})).read()
        b[:len(d)]=d; s.p+=len(d); return len(d)
z=zipfile.ZipFile(io.BufferedReader(HF(sys.argv[1]),buffer_size=1<<20))
if len(sys.argv)==2:
    for i in z.infolist(): print(i.file_size, i.filename)
elif sys.argv[2]=='-x':
    for i in z.infolist():
        if re.search(sys.argv[4], i.filename) and not i.is_dir():
            out=os.path.join(sys.argv[3], i.filename)
            if os.path.normpath(out).startswith('..') or os.path.isabs(i.filename): continue
            os.makedirs(os.path.dirname(out), exist_ok=True)
            open(out,'wb').write(z.read(i))
else:
    open(sys.argv[3],'wb').write(z.read(sys.argv[2]))
