import zlib, struct, sys
from cfb import CFB
f = CFB(sys.argv[1])
hdr = f.read(["FileHeader"]); compressed = hdr[36] & 1
out=[]
secs = sorted([["BodyText",n] for n in f.listdir(["BodyText"])], key=lambda s:int(s[1][7:]))
for s in secs:
    d = f.read(s)
    if compressed: d = zlib.decompress(d, -15)
    i=0
    while i < len(d):
        h = struct.unpack_from('<I', d, i)[0]; tag=h&0x3ff; size=(h>>20)&0xfff; i+=4
        if size==0xfff: size=struct.unpack_from('<I',d,i)[0]; i+=4
        if tag==67:
            b=d[i:i+size]; txt=[]; j=0
            while j < len(b):
                c=struct.unpack_from('<H',b,j)[0]
                if c in (1,2,3,11,12,14,15,16,17,18,21,22,23): j+=16; continue
                if c in (4,5,6,7,8,9,19,20): j+=16; continue
                if c==10: txt.append('\n'); j+=2; continue
                if c==13: j+=2; continue
                txt.append(chr(c)); j+=2
            t=''.join(txt).strip()
            if t: out.append(t)
        i+=size
open(sys.argv[2],'w').write('\n'.join(out))
