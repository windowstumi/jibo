const test=require('node:test');
const assert=require('node:assert/strict');
const {ActionPlayer}=require('../static/action-player.js');

function setup(){
  let now=0;
  const video={duration:2,videoWidth:256,videoHeight:384,readyState:2,plays:0,
    pause(){},load(){},play(){this.plays++;return Promise.resolve();}};
  const errors=[];
  return {video,errors,player:new ActionPlayer({video,now:()=>now,onError:e=>errors.push(e)}),at:t=>now=t};
}
const clip={url:'/clip.webm',duration:2,width:256,height:384,background:'green'};

test('action settles, plays silently, fades out, then releases speech',async()=>{
  const {player,video,at}=setup();let released=false;
  const done=player.play(clip).then(ok=>{released=true;return ok;});
  video.onloadeddata();assert.equal(video.muted,true);
  at(200);assert.equal(player.update(200).motion,.5);assert.equal(video.plays,0);
  at(400);player.update(400);assert.equal(player.phase,'enter');
  at(600);assert.equal(player.update(600).mix,.5);
  at(800);player.update(800);assert.equal(video.plays,1);assert.equal(released,false);
  at(2800);video.onended();assert.equal(player.phase,'exit');
  at(3000);assert.equal(player.update(3000).mix,.5);assert.equal(released,false);
  at(3200);player.update(3200);assert.equal(player.phase,'resume');
  at(3400);assert.equal(player.update(3400).motion,.5);
  at(3600);player.update(3600);assert.equal(await done,true);assert.equal(player.phase,'idle');
});

test('stop or owner loss cancels pending action and cannot release stale speech',async()=>{
  const {player,video,at}=setup();const done=player.play(clip);video.onloadeddata();
  at(800);player.update(400);player.update(800);player.cancel();
  assert.equal(await done,false);assert.equal(player.phase,'idle');assert.equal(player.mix,0);assert.equal(player.motion,1);
});

test('missing, corrupted and stalled video return control instead of blocking queue',async()=>{
  const {player,video,at,errors}=setup();
  const missing=player.play(clip);at(5001);player.update(5001);assert.equal(await missing,false);
  const corrupt=player.play(clip);video.duration=99;video.onloadeddata();assert.equal(await corrupt,false);
  video.duration=2;const stalled=player.play(clip);video.onloadeddata();
  at(5401);player.update(5401);at(5801);player.update(5801);
  at(9900);player.update(9900);at(10300);player.update(10300);at(10700);player.update(10700);
  assert.equal(await stalled,false);assert.equal(errors.length,3);
});

test('decode errors during a transition fade from the current mix without a jump',async()=>{
  const {player,video,at}=setup();const done=player.play(clip);video.onloadeddata();
  at(400);player.update(400);at(600);player.update(600);assert.equal(player.mix,.5);
  video.onerror();assert.equal(player.update(600).mix,.5);
  at(1000);player.update(1000);at(1400);player.update(1400);
  assert.equal(await done,false);assert.equal(player.motion,1);
});
