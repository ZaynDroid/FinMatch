/* FinMatch app.js - DEMO frontend only. Data lives in localStorage. No real security or real reconciliation. */
const ADMIN_SUPPORT_EMAIL='support@finmatch.example'; // change the default support email here
const TODAY='2026-10-30',$=s=>document.querySelector(s),CUR={INR:'₹',USD:'$',EUR:'€'};
let S=JSON.parse(localStorage.getItem('fm_state')||'null')||fresh(),CB=null;
function fresh(){const s=JSON.parse(JSON.stringify(SEED));s.settings={theme:'light',lang:'en',font:'normal',cur:'INR',datefmt:'dmy',density:'normal',email:ADMIN_SUPPORT_EMAIL,biz:'Sharma Traders',wa:'9876543210',notify:true,cards:[1,1,1,1]};return s}
const save=()=>localStorage.setItem('fm_state',JSON.stringify(S)),cfg=()=>S.settings;

/* ---------- helpers ---------- */
const t=k=>(cfg().lang==='hi'&&HI[k])||k;
const inr=n=>CUR[cfg().cur]+Number(n).toLocaleString('en-IN');
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fd=d=>{if(!d)return'-';const[y,m,x]=d.split('-'),f=cfg().datefmt;return f==='mdy'?`${m}/${x}/${y}`:f==='iso'?d:`${x}/${m}/${y}`};
const toast=m=>{const e=document.createElement('div');e.className='tst';e.textContent=m;$('#toast').append(e);setTimeout(()=>e.remove(),2800)};
const modal=h=>$('#modal').innerHTML=`<div class="ov" onclick="if(event.target===this)closeModal()"><div class="mb">${h}</div></div>`;
const closeModal=()=>$('#modal').innerHTML='';
const ask=(msg,cb)=>{CB=cb;modal(`<p>${msg}</p><div class="row"><button class="btn green" onclick="closeModal();CB()">OK</button><button class="btn ghost" onclick="closeModal()">${t('Cancel')}</button></div>`)};
const sh=n=>n>=1e5?(n/1e5).toFixed(1)+'L':Math.round(n/1e3)+'k';
const getInv=id=>S.invoices.find(i=>i.id===id),getPay=id=>S.payments.find(p=>p.id===id);
const paidOf=id=>S.matches.filter(m=>m.inv===id&&m.status==='approved').reduce((a,m)=>a+getPay(m.pay).amt,0); // only approved matches count
function ist(i){const p=paidOf(i.id);if(p>=i.amt)return'Paid';if(p>0)return'Part Paid';return S.matches.some(m=>m.inv===i.id&&m.status==='suggested')?'Please check':'Pending'}
function badge(s){const c={Paid:'green',Matched:'green','Part Paid':'sage','Please check':'red',Pending:'amber','Not matched':'amber'}[s]||'sage';return `<span class="badge b-${c}">${t(s)}</span>`}
const session=()=>JSON.parse(localStorage.getItem('fm_session')||sessionStorage.getItem('fm_session')||'null');
const logo=()=>`<span class="logo"><svg width="30" height="20" viewBox="0 0 30 20"><circle cx="10" cy="10" r="7" fill="none" stroke="#8FBE98" stroke-width="3"/><circle cx="20" cy="10" r="7" fill="none" stroke="#29855F" stroke-width="3"/></svg>FinMatch</span>`;
const footer=()=>`<footer class="ft">Demo version · ${t('Contact Admin')}: <a href="mailto:${cfg().email}">${cfg().email}</a></footer>`;

/* ---------- login / logout ---------- */
async function login(e,role){
 e.preventDefault();
 const f=e.target,id=f.uid.value.trim(),pw=f.pw.value;
 let m='';
 if(!id||!pw){f.querySelector('.err').textContent='Mobile/email aur password bharein';return false}
 if(role==='user'&&/^\d+$/.test(id)&&id.length!==10){f.querySelector('.err').textContent='Mobile number 10 digit ka hona chahiye';return false}

 try {
  const res = await fetch('/api/login', {
   method: 'POST',
   headers: {'Content-Type': 'application/json'},
   body: JSON.stringify({id, pw, role})
  });
  const json = await res.json();
  if(json.ok && json.user) {
   (f.rem&&f.rem.checked?localStorage:sessionStorage).setItem('fm_session',JSON.stringify({
    role: json.user.role,
    id: json.user.email,
    mobile: json.user.mobile,
    name: json.user.business_name,
    owner: json.user.owner_name
   }));
   location.hash='#/'+(role==='admin'?'ahome':'home');
   render();
   return false;
  } else if(!json.ok) {
   m = json.error || 'Password galat hai';
  }
 } catch(err) {
  // Offline fallback to DEMO
  const d=DEMO[role];
  if(!((id===d.id||(role==='user'&&id===d.mobile))&&pw===d.pw)) m='Password galat hai';
 }

 if(m){f.querySelector('.err').textContent=m;return false}
 (f.rem&&f.rem.checked?localStorage:sessionStorage).setItem('fm_session',JSON.stringify({role,id}));
 location.hash='#/'+(role==='admin'?'ahome':'home');render();return false}
function logout(){localStorage.removeItem('fm_session');sessionStorage.removeItem('fm_session');location.hash='';render()}
function fillDemo(r){const f=$('#f-'+r);f.uid.value=DEMO[r].id;f.pw.value=DEMO[r].pw}
function togglePw(r){const i=$('#f-'+r).pw;i.type=i.type==='password'?'text':'password'}
function setLang(){cfg().lang=cfg().lang==='hi'?'en':'hi';save();render()}
function landing(){const L=(r,adm)=>`<form id="f-${r}" class="card lc ${adm?'adm':''}" onsubmit="return login(event,'${r}')" novalidate>
 <h3>${adm?'<span class="role">Admin</span> ':''}${t(adm?'Admin Login':'Business Owner Login')}</h3>
 <input class="in" name="uid" placeholder="${adm?'Admin email':'Mobile number / Email'}" autocomplete="username">
 <input class="in" name="pw" type="password" placeholder="${t('Password')}">
 <div class="row"><label><input type="checkbox" onclick="togglePw('${r}')"> Show password</label>${adm?'':'<label><input type="checkbox" name="rem"> Remember me</label>'}</div>
 <p class="err"></p><button class="btn green" style="width:100%">${t('Login')}</button>
 <div class="demo">Try demo: ${adm?DEMO.admin.id+' / '+DEMO.admin.pw:DEMO.user.id+' / '+DEMO.user.pw}<br><button type="button" class="btn ghost s" onclick="fillDemo('${r}')">Fill demo login</button></div>
 ${adm?'':'<div class="row sm"><a href="#" onclick="forgot();return false">Forgot password?</a><a href="#" onclick="register();return false">New business? Register</a></div>'}</form>`;
 const tiles=[['⬆️','Upload Files','Add your bills and payments.'],['🔗','Reconciliation','Match payments to bills.'],['💰','Outstanding Balances','See who still owes you.'],['📊','Reports','Download or print a summary.']];
 return `<div class="land"><header>${logo()}<span class="row"><button class="ib" style="color:#fff" onclick="setLang()">EN/हिं</button><a style="color:#fff" href="#" onclick="helpModal();return false">Help</a></span></header>
 <section class="hero"><h1>Simple Hisaab. Sahi Match.</h1><p class="mu">Apne bills aur payments ko aasaani se match karein</p><div class="logins">${L('user',0)}${L('admin',1)}</div>
 <p class="sm mu">Connected to FinMatch SQLite Database Backend with Users & Admin Auth.</p></section>
 <section class="tiles">${tiles.map(x=>`<div class="card center"><div class="ic">${x[0]}</div><b>${t(x[1])}</b><p class="sm mu">${x[2]}</p></div>`).join('')}</section>${footer()}</div>`}
