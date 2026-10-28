const {test}=require('node:test'),assert=require('node:assert/strict'),E=require('../portable/portable-engine.js');
test('browser exact constants have independent known prefixes and no shared pi cache identity',()=>{
 for(const [name,spec] of Object.entries(E.NUMBER_INFO))for(const count of [1,2,17,50,1000]){
  const value=E.computeConstant(count,name);assert.equal(value.length,count);assert(value.startsWith(spec.prefix.slice(0,Math.min(50,count))),name);
 }
 assert.notEqual(E.computeConstant(1000,'pi'),E.computeConstant(1000,'e'));
 assert.throws(()=>E.computeConstant(0,'e'));assert.throws(()=>E.computeConstant(50,'../pi'));
});
test('integer square root digits satisfy the exact defining inequalities',()=>{
 const scale=10n**1000n;
 for(const name of ['sqrt2','sqrt3','sqrt5']){
  const spec=E.NUMBER_INFO[name],integer=BigInt(spec.integer+E.computeConstant(1000,name)),target=BigInt(spec.radicand)*scale*scale;
  assert(integer*integer<=target);assert((integer+1n)*(integer+1n)>target);
 }
});
test('100000 decimal digits match independent MPFR and native packed-output validation',()=>{
 const crypto=require('node:crypto'),expected={e:'f86e954468fc3d99e925acadc0b84060012c60632a5120fa1bfa95e05f27d140',sqrt2:'d49f0faf72cdafe891d8282a27e6b1eb3cbe3b007bad88c94f4dcb3d7e72688f',phi:'21c029788bde43aa9fe81fb9838c3100f53576e668439d0c6dd46352bedc5f59'};
 for(const [constant,hash] of Object.entries(expected))assert.equal(crypto.createHash('sha256').update(E.computeConstant(100000,constant)).digest('hex'),hash,constant);
});
