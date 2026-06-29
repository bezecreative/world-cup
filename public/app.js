/* ================= MOX World Cup Bracket — frontend ================= */
const App = document.getElementById('app');
let T = null;            // tournament doc
let MM = {};             // match map
const ROUND_ORDER = ['R32','R16','QF','SF','F'];

/* ---------- tiny helpers ---------- */
const api = async (path, opts={}) => {
  const r = await fetch(path, {headers:{'Content-Type':'application/json',...(opts.headers||{})}, ...opts});
  const ct = r.headers.get('content-type')||'';
  const data = ct.includes('json') ? await r.json() : await r.text();
  if(!r.ok) throw new Error((data && data.error) || ('HTTP '+r.status));
  return data;
};
const h = (tag, attrs={}, ...kids) => {
  const e = document.createElement(tag);
  for(const [k,v] of Object.entries(attrs)){
    if(k==='class') e.className=v;
    else if(k==='html') e.innerHTML=v;
    else if(k.startsWith('on')&&typeof v==='function') e.addEventListener(k.slice(2),v);
    else if(v!==null&&v!==undefined&&v!==false) e.setAttribute(k,v);
  }
  for(let kid of kids.flat()){ if(kid==null||kid===false) continue; e.append(kid.nodeType?kid:document.createTextNode(kid)); }
  return e;
};
const teamName = c => (T.teams[c]?.name) || c || 'TBD';
const teamCode = c => c ? String(c).toUpperCase() : '—';   // 3-letter country code badge
const roundName = k => (T.rounds.find(r=>r.key===k)||{}).name || k;
const roundPts = k => (T.rounds.find(r=>r.key===k)||{}).points || 0;
const initials = n => n.trim().split(/\s+/).slice(0,2).map(s=>s[0]).join('').toUpperCase();

function toast(msg, isErr=false){
  let t = h('div',{class:'toast'+(isErr?' err':'')}, msg);
  document.body.append(t);
  requestAnimationFrame(()=>t.classList.add('show'));
  setTimeout(()=>{t.classList.remove('show');setTimeout(()=>t.remove(),300);}, isErr?3600:2200);
}
function avatar(p, size){
  const st = size?`width:${size}px;height:${size}px`:'';
  return h('div',{class:'avatar',style:st}, initials(p.name||'?'));
}

/* resolve which team is actually in a slot, given real results */
function actualSlot(slot){ return slot.team ? slot.team : (MM[slot.from] && MM[slot.from].winner) || null; }

/* ============================ ROUTER ============================ */
async function boot(){
  T = await api('/api/tournament');
  MM = {}; T.matches.forEach(m=>MM[m.id]=m);
  document.getElementById('liveflag').textContent = T.locked ? 'Brackets locked' : 'Brackets open';
  window.addEventListener('hashchange', route);
  let _rt; window.addEventListener('resize', ()=>{ clearTimeout(_rt);
    _rt=setTimeout(()=>{ if(_redrawBracket) _redrawBracket(); }, 120); });
  route();
}
function setActive(){
  const cur = location.hash || '#/';
  document.querySelectorAll('#navlinks a').forEach(a=>{
    a.classList.toggle('active', a.getAttribute('data-route')===cur);
    if(!a.onclick) a.addEventListener('click',e=>{e.preventDefault();location.hash=a.getAttribute('data-route');});
  });
}
async function route(){
  const hash = location.hash || '#/';
  setActive();
  window.scrollTo(0,0);
  _redrawBracket = null;   // drop any stale bracket from the previous view
  try{
    if(hash.startsWith('#/build')) return renderBuild();
    if(hash.startsWith('#/players')) return renderBrackets();
    if(hash.startsWith('#/player/')) return renderPlayer(hash.split('/')[2]);
    if(hash.startsWith('#/bracket')) return renderTournamentBracket();
    if(hash.startsWith('#/admin')) return renderAdmin();
    return renderLeaderboard();
  }catch(e){ App.innerHTML=''; App.append(h('div',{class:'wrap'}, h('div',{class:'empty'}, 'Error: '+e.message))); }
}

