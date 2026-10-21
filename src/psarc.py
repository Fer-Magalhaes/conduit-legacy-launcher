import struct,zlib,sys,os
def read(path):
    f=open(path,'rb'); h=f.read(32)
    magic,ver,comp,toclen,esz,n,bsz,flags=struct.unpack('>4sI4sIIIII',h)
    assert magic==b'PSAR'
    toc=f.read(n*esz)
    entries=[]
    for i in range(n):
        e=toc[i*esz:(i+1)*esz]
        md5=e[:16]; bi=struct.unpack('>I',e[16:20])[0]
        us=int.from_bytes(e[20:25],'big'); off=int.from_bytes(e[25:30],'big')
        entries.append((md5,bi,us,off))
    bw=2 if bsz<=65536 else (3 if bsz<=1<<24 else 4)
    rest=f.read(toclen-32-n*esz)
    bl=[int.from_bytes(rest[i:i+bw],'big') for i in range(0,len(rest)-bw+1,bw)]
    def data(idx):
        md5,bi,us,off=entries[idx]; f.seek(off); out=bytearray(); b=bi
        while len(out)<us:
            z=bl[b]; chunk=f.read(z if z else bsz)
            if z and chunk[:2] in (b'\x78\xda',b'\x78\x9c',b'\x78\x01',b'\x78\x5e') :
                try: chunk=zlib.decompress(chunk)
                except Exception: pass
            out+=chunk; b+=1
        return bytes(out[:us])
    names=data(0).decode('latin1').split('\n')
    return f,entries,names,data,(ver,comp,bsz,flags)
if __name__=='__main__':
    src,dst=sys.argv[1],sys.argv[2]; listonly=len(sys.argv)>3
    f,entries,names,data,info=read(src)
    print(info,len(names))
    for i,nm in enumerate(names,1):
        if listonly: print(entries[i][2],nm); continue
        p=os.path.join(dst,nm.lstrip('/'))
        os.makedirs(os.path.dirname(p),exist_ok=True); open(p,'wb').write(data(i))
