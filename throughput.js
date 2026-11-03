/* DESK THROUGHPUT panel: reads counters.json (written only by count.py and the desk scripts). Real counts only:
   a missing day/bot shows 0, nothing is estimated. Shared by index.html (bullpen desk) and city.html (Neon City).
   API: THRU.fetch() -> Promise<counters|null>; THRU.render(el, C, opts); THRU.bot(C, id) -> today's numbers for one bot;
        THRU.mount(el, opts) fetches + renders now and every 60 s. */
(function(){
var BOTS=['kiwi','scanner','news','whale','risk','quant','journal','options'];
var NAMES={kiwi:'Kiwi',scanner:'Scanner',news:'News Desk',whale:'Whale Tracker',risk:'Risk Manager',quant:'Quant Lab',journal:'Trade Journal',options:'Options Desk'};
var INT=['quotesCalls','barCalls','bars','optionCalls','optionContracts','webSearches','pagesFetched','xSearches','xPosts','ideasGenerated','ideasLogged','ideasRejected','ordersSent','fills','backtestVariants','simulatedTrades','runs'];
var TILES=[['price','Price checks','Questrade get_quotes calls (quotesCalls)'],['symbols','Symbols','unique symbols quoted today, all bots'],['bars','Bars','candles received from get_historical_data'],
 ['chains','Option chains','option chain / option quote calls (optionCalls)'],['headlines','Headlines','unique headlines recorded (de-duplicated per bot)'],['xPosts','X posts','X posts read'],
 ['ideas','Ideas','ideas generated (never fewer than ideas logged)'],['rejected','Rejected','ideas the Risk Manager blocked (risk_check.py BLOCK)'],['orders','Orders','orders sent (set_activity.py --approved)'],['sim','Simulated trades','backtest trades simulated by Quant Lab']];
function todayET(){return new Date().toLocaleDateString('en-CA',{timeZone:'America/Toronto'})}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function n0(v){return typeof v==='number'&&isFinite(v)?v:0}
function fmt(v){return Math.round(v).toLocaleString('en-US')}
function days(C){return Object.keys(C||{}).filter(function(k){return /^\d{4}-\d{2}-\d{2}$/.test(k)}).sort()}
function ideasOf(b){return Math.max(n0(b.ideasGenerated),n0(b.ideasLogged))}
function bot(C,id,date){var d=(C&&C[date||todayET()])||{},b=d[id]||{};var r={};INT.forEach(function(k){r[k]=n0(b[k])});
 var sq=b.symbolsQuoted||{},hd=b.headlines||{};r.symbols=(sq.unique||[]).slice();r.symbolsTotal=n0(sq.total);r.headlineCount=n0(hd.count);r.headlineItems=(hd.items||[]).slice();r.lastRun=b.lastRun||null;r.ideas=ideasOf(b);
 // items processed = data items received or produced (not API calls)
 r.items=r.symbolsTotal+r.bars+r.optionContracts+r.headlineCount+r.pagesFetched+r.xPosts+r.ideas+r.ideasRejected+r.ordersSent+r.fills+r.simulatedTrades;return r}
function desk(C,date){var t={price:0,symbols:0,bars:0,chains:0,headlines:0,xPosts:0,ideas:0,rejected:0,orders:0,sim:0,runs:0,items:0},u={};
 BOTS.forEach(function(id){var b=bot(C,id,date);t.price+=b.quotesCalls;b.symbols.forEach(function(s){u[s]=1});t.bars+=b.bars;t.chains+=b.optionCalls;t.headlines+=b.headlineCount;t.xPosts+=b.xPosts;
  t.ideas+=b.ideas;t.rejected+=b.ideasRejected;t.orders+=b.ordersSent;t.sim+=b.simulatedTrades;t.runs+=b.runs;t.items+=b.items});t.symbols=Object.keys(u).length;return t}
function avg7(C,today){var past=days(C).filter(function(d){return d<today}).slice(-7);if(!past.length)return null;var s={};
 past.forEach(function(d){var t=desk(C,d);for(var k in t)s[k]=(s[k]||0)+t[k]});for(var k in s)s[k]/=past.length;s._n=past.length;s._from=past[0];s._to=past[past.length-1];return s}
// rolling-digit odometer: each digit is a 0-9 strip that slides to its value
function odo(el,v){var str=fmt(v),prev=el.getAttribute('data-s');if(prev===str)return;
 if(!prev||prev.length!==str.length){var from=str.replace(/\d/g,'0');
  el.innerHTML=str.split('').map(function(ch,i){if(!/\d/.test(ch))return '<span class="od-s">'+ch+'</span>';var f=/\d/.test(from[i])?+from[i]:0;
   return '<span class="od-d"><span class="od-r" style="transform:translateY('+(-f)+'em)">0<br>1<br>2<br>3<br>4<br>5<br>6<br>7<br>8<br>9</span></span>'}).join('');
  el.offsetHeight;}
 var rs=el.querySelectorAll('.od-r'),k=0;str.split('').forEach(function(ch){if(/\d/.test(ch)){var r=rs[k++];if(r)r.style.transform='translateY('+(-ch)+'em)'}});
 el.setAttribute('data-s',str);el.setAttribute('aria-label',str)}
var CSS='.thru .th-g{display:grid;grid-template-columns:repeat(var(--thr-cols,3),1fr);gap:5px}.thru .th-t{border:1px solid var(--thr-line);border-radius:6px;padding:4px 6px;background:var(--thr-bg2)}'+
'.thru .th-t label{display:block;margin:0;font-size:9px;letter-spacing:.08em;color:var(--thr-dim);text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'+
'.thru .od{display:inline-flex;font-weight:800;font-size:16px;line-height:1em;height:1em;overflow:hidden;color:var(--thr-fg);font-variant-numeric:tabular-nums}.thru .od-d{display:inline-block;height:1em;overflow:hidden}.thru .od-r{display:inline-block;line-height:1em;transition:transform 1.3s cubic-bezier(.2,.8,.2,1)}'+
'.thru .th-a{font-size:9px;color:var(--thr-dim);white-space:nowrap}.thru .th-a .u{color:var(--thr-up)}.thru .th-a .d{color:var(--thr-down)}'+
'.thru .th-b{display:grid;grid-template-columns:92px 1fr 104px;gap:5px;align-items:center;font-size:10px;margin:2px 0}.thru .th-b .bb{height:7px;background:var(--thr-track);border-radius:4px;overflow:hidden}.thru .th-b .bb i{display:block;height:100%;border-radius:4px;transition:width 1.2s}'+
'.thru .th-b .n{text-align:right;color:var(--thr-dim);white-space:nowrap}.thru .th-h{font-size:9px;letter-spacing:.12em;color:var(--thr-dim);margin:8px 0 3px;text-transform:uppercase}'+
'.thru details{margin-top:6px;font-size:11px}.thru summary{cursor:pointer;color:var(--thr-accent);font-size:10px;letter-spacing:.06em}.thru ol{margin:4px 0;padding-left:18px;max-height:220px;overflow:auto}.thru li{margin:2px 0}.thru li a{color:var(--thr-fg)}.thru .tg{font-size:9px;color:var(--thr-dim)}'+
'.thru .th-e{font-size:10px;color:var(--thr-dim);margin-top:4px}.thru .au{border:1px dashed var(--thr-line);border-radius:6px;padding:5px 7px;margin-top:6px;font-size:10px;color:var(--thr-dim)}.thru .au b{color:var(--thr-fg)}';
function css(){if(document.getElementById('thru-css'))return;var s=document.createElement('style');s.id='thru-css';s.textContent=CSS;document.head.appendChild(s)}
function render(el,C,o){o=o||{};css();var colors=o.colors||{},names=o.names||NAMES,today=todayET(),T=desk(C,today),A=avg7(C,today),has=!!(C&&C[today]);
 if(!el.querySelector('.th-g')){el.classList.add('thru');el.innerHTML=(o.head||'<div class="ph">DESK THROUGHPUT</div>')+'<small class="th-sub"></small><div class="th-g">'+TILES.map(function(t){return '<div class="th-t" title="'+esc(t[2])+'"><label>'+esc(t[1])+'</label><span class="od" data-k="'+t[0]+'"></span><div class="th-a" data-a="'+t[0]+'"></div></div>'}).join('')+
  '</div><div class="th-avg th-e"></div><div class="th-h">Per bot · runs · items processed today</div><div class="th-bots"></div><div class="th-hl"></div><div class="th-au"></div>';}
 el.querySelector('.th-sub').textContent=(C?('today '+today+' ET · real counts from counters.json'+(C._meta&&C._meta.updated?' · updated '+new Date(C._meta.updated).toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',timeZone:'America/Toronto'})+' ET':'')):'counters.json not found yet · showing 0')+' · re-read every 60s';
 TILES.forEach(function(t){odo(el.querySelector('[data-k="'+t[0]+'"]'),T[t[0]]);var a=el.querySelector('[data-a="'+t[0]+'"]');
  if(!A){a.textContent='7d avg: —';return}var av=A[t[0]],diff=av?Math.round((T[t[0]]-av)/av*100):null;a.innerHTML='7d avg '+fmt(av)+(diff==null?'':' <span class="'+(diff>=0?'u':'d')+'">'+(diff>=0?'▲':'▼')+Math.abs(diff)+'%</span>')});
 el.querySelector('.th-avg').innerHTML=A?('7-day average over '+A._n+' past day'+(A._n===1?'':'s')+' ('+A._from.slice(5)+(A._n>1?' to '+A._to.slice(5):'')+'): '+fmt(A.items)+' items/day vs <b>'+fmt(T.items)+'</b> today · '+fmt(A.runs)+' runs/day vs <b>'+T.runs+'</b>'):'7-day comparison appears once past days are counted (none yet).'+(has?'':' No counts yet today: the numbers rise as routines call count.py.');
 var rows=BOTS.map(function(id){return [id,bot(C,id,today)]}),mx=Math.max(1,Math.max.apply(null,rows.map(function(r){return r[1].items})));
 el.querySelector('.th-bots').innerHTML=rows.map(function(r){var id=r[0],b=r[1],c=colors[id]||'var(--thr-accent)';
  var tip=names[id]+': runs '+b.runs+(b.lastRun?' (last '+b.lastRun.slice(11,16)+')':'')+' · quotes '+b.quotesCalls+' ('+b.symbolsTotal+' symbols, '+b.symbols.length+' unique) · bars '+b.bars+' in '+b.barCalls+' calls · option calls '+b.optionCalls+' ('+b.optionContracts+' contracts) · web searches '+b.webSearches+' · pages '+b.pagesFetched+' · headlines '+b.headlineCount+' · X searches '+b.xSearches+' ('+b.xPosts+' posts) · ideas '+b.ideas+' (logged '+b.ideasLogged+') · rejected '+b.ideasRejected+' · orders '+b.ordersSent+' · fills '+b.fills+' · backtest variants '+b.backtestVariants+' · simulated trades '+b.simulatedTrades;
  return '<div class="th-b" title="'+esc(tip)+'"><span style="color:'+c+'">'+esc(names[id]||id)+'</span><div class="bb"><i style="width:'+(b.items/mx*100)+'%;background:'+c+'"></i></div><span class="n">'+b.runs+' run'+(b.runs===1?'':'s')+' · '+fmt(b.items)+'</span></div>'}).join('');
 var hl=[];rows.forEach(function(r){r[1].headlineItems.forEach(function(h){hl.push({h:h,id:r[0]})})});hl.sort(function(a,b){return String(b.h.time).localeCompare(String(a.h.time))});
 var hEl=el.querySelector('.th-hl'),open=hEl.querySelector('details')&&hEl.querySelector('details').open;
 hEl.innerHTML='<details'+(open?' open':'')+'><summary>TODAY\'S LATEST HEADLINES ('+T.headlines+')</summary>'+(hl.length?'<ol>'+hl.slice(0,40).map(function(x){var h=x.h,t=h.time?new Date(h.time):null;
  var tt=t&&!isNaN(t)?t.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',timeZone:'America/Toronto'}):'';
  return '<li>'+(h.url&&/^https?:\/\//i.test(h.url)?'<a href="'+esc(h.url)+'" target="_blank" rel="noopener">'+esc(h.title)+'</a>':esc(h.title))+' <span class="tg">'+esc(names[x.id]||x.id)+(tt?' · '+tt+' ET':'')+'</span></li>'}).join('')+'</ol>'+(hl.length>40?'<div class="tg">latest 40 shown</div>':''):'<div class="th-e">No headlines recorded today.</div>')+'</details>';
 var au=(C&&C._audits)||[];var aEl=el.querySelector('.th-au'),aopen=aEl.querySelector('details')&&aEl.querySelector('details').open;
 aEl.innerHTML=au.map(function(a){var x=a.totals||{},ap=a.approx||[];var f=function(k,l){return x[k]==null?'':'<span>'+l+' <b>'+(ap.indexOf(k)>=0?'~':'')+fmt(x[k])+'</b></span>'};
  return '<details'+(aopen?' open':'')+' class="au"><summary>'+esc(a.label)+'</summary>'+[f('barRequests','bar requests'),f('bars','bars'),f('symbols','symbols'),f('optionChains','option chains'),f('watchlistPriceUpdates','watchlist price updates'),f('sourcesCited','sources cited'),f('ideas','ideas'),f('rejected','rejected'),f('taken','taken'),f('simulatedTrades','simulated trades')].filter(Boolean).join(' · ')+
  '<div class="tg" style="margin-top:3px">'+esc(a.note||'')+'</div></details>'}).join('');}
function get(){return fetch('counters.json?t='+Date.now(),{cache:'no-store'}).then(function(r){return r.ok?r.json():null}).catch(function(){return null})}
function mount(el,o){var go=function(){return get().then(function(C){window.THRU.data=C;render(el,C,o);o&&o.onData&&o.onData(C)})};go();setInterval(go,60000);return go}
window.THRU={fetch:get,render:render,bot:bot,desk:desk,mount:mount,today:todayET,NAMES:NAMES,data:null};
})();