/* ========================= LEADERBOARD ========================= */
async function renderLeaderboard(){
  const {players} = await api('/api/leaderboard');
  const decidedAny = T.matches.some(m=>m.winner);
  App.innerHTML='';
  const hero = h('section',{class:'hero'},
    h('span',{class:'kick'}, h('span',{class:'dot'}), T.locked?'Tournament underway':'Picks are open'),
    h('h1',{}, 'Who calls the ', h('span',{class:'em'},'Cup'), '?'),
    h('p',{}, T.subtitle+'. Build your bracket, lock it in, and climb the board as the real results roll in. Bragging rights are non-refundable.'),
    h('div',{class:'actions'},
      h('button',{class:'btn primary lg', onclick:()=>location.hash='#/build'}, 'Build your bracket'),
      h('button',{class:'btn lg', onclick:()=>location.hash='#/bracket'}, 'View the bracket'),
      h('button',{class:'btn lg', onclick:()=>location.hash='#/players'}, 'Everyone’s picks'),
    )
  );
  const wrap = h('div',{class:'wrap'});
  wrap.append(hero);
  wrap.append(h('div',{class:'shead'}, h('h2',{},'Leaderboard'),
    h('span',{class:'sub'}, players.length+' '+(players.length===1?'player':'players')+(decidedAny?' · live scoring':' · waiting for results'))));
  if(!players.length){
    wrap.append(h('div',{class:'empty'}, h('div',{},'No brackets yet — be the first to lock one in.'),
      h('div',{style:'margin-top:16px'}, h('button',{class:'btn primary',onclick:()=>location.hash='#/build'},'Build your bracket'))));
  } else {
    const lb = h('div',{class:'lb'});
    players.forEach(p=>{
      const dead = !p.champion_alive && !p.champion_correct;
      lb.append(h('div',{class:'lbrow top'+(p.rank<=3?p.rank:''), onclick:()=>location.hash='#/player/'+p.id},
        h('div',{class:'rank'}, p.rank),
        avatar(p),
        h('div',{class:'who'},
          h('div',{class:'nm'}, p.name),
          h('div',{class:'meta'},
            h('span',{class:'chip'+(dead?' dead':'')}, teamCode(p.champion),' ', teamName(p.champion)),
            h('span',{class:'chip'}, p.correct+' correct'),
            p.champion_correct?h('span',{class:'chip'},'champ won')
              :(dead?h('span',{class:'chip dead'},'champ out'):h('span',{class:'chip'},'champ alive')),
          )
        ),
        h('div',{class:'pts'},
          h('div',{class:'n'}, p.points),
          h('div',{class:'l'},'points'),
          h('div',{class:'max'}, 'max '+p.max_possible),
        )
      ));
    });
    wrap.append(lb);
  }
  App.append(wrap);
}

/* ========================= BRACKETS GALLERY ========================= */
async function renderBrackets(){
  const {players} = await api('/api/leaderboard');
  App.innerHTML='';
  const wrap = h('div',{class:'wrap'});
  wrap.append(h('div',{class:'shead'}, h('h2',{},'Everyone’s brackets'),
    h('span',{class:'sub'},'Tap a card to open the full bracket')));
  if(!players.length){
    wrap.append(h('div',{class:'empty'}, 'No brackets yet.'));
  } else {
    const grid = h('div',{class:'grid-cards'});
    players.forEach(p=>{
      grid.append(h('div',{class:'pcard',onclick:()=>location.hash='#/player/'+p.id},
        h('div',{class:'top'}, avatar(p,44),
          h('div',{}, h('div',{class:'nm'},p.name), h('div',{class:'sm'},'Rank #'+p.rank))),
        h('div',{class:'stat'}, h('span',{},'Points'), h('b',{},String(p.points))),
        h('div',{class:'stat'}, h('span',{},'Correct picks'), h('b',{},String(p.correct))),
        h('div',{class:'champ'}, h('span',{class:'fl'},teamCode(p.champion)),
          h('span',{}, 'Champion · ', h('b',{style:'color:var(--text)'},teamName(p.champion)))),
      ));
    });
    wrap.append(grid);
  }
  App.append(wrap);
}