function forgot(){modal(`<h3>Forgot password?</h3><p>Demo only: no real reset. Use the demo login, or email <a href="mailto:${cfg().email}">${cfg().email}</a>.</p><button class="btn" onclick="closeModal()">OK</button>`)}
function register(){modal(`<h3>New business registration</h3><div class="f"><label>Business name<input class="in" id="r1" placeholder="Sharma Traders"></label><label>Owner name<input class="in" id="r2" placeholder="Rajesh Sharma"></label><label>Mobile number<input class="in" id="r3" inputmode="numeric" placeholder="9876543210"></label><label>Email address<input class="in" id="remail" type="email" placeholder="owner@business.com"></label><label>Password<input class="in" id="r4" type="password" placeholder="Password (min 4 chars)"></label></div><p class="err" id="rerr"></p><button class="btn green" onclick="doReg()">Register Business</button>`)}
async function doReg(){
 const bname=$('#r1').value.trim(),oname=$('#r2').value.trim(),mob=$('#r3').value.trim(),email=$('#remail').value.trim(),pw=$('#r4').value.trim();
 if(!bname||!oname||!mob||!email||!pw)return $('#rerr').textContent='Sab fields bharein';
 if(!/^\d{10}$/.test(mob))return $('#rerr').textContent='Mobile number 10 digit ka hona chahiye';
 if(!/^[\w\.\+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\.\-]+$/.test(email))return $('#rerr').textContent='Email address sahi format mein bharein';
 if(pw.length<4)return $('#rerr').textContent='Password kam se kam 4 character ka ho';

 try {
  const res = await fetch('/api/register', {
   method: 'POST',
   headers: {'Content-Type': 'application/json'},
   body: JSON.stringify({business_name: bname, owner_name: oname, email, mobile: mob, password: pw, role: 'user'})
  });
  const json = await res.json();
  if(json.ok){
   S.businesses.push({id:json.user.user_id,name:bname,owner:oname,town:'-',mobile:mob,email:email,joined:TODAY,status:'Active',files:0});
   save();closeModal();toast('Business registered in SQLite database! You can now login.');
   return;
  } else {
   $('#rerr').textContent = json.error || 'Registration failed';
   return;
  }
 } catch(err) {
  S.businesses.push({id:'B'+Date.now(),name:bname,owner:oname,town:'-',mobile:mob,email:email,joined:TODAY,status:'Active',files:0});
  save();closeModal();toast('Registered (demo mode).');
 }
}
function helpModal(){modal(`<h3>Help</h3><p>Demo login: user@finmatch.demo / demo123</p><p>Admin support: <a href="mailto:${cfg().email}">${cfg().email}</a></p><button class="btn" onclick="closeModal()">OK</button>`)}

/* ---------- shell ---------- */
const USR=[['home','Home','','🏠'],['upload','Upload Files','','⬆️'],['recon','Reconciliation','Match Payments','🔗'],['review','Please Check','Manual Review','👀'],['dues','Outstanding Balances','Pending Dues','💰'],['entries','All Entries','','📒'],['reports','Reports','','📊'],['settings','Settings','','⚙️'],['help','Help & Support','','❓']];
const ADM=[['ahome','Admin Home','','🏠'],['biz','Businesses','','🏪'],['support','Support Requests','','✉️'],['arecon','Reconciliation Overview','','🔗'],['adues','Outstanding Balances Overview','','💰'],['areports','Reports','','📊'],['asettings','Admin Settings','','⚙️']];
const PG={home:['See your bills, payments and pending money at a glance.',()=>pHome(),()=>charts()],upload:['Upload your bills and payments files (CSV or Excel) here.',()=>pUpload()],
 recon:['Click Start Reconciliation to match payments with bills. Matches are only suggestions until you approve them.',()=>pRecon(0)],review:['Check each suggested match. Approve it, reject it, or link the payment to a different bill.',()=>pReview()],
 dues:['See who still owes you money and send a WhatsApp reminder.',()=>pDues(0)],entries:['All your bills and payments in one list.',()=>pEntries()],reports:['Summary of your matching and collections. Download or print.',()=>pReports(0)],
 settings:['Change language, theme and other choices. Saved on this device.',()=>pSettings(0)],help:['Answers to common questions, and a way to contact the admin.',()=>pHelp()],
 ahome:['Platform overview (view only).',()=>pAHome(),()=>achart()],biz:['All registered businesses. You can enable or disable them.',()=>pBiz()],support:['Messages sent by businesses via Contact Admin.',()=>pSupport()],
 arecon:['Pick a business to see its matching results. View only.',()=>bizSel()+pRecon(1)],adues:['Pick a business to see its pending dues. View only.',()=>bizSel()+pDues(1)],areports:['Platform summary.',()=>pReports(1)],asettings:['Admin settings.',()=>pSettings(1)]};
