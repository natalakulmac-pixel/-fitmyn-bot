const {chromium}=require('playwright');
const fs=require('fs'),assert=require('assert');
(async()=>{
const browser=await chromium.launch({headless:true});
try{
const page=await browser.newPage({viewport:{width:390,height:844}});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.addInitScript(()=>{window.Telegram={WebApp:{initData:'test',initDataUnsafe:{user:{id:1,first_name:'Тест'}},ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},HapticFeedback:{impactOccurred(){}}}}});
const types=['breakfast','lunch','snack','dinner'],names=['Завтрак','Обед','Перекус','Ужин'];
const catalog={};
const plan=Array.from({length:7},(_,d)=>({date:new Date(Date.UTC(2026,8,28+d)).toISOString().slice(0,10),meals:Object.fromEntries(types.map((t,i)=>{const id=t+d;catalog[id]={id,type:names[i],name:id,kcal:300,protein:20,fat:10,carbs:30,cookTime:15,image:'/api/app/meal-image/'+id,ingredients:[['Овощи','Томаты',100,'г']],recipe:['Приготовить']};return[t,id]}))}));
const fixture={profile:{name:'Тест',height:'165'},subscription:{status:'trial',has_access:true,stars:350},goal_progress:{current_weight:65,start_weight:60,target_weight:70},water:{date:'2026-09-30',today_ml:250,goal_ml:2000},weight_history:[{weight:60,created_at:'2026-09-28'},{weight:65,created_at:'2026-09-30'}],workout_plan:{name:'Тренировка',note:'Тест',exercises:[{name:'Упражнение',reps:'2 × 8'}]},workout_progress:{completed_count:0,today_completed:false},weeklyMealPlan:plan,mealCatalog:catalog};
const states={};let completes=0,regenerates=0;
await page.route('**/*',async route=>{
 const req=route.request(),url=new URL(req.url()),path=url.pathname;
 const json=body=>route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
 if(path==='/app')return route.fulfill({contentType:'text/html',body:fs.readFileSync('mini_app.html','utf8')});
 if(path==='/api/app/bootstrap')return json(fixture);
 if(path==='/api/app/state'){const key=url.searchParams.get('key');if(req.method()==='POST')states[key]=req.postDataJSON().items;return json({items:states[key]||[]})}
 if(path==='/api/app/week/regenerate'){regenerates++;return json({weeklyMealPlan:plan,mealCatalog:catalog})}
 if(path==='/api/app/meal/replace')return json({weeklyMealPlan:plan,mealCatalog:catalog});
 if(path==='/api/app/workout/complete'){completes++;return json({completed_count:1,today_completed:true})}
 if(path==='/api/app/weight')return json({current_weight:req.postDataJSON().weight});
 if(path==='/api/app/ask')return route.fulfill({status:503,body:'{}'});
 if(path.includes('meal-image'))return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'});
 return route.fulfill({body:''});
});
await page.goto('https://fitmy.test/app?recipe=breakfast0');
await page.waitForSelector('#loading.hide');
assert.equal(await page.locator('#recipeTitle').innerText(),'breakfast0');
await page.locator('#recipeModal [data-close="recipeModal"]').click();
assert.equal(await page.locator('#currentWeight').innerText(),'65,0 кг');
assert.equal(await page.locator('#goalBar').evaluate(e=>e.style.width),'50%');
assert.equal(await page.locator('#subscriptionNotice').isVisible(),false);
await page.locator('#nav [data-go="nutrition"]').click();
await page.locator('[data-sub="week"]').click();
await page.locator('#recalcWeek').click();
await page.waitForFunction(()=>!document.getElementById('recalcWeek').disabled);
assert.equal(regenerates,1);
await page.locator('[data-sub="shopping"]').click();
await page.locator('.shop-check').first().check();
await page.waitForFunction(()=>document.getElementById('shopPct').textContent.startsWith('1 '));
await page.locator('#nav [data-go="workout"]').click();
await page.locator('#finishWorkout').click();assert.equal(completes,0);
await page.locator('[data-ex="0"]').click();
await page.waitForSelector('[data-ex="0"].on');
await page.locator('#finishWorkout').click();
await page.waitForFunction(()=>document.getElementById('progressWorkoutCount').textContent==='1');
assert.equal(completes,1);
await page.reload();await page.waitForSelector('#loading.hide');
await page.locator('#nav [data-go="workout"]').click();
assert.equal(await page.locator('[data-ex="0"]').evaluate(e=>e.classList.contains('on')),true);
await page.screenshot({path:'mobile-check.png',fullPage:true});
fixture.subscription={status:'expired',has_access:false,stars:350};
await page.reload();await page.waitForSelector('#loading.hide');
assert.equal(await page.locator('#subscriptionNotice').isVisible(),true);
assert.equal(await page.locator('[data-page="profile"]').isVisible(),true);await page.locator('#nav [data-go="nutrition"]').click();assert.equal(await page.locator('[data-page="nutrition"]').isVisible(),false);
assert.deepEqual(errors,[]);
console.log('Mobile flows: nutrition, goal, shopping, exercise sync, trial/expired: OK');
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