/* ========================= PLAYER BRACKET VIEW ========================= */
async function renderPlayer(id){
  const p = await api('/api/players/'+id);
  const picks = p.picks;
  App.innerHTML='';
  const wrap = h('div',{class:'wrap'});
  wrap.append(h('button',{class:'linkbtn',onclick:()=>history.length>1?history.back():location.hash='#/'},'← Back'));
  const s = p.score;
  wrap.append(h('div',{class:'shead',style:'margin-top:10px'},
    h('div',{style:'display:flex;align-items:center;gap:16px'},
      avatar(p,58),
      h('div',{}, h('h2',{},p.name),
        h('div',{class:'sub',style:'margin-top:3px'}, s.points+' pts · '+s.correct+' correct · champion pick '+teamName(p.champion)))),
    h('div',{class:'sub'}, 'max possible '+s.max_possible)
  ));
  wrap.append(traditionalBracket(picks, {showResult:true}));
  App.append(wrap);
}

/* ===================== TRADITIONAL BRACKET (with connectors) =====================
   picks = {matchId:teamCode}; mode = {showResult, official}.
   Renders round columns with each match centered between its feeders, then draws
   SVG elbow connectors child->parent (winner paths highlighted in brand red). */
const SVGNS = 'http://www.w3.org/2000/svg';
function svgEl(tag, attrs){ const e=document.createElementNS(SVGNS,tag);
  for(const k in attrs) e.setAttribute(k, attrs[k]); return e; }

/* match id -> the match it feeds into ('CHAMP' for the final) */
function parentMap(){
  const pm = {};
  T.matches.forEach(p=>{
    [p.a,p.b].forEach(s=>{ if(s.from) pm[s.from]=p.id; });
  });
  pm['M31'] = 'CHAMP';
  return pm;
}

function bracketCard(m, picks, mode){
  const pick = picks[m.id];
  const ta = predictedSlot(m.a, picks), tb = predictedSlot(m.b, picks);
  const card = h('div',{class:'tb-card','data-mid':m.id});
  [ta,tb].forEach(code=>{
    let cls='bteam', mk='';
    if(mode.official){
      if(m.winner){ cls = (code===m.winner) ? 'bteam win' : 'bteam wrong'; }
    } else {
      if(code && code===pick) cls+=' win';
      if(mode.showResult && m.winner && code===pick){
        cls = code===m.winner ? 'bteam correct' : 'bteam win'; mk = code===m.winner?('+'+roundPts(m.round)):'';
      }
    }
    card.append(h('div',{class:cls},
      h('span',{class:'fl'}, code?teamCode(code):'·'),
      h('span',{class:'nm'}, code?teamName(code):'TBD'),
      mk?h('span',{class:'mk'},mk):null));
  });
  return card;
}

