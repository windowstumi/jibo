/* One silent clip between utterances; the live renderer keeps its own clock. */
(function(global) {
  'use strict';
  const smooth=t=>{t=Math.max(0,Math.min(1,t));return t*t*(3-2*t);};
  class ActionPlayer {
    constructor({video,now=()=>performance.now(),onError=()=>{}}={}) {
      this.video=video||document.createElement('video');this.now=now;this.onError=onError;
      this.video.muted=true;this.video.playsInline=true;this.video.preload='auto';this.video.loop=false;
      this.phase='idle';this.mix=0;this.motion=1;this.serial=0;
    }
    async play(clip) {
      this.cancel();
      if(!clip)return false;
      const serial=this.serial;this.clip=clip;this.ok=true;this.exitMix=1;this.resumeMotion=0;this.phase='loading';this.since=this.now();
      return new Promise(resolve=>{
        this.resolve=resolve;
        this.video.onloadeddata=()=>{
          if(serial!==this.serial||this.phase!=='loading')return;
          if(!Number.isFinite(this.video.duration)||this.video.duration<1||this.video.duration>8.1||
             Math.abs(this.video.duration-clip.duration)>.3||this.video.videoWidth!==clip.width||this.video.videoHeight!==clip.height) {
            this.fail('动作视频的时长或尺寸与导入记录不一致');return;
          }
          this.video.pause();this.phase='settle';this.since=this.now();
        };
        this.video.onended=()=>{if(serial===this.serial&&this.phase==='playing'){this.phase='exit';this.since=this.now();}};
        this.video.onerror=()=>{if(serial===this.serial)this.fail('动作视频无法解码，已恢复实时角色并继续语音');};
        this.video.src=clip.url;this.video.load();
      });
    }
    update(now=this.now()) {
      const t=(now-this.since)/400;
      if(this.phase==='loading'&&now-this.since>5000)this.fail('动作视频加载超时，已跳过动作');
      else if(this.phase==='settle') {
        this.motion=1-smooth(t);
        if(t>=1){this.phase='enter';this.since=now;this.motion=0;}
      } else if(this.phase==='enter') {
        this.mix=smooth(t);
        if(t>=1){
          this.mix=1;this.phase='playing';this.since=now;
          const serial=this.serial;
          try{Promise.resolve(this.video.play()).catch(()=>{if(serial===this.serial)this.fail('动作播放被阻止，已跳过动作');});}
          catch{this.fail('动作播放被阻止，已跳过动作');}
        }
      } else if(this.phase==='playing'&&now-this.since>(this.clip.duration+2)*1000) {
        this.fail('动作播放中断，已恢复实时角色');
      } else if(this.phase==='exit') {
        this.mix=this.exitMix*(1-smooth(t));
        if(t>=1){this.mix=0;this.phase='resume';this.resumeMotion=this.motion;this.since=now;}
      } else if(this.phase==='resume') {
        this.motion=this.resumeMotion+(1-this.resumeMotion)*smooth(t);
        if(t>=1)this.finish(true);
      }
      return {video:this.video,mix:this.mix,motion:this.motion,background:this.clip?.background,phase:this.phase};
    }
    fail(message) {
      this.ok=false;this.onError(message);this.video.pause();
      if(this.mix>0){this.exitMix=this.mix;this.phase='exit';this.since=this.now();}
      else if(this.motion<1){this.resumeMotion=this.motion;this.phase='resume';this.since=this.now();}
      else this.finish(false);
    }
    finish(ok) {
      const resolve=this.resolve;this.resolve=null;this.phase='idle';this.mix=0;this.motion=1;
      this.video.pause();this.video.onloadeddata=this.video.onended=this.video.onerror=null;
      resolve?.(ok&&this.ok);
    }
    cancel() {this.serial++;this.finish(false);}
  }
  global.ActionPlayer=ActionPlayer;
  if(typeof module!=='undefined')module.exports={ActionPlayer,smooth};
})(typeof window!=='undefined'?window:globalThis);
