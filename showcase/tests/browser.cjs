'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;

const root = path.resolve(__dirname, '..', 'dist');
const output = path.resolve(__dirname, '..', '..', '.tools', 'task36e');
const sizes = [[1920,1080],[1440,900],[1366,768],[390,844],[375,667],[320,568]];
const browserPath = process.env.SHOWCASE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
fs.mkdirSync(path.join(output, 'screenshots'), {recursive:true});
const mime = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8'};
const server = http.createServer((req,res)=>{
  const name = req.url === '/' ? 'index.html' : req.url.split('?')[0].replace(/^\//,'');
  if (!['index.html','app.js','style.css'].includes(name)) {res.writeHead(404).end();return;}
  fs.readFile(path.join(root,name),(err,data)=>{if(err){res.writeHead(404).end();return;} res.writeHead(200,{'Content-Type':mime[path.extname(name)]}).end(data);});
});
async function main(){
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  const browser = await chromium.launch({headless:true,executablePath:browserPath});
  const results = {browser_executable:path.basename(browserPath),browser_version:browser.version(),viewports:[],privacy:'screenshots and reports are local and ignored'};
  try {
    for(const [width,height] of sizes){
      const context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce'});
      const page=await context.newPage();const errors=[];
      page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
      const response=await page.goto(`http://127.0.0.1:${server.address().port}/`,{waitUntil:'networkidle'});
      assert.equal(response.status(),200);assert.equal(await page.title(),'Resilient Delivery Platform on AWS');
      const metrics=await page.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,heading:document.querySelectorAll('h1').length,main:document.querySelectorAll('main').length,nav:document.querySelectorAll('nav').length,reduce:matchMedia('(prefers-reduced-motion: reduce)').matches,scrollBehavior:getComputedStyle(document.documentElement).scrollBehavior}));
      assert.ok(metrics.scroll<=metrics.width,`horizontal overflow ${width}: ${metrics.scroll} > ${metrics.width}`);assert.equal(metrics.heading,1);assert.equal(metrics.main,1);assert.equal(metrics.nav,1);assert.equal(metrics.reduce,true);assert.equal(metrics.scrollBehavior,'auto');
      const links=page.locator('nav a');assert.equal(await links.count(),4);for(const l of await links.all()){assert.ok(await l.isVisible(),'navigation hidden');const target=await l.getAttribute('href');await l.click();assert.equal(new URL(page.url()).hash,target);const rect=await page.locator(target).boundingBox();assert.ok(rect&&rect.width>0&&rect.height>0,'navigation target unavailable');}
      for(const l of await page.locator('a[href^="#"]').all()){const target=await l.getAttribute('href');assert.equal(await page.locator(target).count(),1,'broken in-page link');}
      const clipped=await page.locator('h1,h2,h3,p,a,button').evaluateAll(nodes=>nodes.filter(n=>{const s=getComputedStyle(n);return (s.overflowX==='hidden'&&n.clientWidth>0&&n.scrollWidth>n.clientWidth+1)||(s.overflowY==='hidden'&&n.clientHeight>0&&n.scrollHeight>n.clientHeight+1)}).length);assert.equal(clipped,0,`clipped content ${width}`);
      const buttons=page.locator('[data-detail]');assert.equal(await buttons.count(),6);for(const b of await buttons.all()){assert.ok(await b.isVisible(),'button hidden');assert.ok((await b.innerText()).trim(),'button missing accessible name');await b.click();assert.equal(await page.locator('#architecture-detail').textContent(),await b.getAttribute('data-detail'));}
      const geometry=await page.locator('a,button,h1,h2,h3,p').evaluateAll(nodes=>nodes.filter(n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return r.width && r.height && s.visibility!=='hidden';}).map(n=>{const r=n.getBoundingClientRect();return {tag:n.tagName,text:n.textContent.trim().slice(0,50),left:r.left,right:r.right,top:r.top,bottom:r.bottom,font:parseFloat(getComputedStyle(n).fontSize)};}));
      assert.ok(geometry.filter(x=>x.left < -1 || x.right > width+1).length===0,`element outside viewport ${width}`);
      assert.ok(geometry.filter(x=>x.font<11).length===0,`text smaller than 11px ${width}`);
      for(const tags of [['A','BUTTON'],['H1','H2','H3','P']]){
        const items=geometry.filter(x=>tags.includes(x.tag));
        for(let i=0;i<items.length;i++)for(let j=i+1;j<items.length;j++){const a=items[i],b=items[j];assert.ok(!(Math.min(a.right,b.right)-Math.max(a.left,b.left)>2&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>2),`overlapping elements ${width}: ${a.text}/${b.text}`);}
      }
      await page.locator('body').click({position:{x:2,y:2}});await page.keyboard.press('Tab');const first=await page.evaluate(()=>document.activeElement.tagName);assert.equal(first,'A');
      const focus=await page.evaluate(()=>{const s=getComputedStyle(document.activeElement);return {style:s.outlineStyle,width:parseFloat(s.outlineWidth)}});assert.ok(focus.style!=='none'&&focus.width>=2,'focus indicator missing');
      await page.keyboard.press('Tab');const second=await page.evaluate(()=>document.activeElement.textContent.trim());await page.keyboard.press('Shift+Tab');assert.notEqual((await page.evaluate(()=>document.activeElement.textContent.trim())),second);
      for(const button of await buttons.all()){
        await button.focus();const indicator=await button.evaluate(e=>{const s=getComputedStyle(e);return {style:s.outlineStyle,width:parseFloat(s.outlineWidth)}});assert.ok(indicator.style!=='none'&&indicator.width>=2,'button focus indicator missing');
        for(const key of ['Enter','Space']){await page.locator('#architecture-detail').evaluate(e=>e.textContent='reset');await page.keyboard.press(key);assert.equal(await page.locator('#architecture-detail').textContent(),await button.getAttribute('data-detail'));}
      }
      assert.equal(errors.length,0,errors.join('; '));
      const accessibility=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
      const violations=accessibility.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.length}));
      await page.screenshot({path:path.join(output,'screenshots',`${width}x${height}.png`),fullPage:true});
      results.viewports.push({width,height,overflow:false,navigation:true,architecture_controls:6,keyboard:true,focus:true,reduced_motion:true,console_errors:errors,axe_violations:violations,geometry_elements:geometry.length});
      fs.writeFileSync(path.join(output,'browser-results.json'),JSON.stringify(results,null,2));
      console.log(`${width}x${height}: controls/keyboard/layout checked; axe violations ${violations.length}`);
      await context.close();
    }
    assert.ok(results.viewports.every(v=>v.axe_violations.length===0),'axe detected WCAG-related violations');
  } finally {await browser.close();}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;}).finally(()=>server.close());
