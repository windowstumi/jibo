// Real decoder/queue regression, enabled only by the desktop smoke test.
module.exports = async function checkActions(encoded, sceneId) {
  const request=async(path,options={})=>{
    const res=await fetch(path,options),data=await res.json();
    if(!res.ok)throw Error(JSON.stringify(data));return data;
  };
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  await request('/api/studio/stop',{method:'POST'});
  const blob=new Blob([Uint8Array.from(atob(encoded),c=>c.charCodeAt(0))],{type:'video/webm'});
  const video=document.createElement('video');video.muted=true;video.src=URL.createObjectURL(blob);
  await new Promise((resolve,reject)=>{video.onloadeddata=resolve;video.onerror=reject;});
  const canvas=document.createElement('canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;
  const capture=async time=>{
    await new Promise(resolve=>{video.onseeked=resolve;video.currentTime=time;});
    canvas.getContext('2d').drawImage(video,0,0);
    return new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
  };
  const form=new FormData();form.append('file',blob,'fixture.webm');
  form.append('metadata',JSON.stringify({duration:video.duration,width:video.videoWidth,height:video.videoHeight,background:'green'}));
  form.append('first',await capture(.02),'first.png');form.append('last',await capture(video.duration-.08),'last.png');
  const route='/api/scenes/'+sceneId+'/actions/present';
  const saved=await request(route+'/clip',{method:'POST',body:form});
  URL.revokeObjectURL(video.src);
  await request(route,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:true})});
  await wait(1000);
  const before=sceneRenderer.diagnostics;
  await wait(200);const naturalMotion=sceneRenderer.diagnostics.wind!==before.wind;
  await request('/api/studio/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:'sample-cup'})});
  await request('/api/studio/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'present'})});
  const phases=new Set();let overlap=false,sawClip=false,sawSpeechAfter=false,entryAlpha=0,exitAlpha=0,observedJob='';
  const deadline=performance.now()+30000;
  while(performance.now()<deadline){
    phases.add(actionPlayer.phase);
    if(currentJob?.kind==='action'&&actionPlayer.phase!=='idle'){
      sawClip=true;observedJob=currentJob.id;
      if(!audio.paused)overlap=true;
      if(actionPlayer.phase==='enter'&&actionPlayer.mix>.4&&actionPlayer.mix<.8)entryAlpha++;
      if(actionPlayer.phase==='exit'&&actionPlayer.mix>.2&&actionPlayer.mix<.6)exitAlpha++;
    }
    if(sawClip&&currentJob?.kind==='narration'&&actionPlayer.phase==='idle'&&!audio.paused){sawSpeechAfter=true;break;}
    await wait(25);
  }
  const readyForStop=saved.actions.present;
  const cancelled=actionPlayer.play({...readyForStop,url:'/media/scenes/'+sceneId+'/'+readyForStop.file});
  await wait(1000);stopAudio();const cancelResult=await cancelled;
  await request('/api/studio/stop',{method:'POST'});
  return {naturalMotion,sawClip,sawSpeechAfter,overlap,entryAlpha,exitAlpha,phases:[...phases],cancelled:cancelResult===false&&actionPlayer.phase==='idle',
    glError:sceneRenderer.gl.getError(),owner:isOwner};
};
