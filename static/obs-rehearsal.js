/* OBS renders the videos. This controller only shares the existing speech queue. */
class ObsRehearsal {
  constructor({request,desktop,audio,onStatus=()=>{}}){
    this.request=request;this.desktop=desktop;this.audio=audio;this.onStatus=onStatus;
    this.clientId='desktop-'+crypto.randomUUID();this.active=false;this.serial=0;this.busy=false;
    this.audio.onended=()=>this.finish(false);
    this.audio.onerror=()=>this.finish(true);
  }
  async start(characterId,productId){
    await this.stop();
    await this.desktop.obsSetup(characterId);await this.desktop.obsSpeaking(false);
    await this.request('/api/studio/start',{product_id:productId,character_id:characterId,playback:'desktop-obs'});
    this.characterId=characterId;this.active=true;this.lastTick=Date.now();
    this.timer=setInterval(()=>this.tick(),600);await this.tick();
  }
  async stop(){
    this.active=false;this.serial++;clearInterval(this.timer);
    this.audio.pause();this.audio.removeAttribute('src');this.audio.load();
    this.job=null;this.completed='';this.failed='';
    await this.desktop.obsSpeaking(false).catch(()=>{});
  }
  async finish(failed){
    if(!this.job||!this.active)return;
    this.finishing=true;
    this[failed?'failed':'completed']=this.job.id;this.job=null;
    await this.desktop.obsSpeaking(false).catch(error=>this.onStatus(error.message));
    this.finishing=false;
    if(failed)this.onStatus('音频播放失败，已标记并跳过');
  }
  async play(job){
    const serial=++this.serial;this.job=job;
    try{
      if(job.kind==='action'){
        // Manual actions are queued between utterances; wait their actual duration.
        await this.desktop.obsPresent(job.action);
        await new Promise(resolve=>setTimeout(resolve,(this.assets[job.action]?.duration||3)*1000));
        if(serial===this.serial)await this.finish(false);return;
      }
      this.audio.src=job.audio;
      await this.desktop.obsSpeaking(true);
      if(serial!==this.serial)return;
      if(job.kind==='gift')await this.desktop.obsPresent('thanks');
      if(serial!==this.serial)return;
      await this.audio.play();
      this.onStatus((job.kind==='gift'?'礼物答谢':job.kind==='comment'?'弹幕问答':'商品讲解')+'：'+job.text);
    }catch(error){if(serial===this.serial){await this.finish(true);this.onStatus(error.message);}}
  }
  async tick(){
    if(!this.active||this.busy||this.finishing)return;
    this.busy=true;
    try{
      if(this.desktop.obsStatus && !(await this.desktop.obsStatus()).connected){
        await this.stop();await this.request('/api/studio/stop',{});this.onStatus('OBS已断开，彩排已停止，请重连后开始');return;
      }
      const completed=this.completed||'',failed=this.failed||'';
      const result=await this.request('/api/player/tick',{client_id:this.clientId,role:'desktop-obs',completed,failed});
      this.lastTick=Date.now();
      if(!this.active)return;
      if(!result.runtime.active||result.runtime.character_id!==this.characterId){await this.stop();return;}
      if(!result.owner)throw Error('声音已由另一客户端接管');
      if(this.completed===completed)this.completed='';if(this.failed===failed)this.failed='';
      const job=result.runtime.current;
      if(job && job.id!==this.job?.id && job.id!==this.completed && job.id!==this.failed)void this.play(job);
    }catch(error){
      this.onStatus(error.message);
      if(Date.now()-this.lastTick>5000)await this.stop();
    }finally{this.busy=false;}
  }
}
if(typeof module==='object')module.exports={ObsRehearsal};