function render(){const b=document.body,c=cfg();b.className=(c.theme==='dark'?'dark ':'')+(c.font==='large'?'large ':'')+(c.density==='compact'?'compact':'');
 const ses=session(),root=$('#root');if(!ses){root.innerHTML=landing();return}
 const nav=ses.role==='admin'?ADM:USR;let r=location.hash.slice(2);
 if(!nav.some(n=>n[0]===r)){location.hash='#/'+nav[0][0];return} // role guard: wrong role -> own home
 const n=nav.find(x=>x[0]===r),pg=PG[r];
 root.innerHTML=`<div id="app"><aside><div class="row">${logo()}</div><nav>${nav.map(x=>`<a href="#/${x[0]}" class="${x[0]===r?'on':''}" onclick="document.body.classList.remove('nav')">${x[3]} ${t(x[1])}${x[2]?`<small>${t(x[2])}</small>`:''}</a>`).join('')}</nav></aside>
 <div class="main"><div class="top"><button class="ib burger" onclick="document.body.classList.toggle('nav')">☰</button><h2>${t(n[1])}</h2>
 <input class="in" placeholder="🔍 ${t('Search')}" onkeydown="if(event.key==='Enter')gsearch(this.value)">
 <span class="sm mu">${fd(TODAY)}</span><span class="role">${ses.role==='admin'?'Admin':'Business Owner'}</span>
 <button class="ib" onclick="setLang()">EN/हिं</button><button class="ib" onclick="set('theme',cfg().theme==='dark'?'light':'dark')">${c.theme==='dark'?'☀️':'🌙'}</button>
 <div class="dd"><button class="ib" onclick="this.parentNode.classList.toggle('open')">🔔</button><div class="menu">${notes(ses.role)}</div></div>
 <div class="dd"><button class="ib" onclick="this.parentNode.classList.toggle('open')">❓</button><div class="menu"><b>Help</b><p class="sm">Admin: <a href="mailto:${c.email}">${c.email}</a></p></div></div>
 <div class="dd"><button class="ib" onclick="this.parentNode.classList.toggle('open')">👤</button><div class="menu"><p class="sm">Logged in as: ${ses.role==='admin'?'Admin':'Business Owner'}<br>${esc(ses.id)}</p>${ses.role==='admin'?'':'<a href="#/settings">Profile &amp; '+t('Settings')+'</a>'}<button onclick="logout()">${t('Logout')}</button></div></div></div>
 <main><p class="hint">${t(pg[0])}</p>${pg[1]()}</main>${footer()}</div></div>`;
 if(pg[2])pg[2]()}
function notes(role){if(role==='admin')return `<p class="sm">${S.support.filter(x=>x.status==='Open').length} open support requests</p>`;const n=S.matches.filter(m=>m.status==='suggested').length,o=S.invoices.filter(i=>i.due<TODAY&&paidOf(i.id)<i.amt).length;return `<p class="sm">👀 ${n} ${t('Please check')}</p><p class="sm">⏰ ${o} ${t('Overdue')}</p>`}
function gsearch(q){const ses=session();if(ses.role==='admin'){ST('bizt').q=q;location.hash='#/biz';render()}else{ST('entries').q=q;location.hash='#/entries';render()}}
function set(k,v){cfg()[k]=v;save();render()}

/* ---------- generic table: search, sort, filter chips, pagination, stacked cards on mobile ---------- */
const TB={},T={},ST=id=>T[id]=T[id]||{q:'',p:1,s:null,d:1,f:'all',fs:'',df:''};
function tbl(id,cols,rows,o={}){TB[id]={cols,rows,o};const st=ST(id);return `<div class="card"><div class="tools"><input class="in" placeholder="🔍 ${t('Search')}" value="${esc(st.q)}" oninput="ST('${id}').q=this.value;ST('${id}').p=1;draw('${id}')"><div class="chips" id="ch-${id}">${chips(id)}</div>${o.extra||''}</div><div id="td-${id}">${body(id)}</div></div>`}
const chips=id=>(TB[id].o.chips||[]).map(c=>`<button class="chip ${ST(id).f===c[0]?'on':''}" onclick="ST('${id}').f='${c[0]}';ST('${id}').p=1;draw('${id}')">${t(c[1])}</button>`).join('');
function draw(id){const a=$('#td-'+id),b=$('#ch-'+id);if(a)a.innerHTML=body(id);if(b)b.innerHTML=chips(id)}
function srt(id,i){const s=ST(id);s.d=s.s===i?-s.d:1;s.s=i;draw(id)}
function pgz(id,d){ST(id).p+=d;draw(id)}
function body(id){const{cols,rows,o}=TB[id],st=ST(id);let r=rows();if(o.ff&&st.f!=='all')r=r.filter(x=>o.ff(x,st.f));
 if(st.q)r=r.filter(x=>Object.values(x).join(' ').toLowerCase().includes(st.q.toLowerCase()));
 if(st.s!==null){const c=cols[st.s];r=[...r].sort((a,b)=>{const x=c.v(a),y=c.v(b);return(x>y?1:x<y?-1:0)*st.d})}
 const n=Math.ceil(r.length/8)||1;st.p=Math.max(1,Math.min(st.p,n));const pg=r.slice((st.p-1)*8,st.p*8);
 return `<div class="tw"><table><thead><tr>${cols.map((c,i)=>`<th onclick="srt('${id}',${i})">${t(c.l)}${st.s===i?(st.d>0?' ▲':' ▼'):''}</th>`).join('')}</tr></thead><tbody>${pg.map(x=>`<tr class="${o.rc?o.rc(x):''}">${cols.map(c=>`<td data-label="${t(c.l)}">${c.h?c.h(x):c.v(x)}</td>`).join('')}</tr>`).join('')||'<tr><td>Nothing found</td></tr>'}</tbody></table></div>
 <div class="pager"><button class="chip" ${st.p<2?'disabled':''} onclick="pgz('${id}',-1)">‹</button>${st.p} / ${n}<button class="chip" ${st.p>=n?'disabled':''} onclick="pgz('${id}',1)">›</button></div>`}
const vb=(fn,id)=>`<button class="btn ghost s" onclick="${fn}('${id}')">${t('View')}</button>`;
const eb=id=>`<button class="btn s" onclick="editInv('${id}')">✏️ ${t('Edit Invoice')}</button>`;
const PAYNOTE=()=>`<p class="sm mu">${t('Payment records come from your bank/UPI and cannot be changed.')}</p>`;

/* ---------- Home ---------- */
function totals(){const bill=S.invoices.reduce((a,i)=>a+i.amt,0),rec=S.invoices.reduce((a,i)=>a+paidOf(i.id),0);return{bill,rec,pend:bill-rec,matched:S.invoices.filter(i=>ist(i)==='Paid').length}}
const card=(ic,l,v,d)=>`<div class="card sc"><span class="ic">${ic}</span><div><div class="mu">${t(l)}</div><div class="big">${v}</div><div class="sm mu">${d}</div></div></div>`;
function pHome(){const x=totals(),c=cfg().cards;
 const cs=[['🧾','Total Bills',inr(x.bill),'▲ 8% vs last month'],['💵','Money Received',inr(x.rec),'▲ 5% vs last month'],['✅','Matched Bills',x.matched,'▲ 2 vs last month'],['⏳','Pending Amount',inr(x.pend),'▼ 3% vs last month']].filter((_,i)=>c[i]);
 const rows=()=>[...S.invoices.slice(-5).reverse().map(i=>({id:i.id,cust:i.cust,type:'Bill',bill:i.amt,pa:paidOf(i.id),st:ist(i),date:i.date})),...S.payments.slice(-3).reverse().map(p=>({id:p.id,cust:p.from,type:'Payment',bill:0,pa:p.amt,st:'Matched',date:p.date}))];
 return `<div class="row"><a class="btn" href="#/recon">▶ ${t('Start Reconciliation')}</a><a class="btn ghost" href="#/dues">${t('View Outstanding Balances')}</a></div>
 <div class="grid4">${cs.map(a=>card(...a)).join('')}</div>
 <div class="grid3">${['Bills status','Billed vs Received (6 months)','Top 5 pending customers'].map((h,n)=>`<div class="card"><h3>${h}</h3><canvas id="c${n+1}" height="230"></canvas><p id="tk${n+1}" class="tk"></p></div>`).join('')}</div>
 <h3>${t('Recent Entries')}</h3>`+tbl('recent',[{l:'ID',v:r=>r.id},{l:'Customer',v:r=>r.cust},{l:'Bill Amount',v:r=>r.bill,h:r=>r.bill?inr(r.bill):'-'},{l:'Payment Amount',v:r=>r.pa,h:r=>r.pa?inr(r.pa):'-'},{l:'Status',v:r=>r.st,h:r=>badge(r.st)},{l:'Date',v:r=>r.date,h:r=>fd(r.date)},
 {l:'Action ',v:()=>'',h:r=>r.type==='Bill'?eb(r.id):vb('viewPay',r.id)}],rows)+PAYNOTE()}
