/* MISSED TRADES panel: hypothetical P&L of every desk idea that was NOT traded with real money (skipped, blocked by
   risk_check, vetoed by debate.py, expired, untaken, paper-only). Shared by index.html (bullpen) and city.html (Neon City).
   Same rules as missed.py (which writes missed.json for routines); the browser recomputes live from journal.json +
   data.json (+ counters.json for risk_check BLOCKs) every 60 s, so an open idea is re-marked to the newest desk price.
   Real data only: final = the journal's paper result; unrealized = (latest data.json watchlist price - entry) after fees;
   never triggered = $0. Fees = data.json `fees` (log_idea.py model): $0 commission, SEC fee on US sells, FX % on the USD P&L.
   API: MISSED.compute(journal, data, counters, now) -> model; MISSED.render(el, M, opts); MISSED.mount(el, opts). */
(function(){
var NAMES={kiwi:'Kiwi',scanner:'Scanner',news:'News Desk',whale:'Whale Tracker',risk:'Risk Manager',quant:'Quant Lab',journal:'Trade Journal',options:'Options Desk'};
var WHY={'paper-only':'paper-only','vetoed':'vetoed (debate)','blocked':'blocked (risk)','expired':'expired','skipped':'skipped','untaken':'untaken'};
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function r2(x){return Math.round((x+0)*100+(x>=0?1e-9:-1e-9))/100}
function etParts(d){var p={};new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23',weekday:'short'}).formatToParts(d||new Date()).forEach(function(x){p[x.type]=x.value});
 return {date:p.year+'-'+p.month+'-'+p.day,h:+p.hour%24,m:+p.minute,wd:p.weekday}}
function isoWeek(ds){var d=new Date(ds+'T12:00:00Z'),day=(d.getUTCDay()+6)%7;d.setUTCDate(d.getUTCDate()-day+3);var y=d.getUTCFullYear(),j=new Date(Date.UTC(y,0,4));
 return y+'-W'+String(1+Math.round(((d-j)/864e5-3+((j.getUTCDay()+6)%7))/7)).padStart(2,'0')}
function fees(side,entry,ex,n,cur,cfg){var st=cfg.stocksEtfs||{},comm=(+st.commissionPerOrder||0)*2,ecn=(+((st.ecnPerShare||{})[cur])||0)*n*2,sec=0,fx=0;
 if(cur==='USD'){sec=(+((cfg.secFee||{}).rate)||0)*(side==='long'?ex:entry)*n;}
 if(cur==='USD'&&(cfg.accountCurrency||'CAD')==='CAD'){var f=cfg.fx||{},sp=(+f.spreadPct||0)/100,mode=f.mode||'pnl',g=(ex-entry)*n*(side==='long'?1:-1);
  if(mode==='pnl')fx=sp*Math.abs(g);else if(mode==='round_trip')fx=sp*(entry+ex)*n;}
 return Math.round((comm+ecn+sec+fx)*1e4)/1e4}
function blockedKeys(C){var o={};for(var k in (C||{})){if(k.charAt(0)==='_')continue;var r=(C[k]||{}).risk;((r&&r.keys)||[]).forEach(function(x){if(x.indexOf('rejected:')===0)o[x.slice(9)]=1})}return o}
function realOf(D,k){var o=D&&D[k];if(typeof o==='number')return o;o=o||{};return typeof o.total==='number'?o.total:(+o.realized||0)+(+o.unrealized||0)}
function compute(J,D,C,now){now=now||new Date();var e=etParts(now),today=e.date,mins=e.h*60+e.m,mopen=!/Sat|Sun/.test(e.wd)&&mins>=570&&mins<960;
 D=D||{};var cfg=D.fees||{},rate=+((cfg.usdcad||{}).rate)||1.396,wl={},bl=blockedKeys(C),rows=[],excl=[];
 (D.watchlist||[]).forEach(function(w){if(w.journalId)wl[w.journalId]=w});
 function cad(x,cur){return cur==='USD'?x*rate:x}
 ((J&&J.ideas)||[]).forEach(function(i){var w=wl[i.id],cur=i.currency||'USD';
  if(i.manual||/^(k|manual)$/i.test(String(i.bot||''))){excl.push({id:i.id,why:'manual order by K'});return}
  if(i.taken==='yes'||i.realPnl!=null||i.realPnlCAD!=null){excl.push({id:i.id,why:'filled with real money'});return}
  if(w&&(w.status==='in trade'||w.fill!=null)){excl.push({id:i.id,why:'in trade (real fill)'});return}
  var why=i.mode==='paper'?'paper-only':(i.debate&&i.debate.verdict==='skip')?'vetoed':(bl[i.id]||bl[i.bot+':'+i.ticker+':'+i.side])?'blocked':(w&&w.status==='expired')?'expired':((w&&w.status==='skipped')||i.taken==='no')?'skipped':'untaken';
  var r={id:i.id,date:i.date,loggedAt:i.loggedAt||'',bot:i.bot,ticker:i.ticker,side:i.side,entry:i.entry,stop:i.stop,target:i.target,size:i.shares,currency:cur,strategy:i.strategy,why:why,exit:null,netCAD:0,state:'pending',outcome:null},res=i.result,mark=null;
  if(res){if(res.outcome==='no-fill'){r.state='not triggered';r.outcome='no-fill'}else{mark=res.exit;r.state='final';r.outcome=res.outcome}}
  else{var st=w&&w.status,last=w&&w.last;
   if(st==='target hit'||st==='stopped'){mark=st==='target hit'?i.target:i.stop;r.state='final';r.outcome=st==='target hit'?'target':'stop'}
   else if(st==='triggered'&&typeof last==='number'){var closed=i.date<today||(!mopen&&e.h>=16);mark=last;r.state=closed?'final':'unrealized';r.outcome=closed?'time':null;r.priceTime=w.priceTime}
   else if((st==='watching'||st==='expired')&&(i.date<today||e.h>=16)){r.state='not triggered';r.outcome='expired'}
   else if(st==='watching'){r.state='waiting'}}
  if(mark!=null){var g=(mark-i.entry)*i.shares*(i.side==='long'?1:-1),net=g-fees(i.side,i.entry,mark,i.shares,cur,cfg);r.exit=mark;r.net=r2(net);r.netCAD=r2(cad(net,cur))}
  rows.push(r)});
 rows.sort(function(a,b){return (b.date+b.loggedAt+b.id).localeCompare(a.date+a.loggedAt+a.id)});
 var wk=isoWeek(today),P={today:function(d){return d===today},week:function(d){return isoWeek(d)===wk},allTime:function(){return true}},T={},B={};
 Object.keys(P).forEach(function(p){var t={net:0,final:0,unrealized:0,ideas:0,scored:0,open:0,notTriggered:0,pending:0};
  rows.forEach(function(r){if(!P[p](r.date))return;t.ideas++;t.net+=r.netCAD;if(r.state==='final'){t.final+=r.netCAD;t.scored++}else if(r.state==='unrealized'){t.unrealized+=r.netCAD;t.open++}else if(r.state==='not triggered')t.notTriggered++;else t.pending++;
   var b=(B[r.bot]=B[r.bot]||{}),bp=(b[p]=b[p]||{net:0,ideas:0,open:0});bp.net=r2(bp.net+r.netCAD);bp.ideas++;if(r.state==='unrealized')bp.open++});
  t.net=r2(t.net);t.final=r2(t.final);t.unrealized=r2(t.unrealized);T[p]=t});
 Object.keys(B).forEach(function(b){Object.keys(P).forEach(function(p){B[b][p]=B[b][p]||{net:0,ideas:0,open:0}})});
 var RB={};(D.bots||[]).forEach(function(b){if(b.id)RB[b.id]={today:+b.pnlToday||0,week:+b.pnlWeek||0,allTime:+b.pnlAllTime||0}});
 return {today:today,week:wk,marketOpen:mopen,usdcad:rate,ideas:rows,excluded:excl,totals:T,byBot:B,real:{today:realOf(D,'pnlToday'),week:realOf(D,'pnlWeek'),allTime:realOf(D,'pnlAllTime'),byBot:RB},computedAt:now.toISOString()}}
function m(v){v=r2(v||0);return (v>0?'+':v<0?'−':'')+'$'+Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}
function cls(v){return v>0?'u':v<0?'d':'z'}
function px(v){return typeof v==='number'?(v>=100?v.toFixed(2):v.toFixed(2)):'-'}
function tET(iso){if(!iso)return '';var d=new Date(iso);return isNaN(d)?'':d.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',timeZone:'America/Toronto'})+' ET'}
function dShort(ds){var d=new Date(ds+'T12:00:00Z');return d.toLocaleDateString('en-US',{month:'short',day:'numeric',timeZone:'UTC'})}
var CSS='.missed{container-type:inline-size}.missed .ms-sub{display:block;font-size:10.5px;color:var(--ms-dim);margin-bottom:8px}'+
'.missed .ms-g{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.missed .ms-t{border:1px solid var(--ms-line);border-radius:6px;padding:6px 7px;background:var(--ms-bg2);min-width:0}'+
'.missed .ms-t label{display:block;margin:0;font-size:9px;letter-spacing:.1em;color:var(--ms-dim);text-transform:uppercase}.missed .ms-t b{display:block;font-size:clamp(13px,5.4cqw,20px);font-weight:800;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'+
'.missed .ms-t .cmp{font-size:10px;color:var(--ms-dim);margin-top:2px;line-height:1.3}.missed .ms-t .cmp i{font-style:normal;color:var(--ms-fg)}'+
'.missed .u{color:var(--ms-up)}.missed .d{color:var(--ms-down)}.missed .z{color:var(--ms-fg)}'+
'.missed .ms-line{margin:8px 0 2px;font-size:12px;font-weight:700;font-variant-numeric:tabular-nums}.missed .ms-h{font-size:9px;letter-spacing:.12em;color:var(--ms-dim);margin:10px 0 4px;text-transform:uppercase}'+
'.missed table{border-collapse:collapse;width:100%;font-size:11px}.missed th{font-size:9px;letter-spacing:.08em;color:var(--ms-dim);text-align:right;font-weight:400;padding:3px 4px;border-bottom:1px solid var(--ms-line)}.missed th:first-child,.missed td:first-child{text-align:left}'+
'.missed td{padding:4px;text-align:right;border-bottom:1px solid var(--ms-line);font-variant-numeric:tabular-nums;white-space:nowrap}'+
'.missed .ms-i{border:1px solid var(--ms-line);border-left:3px solid var(--c,var(--ms-accent));border-radius:6px;padding:6px 8px;margin-top:6px;background:var(--ms-bg2)}'+
'.missed .ms-i .top{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.missed .ms-i .tk{font-weight:800;color:var(--ms-fg)}.missed .ms-i .sd{font-size:9px;font-weight:800;letter-spacing:.08em;padding:1px 5px;border-radius:3px;border:1px solid currentColor}.missed .sd.long{color:var(--ms-up)}.missed .sd.short{color:var(--ms-down)}'+
'.missed .ms-i .pl{margin-left:auto;font-weight:800;font-size:14px;font-variant-numeric:tabular-nums}.missed .ms-i .meta{font-size:10.5px;color:var(--ms-dim);margin-top:3px;display:flex;flex-wrap:wrap;gap:2px 10px}.missed .ms-i .meta b{color:var(--ms-fg);font-weight:600}'+
'.missed .st{font-size:9px;font-weight:800;letter-spacing:.08em;padding:1px 5px;border-radius:3px;text-transform:uppercase;border:1px solid var(--ms-line);color:var(--ms-dim)}.missed .st.unrealized{color:var(--ms-warn);border-color:var(--ms-warn);animation:msb 1.6s infinite}.missed .st.final{color:var(--ms-fg)}@keyframes msb{50%{opacity:.45}}'+
'.missed .wy{font-size:9px;color:var(--ms-dim);border:1px dashed var(--ms-line);padding:0 4px;border-radius:3px}'+
'.missed .ms-n{font-size:10px;color:var(--ms-dim);margin-top:8px;line-height:1.4}.missed details{margin-top:4px}.missed summary{cursor:pointer;color:var(--ms-accent);font-size:10px;letter-spacing:.06em}'+
'.missed td .r{display:block;color:var(--ms-dim);font-size:9.5px}@container (max-width:330px){.missed .ms-g{gap:4px}.missed .ms-t{padding:5px}.missed table{font-size:10.5px}.missed td,.missed th{padding:3px 2px}}';
function css(){if(document.getElementById('missed-css'))return;var s=document.createElement('style');s.id='missed-css';s.textContent=CSS;document.head.appendChild(s)}
function item(r,o){var names=o.names||NAMES,col=(o.colors||{})[r.bot];var stLab=r.state==='unrealized'?'unrealized':r.state==='final'?'final · '+(r.outcome==='target'?'hit target':r.outcome==='stop'?'hit stop':'flat at close'):r.state;
 return '<div class="ms-i"'+(col?' style="--c:'+col+'"':'')+'><div class="top"><span class="tk">'+esc(r.ticker)+'</span><span class="sd '+esc(r.side)+'">'+esc(String(r.side).toUpperCase())+' '+esc(r.size)+' sh</span><span class="st '+esc(r.state.replace(' ','-'))+'">'+esc(stLab)+'</span><span class="wy">'+esc(WHY[r.why]||r.why)+'</span>'+
  '<span class="pl '+cls(r.netCAD)+'">'+(r.state==='not triggered'||r.state==='waiting'||r.state==='pending'?'$0.00':m(r.netCAD))+'</span></div>'+
  '<div class="meta"><span>'+esc(dShort(r.date))+' · <b>'+esc(names[r.bot]||r.bot)+'</b></span><span>entry <b>'+px(r.entry)+'</b></span><span>stop <b>'+px(r.stop)+'</b></span><span>target <b>'+px(r.target)+'</b></span>'+
  (r.exit!=null?'<span>'+(r.state==='unrealized'?'last':'exit')+' <b>'+px(r.exit)+'</b>'+(r.priceTime?' '+esc(tET(r.priceTime)):'')+'</span>':'')+'<span>'+esc(r.currency)+'</span></div></div>'}
function render(el,M,o){o=o||{};css();var names=o.names||NAMES,colors=o.colors||{},T=M.totals,R=M.real;el.classList.add('missed');
 var tiles=[['today','Today'],['week','This week'],['allTime','All time']].map(function(p){var t=T[p[0]];
  return '<div class="ms-t"><label>'+p[1]+'</label><b class="'+cls(t.net)+'">'+m(t.net)+'</b><div class="cmp">Real: <i class="'+cls(R[p[0]])+'">'+m(R[p[0]])+'</i><br>'+t.ideas+' idea'+(t.ideas===1?'':'s')+(t.open?' · <span style="color:var(--ms-warn)">'+t.open+' open '+m(t.unrealized)+'</span>':'')+'</div></div>'}).join('');
 var line='<div class="ms-line">Real: <span class="'+cls(R.today)+'">'+m(R.today)+'</span> · Missed: <span class="'+cls(T.today.net)+'">'+m(T.today.net)+'</span> <span style="font-weight:400;color:var(--ms-dim);font-size:10px">today</span></div>';
 var bots=Object.keys(M.byBot).sort(function(a,b){return M.byBot[b].allTime.net-M.byBot[a].allTime.net});
 var tb=bots.length?'<div class="ms-h">Per bot · missed vs real</div><table><tr><th>Bot</th><th>Today</th><th>Week</th><th>All time</th></tr>'+bots.map(function(b){var v=M.byBot[b],rb=R.byBot[b]||{today:0,week:0,allTime:0};
  return '<tr><td style="color:'+(colors[b]||'inherit')+'">'+esc(names[b]||b)+'</td>'+['today','week','allTime'].map(function(p){return '<td><span class="'+cls(v[p].net)+'">'+m(v[p].net)+'</span><span class="r">real '+m(rb[p])+'</span></td>'}).join('')+'</tr>'}).join('')+'</table>':'';
 var first=M.ideas.slice(0,12),rest=M.ideas.slice(12);
 var list='<div class="ms-h">Every idea not traded with real money · newest first</div>'+(M.ideas.length?first.map(function(r){return item(r,o)}).join('')+(rest.length?'<details><summary>'+rest.length+' older ideas</summary>'+rest.map(function(r){return item(r,o)}).join('')+'</details>':''):'<div class="ms-n">No untaken ideas in journal.json yet.</div>');
 var anyOpen=M.ideas.some(function(r){return r.state==='unrealized'});
 el.innerHTML=(o.head||'<div class="ph">MISSED TRADES · NOT REAL MONEY</div>')+'<small class="ms-sub">Hypothetical P&amp;L of the ideas the desk did not take, CAD after fees · recomputed '+esc(tET(M.computedAt))+(M.marketOpen?' · market open':' · market closed')+' · re-read every 60s</small>'+
  '<div class="ms-g">'+tiles+'</div>'+line+tb+list+
  '<div class="ms-n">Not real money. Skipped, blocked (risk_check), vetoed (debate), expired, untaken and paper-only ideas from journal.json, scored at the alert\'s plan. Final = the journal\'s paper result; '+
  '<b>unrealized</b> = triggered, still open, marked to the latest Questrade price the desk wrote to data.json'+(anyOpen?'':' (none open now)')+'; never triggered = $0. Fees: $0 commission, SEC fee on US sells, '+esc(((o.fx)||1.5))+'% FX on the USD P&amp;L, USD at '+esc(M.usdcad.toFixed(4))+' CAD. '+
  'Excludes ideas that filled with real money and K\'s own manual orders'+(M.excluded.length?' ('+M.excluded.length+' excluded)':'')+'. Real = desk P&amp;L in data.json.</div>'}
function j(u){return fetch(u+'?t='+Date.now(),{cache:'no-store'}).then(function(r){return r.ok?r.json():null}).catch(function(){return null})}
function mount(el,o){o=o||{};var go=function(){return Promise.all([j('journal.json'),j('data.json'),j('counters.json')]).then(function(x){
  if(!x[0]&&!x[1]){el.innerHTML=(o.head||'')+'<div class="ms-n">Could not load journal.json / data.json; retrying in 60s.</div>';return}
  var D=x[1]||window.DESK_DATA||{};o.fx=((D.fees||{}).fx||{}).spreadPct;var M=compute(x[0]||{ideas:[]},D,x[2]);window.MISSED.data=M;render(el,M,o);o.onData&&o.onData(M)})};
 go();setInterval(go,60000);return go}
window.MISSED={compute:compute,render:render,mount:mount,fees:fees,data:null};
})();
