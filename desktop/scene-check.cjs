// Pixel regression executed by the desktop smoke test, never by normal user flows.
module.exports = async function checkScenePixels(model, base) {
  const host=document.createElement('div');
  host.style.cssText='position:fixed;left:-2000px;top:0;width:768px;height:768px';
  const canvas=document.createElement('canvas');canvas.style.cssText='width:768px;height:768px';
  host.appendChild(canvas);document.body.appendChild(host);
  const renderer=new SceneRenderer(canvas);
  try {
    await renderer.load(model,base);
    Object.assign(renderer.rig,{breath:0,motion:0,wind:0});
    const now=performance.now(),h=768,w=768;renderer.start=now-1700;
    const frame=wind=>{
      renderer.wind=wind;renderer.windVelocity=0;renderer.last=now;
      renderer.draw(now,0);
      const pixels=new Uint8Array(w*h*4);
      renderer.gl.readPixels(0,0,w,h,renderer.gl.RGBA,renderer.gl.UNSIGNED_BYTE,pixels);
      return pixels;
    };
    const before=frame(-1),after=frame(1);
    const start=model.rig.skirt_y,end=model.rig.skirt_end;
    let changedLegPixels=0,changedClothPixels=0;
    for(let y=0;y<h;y++){
      const uv=(.5-((y+.5)/h-.5)/.94);
      for(let x=0;x<w;x++){
        const i=(y*w+x)*4;
        const changed=before[i]!==after[i]||before[i+1]!==after[i+1]||before[i+2]!==after[i+2]||before[i+3]!==after[i+3];
        if(changed&&uv>end+.015&&uv<.98)changedLegPixels++;
        if(changed&&uv>start&&uv<end)changedClothPixels++;
      }
    }
    renderer.start=now-500;renderer.wind=0;renderer.windVelocity=0;renderer.last=now;renderer.draw(now,0);
    const neutral=new Uint8Array(w*h*4);renderer.gl.readPixels(0,0,w,h,renderer.gl.RGBA,renderer.gl.UNSIGNED_BYTE,neutral);
    // Old gesture arguments must never restore the removed gift/thanks deformation.
    let legacyNodPixels=0;
    for(const removed of ['gift','thanks']){
      renderer.last=now;renderer.draw(now,0,removed);
      const actual=new Uint8Array(w*h*4);renderer.gl.readPixels(0,0,w,h,renderer.gl.RGBA,renderer.gl.UNSIGNED_BYTE,actual);
      for(let i=0;i<actual.length;i++)if(actual[i]!==neutral[i])legacyNodPixels++;
    }
    return {changedLegPixels,changedClothPixels,legacyNodPixels,independentMouthElements:document.querySelectorAll('#mouth,.mouth,.mouth-demo').length};
  } finally {renderer.destroy();host.remove();}
};
