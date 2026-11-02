"""Conservative FBX 7.5+ reserialization for the existing Three.js import contract.

No DCC/model replacement: preserve geometry, textures, animation, IDs and bone order.
Only remove already-ignored ShininessExponent texture connections and persist the
same top-four normalized influences that FBXLoader already renders. Never replace
source files here: emit candidates for independent loader/equivalence validation.
"""
from dataclasses import dataclass, field
from pathlib import Path
import argparse, hashlib, json, math, struct, zlib

HEADER=b'Kaydara FBX Binary  \x00\x1a\x00'
SCALARS={'Y':'h','C':'B','I':'i','F':'f','D':'d','L':'q'}
ARRAYS={'f':'f','d':'d','i':'i','l':'q','b':'B','c':'B'}

@dataclass
class Property:
    raw: bytes
    value: object=None
    kind: str=''

@dataclass
class Node:
    name: bytes
    props: list=field(default_factory=list)
    children: list=field(default_factory=list)
    terminated: bool=False
    def child(self,name):return next((n for n in self.children if n.name==name.encode()),None)

class Document:
    def __init__(self,data):
        if data[:23]!=HEADER:raise ValueError('Expected binary FBX')
        self.version=struct.unpack_from('<I',data,23)[0]
        if self.version<7500:raise ValueError('This bounded writer accepts FBX 7.5+ only')
        self.data=data;self.offset=27;self.nodes=[]
        while True:
            node=self.read_node()
            if node is None:break
            self.nodes.append(node)
        self.footer=data[self.offset:]
    def take(self,n):
        if self.offset+n>len(self.data):raise ValueError('Truncated FBX')
        out=self.data[self.offset:self.offset+n];self.offset+=n;return out
    def read_node(self):
        end,count,prop_size,name_len=struct.unpack('<QQQB',self.take(25))
        if end==0:
            if count or prop_size or name_len:raise ValueError('Invalid null record')
            return None
        name=self.take(name_len);props=[];prop_end=self.offset+prop_size
        for _ in range(count):
            start=self.offset;kind=self.take(1).decode('ascii');value=None
            if kind in SCALARS:value=struct.unpack('<'+SCALARS[kind],self.take(struct.calcsize(SCALARS[kind])))[0]
            elif kind in ('S','R'):
                n=struct.unpack('<I',self.take(4))[0];raw=self.take(n)
                if kind=='S':value=raw.decode('utf-8',errors='replace')
            elif kind in ARRAYS:
                n,encoding,length=struct.unpack('<III',self.take(12));raw=self.take(length)
                if name in (b'Indexes',b'Weights'):
                    decoded=zlib.decompress(raw) if encoding==1 else raw
                    if encoding not in (0,1) or len(decoded)!=n*struct.calcsize(ARRAYS[kind]):raise ValueError('Invalid array')
                    value=list(struct.unpack('<'+str(n)+ARRAYS[kind],decoded))
            else:raise ValueError('Unknown FBX property '+kind)
            props.append(Property(self.data[start:self.offset],value,kind))
        if self.offset!=prop_end:raise ValueError('Property extent mismatch')
        node=Node(name,props)
        while self.offset<end:
            child=self.read_node()
            if child is None:node.terminated=True;break
            node.children.append(child)
        if self.offset!=end:raise ValueError('Node extent mismatch')
        return node
    def root(self,name):return next(n for n in self.nodes if n.name==name.encode())
    def serialize(self):
        def encode(node,start):
            props=b''.join(p.raw for p in node.props)
            cursor=start+25+len(node.name)+len(props);children=[]
            for child in node.children:
                blob=encode(child,cursor);children.append(blob);cursor+=len(blob)
            if node.terminated:children.append(bytes(25));cursor+=25
            return struct.pack('<QQQB',cursor,len(node.props),len(props),len(node.name))+node.name+props+b''.join(children)
        chunks=[self.data[:27]];offset=27
        for node in self.nodes:
            blob=encode(node,offset);chunks.append(blob);offset+=len(blob)
        chunks.append(bytes(25));offset+=25
        # Preserve the original trailer; only extend its zero alignment as needed.
        chunks.append(bytes((-(offset+len(self.footer)))%16));chunks.append(self.footer)
        return b''.join(chunks)

