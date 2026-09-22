// VisaCal 관리자. admin.visacal.com
// 구글 로그인(ID 토큰) → 허용 이메일 확인 → GitHub에 글과 이미지를 커밋합니다.
// 필요한 설정
//   vars:    GOOGLE_CLIENT_ID, ALLOWED_EMAILS(쉼표 구분), GITHUB_REPO, GITHUB_BRANCH
//   secret:  GITHUB_TOKEN  (visacal 레포 Contents read/write 권한만 가진 fine-grained 토큰)

const POSTS_DIR = 'content/posts';
const UPLOAD_DIR = 'docs/uploads';
const JWKS_URL = 'https://www.googleapis.com/oauth2/v3/certs';
let jwksCache = { keys: null, exp: 0 };

// ---------------------------------------------------------------- 인증

const b64urlToBytes = (s) => {
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  while (s.length % 4) s += '=';
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
};
const b64urlToJson = (s) => JSON.parse(new TextDecoder().decode(b64urlToBytes(s)));

async function getJwks() {
  if (jwksCache.keys && Date.now() < jwksCache.exp) return jwksCache.keys;
  const res = await fetch(JWKS_URL);
  const data = await res.json();
  jwksCache = { keys: data.keys, exp: Date.now() + 3600 * 1000 };
  return data.keys;
}

async function verifyGoogle(token, env) {
  const parts = (token || '').split('.');
  if (parts.length !== 3) throw new Error('토큰 형식 오류');
  const header = b64urlToJson(parts[0]);
  const payload = b64urlToJson(parts[1]);
  const jwk = (await getJwks()).find((k) => k.kid === header.kid);
  if (!jwk) throw new Error('서명 키 없음');
  const key = await crypto.subtle.importKey(
    'jwk', jwk, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify'],
  );
  const ok = await crypto.subtle.verify(
    'RSASSA-PKCS1-v1_5', key, b64urlToBytes(parts[2]),
    new TextEncoder().encode(`${parts[0]}.${parts[1]}`),
  );
  if (!ok) throw new Error('서명 불일치');
  if (!['accounts.google.com', 'https://accounts.google.com'].includes(payload.iss)) throw new Error('발급자 불일치');
  if (payload.aud !== env.GOOGLE_CLIENT_ID) throw new Error('대상 불일치');
  if (payload.exp * 1000 < Date.now()) throw new Error('토큰 만료');
  if (!payload.email_verified) throw new Error('이메일 미인증');
  const allowed = (env.ALLOWED_EMAILS || '').split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
  const email = String(payload.email || '').toLowerCase();
  if (!allowed.includes(email)) throw new Error(`허용되지 않은 계정: ${email}`);
  return { email, name: payload.name || email };
}

// ---------------------------------------------------------------- GitHub

function gh(env, path, init = {}) {
  return fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'visacal-admin',
      'X-GitHub-Api-Version': '2022-11-28',
      ...(init.headers || {}),
    },
  });
}

const utf8ToB64 = (s) => {
  const bytes = new TextEncoder().encode(s);
  let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
};
const b64ToUtf8 = (s) => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g, '')), (c) => c.charCodeAt(0)));

