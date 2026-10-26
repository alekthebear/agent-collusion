const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1600,height:520},deviceScaleFactor:3});
await p.goto('file:///home/claude/fig/fig.html');await p.waitForTimeout(300);
await p.screenshot({path:'/home/claude/fig/figure1_overview.png',clip:{x:0,y:0,width:1600,height:520}});
await p.pdf({path:'/home/claude/fig/figure1_overview.pdf',width:'1600px',height:'520px',printBackground:true,pageRanges:'1'});
await b.close();})();
