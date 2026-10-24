const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const source=fs.readFileSync(require('node:path').join(__dirname,'../chrome_extension/background.js'),'utf8');
function setup({failPrepare=false,failCommit=false,offline=false,item={}}={}) {
  const calls=[], store={enabled:true,token:'test-key'};
  let download={id:1,url:'https://civitai.red/api/download/models/1',finalUrl:'https://cdn.example.com/model',
    referrer:'https://civitai.red/models/1',filename:'C:\\Models\\one.safetensors',state:'in_progress',paused:false,
    danger:'safe',totalBytes:100,incognito:false,...item};
  const event=()=>({addListener:()=>{}});
  const chrome={
    storage:{local:{get:async keys=>keys===null?{...store}:Object.fromEntries((Array.isArray(keys)?keys:[keys]).map(k=>[k,store[k]])),
      set:async obj=>Object.assign(store,obj),remove:async key=>{delete store[key]}}},
    downloads:{search:async()=>[{...download}],pause:async()=>{calls.push('pause');download.paused=true;},
      resume:async()=>{calls.push('resume');download.paused=false;},
      cancel:async()=>{calls.push('cancel');download.state='interrupted';},onChanged:event()},
    action:{setBadgeText:async()=>{},setBadgeBackgroundColor:async()=>{}},alarms:{create:async()=>{},onAlarm:event()},
    runtime:{id:'a'.repeat(32),onInstalled:event(),onStartup:event(),onMessage:event()}
  };
  const context={chrome,URL,AbortSignal,crypto:webcrypto,console,fetch:async(url,options)=>{
    const action=url.split('/').pop();calls.push(action);
    if(offline)throw new Error('offline');
    const bad=(action==='prepare'&&failPrepare)||(action==='commit'&&failCommit);
    return {ok:!bad,json:async()=>bad?{ok:false,error:'test failure'}:{ok:true}};
  }};
  vm.createContext(context);vm.runInContext(source,context);
  return {context,calls,store,download};
}
(async()=>{
  let t=setup();await t.context.handoff(1);
  assert.deepEqual(t.calls,['pause','ping','prepare','cancel','prepare','commit']);
  assert.equal(t.store.pending_1,undefined);
  t=setup({offline:true});await t.context.handoff(1);assert(!t.calls.includes('cancel'));assert(!t.download.paused);
  t=setup({failPrepare:true});await t.context.handoff(1);assert(t.calls.includes('resume'));assert(!t.calls.includes('cancel'));
  t=setup({failCommit:true});await t.context.handoff(1);assert.equal(t.store.pending_1.phase,'cancelled');assert(!t.calls.includes('resume'));
  t=setup({item:{referrer:'https://example.com',url:'https://example.com/model'}});await t.context.handoff(1);assert.equal(t.calls.length,0);
  t=setup({item:{incognito:true}});await t.context.handoff(1);assert.equal(t.calls.length,0);
  t=setup({item:{paused:true}});await t.context.handoff(1);assert.equal(t.calls.length,0);
  t=setup({item:{filename:'C:\\Models\\evil.exe'}});await t.context.handoff(1);assert.equal(t.calls.length,0);
  t=setup({item:{danger:'dangerous'}});await t.context.handoff(1);assert.equal(t.calls.length,0);
  t=setup();await Promise.all([t.context.handoff(1),t.context.handoff(1)]);assert.equal(t.calls.filter(c=>c==='cancel').length,1);
  t=setup();t.store.pending_1={phase:'prepared',payload:{request_id:'a'.repeat(32)}};t.download.paused=true;
  await t.context.retryPending();assert.deepEqual(t.calls,['resume']);assert.equal(t.store.pending_1,undefined);
  t=setup();t.store.pending_1={phase:'cancelled',payload:{request_id:'a'.repeat(32),filename:'C:\\Models\\one.safetensors'}};
  t.download.state='interrupted';await t.context.retryPending();assert.deepEqual(t.calls,['prepare','commit']);assert.equal(t.store.pending_1,undefined);
  for (const host of ['huggingface.co','civitai.com','civitai.red','modelscope.cn']) {
    t=setup({item:{url:'https://'+host+'/model',referrer:''}});
    await t.context.handoff(1);assert(t.calls.includes('commit'),host);
    t=setup({item:{url:'https://cdn.example.org/file',referrer:'https://'+host+'/model'}});
    await t.context.handoff(1);assert(t.calls.includes('commit'),host+' CDN');
    t=setup({item:{url:'https://'+host+'.evil.org/file',referrer:''}});
    await t.context.handoff(1);assert.equal(t.calls.length,0);
  }
  console.log('24 Chrome handoff scenarios passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
