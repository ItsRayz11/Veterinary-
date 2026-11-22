import puppeteer from "puppeteer-core";
const BASE=process.argv[2]||"http://localhost:3100";
const b=await puppeteer.launch({executablePath:"C:/Program Files/Google/Chrome/Application/chrome.exe",headless:true,args:["--no-sandbox"]});
const res=[]; const ok=(n,c,x="")=>{res.push(c);console.log(`${c?"PASS":"FAIL"}  ${n}${x?"  ["+x+"]":""}`)};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
// SYNTHETIC test fixtures only (not real drug data).
const fx=n=>({generics:[{name:"FIXTURE-"+n,slug:"fixture-"+n}],products:[],companies:[],did_you_mean:[]});
async function page(handler){
  const p=await b.newPage(); await p.setViewport({width:1280,height:800});
  await p.setRequestInterception(true);
  p.on("request",rq=>{ const u=new URL(rq.url());
    if(u.pathname.startsWith("/api/v1/search")&&handler) handler(rq,u.searchParams.get("q")); else rq.continue(); });
  return p;
}
const val=p=>p.$eval("#global-search",e=>e.value);
const opts=p=>p.$$eval('[role=option]',e=>e.map(x=>x.textContent));
const live=p=>p.$eval('[aria-live=polite]',e=>e.textContent).catch(()=>"");
const json=(rq,body,status=200)=>rq.respond({status,contentType:"application/json",body:JSON.stringify(body)});

// 1-3 URL -> input
for(const [q,exp] of [["amox","amox"],["amoxicillin%20clavulanate","amoxicillin clavulanate"],["amoxicillin+clavulanate","amoxicillin clavulanate"],["caf%C3%A9","café"],["a%26b%3Dc%2B%2F%3F%23%22%3C%3E%27","a&b=c+/?#\"<>'"],["%3Cscript%3Ealert(1)%3C%2Fscript%3E","<script>alert(1)</script>"]]){
  const p=await page(null); await p.goto(`${BASE}/search?q=${q}`,{waitUntil:"networkidle0"});
  const v=await val(p); const dialogs=[]; 
  ok(`url q=${q} -> input`, v===exp, JSON.stringify(v));
  ok(`  no injected <script> element`, (await p.$$eval("main script",e=>e.length))===0);
  await p.close();
}
{ const p=await page(null); await p.goto(`${BASE}/search`,{waitUntil:"networkidle0"});
  ok("empty (no q): input empty, no clear button", (await val(p))===""&&!(await p.$('[aria-label="Clear search"]')));
  await p.goto(`${BASE}/search?q=`,{waitUntil:"networkidle0"}); ok("empty (q=): input empty", (await val(p))==="");
  await p.goto(`${BASE}/search?q=a`,{waitUntil:"networkidle0"}); ok("1-char q: input shows 'a', page asks for 2 chars", (await val(p))==="a"&&(await p.evaluate(()=>document.body.innerText)).includes("at least 2"));
  await p.close(); }

// 4 back/forward
{ const p=await page((rq)=>json(rq,fx("x"))); await p.goto(`${BASE}/search?q=aaa`,{waitUntil:"networkidle0"});
  await p.focus("#global-search"); await p.keyboard.down("Control"); await p.keyboard.press("a"); await p.keyboard.up("Control"); await p.keyboard.type("bbb"); await p.keyboard.press("Enter");
  await p.waitForFunction(()=>location.search==="?q=bbb"); await sleep(800);
  ok("submit -> URL and input both bbb", (await val(p))==="bbb");
  await p.goBack(); await p.waitForFunction(()=>location.search==="?q=aaa"); await sleep(800);
  ok("back -> input follows URL (aaa)", (await val(p))==="aaa", await val(p));
  await p.goForward(); await p.waitForFunction(()=>location.search==="?q=bbb"); await sleep(800);
  ok("forward -> input follows URL (bbb)", (await val(p))==="bbb", await val(p));
  await p.close(); }

// 5 stale responses: slow "slow" must not overwrite fast "fast"
{ const p=await page((rq,q)=>{ if(q.startsWith("slow")) setTimeout(()=>json(rq,fx("SLOW")),1500); else json(rq,fx("FAST")); });
  await p.goto(`${BASE}/search`,{waitUntil:"networkidle0"}); await p.click("#global-search");
  await p.keyboard.type("slow"); await sleep(350);   // debounce fires, slow request in flight
  ok("loading status announced via aria-live while pending", (await live(p)).includes("Searching"), await live(p));
  await p.focus("#global-search"); await p.keyboard.down("Control"); await p.keyboard.press("a"); await p.keyboard.up("Control"); await p.keyboard.type("fast");
  await sleep(700); const mid=await opts(p);
  await sleep(1800); const end=await opts(p);
  ok("fast result shown", mid.join().includes("FIXTURE-FAST"), mid.join());
  ok("late slow response did NOT overwrite newer results", end.join().includes("FIXTURE-FAST")&&!end.join().includes("SLOW"), end.join());
  ok("loading status cleared afterwards", !(await live(p)).includes("Searching"), JSON.stringify(await live(p)));
  await p.close(); }

