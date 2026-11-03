import { CanvasTexture, SRGBColorSpace } from 'three';

export const CITY_TEXTURE_SIZE = [1024, 512] as const;

/** Restrained architectural illustration: a distant, hazy blue-hour city.
 * One static texture, no animation, external requests or additional scene meshes.
 * Buildings use coherent facade bands rather than random yellow window dots.
 */
export function paintCity(ctx:CanvasRenderingContext2D) {
  const [w,h]=CITY_TEXTURE_SIZE;
  const sky=ctx.createLinearGradient(0,0,0,h);
  sky.addColorStop(0,'#172A3B');sky.addColorStop(.65,'#697F8E');sky.addColorStop(1,'#9AA9AC');
  ctx.fillStyle=sky;ctx.fillRect(0,0,w,h);
  const distant=[[0,110,115],[84,90,150],[164,105,128],[255,80,178],[320,116,140],[425,98,187],[510,105,156],[604,84,133],[675,140,192],[790,96,144],[875,100,164],[952,94,120]];
  ctx.fillStyle='#526B7B';
  for(const [x,width,height] of distant)ctx.fillRect(x,410-height,width,height+102);
  const foreground=[[25,94,190],[152,74,224],[278,116,165],[446,88,260],[590,110,194],[759,102,234],[910,94,172]];
  for(const [x,width,height] of foreground){
    const y=445-height;
    const facade=ctx.createLinearGradient(x,0,x+width,0);
    facade.addColorStop(0,'#334C5D');facade.addColorStop(.72,'#3D5666');facade.addColorStop(1,'#293F50');
    ctx.fillStyle=facade;ctx.fillRect(x,y,width,height+67);
    ctx.fillStyle='#738793';ctx.globalAlpha=.22;
    for(let floor=y+12;floor<445;floor+=12)ctx.fillRect(x+5,floor,width-10,2);
    ctx.globalAlpha=.17;ctx.fillStyle='#A6B4B9';ctx.fillRect(x+width*.72,y,2,height);
    ctx.globalAlpha=1;ctx.fillStyle='#304757';ctx.fillRect(x+width*.35,y-6,width*.3,6);
  }
  const haze=ctx.createLinearGradient(0,280,0,h);
  haze.addColorStop(0,'rgba(148,169,178,0)');haze.addColorStop(1,'rgba(148,169,178,0.46)');
  ctx.fillStyle=haze;ctx.fillRect(0,280,w,h-280);
}

export function createCityTexture():CanvasTexture {
  const canvas=document.createElement('canvas');[canvas.width,canvas.height]=CITY_TEXTURE_SIZE;
  const ctx=canvas.getContext('2d');if(ctx)paintCity(ctx);
  const texture=new CanvasTexture(canvas);texture.colorSpace=SRGBColorSpace;return texture;
}
