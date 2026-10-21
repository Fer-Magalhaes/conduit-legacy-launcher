import struct,zlib,sys,os
def repack(src,dst,repl):
    f=open(src,'rb'); h=f.read(32)
    magic,ver,comp,toclen,esz,n,bsz,flags=struct.unpack('>4sI4sIIIII',h)
    toc=f.read(n*esz); bw=2 if bsz<=65536 else (3 if bsz<=1<<24 else 4)
    rest=f.read(toclen-32-n*esz)
    bl=[int.from_bytes(rest[i:i+bw],'big') for i in range(0,len(rest),bw)]
    E=[]
    for i in range(n):
        e=toc[i*esz:(i+1)*esz]
        E.append([e[:16],struct.unpack('>I',e[16:20])[0],int.from_bytes(e[20:25],'big'),int.from_bytes(e[25:30],'big')])
    # read manifest names
    sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
    import psarc
    _,_,names,data,_=psarc.read(src)
    names=['']+[x.lstrip('/') for x in names]
    # plan blocks per entry
    plan=[]  # (newblocks list of (sizecode, bytes or (offset,len)), usize)
    used=set()
    for i,(md5,bi,us,off) in enumerate(E):
        nm=names[i] if i<len(names) else ''
        if nm in repl:
            used.add(nm)
            raw=open(repl[nm],'rb').read(); blocks=[]
            for k in range(0,len(raw),bsz):
                chunk=raw[k:k+bsz]; c=zlib.compress(chunk,9)
                if len(c)>=len(chunk): blocks.append(( (0 if len(chunk)==bsz else len(chunk)), chunk))
                else: blocks.append((len(c),c))
            if not raw: blocks=[]
            plan.append(('new',blocks,len(raw)))
        else:
            nb=(us+bsz-1)//bsz; codes=bl[bi:bi+nb]
            length=sum(c if c else bsz for c in codes)
            plan.append(('copy',codes,us,off,length))
    missing=set(repl)-used
    if missing: raise SystemExit('not found in archive: %s'%missing)
    total_blocks=sum(len(p[1]) for p in plan)
    newtoclen=32+n*esz+total_blocks*bw
    out=open(dst,'wb'); out.write(b'\x00'*newtoclen)
    newE=[]; codes_all=[]; pos=newtoclen
    for i,p in enumerate(plan):
        bi=len(codes_all)
        if p[0]=='new':
            _,blocks,us=p
            for code,bb in blocks: codes_all.append(code); out.write(bb)
            newE.append((E[i][0],bi,us,pos)); pos+=sum(len(bb) for _,bb in blocks)
        else:
            _,codes,us,off,length=p
            f.seek(off); left=length
            while left: c=f.read(min(left,1<<24)); out.write(c); left-=len(c)
            codes_all+=codes; newE.append((E[i][0],bi,us,pos)); pos+=length
    out.seek(0)
    out.write(struct.pack('>4sI4sIIIII',magic,ver,comp,newtoclen,esz,n,bsz,flags))
    for md5,bi,us,off in newE: out.write(md5+struct.pack('>I',bi)+us.to_bytes(5,'big')+off.to_bytes(5,'big'))
    for c in codes_all: out.write(c.to_bytes(bw,'big'))
    out.close()
if __name__=='__main__':
    src,dst=sys.argv[1],sys.argv[2]; repl=dict(a.split('=',1) for a in sys.argv[3:])
    repack(src,dst,repl); print('ok')
