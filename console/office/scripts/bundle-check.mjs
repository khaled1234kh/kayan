import fs from 'node:fs';
import assert from 'node:assert/strict';
const dir = new URL('../dist/assets/',import.meta.url);
const chunks=fs.readdirSync(dir).filter(n=>n.endsWith('.js')).map(name=>({name,bytes:fs.statSync(new URL(name,dir)).size}));
assert(chunks.length>=5,'Expected independently cacheable engine/runtime/application chunks');
for (const chunk of chunks) assert(chunk.bytes<=500000,`${chunk.name} exceeds the unchanged 500 kB budget`);
const entry=chunks.find(c=>c.name.startsWith('index-'));
assert(entry && entry.bytes<=100000,'Application entry exceeds 100 kB');
for (const prefix of ['react-','three-engine-','three-shaders-','three-math-','office-runtime-']) {
  assert.equal(chunks.filter(c=>c.name.startsWith(prefix)).length,1,`Expected exactly one ${prefix} chunk`);
}
console.log(JSON.stringify({chunks,totalBytes:chunks.reduce((n,c)=>n+c.bytes,0)},null,2));
