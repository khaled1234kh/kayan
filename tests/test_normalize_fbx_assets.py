"""Bounded FBX compatibility migration: fail closed and preserve untouched data."""
import hashlib
import struct
import pytest
from scripts.normalize_fbx_assets import Document, Node, Property, HEADER, normalize, set_array

def prop(value):
    if isinstance(value, int):
        return Property(b'L'+struct.pack('<q',value),value,'L')
    data=value.encode()
    return Property(b'S'+struct.pack('<I',len(data))+data,value,'S')

def array(name,values,kind):
    node=Node(name.encode(),[Property(b'',None,kind)])
    set_array(node,values)
    return node

def fixture(weights):
    doc=Document.__new__(Document)
    doc.version=7700;doc.data=HEADER+struct.pack('<I',7700);doc.footer=b'opaque-footer'
    clusters=[Node(b'Deformer',[prop(i+2),prop('bone'),prop('Cluster')],[array('Indexes',[0],'i'),array('Weights',[w],'d')],True) for i,w in enumerate(weights)]
    untouched=Node(b'Geometry',[Property(b'R'+struct.pack('<I',6)+b'opaque',None,'R')])
    doc.nodes=[Node(b'Objects',[],[Node(b'Deformer',[prop(1),prop('skin'),prop('Skin')]),*clusters,untouched],True),
               Node(b'Connections',[],[*(Node(b'C',[prop('OO'),prop(i+2),prop(1)]) for i in range(len(weights))),
                    Node(b'C',[prop('OP'),prop(80),prop(81),prop('ShininessExponent')]),
                    Node(b'C',[prop('OP'),prop(82),prop(81),prop('DiffuseColor')])],True)]
    return doc

def test_binary_roundtrip_and_opaque_property_preserved():
    source=fixture([1]).serialize();doc=Document(source)
    assert doc.serialize()==source
    raw=doc.root('Objects').children[-1].props[0].raw
    normalize(doc)
    assert Document(doc.serialize()).root('Objects').children[-1].props[0].raw==raw

def test_top_four_stable_ties_and_normalization():
    doc=Document(fixture([.2,.2,.2,.2,.2,.1]).serialize())
    result=normalize(doc)
    assert result['over_four_before']==1 and result['max_before']==6
    clusters=doc.root('Objects').children[1:-1]
    assert [c.child('Indexes').props[0].value for c in clusters]==[[0],[0],[0],[0],[],[]]
    assert [c.child('Weights').props[0].value for c in clusters]==[[.25],[.25],[.25],[.25],[],[]]
    assert result['removed_ignored_maps']==1
    assert doc.root('Connections').children[-1].props[-1].value=='DiffuseColor'
    assert normalize(Document(doc.serialize()))['over_four_before']==0

@pytest.mark.parametrize('weights',[[0,0],[-.1,1],[float('nan'),1],[float('inf'),1]])
def test_invalid_weights_refuse_migration(weights):
    with pytest.raises(ValueError):normalize(Document(fixture(weights).serialize()))

@pytest.mark.parametrize('data',[b'not an FBX',HEADER+struct.pack('<I',7400)+bytes(50),HEADER+struct.pack('<I',7700)])
def test_unsupported_or_truncated_input_refused(data):
    with pytest.raises((ValueError,struct.error)):Document(data)

def untouched_payload_digest(doc):
    import json
    result={}
    def walk(node,path):
        for i,p in enumerate(node.props):
            if node.name not in (b'Indexes',b'Weights'):
                result[repr(path+(i,))]=hashlib.sha256(p.raw).hexdigest()
        for i,child in enumerate(node.children):walk(child,path+(child.name,i))
    # Connections are deliberately filtered, causing ordinal shifts.
    for i,node in enumerate(doc.nodes):
        if node.name!=b'Connections':walk(node,(node.name,i))
    return hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def test_unrelated_source_bytes_match_independently_preserved_original_digest():
    from pathlib import Path
    import json
    # A checked-in original-payload fingerprint makes this assertion reproducible
    # in a fresh clone, without skipping or comparing a candidate with itself.
    manifest=json.loads(Path('tests/fixtures/fbx_untouched_payloads.json').read_text(encoding='utf-8'))
    for item in manifest['models']:
        data=(Path('console/office/public/models')/item['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest()==item['after_sha256']
        assert untouched_payload_digest(Document(data))==item['original_untouched_payload_sha256']

@pytest.mark.parametrize('filename',['AIManager.fbx','AIOps.fbx','AISales.fbx','Employee.fbx'])
def test_active_asset_has_no_discarded_map_or_excess_weights(filename):
    from pathlib import Path
    doc=Document((Path('console/office/public/models')/filename).read_bytes())
    result=normalize(doc)
    assert result['removed_ignored_maps']==0
    assert result['over_four_before']==0 and result['max_before']<=4
