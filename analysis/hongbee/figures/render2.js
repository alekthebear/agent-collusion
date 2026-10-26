const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1240,height:820},deviceScaleFactor:2});
await p.goto('file:///home/claude/fig/fig2.html');await p.waitForTimeout(300);
await p.screenshot({path:'/home/claude/fig/figure_loop.png',clip:{x:0,y:0,width:1240,height:820}});
await p.pdf({path:'/home/claude/fig/figure_loop.pdf',width:'1240px',height:'820px',printBackground:true,pageRanges:'1'});
await b.close();})();
