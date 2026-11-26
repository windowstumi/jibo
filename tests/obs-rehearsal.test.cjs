const test=require('node:test');
const assert=require('node:assert/strict');
const {ObsRehearsal}=require('../static/obs-rehearsal.js');

function fixture(){
  const calls=[];
  const audio={pause(){calls.push('pause');},removeAttribute(){},load(){},async play(){calls.push('play');}};
  const desktop={async obsSpeaking(value){calls.push(value?'talk':'idle');},async obsPresent(kind){calls.push(kind);}};
  const player=new ObsRehearsal({audio,desktop,request:async()=>({owner:true,runtime:{active:true,character_id:'character',current:null}})});
  player.active=true;player.characterId='character';player.lastTick=Date.now();return {player,audio,calls,desktop};
}

test('gift audio and native motion share lifecycle, stop cancels pending audio',async()=>{
  const {player,audio,calls,desktop}=fixture();
  await player.play({id:'gift',kind:'gift',audio:'/gift.wav',text:'谢谢'});
  assert.deepEqual(calls,['talk','thanks','play']);
  await audio.onended();assert.equal(player.completed,'gift');assert.equal(calls.at(-1),'idle');
  let release;desktop.obsSpeaking=()=>new Promise(resolve=>{release=resolve;});
  const pending=player.play({id:'late',kind:'comment',audio:'/late.wav',text:'回复'});
  const oldRelease=release;desktop.obsSpeaking=async()=>{};
  await player.stop();oldRelease();await pending;
  assert.equal(calls.filter(value=>value==='play').length,1);
});

test('late heartbeat cannot replay an utterance that ended during its request',async()=>{
  const {player}=fixture();const job={id:'once',kind:'comment',audio:'/reply.wav',text:'回复'};
  player.job=job;
  player.request=async()=>{await player.finish(false);return {owner:true,runtime:{active:true,character_id:'character',current:job}};};
  let played=false;player.play=async()=>{played=true;};await player.tick();assert.equal(played,false);
});
