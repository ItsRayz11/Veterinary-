import fs from "node:fs";
for(const f of fs.readdirSync("lh").filter(f=>f.startsWith("p2-")).sort()){
  const j=JSON.parse(fs.readFileSync("lh/"+f)); if(j.runtimeError){console.log(f,"RUNTIME ERROR",j.runtimeError.code);continue}
  const c=j.categories,a=j.audits,s=k=>Math.round(c[k].score*100),n=k=>Math.round(a[k].numericValue);
  console.log(f.replace("p2-","").replace(".json","").padEnd(22),"perf",s("performance"),"a11y",s("accessibility"),"bp",s("best-practices"),"seo",s("seo"),"| FCP",n("first-contentful-paint"),"LCP",n("largest-contentful-paint"),"TBT",n("total-blocking-time"),"CLS",a["cumulative-layout-shift"].numericValue.toFixed(3),"SI",n("speed-index"));
}