async function putFile(env, path, contentB64, message, sha) {
  const res = await gh(env, `contents/${encodeURI(path)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, content: contentB64, branch: env.GITHUB_BRANCH || 'main', ...(sha ? { sha } : {}) }),
  });
  if (!res.ok) throw new Error(`GitHub 저장 실패 ${res.status}: ${(await res.text()).slice(0, 200)}`);
  return res.json();
}

// ---------------------------------------------------------------- 글 형식

const q = (v) => JSON.stringify(String(v ?? ''));

function toMarkdown(m) {
  return [
    '---',
    `title: ${q(m.title)}`,
    `slug: ${q(m.slug)}`,
    `date: ${m.date}`,
    `category: ${q(m.category || '뉴스')}`,
    `summary: ${q(m.summary)}`,
    `cover: ${q(m.cover)}`,
    `draft: ${m.draft ? 'true' : 'false'}`,
    ...(m.publish_at ? [`publish_at: ${q(m.publish_at)}`] : []),
    '---',
    '',
    (m.body || '').trim(),
    '',
  ].join('\n');
}

function parseMarkdown(text) {
  const m = text.match(/^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/);
  const meta = {};
  if (m) {
    for (const line of m[1].split('\n')) {
      const i = line.indexOf(':');
      if (i < 0) continue;
      const k = line.slice(0, i).trim();
      let v = line.slice(i + 1).trim();
      if (v.startsWith('"')) { try { v = JSON.parse(v); } catch {} }
      else if (v.startsWith("'") && v.endsWith("'")) v = v.slice(1, -1);
      if (v === 'true') v = true; else if (v === 'false') v = false;
      meta[k] = v;
    }
  }
  return { ...meta, body: m ? m[2].trim() : text };
}

const cleanSlug = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'post';

// ---------------------------------------------------------------- API

const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' },
});

async function api(request, env, url) {
  let user;
  try {
    user = await verifyGoogle((request.headers.get('Authorization') || '').replace(/^Bearer\s+/i, ''), env);
  } catch (e) {
    return json({ error: e.message }, 401);
  }
  const who = `${user.name} <${user.email}>`;

  if (url.pathname === '/api/me') return json(user);

  if (url.pathname === '/api/posts' && request.method === 'GET') {
    const res = await gh(env, `contents/${POSTS_DIR}?ref=${env.GITHUB_BRANCH || 'main'}`);
    if (res.status === 404) return json([]);
    const files = (await res.json()).filter((f) => f.name.endsWith('.md'));
    files.sort((a, b) => b.name.localeCompare(a.name));
    return json(files.map((f) => ({ path: f.path, name: f.name, sha: f.sha })));
  }

  if (url.pathname === '/api/post' && request.method === 'GET') {
    const path = url.searchParams.get('path') || '';
    if (!path.startsWith(`${POSTS_DIR}/`)) return json({ error: '잘못된 경로' }, 400);
    const res = await gh(env, `contents/${encodeURI(path)}?ref=${env.GITHUB_BRANCH || 'main'}`);
    if (!res.ok) return json({ error: '글을 찾을 수 없음' }, 404);
    const f = await res.json();
    return json({ path: f.path, sha: f.sha, ...parseMarkdown(b64ToUtf8(f.content)) });
  }

  if (url.pathname === '/api/post' && request.method === 'POST') {
    const m = await request.json();
    if (!m.title || !m.date) return json({ error: '제목과 게시일은 필수입니다' }, 400);
    m.slug = cleanSlug(m.slug || m.title);
    const path = m.path && m.path.startsWith(`${POSTS_DIR}/`) ? m.path : `${POSTS_DIR}/${m.date}-${m.slug}.md`;
    const r = await putFile(env, path, utf8ToB64(toMarkdown(m)),
      `post: ${m.slug} ${m.sha ? '수정' : '작성'} (${who})`, m.sha);
    return json({ path, sha: r.content.sha });
  }

  if (url.pathname === '/api/post' && request.method === 'DELETE') {
    const { path, sha } = await request.json();
    if (!path?.startsWith(`${POSTS_DIR}/`) || !sha) return json({ error: '잘못된 요청' }, 400);
    const res = await gh(env, `contents/${encodeURI(path)}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: `post: 삭제 ${path} (${who})`, sha, branch: env.GITHUB_BRANCH || 'main' }),
    });
    if (!res.ok) return json({ error: `삭제 실패 ${res.status}` }, 500);
    return json({ ok: true });
  }

  if (url.pathname === '/api/upload' && request.method === 'POST') {
    const { name, data } = await request.json();
    const ext = (String(name).match(/\.(png|jpe?g|gif|webp|svg)$/i) || [])[1];
    if (!ext || !data) return json({ error: '이미지 파일만 올릴 수 있습니다' }, 400);
    if (data.length > 7_000_000) return json({ error: '5MB 이하 이미지만 올릴 수 있습니다' }, 400);
    const stamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
    const base = cleanSlug(String(name).replace(/\.[^.]+$/, '')).slice(0, 40);
    const path = `${UPLOAD_DIR}/${stamp}-${base}.${ext.toLowerCase()}`;
    await putFile(env, path, data, `media: ${path} 업로드 (${who})`);
    return json({ url: path.replace(/^docs/, '') });
  }

  if (url.pathname === '/api/fees' && request.method === 'GET') {
    const res = await gh(env, `contents/data/fees.json?ref=${env.GITHUB_BRANCH || 'main'}`);
    if (!res.ok) return json({ error: '원장을 불러오지 못했습니다' }, 500);
    const f = await res.json();
    return json({ sha: f.sha, data: JSON.parse(b64ToUtf8(f.content)) });
  }

  if (url.pathname === '/api/fees' && request.method === 'PUT') {
    const { sha, fees } = await request.json();
    if (!Array.isArray(fees)) return json({ error: '잘못된 요청' }, 400);
    const res = await gh(env, `contents/data/fees.json?ref=${env.GITHUB_BRANCH || 'main'}`);
    const cur = await res.json();
    if (cur.sha !== sha) return json({ error: '그 사이 자동 감시가 원장을 갱신했습니다. 새로고침 후 다시 저장하십시오.' }, 409);
    const data = JSON.parse(b64ToUtf8(cur.content));
    const byId = Object.fromEntries(fees.map((f) => [f.fee_id, f]));
    for (const f of data.fees) {
      const u = byId[f.fee_id];
      if (!u) continue;
      const amt = u.amount === '' || u.amount === null ? null : Number(u.amount);
      if (amt !== f.amount) { f.prev_amount = f.amount; f.amount = Number.isFinite(amt) ? amt : null; }
      f.status = u.status || f.status;
      f.effective_date = u.effective_date || null;
      f.basis = u.basis ?? f.basis;
      delete f.pending_update;
    }
    data.updated_at = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
    const r = await putFile(env, 'data/fees.json', utf8ToB64(JSON.stringify(data, null, 2) + '\n'),
      `fees: 원장 수정 (${who})`, cur.sha);
    return json({ sha: r.content.sha });
  }

  return json({ error: 'not found' }, 404);
}

