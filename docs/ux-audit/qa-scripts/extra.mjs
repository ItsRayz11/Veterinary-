import puppeteer from "puppeteer-core";
const BASE="http://localhost:3100";
const b=await puppeteer.launch({executablePath:"C:/Program Files/Google/Chrome/Application/chrome.exe",headless:true,args:["--no-sandbox"]});
const ok=(n,c,x="")=>console.log(`${c?"PASS":"FAIL"}  ${n}${x?"  ["+x+"]":""}`);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
// A. keyboard focus visibility, desktop + mobile
for(const w of [1280,390]){
  const p=await b.newPage(); await p.setViewport({width:w,height:800});
  await p.goto(BASE+"/",{waitUntil:"networkidle0"});
  const seen=[]; for(let i=0;i<10;i++){ await p.keyboard.press("Tab");
    seen.push(await p.evaluate(()=>{const e=document.activeElement;if(!e||e===document.body)return null;const r=e.getBoundingClientRect();const cs=getComputedStyle(e);
      return {t:(e.textContent||e.getAttribute("aria-label")||"").trim().slice(0,14),outline:cs.outlineStyle!=="none"&&parseFloat(cs.outlineWidth)>0,onscreen:r.bottom>0&&r.top<innerHeight&&r.width>0}})); }
  const bad=seen.filter(s=>!s||!s.outline||!s.onscreen);
  ok(`w=${w} first 10 Tab stops all show a focus outline & are on-screen`, bad.length===0, bad.length?JSON.stringify(bad):seen.map(s=>s.t).join(" > "));
  const hidden=await p.evaluate(()=>[...document.querySelectorAll("nav")].filter(n=>getComputedStyle(n).display==="none").map(n=>n.ariaLabel));
  ok(`w=${w} the hidden nav is display:none (not reachable by Tab/AT)`, hidden.length===1, hidden.join());
  await p.close();
}
// B. reduced motion
{ const p=await b.newPage(); await p.setViewport({width:1280,height:800}); await p.emulateMediaFeatures([{name:"prefers-reduced-motion",value:"reduce"}]);
  await p.goto(BASE+"/",{waitUntil:"networkidle0"});
  const d=await p.evaluate(()=>{const a=document.querySelector('nav[aria-label="Primary"] a');const c=getComputedStyle(a);return {t:c.transitionDuration,anim:[...document.querySelectorAll("*")].filter(e=>{const s=getComputedStyle(e);return s.animationName!=="none"&&parseFloat(s.animationDuration)>0.05}).length}});
  ok("reduced-motion: nav transition ~0 and no animation >50ms", parseFloat(d.t)<0.05&&d.anim===0, JSON.stringify(d)); await p.close(); }
// C. logged-in state (SYNTHETIC user via mocked /auth/me; nothing sent to the API)
for(const w of [1280,390,768]){
  const p=await b.newPage(); await p.setViewport({width:w,height:800}); await p.setRequestInterception(true);
  p.on("request",rq=>{ if(new URL(rq.url()).pathname==="/api/v1/auth/me") rq.respond({status:200,contentType:"application/json",body:JSON.stringify({id:1,username:"test-user",email:"t@example.test",role:"viewer"})}); else rq.continue(); });
  await p.goto(BASE+"/",{waitUntil:"networkidle0"}); await sleep(300);
  const r=await p.evaluate(()=>{const h=document.querySelector("header");const links=[...h.querySelectorAll("a,button")].filter(e=>/test-user|Sign out/.test(e.textContent)).map(e=>[e.textContent.trim(),Math.round(e.getBoundingClientRect().height)]);return {links,signedOutShown:!!h.querySelector('a[href="/login"]'),over:document.documentElement.scrollWidth-document.documentElement.clientWidth}});
  ok(`logged-in w=${w}: username + Sign out shown, sign-in hidden, targets>=40px, no overflow`, r.links.length===2&&!r.signedOutShown&&r.links.every(l=>l[1]>=40)&&r.over<=0, JSON.stringify(r)); await p.close(); }
// D. which URLs 404? probe all top-level routes
{ const p=await b.newPage(); const bad=[]; p.on("response",r=>{if(r.status()>=400&&!r.url().includes("/auth/me"))bad.push(r.status()+" "+r.url().replace(BASE,""))});
  for(const r of ["/","/drugs","/search","/calculators","/species","/study","/study/books","/study/past-papers","/study/lessons","/study/flashcards","/universities","/jobs","/scholarships","/countries","/classes","/companies","/products","/interactions","/ask","/blog","/credits","/catalogs-3d","/login","/register","/offline","/admin-panel","/account","/manifest.webmanifest","/sitemap.xml","/robots.txt","/sw.js","/favicon.ico"]){
    const resp=await p.goto(BASE+r,{waitUntil:"networkidle0",timeout:60000}).catch(()=>null); console.log("route",r,resp?.status()); }
  console.log("non-auth 4xx/5xx subresources:",[...new Set(bad)]); await p.close(); }
await b.close();
