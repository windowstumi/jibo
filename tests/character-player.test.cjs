const test=require('node:test');
const assert=require('node:assert/strict');
const {CharacterPlayer}=require('../static/character-player.js');

class Video extends EventTarget {
  constructor(){super();this.style={};this.paused=true;this.src='';}
  load(){if(this.src)queueMicrotask(()=>this.dispatchEvent(new Event('loadeddata')));}
  async play(){this.paused=false;}
  pause(){this.paused=true;}
  removeAttribute(){this.src='';}
  getAnimations(){return [];}
  animate(){return {finished:Promise.resolve(),cancel(){}};}
  remove(){}
}
function fixture(){
  global.document={createElement:()=>new Video()};
  const host={dataset:{},append(){}};
  return {host,player:new CharacterPlayer(host)};
}
function card(id='one'){return {id,assets:{idle:{file:'idle.webm',loop:true},talk:{file:'talk.webm',loop:true},thanks:{file:'thanks.webm',loop:false}}};}
const flush=()=>new Promise(resolve=>setImmediate(resolve));

test('native player uses neutral talk fallback and finishes one-shot before idle',async()=>{
  const {host,player}=fixture();await player.load(card(),'/one/');
  await player.beginSpeech(null,'happy');assert.equal(host.dataset.kind,'talk');assert.equal(host.dataset.fallback,'true');
  assert.equal(player.front.muted,true);assert.equal(player.front.loop,true);
  await player.beginSpeech('thanks');await player.endSpeech();assert.equal(player.kind,'thanks');
  player.front.onended();await flush();assert.equal(player.kind,'idle');assert.equal(player.speaking,false);player.destroy();
});
test('switching characters cancels stale media loads and clears both decoders',async()=>{
  const {player}=fixture();const first=player.load(card('one'),'/one/');const second=player.load(card('two'),'/two/');
  assert.equal((await first).cancelled,true);await second;assert.equal(player.card.id,'two');assert.equal(player.front.src,'/two/idle.webm');
  player.destroy();assert.ok(player.videos.every(v=>v.paused&&!v.src));
});
test('stop cancels a pending gesture and missing gestures never become speech',async()=>{
  const {player}=fixture();await player.load(card(),'/one/');
  const pending=player.gesture('thanks');await flush();await player.reset();assert.equal(await pending,false);
  await assert.rejects(player.show('greeting'));assert.equal(player.kind,'idle');player.destroy();
});