// 6 rapid typing: only final query's results
{ const seen=[]; const p=await page((rq,q)=>{seen.push(q); setTimeout(()=>json(rq,fx(q)),q.length<4?900:50)});
  await p.goto(`${BASE}/search`,{waitUntil:"networkidle0"}); await p.click("#global-search");
  for(const c of "dogs"){await p.keyboard.type(c);await sleep(260)} await sleep(1800);
  const o=await opts(p); ok("rapid typing ends on final query only", o.length===1&&o[0].includes("FIXTURE-dogs"), o.join()+" | requests:"+seen.join(","));
  await p.close(); }

// 7 failed request, then recovery
{ let fail=true; const p=await page((rq)=>fail?rq.respond({status:500,body:"x"}):json(rq,fx("OK")));
  await p.goto(`${BASE}/search`,{waitUntil:"networkidle0"}); await p.click("#global-search"); await p.keyboard.type("fail"); await sleep(900);
  ok("failed request: error announced, no 'Searching…' stuck", (await live(p)).includes("unavailable")&&!(await live(p)).includes("Searching"), await live(p));
  fail=false; await p.keyboard.type("s"); await sleep(900);
  ok("recovers on next keystroke", (await opts(p)).join().includes("FIXTURE-OK")&&!(await live(p)).includes("unavailable"), await live(p)+"|"+(await opts(p)).join());
  await p.close(); }

// 8 slow network + clear
{ const p=await page((rq)=>setTimeout(()=>json(rq,fx("LATE")),1500));
  await p.goto(`${BASE}/search`,{waitUntil:"networkidle0"}); await p.click("#global-search"); await p.keyboard.type("clearme"); await sleep(400);
  ok("clear button appears when there is text", !!(await p.$('[aria-label="Clear search"]')));
  await p.click('[aria-label="Clear search"]');
  ok("clear: input emptied", (await val(p))==="");
  ok("clear: focus returns to input", await p.evaluate(()=>document.activeElement?.id==="global-search"));
  ok("clear: 'Searching…' removed immediately", !(await live(p)).includes("Searching"), await live(p));
  await sleep(1800);
  ok("clear: in-flight response can't resurrect suggestions", (await opts(p)).length===0 && (await val(p))==="");
  ok("clear button gone when empty", !(await p.$('[aria-label="Clear search"]')));
  const box=await (await p.$("#global-search")).boundingBox(); ok("input is >=44px tall for touch", box.height>=44, box.height+"px");
  await p.close(); }

// 9 keyboard: Escape, arrows
{ const p=await page((rq)=>json(rq,{generics:[{name:"FIXTURE-A",slug:"a"},{name:"FIXTURE-B",slug:"b"}],products:[],companies:[],did_you_mean:[]}));
  await p.goto(`${BASE}/search`,{waitUntil:"networkidle0"}); await p.click("#global-search"); await p.keyboard.type("fix"); await sleep(700);
  await p.keyboard.press("ArrowDown"); await p.keyboard.press("ArrowDown");
  ok("ArrowDown moves aria-activedescendant to 2nd option", await p.evaluate(()=>{const i=document.querySelector("#global-search");const el=document.getElementById(i.getAttribute("aria-activedescendant")||"");return el?.textContent.includes("FIXTURE-B")}));
  await p.keyboard.press("Escape"); ok("Escape closes suggestions", (await opts(p)).length===0);
  await p.close(); }
// 10 URL-seeded query must not auto-open a duplicate suggestions dropdown or fetch on load
{ let n=0; const p=await page((rq)=>{n++;json(rq,fx("X"))});
  await p.goto(`${BASE}/search?q=amox`,{waitUntil:"networkidle0"}); await sleep(1200);
  ok("URL-seeded query: no suggestion fetch and no dropdown on load", n===0&&!(await p.$("[role=listbox]")), "fetches="+n);
  await p.focus("#global-search"); await p.keyboard.type("i"); await sleep(900);
  ok("typing after load does fetch suggestions", n>=1&&(await opts(p)).length===1, "fetches="+n);
  await p.close(); }
// 11 no-match suggestions: valid ARIA (no empty listbox), announced as status
{ const p=await page((rq)=>json(rq,{generics:[],products:[],companies:[],did_you_mean:[]}));
  await p.goto(`${BASE}/search`,{waitUntil:"networkidle0"}); await p.click("#global-search"); await p.keyboard.type("zzzz"); await sleep(900);
  ok("no-match: no empty role=listbox", !(await p.$("[role=listbox]")));
  ok("no-match: message exposed as role=status", (await p.$$eval("[role=status]",e=>e.map(x=>x.textContent).join())).includes("No results"));
  ok("no-match: combobox aria-expanded=false", (await p.$eval("#global-search",e=>e.getAttribute("aria-expanded")))==="false");
  await p.close(); }
console.log(`\n${res.filter(Boolean).length}/${res.length} checks passed`);
await b.close();