const valPlug={id:'v',afterDatasetsDraw(ch){const x=ch.ctx,h=ch.options.indexAxis==='y';x.fillStyle=cfg().theme==='dark'?'#F2F7F4':'#061F24';x.font='bold 12px sans-serif';x.textAlign=h?'left':'center';
 ch.data.datasets.forEach((d,i)=>ch.getDatasetMeta(i).data.forEach((b,j)=>x.fillText(sh(d.data[j]),h?b.x+4:b.x,h?b.y+4:b.y-4)))}};
function charts(){if(typeof Chart==='undefined'){['tk1','tk2','tk3'].forEach(i=>$('#'+i).textContent='Charts need internet (first load).');return}
 Chart.defaults.color=cfg().theme==='dark'?'#F2F7F4':'#061F24';Chart.defaults.font.size=13;
 const cnt={Paid:0,Pending:0,'Please check':0};S.invoices.forEach(i=>{const s=ist(i);cnt[s==='Part Paid'?'Pending':s]++});const tot=S.invoices.length,pc=k=>Math.round(cnt[k]/tot*100);
 new Chart($('#c1'),{type:'doughnut',data:{labels:Object.keys(cnt).map(k=>`${t(k)} ${pc(k)}%`),datasets:[{data:Object.values(cnt),backgroundColor:['#29855F','#E0A12B','#C0392B'],borderWidth:0}]},options:{plugins:{legend:{position:'bottom'}}}});
 $('#tk1').textContent=`Is mahine ${Math.round(totals().rec/totals().bill*100)}% bills ka paisa aa chuka hai.`;
 new Chart($('#c2'),{type:'bar',data:{labels:MONTHS,datasets:[{label:'Billed',data:BILLED,backgroundColor:'#0C5150'},{label:'Received',data:RECEIVED,backgroundColor:'#29855F'}]},options:{scales:{y:{display:false},x:{grid:{display:false}}},plugins:{legend:{position:'bottom'}}},plugins:[valPlug]});
 $('#tk2').textContent=`Oct mein ${inr(BILLED[5])} ke bill bane, ${inr(RECEIVED[5])} aaye.`;
 const by={};S.invoices.forEach(i=>by[i.cust]=(by[i.cust]||0)+i.amt-paidOf(i.id));const top=Object.entries(by).sort((a,b)=>b[1]-a[1]).slice(0,5);
 new Chart($('#c3'),{type:'bar',data:{labels:top.map(x=>x[0]),datasets:[{data:top.map(x=>x[1]),backgroundColor:'#8FBE98'}]},options:{indexAxis:'y',layout:{padding:{right:40}},scales:{x:{display:false},y:{grid:{display:false}}},plugins:{legend:{display:false}}},plugins:[valPlug]});
 $('#tk3').textContent=`${top[0][0]} ka sabse zyada ${inr(top[0][1])} baaki hai.`}

/* ---------- Upload ---------- */
const UP={inv:[],pay:[]};
function pUpload(){const p=(k,h)=>`<div class="card"><h3>${h}</h3><div class="drop" ondragover="event.preventDefault();this.classList.add('on')" ondragleave="this.classList.remove('on')" ondrop="event.preventDefault();this.classList.remove('on');pick('${k}',event.dataTransfer.files[0])"><p>Drag &amp; drop a file here</p><label class="btn">Browse<input type="file" hidden accept=".csv,.xlsx,.xls" onchange="pick('${k}',this.files[0])"></label></div><div id="fi-${k}"></div><button class="btn ghost" onclick="sample('${k}')">⬇ Sample CSV</button><p class="sm mu">CSV / Excel only. Columns: customer, amount, date (YYYY-MM-DD), reference</p></div>`;
 return `<div class="grid2">${p('inv','Upload Bills (Invoices)')}${p('pay','Upload Payments Received')}</div>`}
function dl(blob,n){const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=n;a.click()}
function sample(k){dl(new Blob(['customer,amount,date,reference\nSharma Kirana,12500,2026-10-05,'+(k==='inv'?'B-2201':'UPI4382910')+'\nGupta Hardware,48000,2026-10-06,'+(k==='inv'?'B-2202':'NEFT771204')+'\n'],{type:'text/csv'}),k==='inv'?'sample-bills.csv':'sample-payments.csv')}
function pick(k,f){if(!f)return;const box=$('#fi-'+k);if(!/\.(csv|xlsx|xls)$/i.test(f.name)){box.innerHTML='<p class="err">Sirf CSV ya Excel file chunein.</p>';return}
 if(typeof XLSX==='undefined')return toast('Internet chahiye (SheetJS load nahi hua)');
 box.innerHTML=`<p>📄 ${esc(f.name)} (${(f.size/1024).toFixed(1)} KB)</p><div class="bar"><i id="pb-${k}"></i></div>`;let w=0;
 const iv=setInterval(()=>{const b=$('#pb-'+k);if(!b)return clearInterval(iv);w+=25;b.style.width=w+'%';if(w>=100){clearInterval(iv);f.arrayBuffer().then(buf=>parse(k,f,buf))}},90)}
