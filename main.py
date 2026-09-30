import asyncio
import base64
import gzip
import hashlib
import hmac
import json
import logging
import os
import re
import time
import random
from urllib.parse import parse_qsl
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    Update,
    MenuButtonWebApp,
    WebAppInfo,
    LabeledPrice,
    PreCheckoutQuery,
)
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openrouter/free").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "fitmyn-webhook").strip()
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "10000"))
CRON_SECRET = os.getenv("CRON_SECRET", "").strip()
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow"
DEFAULT_MORNING_TIME = os.getenv("DEFAULT_MORNING_TIME", "08:00").strip() or "08:00"
DEFAULT_EVENING_TIME = os.getenv("DEFAULT_EVENING_TIME", "20:30").strip() or "20:30"
TRIAL_DAYS = 14
SUBSCRIPTION_STARS = int(os.getenv("SUBSCRIPTION_STARS", "350"))
SUBSCRIPTION_PERIOD = 30 * 24 * 60 * 60
APP_BUILD_VERSION = "v12-profile-sync-3"
APP_URL = f"{RENDER_EXTERNAL_URL}/app?v={APP_BUILD_VERSION}" if RENDER_EXTERNAL_URL else ""
MINI_APP_HTML_GZIP_B64 = """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"""
MINI_APP_HTML = gzip.decompress(base64.b64decode(MINI_APP_HTML_GZIP_B64)).decode("utf-8")


MINI_APP_PATCH = r"""
<style>
#profileInitial.has-photo{background-size:cover;background-position:center;font-size:0}
.fitmy-extra-btn{margin-top:10px}
.weight-entry{margin-top:10px;padding:14px}.weight-entry-row{display:flex;gap:8px;align-items:center}.weight-entry input{flex:1;border:1px solid var(--border);background:#fff;border-radius:14px;padding:12px;font-size:16px;min-width:0}.weight-entry button{border:0;border-radius:14px;background:var(--primary);color:#fff;padding:12px 14px;font-weight:800}
.weight-history{margin-top:10px;padding:14px}.weight-history-list{display:flex;gap:7px;overflow:auto;padding-top:8px}.weight-chip{white-space:nowrap;background:#f1eee6;border-radius:12px;padding:8px 10px;font-size:11px}
</style>
<script>
(()=> {
 const oldBootstrap=window.bootstrap;
 const workoutSets=[
  {name:'Full body',mins:45,items:[['Приседания','3 × 12'],['Отжимания от опоры','3 × 10'],['Тяга гантелей в наклоне','3 × 12'],['Выпады назад','3 × 10'],['Ягодичный мост','3 × 15'],['Планка','3 × 40 сек']]},
  {name:'Ноги и ягодицы',mins:40,items:[['Приседания сумо','3 × 12'],['Румынская тяга','3 × 12'],['Болгарские выпады','3 × 10'],['Ягодичный мост','4 × 15'],['Отведение ноги','3 × 15'],['Боковая планка','3 × 30 сек']]},
  {name:'Спина и корпус',mins:35,items:[['Тяга гантелей','3 × 12'],['Разведение рук','3 × 12'],['Пуловер','3 × 12'],['Bird dog','3 × 12'],['Dead bug','3 × 12'],['Планка','3 × 45 сек']]},
  {name:'Функциональная',mins:38,items:[['Присед + подъём рук','3 × 12'],['Шаги в планку','3 × 8'],['Выпады с подъёмом колена','3 × 10'],['Ягодичный мост','3 × 15'],['Альпинист','3 × 30 сек'],['Скручивания','3 × 15']]}
 ];
 function weekNumber(){const d=new Date(),onejan=new Date(d.getFullYear(),0,1);return Math.floor(((d-onejan)/86400000+onejan.getDay()+6)/7)}
 function workoutForNow(){return workoutSets[weekNumber()%workoutSets.length]}
 function applyWorkout(){
   const w=workoutForNow(), head=document.querySelector('[data-page="workout"] .workout-head');
   if(head){head.querySelector('h2').textContent=w.name;const tags=head.querySelectorAll('.workout-tags span');if(tags[0])tags[0].textContent=w.mins+' минут'}
   const box=document.getElementById('exerciseList'); if(box){box.innerHTML=w.items.map((x,i)=>'<div class="card exercise"><div class="num">'+(i+1)+'</div><div class="ei"><h3>'+x[0]+'</h3><p>'+x[1]+'</p></div><button class="done" data-ex="'+i+'">✓</button></div>').join('')}
   if(window.__fitmyWorkoutDone) document.querySelectorAll('.done').forEach(x=>x.classList.add('on'));
   if(typeof updateWorkout==='function')updateWorkout();
 }
 const heroCopy=document.querySelector('.hero-copy'); if(heroCopy)heroCopy.textContent='Здоровые привычки — энергия каждый день';

 const profileHead=document.querySelector('.profile-head');
 if(profileHead && !document.getElementById('profilePhotoInput')){
   const b=document.createElement('button');b.className='secondary-btn fitmy-extra-btn';b.id='changeProfilePhoto';b.textContent='Установить своё фото';
   const inp=document.createElement('input');inp.type='file';inp.accept='image/*';inp.id='profilePhotoInput';inp.style.display='none';
   profileHead.appendChild(b);profileHead.appendChild(inp);
   b.onclick=()=>inp.click();
   inp.onchange=async()=>{
     const file=inp.files&&inp.files[0];if(!file)return;
     const img=new Image(),reader=new FileReader();
     reader.onload=()=>img.src=reader.result;
     img.onload=async()=>{
       const c=document.createElement('canvas'),max=420,scale=Math.min(1,max/Math.max(img.width,img.height));c.width=Math.round(img.width*scale);c.height=Math.round(img.height*scale);c.getContext('2d').drawImage(img,0,0,c.width,c.height);
       const data=c.toDataURL('image/jpeg',.78);
       if(initData){const r=await fetch(API+'/api/app/profile/photo',{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':initData},body:JSON.stringify({photo_data:data})});if(!r.ok){showToast('Не удалось сохранить фото');return}}
       const circle=document.getElementById('profileInitial');circle.style.backgroundImage='url("'+data+'")';circle.classList.add('has-photo');showToast('Фото профиля сохранено');
     };reader.readAsDataURL(file);
   };
 }
 const progressPage=document.querySelector('[data-page="progress"]');
 if(progressPage && !document.getElementById('dailyWeightInput')){
   const card=document.createElement('div');card.className='card weight-entry';card.innerHTML='<b>Ежедневный вес</b><div class="sub" style="margin-top:3px">Вноси новый вес — он сразу попадёт в текущий результат и историю.</div><div class="weight-entry-row" style="margin-top:10px"><input id="dailyWeightInput" inputmode="decimal" placeholder="Например, 56,1"><button id="saveDailyWeight">Сохранить</button></div>';
   progressPage.insertBefore(card,progressPage.children[1]);
   document.getElementById('saveDailyWeight').onclick=async()=>{const el=document.getElementById('dailyWeightInput'),v=parseFloat(el.value.replace(',','.'));if(Number.isFinite(v)){await saveWeight('current',v);el.value='';await loadWeightHistory()}};
   const hist=document.createElement('div');hist.className='card weight-history';hist.innerHTML='<b>История веса</b><div class="weight-history-list" id="weightHistoryList"></div>';progressPage.insertBefore(hist,progressPage.children[2]);
 }
 async function loadWeightHistory(items){
   if(!items&&initData){try{const r=await fetch(API+'/api/app/weight/history',{headers:{'X-Telegram-Init-Data':initData,'Cache-Control':'no-cache'}});if(r.ok)items=(await r.json()).items}catch{}}
   items=items||[];const box=document.getElementById('weightHistoryList');if(box)box.innerHTML=items.slice(-12).reverse().map(x=>'<div class="weight-chip">'+new Date(x.created_at).toLocaleDateString('ru-RU',{day:'2-digit',month:'2-digit'})+' · <b>'+Number(x.weight).toFixed(1).replace('.',',')+' кг</b></div>').join('')||'<span class="sub">Добавь первый результат</span>';
 }
 const originalFetch=window.fetch.bind(window);
 window.fetch=async(...args)=>{const r=await originalFetch(...args);try{const u=String(args[0]);if(u.includes('/api/app/bootstrap')&&r.ok){const clone=r.clone(),j=await clone.json();window.__fitmyWorkoutDone=!!j.workout_progress?.today_completed;window.__fitmyWorkoutCount=j.workout_progress?.completed_count||0;setTimeout(()=>{const pc=document.querySelectorAll('.progress-card .big');if(pc[2])pc[2].textContent=window.__fitmyWorkoutCount;const ph=document.getElementById('profileInitial');if(j.profile_photo&&ph){ph.style.backgroundImage='url("'+j.profile_photo+'")';ph.classList.add('has-photo')}loadWeightHistory(j.weight_history);applyWorkout()},50)}}catch{}return r};
 const finish=document.getElementById('finishWorkout');
 if(finish){finish.onclick=async()=>{document.querySelectorAll('.done').forEach(x=>x.classList.add('on'));updateWorkout();const w=workoutForNow();if(initData){try{const r=await originalFetch(API+'/api/app/workout/complete',{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':initData},body:JSON.stringify({workout_key:'week-'+weekNumber()+'-'+new Date().getDay(),workout_name:w.name})});if(r.ok){const j=await r.json();window.__fitmyWorkoutDone=true;window.__fitmyWorkoutCount=j.completed_count||1;const pc=document.querySelectorAll('.progress-card .big');if(pc[2])pc[2].textContent=window.__fitmyWorkoutCount}}catch{}}showToast('Тренировка засчитана в прогресс 💚')}}
 setTimeout(applyWorkout,400);
})();
</script>
<script>
(()=>{
 const OATMEAL_IMAGE='https://cf-img-a-in.tosshub.com/sites/visualstory/wp/2025/09/imageITG-1757139143153.png?size=%2A%3A900';

 function normalizeHeight(v){
   const m=String(v??'').replace(',','.').match(/\d{2,3}(?:\.\d+)?/);
   return m ? String(Math.round(Number(m[0]))) : '';
 }
 function forceProfileHeight(height){
   height=normalizeHeight(height); if(!height)return;
   const page=document.querySelector('[data-page="profile"]')||document;
   const walker=document.createTreeWalker(page,NodeFilter.SHOW_TEXT);
   const nodes=[]; while(walker.nextNode())nodes.push(walker.currentNode);
   nodes.forEach(n=>{
     const t=n.nodeValue||'';
     if(/\b\d{2,3}\s*см\b/i.test(t)) n.nodeValue=t.replace(/\b\d{2,3}\s*см\b/gi,height+' см');
   });
   ['profileHeight','heightValue','userHeight'].forEach(id=>{const e=document.getElementById(id);if(e)e.textContent=height+' см'});
 }
 function fixMealLibrary(){
   try{
     if(typeof mealLibrary!=='undefined' && mealLibrary.oatmeal){
       mealLibrary.oatmeal.image=OATMEAL_IMAGE;
       mealLibrary.oatmeal.img=OATMEAL_IMAGE;
       mealLibrary.oatmeal.photo=OATMEAL_IMAGE;
     }
   }catch(e){}
   document.querySelectorAll('img').forEach(img=>{
     // Change only the image inside the ONE meal tile that actually contains oatmeal.
     // Never climb to the day/row container: it contains several meals and previously
     // caused the oatmeal photo to overwrite salmon, yogurt, turkey, etc.
     let box=img.parentElement, ownMealBox=null;
     for(let depth=0;box && depth<6;depth++,box=box.parentElement){
       const images=box.querySelectorAll ? box.querySelectorAll('img').length : 0;
       const txt=(box.textContent||'').trim();
       if(images===1 && txt.length>0 && txt.length<180){ownMealBox=box;break;}
       if(images>1)break;
     }
     if(ownMealBox && /овсянк/i.test(ownMealBox.textContent||'')){
       if(img.src!==OATMEAL_IMAGE) img.src=OATMEAL_IMAGE;
       img.alt='Овсянка с ягодами и орехами';
     }
   });
 }
 async function hardSync(){
   if(!initData)return;
   try{
     const r=await fetch(API+'/api/app/bootstrap?fresh='+Date.now(),{headers:{'X-Telegram-Init-Data':initData,'Cache-Control':'no-store'}});
     if(!r.ok)return;
     const j=await r.json();
     if(j.profile?.height) forceProfileHeight(j.profile.height);
     if(j.profile_photo){const ph=document.getElementById('profileInitial');if(ph){ph.style.backgroundImage='url("'+j.profile_photo+'")';ph.classList.add('has-photo')}}
     fixMealLibrary();
     try{ if(typeof renderMeals==='function')renderMeals(); if(typeof renderWeek==='function')renderWeek(); }catch(e){}
     setTimeout(fixMealLibrary,100);
   }catch(e){}
 }
 const observer=new MutationObserver(()=>{fixMealLibrary()});
 observer.observe(document.body,{subtree:true,childList:true});
 fixMealLibrary();
 setTimeout(hardSync,250);
 setTimeout(hardSync,1400);
})();
</script>
<script>
(()=>{
 const TG_INIT=(window.Telegram&&window.Telegram.WebApp&&window.Telegram.WebApp.initData)||window.initData||'';
 const API_BASE=window.API||'';
 const authHeaders=(json=false)=>Object.assign(json?{'Content-Type':'application/json'}:{},{'X-Telegram-Init-Data':TG_INIT,'Cache-Control':'no-store'});

 function setProfileRow(label,value){
   if(value===undefined||value===null||value==='')return;
   const page=document.querySelector('[data-page="profile"]')||document;
   const all=[...page.querySelectorAll('div,span,p,b,strong')];
   const lab=all.find(e=>e.children.length===0 && (e.textContent||'').trim().toLowerCase()===label.toLowerCase());
   if(!lab)return;
   const row=lab.closest('.card,.profile-row,.setting-row,.row')||lab.parentElement;
   if(!row)return;
   const texts=[...row.querySelectorAll('div,span,p,b,strong')].filter(e=>e!==lab&&e.children.length===0);
   const target=texts[texts.length-1];
   if(target)target.textContent=value;
 }
 function fmtKg(v){return Number(v).toFixed(1).replace('.',',')+' кг'}
 function applyAll(j){
   if(!j)return;
   if(j.profile){
     setProfileRow('Рост',String(j.profile.height).match(/\d{2,3}/)?.[0]+' см');
     setProfileRow('Текущий вес',fmtKg(j.goal_progress?.current_weight??j.profile.weight));
     if(j.profile.activity)setProfileRow('Активность',j.profile.activity);
     if(j.profile.frequency)setProfileRow('Тренировок в неделю',String(j.profile.frequency).match(/\d+/)?.[0]||j.profile.frequency);
   }
   const gp=j.goal_progress||{};
   const big=[...document.querySelectorAll('[data-page="progress"] .big')];
   if(big[0]&&gp.current_weight!=null)big[0].textContent=fmtKg(gp.current_weight);
   if(big[1]&&gp.target_weight!=null)big[1].textContent=fmtKg(gp.target_weight);
   if(big[2]&&gp.remaining_weight!=null)big[2].textContent=fmtKg(gp.remaining_weight);
   const history=document.getElementById('weightHistoryList');
   const wh=j.weight_history||[];
   if(history)history.innerHTML=wh.length?wh.slice(-12).reverse().map(x=>'<div class="weight-chip">'+new Date(x.created_at).toLocaleDateString('ru-RU',{day:'2-digit',month:'2-digit'})+' · <b>'+fmtKg(x.weight)+'</b></div>').join(''):'<span class="sub">Добавь первый результат</span>';
   const statLabels=[...document.querySelectorAll('[data-page="progress"] *')];
   const trainLabel=statLabels.find(e=>e.children.length===0&&/тренировок за неделю/i.test(e.textContent||''));
   if(trainLabel){const card=trainLabel.closest('.card')||trainLabel.parentElement;const val=card&&card.querySelector('.big');if(val)val.textContent=String(j.workout_progress?.completed_count??0)}
   const ph=document.getElementById('profileInitial');
   if(ph&&j.profile_photo){ph.style.backgroundImage='url("'+j.profile_photo+'")';ph.style.backgroundSize='cover';ph.style.backgroundPosition='center';ph.textContent=''}
 }
 async function fresh(){
   if(!TG_INIT)return;
   try{
     const r=await fetch(API_BASE+'/api/app/bootstrap?ts='+Date.now(),{headers:authHeaders()});
     if(r.ok)applyAll(await r.json());
   }catch(e){}
 }
 // Replace fragile handlers with Telegram initData taken directly from the WebApp SDK.
 const photoInput=document.getElementById('profilePhotoInput');
 if(photoInput){
   photoInput.addEventListener('change',async()=>{
     const file=photoInput.files&&photoInput.files[0];if(!file||!TG_INIT)return;
     const img=new Image(),rd=new FileReader();rd.onload=()=>img.src=rd.result;
     img.onload=async()=>{
       const c=document.createElement('canvas'),scale=Math.min(1,420/Math.max(img.width,img.height));c.width=Math.round(img.width*scale);c.height=Math.round(img.height*scale);c.getContext('2d').drawImage(img,0,0,c.width,c.height);
       const data=c.toDataURL('image/jpeg',.75);
       const r=await fetch(API_BASE+'/api/app/profile/photo',{method:'POST',headers:authHeaders(true),body:JSON.stringify({photo_data:data})});
       if(r.ok){const ph=document.getElementById('profileInitial');if(ph){ph.style.backgroundImage='url("'+data+'")';ph.style.backgroundSize='cover';ph.textContent=''};if(window.showToast)showToast('Фото сохранено')}
     };rd.readAsDataURL(file);
   },true);
 }
 const finish=document.getElementById('finishWorkout');
 if(finish){
   finish.addEventListener('click',async()=>{
     if(!TG_INIT)return;
     try{
       const r=await fetch(API_BASE+'/api/app/workout/complete',{method:'POST',headers:authHeaders(true),body:JSON.stringify({workout_key:'day-'+new Date().toISOString().slice(0,10),workout_name:(document.querySelector('[data-page="workout"] h2')?.textContent||'Тренировка')})});
       if(r.ok){await fresh();if(window.showToast)showToast('Тренировка засчитана в прогресс')}
     }catch(e){}
   },true);
 }
 fresh(); setTimeout(fresh,700); setTimeout(fresh,2200);
})();
</script>
<script>
(()=>{
 let serverData=null, applying=false;
 const kg=v=>v==null?'—':Number(v).toFixed(1).replace('.',',')+' кг';
 const cm=v=>{const m=String(v??'').match(/\d{2,3}/);return m?m[0]+' см':'—'};

 function leafs(root=document){return [...root.querySelectorAll('*')].filter(e=>e.children.length===0)}
 function byExact(label,root=document){return leafs(root).find(e=>(e.textContent||'').trim().toLowerCase()===label.toLowerCase())}
 function setNear(label,value,root=document){
   const lab=byExact(label,root); if(!lab)return false;
   // Profile/settings rows contain free-text values (activity, frequency, etc.).
   // Always update the value leaf inside the SAME row first; never climb into a
   // larger card where another questionnaire answer could be selected.
   const direct=lab.parentElement;
   if(direct){
     const candidates=leafs(direct).filter(e=>e!==lab && (e.textContent||'').trim());
     if(candidates.length){
       const target=candidates[candidates.length-1];
       target.textContent=value; return true;
     }
   }
   let box=lab.parentElement;
   for(let depth=0;box&&depth<3;depth++,box=box.parentElement){
     const candidates=leafs(box).filter(e=>e!==lab && (e.textContent||'').trim() && !/^(Результат|Цель|До цели осталось|Рост|Текущий вес|Цель по весу|Активность|Тренировок в неделю)$/i.test((e.textContent||'').trim()));
     const numeric=candidates.find(e=>/^\s*(?:\d+[,.]?\d*\s*(?:кг|см)?|—)\s*$/i.test(e.textContent||''));
     if(numeric){numeric.textContent=value;return true}
   }
   return false;
 }
 function applyServer(){
   if(!serverData||applying)return; applying=true;
   try{
     const j=serverData,p=j.profile||{},g=j.goal_progress||{};
     setNear('Результат',kg(g.current_weight??p.weight));
     setNear('Цель',kg(g.target_weight));
     setNear('До цели осталось',kg(g.remaining_weight));
     setNear('Рост',cm(p.height));
     setNear('Текущий вес',kg(g.current_weight??p.weight));
     setNear('Цель по весу',kg(g.target_weight));
     if(p.activity)setNear('Активность',p.activity);
     if(p.frequency)setNear('Тренировок в неделю',(String(p.frequency).match(/\d+/)||[p.frequency])[0]);

     // Never show somebody else's/demo goal when this user has no numeric goal saved.
     if(g.target_weight==null){setNear('Цель','—');setNear('До цели осталось','—');setNear('Цель по весу','—')}

     // Profile name must come from this Telegram questionnaire.
     const prof=document.querySelector('[data-page="profile"]')||document;
     if(p.name){
       const h=[...prof.querySelectorAll('h1,h2,h3,.profile-name')].find(e=>/наталья|профиль|^[А-ЯЁA-Z][а-яёa-z]+$/i.test((e.textContent||'').trim()));
       if(h && !/профиль/i.test(h.textContent||''))h.textContent=p.name;
     }
     const ph=document.getElementById('profileInitial');
     if(ph){
       if(j.profile_photo){ph.style.backgroundImage='url("'+j.profile_photo+'")';ph.style.backgroundSize='cover';ph.style.backgroundPosition='center';ph.textContent=''}
       else if(p.name)ph.textContent=p.name.trim().charAt(0).toUpperCase();
     }
   }finally{applying=false}
 }
 async function loadServer(){
   const init=(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.initData)||'';
   if(!init)return;
   try{
     const r=await fetch('/api/app/bootstrap?authoritative='+Date.now(),{headers:{'X-Telegram-Init-Data':init,'Cache-Control':'no-store'}});
     if(r.ok){serverData=await r.json();applyServer()}
   }catch(e){}
 }
 let timer=0;
 new MutationObserver(()=>{if(serverData&&!applying){clearTimeout(timer);timer=setTimeout(applyServer,30)}}).observe(document.body,{subtree:true,childList:true,characterData:true});
 loadServer();setTimeout(loadServer,600);setTimeout(loadServer,1800);
})();
</script>
<script>
(()=>{
 const fancy=/(лосос|с[её]мг|форел|кревет|морепродукт|киноа|авокад|чиа|тунец)/i;
 const ordinary=[
   /минтай.*рис|рис.*минтай|белая рыба.*рис/i,
   /куриц.*греч|греч.*куриц/i,
   /куриц.*рис|рис.*куриц/i,
   /творог.*яблок|творог.*банан/i,
   /омлет.*овощ|яйц.*овощ/i,
   /йогурт.*банан|кефир.*овсян/i
 ];
 function mealName(x){return String(x?.name||x?.title||x?.label||'')}
 function clone(x){try{return JSON.parse(JSON.stringify(x))}catch{return null}}
 function sanitizeLibrary(){
   try{
     if(typeof mealLibrary==='undefined'||!mealLibrary)return false;
     const entries=Object.entries(mealLibrary), vals=entries.map(x=>x[1]);
     const pools=ordinary.map(rx=>vals.find(v=>rx.test(mealName(v)))).filter(Boolean);
     let n=0;
     for(const [key,item] of entries){
       if(!fancy.test(mealName(item)))continue;
       const replacement=pools[n%pools.length]; n++;
       if(replacement){
         const c=clone(replacement);
         Object.keys(item).forEach(k=>delete item[k]);
         Object.assign(item,c);
       }else{
         const name=mealName(item);
         const simple=/лосос|с[её]мг|форел|тунец/i.test(name)?'Минтай с рисом и овощами':
                      /кревет|морепродукт/i.test(name)?'Курица с рисом и овощами':
                      /киноа/i.test(name)?'Гречка с курицей и овощами':
                      /авокад/i.test(name)?'Яйца с тостом и овощами':
                      'Овсянка с яблоком';
         if('name'in item)item.name=simple;
         if('title'in item)item.title=simple;
         if('label'in item)item.label=simple;
       }
     }
     return true;
   }catch(e){return false}
 }
 function sanitizeVisible(){
   document.querySelectorAll('*').forEach(el=>{
     if(el.children.length||!fancy.test(el.textContent||''))return;
     let t=el.textContent;
     t=t.replace(/лосос[^·,;]*/ig,'Минтай с рисом и овощами')
        .replace(/[сc][её]мг[^·,;]*/ig,'Минтай с картофелем')
        .replace(/форел[^·,;]*/ig,'Минтай с овощами')
        .replace(/кревет[^·,;]*/ig,'Курица с рисом и овощами')
        .replace(/киноа[^·,;]*/ig,'Гречка с курицей')
        .replace(/авокад[^·,;]*/ig,'Яйца с овощами')
        .replace(/чиа[^·,;]*/ig,'Овсянка с яблоком')
        .replace(/тунец[^·,;]*/ig,'Курица с овощами');
     el.textContent=t;
   });
 }
 function run(){
   const changed=sanitizeLibrary();
   if(changed){try{if(typeof renderWeek==='function')renderWeek();if(typeof renderMeals==='function')renderMeals()}catch(e){}}
   sanitizeVisible();
 }
 run();setTimeout(run,300);setTimeout(run,1200);
 let busy=false;
 new MutationObserver(()=>{if(busy)return;busy=true;setTimeout(()=>{run();busy=false},60)}).observe(document.body,{subtree:true,childList:true});
})();
</script>
<style id="fitmy-sub-style">
#fitmyTrialBar{position:fixed;left:16px;right:16px;bottom:88px;z-index:9997;background:#f7f3e9;border:1px solid rgba(31,74,43,.16);border-radius:18px;padding:10px 12px;display:flex;align-items:center;justify-content:space-between;gap:10px;box-shadow:0 8px 30px rgba(30,55,35,.10);font:13px/1.25 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#173b25}
#fitmyTrialBar button,#fitmyPaywall button{border:0;border-radius:14px;background:#214d2c;color:#fff;padding:10px 13px;font-weight:700}
#fitmyPaywall{position:fixed;inset:0;z-index:10000;background:rgba(245,241,231,.97);display:flex;align-items:center;justify-content:center;padding:24px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
#fitmyPayCard{max-width:390px;width:100%;background:#fffdf8;border-radius:28px;padding:28px 22px;text-align:center;box-shadow:0 18px 60px rgba(30,55,35,.14);color:#173b25}
#fitmyPayCard h2{font:700 30px/1.05 Georgia,serif;margin:0 0 12px}#fitmyPayCard p{line-height:1.45;color:#536057}
#fitmyPayCard .price{font:700 26px/1.1 Georgia,serif;margin:18px 0 6px}#fitmyPayCard button{width:100%;font-size:16px;padding:14px;margin-top:14px}
#fitmyPayCard .terms{background:transparent;color:#355b3f;font-size:13px;padding:8px}
</style>
<script>
(()=>{
 const PRICE=350;
 function terms(){
   const t='14 дней бесплатно. Далее 350 Telegram Stars за каждые 30 дней. После первой оплаты подписка продлевается автоматически каждые 30 дней, пока автопродление не отменено. При отмене оплаченный доступ действует до конца периода. По вопросам оплаты: /paysupport.';
   try{Telegram.WebApp.showPopup({title:'Условия подписки',message:t,buttons:[{type:'ok'}]})}catch(e){alert(t)}
 }
 async function pay(){
   const init=(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.initData)||'';
   if(!init)return;
   try{
     const r=await fetch('/api/app/subscription/checkout',{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':init},body:JSON.stringify({terms_accepted:true})});
     const j=await r.json();
     if(!r.ok){if(j.error==='already_active')location.reload();return}
     const link=j.invoice_link;
     if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.openInvoice){
       Telegram.WebApp.openInvoice(link,status=>{if(status==='paid')setTimeout(()=>location.reload(),700)});
     }else location.href=link;
   }catch(e){}
 }
 function render(sub){
   document.getElementById('fitmyTrialBar')?.remove();
   document.getElementById('fitmyPaywall')?.remove();
   if(!sub)return;
   if(sub.status==='trial'){
     const bar=document.createElement('div');bar.id='fitmyTrialBar';
     bar.innerHTML='<span><b>Бесплатный период</b><br>Осталось '+sub.days_left+' дн.</span><button type="button">Подписка</button>';
     bar.querySelector('button').onclick=pay;document.body.appendChild(bar);
   }else if(sub.status==='expired'){
     const ov=document.createElement('div');ov.id='fitmyPaywall';
     ov.innerHTML='<div id="fitmyPayCard"><h2>Продолжить с Fitmy2.0</h2><p>Пробный период закончился. Рацион, тренировки, прогресс и ИИ-агент снова откроются после оформления подписки.</p><div class="price">'+PRICE+' ⭐</div><p>на 30 дней · с автоматическим продлением</p><button id="fitmyPayBtn" type="button">Принимаю условия · оплатить '+PRICE+' ⭐</button><button id="fitmyTermsBtn" class="terms" type="button">Условия подписки</button></div>';
     ov.querySelector('#fitmyPayBtn').onclick=pay;ov.querySelector('#fitmyTermsBtn').onclick=terms;document.body.appendChild(ov);
   }
 }
 async function load(){
   const init=(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.initData)||'';
   if(!init)return;
   try{const r=await fetch('/api/app/bootstrap?subscription='+Date.now(),{headers:{'X-Telegram-Init-Data':init,'Cache-Control':'no-store'}});if(r.ok){const j=await r.json();render(j.subscription)}}catch(e){}
 }
 load();setTimeout(load,900);
})();
</script>
"""

ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fitmyn")