function traditionalBracket(picks, mode){
  mode = mode || {};
  const scroll = h('div',{class:'tb-scroll'});
  const inner = h('div',{class:'tbracket'});
  const svg = svgEl('svg',{class:'tb-lines'});
  const cols = h('div',{class:'tb-cols'});
  const r32n = T.matches.filter(m=>m.round==='R32').length;
  const height = Math.max(460, r32n * 84);
  cols.style.height = height + 'px';

  ROUND_ORDER.forEach(rk=>{
    const col = h('div',{class:'tb-col'});
    col.append(h('div',{class:'rname'}, rk==='F'?'Final':roundName(rk)));
    const body = h('div',{class:'tb-body'});
    T.matches.filter(m=>m.round===rk).forEach(m=> body.append(bracketCard(m, picks, mode)));
    col.append(body);
    cols.append(col);
  });
  // champion column
  const champ = picks['M31'], champWin = MM['M31'].winner;
  let ccls = champ ? 'bteam win' : 'bteam';
  if(mode.showResult && champWin) ccls = champ===champWin ? 'bteam correct':'bteam wrong';
  if(mode.official && champWin) ccls = 'bteam win';
  const champCol = h('div',{class:'tb-col'});
  champCol.append(h('div',{class:'rname'},'Champion'));
  const champBody = h('div',{class:'tb-body'});
  champBody.append(h('div',{class:'tb-card','data-mid':'CHAMP'},
    h('div',{class:ccls,style:'padding:11px'},
      h('span',{class:'fl'},teamCode(champ)), h('span',{class:'nm'},teamName(champ)))));
  champCol.append(champBody);
  cols.append(champCol);

  inner.append(svg, cols);
  scroll.append(inner);

  const draw = ()=>drawBracketLines(inner, svg);
  _redrawBracket = draw;
  // rAF for the common case + setTimeout fallbacks (rAF is throttled in
  // background/offscreen tabs; the later timer also catches late font/emoji layout)
  requestAnimationFrame(()=>requestAnimationFrame(draw));
  setTimeout(draw, 80);
  setTimeout(draw, 320);
  return scroll;
}

function drawBracketLines(inner, svg){
  if(!inner.isConnected) return;
  const base = inner.getBoundingClientRect();
  const W = inner.offsetWidth, H = inner.offsetHeight;
  svg.setAttribute('width', W); svg.setAttribute('height', H);
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  while(svg.firstChild) svg.removeChild(svg.firstChild);
  const pos = {};
  inner.querySelectorAll('.tb-card').forEach(c=>{
    const r = c.getBoundingClientRect();
    pos[c.getAttribute('data-mid')] = {
      l: r.left-base.left, r: r.right-base.left, cy: r.top-base.top + r.height/2 };
  });
  const pm = parentMap();
  T.matches.forEach(m=>{
    const par = pm[m.id]; if(!par) return;
    const a = pos[m.id], b = pos[par]; if(!a||!b) return;
    const midX = (a.r + b.l) / 2;
    const d = `M ${a.r} ${a.cy} H ${midX} V ${b.cy} H ${b.l}`;
    const lit = !!m.winner; // this matchup is decided -> highlight the path
    svg.append(svgEl('path',{ d, class: 'tb-line' + (lit?' lit':'') }));
  });
}

let _redrawBracket = null;

/* ===================== OFFICIAL TOURNAMENT BRACKET ===================== */
async function renderTournamentBracket(){
  await refreshT();           // pull the latest real results
  const actual = {};
  T.matches.forEach(m=>{ if(m.winner) actual[m.id]=m.winner; });
  const decided = T.matches.filter(m=>m.winner).length;
  App.innerHTML='';
  const wrap = h('div',{class:'wrap'});
  wrap.append(h('div',{class:'shead'},
    h('h2',{},'The bracket'),
    h('span',{class:'sub'}, decided+' / '+T.matches.length+' games decided')));
  wrap.append(h('p',{class:'muted',style:'margin:-8px 0 18px'},
    decided ? 'The real tournament — winners advance as results come in.'
            : 'The full Round of 32. Winners will fill in here as results come in.'));
  wrap.append(traditionalBracket(actual, {official:true}));
  App.append(wrap);
}
/* slot resolved by the player's own bracket picks */
function predictedSlot(slot, picks){ return slot.team ? slot.team : picks[slot.from] || null; }

/* ============================ BUILDER ============================ */
let B = null;
function renderBuild(){
  if(T.locked){
    App.innerHTML='';
    App.append(h('div',{class:'wrap'}, h('div',{class:'empty'},
      'Brackets are locked — the tournament has already kicked off.',
      h('div',{style:'margin-top:14px'}, h('button',{class:'btn',onclick:()=>location.hash='#/'},'View the leaderboard')))));
    return;
  }
  B = {step:0, name:'', picks:{}, tiebreak:''};
  drawBuild();
}
const buildSteps = () => ['name', ...T.matches.map(m=>m.id), 'review'];
function pickCount(){ return Object.keys(B.picks).length; }