function parse(k,f,buf){const wb=XLSX.read(buf),rows=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]],{defval:''}).map(o=>{const n={};for(const x in o)n[x.toLowerCase().trim()]=o[x];return n}),bad=[],ok=[];
 rows.forEach((r,i)=>{const a=Number(String(r.amount).replace(/,/g,''));if(!String(r.customer||'').trim())bad.push(`Row ${i+2} mein customer ka naam khaali hai`);else if(r.amount==='')bad.push(`Row ${i+2} mein amount khaali hai`);else if(!(a>0))bad.push(`Row ${i+2} mein amount galat hai`);
  else ok.push({cust:String(r.customer).trim(),amt:a,date:/^\d{4}-\d\d-\d\d$/.test(r.date)?r.date:TODAY,ref:String(r.reference||'')})});UP[k]=ok;
 $('#fi-'+k).innerHTML=`<p>📄 ${esc(f.name)}</p><p><b>${rows.length}</b> rows found, <b>${bad.length}</b> with problems</p>${bad.slice(0,5).map(x=>`<p class="err">${esc(x)}</p>`).join('')}
 <div class="tw"><table><tr><th>Customer</th><th>Amount</th><th>Date</th><th>Ref</th></tr>${ok.slice(0,5).map(r=>`<tr><td>${esc(r.cust)}</td><td>${inr(r.amt)}</td><td>${fd(r.date)}</td><td>${esc(r.ref)}</td></tr>`).join('')}</table></div>
 <div class="row"><button class="btn green" onclick="imp('${k}')">Add ${ok.length} rows</button><button class="btn ghost" onclick="UP['${k}']=[];$('#fi-${k}').innerHTML=''">✖ Remove</button></div>`}
function imp(k){const n=Date.now()%100000;UP[k].forEach((r,i)=>{if(k==='inv'){const d=new Date(r.date);d.setDate(d.getDate()+15);S.invoices.push({id:'INV-'+(n+i),cust:r.cust,amt:r.amt,date:r.date,due:d.toISOString().slice(0,10),ref:r.ref,phone:'',note:'',edited:'',hist:[]})}
 else S.payments.push({id:'PAY-'+(n+i),from:r.cust,amt:r.amt,date:r.date,mode:'UPI',ref:r.ref})});S.businesses[0].files++;save();toast(UP[k].length+' rows added. Now run Reconciliation.');UP[k]=[];$('#fi-'+k).innerHTML=''}

/* ---------- Reconciliation ---------- */
function runRecon(){const w=s=>s.toLowerCase().split(/\W+/).filter(x=>x.length>2); // simple demo rule: name + amount + date closeness
 S.payments.forEach(p=>{if(S.matches.some(m=>m.pay===p.id))return;S.invoices.forEach(i=>{if(paidOf(i.id)>=i.amt)return;const nm=w(p.from).some(x=>w(i.cust).includes(x)),same=p.amt===i.amt,
  sc=(nm?40:0)+(same?45:p.amt<i.amt?15:0)+(Math.abs(new Date(p.date)-new Date(i.date))<12*864e5?10:0);
  if(sc>=50)S.matches.push({id:'M'+Date.now()+i.id,inv:i.id,pay:p.id,score:sc,reason:`${nm?'Naam milta hai':'Naam alag hai'}, ${same?'amount same hai':'amount alag hai'}`,status:'suggested'})})});save()}
function startRecon(){$('#rp').innerHTML='<div class="bar"><i id="rpb"></i></div>';let w=0;const iv=setInterval(()=>{w+=10;$('#rpb').style.width=w+'%';if(w>=100){clearInterval(iv);runRecon();toast('Reconciliation done');render()}},120)}
function reconRows(){const r=[];S.matches.forEach(m=>{if(m.status==='rejected')return;const i=getInv(m.inv),p=getPay(m.pay);r.push({id:i.id,cust:i.cust,amt:i.amt,pa:p.amt,score:m.score,st:m.status==='approved'?(p.amt>=i.amt?'matched':'part'):'check'})});
 S.invoices.forEach(i=>{if(!S.matches.some(m=>m.inv===i.id&&m.status!=='rejected'))r.push({id:i.id,cust:i.cust,amt:i.amt,pa:0,score:0,st:'none'})});return r}
function pRecon(ro){const r=reconRows(),c=k=>r.filter(x=>x.st===k).length,L={matched:'Matched',part:'Part Paid',check:'Please check',none:'Not matched'};
 return `${ro?'':`<div class="row"><button class="btn green" onclick="startRecon()">▶ ${t('Start Reconciliation')}</button><div id="rp" style="flex:1"></div></div>`}
 <div class="note a">Matches are suggestions until you approve them. Only approved matches change the balances.</div>
 <div class="grid4">${card('📋','Records checked',S.invoices.length+S.payments.length,'')}${card('✅','Matched',c('matched'),'')}${card('🟢','Part Paid',c('part'),'')}${card('❔','Not matched',c('none'),'')}</div>`+
 tbl('recon',[{l:'Invoice ID',v:x=>x.id},{l:'Customer',v:x=>x.cust},{l:'Bill Amount',v:x=>x.amt,h:x=>inr(x.amt)},{l:'Payment Amount',v:x=>x.pa,h:x=>x.pa?inr(x.pa):'-'},
 {l:'Match Strength',v:x=>x.score,h:x=>`<div class="bar"><i style="width:${x.score}%"></i></div>${x.score>=80?'Strong':x.score>=60?'Medium':'Weak'}`},{l:'Status',v:x=>x.st,h:x=>badge(L[x.st])},
 {l:'Action ',v:()=>'',h:x=>x.st==='check'&&!ro?`<a class="btn ghost s" href="#/review">${t('Please Check')}</a>`:vb('viewInv',x.id)}],reconRows,
 {chips:[['all','All'],['matched','Matched'],['part','Part Paid'],['none','Not matched'],['check','Please check']],ff:(x,f)=>x.st===f})}

/* ---------- Please Check (manual review) ---------- */
function pReview(){const L=S.matches.filter(m=>m.status==='suggested');if(!L.length)return '<div class="card center">✅ Nothing to check right now.</div>';
 return L.map(m=>{const i=getInv(m.inv),p=getPay(m.pay),amb=S.matches.filter(x=>x.pay===m.pay&&x.status==='suggested').length>1,diff=i.amt-paidOf(i.id)-p.amt;
 return `<div class="card" style="margin-bottom:14px"><div class="pair"><div><b>🧾 ${i.id}</b><br>${esc(i.cust)}<br>${inr(i.amt)} · ${fd(i.due)}<br>${eb(i.id)}</div>
 <div class="center">${m.score}%<br><span class="sm">${m.score>=80?'Strong':m.score>=60?'Medium':'Weak'}</span></div>
 <div><b>💵 ${p.id}</b> (${t('View')} only)<br>${esc(p.from)}<br>${inr(p.amt)} · ${fd(p.date)} · ${p.mode}<br><span class="sm">${esc(p.ref)}</span></div></div>
 <p>💡 ${esc(m.reason)}</p>${amb?'<div class="note a">⚠ This payment could match more than one bill. Please choose carefully.</div>':''}
 ${diff?`<div class="note ${diff>0?'a':'r'}">Amount differs by ${inr(Math.abs(diff))}. Fix it by editing the bill or linking to another bill. Payments cannot be changed.</div>`:''}${PAYNOTE()}
 <div class="row"><button class="btn green" onclick="decide('${m.id}','approved')">✔ ${t('Approve')}</button><button class="btn red" onclick="decide('${m.id}','rejected')">✖ ${t('Reject')}</button><button class="btn ghost" onclick="relink('${m.id}')">🔀 ${t('Link to a different bill')}</button></div></div>`}).join('')}
