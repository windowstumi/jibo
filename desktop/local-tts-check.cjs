// Real NVIDIA component acceptance; uses the installed, authorized target voice.
module.exports=async function checkLocalSpeech(){
  const wait=async(fn,label,timeout=180000)=>{
    const end=Date.now()+timeout;
    while(Date.now()<end){const result=await fn();if(result)return result;await new Promise(r=>setTimeout(r,200));}
    throw Error('Local voice check timed out: '+label);
  };
  navigate('settings');
  await wait(()=>typeof localSpeechStatus==='object','component controls');
  if(!localSpeechStatus.installed)throw Error('Prepare the real local component before this acceptance test');
  $('tts-provider').value='local';$('tts-provider').dispatchEvent(new Event('change'));
  $('local-tts-auto').checked=true;
  await saveLocalSpeech();
  const phases=new Set();let loadingDialog=false,status;
  await wait(async()=>{
    status=await api('/api/local-tts/status');phases.add(status.phase);
    loadingDialog=loadingDialog||$('local-tts-startup').open;
    if(status.phase==='error')throw Error(status.error);
    return status.phase==='ready';
  },'actual model loading and warmup');
  await refreshLocalSpeech();
  const text='你好，本地音色已经准备好了。欢迎来到极播直播间，感谢你的关注。';
  $('local-tts-test-text').value=text;
  const audio=$('local-tts-audio');
  const started=performance.now();$('local-tts-test').click();
  await wait(()=>!audio.hidden&&Number.isFinite(audio.duration)&&audio.currentTime>.1,'actual speech playback',90000);
  const elapsed=(performance.now()-started)/1000;
  const first=new URL(audio.src).pathname;
  const cachedStart=performance.now();const cached=await send('/api/local-tts/test',{text});
  const cacheSeconds=(performance.now()-cachedStart)/1000;
  if(cached.audio!==first)throw Error('The same voice/text was not cached');
  const result={installed:status.installed,ready:status.phase==='ready',loadedVoice:status.loaded_voice,
    phases:[...phases],loadingDialog,played:audio.currentTime>.1,audioSeconds:audio.duration,
    synthesisAndPlaybackSeconds:elapsed,cacheSeconds,cached:true,audio:first,
    provider:(await api('/api/state')).settings.tts.provider};
  audio.pause();$('local-tts-fields').scrollIntoView({block:'center'});
  return result;
};
