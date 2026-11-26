const test=require('node:test');
const assert=require('node:assert/strict');
const {ObsClient}=require('../desktop/obs-client.cjs');

test('OBS adapter uses existing media/transition requests and restricts endpoints',async()=>{
  const calls=[];
  const client={disconnect:async()=>{},connect:async()=>{},on:()=>{},call:async(kind,data)=>{
    calls.push({kind,data});
    if(kind==='GetVersion')return {obsVersion:'test'};
    if(kind==='GetSceneTransitionList')return {transitions:[{transitionKind:'fade_transition',transitionName:'淡化'}]};
    return {};
  }};
  const obs=new ObsClient(client);
  await assert.rejects(obs.connect({url:'ws://example.com:4455'}));
  await obs.connect({url:'ws://127.0.0.1:4455'});obs.scenes={idle:'极播-idle',talk:'极播-talk'};
  await obs.present('talk');
  assert.equal(calls.find(c=>c.kind==='SetCurrentProgramScene').data.sceneName,'极播-talk');
  assert.equal(calls.find(c=>c.kind==='SetCurrentSceneTransitionDuration').data.transitionDuration,250);
  await assert.rejects(obs.present('missing'));
  assert.equal(calls.some(c=>['StartStream','StopStream','RemoveScene'].includes(c.kind)),false);
});

test('unreviewed characters cannot be configured for production OBS output',async()=>{
  const obs=new ObsClient({});obs.connected=true;
  await assert.rejects(obs.setup({accepted:false},'/unused'),/验收/);
});

test('one-shot media completion returns to talk during speech, otherwise idle',async()=>{
  const handlers={};const client={on:(event,fn)=>handlers[event]=fn};const obs=new ObsClient(client);
  obs.scenes={thanks:'thanks-scene',talk:'talk-scene',idle:'idle-scene'};obs.assets={thanks:{loop:false}};
  const selected=[];obs.present=async kind=>{selected.push(kind);obs.current=kind;};
  obs.current='thanks';obs.speaking=true;
  handlers.MediaInputPlaybackEnded({inputName:'other-video'});assert.equal(selected.length,0);
  handlers.MediaInputPlaybackEnded({inputName:'thanks-scene-video'});assert.deepEqual(selected,['talk']);
  obs.current='thanks';obs.speaking=false;
  handlers.MediaInputPlaybackEnded({inputName:'thanks-scene-video'});assert.deepEqual(selected,['talk','idle']);
});

test('missing optional emotion uses neutral talk, gestures never fall back to speech',async()=>{
  const calls=[];const client={on:()=>{},call:async(kind,data)=>{
    calls.push({kind,data});
    if(kind==='GetSceneTransitionList')return {transitions:[{transitionKind:'fade_transition',transitionName:'Fade'}]};
    return {};
  }};
  const obs=new ObsClient(client);obs.connected=true;obs.scenes={idle:'idle',talk:'neutral',happy:'happy'};
  let result=await obs.present('happy');assert.equal(result.kind,'happy');assert.equal(result.fallback,false);
  delete obs.scenes.happy;
  for(const kind of ['happy','thoughtful']){
    result=await obs.present(kind);assert.equal(result.kind,'talk');assert.equal(result.requested,kind);assert.equal(result.fallback,true);
    assert.equal(obs.current,'talk');assert.equal(calls.at(-1).data.sceneName,'neutral');
  }
  await assert.rejects(obs.present('greeting'));await assert.rejects(obs.present('missing'));
});
