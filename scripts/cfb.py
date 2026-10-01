import struct
class CFB:
    def __init__(s, path):
        d=s.d=open(path,'rb').read()
        s.ss=1<<struct.unpack_from('<H',d,30)[0]; s.mss=1<<struct.unpack_from('<H',d,32)[0]
        nfat=struct.unpack_from('<I',d,44)[0]; dirstart=struct.unpack_from('<I',d,48)[0]
        s.cutoff=struct.unpack_from('<I',d,56)[0]; minfat=struct.unpack_from('<I',d,60)[0]
        difat_start=struct.unpack_from('<I',d,68)[0]
        difat=list(struct.unpack_from('<109I',d,76))
        nxt=difat_start
        while nxt not in (0xFFFFFFFE,0xFFFFFFFF):
            sec=s.sec(nxt); vals=struct.unpack('<%dI'%(s.ss//4),sec); difat+=vals[:-1]; nxt=vals[-1]
        s.fat=[]
        for x in difat[:nfat]: s.fat+=struct.unpack('<%dI'%(s.ss//4),s.sec(x))
        s.dirs=[]; raw=s.chain(dirstart)
        for i in range(0,len(raw),128):
            e=raw[i:i+128]; nl=struct.unpack_from('<H',e,64)[0]
            name=e[:max(nl-2,0)].decode('utf-16le'); typ=e[66]
            l,r,c=struct.unpack_from('<III',e,68); st,sz=struct.unpack_from('<IQ',e,116)
            s.dirs.append(dict(name=name,type=typ,l=l,r=r,c=c,start=st,size=sz&0xffffffff))
        root=s.dirs[0]; s.ministream=s.chain(root['start'])
        s.minifat=[]
        if minfat!=0xFFFFFFFE:
            m=s.chain(minfat); s.minifat=list(struct.unpack('<%dI'%(len(m)//4),m))
    def sec(s,i): o=(i+1)*s.ss; return s.d[o:o+s.ss]
    def chain(s,st):
        out=[]; 
        while st<0xFFFFFFFA: out.append(s.sec(st)); st=s.fat[st]
        return b''.join(out)
    def minichain(s,st):
        out=[]
        while st<0xFFFFFFFA: o=st*s.mss; out.append(s.ministream[o:o+s.mss]); st=s.minifat[st]
        return b''.join(out)
    def children(s,idx):
        res=[]
        def w(i):
            if i==0xFFFFFFFF: return
            e=s.dirs[i]; w(e['l']); res.append(i); w(e['r'])
        w(s.dirs[idx]['c']); return res
    def find(s,path):
        idx=0
        for p in path:
            idx=next(i for i in s.children(idx) if s.dirs[i]['name']==p)
        return idx
    def read(s,path):
        e=s.dirs[s.find(path)]
        data=s.chain(e['start']) if e['size']>=s.cutoff else s.minichain(e['start'])
        return data[:e['size']]
    def listdir(s,path):
        return [s.dirs[i]['name'] for i in s.children(s.find(path))]
