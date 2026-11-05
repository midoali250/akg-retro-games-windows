import json,urllib.request
ref=json.load(open('engine-reference.json'))
with urllib.request.urlopen('https://raw.githubusercontent.com/midoali250/bitvault-engine/'+ref['commit']+'/'+ref['registry'],timeout=30) as r: registry=json.load(r)
expected={'NES':('libretro/libretro-fceumm','e0f3086a8104f8fbbe49a2615b10401504a9533f'),'SNES':('libretro/snes9x','fae2fea08f74180759ef540ee94259213f503480')}
for system, pair in expected.items():
 rows=[c for c in registry['cores'] if c['system']==system]
 assert len(rows)==1 and (rows[0]['repository'],rows[0]['revision'])==pair,'Core mismatch against pinned BitVault Engine registry'
print('Engine registry verified')
