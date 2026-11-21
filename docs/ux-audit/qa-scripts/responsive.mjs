import puppeteer from "puppeteer-core";
const BASE="http://localhost:3100";
const widths=[320,375,390,640,768,820,910,1024,1280,1440,1920];
const routes=["/","/search","/calculators","/species","/study","/universities","/jobs","/scholarships","/login"];
const tag=process.argv[2]||"after";
const b=await puppeteer.launch({executablePath:"C:/Program Files/Google/Chrome/Application/chrome.exe",headless:true,args:["--no-sandbox"]});
const bad4xx=new Map();
const rows=[];
for(const w of widths){
  const p=await b.newPage(); await p.setViewport({width:w,height:800,isMobile:w<500,hasTouch:w<500});
  p.on("response",r=>{if(r.status()>=400){const k=r.status()+" "+r.url().replace(BASE,"");bad4xx.set(k,(bad4xx.get(k)||0)+1)}});
  const row={w,overflow:[],overlap:[],covered:[],smallAuth:[],footer:null};
  for(const r of routes){
    await p.goto(BASE+r,{waitUntil:"networkidle0",timeout:60000}).catch(()=>{});
    const o=await p.evaluate(async()=>{
      const de=document.documentElement; const vis=e=>e&&getComputedStyle(e).display!=="none"&&e.getBoundingClientRect().width>0;
      const top=document.querySelector('nav[aria-label="Primary"]'), bot=document.querySelector('nav[aria-label="Mobile"]');
      const footer=document.querySelector("footer");
      window.scrollTo(0,document.body.scrollHeight); await new Promise(r=>setTimeout(r,50));
      const main=document.querySelector("main"); const kids=[...main.querySelectorAll("*")].filter(e=>e.getBoundingClientRect().height>0);
      const lastBottom=Math.max(...kids.map(e=>e.getBoundingClientRect().bottom));
      const botTop=vis(bot)?bot.getBoundingClientRect().top:Infinity;
      const auth=[...document.querySelectorAll("header a[href='/login'],header a[href='/register']")].map(a=>{const r=a.getBoundingClientRect();return Math.round(r.height)});
      return {over:de.scrollWidth-de.clientWidth,top:vis(top),bot:vis(bot),footer:vis(footer),covered:Math.round(lastBottom-botTop),auth};
    });
    if(o.over>0)row.overflow.push(r+"+"+o.over);
    if(o.top===o.bot)row.overlap.push(r+(o.top?" BOTH":" NEITHER"));
    if(o.covered>0)row.covered.push(r+" "+o.covered+"px");
    if(o.auth.some(h=>h<24))row.smallAuth.push(r+" "+o.auth);
    row.footer=o.footer; row.authH=o.auth[0]; row.nav=o.top?"top":"bottom";
  }
  rows.push(row); await p.close();
  console.log(`${tag} w=${w} nav=${row.nav} footer=${row.footer} authH=${row.authH} overflow=${row.overflow.join(",")||"none"} navConflict=${row.overlap.join(",")||"none"} contentCovered=${row.covered.join(",")||"none"} smallAuth=${row.smallAuth.join(",")||"none"}`);
}
console.log("4xx/5xx responses:"); for(const [k,v] of bad4xx) console.log("  ",v+"x",k);
await b.close();