def set_array(node,values):
    if len(node.props)!=1 or node.props[0].kind not in ARRAYS:raise ValueError('Unexpected array node')
    kind=node.props[0].kind
    raw=struct.pack('<'+str(len(values))+ARRAYS[kind],*values)
    compressed=zlib.compress(raw,6)
    node.props[0]=Property(kind.encode()+struct.pack('<III',len(values),1,len(compressed))+compressed,list(values),kind)

def normalize(document):
    objects=document.root('Objects');connections=document.root('Connections')
    deformers={n.props[0].value:n for n in objects.children if n.name==b'Deformer'}
    relationships=connections.children
    report={'skins':0,'vertices':0,'over_four_before':0,'max_before':0,'removed_ignored_maps':0}
    for skin_id,skin in deformers.items():
        if len(skin.props)<3 or skin.props[2].value!='Skin':continue
        clusters=[]
        for c in relationships:
            v=[p.value for p in c.props]
            if len(v)>=3 and v[2]==skin_id and v[1] in deformers:
                node=deformers[v[1]]
                if node.props[2].value=='Cluster':clusters.append(node)
        if not clusters:continue
        vertices={}
        for index,cluster in enumerate(clusters):
            ids=cluster.child('Indexes');weights=cluster.child('Weights')
            if ids is None and weights is None:continue
            if ids is None or weights is None:raise ValueError('Incomplete cluster')
            vi=ids.props[0].value;vw=weights.props[0].value
            if len(vi)!=len(vw):raise ValueError('Influence extent mismatch')
            for vertex,weight in zip(vi,vw):
                if not math.isfinite(weight) or weight<0:raise ValueError('Non-finite/negative influence')
                vertices.setdefault(vertex,[]).append((index,weight))
        retained=[[] for _ in clusters]
        for vertex,weights in vertices.items():
            report['max_before']=max(report['max_before'],len(weights));report['vertices']+=1
            if len(weights)>4:report['over_four_before']+=1
            # Stable top-four selection matches the loader's strict-greater insertion.
            top=sorted(weights,key=lambda item:-item[1])[:4]
            total=sum(w for _,w in top)
            if total<=0:raise ValueError('Zero-weight vertex needs author review')
            for index,weight in top:
                if weight>0:retained[index].append((vertex,weight/total))
        for cluster,items in zip(clusters,retained):
            if cluster.child('Indexes') is not None:
                set_array(cluster.child('Indexes'),[v for v,w in items]);set_array(cluster.child('Weights'),[w for v,w in items])
        report['skins']+=1
    kept=[]
    for c in connections.children:
        if len(c.props)>=4 and c.props[3].value=='ShininessExponent':report['removed_ignored_maps']+=1
        else:kept.append(c)
    connections.children=kept
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=Path('console/office/public/models'));parser.add_argument('--output',type=Path,default=Path('tmp/normalized-models'));args=parser.parse_args()
    if args.source.resolve()==args.output.resolve():raise ValueError('Candidates must be separate from originals')
    args.output.mkdir(parents=True,exist_ok=True);results=[]
    for source in sorted(args.source.glob('*.fbx')):
        original=source.read_bytes();doc=Document(original)
        if doc.serialize()!=original:raise ValueError('Lossless round-trip failed: '+source.name)
        report=normalize(doc);candidate=doc.serialize();reparsed=Document(candidate)
        second=normalize(reparsed)
        if second['over_four_before'] or second['max_before']>4 or second['removed_ignored_maps']:raise ValueError('Candidate is not normalized')
        output=args.output/source.name;output.write_bytes(candidate)
        results.append({'file':source.name,'before_sha256':hashlib.sha256(original).hexdigest(),'after_sha256':hashlib.sha256(candidate).hexdigest(),**report})
        print(source.name,json.dumps(report))
    (args.output/'normalization.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
if __name__=='__main__':main()
