/* A complete character texture is deformed once. Background never shares its mesh. */
(function(global) {
  'use strict';
  const vertex=`
  attribute vec2 aPosition;
  varying vec2 vUV;
  uniform vec2 uScale;
  uniform vec4 uHead;
  uniform vec4 uBody;
  uniform vec4 uMotion;
  uniform highp float uTime;
  void main(){
    vec2 p=aPosition;vUV=p;
    float hx=uHead.x, hy=uHead.y, neck=uHead.z, fw=uHead.w;
    float headWeight=1.0-smoothstep(neck-.025,neck+.08,p.y);
    float bodyWeight=1.0-smoothstep(neck,uBody.x,p.y);
    float angle=uMotion.x*headWeight;
    vec2 q=p-vec2(hx,neck);
    vec2 rotated=vec2(cos(angle)*q.x-sin(angle)*q.y,sin(angle)*q.x+cos(angle)*q.y);
    p+=rotated-q;
    float hairSides=smoothstep(fw*.25,fw*.9,abs(aPosition.x-hx));
    float hairHeight=(1.0-smoothstep(neck,neck+.10,aPosition.y))*smoothstep(hy-.06,neck,aPosition.y);
    p.x+=sin(uTime*1.5+aPosition.y*10.0)*uMotion.y*.010*hairSides*hairHeight;
    p.x+=(aPosition.x-hx)*uMotion.z*.012*bodyWeight;
    p.y-=uMotion.z*.004*bodyWeight;
    p.x+=uMotion.w*.025*bodyWeight;
    p.y+=abs(uMotion.w)*.012*bodyWeight;
    gl_Position=vec4((p.x-.5)*2.0*uScale.x,(.5-p.y)*2.0*uScale.y,0,1);
  }`;
  const fragment=`
  precision mediump float;
  varying vec2 vUV;
  uniform sampler2D uNeutral;
  uniform sampler2D uSpeaking;
  uniform sampler2D uBlink;
  uniform sampler2D uCloth;
  uniform float uWind;
  uniform highp float uTime;
  uniform vec4 uFace;
  uniform vec2 uExpression;
  void main(){
    vec2 uv=vUV;
    float cloth=texture2D(uCloth,vUV).r;
    vec2 flow=vec2(sin(uTime*1.6+uv.y*13.0)*.008,sin(uTime*2.1+uv.x*20.0)*.002)*uWind*cloth;
    vec2 source=uv+flow;
    // Both destination and source must be cloth. No vertex displacement can pull the legs.
    float sourceCloth=texture2D(uCloth,source).r;
    float fabric=cloth*smoothstep(.05,.5,sourceCloth);
    vec4 original=texture2D(uNeutral,uv);
    vec4 flowed=texture2D(uNeutral,source);
    vec4 base=vec4(mix(original.rgb,flowed.rgb,fabric),original.a);
    vec4 talk=texture2D(uSpeaking,vUV);
    vec4 shut=texture2D(uBlink,vUV);
    float width=uFace.w;
    vec2 mouthD=(vUV-vec2(uFace.x,uFace.z))/vec2(width*.38,width*.31);
    vec2 eyeD=(vUV-vec2(uFace.x,uFace.y))/vec2(width*.72,width*.24);
    float mouthMask=1.0-smoothstep(.55,1.0,length(mouthD));
    float eyeMask=1.0-smoothstep(.65,1.0,length(eyeD));
    vec3 c=base.rgb+(talk.rgb-base.rgb)*mouthMask*uExpression.x*step(.7,talk.a)+(shut.rgb-base.rgb)*eyeMask*uExpression.y*step(.7,shut.a);
    gl_FragColor=vec4(clamp(c,0.0,1.0),base.a);
  }`;

  function shader(gl,type,source){
    const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);
    if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));
    return s;
  }
  function image(url){return new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('无法读取场景素材'));im.src=url;});}

  class SceneRenderer {
    constructor(canvas){
      this.canvas=canvas;
      this.gl=canvas.getContext('webgl',{alpha:true,premultipliedAlpha:false,antialias:true,preserveDrawingBuffer:false});
      if(!this.gl)throw Error('当前设备无法创建 WebGL 场景，请检查显卡驱动');
      const gl=this.gl;
      this.program=gl.createProgram();
      gl.attachShader(this.program,shader(gl,gl.VERTEX_SHADER,vertex));
      gl.attachShader(this.program,shader(gl,gl.FRAGMENT_SHADER,fragment));gl.linkProgram(this.program);
      if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw Error('场景着色器无法初始化：'+gl.getProgramInfoLog(this.program));
      this.uniforms={};for(const name of ['uScale','uHead','uBody','uMotion','uTime','uFace','uExpression','uNeutral','uSpeaking','uBlink','uCloth','uWind'])this.uniforms[name]=gl.getUniformLocation(this.program,name);
      this.bgCanvas=document.createElement('canvas');this.bgCanvas.className='scene-background';
      canvas.parentNode.insertBefore(this.bgCanvas,canvas);this.bg=this.bgCanvas.getContext('2d');
      this.textures=[];this.ready=false;this.open=0;this.wind=0;this.windVelocity=0;this.start=performance.now();this.last=this.start;this.frames=0;this.fps=0;this.fpsTime=this.start;
      this.onContextLost=e=>{e.preventDefault();this.ready=false;this.error='显卡上下文丢失，请重新打开播出窗口';};
      canvas.addEventListener('webglcontextlost',this.onContextLost);
    }
    async load(model,base){
      this.ready=false;this.model=model;this.rig={...model.rig};this.error=null;
      const gl=this.gl;
      if(!model.textures.cloth_mask)throw Error('场景缺少衣料遮罩，请先本地更新绑定');
      const suffix='?v='+encodeURIComponent(model.revision||'1');
      const [neutral,speaking,blink,background,cloth]=await Promise.all(['neutral','speaking','blink','background','cloth_mask'].map(n=>image(base+model.textures[n]+suffix)));
      this.background=background;
      for(const t of this.textures)gl.deleteTexture(t);this.textures=[];
      for(const [i,im] of [neutral,speaking,blink,cloth].entries()){
        const tex=gl.createTexture();this.textures.push(tex);gl.activeTexture(gl.TEXTURE0+i);gl.bindTexture(gl.TEXTURE_2D,tex);
        gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
        gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,im);
      }
      const cols=Math.min(60,Math.max(8,model.mesh.columns)),rows=Math.min(80,Math.max(8,model.mesh.rows));
      const vertices=[];
      for(let y=0;y<rows;y++)for(let x=0;x<cols;x++){
        const l=x/cols,r=(x+1)/cols,t=y/rows,b=(y+1)/rows;
        vertices.push(l,t,r,t,l,b,r,t,r,b,l,b);
      }
      if(this.buffer)gl.deleteBuffer(this.buffer);this.buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.STATIC_DRAW);this.count=vertices.length/2;
      this.ready=true;
    }
    draw(now,openness=0,gesture='idle'){
      if(!this.ready)return;
      const gl=this.gl,r=this.rig,dt=Math.min(.05,(now-this.last)/1000||.016);this.last=now;
      const time=(now-this.start)/1000;
      const scale=Math.min(2,window.devicePixelRatio||1),w=Math.max(1,Math.round(this.canvas.clientWidth*scale)),h=Math.max(1,Math.round(this.canvas.clientHeight*scale));
      if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=this.bgCanvas.width=w;this.canvas.height=this.bgCanvas.height=h;}
      const target=Math.sin(time*.75)*r.wind+Math.sin(time*1.63)*r.wind*.28;
      this.windVelocity+=(target-this.wind)*dt*7;this.windVelocity*=Math.exp(-dt*3);this.wind+=this.windVelocity*dt*6;
      this.open+=(Math.min(1,openness)-this.open)*(1-Math.exp(-dt*(openness>this.open?22:13)));
      const blinkPhase=time%4.7;
      const blink=blinkPhase>4.42?Math.max(0,Math.sin((blinkPhase-4.42)/.28*Math.PI)):0;
      const bow=gesture==='gift' || gesture==='thanks'? Math.max(0,Math.sin(time*2.7))*.7 : 0;
      const headAngle=(Math.sin(time*.71)*.018+Math.sin(time*1.9)*this.open*.008)*r.motion+bow*.07;
      const modelAspect=this.model.width/this.model.height,viewAspect=w/h;
      const sy=.94,sx=sy*modelAspect/viewAspect;
      this.drawBackground(time,w,h);
      gl.viewport(0,0,w,h);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);gl.useProgram(this.program);
      gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);
      const a=gl.getAttribLocation(this.program,'aPosition');gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,2,gl.FLOAT,false,0,0);
      gl.uniform2f(this.uniforms.uScale,sx,sy);
      gl.uniform4f(this.uniforms.uHead,r.head_x,r.head_y,r.neck_y,r.face_width);
      gl.uniform4f(this.uniforms.uBody,r.waist_y,r.skirt_y,r.skirt_end||.7,0);
      gl.uniform4f(this.uniforms.uMotion,headAngle,this.wind,Math.sin(time*1.6)*r.breath,bow);
      gl.uniform4f(this.uniforms.uFace,r.head_x,r.eye_y,r.mouth_y,r.face_width);
      gl.uniform2f(this.uniforms.uExpression,this.open,blink);gl.uniform1f(this.uniforms.uTime,time);
      gl.uniform1f(this.uniforms.uWind,this.wind);
      for(let i=0;i<4;i++){gl.activeTexture(gl.TEXTURE0+i);gl.bindTexture(gl.TEXTURE_2D,this.textures[i]);gl.uniform1i(this.uniforms[['uNeutral','uSpeaking','uBlink','uCloth'][i]],i);}
      // One continuous mesh: write straight RGBA once; source-alpha blending here would square edge alpha.
      gl.disable(gl.BLEND);gl.drawArrays(gl.TRIANGLES,0,this.count);
      if(now-this.fpsTime>=1000){this.fps=Math.round(this.frames*1000/(now-this.fpsTime));this.frames=0;this.fpsTime=now;}this.frames++;
      this.diagnostics={fps:this.fps,openness:this.open,wind:this.wind,triangles:this.count/3,gesture};
    }
    drawBackground(time,w,h){
      const ctx=this.bg,r=this.rig;ctx.clearRect(0,0,w,h);
      if(this.transparent)return;
      const im=this.background,fill=Math.max(w/im.width,h/im.height)*1.04;
      const iw=im.width*fill,ih=im.height*fill;
      ctx.drawImage(im,(w-iw)/2+Math.sin(time*.15)*w*.008*r.background_motion,(h-ih)/2+Math.cos(time*.13)*h*.005*r.background_motion,iw,ih);
      const glow=ctx.createRadialGradient(w*(.3+.05*Math.sin(time*.13)),h*.17,0,w*.4,h*.2,w*.9);
      glow.addColorStop(0,`rgba(255,243,200,${.08*r.background_motion})`);glow.addColorStop(1,'rgba(255,255,255,0)');ctx.fillStyle=glow;ctx.fillRect(0,0,w,h);
      for(let i=0;i<22;i++){
        const speed=.008+(i%5)*.002;
        const x=((i*.6180339+time*speed*r.particles)%1)*w,y=((i*.381966-time*.013*r.particles)%1+1)%1*h;
        ctx.globalAlpha=(.1+.2*Math.sin(time+i)**2)*r.particles;ctx.fillStyle='#fff9df';ctx.beginPath();ctx.ellipse(x,y,1.5+(i%3),1.5+(i%3),0,0,Math.PI*2);ctx.fill();
      }
      ctx.globalAlpha=1;
    }
    destroy(){for(const tex of this.textures)this.gl.deleteTexture(tex);if(this.buffer)this.gl.deleteBuffer(this.buffer);this.gl.deleteProgram(this.program);this.bgCanvas.remove();this.canvas.removeEventListener('webglcontextlost',this.onContextLost);}
  }
  global.SceneRenderer=SceneRenderer;
})(window);