function decide(id,s){ask(s==='approved'?'Approve this match? Balances will change.':'Reject this match?',()=>{S.matches.find(m=>m.id===id).status=s;save();toast(s==='approved'?'Match approved':'Match rejected');render()})}
function relink(id){const m=S.matches.find(x=>x.id===id);modal(`<h3>${t('Link to a different bill')}</h3><select class="in" id="rl">${S.invoices.map(i=>`<option value="${i.id}" ${i.id===m.inv?'selected':''}>${i.id} - ${esc(i.cust)} - ${inr(i.amt)}</option>`).join('')}</select><p class="sm">This will link ${m.pay} to the chosen bill and approve it.</p><div class="row"><button class="btn green" onclick="doRelink('${id}')">OK</button><button class="btn ghost" onclick="closeModal()">${t('Cancel')}</button></div>`)}
function doRelink(id){const m=S.matches.find(x=>x.id===id);m.inv=$('#rl').value;m.status='approved';m.score=100;m.reason='Aapne khud bill chuna';save();closeModal();toast('Linked and approved');render()}

/* ---------- Outstanding Balances ---------- */
function duesRows(){return S.invoices.map(i=>{const p=paidOf(i.id);return{id:i.id,cust:i.cust,amt:i.amt,paid:p,bal:i.amt-p,due:i.due,st:ist(i),od:i.due<TODAY&&i.amt-p>0}})}
function wa(id){const i=getInv(id),b=i.amt-paidOf(id),msg=`Namaste ${i.cust}, aapka ${inr(b)} baaki hai (Bill ${id}, due ${fd(i.due)}). Kripya bhugtan karein. - ${cfg().biz}`;window.open('https://wa.me/91'+i.phone+'?text='+encodeURIComponent(msg),'_blank')}
function pDues(ro){const r=duesRows(),n=f=>r.filter(f).length;
 return `<div class="grid4">${card('💰','Total outstanding',inr(r.reduce((a,x)=>a+x.bal,0)),'')}${card('✅','Fully paid',n(x=>x.st==='Paid'),'')}${card('🟢','Part paid',n(x=>x.st==='Part Paid'),'')}${card('⏳','Unpaid',n(x=>x.st==='Pending'||x.st==='Please check'),'')}</div><p class="sm mu">Balance Left is calculated only from approved matches. Overdue bills are highlighted.</p>`+
 tbl('dues',[{l:'Invoice ID',v:x=>x.id},{l:'Customer',v:x=>x.cust},{l:'Bill Amount',v:x=>x.amt,h:x=>inr(x.amt)},{l:'Paid So Far',v:x=>x.paid,h:x=>inr(x.paid)},{l:'Balance Left',v:x=>x.bal,h:x=>`<b>${inr(x.bal)}</b>`},{l:'Due Date',v:x=>x.due,h:x=>fd(x.due)},{l:'Status',v:x=>x.st,h:x=>badge(x.st)},
 {l:'Action ',v:()=>'',h:x=>vb('viewInv',x.id)+(ro||!x.bal?'':eb(x.id)+`<button class="btn green s" onclick="wa('${x.id}')">💬 ${t('WhatsApp Reminder')}</button>`)}],duesRows,
 {chips:[['all','All'],['unpaid','Unpaid'],['part','Part paid'],['paid','Fully paid'],['od','Overdue']],ff:(x,f)=>f==='unpaid'?(x.st==='Pending'||x.st==='Please check'):f==='part'?x.st==='Part Paid':f==='paid'?x.st==='Paid':x.od,rc:x=>x.od?'od':''})}

/* ---------- All Entries ---------- */
function entRows(){const st=ST('entries');return[...S.invoices.map(i=>({id:i.id,cust:i.cust,type:'Bill',amt:i.amt,date:i.date,ref:i.ref,st:ist(i)})),...S.payments.map(p=>({id:p.id,cust:p.from,type:'Payment',amt:p.amt,date:p.date,ref:p.ref,st:S.matches.some(m=>m.pay===p.id&&m.status==='approved')?'Matched':S.matches.some(m=>m.pay===p.id&&m.status==='suggested')?'Please check':'Pending'}))].filter(r=>(!st.fs||r.st===st.fs)&&(!st.df||r.date>=st.df))}
function pEntries(){const x=`<select class="in" style="width:150px" onchange="ST('entries').fs=this.value;draw('entries')"><option value="">Status: All</option>${['Paid','Matched','Part Paid','Pending','Please check'].map(s=>`<option>${s}</option>`).join('')}</select><input type="date" class="in" style="width:160px" onchange="ST('entries').df=this.value;draw('entries')">`;
 return tbl('entries',[{l:'ID',v:r=>r.id},{l:'Customer',v:r=>r.cust},{l:'Type',v:r=>r.type},{l:'Amount',v:r=>r.amt,h:r=>inr(r.amt)},{l:'Date',v:r=>r.date,h:r=>fd(r.date)},{l:'Reference',v:r=>r.ref},{l:'Status',v:r=>r.st,h:r=>badge(r.st)},
 {l:'Action ',v:()=>'',h:r=>r.type==='Bill'?vb('viewInv',r.id)+eb(r.id):vb('viewPay',r.id)}],entRows,{chips:[['all','All'],['Bill','Bill'],['Payment','Payment']],ff:(r,f)=>r.type===f,extra:x})+PAYNOTE()}

/* ---------- invoice edit / views (payments are VIEW ONLY everywhere) ---------- */
function editInv(id){const i=getInv(id);modal(`<h3>${t('Edit Invoice')} ${id}</h3><div class="f"><label>${t('Customer')}<input class="in" id="e1" value="${esc(i.cust)}"></label><label>${t('Bill Amount')}<input class="in" id="e2" type="number" value="${i.amt}"></label><label>${t('Due Date')}<input class="in" id="e3" type="date" value="${i.due}"></label><label>Reference<input class="in" id="e4" value="${esc(i.ref)}"></label><label>Notes<input class="in" id="e5" value="${esc(i.note)}"></label></div><p class="err" id="eerr"></p><div class="row"><button class="btn green" onclick="saveInv('${id}')">${t('Save')}</button><button class="btn ghost" onclick="closeModal()">${t('Cancel')}</button></div>`)}
function saveInv(id){const i=getInv(id),c=$('#e1').value.trim(),a=Number($('#e2').value),d=$('#e3').value,er=m=>$('#eerr').textContent=m;
 if(!c)return er('Customer ka naam likhein');if(!(a>0))return er('Amount 0 se zyada hona chahiye');if(!d)return er('Due date chunein');if(a<paidOf(id))return er('Amount, ab tak mile paise se kam nahi ho sakta');
 const ch=[];if(c!==i.cust)ch.push('customer');if(a!==i.amt)ch.push(`amount ${inr(i.amt)} → ${inr(a)}`);if(d!==i.due)ch.push('due date');
 Object.assign(i,{cust:c,amt:a,due:d,ref:$('#e4').value.trim(),note:$('#e5').value.trim(),edited:new Date().toLocaleString()});i.hist.unshift({t:i.edited,c:ch.join(', ')||'details'});save();closeModal();toast('Invoice saved');render()}
