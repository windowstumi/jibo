// Opt-in acceptance against the target role, configured cloud, and real speech.
module.exports=async function checkInteraction(){
  const wait=async(fn,label,timeout=120000)=>{const end=Date.now()+timeout;while(Date.now()<end){const value=await fn();if(value)return value;await new Promise(r=>setTimeout(r,100));}throw Error('Interaction check timeout: '+label);};
  const frame=()=>document.getElementById('studio-preview').contentDocument;
  const audio=()=>frame()?.getElementById('stage-audio');
  const host=()=>frame()?.getElementById('character-videos');
  const stateNow=()=>api('/api/state');
  const result={};
  await refresh();navigate('studio');
  const initial=await stateNow();if(initial.runtime.active)throw Error('Test must begin without narration or playback');
  const card=selectedStudioCard();if(!card?.accepted)throw Error('Expected an accepted real role card');
  const question='很高兴认识你！今天有什么让人开心又轻松的小事可以分享吗？';
  document.querySelector('[data-event-kind="comment"]').click();
  document.getElementById('sim-user').value='测试';document.getElementById('sim-text').value=question;
  const form=document.getElementById('simulate-form');form.requestSubmit(form.querySelector('[type="submit"]'));
  const first=await wait(async()=>{
    const s=await stateNow(),row=s.events.find(e=>e.content===question);
    if(row&&['error','skipped'].includes(row.status))throw Error(row.reason);
    if(s.runtime.current?.event_id===row?.id&&audio()?.currentTime>.1&&!audio().paused)return {state:s,event:row,job:s.runtime.current};
  },'cloud reply, actual sound and automatic interaction preview');
  if(first.state.runtime.mode!=='interaction')throw Error('Lab test started product narration');
  const subtitle=frame().getElementById('subtitle');
  if(subtitle.classList.contains('hidden')||frame().getElementById('subtitle-text').textContent!==first.job.text)throw Error('Caption belongs to a different turn');
  if(!new URL(audio().currentSrc).pathname.endsWith(first.job.audio))throw Error('Speech belongs to a different turn');
  const expected=first.job.gesture||(card.assets[first.job.emotion]?first.job.emotion:'talk');
  if(host().dataset.kind!==expected)throw Error('Animation does not match the reviewed reply delivery');
  result.autoStarted=true;result.captionAndSpeech=true;result.delivery={tone:first.job.tone,emotion:first.job.emotion,gesture:first.job.gesture,actualVideo:host().dataset.kind};
  result.reply=first.job.text;result.replyAudio=first.job.audio;result.replySeconds=audio().duration;
  const gift=await send('/api/simulate',{kind:'gift',username:'测试',gift:'鲜花',count:1});
  await wait(async()=>{const s=await stateNow();return s.events.find(e=>e.id===first.event.id)?.status==='done';},'first turn ended after its motion');
  const giftJob=await wait(async()=>{const s=await stateNow();return s.runtime.current?.event_id===gift.event_id&&audio()?.currentTime>.1&&!audio().paused?s.runtime.current:null;},'gift speech and nod');
  if(host().dataset.kind!=='thanks'||giftJob.gesture!=='thanks')throw Error('Gift did not use its own thanks clip');
  result.giftAudio=giftJob.audio;result.giftSeconds=audio().duration;
  // Only this isolated test configuration is changed; no extra paid request for the next turn.
  await send('/api/settings',{interaction:{allow_chat:false},llm:{clear_key:true}},'PUT');
  const next=await send('/api/simulate',{kind:'comment',username:'测试',text:'可以放洗碗机吗？'});
  await wait(()=>audio()?.ended&&host()?.dataset.kind==='thanks','short gift speech ended before the real nod');
  const during=await stateNow();
  if(during.runtime.current?.event_id!==gift.event_id||!frame().getElementById('subtitle').classList.contains('hidden'))throw Error('Next turn started before the gift motion ended');
  result.motionFence=true;
  const neutral=await wait(async()=>{const s=await stateNow();return s.runtime.current?.event_id===next.event_id&&audio()?.currentTime>.1&&!audio().paused?s.runtime.current:null;},'next neutral reply');
  if(host().dataset.kind!=='talk'||neutral.gesture!==null||frame().getElementById('subtitle-text').textContent!==neutral.text)throw Error('Previous gesture leaked into neutral speech');
  result.neutralTurn=true;result.neutralAudio=neutral.audio;
  await wait(async()=>{const s=await stateNow();return s.events.find(e=>e.id===next.event_id)?.status==='done'&&host()?.dataset.kind==='idle';},'natural idle without product narration');
  result.idleAfterSpeech=true;await send('/api/studio/stop',{});return result;
};