// ---------------------------------------------------------------- 화면

const PAGE = (clientId) => `<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>VisaCal 관리자</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<script src="https://accounts.google.com/gsi/client" async></script>
<style>
:root{--ink:#14243c;--muted:#6b7688;--faint:#98a1b0;--rule:#d8dee7;--hair:#e8ecf1;--ground:#eef1f5;--paper:#fff;--warn:#9b2226;--ok:#1f6b45}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:Pretendard,'Apple SD Gothic Neo',system-ui,sans-serif;font-size:15px;line-height:1.55}
.top{display:flex;justify-content:space-between;align-items:center;padding:14px 22px;background:var(--paper);border-bottom:2px solid var(--ink)}
.top b{font-size:17px;letter-spacing:-.02em}
.top span{color:var(--muted);font-size:13px}
.top a{color:var(--muted);font-size:13px;margin-left:14px}
.login{max-width:380px;margin:12vh auto;background:var(--paper);border:1px solid var(--rule);border-top:3px solid var(--ink);padding:30px;text-align:center}
.login h1{font-size:19px;margin:0 0 6px}.login p{color:var(--muted);font-size:13.5px;margin:0 0 22px}
.wrap{display:grid;grid-template-columns:280px minmax(0,1fr);gap:22px;max-width:1180px;margin:22px auto;padding:0 20px}
.side,.editor{background:var(--paper);border:1px solid var(--rule)}
.side h2,.editor h2{font-size:13px;color:var(--muted);font-weight:600;margin:0;padding:14px 16px;border-bottom:1px solid var(--hair);display:flex;justify-content:space-between;align-items:center}
.side ul{list-style:none;margin:0;padding:0;max-height:70vh;overflow:auto}
.side li{padding:11px 16px;border-bottom:1px solid var(--hair);cursor:pointer;font-size:13.5px}
.side li:hover,.side li.on{background:#f4f6f9}
.side li small{display:block;color:var(--faint);font-size:12px}
.editor form{padding:18px 20px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
label{display:block;font-size:12.5px;color:var(--muted);margin:12px 0 5px}
input[type=text],input[type=date],select,textarea{width:100%;border:1px solid var(--rule);padding:9px 10px;font:inherit;font-size:14px;border-radius:2px;background:var(--paper);color:var(--ink)}
textarea{resize:vertical}
#body{min-height:340px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13.5px;line-height:1.6}
.cover{display:flex;gap:12px;align-items:center}
.cover img{width:120px;height:80px;object-fit:cover;border:1px solid var(--rule);display:none}
.btn{border:1px solid var(--ink);background:var(--paper);color:var(--ink);padding:9px 16px;font:inherit;font-size:14px;cursor:pointer;border-radius:2px}
.btn.solid{background:var(--ink);color:#fff}.btn.danger{border-color:var(--warn);color:var(--warn)}
.btn:disabled{opacity:.5;cursor:wait}
.bar{display:flex;gap:8px;align-items:center;margin-top:18px;padding-top:16px;border-top:1px solid var(--hair)}
.bar .sp{flex:1}
.msg{font-size:13px;margin-left:6px}.msg.ok{color:var(--ok)}.msg.err{color:var(--warn)}
.tools{display:flex;gap:6px;margin:6px 0}
.tools button{border:1px solid var(--rule);background:var(--paper);font:inherit;font-size:12.5px;padding:4px 9px;cursor:pointer;border-radius:2px}
.chk{display:flex;gap:6px;align-items:center;margin-top:12px;font-size:13.5px}
@media(max-width:820px){.wrap{grid-template-columns:1fr}.row{grid-template-columns:1fr}}
</style></head><body>
<div class="top"><b>VisaCal 관리자</b><div><a href="#" id="tab-posts" style="display:none">글</a><a href="#" id="tab-fees" style="display:none">수수료 원장</a><span id="who" style="margin-left:14px"></span><a href="https://visacal.com/guides.html" target="_blank">사이트 보기</a><a href="#" id="logout" style="display:none">로그아웃</a></div></div>

<div class="login" id="login">
  <h1>로그인</h1>
  <p>허용된 구글 계정만 들어올 수 있습니다.</p>
  <div id="gbtn" style="display:inline-block"></div>
  <p class="msg err" id="lerr" style="margin-top:14px"></p>
</div>

<div class="wrap" id="app" style="display:none">
  <div class="side">
    <h2>글 목록 <button class="btn" id="new" style="padding:4px 10px;font-size:12.5px">새 글</button></h2>
    <ul id="list"></ul>
  </div>
  <div class="editor">
    <h2 id="mode">새 글</h2>
    <form id="f" onsubmit="return false">
      <label>제목</label><input type="text" id="title" required>
      <div class="row">
        <div><label>게시일</label><input type="date" id="date" required></div>
        <div><label>분류</label><select id="category"><option>뉴스</option><option>수수료 변경</option><option>정책 해설</option><option>공지</option><option>가이드</option></select></div>
      </div>
      <label>주소용 영문 키워드 <small style="color:var(--faint)">영문 소문자와 하이픈, 비우면 자동</small></label><input type="text" id="slug" placeholder="g1055-biometric-fee">
      <label>요약 <small style="color:var(--faint)">목록과 검색 결과에 노출, 두 문장 이내</small></label><textarea id="summary" rows="2"></textarea>
      <label>대표 이미지</label>
      <div class="cover"><img id="coverimg" alt=""><input type="file" id="coverfile" accept="image/*"><button type="button" class="btn" id="coverdel" style="display:none">빼기</button></div>
      <label>본문 <small style="color:var(--faint)">## 소제목, - 목록, **굵게**</small></label>
      <div class="tools"><button type="button" data-ins="## ">소제목</button><button type="button" data-ins="- ">목록</button><button type="button" data-wrap="**">굵게</button><button type="button" id="imgbtn">이미지 넣기</button><input type="file" id="imgfile" accept="image/*" style="display:none"></div>
      <textarea id="body"></textarea>
      <div class="row"><div><label>예약 게시 <small style="color:var(--faint)">비우면 즉시 게시, 한국 시간</small></label><input type="datetime-local" id="publish_at" style="width:100%;border:1px solid var(--rule);padding:8px 10px;font:inherit;font-size:14px"></div><div></div></div>
      <label class="chk"><input type="checkbox" id="draft"> 임시저장 (사이트에 공개하지 않음)</label>
      <div class="bar"><button class="btn solid" id="save">저장하고 게시</button><span class="msg" id="msg"></span><span class="sp"></span><button class="btn danger" id="del" style="display:none">삭제</button></div>
    </form>
  </div>
</div>

<div class="wrap" id="feesview" style="display:none;grid-template-columns:1fr">
  <div class="editor">
    <h2>수수료 원장 <span><button class="btn solid" id="feesave" style="padding:5px 12px;font-size:12.5px">저장하고 반영</button> <span class="msg" id="fmsg"></span></span></h2>
    <div style="overflow:auto"><table id="ftable" style="width:100%;border-collapse:collapse;font-size:13.5px"></table></div>
  </div>
</div>

<script>
const CLIENT_ID=${JSON.stringify(clientId)};
let token=sessionStorage.getItem('vc_tok')||'', cur=null, cover='';
const $=id=>document.getElementById(id);
const today=()=>new Date(Date.now()+9*3600e3).toISOString().slice(0,10);

async function call(path,opt={}){
  const r=await fetch(path,{...opt,headers:{'Content-Type':'application/json',Authorization:'Bearer '+token}});
  const d=await r.json().catch(()=>({}));
  if(r.status===401){token='';sessionStorage.removeItem('vc_tok');showLogin(d.error);throw new Error(d.error||'로그인 필요');}
  if(!r.ok)throw new Error(d.error||('오류 '+r.status));
  return d;
}
function msg(t,ok){const m=$('msg');m.textContent=t;m.className='msg '+(ok?'ok':'err');}
function showLogin(err){$('feesview').style.display='none';$('tab-posts').style.display='none';$('tab-fees').style.display='none';$('app').style.display='none';$('login').style.display='';$('logout').style.display='none';$('who').textContent='';if(err)$('lerr').textContent=err;}

async function start(){
  try{const me=await call('/api/me');$('who').textContent=me.email;$('login').style.display='none';$('app').style.display='';$('logout').style.display='';$('tab-posts').style.display='';$('tab-fees').style.display='';blank();load();}
  catch(e){}
}
window.onGoogle=r=>{token=r.credential;sessionStorage.setItem('vc_tok',token);$('lerr').textContent='';start();};
window.addEventListener('load',()=>{
  const init=()=>{ if(!window.google){return setTimeout(init,200);}
    google.accounts.id.initialize({client_id:CLIENT_ID,callback:onGoogle});
    google.accounts.id.renderButton($('gbtn'),{theme:'outline',size:'large',text:'signin_with',locale:'ko'});
    if(token)start();
  };init();
});
$('logout').onclick=e=>{e.preventDefault();token='';sessionStorage.removeItem('vc_tok');showLogin();};

async function load(){
  const list=await call('/api/posts');
  $('list').innerHTML=list.map(p=>'<li data-p="'+p.path+'"'+(cur&&cur.path===p.path?' class="on"':'')+'>'+p.name.replace(/\\.md$/,'').slice(11)+'<small>'+p.name.slice(0,10)+'</small></li>').join('')||'<li>글이 없습니다</li>';
  document.querySelectorAll('#list li[data-p]').forEach(li=>li.onclick=()=>openPost(li.dataset.p));
}
function setCover(u){cover=u||'';const i=$('coverimg');i.src=u?'https://visacal.com'+u:'';i.style.display=u?'block':'none';$('coverdel').style.display=u?'':'none';}
function blank(){cur=null;$('mode').textContent='새 글';['title','slug','summary','body'].forEach(k=>$(k).value='');$('date').value=today();$('publish_at').value='';$('category').value='뉴스';$('draft').checked=false;setCover('');$('del').style.display='none';msg('');}
async function openPost(path){
  msg('불러오는 중',true);
  const p=await call('/api/post?path='+encodeURIComponent(path));
  cur={path:p.path,sha:p.sha};$('mode').textContent='수정: '+(p.title||'');
  $('title').value=p.title||'';$('slug').value=p.slug||'';$('date').value=String(p.date||today()).slice(0,10);
  $('category').value=p.category||'뉴스';$('summary').value=p.summary||'';$('body').value=p.body||'';$('draft').checked=!!p.draft;$('publish_at').value=(p.publish_at||'').slice(0,16);
  setCover(p.cover||'');$('del').style.display='';msg('');load();
}
$('new').onclick=()=>{blank();load();};

function readB64(file){return new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=no;r.readAsDataURL(file);});}
async function upload(file){
  if(file.size>5*1024*1024)throw new Error('5MB 이하 이미지만 가능합니다');
  msg('이미지 올리는 중',true);
  const d=await call('/api/upload',{method:'POST',body:JSON.stringify({name:file.name,data:await readB64(file)})});
  msg('이미지 저장됨',true);return d.url;
}
$('coverfile').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{setCover(await upload(f));}catch(x){msg(x.message);}e.target.value='';};
$('coverdel').onclick=()=>setCover('');
$('imgbtn').onclick=()=>$('imgfile').click();
$('imgfile').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const u=await upload(f);insert('\\n![]('+u+')\\n');}catch(x){msg(x.message);}e.target.value='';};
function insert(t){const b=$('body'),s=b.selectionStart;b.value=b.value.slice(0,s)+t+b.value.slice(b.selectionEnd);b.focus();b.selectionStart=b.selectionEnd=s+t.length;}
document.querySelectorAll('[data-ins]').forEach(x=>x.onclick=()=>insert(x.dataset.ins));
document.querySelectorAll('[data-wrap]').forEach(x=>x.onclick=()=>{const b=$('body'),s=b.selectionStart,e=b.selectionEnd,w=x.dataset.wrap;b.value=b.value.slice(0,s)+w+b.value.slice(s,e)+w+b.value.slice(e);b.focus();});

$('save').onclick=async()=>{
  if(!$('title').value.trim())return msg('제목을 입력하십시오');
  $('save').disabled=true;msg('저장 중',true);
  try{
    const d=await call('/api/post',{method:'POST',body:JSON.stringify({path:cur&&cur.path,sha:cur&&cur.sha,title:$('title').value.trim(),slug:$('slug').value.trim(),date:$('date').value,category:$('category').value,summary:$('summary').value.trim(),cover,body:$('body').value,draft:$('draft').checked,publish_at:$('publish_at').value})});
    cur={path:d.path,sha:d.sha};$('del').style.display='';
    const pa=$('publish_at').value;msg($('draft').checked?'임시저장됨':(pa&&pa>new Date(Date.now()+9*3600e3).toISOString().slice(0,16)?('예약됨. '+pa.replace('T',' ')+'에 게시됩니다'):'게시됨. 1분 안에 사이트에 반영됩니다'),true);load();
  }catch(x){msg(x.message);}
  $('save').disabled=false;
};
$('del').onclick=async()=>{
  if(!cur||!confirm('이 글을 삭제할까요? 사이트에서도 내려갑니다.'))return;
  try{await call('/api/post',{method:'DELETE',body:JSON.stringify(cur)});blank();load();msg('삭제됨',true);}catch(x){msg(x.message);}
};
let F=null;
const ST=['시행중','시행예정','집행정지','검토필요'];
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function fmsg(t,ok){const m=$('fmsg');m.textContent=t;m.className='msg '+(ok?'ok':'err');}
async function loadFees(){
  fmsg('불러오는 중',true);
  F=await call('/api/fees');
  const th='padding:8px;border-bottom:1px solid var(--rule);text-align:left;color:var(--faint);font-weight:600;font-size:12px';
  const td='padding:6px 8px;border-bottom:1px solid var(--hair)';
  const inp='width:100%;border:1px solid var(--rule);padding:5px 7px;font:inherit;font-size:13px';
  $('ftable').innerHTML='<tr><th style="'+th+'">비자</th><th style="'+th+'">항목</th><th style="'+th+'">금액</th><th style="'+th+'">상태</th><th style="'+th+'">시행일</th><th style="'+th+'">근거</th></tr>'+
    F.data.fees.map(f=>'<tr data-id="'+esc(f.fee_id)+'"><td style="'+td+'">'+esc(f.visa)+'</td><td style="'+td+'">'+esc(f.item)+'</td>'+
    '<td style="'+td+';width:110px"><input data-k="amount" style="'+inp+';text-align:right" value="'+(f.amount??'')+'" placeholder="확인 필요"></td>'+
    '<td style="'+td+';width:110px"><select data-k="status" style="'+inp+'">'+ST.map(x=>'<option'+(x===f.status?' selected':'')+'>'+x+'</option>').join('')+'</select></td>'+
    '<td style="'+td+';width:140px"><input data-k="effective_date" type="date" style="'+inp+'" value="'+esc(f.effective_date||'')+'"></td>'+
    '<td style="'+td+'"><input data-k="basis" style="'+inp+'" value="'+esc(f.basis)+'"></td></tr>').join('');
  fmsg('',true);
}
$('feesave').onclick=async()=>{
  const fees=[...document.querySelectorAll('#ftable tr[data-id]')].map(tr=>{const o={fee_id:tr.dataset.id};tr.querySelectorAll('[data-k]').forEach(i=>o[i.dataset.k]=i.value.trim());return o;});
  $('feesave').disabled=true;fmsg('저장 중',true);
  try{const d=await call('/api/fees',{method:'PUT',body:JSON.stringify({sha:F.sha,fees})});F.sha=d.sha;fmsg('저장됨. 1분 안에 계산기에 반영됩니다',true);}catch(x){fmsg(x.message);}
  $('feesave').disabled=false;
};
$('tab-fees').onclick=e=>{e.preventDefault();$('app').style.display='none';$('feesview').style.display='grid';loadFees();};
$('tab-posts').onclick=e=>{e.preventDefault();$('feesview').style.display='none';$('app').style.display='';};
</script></body></html>`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/api/')) {
      try { return await api(request, env, url); }
      catch (e) { return json({ error: e.message }, 500); }
    }
    if (url.pathname === '/' || url.pathname === '/index.html') {
      return new Response(PAGE(env.GOOGLE_CLIENT_ID || ''), {
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'no-store',
          'X-Robots-Tag': 'noindex',
          'Referrer-Policy': 'strict-origin-when-cross-origin',
        },
      });
    }
    return new Response('Not found', { status: 404 });
  },
};