function drawBuild(){
  const steps = buildSteps();
  const key = steps[B.step];
  App.innerHTML='';
  const wrap = h('div',{class:'wrap'});
  const inner = h('div',{class:'builder'});

  // progress across name + each round
  const prog = h('div',{class:'progress'});
  ['name','R32','R16','QF','SF','F'].forEach((seg)=>{
    let cls='seg';
    if(seg==='name'){ if(B.name) cls+=' done'; if(key==='name') cls+=' cur'; }
    else { // rounds
      const ms = T.matches.filter(m=>m.round===seg);
      const done = ms.every(m=>B.picks[m.id]);
      const cur = MM[key] && MM[key].round===seg;
      if(done) cls+=' done'; if(cur) cls+=' cur';
    }
    prog.append(h('div',{class:cls}));
  });
  inner.append(prog);

  if(key==='name') inner.append(stepName());
  else if(key==='review') inner.append(stepReview());
  else inner.append(stepMatch(key));

  wrap.append(inner);
  App.append(wrap);
}

function stepName(){
  const s = h('div',{class:'step'});
  s.append(h('h2',{style:'font-size:clamp(28px,5vw,46px);text-align:center;margin-bottom:8px'},'Let’s build your bracket'),
    h('p',{class:'muted',style:'text-align:center;margin:0 auto 30px;max-width:420px'},'First — who’s making these bold predictions?'));
  const input = h('input',{class:'input',type:'text',maxlength:'40',placeholder:'Your name',value:B.name,
    style:'text-align:center;font-size:24px',
    oninput:e=>{B.name=e.target.value; next.disabled=!B.name.trim();}});
  s.append(h('div',{class:'field'}, input));
  const next = h('button',{class:'btn primary lg',style:'width:100%',disabled:!B.name.trim(),
    onclick:()=>{ if(B.name.trim()){B.step++;drawBuild();} }}, 'Continue →');
  s.append(next);
  setTimeout(()=>input.focus(),50);
  input.addEventListener('keydown',e=>{if(e.key==='Enter'&&B.name.trim()){B.step++;drawBuild();}});
  return s;
}

function stepMatch(mid){
  const m = MM[mid];
  const ta = predictedSlot(m.a, B.picks), tb = predictedSlot(m.b, B.picks);
  const idxInRound = T.matches.filter(x=>x.round===m.round).findIndex(x=>x.id===mid)+1;
  const totalRound = T.matches.filter(x=>x.round===m.round).length;
  const s = h('div',{class:'step matchwrap'});
  s.append(h('div',{class:'match-round'}, roundName(m.round)+(m.round==='F'?'':' · '+roundPts(m.round)+' pt'+(roundPts(m.round)>1?'s':'')+' each')),
    h('div',{class:'match-count'}, m.round==='F'?'Pick your champion':('Match '+idxInRound+' of '+totalRound)));
  const grid = h('div',{class:'vs-grid'});
  const card = (code)=>{
    if(!code) return h('div',{class:'teamcard tbd'}, h('div',{class:'fl'},'—'), h('div',{class:'tn'},'TBD'));
    const picked = B.picks[mid]===code;
    return h('div',{class:'teamcard'+(picked?' picked':''), onclick:()=>choose(mid,code)},
      h('div',{class:'check'}),
      h('div',{class:'fl'}, teamCode(code)),
      h('div',{class:'tn'}, teamName(code)),
      h('div',{class:'tag'}, m.round==='F'?'Champion':'Advances'));
  };
  grid.append(card(ta), h('div',{class:'vs-mid'},'VS'), card(tb));
  s.append(grid);

  s.append(h('div',{class:'builder-nav'},
    h('button',{class:'linkbtn',onclick:()=>{B.step--;drawBuild();}},'← Back'),
    h('div',{class:'muted',style:'font-size:13px'}, pickCount()+' / '+T.matches.length+' picked'),
    h('button',{class:'linkbtn',disabled:!B.picks[mid],onclick:()=>advance()}, B.picks[mid]?'Next →':'Pick one')
  ));
  return s;
}

