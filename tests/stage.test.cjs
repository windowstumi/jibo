const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const flush=()=>new Promise(resolve=>setImmediate(resolve));

async function fixture(){
  const calls=[],elements=new Map();let media;
  const element=()=>({hidden:false,dataset:{},textContent:'',classList:{values:new Set(),add(x){this.values.add(x);},remove(x){this.values.delete(x);},toggle(){}},getAttribute(){return '';}});
  const el=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
  class Audio extends EventTarget{
    constructor(){super();media=this;this.readyState=0;this.currentTime=0;this.paused=true;}
    load(){}
    pause(){this.paused=true;}
    async play(){calls.push('audio');this.paused=false;}
  }
  let finishMotion;
  class CharacterPlayer{
    async load(){return {};}
    async beginSpeech(gesture,emotion){calls.push({gesture,emotion});}
    endSpeech(){return new Promise(resolve=>{finishMotion=resolve;});}
    async reset(){calls.push('reset');finishMotion?.(false);}
    destroy(){}
  }
  const parent={postMessage(){}},window={parent,addEventListener(){}};
  const context=vm.createContext({document:{getElementById:el,body:{append(){},classList:{toggle(){}}}},window,parent,
    location:{search:'?mode=inspect&character_id=role',origin:'http://local'},Audio,CharacterPlayer,URLSearchParams,
    crypto:{randomUUID:()=> 'test'},setTimeout,clearTimeout,setInterval,Date,Promise,
    fetch:async url=>({ok:true,json:async()=>url.startsWith('/api/characters/')?{id:'role',name:'真实协议'}:{settings:{avatar:{mode:'character',character_id:'role'}},runtime:{active:false}}})});
  vm.runInContext(fs.readFileSync('static/stage.js','utf8'),context);await flush();
  return {context,calls,el,get audio(){return media;},finish(){finishMotion();},run:code=>vm.runInContext(code,context)};
}
test('subtitles and motion wait for real audio readiness, and completion waits for motion',async()=>{
  const f=await fixture();const pending=f.run("play({id:'reply',kind:'comment',text:'你好',audio:'/voice.wav',gesture:'greeting',emotion:'happy'})");
  await flush();assert.equal(f.calls.some(x=>x==='audio'),false);assert.equal(f.el('subtitle').classList.values.has('hidden'),true);
  f.audio.readyState=3;f.audio.dispatchEvent(new Event('canplay'));await pending;
  assert.deepEqual(f.calls.find(x=>typeof x==='object'),{gesture:'greeting',emotion:'happy'});
  assert.equal(f.el('subtitle-text').textContent,'你好');assert.equal(f.el('subtitle').classList.values.has('hidden'),false);
  const ending=f.audio.onended();await flush();assert.equal(f.run('completed'),'');assert.equal(f.el('subtitle').classList.values.has('hidden'),true);
  f.finish();await ending;assert.equal(f.run('completed'),'reply');
});
test('stop cancels pending audio and a cancelled server job stops its sound and caption',async()=>{
  const f=await fixture();const pending=f.run("play({id:'old',kind:'comment',text:'旧回复',audio:'/old.wav'})");
  f.run('stopAudio()');f.audio.dispatchEvent(new Event('canplay'));await pending;
  assert.equal(f.calls.includes('audio'),false);
  f.context.fetch=async()=>({ok:true,json:async()=>({owner:true,runtime:{active:true,current:null}})});
  f.run("ready=true;active=true;currentId='cancelled';currentJob={id:'cancelled'};audio.paused=false");
  await f.run('tick()');assert.equal(f.audio.paused,true);assert.equal(f.run('currentId'),'');
});