function viewInv(id){const i=getInv(id),ps=S.matches.filter(m=>m.inv===id&&m.status==='approved').map(m=>getPay(m.pay));
 modal(`<h3>🧾 ${id}</h3><p>${esc(i.cust)}<br>${t('Bill Amount')}: ${inr(i.amt)} · ${t('Paid So Far')}: ${inr(paidOf(id))}<br>${t('Due Date')}: ${fd(i.due)} · ${badge(ist(i))}<br>Ref: ${esc(i.ref)} ${i.note?'· '+esc(i.note):''}</p>
 <b>Approved payments</b>${ps.map(p=>`<p class="sm">${p.id}: ${inr(p.amt)} (${p.mode}, ${fd(p.date)})</p>`).join('')||'<p class="sm">None yet</p>'}
 <b>History</b>${i.hist.map(h=>`<p class="sm">${esc(h.t)}: ${esc(h.c)}</p>`).join('')||'<p class="sm">No edits</p>'}<button class="btn" onclick="closeModal()">OK</button>`)}
function viewPay(id){const p=getPay(id);modal(`<h3>💵 ${id}</h3><p>${esc(p.from)}<br>${inr(p.amt)} · ${p.mode}<br>${fd(p.date)} · ${esc(p.ref)}</p>${PAYNOTE()}<button class="btn" onclick="closeModal()">OK</button>`)}

/* ---------- Reports and export ---------- */
function repRows(){return[...S.matches.map(m=>({Type:'Match',Invoice:m.inv,Payment:m.pay,Customer:getInv(m.inv).cust,'Bill Amount':getInv(m.inv).amt,'Payment Amount':getPay(m.pay).amt,Decision:m.status,Strength:m.score,Reason:m.reason})),
 ...S.invoices.filter(i=>!S.matches.some(m=>m.inv===i.id&&m.status!=='rejected')).map(i=>({Type:'Unresolved',Invoice:i.id,Customer:i.cust,'Bill Amount':i.amt,Decision:'No payment found'}))]}
function exp(kind,rows,name){if(typeof XLSX==='undefined')return toast('Internet chahiye (SheetJS)');const ws=XLSX.utils.json_to_sheet(rows);
 if(kind==='csv')dl(new Blob([XLSX.utils.sheet_to_csv(ws)],{type:'text/csv'}),name+'.csv');else{const wb=XLSX.utils.book_new();XLSX.utils.book_append_sheet(wb,ws,'Report');XLSX.writeFile(wb,name+'.xlsx')}}
function pReports(adm){const x=totals(),R=adm?S.businesses.map(b=>({Business:b.name,Owner:b.owner,Town:b.town,Status:b.status,Files:b.files})):repRows(),nm=adm?'platform-report':'finmatch-report';
 const by={};S.invoices.forEach(i=>by[i.cust]=(by[i.cust]||0)+i.amt-paidOf(i.id));const top=Object.entries(by).sort((a,b)=>b[1]-a[1]).slice(0,5);
 const btn=`<div class="row"><button class="btn" onclick='exp("csv",${JSON.stringify(R).replace(/'/g,'&#39;')},"${nm}")'>⬇ CSV</button><button class="btn" onclick='exp("xlsx",${JSON.stringify(R).replace(/'/g,'&#39;')},"${nm}")'>⬇ Excel</button><button class="btn ghost" onclick="window.print()">🖨 Print</button></div>`;
 if(adm)return `${btn}<div class="grid4">${card('🏪','Total Businesses',S.businesses.length,'')}${card('📁','Total Files Uploaded',S.businesses.reduce((a,b)=>a+b.files,0),'')}${card('✉️','Open Support Requests',S.support.filter(s=>s.status==='Open').length,'')}${card('🚫','Disabled',S.businesses.filter(b=>b.status==='Disabled').length,'')}</div>`;
 return `${btn}<div class="grid4">${card('🧾','Total Bills',inr(x.bill),'')}${card('💵','Money Received',inr(x.rec),'')}${card('⏳','Pending Amount',inr(x.pend),'')}${card('👀','Please check',S.matches.filter(m=>m.status==='suggested').length,'')}</div>
 <div class="grid2"><div class="card"><h3>Top 5 pending customers</h3>${top.map(a=>`<p>${esc(a[0])}: <b>${inr(a[1])}</b></p>`).join('')}</div><div class="card"><h3>Monthly collection</h3>${MONTHS.map((m,i)=>`<p>${m}: ${inr(RECEIVED[i])} / ${inr(BILLED[i])}</p>`).join('')}</div></div><p class="sm mu">Export includes match decisions, reasons and unresolved items.</p>`}

/* ---------- Settings / Help ---------- */
function pSettings(adm){const c=cfg(),sel=(k,o)=>`<select class="in" onchange="set('${k}',this.value)">${o.map(v=>`<option value="${v[0]}" ${c[k]===v[0]?'selected':''}>${v[1]}</option>`).join('')}</select>`;
 const common=`<label>Theme${sel('theme',[['light','Light'],['dark','Dark']])}</label><label>Language${sel('lang',[['en','English'],['hi','हिन्दी']])}</label>`;
 if(adm)return `<div class="card f"><label>Admin support email<input class="in" type="email" value="${esc(c.email)}" onchange="if(/^\\S+@\\S+\\.\\S+$/.test(this.value)){cfg().email=this.value;save();render();toast('Saved')}else toast('Email galat hai')"></label>${common}</div>`;
 return `<div class="card f">${common}<label>Font size${sel('font',[['normal','Normal'],['large','Large']])}</label><label>Currency (symbol only, no conversion)${sel('cur',[['INR','INR ₹'],['USD','USD $'],['EUR','EUR €']])}</label>
 <label>Date format${sel('datefmt',[['dmy','DD/MM/YYYY'],['mdy','MM/DD/YYYY'],['iso','YYYY-MM-DD']])}</label><label>Table density${sel('density',[['normal','Normal'],['compact','Compact']])}</label>
 <p>Home cards:</p>${['Total Bills','Money Received','Matched Bills','Pending Amount'].map((n,i)=>`<label><input type="checkbox" ${c.cards[i]?'checked':''} onchange="cfg().cards[${i}]=this.checked?1:0;save()"> ${t(n)}</label>`).join('')}
 <label><input type="checkbox" ${c.notify?'checked':''} onchange="cfg().notify=this.checked;save()"> Notifications on</label>
 <label>Business name<input class="in" value="${esc(c.biz)}" onchange="set('biz',this.value)"></label><label>WhatsApp number<input class="in" value="${esc(c.wa)}" onchange="set('wa',this.value)"></label>
 <button class="btn red" onclick="ask('Restore default settings?',()=>{const e=cfg().email;S.settings=fresh().settings;S.settings.email=e;save();render()})">${t('Restore Default Settings')}</button></div>`}