function choose(mid, code){
  const prev = B.picks[mid];
  if(prev!==code){
    B.picks[mid]=code;
    // clear any downstream picks (later matches) that depended on this result
    const num = parseInt(mid.slice(1));
    Object.keys(B.picks).forEach(k=>{ if(parseInt(k.slice(1))>num) delete B.picks[k]; });
  }
  // visual feedback then advance
  drawBuild();
  if(MM[mid].round==='F'){ celebrate(code); }
  else {
    // cancelable, step-guarded auto-advance so a manual "Next" can't double-skip
    if(B._adv) clearTimeout(B._adv);
    const at = B.step;
    B._adv = setTimeout(()=>{ if(B.step===at) advance(); }, 360);
  }
}
function advance(){
  if(B._adv){ clearTimeout(B._adv); B._adv=null; }
  if(B.step < buildSteps().length-1){ B.step++; drawBuild(); }
}

function stepReview(){
  const s = h('div',{class:'step'});
  const champ = B.picks['M31'];
  s.append(h('div',{class:'champ-splash'},
    h('div',{class:'lbl'},'Your champion'),
    h('div',{class:'fl'}, teamCode(champ)),
    h('div',{class:'nm'}, teamName(champ))));
  s.append(h('p',{class:'muted',style:'text-align:center;margin:6px auto 22px'},'Here’s the bracket you’re locking in:'));
  s.append(traditionalBracket(B.picks, {}));

  s.append(h('div',{class:'field',style:'max-width:340px;margin:24px auto 0'},
    h('label',{},'Tiebreaker — total goals in the final'),
    h('input',{class:'input',type:'number',min:'0',max:'20',placeholder:'e.g. 3',value:B.tiebreak,
      style:'text-align:center', oninput:e=>B.tiebreak=e.target.value})));

  const submit = h('button',{class:'btn primary lg',style:'width:100%;max-width:340px;margin:18px auto 0;display:block',
    onclick:doSubmit}, 'Lock in my bracket');
  s.append(submit);
  s.append(h('div',{style:'text-align:center;margin-top:10px'},
    h('button',{class:'linkbtn',onclick:()=>{B.step--;drawBuild();}},'← Back to edit')));
  return s;
}

async function doSubmit(){
  if(pickCount()!==T.matches.length){ toast('Finish every matchup first',true); return; }
  try{
    const res = await api('/api/players',{method:'POST',body:JSON.stringify({
      name:B.name, picks:B.picks, tiebreak:parseInt(B.tiebreak)||0
    })});
    bigConfetti();
    toast('Bracket locked in.');
    setTimeout(()=>location.hash='#/player/'+res.id, 900);
  }catch(e){ toast(e.message, true); }
}