router = Router()
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)

bot = Bot(TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None
client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL) if OPENAI_API_KEY else None
pool: asyncpg.Pool | None = None

_seen_update_ids: dict[int, float] = {}
_update_tasks: set[asyncio.Task] = set()
UPDATE_DEDUPE_TTL = 600

APP_MEAL_TYPE_ORDER = ["Завтрак", "Обед", "Перекус", "Ужин"]
APP_MEAL_CATALOG = {
    "oatsApple": {"type": "Завтрак", "name": "Овсянка с яблоком и корицей", "kcal": 330, "cook": 10, "protein": 23, "fat": 10, "carbs": 37, "budget": True, "goals": ["loss","maintain"]},
    "oatsBanana": {"type": "Завтрак", "name": "Овсянка с бананом", "kcal": 370, "cook": 10, "protein": 26, "fat": 12, "carbs": 40, "budget": True, "goals": ["loss","maintain"]},
    "milletPumpkin": {"type": "Завтрак", "name": "Пшённая каша с тыквой", "kcal": 340, "cook": 20, "protein": 24, "fat": 11, "carbs": 36, "budget": True, "goals": ["loss","maintain"]},
    "ricePorridge": {"type": "Завтрак", "name": "Рисовая каша с яблоком", "kcal": 350, "cook": 20, "protein": 25, "fat": 11, "carbs": 38, "budget": True, "goals": ["loss","maintain"]},
    "buckwheatEgg": {"type": "Завтрак", "name": "Гречка с яйцом и овощами", "kcal": 390, "cook": 15, "protein": 27, "fat": 12, "carbs": 44, "budget": True, "goals": ["loss","maintain"]},
    "omeletVeg": {"type": "Завтрак", "name": "Омлет с овощами", "kcal": 350, "cook": 12, "protein": 25, "fat": 11, "carbs": 38, "budget": True, "goals": ["loss","maintain"]},
    "eggsToast": {"type": "Завтрак", "name": "Яйца с цельнозерновым тостом", "kcal": 380, "cook": 10, "protein": 27, "fat": 12, "carbs": 41, "budget": True, "goals": ["loss","maintain"]},
    "cottageApple": {"type": "Завтрак", "name": "Творог с яблоком и корицей", "kcal": 320, "cook": 5, "protein": 22, "fat": 10, "carbs": 36, "budget": True, "goals": ["loss","maintain"]},
    "cottageBanana2": {"type": "Завтрак", "name": "Творог с бананом", "kcal": 380, "cook": 5, "protein": 27, "fat": 12, "carbs": 41, "budget": True, "goals": ["loss","maintain"]},
    "kefirOats": {"type": "Завтрак", "name": "Ленивая овсянка на кефире", "kcal": 360, "cook": 5, "protein": 25, "fat": 11, "carbs": 40, "budget": True, "goals": ["loss","maintain"]},
    "cheeseOmelet": {"type": "Завтрак", "name": "Омлет с сыром и томатами", "kcal": 420, "cook": 12, "protein": 29, "fat": 13, "carbs": 47, "budget": True, "goals": ["loss","maintain","gain"]},
    "oatPancakes": {"type": "Завтрак", "name": "Овсяноблин с творогом", "kcal": 410, "cook": 15, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "syrniki": {"type": "Завтрак", "name": "Сырники в духовке", "kcal": 430, "cook": 25, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "lavashEgg": {"type": "Завтрак", "name": "Лаваш с яйцом и сыром", "kcal": 440, "cook": 12, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "sandwichChicken": {"type": "Завтрак", "name": "Сэндвич с курицей и яйцом", "kcal": 470, "cook": 10, "protein": 33, "fat": 15, "carbs": 51, "budget": True, "goals": ["maintain","gain"]},
    "buckwheatMilk": {"type": "Завтрак", "name": "Гречневая каша с молоком", "kcal": 360, "cook": 15, "protein": 25, "fat": 11, "carbs": 40, "budget": True, "goals": ["loss","maintain"]},
    "semolinaBerry": {"type": "Завтрак", "name": "Манная каша с ягодами", "kcal": 350, "cook": 10, "protein": 25, "fat": 11, "carbs": 38, "budget": True, "goals": ["loss","maintain"]},
    "cottageCarrot": {"type": "Завтрак", "name": "Творожная запеканка с морковью", "kcal": 400, "cook": 35, "protein": 28, "fat": 12, "carbs": 45, "budget": True, "goals": ["loss","maintain","gain"]},
    "eggPotato": {"type": "Завтрак", "name": "Яйца с картофелем и овощами", "kcal": 450, "cook": 20, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "oatsCottage": {"type": "Завтрак", "name": "Овсянка с творогом и бананом", "kcal": 460, "cook": 10, "protein": 32, "fat": 14, "carbs": 52, "budget": True, "goals": ["maintain","gain"]},
    "pitaOmelet": {"type": "Завтрак", "name": "Пита с омлетом и овощами", "kcal": 450, "cook": 15, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "toastCottage": {"type": "Завтрак", "name": "Тосты с творогом и бананом", "kcal": 400, "cook": 7, "protein": 28, "fat": 12, "carbs": 45, "budget": True, "goals": ["loss","maintain","gain"]},
    "applePancakes": {"type": "Завтрак", "name": "Яблочные овсяные оладьи", "kcal": 390, "cook": 18, "protein": 27, "fat": 12, "carbs": 44, "budget": True, "goals": ["loss","maintain"]},
    "eggRice": {"type": "Завтрак", "name": "Рис с яйцом и овощами", "kcal": 430, "cook": 15, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "cottageRaisins": {"type": "Завтрак", "name": "Творог с изюмом и овсянкой", "kcal": 420, "cook": 5, "protein": 29, "fat": 13, "carbs": 47, "budget": True, "goals": ["loss","maintain","gain"]},
    "omeletChicken": {"type": "Завтрак", "name": "Омлет с курицей", "kcal": 470, "cook": 15, "protein": 33, "fat": 15, "carbs": 51, "budget": True, "goals": ["maintain","gain"]},
    "bananaPorridge": {"type": "Завтрак", "name": "Пшённая каша с бананом", "kcal": 390, "cook": 20, "protein": 27, "fat": 12, "carbs": 44, "budget": True, "goals": ["loss","maintain"]},
    "bakedOats": {"type": "Завтрак", "name": "Запечённая овсянка с яблоком", "kcal": 410, "cook": 30, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "eggBeans": {"type": "Завтрак", "name": "Яйца с фасолью и томатами", "kcal": 440, "cook": 15, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "curdLavash": {"type": "Завтрак", "name": "Лаваш с творогом и яблоком", "kcal": 430, "cook": 15, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "chickenBuckwheat": {"type": "Обед", "name": "Курица с гречкой и овощами", "kcal": 500, "cook": 25, "protein": 35, "fat": 16, "carbs": 54, "budget": True, "goals": ["maintain","gain"]},
    "chickenRice": {"type": "Обед", "name": "Курица с рисом и овощами", "kcal": 520, "cook": 25, "protein": 36, "fat": 16, "carbs": 58, "budget": True, "goals": ["maintain","gain"]},
    "chickenPasta": {"type": "Обед", "name": "Паста с курицей и томатами", "kcal": 540, "cook": 25, "protein": 38, "fat": 17, "carbs": 59, "budget": True, "goals": ["maintain","gain"]},
    "chickenPotato": {"type": "Обед", "name": "Курица с картофелем и салатом", "kcal": 510, "cook": 30, "protein": 36, "fat": 16, "carbs": 56, "budget": True, "goals": ["maintain","gain"]},
    "turkeyRice": {"type": "Обед", "name": "Индейка с рисом и морковью", "kcal": 520, "cook": 25, "protein": 36, "fat": 16, "carbs": 58, "budget": True, "goals": ["maintain","gain"]},
    "turkeyPasta": {"type": "Обед", "name": "Макароны с индейкой в томатном соусе", "kcal": 540, "cook": 25, "protein": 38, "fat": 17, "carbs": 59, "budget": True, "goals": ["maintain","gain"]},
    "beefBarley": {"type": "Обед", "name": "Говядина с перловкой", "kcal": 530, "cook": 35, "protein": 37, "fat": 16, "carbs": 60, "budget": True, "goals": ["maintain","gain"]},
    "beefRice": {"type": "Обед", "name": "Говядина с рисом и овощами", "kcal": 550, "cook": 30, "protein": 39, "fat": 17, "carbs": 60, "budget": True, "goals": ["maintain","gain"]},
    "liverBuckwheat": {"type": "Обед", "name": "Куриная печень с гречкой", "kcal": 490, "cook": 25, "protein": 34, "fat": 15, "carbs": 55, "budget": True, "goals": ["maintain","gain"]},
    "liverPotato": {"type": "Обед", "name": "Печень с картофельным пюре", "kcal": 510, "cook": 30, "protein": 36, "fat": 16, "carbs": 56, "budget": True, "goals": ["maintain","gain"]},
    "pollockRice": {"type": "Обед", "name": "Минтай с рисом и овощами", "kcal": 480, "cook": 25, "protein": 34, "fat": 15, "carbs": 52, "budget": True, "goals": ["maintain","gain"]},
    "pollockPotato": {"type": "Обед", "name": "Минтай с картофелем и салатом", "kcal": 470, "cook": 30, "protein": 33, "fat": 15, "carbs": 51, "budget": True, "goals": ["maintain","gain"]},
    "mackerelPotato": {"type": "Обед", "name": "Скумбрия с картофелем и капустой", "kcal": 540, "cook": 30, "protein": 38, "fat": 17, "carbs": 59, "budget": True, "goals": ["maintain","gain"]},
    "tunaRice": {"type": "Обед", "name": "Рис с тунцом и кукурузой", "kcal": 500, "cook": 15, "protein": 35, "fat": 16, "carbs": 54, "budget": True, "goals": ["maintain","gain"]},
    "lentilChicken": {"type": "Обед", "name": "Чечевица с курицей и овощами", "kcal": 510, "cook": 30, "protein": 36, "fat": 16, "carbs": 56, "budget": True, "goals": ["maintain","gain"]},
    "lentilStew": {"type": "Обед", "name": "Чечевичное рагу с овощами", "kcal": 450, "cook": 30, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "beansRice": {"type": "Обед", "name": "Фасоль с рисом и овощами", "kcal": 470, "cook": 25, "protein": 33, "fat": 15, "carbs": 51, "budget": True, "goals": ["maintain","gain"]},
    "peasChicken": {"type": "Обед", "name": "Гороховое пюре с курицей", "kcal": 510, "cook": 35, "protein": 36, "fat": 16, "carbs": 56, "budget": True, "goals": ["maintain","gain"]},
    "chickenBorscht": {"type": "Обед", "name": "Борщ с курицей и сметаной", "kcal": 440, "cook": 45, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "peaSoup": {"type": "Обед", "name": "Гороховый суп с курицей", "kcal": 460, "cook": 45, "protein": 32, "fat": 14, "carbs": 52, "budget": True, "goals": ["maintain","gain"]},
    "chickenNoodleSoup": {"type": "Обед", "name": "Куриный суп с лапшой", "kcal": 430, "cook": 35, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "meatballsBuckwheat": {"type": "Обед", "name": "Куриные тефтели с гречкой", "kcal": 510, "cook": 35, "protein": 36, "fat": 16, "carbs": 56, "budget": True, "goals": ["maintain","gain"]},
    "meatballsPasta": {"type": "Обед", "name": "Тефтели из индейки с макаронами", "kcal": 530, "cook": 35, "protein": 37, "fat": 16, "carbs": 60, "budget": True, "goals": ["maintain","gain"]},
    "cabbageChicken": {"type": "Обед", "name": "Тушёная капуста с курицей", "kcal": 460, "cook": 35, "protein": 32, "fat": 14, "carbs": 52, "budget": True, "goals": ["maintain","gain"]},
    "lazyCabbageRolls": {"type": "Обед", "name": "Ленивые голубцы с рисом", "kcal": 500, "cook": 40, "protein": 35, "fat": 16, "carbs": 54, "budget": True, "goals": ["maintain","gain"]},
    "pilafChicken": {"type": "Обед", "name": "Домашний плов с курицей", "kcal": 550, "cook": 40, "protein": 39, "fat": 17, "carbs": 60, "budget": True, "goals": ["maintain","gain"]},
    "pastaBeans": {"type": "Обед", "name": "Паста с фасолью и томатами", "kcal": 480, "cook": 20, "protein": 34, "fat": 15, "carbs": 52, "budget": True, "goals": ["maintain","gain"]},
    "buckwheatMushroomChicken": {"type": "Обед", "name": "Гречка с курицей и грибами", "kcal": 520, "cook": 30, "protein": 36, "fat": 16, "carbs": 58, "budget": True, "goals": ["maintain","gain"]},
    "potatoTurkeyStew": {"type": "Обед", "name": "Картофельное рагу с индейкой", "kcal": 500, "cook": 35, "protein": 35, "fat": 16, "carbs": 54, "budget": True, "goals": ["maintain","gain"]},
    "barleyChicken": {"type": "Обед", "name": "Перловка с курицей и овощами", "kcal": 490, "cook": 40, "protein": 34, "fat": 15, "carbs": 55, "budget": True, "goals": ["maintain","gain"]},
    "appleKefir": {"type": "Перекус", "name": "Яблоко и кефир", "kcal": 190, "cook": 2, "protein": 9, "fat": 6, "carbs": 25, "budget": True, "goals": ["loss","maintain"]},
    "bananaKefir": {"type": "Перекус", "name": "Банан и кефир", "kcal": 220, "cook": 2, "protein": 10, "fat": 7, "carbs": 29, "budget": True, "goals": ["loss","maintain"]},
    "cottageAppleSnack": {"type": "Перекус", "name": "Творог с яблоком", "kcal": 230, "cook": 4, "protein": 10, "fat": 7, "carbs": 32, "budget": True, "goals": ["loss","maintain"]},
    "cottageBananaSnack": {"type": "Перекус", "name": "Творог с бананом", "kcal": 270, "cook": 4, "protein": 12, "fat": 8, "carbs": 38, "budget": True, "goals": ["loss","maintain"]},
    "yogurtApple": {"type": "Перекус", "name": "Йогурт с яблоком и овсянкой", "kcal": 240, "cook": 4, "protein": 11, "fat": 7, "carbs": 33, "budget": True, "goals": ["loss","maintain"]},
    "yogurtBanana": {"type": "Перекус", "name": "Йогурт с бананом", "kcal": 230, "cook": 3, "protein": 10, "fat": 7, "carbs": 32, "budget": True, "goals": ["loss","maintain"]},
    "eggToastSnack": {"type": "Перекус", "name": "Яйцо и цельнозерновой тост", "kcal": 220, "cook": 8, "protein": 10, "fat": 7, "carbs": 29, "budget": True, "goals": ["loss","maintain"]},
    "cheeseApple": {"type": "Перекус", "name": "Сыр и яблоко", "kcal": 230, "cook": 2, "protein": 10, "fat": 7, "carbs": 32, "budget": True, "goals": ["loss","maintain"]},
    "kefirOatSnack": {"type": "Перекус", "name": "Кефир с овсяными хлопьями", "kcal": 220, "cook": 3, "protein": 10, "fat": 7, "carbs": 29, "budget": True, "goals": ["loss","maintain"]},
    "carrotHummus": {"type": "Перекус", "name": "Морковь с домашним хумусом", "kcal": 210, "cook": 5, "protein": 9, "fat": 7, "carbs": 28, "budget": True, "goals": ["loss","maintain"]},
    "bananaPeanutBudget": {"type": "Перекус", "name": "Банан с арахисовой пастой", "kcal": 250, "cook": 3, "protein": 11, "fat": 8, "carbs": 34, "budget": True, "goals": ["loss","maintain"]},
    "applePeanutBudget": {"type": "Перекус", "name": "Яблоко с арахисовой пастой", "kcal": 230, "cook": 3, "protein": 10, "fat": 7, "carbs": 32, "budget": True, "goals": ["loss","maintain"]},
    "curdRaisins": {"type": "Перекус", "name": "Творог с изюмом", "kcal": 250, "cook": 4, "protein": 11, "fat": 8, "carbs": 34, "budget": True, "goals": ["loss","maintain"]},
    "yogurtSeeds": {"type": "Перекус", "name": "Йогурт с семечками", "kcal": 240, "cook": 3, "protein": 11, "fat": 7, "carbs": 33, "budget": True, "goals": ["loss","maintain"]},
    "milkBanana": {"type": "Перекус", "name": "Молочно-банановый коктейль", "kcal": 250, "cook": 4, "protein": 11, "fat": 8, "carbs": 34, "budget": True, "goals": ["loss","maintain"]},
    "ryazhenkaApple": {"type": "Перекус", "name": "Ряженка и яблоко", "kcal": 220, "cook": 2, "protein": 10, "fat": 7, "carbs": 29, "budget": True, "goals": ["loss","maintain"]},
    "eggCucumber": {"type": "Перекус", "name": "Яйца и огурец", "kcal": 200, "cook": 8, "protein": 9, "fat": 6, "carbs": 28, "budget": True, "goals": ["loss","maintain"]},
    "toastCheese": {"type": "Перекус", "name": "Тост с сыром и томатом", "kcal": 250, "cook": 6, "protein": 11, "fat": 8, "carbs": 34, "budget": True, "goals": ["loss","maintain"]},
    "cottageCarrotSnack": {"type": "Перекус", "name": "Творог с морковью и зеленью", "kcal": 210, "cook": 5, "protein": 9, "fat": 7, "carbs": 28, "budget": True, "goals": ["loss","maintain"]},
    "beansToast": {"type": "Перекус", "name": "Паштет из фасоли с хлебцем", "kcal": 230, "cook": 7, "protein": 10, "fat": 7, "carbs": 32, "budget": True, "goals": ["loss","maintain"]},
    "bakedAppleCurd": {"type": "Перекус", "name": "Запечённое яблоко с творогом", "kcal": 250, "cook": 20, "protein": 11, "fat": 8, "carbs": 34, "budget": True, "goals": ["loss","maintain"]},
    "bananaOatsSnack": {"type": "Перекус", "name": "Банан с овсянкой и йогуртом", "kcal": 270, "cook": 5, "protein": 12, "fat": 8, "carbs": 38, "budget": True, "goals": ["loss","maintain"]},
    "kefirCottage": {"type": "Перекус", "name": "Кефир и творог", "kcal": 240, "cook": 3, "protein": 11, "fat": 7, "carbs": 33, "budget": True, "goals": ["loss","maintain"]},
    "appleSunflower": {"type": "Перекус", "name": "Яблоко с семечками", "kcal": 210, "cook": 2, "protein": 9, "fat": 7, "carbs": 28, "budget": True, "goals": ["loss","maintain"]},
    "pearYogurt": {"type": "Перекус", "name": "Груша с йогуртом", "kcal": 220, "cook": 3, "protein": 10, "fat": 7, "carbs": 29, "budget": True, "goals": ["loss","maintain"]},
    "curdCocoa": {"type": "Перекус", "name": "Творог с какао и бананом", "kcal": 270, "cook": 4, "protein": 12, "fat": 8, "carbs": 38, "budget": True, "goals": ["loss","maintain"]},
    "eggLavashSnack": {"type": "Перекус", "name": "Мини-лаваш с яйцом", "kcal": 260, "cook": 10, "protein": 12, "fat": 8, "carbs": 35, "budget": True, "goals": ["loss","maintain"]},
    "oatCookieKefir": {"type": "Перекус", "name": "Домашнее овсяное печенье и кефир", "kcal": 250, "cook": 20, "protein": 11, "fat": 8, "carbs": 34, "budget": True, "goals": ["loss","maintain"]},
    "cheeseCucumberToast": {"type": "Перекус", "name": "Тост с сыром и огурцом", "kcal": 240, "cook": 5, "protein": 11, "fat": 7, "carbs": 33, "budget": True, "goals": ["loss","maintain"]},
    "bananaCottageMini": {"type": "Перекус", "name": "Банан с творогом", "kcal": 260, "cook": 3, "protein": 12, "fat": 8, "carbs": 35, "budget": True, "goals": ["loss","maintain"]},
    "chickenCabbage": {"type": "Ужин", "name": "Курица с тушёной капустой", "kcal": 400, "cook": 30, "protein": 28, "fat": 12, "carbs": 45, "budget": True, "goals": ["loss","maintain","gain"]},
    "chickenVeg": {"type": "Ужин", "name": "Курица с овощами на сковороде", "kcal": 410, "cook": 25, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "chickenBuckwheatDinner": {"type": "Ужин", "name": "Курица с гречкой и салатом", "kcal": 440, "cook": 25, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "turkeyCabbage": {"type": "Ужин", "name": "Индейка с капустой и морковью", "kcal": 410, "cook": 30, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "turkeyVeg": {"type": "Ужин", "name": "Индейка с овощным рагу", "kcal": 420, "cook": 30, "protein": 29, "fat": 13, "carbs": 47, "budget": True, "goals": ["loss","maintain","gain"]},
    "pollockVeg": {"type": "Ужин", "name": "Минтай с овощами", "kcal": 380, "cook": 25, "protein": 27, "fat": 12, "carbs": 41, "budget": True, "goals": ["loss","maintain"]},
    "pollockPotatoDinner": {"type": "Ужин", "name": "Минтай с картофелем и огурцом", "kcal": 430, "cook": 30, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "mackerelSalad": {"type": "Ужин", "name": "Скумбрия с капустным салатом", "kcal": 450, "cook": 25, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "liverVeg": {"type": "Ужин", "name": "Куриная печень с овощами", "kcal": 410, "cook": 25, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "liverBuckwheatDinner": {"type": "Ужин", "name": "Печень с гречкой и огурцом", "kcal": 440, "cook": 25, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "omeletDinner": {"type": "Ужин", "name": "Омлет с овощами и сыром", "kcal": 390, "cook": 15, "protein": 27, "fat": 12, "carbs": 44, "budget": True, "goals": ["loss","maintain"]},
    "cottageDinner": {"type": "Ужин", "name": "Творог с зеленью и овощами", "kcal": 340, "cook": 5, "protein": 24, "fat": 11, "carbs": 36, "budget": True, "goals": ["loss","maintain"]},
    "beansChicken": {"type": "Ужин", "name": "Фасоль с курицей и томатами", "kcal": 430, "cook": 25, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "lentilTurkey": {"type": "Ужин", "name": "Чечевица с индейкой", "kcal": 440, "cook": 30, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "lentilVegDinner": {"type": "Ужин", "name": "Чечевица с овощами", "kcal": 390, "cook": 25, "protein": 27, "fat": 12, "carbs": 44, "budget": True, "goals": ["loss","maintain"]},
    "cabbageMeatballs": {"type": "Ужин", "name": "Капуста с куриными тефтелями", "kcal": 420, "cook": 35, "protein": 29, "fat": 13, "carbs": 47, "budget": True, "goals": ["loss","maintain","gain"]},
    "zucchiniChicken": {"type": "Ужин", "name": "Кабачки с курицей и томатами", "kcal": 390, "cook": 25, "protein": 27, "fat": 12, "carbs": 44, "budget": True, "goals": ["loss","maintain"]},
    "eggBeansDinner": {"type": "Ужин", "name": "Яйца с фасолью и овощами", "kcal": 400, "cook": 15, "protein": 28, "fat": 12, "carbs": 45, "budget": True, "goals": ["loss","maintain","gain"]},
    "buckwheatMushroomDinner": {"type": "Ужин", "name": "Гречка с грибами и яйцом", "kcal": 410, "cook": 25, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "riceChickenDinner": {"type": "Ужин", "name": "Рис с курицей и овощами", "kcal": 450, "cook": 25, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "potatoChickenDinner": {"type": "Ужин", "name": "Картофель с курицей и салатом", "kcal": 450, "cook": 30, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "pastaTurkeyDinner": {"type": "Ужин", "name": "Паста с индейкой и овощами", "kcal": 460, "cook": 25, "protein": 32, "fat": 14, "carbs": 52, "budget": True, "goals": ["maintain","gain"]},
    "fishCabbage": {"type": "Ужин", "name": "Белая рыба с тушёной капустой", "kcal": 380, "cook": 25, "protein": 27, "fat": 12, "carbs": 41, "budget": True, "goals": ["loss","maintain"]},
    "chickenPumpkin": {"type": "Ужин", "name": "Курица с тыквой и гречкой", "kcal": 430, "cook": 30, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "turkeyPotatoDinner": {"type": "Ужин", "name": "Индейка с картофелем и овощами", "kcal": 450, "cook": 30, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "curdCasseroleDinner": {"type": "Ужин", "name": "Творожная запеканка без сахара", "kcal": 380, "cook": 35, "protein": 27, "fat": 12, "carbs": 41, "budget": True, "goals": ["loss","maintain"]},
    "omeletChickenDinner": {"type": "Ужин", "name": "Омлет с курицей и томатами", "kcal": 430, "cook": 15, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "beansVegDinner": {"type": "Ужин", "name": "Фасоль с овощами и яйцом", "kcal": 410, "cook": 25, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "chickenBarleyDinner": {"type": "Ужин", "name": "Курица с перловкой и овощами", "kcal": 440, "cook": 35, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "pollockBuckwheat": {"type": "Ужин", "name": "Минтай с гречкой и салатом", "kcal": 420, "cook": 25, "protein": 29, "fat": 13, "carbs": 47, "budget": True, "goals": ["loss","maintain","gain"]},
}


_main_rows = []
if APP_URL:
    _main_rows.append([KeyboardButton(text="📱 Открыть Fitmy2.0", web_app=WebAppInfo(url=APP_URL))])
_main_rows.extend([
    [KeyboardButton(text="🥗 Питание"), KeyboardButton(text="🏋️ Тренировка")],
    [KeyboardButton(text="📊 Отчёт"), KeyboardButton(text="📅 Неделя")],
    [KeyboardButton(text="🗓 Рацион на неделю"), KeyboardButton(text="🛒 Список покупок")],
    [KeyboardButton(text="💬 Спросить агента"), KeyboardButton(text="👤 Мой профиль")],
    [KeyboardButton(text="⏰ Расписание")],
])
MAIN_KB = ReplyKeyboardMarkup(keyboard=_main_rows, resize_keyboard=True)

CONSENT_KB = InlineKeyboardMarkup(
    inline_keyboard=[[
        InlineKeyboardButton(text="Согласен", callback_data="consent_yes"),
        InlineKeyboardButton(text="Не согласен", callback_data="consent_no"),
    ]]
)

SYSTEM_PROMPT = """
Ты — персональный ИИ-ассистент по питанию, тренировкам, восстановлению и устойчивым привычкам.

Работай как помощник по питанию, персональный тренер, трекер прогресса и коуч по привычкам.

Правила безопасности:
- Не ставь диагнозы и не заменяй врача.
- Не назначай лекарства, БАДы, гормоны или лечение.
- Не рекомендуй экстремальные диеты, длительное голодание, обезвоживание, очищения или опасное снижение веса.
- Не стыди человека за еду, вес, внешность или пропущенные тренировки.
- При боли в груди, выраженной одышке, обмороке, сильной необычной боли и других потенциально опасных симптомах
  рекомендуй прекратить тренировку и обратиться за медицинской помощью.
- При беременности, расстройствах пищевого поведения, серьёзных травмах, хронических заболеваниях или значимых лекарствах
  действуй осторожно и при необходимости рекомендуй консультацию профильного специалиста.
- Не создавай ложную точность для калорий и КБЖУ.
- Для тренировок учитывай уровень, ограничения, оборудование, восстановление и постепенную прогрессию.
- Для питания учитывай предпочтения, доступность продуктов, поездки, домашнюю еду и рестораны.
- Не раскрывай данные других пользователей.
- Для командной механики не соревнуй людей по весу, калориям или внешности.

Стиль ответа для Telegram:
- Пиши простым живым русским языком.
- Не используй Markdown-разметку: никаких **, ##, ``` и таблиц.
- Не используй HTML-теги, включая <br>.
- Не используй таблицы и вертикальные черты |.
- Делай короткие абзацы и списки с символом •.
- Для нумерации используй обычные 1., 2., 3.
- Заголовок — одна короткая строка с подходящим эмодзи.
- Не делай длинное полотно текста.
- Не повторяй данные профиля без необходимости.
- Для тренировки используй блоки: Цель, Разминка, Основная часть, Отдых, Заминка, Совет.
- Для питания на день используй блоки: Главная задача, Завтрак, Обед, Ужин, Перекус, Фокус дня.
- Для рациона на неделю составляй реалистичный план на 7 дней без таблиц: завтрак, обед, ужин и 1 перекус на каждый день.
- Рацион должен быть удобным в жизни: повторно используй продукты, учитывай остатки, не добавляй десятки редких ингредиентов.
- Список покупок должен точно соответствовать рациону и быть сгруппирован по категориям с примерным количеством на 1 человека.
- Ответ на обычный запрос обычно должен помещаться примерно в 900–1400 символов.
- Выводи только готовый текст для пользователя, без пояснений про форматирование.
"""

class Onboarding(StatesGroup):
    name = State()
    age = State()
    sex = State()
    height = State()
    weight = State()
    goal = State()
    activity = State()
    frequency = State()
    equipment = State()
    restrictions = State()
    food = State()
    sleep = State()

class Checkin(StatesGroup):
    waiting_report = State()

def now_utc():
    return datetime.now(timezone.utc)

async def db_execute(sql: str, *params):
    if not pool:
        raise RuntimeError("Database is not configured")
    async with pool.acquire() as conn:
        await conn.execute(sql, *params)

async def db_fetchrow(sql: str, *params):
    if not pool:
        raise RuntimeError("Database is not configured")
    async with pool.acquire() as conn:
        return await conn.fetchrow(sql, *params)

async def db_fetch(sql: str, *params):
    if not pool:
        raise RuntimeError("Database is not configured")
    async with pool.acquire() as conn:
        return await conn.fetch(sql, *params)

async def init_db():
    global pool
    if not DATABASE_URL:
        logger.warning("DATABASE_URL is missing; service starts in configuration mode")
        return

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            consent BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL,
            last_seen TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS profiles (
            telegram_id BIGINT PRIMARY KEY,
            name TEXT,
            age TEXT,
            sex TEXT,
            height TEXT,
            weight TEXT,
            goal TEXT,
            activity TEXT,
            frequency TEXT,
            equipment TEXT,
            restrictions TEXT,
            food TEXT,
            sleep TEXT,
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS checkins (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            report TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notification_settings (
            telegram_id BIGINT PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            timezone TEXT NOT NULL DEFAULT 'Europe/Moscow',
            morning_time TEXT NOT NULL DEFAULT '08:00',
            evening_time TEXT NOT NULL DEFAULT '20:30',
            workout_days TEXT NOT NULL DEFAULT '0,2,4',
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notification_log (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            kind TEXT NOT NULL,
            local_date DATE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            UNIQUE(telegram_id, kind, local_date)
        );

        CREATE TABLE IF NOT EXISTS weekly_meal_plans (
            telegram_id BIGINT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            meal_plan TEXT NOT NULL,
            shopping_list TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (telegram_id, start_date)
        );

        CREATE TABLE IF NOT EXISTS app_week_plans (
            telegram_id BIGINT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            plan_json JSONB NOT NULL,
            source TEXT NOT NULL DEFAULT 'fallback',
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (telegram_id, start_date)
        );

        CREATE TABLE IF NOT EXISTS app_goal_settings (
            telegram_id BIGINT PRIMARY KEY,
            target_weight NUMERIC(6,2),
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS app_weight_log (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            weight NUMERIC(6,2) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_app_weight_log_user_time
            ON app_weight_log(telegram_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS app_water_log (
            telegram_id BIGINT NOT NULL,
            local_date DATE NOT NULL,
            water_ml INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (telegram_id, local_date)
        );

        CREATE TABLE IF NOT EXISTS app_workout_log (
            telegram_id BIGINT NOT NULL,
            local_date DATE NOT NULL,
            workout_key TEXT NOT NULL,
            workout_name TEXT NOT NULL,
            completed_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (telegram_id, local_date, workout_key)
        );

        CREATE TABLE IF NOT EXISTS app_profile_photos (
            telegram_id BIGINT PRIMARY KEY,
            photo_data TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS app_subscriptions (
            telegram_id BIGINT PRIMARY KEY,
            trial_started_at TIMESTAMPTZ NOT NULL,
            trial_ends_at TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL DEFAULT 'trial',
            subscription_until TIMESTAMPTZ,
            telegram_payment_charge_id TEXT,
            auto_renew BOOLEAN NOT NULL DEFAULT FALSE,
            stars_amount INTEGER NOT NULL DEFAULT 350,
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS app_payments (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            telegram_payment_charge_id TEXT NOT NULL UNIQUE,
            total_amount INTEGER NOT NULL,
            currency TEXT NOT NULL,
            subscription_expiration_date TIMESTAMPTZ,
            is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
            is_first_recurring BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_app_payments_user_time
            ON app_payments(telegram_id, created_at DESC);
        """)

async def touch_user(message: Message):
    await db_execute(
        """
        INSERT INTO users(telegram_id, username, first_name, created_at, last_seen)
        VALUES ($1, $2, $3, $4, $4)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username=EXCLUDED.username,
            first_name=EXCLUDED.first_name,
            last_seen=EXCLUDED.last_seen
        """,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        now_utc(),
    )

async def has_consent(user_id: int) -> bool:
    row = await db_fetchrow("SELECT consent FROM users WHERE telegram_id=$1", user_id)
    return bool(row and row["consent"])


async def ensure_subscription(user_id: int):
    row = await db_fetchrow("SELECT * FROM app_subscriptions WHERE telegram_id=$1", user_id)
    if row:
        return row
    now = now_utc()
    trial_end = now + timedelta(days=TRIAL_DAYS)
    await db_execute(
        """INSERT INTO app_subscriptions(
            telegram_id, trial_started_at, trial_ends_at, status,
            subscription_until, telegram_payment_charge_id, auto_renew,
            stars_amount, updated_at
        ) VALUES($1,$2,$3,'trial',NULL,NULL,FALSE,$4,$2)
        ON CONFLICT(telegram_id) DO NOTHING""",
        user_id, now, trial_end, SUBSCRIPTION_STARS,
    )
    return await db_fetchrow("SELECT * FROM app_subscriptions WHERE telegram_id=$1", user_id)


async def subscription_info(user_id: int) -> dict:
    row = await ensure_subscription(user_id)
    now = now_utc()
    paid_until = row["subscription_until"]
    paid_active = bool(paid_until and paid_until > now)
    trial_active = bool(row["trial_ends_at"] and row["trial_ends_at"] > now)
    if paid_active:
        status = "active"
        access = True
        seconds_left = max(0, int((paid_until - now).total_seconds()))
        days_left = (seconds_left + 86399) // 86400
    elif trial_active:
        status = "trial"
        access = True
        seconds_left = max(0, int((row["trial_ends_at"] - now).total_seconds()))
        days_left = (seconds_left + 86399) // 86400
    else:
        status = "expired"
        access = False
        days_left = 0
        if row["status"] != "expired":
            await db_execute(
                "UPDATE app_subscriptions SET status='expired', auto_renew=FALSE, updated_at=$2 WHERE telegram_id=$1",
                user_id, now,
            )
    return {
        "status": status,
        "has_access": access,
        "trial_started_at": row["trial_started_at"].isoformat() if row["trial_started_at"] else None,
        "trial_ends_at": row["trial_ends_at"].isoformat() if row["trial_ends_at"] else None,
        "subscription_until": paid_until.isoformat() if paid_until else None,
        "days_left": int(days_left),
        "auto_renew": bool(row["auto_renew"]) if paid_active else False,
        "stars": SUBSCRIPTION_STARS,
        "period_days": 30,
    }


async def subscription_has_access(user_id: int) -> bool:
    return bool((await subscription_info(user_id))["has_access"])


async def create_subscription_invoice_link(user_id: int) -> str:
    if not bot:
        raise RuntimeError("Telegram bot is not configured")
    payload = f"fitmy2-sub:{user_id}:{int(time.time())}"
    return await bot.create_invoice_link(
        title="Fitmy2.0 — подписка",
        description="Полный доступ к питанию, тренировкам, прогрессу и ИИ-агенту на 30 дней. Автопродление каждые 30 дней.",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Fitmy2.0 — 30 дней", amount=SUBSCRIPTION_STARS)],
        subscription_period=SUBSCRIPTION_PERIOD,
    )


def subscription_terms_text() -> str:
    return (
        f"Условия подписки Fitmy2.0\n\n"
        f"• Новому пользователю предоставляется {TRIAL_DAYS} дней бесплатного полного доступа.\n"
        f"• После пробного периода подписка стоит {SUBSCRIPTION_STARS} Telegram Stars за 30 дней.\n"
        "• После первой оплаты подписка автоматически продлевается каждые 30 дней, пока автопродление не отменено.\n"
        "• При отмене уже оплаченный доступ сохраняется до конца оплаченного периода.\n"
        "• Fitmy2.0 — информационный помощник по питанию и тренировкам и не заменяет медицинскую помощь.\n"
        "• По вопросам платежей используй /paysupport."
    )


async def get_profile(user_id: int):
    return await db_fetchrow("SELECT * FROM profiles WHERE telegram_id=$1", user_id)

def profile_to_text(p) -> str:
    if not p:
        return "Профиль ещё не заполнен."
    return f"""
Имя: {p['name']}
Возраст: {p['age']}
Пол: {p['sex']}
Рост: {p['height']}
Вес: {p['weight']}
Цель: {p['goal']}
Активность: {p['activity']}
Тренировок в неделю: {p['frequency']}
Где тренируется / оборудование: {p['equipment']}
Ограничения и травмы: {p['restrictions']}
Питание и предпочтения: {p['food']}
Сон: {p['sleep']}
""".strip()



async def user_local_date(user_id: int):
    settings = await ensure_notification_settings(user_id)
    tz_name = settings["timezone"] if settings else DEFAULT_TIMEZONE
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return now_utc().astimezone(tz).date()



def app_week_start(local_date):
    return local_date - timedelta(days=local_date.weekday())


def valid_app_week_plan(plan) -> bool:
    if not isinstance(plan, list) or len(plan) != 7:
        return False
    for day in plan:
        if not isinstance(day, list) or len(day) != 4:
            return False
        for idx, meal_id in enumerate(day):
            meal = APP_MEAL_CATALOG.get(str(meal_id))
            if not meal or meal["type"] != APP_MEAL_TYPE_ORDER[idx]:
                return False
    # Внутри одной недели каждый завтрак/обед/перекус/ужин уникален.
    for idx in range(4):
        ids = [str(day[idx]) for day in plan]
        if len(set(ids)) != 7:
            return False
    return True


def decode_app_plan(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return value


def app_goal_mode(profile) -> str:
    goal = str(profile["goal"] if profile else "").lower()
    if any(x in goal for x in ("набор", "мыш", "мас")):
        return "gain"
    if any(x in goal for x in ("сниж", "похуд", "сброс", "дефиц")):
        return "loss"
    return "maintain"


def fallback_app_week_plan(user_id: int, start_date, salt: str = "", goal_mode: str = "maintain") -> list[list[str]]:
    pools = {
        meal_type: [
            meal_id for meal_id, item in APP_MEAL_CATALOG.items()
            if item["type"] == meal_type and goal_mode in item.get("goals", ["loss","maintain","gain"])
        ]
        for meal_type in APP_MEAL_TYPE_ORDER
    }
    seed_text = f"{user_id}:{start_date.isoformat()}:{salt}"
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    ordered = {}
    for meal_type, choices in pools.items():
        choices = list(choices)
        rng.shuffle(choices)
        ordered[meal_type] = choices[:7]
    return [
        [ordered[meal_type][day_index] for meal_type in APP_MEAL_TYPE_ORDER]
        for day_index in range(7)
    ]


def parse_ai_app_plan(answer: str):
    if not answer:
        return None
    candidates = [answer.strip()]
    start = answer.find("{")
    end = answer.rfind("}")
    if start >= 0 and end > start:
        candidates.append(answer[start:end + 1])
    start = answer.find("[")
    end = answer.rfind("]")
    if start >= 0 and end > start:
        candidates.append(answer[start:end + 1])
    for raw in candidates:
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, dict):
            data = data.get("days") or data.get("plan")
        if valid_app_week_plan(data):
            return data
    return None


async def generate_ai_app_week_plan(user_id: int, start_date, previous_plan=None):
    if not client:
        return None
    profile = await get_profile(user_id)
    goal_mode = app_goal_mode(profile)
    choices = "\n".join(
        f"{meal_id} | {item['type']} | {item['name']} | {item['kcal']} ккал | Б {item['protein']} Ж {item['fat']} У {item['carbs']} | {item['cook']} мин | бюджетное"
        for meal_id, item in APP_MEAL_CATALOG.items()
        if goal_mode in item.get("goals", ["loss","maintain","gain"]) and item.get("budget", True)
    )
    previous = json.dumps(previous_plan, ensure_ascii=False) if previous_plan else "нет"
    answer = await ask_ai(
        user_id,
        f"Подбери рацион Fitmy2.0 на неделю с {start_date.strftime('%d.%m.%Y')}.",
        f"""
Выбери рацион на 7 дней ТОЛЬКО из библиотеки ниже.
Учитывай профиль пользователя, его цель, пищевые предпочтения и ограничения.
Целевой режим: {goal_mode}. Все блюда должны быть доступными и бюджетными: обычные крупы, яйца, творог, курица, индейка, печень, минтай/скумбрия, бобовые, сезонные овощи и фрукты. Не используй дорогие продукты вроде лосося, креветок, киноа, авокадо и чиа.
Для loss выбирай более лёгкие и сытные варианты; для gain — более калорийные варианты с достаточным белком и углеводами; для maintain — средний диапазон.
Если профиль явно исключает продукт, не выбирай блюдо с этим продуктом.
КРИТИЧНО: все 7 завтраков должны быть разными, все 7 обедов разными, все 7 перекусов разными и все 7 ужинов разными. Никаких повторов блюд внутри недели.
По возможности не копируй прошлую неделю целиком.

БИБЛИОТЕКА:
{choices}

ПРОШЛАЯ НЕДЕЛЯ:
{previous}

Ответь ТОЛЬКО валидным JSON без пояснений:
{{"days":[
["id_завтрака","id_обеда","id_перекуса","id_ужина"],
["...","...","...","..."],
["...","...","...","..."],
["...","...","...","..."],
["...","...","...","..."],
["...","...","...","..."],
["...","...","...","..."]
]}}

В каждом дне порядок строго: Завтрак, Обед, Перекус, Ужин.
Используй только ID из библиотеки.
""",
        save_history=False,
    )
    return parse_ai_app_plan(answer)


async def get_app_week_plan(user_id: int, local_date=None):
    local_date = local_date or await user_local_date(user_id)
    start_date = app_week_start(local_date)
    return await db_fetchrow(
        """
        SELECT * FROM app_week_plans
        WHERE telegram_id=$1 AND start_date=$2
        LIMIT 1
        """,
        user_id, start_date
    )


async def _upgrade_app_week_plan_with_ai(user_id: int, start_date, fallback_plan, previous_plan=None):
    try:
        ai_plan = await generate_ai_app_week_plan(user_id, start_date, previous_plan)
        final_plan = ai_plan if valid_app_week_plan(ai_plan) else fallback_plan
        source = "ai" if ai_plan else "fallback"
        await db_execute(
            """
            UPDATE app_week_plans
            SET plan_json=$3::jsonb, source=$4, updated_at=$5
            WHERE telegram_id=$1 AND start_date=$2
            """,
            user_id, start_date, json.dumps(final_plan), source, now_utc()
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Weekly app plan AI generation failed for %s", user_id)
        await db_execute(
            """
            UPDATE app_week_plans
            SET source='fallback', updated_at=$3
            WHERE telegram_id=$1 AND start_date=$2
            """,
            user_id, start_date, now_utc()
        )


async def ensure_app_week_plan(user_id: int, local_date=None, wait_for_ai: bool = False):
    local_date = local_date or await user_local_date(user_id)
    start_date = app_week_start(local_date)
    end_date = start_date + timedelta(days=6)

    existing = await db_fetchrow(
        "SELECT * FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
        user_id, start_date
    )
    if existing:
        existing_plan = decode_app_plan(existing["plan_json"])
        if valid_app_week_plan(existing_plan) and str(existing["source"] or "").startswith("v11-simple"):
            return existing
        if valid_app_week_plan(existing_plan):
            profile = await get_profile(user_id)
            fresh_plan = fallback_app_week_plan(user_id, start_date, salt="v11-simple", goal_mode=app_goal_mode(profile))
            await db_execute(
                """UPDATE app_week_plans SET plan_json=$3::jsonb, source='v11-simple', updated_at=$4
                   WHERE telegram_id=$1 AND start_date=$2""",
                user_id, start_date, json.dumps(fresh_plan), now_utc(),
            )
            return await db_fetchrow("SELECT * FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2", user_id, start_date)
        # Миграция старого плана v7: сразу заменяем его на новую библиотеку из 28 уникальных блюд.
        profile = await get_profile(user_id)
        fallback_plan = fallback_app_week_plan(user_id, start_date, salt="v11-simple", goal_mode=app_goal_mode(profile))
        await db_execute(
            """UPDATE app_week_plans
            SET plan_json=$3::jsonb, source='v11-simple', updated_at=$4
            WHERE telegram_id=$1 AND start_date=$2""",
            user_id, start_date, json.dumps(fallback_plan), now_utc(),
        )
        task = asyncio.create_task(_upgrade_app_week_plan_with_ai(user_id, start_date, fallback_plan, existing_plan))
        _update_tasks.add(task)
        task.add_done_callback(_update_tasks.discard)
        return await db_fetchrow(
            "SELECT * FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
            user_id, start_date
        )

    previous_row = await db_fetchrow(
        """
        SELECT plan_json FROM app_week_plans
        WHERE telegram_id=$1 AND start_date < $2
        ORDER BY start_date DESC
        LIMIT 1
        """,
        user_id, start_date
    )
    previous_plan = decode_app_plan(previous_row["plan_json"]) if previous_row else None
    profile = await get_profile(user_id)
    fallback_plan = fallback_app_week_plan(user_id, start_date, salt="v11-simple", goal_mode=app_goal_mode(profile))

    inserted = await db_fetchrow(
        """
        INSERT INTO app_week_plans
            (telegram_id, start_date, end_date, plan_json, source, created_at, updated_at)
        VALUES ($1,$2,$3,$4::jsonb,'pending',$5,$5)
        ON CONFLICT(telegram_id, start_date) DO NOTHING
        RETURNING *
        """,
        user_id, start_date, end_date, json.dumps(fallback_plan), now_utc()
    )
    if not inserted:
        return await db_fetchrow(
            "SELECT * FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
            user_id, start_date
        )

    if wait_for_ai:
        await _upgrade_app_week_plan_with_ai(user_id, start_date, fallback_plan, previous_plan)
        return await db_fetchrow(
            "SELECT * FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
            user_id, start_date
        )

    task = asyncio.create_task(
        _upgrade_app_week_plan_with_ai(user_id, start_date, fallback_plan, previous_plan)
    )
    _update_tasks.add(task)
    task.add_done_callback(_update_tasks.discard)
    return inserted


async def regenerate_app_week_plan(user_id: int, local_date=None):
    local_date = local_date or await user_local_date(user_id)
    start_date = app_week_start(local_date)
    end_date = start_date + timedelta(days=6)
    current = await db_fetchrow(
        "SELECT plan_json FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
        user_id, start_date
    )
    previous_plan = decode_app_plan(current["plan_json"]) if current else None
    ai_plan = await generate_ai_app_week_plan(user_id, start_date, previous_plan)
    plan = ai_plan if valid_app_week_plan(ai_plan) else fallback_app_week_plan(
        user_id, start_date, salt=str(time.time_ns())
    )
    source = "manual-ai" if ai_plan else "manual-fallback"
    await db_execute(
        """
        INSERT INTO app_week_plans
            (telegram_id, start_date, end_date, plan_json, source, created_at, updated_at)
        VALUES ($1,$2,$3,$4::jsonb,$5,$6,$6)
        ON CONFLICT(telegram_id, start_date) DO UPDATE SET
            end_date=EXCLUDED.end_date,
            plan_json=EXCLUDED.plan_json,
            source=EXCLUDED.source,
            updated_at=EXCLUDED.updated_at
        """,
        user_id, start_date, end_date, json.dumps(plan), source, now_utc()
    )
    return await get_app_week_plan(user_id, local_date)



async def choose_ai_replacement(user_id: int, old_id: str, candidate_ids: list[str], reason: str):
    if not client or not candidate_ids:
        return None
    old = APP_MEAL_CATALOG[old_id]
    choices = "\n".join(
        f"{mid} | {APP_MEAL_CATALOG[mid]['name']} | {APP_MEAL_CATALOG[mid]['kcal']} ккал | {APP_MEAL_CATALOG[mid]['cook']} мин"
        for mid in candidate_ids
    )
    answer = await ask_ai(
        user_id,
        f"Замени блюдо {old['name']}. Причина: {reason}.",
        f"""
Выбери ОДНО подходящее блюдо на замену из списка ниже.
Учитывай профиль пользователя, цель, пищевые предпочтения и ограничения.
Причина замены: {reason}
Текущее блюдо: {old['name']}.

Варианты:
{choices}

Старайся сохранить близкую калорийность и тип приёма пищи.
Выбирай только обычные повседневные продукты из супермаркета. Не предлагай лосось, форель, креветки, морепродукты, киноа, авокадо, чиа и другие дорогие или экзотические продукты.
Ответь только одним ID из списка, без пояснений.
""",
        save_history=False,
    )
    candidate = answer.strip().split()[0].strip("`'\".,;:")
    return candidate if candidate in candidate_ids else None


async def replace_app_meal(user_id: int, day_index: int, meal_index: int, reason: str, local_date=None):
    row = await ensure_app_week_plan(user_id, local_date)
    plan = decode_app_plan(row["plan_json"])
    if not valid_app_week_plan(plan):
        profile = await get_profile(user_id)
        plan = fallback_app_week_plan(user_id, row["start_date"], salt="v11-simple", goal_mode=app_goal_mode(profile))

    old_id = plan[day_index][meal_index]
    old = APP_MEAL_CATALOG[old_id]
    used_same_type = {str(day[meal_index]) for day in plan if isinstance(day, list) and len(day) > meal_index}
    candidates = [
        meal_id for meal_id, item in APP_MEAL_CATALOG.items()
        if item["type"] == old["type"] and item.get("budget", True) and meal_id != old_id and meal_id not in used_same_type
    ]
    if not candidates:
        candidates = [
            meal_id for meal_id, item in APP_MEAL_CATALOG.items()
            if item["type"] == old["type"] and item.get("budget", True) and meal_id != old_id
        ]
    if not candidates:
        return row

    if reason == "fast":
        new_id = min(candidates, key=lambda mid: APP_MEAL_CATALOG[mid]["cook"])
    else:
        new_id = await choose_ai_replacement(user_id, old_id, candidates, reason)
        if not new_id:
            seed_text = f"{user_id}:{row['start_date']}:{day_index}:{meal_index}:{reason}:{old_id}"
            idx = int(hashlib.sha256(seed_text.encode()).hexdigest()[:12], 16) % len(candidates)
            new_id = candidates[idx]

    plan[day_index][meal_index] = new_id
    await db_execute(
        """
        UPDATE app_week_plans
        SET plan_json=$3::jsonb, source='edited', updated_at=$4
        WHERE telegram_id=$1 AND start_date=$2
        """,
        user_id, row["start_date"], json.dumps(plan), now_utc()
    )
    return await db_fetchrow(
        "SELECT * FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
        user_id, row["start_date"]
    )


def app_plan_day_text(row, local_date) -> str | None:
    if not row:
        return None
    plan = decode_app_plan(row["plan_json"])
    if not valid_app_week_plan(plan):
        return None
    day_index = (local_date - row["start_date"]).days
    if day_index < 0 or day_index > 6:
        return None
    lines = []
    for meal_id in plan[day_index]:
        item = APP_MEAL_CATALOG[meal_id]
        lines.append(f"{item['type']}: {item['name']} — около {item['kcal']} ккал")
    return "\n".join(lines)

async def save_weekly_meal_plan(user_id: int, start_date, meal_plan: str, shopping_list: str):
    end_date = start_date + timedelta(days=6)
    await db_execute(
        """
        INSERT INTO weekly_meal_plans(telegram_id, start_date, end_date, meal_plan, shopping_list, created_at)
        VALUES ($1,$2,$3,$4,$5,$6)
        ON CONFLICT(telegram_id, start_date) DO UPDATE SET
            end_date=EXCLUDED.end_date,
            meal_plan=EXCLUDED.meal_plan,
            shopping_list=EXCLUDED.shopping_list,
            created_at=EXCLUDED.created_at
        """,
        user_id, start_date, end_date, meal_plan, shopping_list, now_utc()
    )


async def get_active_weekly_meal_plan(user_id: int, local_date=None):
    local_date = local_date or await user_local_date(user_id)
    return await db_fetchrow(
        """
        SELECT * FROM weekly_meal_plans
        WHERE telegram_id=$1 AND start_date <= $2 AND end_date >= $2
        ORDER BY start_date DESC
        LIMIT 1
        """,
        user_id, local_date
    )


def extract_day_from_weekly_plan(meal_plan: str, day_number: int) -> str | None:
    if not meal_plan or not (1 <= day_number <= 7):
        return None
    start_marker = f"===DAY_{day_number}==="
    next_marker = f"===DAY_{day_number + 1}===" if day_number < 7 else None
    if start_marker in meal_plan:
        chunk = meal_plan.split(start_marker, 1)[1]
        if next_marker and next_marker in chunk:
            chunk = chunk.split(next_marker, 1)[0]
        return clean_telegram_text(chunk.strip())
    # запасной вариант, если модель не соблюла служебные маркеры
    pattern = rf"(?is)(День\s*{day_number}\b.*?)(?=\n\s*День\s*{day_number + 1}\b|$)" if day_number < 7 else rf"(?is)(День\s*{day_number}\b.*)$"
    m = re.search(pattern, meal_plan)
    return clean_telegram_text(m.group(1).strip()) if m else None


def split_telegram_chunks(text: str, limit: int = 3600) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]
    chunks = []
    current = ""
    for block in text.split("\n\n"):
        candidate = block if not current else current + "\n\n" + block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        while len(block) > limit:
            cut = block.rfind("\n", 0, limit)
            if cut < limit // 2:
                cut = limit
            chunks.append(block[:cut].strip())
            block = block[cut:].strip()
        current = block
    if current:
        chunks.append(current)
    return [c for c in chunks if c]


async def send_long_message(message: Message, text: str):
    for chunk in split_telegram_chunks(text):
        await message.answer(chunk)
        await asyncio.sleep(0.15)


def parse_weekly_bundle(answer: str) -> tuple[str, str]:
    marker = "===FITMYN_SHOPPING==="
    if marker in answer:
        meal_plan, shopping = answer.split(marker, 1)
        return meal_plan.strip(), shopping.strip()
    # запасной поиск по заголовку списка покупок
    m = re.search(r"(?im)^🛒\s*Список покупок.*$", answer)
    if m:
        return answer[:m.start()].strip(), answer[m.start():].strip()
    return answer.strip(), "🛒 Список покупок\n\nНе удалось отделить список покупок. Нажми «🗓 Рацион на неделю» ещё раз."


async def generate_weekly_meal_bundle(user_id: int, start_date) -> tuple[str, str]:
    end_date = start_date + timedelta(days=6)
    answer = await ask_ai(
        user_id,
        f"Составь мой рацион на 7 дней с {start_date.strftime('%d.%m')} по {end_date.strftime('%d.%m')} и список покупок к нему.",
        f"""
Составь персональный рацион на 7 дней с учетом профиля, цели, предпочтений и ограничений пользователя.
Период: {start_date.strftime('%d.%m.%Y')}–{end_date.strftime('%d.%m.%Y')}.

Важно:
• План должен быть реалистичным для обычной жизни и не требовать готовить 4 разных сложных блюда каждый день.
• Повторно используй часть продуктов и заготовок, чтобы уменьшить расходы и отходы.
• На каждый день: завтрак, обед, ужин, 1 перекус.
• Для каждого приема пищи укажи конкретное блюдо и ориентир порции обычными мерами или примерным весом, без ложной точности.
• Если продукт не подходит по анкете, не используй его.
• Не добавляй сладости и мучное, если пользователь указал, что их исключает.
• Для сложного блюда дай очень короткое пояснение состава, но не полноценный рецепт.
• Сохраняй разнообразие, но используй разумное число ингредиентов.

Строго используй служебные маркеры — каждый на отдельной строке:
===DAY_1===
📅 День 1 — {start_date.strftime('%d.%m')}
Завтрак
• ...
Обед
• ...
Ужин
• ...
Перекус
• ...

===DAY_2===
...
И так до ===DAY_7===.

После 7-го дня поставь отдельной строкой:
===FITMYN_SHOPPING===

Затем:
🛒 Список покупок на 7 дней

🥩 Белок
• продукт — примерное количество

🥚 Яйца и молочные продукты
• ...

🌾 Крупы и гарниры
• ...

🥦 Овощи и зелень
• ...

🍎 Фрукты и ягоды
• ...

🥜 Орехи, масла и прочее
• ...

Проверь перед ответом:
1. Каждый продукт из списка покупок реально используется в рационе.
2. В списке есть примерное суммарное количество на 1 человека на 7 дней.
3. Нет таблиц, Markdown, HTML и <br>.
4. Не добавляй вступление и заключение.
""",
        save_history=False,
    )
    return parse_weekly_bundle(answer)


def workout_days_from_frequency(value: str | None) -> str:
    """Подбирает равномерные тренировочные дни из ответа анкеты."""
    match = re.search(r"\d+", value or "")
    n = int(match.group()) if match else 3
    if n <= 1:
        days = [2]  # Ср
    elif n == 2:
        days = [1, 4]  # Вт, Пт
    elif n == 3:
        days = [0, 2, 4]  # Пн, Ср, Пт
    elif n == 4:
        days = [0, 1, 3, 5]  # Пн, Вт, Чт, Сб
    elif n == 5:
        days = [0, 1, 2, 4, 5]  # Пн, Вт, Ср, Пт, Сб
    elif n == 6:
        days = [0, 1, 2, 3, 4, 5]
    else:
        days = [0, 1, 2, 3, 4, 5, 6]
    return ",".join(str(x) for x in days)


def workout_days_label(value: str) -> str:
    labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    result = []
    for item in (value or "").split(","):
        item = item.strip()
        if item.isdigit() and 0 <= int(item) <= 6:
            result.append(labels[int(item)])
    return ", ".join(result) or "не выбраны"


def timezone_label(value: str) -> str:
    names = {
        "Europe/Moscow": "Москва",
        "Europe/London": "Лондон",
        "Asia/Dubai": "Дубай",
        "Asia/Novosibirsk": "Новосибирск",
        "Asia/Almaty": "Алматы",
        "Asia/Tbilisi": "Тбилиси",
    }
    return names.get(value, value)


async def ensure_notification_settings(user_id: int):
    row = await db_fetchrow(
        "SELECT * FROM notification_settings WHERE telegram_id=$1", user_id
    )
    if row:
        return row
    profile = await get_profile(user_id)
    days = workout_days_from_frequency(profile["frequency"] if profile else None)
    await db_execute(
        """
        INSERT INTO notification_settings(
            telegram_id, enabled, timezone, morning_time, evening_time,
            workout_days, updated_at
        ) VALUES ($1, TRUE, $2, $3, $4, $5, $6)
        ON CONFLICT(telegram_id) DO NOTHING
        """,
        user_id, DEFAULT_TIMEZONE, DEFAULT_MORNING_TIME, DEFAULT_EVENING_TIME,
        days, now_utc()
    )
    return await db_fetchrow(
        "SELECT * FROM notification_settings WHERE telegram_id=$1", user_id
    )


def schedule_keyboard(settings) -> InlineKeyboardMarkup:
    toggle_text = "🔕 Выключить авто" if settings["enabled"] else "🔔 Включить авто"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data="notify_toggle")],
        [
            InlineKeyboardButton(text="Утро 07:00", callback_data="notify_m_0700"),
            InlineKeyboardButton(text="08:00", callback_data="notify_m_0800"),
            InlineKeyboardButton(text="09:00", callback_data="notify_m_0900"),
            InlineKeyboardButton(text="10:00", callback_data="notify_m_1000"),
        ],
        [
            InlineKeyboardButton(text="Вечер 19:00", callback_data="notify_e_1900"),
            InlineKeyboardButton(text="20:00", callback_data="notify_e_2000"),
            InlineKeyboardButton(text="21:00", callback_data="notify_e_2100"),
            InlineKeyboardButton(text="22:00", callback_data="notify_e_2200"),
        ],
        [
            InlineKeyboardButton(text="Москва", callback_data="notify_tz_moscow"),
            InlineKeyboardButton(text="Лондон", callback_data="notify_tz_london"),
        ],
        [
            InlineKeyboardButton(text="Дубай", callback_data="notify_tz_dubai"),
            InlineKeyboardButton(text="Новосибирск", callback_data="notify_tz_nsk"),
        ],
        [InlineKeyboardButton(text="♻️ Дни тренировок по анкете", callback_data="notify_days_auto")],
    ])


def schedule_text(settings) -> str:
    status = "включены" if settings["enabled"] else "выключены"
    return (
        "⏰ Автоматическое сопровождение\n\n"
        f"Статус: {status}\n"
        f"Часовой пояс: {timezone_label(settings['timezone'])}\n"
        f"Утренний план: {settings['morning_time']}\n"
        f"Вечерний отчёт: {settings['evening_time']}\n"
        f"Тренировочные дни: {workout_days_label(settings['workout_days'])}\n\n"
        "Утром я сам пришлю питание и тренировку или восстановление. "
        "Вечером напомню про короткий отчёт."
    )


def parse_hhmm(value: str) -> tuple[int, int]:
    try:
        h, m = value.split(":", 1)
        return int(h), int(m)
    except Exception:
        return 8, 0


def is_due(local_now: datetime, hhmm: str, window_minutes: int = 90) -> bool:
    hour, minute = parse_hhmm(hhmm)
    scheduled = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return scheduled <= local_now < scheduled + timedelta(minutes=window_minutes)


async def claim_notification(user_id: int, kind: str, local_date):
    return await db_fetchrow(
        """
        INSERT INTO notification_log(telegram_id, kind, local_date, created_at)
        VALUES ($1,$2,$3,$4)
        ON CONFLICT(telegram_id, kind, local_date) DO NOTHING
        RETURNING id
        """,
        user_id, kind, local_date, now_utc()
    )


async def release_notification(log_id: int):
    await db_execute("DELETE FROM notification_log WHERE id=$1", log_id)


async def build_daily_auto_plan(user_id: int, local_date, workout_day: bool) -> tuple[str, str]:
    task = "Сегодня тренировочный день." if workout_day else "Сегодня день восстановления без силовой тренировки."

    # Текущий недельный рацион Mini App создаётся автоматически раз в неделю.
    # В понедельник (или при первом открытии приложения) формируется новый план,
    # сохраняется в БД и затем используется без повторных AI-запросов.
    app_plan = await ensure_app_week_plan(user_id, local_date, wait_for_ai=True)
    planned_food = app_plan_day_text(app_plan, local_date)

    # Совместимость со старым текстовым недельным рационом.
    if not planned_food:
        active_plan = await get_active_weekly_meal_plan(user_id, local_date)
        if active_plan:
            day_number = (local_date - active_plan["start_date"]).days + 1
            planned_food = extract_day_from_weekly_plan(active_plan["meal_plan"], day_number)

    if planned_food:
        activity = await ask_ai(
            user_id,
            f"Составь активность на сегодня. {task}",
            f"""
{task}
Сформируй только второе сообщение:
{'🏋️ Тренировка на сегодня: Цель, Разминка, Основная часть, Отдых, Заминка, Совет.' if workout_day else '🌿 Восстановление сегодня: активность, мобильность, шаги, сон и один совет.'}
Без Markdown, HTML, таблиц и <br>. Компактно.
""",
            save_history=False,
        )
        food = "🥗 Питание на сегодня\n\n" + planned_food
        return food, activity

    answer = await ask_ai(
        user_id,
        f"Составь автоматический план на сегодня. {task}",
        f"""
Сформируй два коротких сообщения для Telegram на сегодня с учетом профиля пользователя.
{task}

Сначала питание, потом тренировку или восстановление.
Между сообщениями поставь отдельной строкой ТОЧНО такой маркер:
===FITMYN_SPLIT===

Первая часть:
🥗 Питание на сегодня
Главная задача
Завтрак
Обед
Ужин
Перекус
Фокус дня

Вторая часть:
{'🏋️ Тренировка на сегодня: Цель, Разминка, Основная часть, Отдых, Заминка, Совет.' if workout_day else '🌿 Восстановление сегодня: активность, мобильность, шаги, сон и один совет.'}

Каждая часть должна быть компактной. Без Markdown, HTML, таблиц и <br>.
""",
        save_history=False,
    )
    parts = [p.strip() for p in answer.split("===FITMYN_SPLIT===", 1)]
    if len(parts) == 2:
        return parts[0], parts[1]
    return answer, (
        "🏋️ Тренировка сегодня\n\nОткрой кнопку «🏋️ Тренировка», и я соберу план под тебя."
        if workout_day else
        "🌿 Сегодня восстановление\n\nЛёгкая активность, прогулка и качественный сон — достаточно."
    )


async def send_morning_plan(user_id: int, local_date, workout_day: bool):
    if not bot:
        return False
    claim = await claim_notification(user_id, "morning", local_date)
    if not claim:
        return False
    log_id = claim["id"]
    try:
        food, activity = await build_daily_auto_plan(user_id, local_date, workout_day)
        await bot.send_message(user_id, food, reply_markup=MAIN_KB)
        await asyncio.sleep(0.3)
        await bot.send_message(user_id, activity, reply_markup=MAIN_KB)
        return True
    except Exception:
        logger.exception("Failed to send morning plan to %s", user_id)
        await release_notification(log_id)
        return False


async def send_evening_checkin(user_id: int, local_date):
    if not bot:
        return False
    claim = await claim_notification(user_id, "evening", local_date)
    if not claim:
        return False
    log_id = claim["id"]
    try:
        await bot.send_message(
            user_id,
            "📊 Как прошёл день?\n\n"
            "Нажми «📊 Отчёт» и коротко отметь питание, тренировку или активность, сон, энергию и самочувствие.",
            reply_markup=MAIN_KB,
        )
        return True
    except Exception:
        logger.exception("Failed to send evening checkin to %s", user_id)
        await release_notification(log_id)
        return False


async def run_due_notifications() -> dict:
    if not pool or not bot:
        return {"checked": 0, "morning_sent": 0, "evening_sent": 0}

    users = await db_fetch(
        """
        SELECT u.telegram_id
        FROM users u
        JOIN profiles p ON p.telegram_id=u.telegram_id
        WHERE u.consent=TRUE
        ORDER BY u.telegram_id
        """
    )
    stats = {"checked": len(users), "morning_sent": 0, "evening_sent": 0}
    utc_now = now_utc()

    for row in users:
        uid = row["telegram_id"]
        settings = await ensure_notification_settings(uid)
        if not settings:
            continue
        try:
            tz = ZoneInfo(settings["timezone"])
        except ZoneInfoNotFoundError:
            tz = ZoneInfo(DEFAULT_TIMEZONE)
        local_now = utc_now.astimezone(tz)
        local_date = local_now.date()
        sub = await subscription_info(uid)

        if sub["status"] == "trial" and sub["days_left"] in (3, 1) and local_now.hour == 10:
            log_id = await reserve_notification(uid, f"trial_{sub['days_left']}", local_date)
            if log_id:
                try:
                    await bot.send_message(uid, f"До конца бесплатного периода Fitmy2.0 осталось {sub['days_left']} дн. После этого подписка — {SUBSCRIPTION_STARS} ⭐ на 30 дней. Оформить: /subscribe")
                except Exception:
                    await release_notification(log_id)
        if not sub["has_access"]:
            if local_now.hour == 10:
                log_id = await reserve_notification(uid, "trial_expired", local_date)
                if log_id:
                    try:
                        await bot.send_message(uid, f"Бесплатный период Fitmy2.0 закончился. Полный доступ — {SUBSCRIPTION_STARS} ⭐ на 30 дней. Оформить: /subscribe")
                    except Exception:
                        await release_notification(log_id)
            continue

        # Каждую неделю новый рацион создаётся автоматически.
        # Cron будит сервис каждые 15 минут; в понедельник после 05:00
        # план создаётся один раз и сохраняется в БД, даже если пользователь
        # ещё не открывал Mini App.
        if local_now.weekday() == 0 and local_now.hour >= 5:
            await ensure_app_week_plan(uid, local_date, wait_for_ai=False)

        if not settings["enabled"]:
            continue

        if is_due(local_now, settings["morning_time"]):
            workout_days = {
                int(x) for x in settings["workout_days"].split(",")
                if x.strip().isdigit()
            }
            if await send_morning_plan(uid, local_date, local_now.weekday() in workout_days):
                stats["morning_sent"] += 1

        if is_due(local_now, settings["evening_time"]):
            if await send_evening_checkin(uid, local_date):
                stats["evening_sent"] += 1

    return stats


async def notification_loop():
    """Фоновая подстраховка, пока Render-сервис не спит."""
    while True:
        try:
            await run_due_notifications()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notification loop error")
        await asyncio.sleep(60)

async def recent_history(user_id: int, limit: int = 12):
    rows = await db_fetch(
        """
        SELECT role, content
        FROM messages
        WHERE telegram_id=$1
        ORDER BY id DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )
    return list(reversed(rows))

async def save_message(user_id: int, role: str, content: str):
    await db_execute(
        "INSERT INTO messages(telegram_id, role, content, created_at) VALUES ($1,$2,$3,$4)",
        user_id, role, content, now_utc()
    )

def clean_telegram_text(text: str) -> str:
    """Убирает типичные артефакты Markdown/HTML из ответов моделей."""
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("**", "").replace("__", "").replace("```", "")
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*\|[ \t]*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]*\|[ \t]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]*\|[ \t]*", " • ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

async def ask_ai(user_id: int, user_text: str, extra_instruction: str = "", save_history: bool = True) -> str:
    if not client:
        return "ИИ пока не подключён. Администратору нужно добавить OPENAI_API_KEY."

    profile = await get_profile(user_id)
    history = await recent_history(user_id)

    history_text = "\n".join(
        f"{row['role'].upper()}: {row['content']}" for row in history
    )

    instructions = SYSTEM_PROMPT
    if extra_instruction:
        instructions += "\n\nТекущая задача:\n" + extra_instruction

    prompt = f"""
ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
{profile_to_text(profile)}

ПОСЛЕДНИЙ КОНТЕКСТ:
{history_text or "Нет истории."}

НОВОЕ СООБЩЕНИЕ:
{user_text}
""".strip()

    response = await client.responses.create(
        model=OPENAI_MODEL,
        instructions=instructions,
        input=prompt,
    )
    answer = clean_telegram_text((response.output_text or "").strip()) or "Не получилось сформировать ответ."
    if save_history:
        await save_message(user_id, "user", user_text)
        await save_message(user_id, "assistant", answer)
    return answer

async def ensure_ready(message: Message) -> bool:
    if not pool:
        await message.answer("База данных пока не подключена. Администратор завершает настройку.")
        return False
    await touch_user(message)
    if not await has_consent(message.from_user.id):
        await message.answer("Сначала нужно согласиться с правилами через /start.")
        return False
    if not await get_profile(message.from_user.id):
        await message.answer("Сначала заполним короткую анкету. Напиши /start.")
        return False
    sub = await subscription_info(message.from_user.id)
    if not sub["has_access"]:
        await message.answer(
            f"Пробный период закончился. Полный доступ к Fitmy2.0 — {SUBSCRIPTION_STARS} ⭐ на 30 дней.\n\n"
            "Для оформления подписки отправь /subscribe."
        )
        return False
    return True

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if not pool:
        await message.answer("FitMyN почти готов. Администратор завершает подключение базы.")
        return

    await touch_user(message)
    await state.clear()

    if await has_consent(message.from_user.id) and await get_profile(message.from_user.id):
        await message.answer(
            "Я FitMyN — твой ИИ-помощник по питанию, тренировкам и привычкам. Что делаем?",
            reply_markup=MAIN_KB,
        )
        return

    await message.answer(
        "Привет! Я FitMyN — ИИ-помощник по питанию, тренировкам и привычкам.\n\n"
        "Я не заменяю врача и не ставлю диагнозы. Для персонализации я сохраняю только данные, "
        "которые ты сам сообщишь: цель, питание, активность, тренировки и ограничения.\n\n"
        "Продолжить?",
        reply_markup=CONSENT_KB,
    )

@router.callback_query(F.data == "consent_no")
async def consent_no(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Без согласия персональный профиль сохраняться не будет. Если передумаешь — /start."
    )

@router.callback_query(F.data == "consent_yes")
async def consent_yes(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await db_execute("UPDATE users SET consent=TRUE WHERE telegram_id=$1", call.from_user.id)
    await state.set_state(Onboarding.name)
    await call.message.answer("Как тебя зовут?")

@router.message(Onboarding.name)
async def ob_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Onboarding.age)
    await message.answer("Сколько тебе лет?")

@router.message(Onboarding.age)
async def ob_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text.strip())
    await state.set_state(Onboarding.sex)
    await message.answer("Пол? Можно написать: женский / мужской / не хочу указывать.")

@router.message(Onboarding.sex)
async def ob_sex(message: Message, state: FSMContext):
    await state.update_data(sex=message.text.strip())
    await state.set_state(Onboarding.height)
    await message.answer("Рост в сантиметрах? Можно написать «пропустить».")

@router.message(Onboarding.height)
async def ob_height(message: Message, state: FSMContext):
    await state.update_data(height=message.text.strip())
    await state.set_state(Onboarding.weight)
    await message.answer("Текущий вес? Если не хочешь указывать — «пропустить».")

@router.message(Onboarding.weight)
async def ob_weight(message: Message, state: FSMContext):
    await state.update_data(weight=message.text.strip())
    await state.set_state(Onboarding.goal)
    await message.answer(
        "Какая главная цель? Например: снизить вес, набрать мышцы, стать сильнее, "
        "улучшить форму или повысить уровень энергии."
    )

@router.message(Onboarding.goal)
async def ob_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text.strip())
    await state.set_state(Onboarding.activity)
    await message.answer(
        "Опиши обычную активность: сидячая работа, сколько примерно шагов, есть ли спорт сейчас."
    )

@router.message(Onboarding.activity)
async def ob_activity(message: Message, state: FSMContext):
    await state.update_data(activity=message.text.strip())
    await state.set_state(Onboarding.frequency)
    await message.answer("Сколько тренировок в неделю реально готов(а) делать?")

@router.message(Onboarding.frequency)
async def ob_frequency(message: Message, state: FSMContext):
    await state.update_data(frequency=message.text.strip())
    await state.set_state(Onboarding.equipment)
    await message.answer("Где будешь тренироваться и какое оборудование доступно?")

@router.message(Onboarding.equipment)
async def ob_equipment(message: Message, state: FSMContext):
    await state.update_data(equipment=message.text.strip())
    await state.set_state(Onboarding.restrictions)
    await message.answer(
        "Есть ли травмы, боли, ограничения, заболевания или другие особенности, "
        "которые важно учитывать? Если нет — напиши «нет»."
    )

@router.message(Onboarding.restrictions)
async def ob_restrictions(message: Message, state: FSMContext):
    await state.update_data(restrictions=message.text.strip())
    await state.set_state(Onboarding.food)
    await message.answer(
        "Расскажи про питание: что любишь/не ешь, аллергии, готовишь ли дома, "
        "хочешь ли считать калории."
    )

@router.message(Onboarding.food)
async def ob_food(message: Message, state: FSMContext):
    await state.update_data(food=message.text.strip())
    await state.set_state(Onboarding.sleep)
    await message.answer("Сколько обычно спишь и как оцениваешь качество сна?")

@router.message(Onboarding.sleep)
async def ob_sleep(message: Message, state: FSMContext):
    await state.update_data(sleep=message.text.strip())
    data = await state.get_data()
    uid = message.from_user.id

    await db_execute(
        """
        INSERT INTO profiles(
            telegram_id, name, age, sex, height, weight, goal, activity,
            frequency, equipment, restrictions, food, sleep, updated_at
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
        ON CONFLICT(telegram_id) DO UPDATE SET
            name=EXCLUDED.name,
            age=EXCLUDED.age,
            sex=EXCLUDED.sex,
            height=EXCLUDED.height,
            weight=EXCLUDED.weight,
            goal=EXCLUDED.goal,
            activity=EXCLUDED.activity,
            frequency=EXCLUDED.frequency,
            equipment=EXCLUDED.equipment,
            restrictions=EXCLUDED.restrictions,
            food=EXCLUDED.food,
            sleep=EXCLUDED.sleep,
            updated_at=EXCLUDED.updated_at
        """,
        uid, data["name"], data["age"], data["sex"], data["height"], data["weight"],
        data["goal"], data["activity"], data["frequency"], data["equipment"],
        data["restrictions"], data["food"], data["sleep"], now_utc()
    )
    await ensure_subscription(uid)
    local_date = await user_local_date(uid)
    await db_execute(
        "DELETE FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
        uid, app_week_start(local_date)
    )
    await state.clear()

    await message.answer("Профиль готов. Собираю стартовый план…", reply_markup=MAIN_KB)
    answer = await ask_ai(
        uid,
        "Составь мой стартовый план.",
        """
Сделай стартовый план на 7 дней.
Оформи короткими блоками с эмодзи и маркированными списками.
Без таблиц, Markdown, HTML и <br>.

Нужные блоки:
🎯 Цель недели
🥗 Питание — 4–6 простых правил
🍽 Пример одного дня
🏋️ Тренировки на неделю
⚡ Минимум на занятый день
📊 Что отслеживать ежедневно

Не давай медицинских обещаний.
""",
    )
    await message.answer(answer)

@router.message(F.text == "🥗 Питание")
async def food_menu(message: Message):
    if not await ensure_ready(message):
        return
    answer = await ask_ai(
        message.from_user.id,
        "Составь мне план питания на сегодня.",
        """
Составь практичный план питания на сегодня с учётом профиля пользователя.

Формат:
🥗 Питание на сегодня

Главная задача
1–2 коротких предложения.

Завтрак
• вариант блюда
• при необходимости замена

Обед
• вариант блюда
• при необходимости замена

Ужин
• вариант блюда

Перекус
• 1–2 варианта

Фокус дня
Одна простая задача.

Без таблиц, Markdown, HTML и <br>. Пиши компактно.
"""
    )
    await message.answer(answer)

@router.message(F.text == "🏋️ Тренировка")
async def workout_menu(message: Message):
    if not await ensure_ready(message):
        return
    answer = await ask_ai(
        message.from_user.id,
        "Какую тренировку мне сделать сегодня?",
        """
Подбери тренировку под профиль пользователя и доступное оборудование.

Формат:
🏋️ Тренировка на сегодня

Цель
Одна короткая строка.

Разминка
• 2–4 пункта

Основная часть
1. Упражнение — подходы × повторения
2. Упражнение — подходы × повторения
3. И так далее, без лишнего текста

Отдых
• сколько между подходами

Заминка
• 2–3 коротких пункта

Совет
Одна рекомендация по технике или нагрузке.

Без таблиц, Markdown, HTML, <br> и вертикальных черт.
Если есть боль или выраженное недомогание, не предлагай нагрузку через боль.
"""
    )
    await message.answer(answer)

@router.message(Command("mealplan"))
@router.message(F.text == "🗓 Рацион на неделю")
async def weekly_meal_plan(message: Message):
    if not await ensure_ready(message):
        return
    await message.answer("🗓 Собираю рацион на 7 дней и список покупок. Обычно это занимает несколько секунд…")
    try:
        start_date = await user_local_date(message.from_user.id)
        meal_plan, shopping = await generate_weekly_meal_bundle(message.from_user.id, start_date)
        await save_weekly_meal_plan(message.from_user.id, start_date, meal_plan, shopping)

        # Служебные маркеры нужны для связи с ежедневным планом, пользователю их не показываем.
        visible_plan = re.sub(r"(?m)^===DAY_[1-7]===\s*$", "", meal_plan).strip()
        visible_shopping = shopping.replace("===FITMYN_SHOPPING===", "").strip()

        await send_long_message(message, visible_plan)
        await message.answer("🛒 К этому рациону готов список покупок:")
        await send_long_message(message, visible_shopping)
        await message.answer(
            "Готово. До конца этих 7 дней утреннее питание будет опираться на этот рацион, чтобы меню и покупки не расходились.",
            reply_markup=MAIN_KB,
        )
    except Exception:
        logger.exception("Weekly meal plan error")
        await message.answer("Не получилось собрать рацион. Попробуй ещё раз через минуту.", reply_markup=MAIN_KB)


@router.message(Command("shopping"))
@router.message(F.text == "🛒 Список покупок")
async def shopping_list(message: Message):
    if not await ensure_ready(message):
        return
    plan = await get_active_weekly_meal_plan(message.from_user.id)
    if not plan:
        await message.answer(
            "Сначала нажми «🗓 Рацион на неделю». Я составлю меню на 7 дней и сохраню список покупок именно к нему.",
            reply_markup=MAIN_KB,
        )
        return
    await send_long_message(message, plan["shopping_list"])


@router.message(F.text == "📊 Отчёт")
async def report_start(message: Message, state: FSMContext):
    if not await ensure_ready(message): return
    await state.set_state(Checkin.waiting_report)
    await message.answer(
        "Пришли одним сообщением:\n\n"
        "Питание: …\nТренировка: …\nШаги/активность: …\nСон: … часов\n"
        "Энергия: …/10\nГолод: …/10\nСамочувствие: …\nЧто было сложным: …"
    )

@router.message(Checkin.waiting_report)
async def report_finish(message: Message, state: FSMContext):
    report = message.text.strip()
    await db_execute(
        "INSERT INTO checkins(telegram_id, report, created_at) VALUES ($1,$2,$3)",
        message.from_user.id, report, now_utc()
    )
    await state.clear()
    answer = await ask_ai(
        message.from_user.id,
        report,
        """
Это ежедневный отчёт. Ответь:
Итог дня
Что получилось
Что скорректировать — максимум 2 пункта
Одна задача на завтра
Будь кратким.
"""
    )
    await message.answer(answer, reply_markup=MAIN_KB)

@router.message(F.text == "📅 Неделя")
async def week_summary(message: Message):
    if not await ensure_ready(message): return
    since = now_utc() - timedelta(days=7)
    rows = await db_fetch(
        """
        SELECT report, created_at
        FROM checkins
        WHERE telegram_id=$1 AND created_at >= $2
        ORDER BY created_at ASC
        """,
        message.from_user.id, since
    )
    if not rows:
        await message.answer("За последние 7 дней пока нет отчётов. Начни с «📊 Отчёт».")
        return

    reports = "\n\n".join(
        f"{r['created_at'].date()}:\n{r['report']}" for r in rows
    )
    answer = await ask_ai(
        message.from_user.id,
        f"Мои отчёты за неделю:\n\n{reports}",
        """
Сделай недельный разбор:
1. Что получилось.
2. Какие тенденции видны.
3. Что мешает.
4. Что изменить на следующей неделе.
5. План тренировок.
6. Фокус питания.
7. Одна главная задача недели.
Не делай выводов по одному измерению веса.
"""
    )
    await message.answer(answer)

@router.message(F.text == "👤 Мой профиль")
async def my_profile(message: Message):
    if not await ensure_ready(message): return
    await message.answer(profile_to_text(await get_profile(message.from_user.id)))

@router.message(F.text == "💬 Спросить агента")
async def ask_prompt(message: Message):
    if not await ensure_ready(message): return
    await message.answer("Напиши вопрос обычным сообщением. Я учту профиль и последние диалоги.")


@router.message(Command("schedule"))
@router.message(F.text == "⏰ Расписание")
async def notification_schedule(message: Message):
    if not await ensure_ready(message):
        return
    settings = await ensure_notification_settings(message.from_user.id)
    await message.answer(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data == "notify_toggle")
async def notify_toggle(call: CallbackQuery):
    await call.answer()
    settings = await ensure_notification_settings(call.from_user.id)
    await db_execute(
        "UPDATE notification_settings SET enabled=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, not settings["enabled"], now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data.startswith("notify_m_"))
async def notify_morning_time(call: CallbackQuery):
    await call.answer("Время сохранено")
    raw = call.data.rsplit("_", 1)[-1]
    value = f"{raw[:2]}:{raw[2:]}"
    await db_execute(
        "UPDATE notification_settings SET morning_time=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, value, now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data.startswith("notify_e_"))
async def notify_evening_time(call: CallbackQuery):
    await call.answer("Время сохранено")
    raw = call.data.rsplit("_", 1)[-1]
    value = f"{raw[:2]}:{raw[2:]}"
    await db_execute(
        "UPDATE notification_settings SET evening_time=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, value, now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data.startswith("notify_tz_"))
async def notify_timezone(call: CallbackQuery):
    mapping = {
        "notify_tz_moscow": "Europe/Moscow",
        "notify_tz_london": "Europe/London",
        "notify_tz_dubai": "Asia/Dubai",
        "notify_tz_nsk": "Asia/Novosibirsk",
    }
    value = mapping.get(call.data)
    if not value:
        await call.answer("Не удалось выбрать часовой пояс")
        return
    await call.answer("Часовой пояс сохранён")
    await ensure_notification_settings(call.from_user.id)
    await db_execute(
        "UPDATE notification_settings SET timezone=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, value, now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data == "notify_days_auto")
async def notify_days_auto(call: CallbackQuery):
    await call.answer("Дни обновлены")
    await ensure_notification_settings(call.from_user.id)
    profile = await get_profile(call.from_user.id)
    days = workout_days_from_frequency(profile["frequency"] if profile else None)
    await db_execute(
        "UPDATE notification_settings SET workout_days=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, days, now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.message(Command("team"))
async def team_stats(message: Message):
    if not pool:
        await message.answer("База данных пока не подключена.")
        return
    await touch_user(message)
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Эта команда доступна только администратору.")
        return

    since = now_utc() - timedelta(days=7)
    total = await db_fetchrow("SELECT COUNT(*) AS c FROM users WHERE consent=TRUE")
    active = await db_fetchrow(
        "SELECT COUNT(DISTINCT telegram_id) AS c FROM checkins WHERE created_at >= $1", since
    )
    checkins = await db_fetchrow(
        "SELECT COUNT(*) AS c FROM checkins WHERE created_at >= $1", since
    )
    await message.answer(
        "Команда за 7 дней\n\n"
        f"Участников с согласием: {total['c']}\n"
        f"Сдали хотя бы 1 отчёт: {active['c']}\n"
        f"Всего дневных отчётов: {checkins['c']}\n\n"
        "Личные медицинские сведения, вес и ограничения здесь не показываются."
    )

@router.message(Command("reset_profile"))
async def reset_profile(message: Message, state: FSMContext):
    if not pool: return
    await touch_user(message)
    if not await has_consent(message.from_user.id):
        await message.answer("Сначала /start.")
        return
    await db_execute("DELETE FROM app_week_plans WHERE telegram_id=$1", message.from_user.id)
    await db_execute("DELETE FROM profiles WHERE telegram_id=$1", message.from_user.id)
    await state.clear()
    await message.answer("Профиль сброшен. Напиши /start, чтобы заполнить его заново.")

@router.message(Command("delete_me"))
async def delete_me(message: Message, state: FSMContext):
    if not pool: return
    uid = message.from_user.id
    await db_execute("DELETE FROM notification_log WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM notification_settings WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM weekly_meal_plans WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM app_week_plans WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM app_payments WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM app_subscriptions WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM checkins WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM messages WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM profiles WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM users WHERE telegram_id=$1", uid)
    await state.clear()
    await message.answer("Твои данные FitMyN удалены. Чтобы начать заново — /start.")

@router.message(Command("terms"))
async def subscription_terms(message: Message):
    await message.answer(subscription_terms_text())


@router.message(Command("subscribe"))
async def subscribe_command(message: Message):
    if not pool or not bot:
        await message.answer("Оплата временно недоступна. Попробуй чуть позже.")
        return
    await touch_user(message)
    if not await get_profile(message.from_user.id):
        await message.answer("Сначала заполни анкету через /start — после неё начнутся 14 бесплатных дней.")
        return
    sub = await subscription_info(message.from_user.id)
    if sub["status"] == "active":
        until = sub["subscription_until"][:10] if sub["subscription_until"] else ""
        await message.answer(f"Подписка уже активна до {until}.")
        return
    link = await create_subscription_invoice_link(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Принимаю условия · оплатить {SUBSCRIPTION_STARS} ⭐", url=link)],
    ])
    await message.answer(subscription_terms_text(), reply_markup=kb)


@router.message(Command("cancel_subscription"))
async def cancel_subscription_command(message: Message):
    if not pool or not bot:
        return
    row = await ensure_subscription(message.from_user.id)
    charge_id = row["telegram_payment_charge_id"]
    if not charge_id or not row["subscription_until"] or row["subscription_until"] <= now_utc():
        await message.answer("Активной платной подписки с автопродлением сейчас нет.")
        return
    try:
        await bot.edit_user_star_subscription(user_id=message.from_user.id, telegram_payment_charge_id=charge_id, is_canceled=True)
        await db_execute("UPDATE app_subscriptions SET auto_renew=FALSE, updated_at=$2 WHERE telegram_id=$1", message.from_user.id, now_utc())
        await message.answer("Автопродление отключено. Доступ сохранится до конца уже оплаченного периода.")
    except Exception:
        logger.exception("Failed to cancel Telegram Stars subscription")
        await message.answer("Не получилось отключить автопродление. Напиши /paysupport с описанием проблемы.")


@router.message(Command("paysupport"))
async def payment_support(message: Message):
    details = (message.text or "").partition(" ")[2].strip()
    if not details:
        await message.answer("По вопросам оплаты отправь одним сообщением:\n/paysupport описание проблемы\n\nНе присылай данные карты, коды из SMS и пароли.")
        return
    delivered = False
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"💳 Fitmy2.0 — вопрос по оплате\nПользователь: {message.from_user.id} @{message.from_user.username or 'без_username'}\n\n{details}")
            delivered = True
        except Exception:
            logger.exception("Failed to deliver payment support request to admin %s", admin_id)
    await message.answer("Сообщение по оплате передано администратору." if delivered else "Не удалось передать сообщение. Попробуй ещё раз чуть позже.")


@router.pre_checkout_query()
async def subscription_pre_checkout(query: PreCheckoutQuery):
    ok = False
    error = "Не удалось проверить подписку. Создай новый счёт через /subscribe."
    try:
        parts = query.invoice_payload.split(":")
        payload_uid = int(parts[1]) if len(parts) >= 3 and parts[0] == "fitmy2-sub" else 0
        ok = payload_uid == query.from_user.id and query.currency == "XTR" and query.total_amount == SUBSCRIPTION_STARS
    except Exception:
        logger.exception("Subscription pre-checkout validation failed")
    await query.answer(ok=ok, error_message=None if ok else error)


@router.message(F.successful_payment)
async def subscription_successful_payment(message: Message):
    payment = message.successful_payment
    if not payment or payment.currency != "XTR" or not payment.invoice_payload.startswith("fitmy2-sub:"):
        return
    try:
        payload_uid = int(payment.invoice_payload.split(":")[1])
    except Exception:
        return
    if payload_uid != message.from_user.id or payment.total_amount != SUBSCRIPTION_STARS:
        logger.warning("Rejected mismatched subscription payment payload for user %s", message.from_user.id)
        return
    exp_ts = getattr(payment, "subscription_expiration_date", None)
    paid_until = datetime.fromtimestamp(exp_ts, tz=timezone.utc) if exp_ts else now_utc() + timedelta(days=30)
    charge_id = payment.telegram_payment_charge_id
    now = now_utc()
    await db_execute(
        """INSERT INTO app_payments(telegram_id,telegram_payment_charge_id,total_amount,currency,subscription_expiration_date,is_recurring,is_first_recurring,created_at)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT(telegram_payment_charge_id) DO NOTHING""",
        message.from_user.id, charge_id, payment.total_amount, payment.currency, paid_until,
        bool(getattr(payment, "is_recurring", False)), bool(getattr(payment, "is_first_recurring", False)), now,
    )
    await ensure_subscription(message.from_user.id)
    await db_execute(
        """UPDATE app_subscriptions SET status='active',subscription_until=$2,
        telegram_payment_charge_id=COALESCE(telegram_payment_charge_id,$3),auto_renew=TRUE,stars_amount=$4,updated_at=$5
        WHERE telegram_id=$1""",
        message.from_user.id, paid_until, charge_id, SUBSCRIPTION_STARS, now,
    )
    await message.answer(f"Оплата получена. Fitmy2.0 открыт до {paid_until.strftime('%d.%m.%Y')}. Автопродление включено. Отключить: /cancel_subscription.")


@router.message()
async def free_chat(message: Message):
    if not message.text: return
    if not await ensure_ready(message): return
    try:
        answer = await ask_ai(message.from_user.id, message.text)
        await message.answer(answer)
    except Exception:
        logger.exception("AI error")
        await message.answer("Не получилось получить ответ. Попробуй ещё раз.")

async def setup_telegram():
    if not bot:
        logger.warning("TELEGRAM_BOT_TOKEN is missing")
        return
    await bot.set_my_commands([
        BotCommand(command="start", description="Начать работу с FitMyN"),
        BotCommand(command="team", description="Статистика команды"),
        BotCommand(command="schedule", description="Настроить авто-сообщения"),
        BotCommand(command="mealplan", description="Рацион на 7 дней"),
        BotCommand(command="shopping", description="Список покупок"),
        BotCommand(command="subscribe", description="Оформить подписку"),
        BotCommand(command="cancel_subscription", description="Отключить автопродление"),
        BotCommand(command="terms", description="Условия подписки"),
        BotCommand(command="paysupport", description="Поддержка по оплате"),
        BotCommand(command="reset_profile", description="Перезаполнить профиль"),
        BotCommand(command="delete_me", description="Удалить мои данные"),
    ])
    await bot.set_my_description(
        "FitMyN — персональный ИИ-помощник по питанию, тренировкам и привычкам."
    )
    await bot.set_my_short_description(
        "ИИ-тренер и помощник по питанию: план, тренировки и контроль прогресса."
    )

    if APP_URL:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Открыть Fitmy2.0",
                    web_app=WebAppInfo(url=APP_URL),
                )
            )
            logger.info("Telegram Mini App menu button configured: %s", APP_URL)
        except Exception:
            logger.exception("Failed to configure Mini App menu button")

    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL}/telegram/{WEBHOOK_SECRET}"
        await bot.set_webhook(
            webhook_url,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=False,
        )
        logger.info("Webhook configured: %s", webhook_url)
    else:
        logger.warning("RENDER_EXTERNAL_URL missing; webhook not configured")

async def health(request: web.Request):
    configured = bool(bot and client and pool)
    status = 200 if configured else 503
    return web.json_response(
        {
            "service": "FitMyN",
            "configured": configured,
            "telegram": bool(bot),
            "openai": bool(client),
            "database": bool(pool),
        },
        status=status,
    )

async def _process_telegram_payload(payload: dict):
    try:
        if not bot:
            return
        update = Update.model_validate(payload, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception:
        logger.exception("Telegram update processing failed")


async def telegram_webhook(request: web.Request):
    """Acknowledge Telegram immediately and process updates in background.

    This prevents Telegram from retrying slow AI requests and also ignores duplicate update_id values.
    """
    if not bot:
        return web.Response(status=503, text="Telegram not configured")

    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != WEBHOOK_SECRET:
        return web.Response(status=403, text="Forbidden")

    payload = await request.json()
    update_id = payload.get("update_id")
    now = time.monotonic()

    # prune old ids
    for uid, ts in list(_seen_update_ids.items()):
        if now - ts > UPDATE_DEDUPE_TTL:
            _seen_update_ids.pop(uid, None)

    if isinstance(update_id, int):
        if update_id in _seen_update_ids:
            logger.info("Duplicate Telegram update ignored: %s", update_id)
            return web.Response(text="ok")
        _seen_update_ids[update_id] = now

    task = asyncio.create_task(_process_telegram_payload(payload))
    _update_tasks.add(task)
    task.add_done_callback(_update_tasks.discard)
    return web.Response(text="ok")


def validate_telegram_init_data(init_data: str, max_age_seconds: int = 86400):
    """Validate Telegram Mini App initData and return the Telegram user dict."""
    if not init_data or not TELEGRAM_BOT_TOKEN:
        return None
    try:
        values = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = values.pop("hash", "")
        if not received_hash:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(values.items()))
        secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated_hash, received_hash):
            return None
        auth_date = int(values.get("auth_date", "0") or 0)
        if auth_date and time.time() - auth_date > max_age_seconds:
            return None
        user_raw = values.get("user", "")
        user = json.loads(user_raw) if user_raw else None
        return user if isinstance(user, dict) else None
    except Exception:
        logger.exception("Telegram Mini App initData validation failed")
        return None


def app_request_user(request: web.Request):
    return validate_telegram_init_data(request.headers.get("X-Telegram-Init-Data", ""))


async def mini_app_index(request: web.Request):
    telegram_sdk = '<script src="https://telegram.org/js/telegram-web-app.js"></script>'
    html = MINI_APP_HTML
    if "telegram-web-app.js" not in html:
        html = html.replace("</head>", telegram_sdk + "</head>")
    html = html.replace("</body>", MINI_APP_PATCH + "</body>")
    return web.Response(
        text=html,
        content_type="text/html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"},
    )


def _parse_weight_value(value):
    if value is None:
        return None
    m = re.search(r"(\d{2,3}(?:[.,]\d{1,2})?)", str(value))
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", "."))
        return v if 30 <= v <= 300 else None
    except Exception:
        return None


async def get_app_goal_progress(user_id: int, profile=None):
    profile = profile or await get_profile(user_id)
    latest = await db_fetchrow(
        "SELECT weight FROM app_weight_log WHERE telegram_id=$1 ORDER BY created_at DESC LIMIT 1",
        user_id,
    )
    current = float(latest["weight"]) if latest else _parse_weight_value(profile["weight"] if profile else None)
    goal = await db_fetchrow("SELECT target_weight FROM app_goal_settings WHERE telegram_id=$1", user_id)
    target = float(goal["target_weight"]) if goal and goal["target_weight"] is not None else None
    first = await db_fetchrow(
        "SELECT weight FROM app_weight_log WHERE telegram_id=$1 ORDER BY created_at ASC LIMIT 1",
        user_id,
    )
    start = float(first["weight"]) if first else current
    remaining = max(0.0, current - target) if current is not None and target is not None else None
    progress = None
    if current is not None and target is not None and start is not None:
        total = max(0.1, start - target)
        progress = 100.0 if current <= target else max(0.0, min(100.0, (start - current) / total * 100.0))
    return {
        "current_weight": current,
        "target_weight": target,
        "start_weight": start,
        "remaining_weight": remaining,
        "progress_percent": progress,
    }


async def get_app_water(user_id: int):
    local_date = await user_local_date(user_id)
    row = await db_fetchrow(
        "SELECT water_ml FROM app_water_log WHERE telegram_id=$1 AND local_date=$2",
        user_id, local_date,
    )
    return {"date": local_date.isoformat(), "today_ml": int(row["water_ml"]) if row else 0, "goal_ml": 2000}


async def api_app_bootstrap(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)

    profile = await get_profile(user_id)
    first_weight_row = await db_fetchrow("SELECT 1 FROM app_weight_log WHERE telegram_id=$1 LIMIT 1", user_id)
    if not first_weight_row and profile:
        initial_weight = _parse_weight_value(profile["weight"])
        if initial_weight is not None:
            await db_execute(
                "INSERT INTO app_weight_log(telegram_id,weight,created_at) VALUES($1,$2,$3)",
                user_id, initial_weight, profile["updated_at"] or now_utc(),
            )
    settings = await db_fetchrow("SELECT * FROM notification_settings WHERE telegram_id=$1", user_id)
    active_plan = await get_active_weekly_meal_plan(user_id)
    goal_progress = await get_app_goal_progress(user_id, profile)
    water = await get_app_water(user_id)
    workout_progress = await get_app_workout_progress(user_id)
    photo_row = await db_fetchrow("SELECT photo_data FROM app_profile_photos WHERE telegram_id=$1", user_id)
    weight_rows = await db_fetch(
        "SELECT weight, created_at FROM app_weight_log WHERE telegram_id=$1 ORDER BY created_at ASC LIMIT 180",
        user_id,
    )
    subscription = await subscription_info(user_id) if profile else None
    app_week_plan = None
    if profile and await has_consent(user_id) and subscription and subscription["has_access"]:
        app_week_plan = await ensure_app_week_plan(user_id, wait_for_ai=False)

    profile_json = None
    if profile:
        profile_json = {k: profile[k] for k in [
            "name", "age", "sex", "height", "weight", "goal", "activity",
            "frequency", "equipment", "restrictions", "food", "sleep"
        ]}
    settings_json = None
    if settings:
        settings_json = {k: settings[k] for k in [
            "enabled", "timezone", "morning_time", "evening_time", "workout_days"
        ]}

    return web.json_response({
        "telegram_user": {
            "id": user_id,
            "first_name": tg_user.get("first_name"),
            "username": tg_user.get("username"),
            "photo_url": tg_user.get("photo_url"),
        },
        "profile": profile_json,
        "profile_updated_at": profile["updated_at"].isoformat() if profile and profile["updated_at"] else None,
        "goal_progress": goal_progress,
        "water": water,
        "workout_progress": workout_progress,
        "profile_photo": photo_row["photo_data"] if photo_row else None,
        "weight_history": [{"weight": float(r["weight"]), "created_at": r["created_at"].isoformat()} for r in weight_rows],
        "notifications": settings_json,
        "subscription": subscription,
        "weekly_plan": ({
            "start_date": active_plan["start_date"].isoformat(),
            "end_date": active_plan["end_date"].isoformat(),
            "meal_plan": active_plan["meal_plan"],
            "shopping_list": active_plan["shopping_list"],
        } if active_plan else None),
        "app_week_plan": ({
            "start_date": app_week_plan["start_date"].isoformat(),
            "end_date": app_week_plan["end_date"].isoformat(),
            "plan": decode_app_plan(app_week_plan["plan_json"]),
            "source": app_week_plan["source"],
        } if app_week_plan else None),
    }, headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"})




async def get_app_workout_progress(user_id: int):
    local_date = await user_local_date(user_id)
    week_start = local_date - timedelta(days=local_date.weekday())
    rows = await db_fetch(
        """SELECT local_date, workout_key, workout_name, completed_at
           FROM app_workout_log
           WHERE telegram_id=$1 AND local_date BETWEEN $2 AND $3
           ORDER BY local_date""",
        user_id, week_start, week_start + timedelta(days=6),
    )
    return {
        "week_start": week_start.isoformat(),
        "completed_count": len(rows),
        "completed_dates": [r["local_date"].isoformat() for r in rows],
        "today_completed": any(r["local_date"] == local_date for r in rows),
    }


async def api_app_complete_workout(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    try:
        body = await request.json()
    except Exception:
        body = {}
    workout_key = str(body.get("workout_key") or "daily").strip()[:80]
    workout_name = str(body.get("workout_name") or "Тренировка").strip()[:120]
    local_date = await user_local_date(user_id)
    await db_execute(
        """INSERT INTO app_workout_log(telegram_id,local_date,workout_key,workout_name,completed_at)
           VALUES($1,$2,$3,$4,$5)
           ON CONFLICT(telegram_id,local_date,workout_key)
           DO UPDATE SET workout_name=EXCLUDED.workout_name, completed_at=EXCLUDED.completed_at""",
        user_id, local_date, workout_key, workout_name, now_utc(),
    )
    return web.json_response(await get_app_workout_progress(user_id))


async def api_app_profile_photo(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    try:
        body = await request.json()
        photo_data = str(body.get("photo_data") or "")
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)
    if not photo_data.startswith("data:image/") or len(photo_data) > 1400000:
        return web.json_response({"error": "bad_photo"}, status=400)
    await db_execute(
        """INSERT INTO app_profile_photos(telegram_id,photo_data,updated_at) VALUES($1,$2,$3)
           ON CONFLICT(telegram_id) DO UPDATE SET photo_data=EXCLUDED.photo_data,updated_at=EXCLUDED.updated_at""",
        user_id, photo_data, now_utc(),
    )
    return web.json_response({"ok": True})


async def api_app_weight_history(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    rows = await db_fetch(
        "SELECT weight, created_at FROM app_weight_log WHERE telegram_id=$1 ORDER BY created_at ASC LIMIT 180",
        user_id,
    )
    return web.json_response({"items": [{"weight": float(r["weight"]), "created_at": r["created_at"].isoformat()} for r in rows]})


async def api_app_set_goal(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    try:
        body = await request.json()
        target = float(str(body.get("target_weight", "")).replace(",", "."))
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)
    if not 30 <= target <= 300:
        return web.json_response({"error": "bad_weight"}, status=400)
    first_weight = await db_fetchrow("SELECT 1 FROM app_weight_log WHERE telegram_id=$1 LIMIT 1", user_id)
    if not first_weight:
        profile = await get_profile(user_id)
        initial_weight = _parse_weight_value(profile["weight"] if profile else None)
        if initial_weight is not None:
            await db_execute("INSERT INTO app_weight_log(telegram_id,weight,created_at) VALUES($1,$2,$3)", user_id, initial_weight, now_utc())
    await db_execute(
        """INSERT INTO app_goal_settings(telegram_id,target_weight,updated_at) VALUES($1,$2,$3)
        ON CONFLICT(telegram_id) DO UPDATE SET target_weight=EXCLUDED.target_weight, updated_at=EXCLUDED.updated_at""",
        user_id, target, now_utc(),
    )
    return web.json_response({"target_weight": target})


async def api_app_set_weight(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    try:
        body = await request.json()
        weight = float(str(body.get("weight", "")).replace(",", "."))
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)
    if not 30 <= weight <= 300:
        return web.json_response({"error": "bad_weight"}, status=400)
    first_weight = await db_fetchrow("SELECT 1 FROM app_weight_log WHERE telegram_id=$1 LIMIT 1", user_id)
    if not first_weight:
        profile = await get_profile(user_id)
        initial_weight = _parse_weight_value(profile["weight"] if profile else None)
        if initial_weight is not None and abs(initial_weight - weight) > 0.001:
            await db_execute("INSERT INTO app_weight_log(telegram_id,weight,created_at) VALUES($1,$2,$3)", user_id, initial_weight, now_utc() - timedelta(seconds=1))
    await db_execute("INSERT INTO app_weight_log(telegram_id,weight,created_at) VALUES($1,$2,$3)", user_id, weight, now_utc())
    await db_execute("UPDATE profiles SET weight=$2, updated_at=$3 WHERE telegram_id=$1", user_id, str(weight), now_utc())
    return web.json_response({"current_weight": weight})


async def api_app_add_water(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    try:
        body = await request.json()
        delta = int(body.get("delta_ml", 0))
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)
    if delta == 0 or abs(delta) > 2000:
        return web.json_response({"error": "bad_amount"}, status=400)
    local_date = await user_local_date(user_id)
    row = await db_fetchrow(
        """INSERT INTO app_water_log(telegram_id,local_date,water_ml,updated_at)
        VALUES($1,$2,GREATEST(0,$3),$4)
        ON CONFLICT(telegram_id,local_date) DO UPDATE SET
            water_ml=GREATEST(0,LEAST(10000,app_water_log.water_ml+$3)), updated_at=EXCLUDED.updated_at
        RETURNING water_ml""",
        user_id, local_date, delta, now_utc(),
    )
    return web.json_response({"date": local_date.isoformat(), "water_ml": int(row["water_ml"]), "water_goal_ml": 2000})


async def api_app_week_regenerate(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    if not await has_consent(user_id):
        return web.json_response({"error": "consent_required"}, status=403)
    try:
        row = await regenerate_app_week_plan(user_id)
        return web.json_response({
            "start_date": row["start_date"].isoformat(),
            "end_date": row["end_date"].isoformat(),
            "plan": decode_app_plan(row["plan_json"]),
            "source": row["source"],
        })
    except Exception:
        logger.exception("Mini App week regeneration failed")
        return web.json_response({"error": "week_generation_failed"}, status=500)


async def api_app_replace_meal(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    if not await has_consent(user_id):
        return web.json_response({"error": "consent_required"}, status=403)
    try:
        body = await request.json()
        day = int(body.get("day"))
        index = int(body.get("index"))
        reason = str(body.get("reason", "different"))[:200]
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)
    if day not in range(7) or index not in range(4):
        return web.json_response({"error": "bad_position"}, status=400)
    try:
        row = await replace_app_meal(user_id, day, index, reason)
        return web.json_response({
            "start_date": row["start_date"].isoformat(),
            "end_date": row["end_date"].isoformat(),
            "plan": decode_app_plan(row["plan_json"]),
            "source": row["source"],
        })
    except Exception:
        logger.exception("Mini App meal replacement failed")
        return web.json_response({"error": "replace_failed"}, status=500)

async def api_app_subscription_checkout(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool or not bot:
        return web.json_response({"error": "not_ready"}, status=503)
    try:
        body = await request.json()
    except Exception:
        body = {}
    if body.get("terms_accepted") is not True:
        return web.json_response({"error": "terms_required"}, status=400)
    if not await get_profile(user_id):
        return web.json_response({"error": "profile_required"}, status=400)
    sub = await subscription_info(user_id)
    if sub["status"] == "active":
        return web.json_response({"error": "already_active", "subscription": sub}, status=409)
    try:
        link = await create_subscription_invoice_link(user_id)
        return web.json_response({"invoice_link": link, "stars": SUBSCRIPTION_STARS, "period_days": 30})
    except Exception:
        logger.exception("Failed to create subscription invoice link")
        return web.json_response({"error": "invoice_failed"}, status=500)


async def api_app_ask(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    if not await has_consent(user_id):
        return web.json_response({"error": "consent_required"}, status=403)
    body = await request.json()
    message = str(body.get("message", "")).strip()
    if not message:
        return web.json_response({"error": "message_required"}, status=400)
    if len(message) > 1500:
        return web.json_response({"error": "message_too_long"}, status=400)
    try:
        answer = await ask_ai(user_id, message)
        return web.json_response({"answer": answer})
    except Exception:
        logger.exception("Mini App AI request failed")
        return web.json_response({"error": "ai_failed"}, status=500)


async def cron_due(request: web.Request):
    if not CRON_SECRET:
        return web.Response(status=503, text="CRON_SECRET is not configured")
    supplied = request.headers.get("X-Cron-Secret", "")
    if supplied != CRON_SECRET:
        return web.Response(status=403, text="Forbidden")
    stats = await run_due_notifications()
    return web.json_response(stats)


async def on_startup(app: web.Application):
    await init_db()
    await setup_telegram()
    app["notification_task"] = asyncio.create_task(notification_loop())

async def on_cleanup(app: web.Application):
    for update_task in list(_update_tasks):
        update_task.cancel()
    if _update_tasks:
        await asyncio.gather(*list(_update_tasks), return_exceptions=True)

    task = app.get("notification_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    if bot:
        await bot.session.close()
    if pool:
        await pool.close()

def create_app():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_get("/app", mini_app_index)
    app.router.add_get("/app/", mini_app_index)
    app.router.add_get("/api/app/bootstrap", api_app_bootstrap)
    app.router.add_post("/api/app/goal", api_app_set_goal)
    app.router.add_post("/api/app/weight", api_app_set_weight)
    app.router.add_post("/api/app/water", api_app_add_water)
    app.router.add_post("/api/app/workout/complete", api_app_complete_workout)
    app.router.add_post("/api/app/profile/photo", api_app_profile_photo)
    app.router.add_get("/api/app/weight/history", api_app_weight_history)
    app.router.add_post("/api/app/week/regenerate", api_app_week_regenerate)
    app.router.add_post("/api/app/meal/replace", api_app_replace_meal)
    app.router.add_post("/api/app/subscription/checkout", api_app_subscription_checkout)
    app.router.add_post("/api/app/ask", api_app_ask)
    app.router.add_post("/telegram/{secret}", telegram_webhook)
    app.router.add_post("/cron/due", cron_due)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
