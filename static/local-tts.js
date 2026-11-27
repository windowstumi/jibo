/* UI for the optional, independently installed NVIDIA speech component. */
let localSpeechStatus, localSpeechDismissed=false, localSpeechTimer;

function localSpeechSettings(){
  return {voice_id:$('local-tts-voice').value||'cao',auto_load:$('local-tts-auto').checked,
    speed:Number($('local-tts-speed').value),package_index:$('local-tts-index').value};
}
function localSpeechVisibility(){
  const local=$('tts-provider').value==='local';
  $('local-tts-fields').hidden=!local;
  $('tts-api-fields').hidden=$('tts-provider').value!=='compatible';
  for(const id of ['tts-voice','tts-rate']){
    $(id).hidden=local;document.querySelector(`label[for="${id}"]`).hidden=local;
  }
  $('voice-platform-hint').parentElement.hidden=local;
}
function setSpeechProgress(element,progress){
  if(typeof progress==='number')element.value=progress;else element.removeAttribute('value');
}
function renderLocalSpeech(status){
  localSpeechStatus=status;
  if(typeof renderWorkspace==='function')renderWorkspace(status);
  const active=['installing','loading','warming'].includes(status.phase);
  let message=status.error||status.message;
  if(status.total_bytes){
    const mb=value=>(value/1048576).toFixed(1);
    message+=` · ${mb(status.downloaded_bytes)} / ${mb(status.total_bytes)} MB`;
  }
  $('local-tts-status').textContent=message;
  $('local-tts-status').classList.toggle('error',status.phase==='error');
  $('local-tts-progress').hidden=!active;
  setSpeechProgress($('local-tts-progress'),status.progress);
  $('local-tts-install').disabled=active||!status.supported;
  $('local-tts-load').disabled=active||!status.installed||!status.supported;
  $('local-tts-test').disabled=status.phase!=='ready'||status.loaded_voice!==$('local-tts-voice').value;
  const select=$('local-tts-voice'),previous=select.value;
  const voices=status.voices.length?status.voices:[{id:'cao',name:'尚未导入音色包'}];
  const signature=JSON.stringify(voices);
  if(select.dataset.voices!==signature){
    select.replaceChildren(...voices.map(voice=>new Option(voice.name,voice.id)));
    select.dataset.voices=signature;
    select.value=voices.some(voice=>voice.id===previous)?previous:(state?.settings.local_tts.voice_id||voices[0].id);
  }
  const dialog=$('local-tts-startup');
  if(state?.settings.tts.provider==='local'&&active&&!localSpeechDismissed){
    $('local-tts-startup-message').textContent=message;
    setSpeechProgress($('local-tts-startup-progress'),status.progress);
    if(!dialog.open)dialog.showModal();
  }else if(dialog.open){dialog.close();}
  if(status.phase==='ready')localSpeechDismissed=false;
}
async function refreshLocalSpeech(){
  try{renderLocalSpeech(await api('/api/local-tts/status'));}catch(error){$('local-tts-status').textContent=error.message;}
}
async function saveLocalSpeech(){
  await send('/api/settings',{tts:{provider:'local'},local_tts:localSpeechSettings()},'PUT');
  await refresh();
}
$('tts-provider').addEventListener('change',localSpeechVisibility);
$('local-tts-background').onclick=()=>{localSpeechDismissed=true;$('local-tts-startup').close();};
$('local-tts-startup').addEventListener('cancel',()=>{localSpeechDismissed=true;});
$('local-tts-install').onclick=()=>busy($('local-tts-install'),'正在准备…',async()=>{
  localSpeechDismissed=false;
  await saveLocalSpeech();
  renderLocalSpeech(await send('/api/local-tts/install',{}));
  await refreshLocalSpeech();
});
$('local-tts-load').onclick=()=>busy($('local-tts-load'),'加载中…',async()=>{
  localSpeechDismissed=false;
  await saveLocalSpeech();
  renderLocalSpeech(await send('/api/local-tts/start',{}));
});
$('local-tts-import').onchange=async()=>{
  const input=$('local-tts-import'),file=input.files[0];if(!file)return;
  if(file.size>600000000){toast('音色包不能超过600MB',true);input.value='';return;}
  try{
    const form=new FormData();form.append('file',file);
    const voice=await api('/api/local-tts/voices/import',{method:'POST',body:form});
    await refreshLocalSpeech();$('local-tts-voice').value=voice.id;
    toast('音色已导入，请点击“加载所选音色”');
  }catch(error){toast(error.message,true);}finally{input.value='';}
};
$('local-tts-voice').onchange=()=>{if(localSpeechStatus)renderLocalSpeech(localSpeechStatus);};
$('local-tts-test').onclick=()=>busy($('local-tts-test'),'正在合成…',async()=>{
  await saveLocalSpeech();
  const result=await send('/api/local-tts/test',{text:$('local-tts-test-text').value});
  $('local-tts-audio').src=result.audio;$('local-tts-audio').hidden=false;
  await $('local-tts-audio').play();
});
window.addEventListener('studio-event',event=>{
  if(event.detail.type==='local-tts')renderLocalSpeech(event.detail.data);
});
// app.js initializes state asynchronously. Do not reset a customer's edits on polls.
(async()=>{
  while(typeof state==='undefined'||!state)await new Promise(resolve=>setTimeout(resolve,100));
  const cfg=state.settings.local_tts;
  $('local-tts-speed').value=cfg.speed;$('local-tts-auto').checked=cfg.auto_load;
  $('local-tts-index').value=cfg.package_index;
  await refreshLocalSpeech();$('local-tts-voice').value=cfg.voice_id;
  localSpeechVisibility();
  localSpeechTimer=setInterval(refreshLocalSpeech,1500);
})();