function pHelp(){const q=[['How do I upload files?','Go to Upload Files, drop your CSV/Excel file, check the preview, then click Add.'],['What does "Please check" mean?','The app found a possible match but is not sure. You decide: approve, reject, or link to another bill.'],['Why can payments not be edited?','Payments come from your bank/UPI. To fix a difference, edit the bill or link the payment to another bill.'],['How does reconciliation work?','The app compares names, amounts and dates and suggests matches. Only approved matches change balances.']];
 return `<div class="grid2"><div class="card"><h3>FAQ</h3>${q.map(a=>`<details><summary>${a[0]}</summary><p class="mu">${a[1]}</p></details>`).join('')}</div>
 <div class="card"><h3>${t('Contact Admin')}</h3><p><a href="mailto:${cfg().email}">${cfg().email}</a></p><button class="btn" onclick="contact()">✉️ ${t('Email Admin')}</button></div></div>`}
function contact(){modal(`<h3>${t('Email Admin')}</h3><div class="f"><label>Name<input class="in" id="c1"></label><label>Topic<input class="in" id="c2"></label><label>Message<textarea class="in" id="c3" rows="4"></textarea></label></div><p class="err" id="cerr"></p><button class="btn green" onclick="sendReq()">Send</button>`)}
function sendReq(){const v=[1,2,3].map(n=>$('#c'+n).value.trim());if(v.some(x=>!x))return $('#cerr').textContent='Sab fields bharein';
 S.support.unshift({id:'R'+Date.now(),name:v[0],biz:cfg().biz,topic:v[1],msg:v[2],date:TODAY,status:'Open'});save();closeModal();toast('Request saved for admin');
 location.href=`mailto:${cfg().email}?subject=${encodeURIComponent(v[1])}&body=${encodeURIComponent(v[2]+'\n\n- '+v[0]+', '+cfg().biz)}`}

/* ---------- Admin pages (view only for business data) ---------- */
function pAHome(){return `<div class="grid4">${card('🏪','Total Businesses',S.businesses.length,'')}${card('🟢','Active Today',S.businesses.filter(b=>b.status==='Active').length-1,'')}${card('✉️','Open Support Requests',S.support.filter(s=>s.status==='Open').length,'')}${card('📁','Total Files Uploaded',S.businesses.reduce((a,b)=>a+b.files,0),'')}</div><div class="card" style="max-width:640px"><h3>New businesses per month</h3><canvas id="ac" height="200"></canvas><p class="tk" id="atk"></p></div>`}
function achart(){if(typeof Chart==='undefined')return;Chart.defaults.color=cfg().theme==='dark'?'#F2F7F4':'#061F24';new Chart($('#ac'),{type:'bar',data:{labels:MONTHS,datasets:[{data:NEWBIZ,backgroundColor:'#29855F'}]},options:{scales:{y:{display:false}},plugins:{legend:{display:false}}},plugins:[{id:'n',afterDatasetsDraw(c){c.getDatasetMeta(0).data.forEach((b,i)=>{c.ctx.fillStyle=Chart.defaults.color;c.ctx.textAlign='center';c.ctx.fillText(NEWBIZ[i],b.x,b.y-4)})}}]});$('#atk').textContent=`Oct mein ${NEWBIZ[5]} naye businesses jude.`}
function pBiz(){return tbl('bizt',[{l:'Business',v:b=>b.name},{l:'Owner',v:b=>b.owner},{l:'Town/City',v:b=>b.town},{l:'Mobile',v:b=>b.mobile},{l:'Joined',v:b=>b.joined,h:b=>fd(b.joined)},{l:'Status',v:b=>b.status,h:b=>`<span class="badge ${b.status==='Active'?'b-green':'b-red'}">${b.status}</span>`},
 {l:'Action ',v:()=>'',h:b=>vb('viewBiz',b.id)+`<button class="btn s ${b.status==='Active'?'red':'green'}" onclick="togBiz('${b.id}')">${b.status==='Active'?'Disable':'Enable'}</button>`}],()=>S.businesses)}
function viewBiz(id){const b=S.businesses.find(x=>x.id===id);modal(`<h3>${esc(b.name)}</h3><p>${esc(b.owner)} · ${esc(b.town)} · ${b.mobile}<br>Joined ${fd(b.joined)} · ${b.status}<br>Files uploaded: ${b.files}</p><p class="sm mu">View only. Admin cannot edit invoices or payments.</p><button class="btn" onclick="closeModal()">OK</button>`)}
function togBiz(id){const b=S.businesses.find(x=>x.id===id);ask(`${b.status==='Active'?'Disable':'Enable'} ${esc(b.name)}?`,()=>{b.status=b.status==='Active'?'Disabled':'Active';save();render()})}
function pSupport(){return tbl('sup',[{l:'Name',v:s=>s.name},{l:'Business',v:s=>s.biz},{l:'Topic',v:s=>s.topic},{l:'Message',v:s=>s.msg},{l:'Date',v:s=>s.date,h:s=>fd(s.date)},{l:'Status',v:s=>s.status,h:s=>`<span class="badge ${s.status==='Open'?'b-amber':'b-green'}">${s.status}</span>`},
 {l:'Action ',v:()=>'',h:s=>vb('viewSup',s.id)+(s.status==='Open'?`<button class="btn green s" onclick="resolve('${s.id}')">Mark as Resolved</button>`:'')+`<a class="btn ghost s" href="mailto:?subject=${encodeURIComponent('Re: '+s.topic)}">Reply by Email</a>`}],()=>S.support)}
function viewSup(id){const s=S.support.find(x=>x.id===id);modal(`<h3>${esc(s.topic)}</h3><p>${esc(s.name)} (${esc(s.biz)}) · ${fd(s.date)}</p><p>${esc(s.msg)}</p><button class="btn" onclick="closeModal()">OK</button>`)}
function resolve(id){S.support.find(x=>x.id===id).status='Resolved';save();toast('Marked as resolved');render()}
const bizSel=()=>`<div class="row"><label>Business: <select class="in" style="width:260px">${S.businesses.map(b=>`<option>${esc(b.name)}</option>`).join('')}</select></label><span class="sm mu">Demo: every business shows the sample data. View only.</span></div>`;

/* ---------- start ---------- */
addEventListener('hashchange',render);
document.addEventListener('click',e=>{if(!e.target.closest('.dd'))document.querySelectorAll('.dd.open').forEach(x=>x.classList.remove('open'))});
render();
