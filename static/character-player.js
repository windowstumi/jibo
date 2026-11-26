/* Chromium decodes transparent videos; native Web Animations cross-fades two slots.
   No canvas mouth overlay, frame cache, mesh deformation, or inference runtime. */
class CharacterPlayer {
  constructor(host,{onError=()=>{},onState=()=>{}}={}){
    this.host=host;this.onError=onError;this.onState=onState;this.serial=0;
    this.videos=[0,1].map(()=>{
      const video=document.createElement('video');video.muted=true;video.playsInline=true;video.preload='auto';
      video.className='character-video';video.style.opacity='0';host.append(video);return video;
    });
    this.front=this.videos[0];this.kind='';this.speaking=false;this.gestureActive=false;
  }
  async load(card,base){
    this.clear();this.card=card;this.base=base;this.host.dataset.characterId=card.id;
    return this.show('idle');
  }
  async show(requested){
    let kind=requested;
    if(!this.card?.assets[kind] && ['happy','thoughtful'].includes(kind))kind='talk';
    const asset=this.card?.assets[kind];if(!asset)throw Error('角色缺少动作视频：'+kind);
    if(kind===this.kind && asset.loop && !this.front.paused){
      if(this.cancelLoad){
        this.serial++;this.cancelLoad();this.cancelLoad=null;
        for(const video of this.videos){for(const animation of video.getAnimations())animation.cancel();video.style.opacity=video===this.front?'1':'0';if(video!==this.front)video.pause();}
      }
      this.host.dataset.fallback=String(kind!==requested);this.onState({kind,requested,fallback:kind!==requested});
      return {kind,fallback:kind!==requested};
    }
    const serial=++this.serial;this.cancelLoad?.();this.cancelLoad=null;
    this.finishGesture?.(false);this.finishGesture=null;
    const old=this.front,video=this.videos.find(v=>v!==old);
    for(const v of this.videos)for(const animation of v.getAnimations())animation.cancel();
    video.pause();video.style.opacity='0';old.style.opacity=this.kind?'1':'0';
    await new Promise((resolve,reject)=>{
      const cleanup=()=>{clearTimeout(timer);video.removeEventListener('loadeddata',loaded);video.removeEventListener('error',failed);if(this.cancelLoad===cancel)this.cancelLoad=null;};
      const loaded=()=>{cleanup();resolve();};
      const failed=()=>{cleanup();reject(Error('视频无法解码：'+kind));};
      const cancel=()=>{cleanup();resolve();};
      const timer=setTimeout(()=>{cleanup();reject(Error('视频加载超时：'+kind));},8000);
      this.cancelLoad=cancel;video.addEventListener('loadeddata',loaded,{once:true});video.addEventListener('error',failed,{once:true});
      video.loop=asset.loop===true;video.src=this.base+asset.file;video.load();
    });
    if(serial!==this.serial)return {cancelled:true};
    try{await video.play();}catch(error){if(serial!==this.serial)return {cancelled:true};throw error;}
    if(serial!==this.serial)return {cancelled:true};
    this.front=video;this.kind=kind;
    this.gestureActive=asset.loop===false;
    video.onended=()=>{
      if(video!==this.front||video.loop)return;
      this.gestureActive=false;const done=this.finishGesture;this.finishGesture=null;done?.(true);
      this.show(this.speaking?(this.speechKind||'talk'):'idle').catch(error=>this.onError(error.message));
    };
    video.onerror=()=>{if(video===this.front)this.onError('动作视频播放中断，请检查角色素材');};
    this.host.dataset.kind=kind;this.host.dataset.ready='true';this.host.dataset.fallback=String(kind!==requested);
    this.onState({kind,requested,fallback:kind!==requested});
    const fades=[video.animate([{opacity:0},{opacity:1}],{duration:250,fill:'forwards'})];
    if(this.kind)fades.push(old.animate([{opacity:1},{opacity:0}],{duration:250,fill:'forwards'}));
    await Promise.all(fades.map(animation=>animation.finished.catch(()=>{})));
    if(serial===this.serial){video.style.opacity='1';old.style.opacity='0';for(const fade of fades)fade.cancel();old.pause();old.onended=null;old.onerror=null;}
    return {kind,fallback:kind!==requested};
  }
  async gesture(kind,wait=true){
    const result=await this.show(kind);if(result.cancelled)return false;
    if(!wait)return true;
    return new Promise(resolve=>{this.finishGesture=resolve;});
  }
  async beginSpeech(gesture,emotion='talk'){
    this.speaking=true;this.speechKind=emotion;
    if(gesture)return this.gesture(gesture,false);
    if(this.gestureActive)return;
    return this.show(emotion);
  }
  endSpeech(){this.speaking=false;if(!this.gestureActive)return this.show('idle');return Promise.resolve();}
  async reset(){this.speaking=false;this.gestureActive=false;return this.card?this.show('idle'):null;}
  clear(){
    this.serial++;this.cancelLoad?.();this.cancelLoad=null;
    this.finishGesture?.(false);this.finishGesture=null;this.kind='';this.speaking=false;this.gestureActive=false;
    this.host.dataset.ready='false';
    for(const video of this.videos){
      for(const animation of video.getAnimations())animation.cancel();
      video.pause();video.onended=video.onerror=null;video.removeAttribute('src');video.load();video.style.opacity='0';
    }
  }
  destroy(){this.clear();for(const video of this.videos)video.remove();}
}
if(typeof module==='object')module.exports={CharacterPlayer};