/* ============================ ADMIN ============================ */
let ADMIN_PW = sessionStorage.getItem('mox_admin')||'';
async function renderAdmin(){
  App.innerHTML='';
  const wrap = h('div',{class:'wrap'});
  wrap.append(h('div',{class:'shead'}, h('h2',{},'Admin · results & control'),
    h('span',{class:'sub'}, T.locked?'Brackets LOCKED':'Brackets open')));

  const pwRow = h('div',{class:'panel',style:'margin-bottom:18px;display:flex;gap:10px;align-items:center;flex-wrap:wrap'},
    h('span',{class:'muted'},'Admin password:'),
    h('input',{class:'input',type:'password',value:ADMIN_PW,placeholder:'password',style:'max-width:200px;padding:10px 14px;font-size:15px',
      oninput:e=>{ADMIN_PW=e.target.value;sessionStorage.setItem('mox_admin',ADMIN_PW);}}),
    h('div',{style:'flex:1'}),
    h('button',{class:'btn',onclick:doSync},'Sync live results'),
    h('button',{class:'btn',onclick:toggleLock}, T.locked?'Unlock brackets':'Lock brackets'),
    h('button',{class:'btn',onclick:resetResults},'Clear all results'),
  );
  wrap.append(pwRow);

  // matches grouped by round, only show those whose both teams are decided
  ROUND_ORDER.forEach(rk=>{
    const ms = T.matches.filter(m=>m.round===rk);
    const panel = h('div',{class:'panel',style:'margin-bottom:14px'});
    panel.append(h('h3',{style:'font-size:18px;margin-bottom:6px'}, roundName(rk),
      h('span',{class:'sub',style:'font-weight:300;margin-left:8px'}, roundPts(rk)+' pts each')));
    ms.forEach(m=>{
      const ta = actualSlot(m.a), tb = actualSlot(m.b);
      const row = h('div',{class:'admin-match'});
      row.append(h('div',{class:'mid'}, m.id));
      [[ta,m.a],[tb,m.b]].forEach(([code])=>{
        const ready = !!code;
        row.append(h('button',{class:'tbtn'+(m.winner===code&&code?' on':''),disabled:!ready,
          onclick:()=>setResult(m.id, m.winner===code?null:code)},
          ready?h('span',{},teamCode(code)):'', ready?teamName(code):'awaiting…'));
      });
      panel.append(row);
    });
    wrap.append(panel);
  });
  App.append(wrap);
}
const adminHeaders = () => ({'X-Admin-Password':ADMIN_PW});
async function setResult(match, winner){
  try{ await api('/api/admin/result',{method:'POST',headers:adminHeaders(),body:JSON.stringify({match,winner})});
    await refreshT(); renderAdmin(); toast('Result saved'); }
  catch(e){ toast(e.message,true); }
}
async function toggleLock(){
  try{ const r=await api('/api/admin/lock',{method:'POST',headers:adminHeaders(),body:JSON.stringify({locked:!T.locked})});
    await refreshT(); renderAdmin(); toast(r.locked?'Brackets locked':'Brackets unlocked'); }
  catch(e){ toast(e.message,true); }
}
async function resetResults(){
  if(!confirm('Clear ALL match results? Player brackets stay; scores reset to zero.')) return;
  try{ await api('/api/admin/reset-results',{method:'POST',headers:adminHeaders(),body:'{}'});
    await refreshT(); renderAdmin(); toast('Results cleared'); }
  catch(e){ toast(e.message,true); }
}
async function doSync(){
  try{ const r=await api('/api/admin/sync',{method:'POST',headers:adminHeaders(),body:'{}'});
    if(!r.ok){ toast(r.error||'Sync unavailable',true); return; }
    await refreshT(); renderAdmin(); toast('Synced — '+r.updated+' result'+(r.updated===1?'':'s')+' updated'); }
  catch(e){ toast(e.message,true); }
}
async function refreshT(){ T = await api('/api/tournament'); MM={}; T.matches.forEach(m=>MM[m.id]=m);
  document.getElementById('liveflag').textContent = T.locked?'Brackets locked':'Brackets open'; }

/* ============================ utils: confetti ============================ */
function celebrate(code){
  // little burst when champion picked on the final step
  bigConfetti(28);
}
function bigConfetti(n=70){
  const colors=['#B91800','#E5320F','#D9794E','#F2C14E','#EDE6DA'];
  for(let i=0;i<n;i++){
    const c=h('div',{class:'confetti'});
    c.style.background=colors[i%colors.length];
    c.style.left=(50+(Math.random()*40-20))+'vw';
    c.style.top='-20px';
    c.style.borderRadius=Math.random()>.5?'50%':'2px';
    document.body.append(c);
    const dx=(Math.random()*2-1)*40, dur=1400+Math.random()*1200, rot=Math.random()*720;
    c.animate([{transform:'translate(0,0) rotate(0)',opacity:1},
      {transform:`translate(${dx}vw,110vh) rotate(${rot}deg)`,opacity:.9}],
      {duration:dur,easing:'cubic-bezier(.2,.6,.4,1)'}).onfinish=()=>c.remove();
  }
}

boot();
