import os,json,sqlite3,secrets,csv,io
from datetime import datetime,timezone
from functools import wraps
from flask import Flask,request,session,redirect,url_for,render_template_string,jsonify,Response,abort
from werkzeug.security import check_password_hash,generate_password_hash
app=Flask(__name__);app.secret_key=os.environ.get('SECRET_KEY',secrets.token_hex(32));DB=os.environ.get('DATABASE','exam.sqlite3')
BANK=json.load(open(os.path.join(os.path.dirname(__file__),'questions.json'),encoding='utf8'))
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');return c
def init():
 with db() as c:
  c.execute('CREATE TABLE IF NOT EXISTS invitations(token TEXT PRIMARY KEY,ticket INTEGER NOT NULL,created TEXT NOT NULL)')
  c.execute('CREATE TABLE IF NOT EXISTS results(token TEXT PRIMARY KEY,name TEXT NOT NULL,ticket INTEGER NOT NULL,answers TEXT NOT NULL,score INTEGER NOT NULL,submitted TEXT NOT NULL)')
init()
STYLE='''<meta name="viewport" content="width=device-width, initial-scale=1"><style>body{font:16px system-ui,Arial;background:#f2f5f9;color:#152b3d;margin:0}main{max-width:850px;margin:24px auto;padding:12px}.card{background:white;padding:22px;margin:14px 0;border-radius:13px;box-shadow:0 2px 12px #152b3d12}button,.btn{background:#145a93;color:white;border:0;border-radius:8px;padding:11px 16px;cursor:pointer;text-decoration:none;display:inline-block}input{padding:10px;margin:5px 0}label.opt{display:block;padding:12px;border:1px solid #dce3ec;border-radius:8px;margin:8px 0}table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #ddd;text-align:left;padding:8px}small{color:#607080}a{color:#145a93}.bad{color:#a52b2b}.ok{color:#157548}</style>'''
def admin_required(fn):
 @wraps(fn)
 def inner(*a,**k):
  if not session.get('admin'):return redirect(url_for('login'))
  return fn(*a,**k)
 return inner
@app.route('/admin/login',methods=['GET','POST'])
def login():
 error=''
 if request.method=='POST':
  password=os.environ.get('ADMIN_PASSWORD','')
  if password and secrets.compare_digest(request.form.get('password',''),password):session['admin']=True;return redirect('/admin')
  error='Yanlış parol'
 return render_template_string(STYLE+'<main><div class="card"><h2>Rəhbər girişi</h2><p class="bad">{{error}}</p><form method="post"><input type="password" name="password" required placeholder="Admin parolu"><button>Giriş</button></form></div></main>',error=error)
@app.route('/admin/logout')
def logout():session.clear();return redirect('/admin/login')
@app.route('/admin',methods=['GET','POST'])
@admin_required
def admin():
 if request.method=='POST':
  t=int(request.form['ticket']);count=min(100,max(1,int(request.form.get('count',1))))
  if t not in range(1,11):abort(400)
  with db() as c:
   for _ in range(count):c.execute('INSERT INTO invitations VALUES (?,?,?)',(secrets.token_urlsafe(24),t,datetime.now(timezone.utc).isoformat()))
  return redirect('/admin')
 with db() as c:
  invites=c.execute('SELECT i.token,i.ticket,r.name,r.score,r.submitted FROM invitations i LEFT JOIN results r ON i.token=r.token ORDER BY i.created DESC').fetchall()
  results=c.execute('SELECT * FROM results ORDER BY submitted DESC').fetchall()
 base=request.url_root.rstrip('/')
 return render_template_string(STYLE+'''<main><div class="card"><h1>QƏYT MTİ — Rəhbər paneli</h1><p>İştirakçı sayı: <b>{{results|length}}</b> | Orta nəticə: <b>{{'%.1f'|format((results|sum(attribute='score')/results|length)*20) if results else 0}}%</b></p><a href="/admin/export">CSV hesabatı</a> · <a href="/admin/logout">Çıxış</a></div><div class="card"><h2>Şəxsi imtahan linkləri yarat</h2><form method="post">Bilet <select name="ticket">{% for i in range(1,11) %}<option value="{{i}}">{{i}}</option>{% endfor %}</select> Say <input name="count" type="number" min="1" max="100" value="1" style="width:65px"><button>Yarat</button></form><small>Hər link yalnız bir dəfə yekunlaşdırıla bilər. Linki paylaşdığınız şəxsin kimliyini ayrıca təsdiqləyin.</small></div><div class="card"><h2>İştirakçılar və nəticələr</h2><table><tr><th>Ad, soyad</th><th>Bilet</th><th>Nəticə</th><th>Tarix</th><th>Ətraflı</th></tr>{% for r in results %}<tr><td>{{r['name']}}</td><td>{{r['ticket']}}</td><td>{{r['score']}}/5</td><td>{{r['submitted'][:19]}}</td><td><a href="/admin/result/{{r['token']}}">Cavablar</a></td></tr>{% endfor %}</table></div><div class="card"><h2>İmtahan dəvətnamələri</h2><table><tr><th>Bilet</th><th>Link</th><th>Status</th></tr>{% for i in invites %}<tr><td>{{i['ticket']}}</td><td><a href="{{base}}/exam/{{i['token']}}" target="_blank">İmtahan linki</a> <button type="button" onclick="navigator.clipboard.writeText('{{base}}/exam/{{i['token']}}')">Kopyala</button> <a href="/admin/qr/{{i['token']}}" target="_blank">QR kod</a></td><td>{{'Tamamlanıb' if i['submitted'] else 'Gözləyir'}}</td></tr>{% endfor %}</table></div></main>''',results=results,invites=invites,base=base)
@app.route('/admin/result/<token>')
@admin_required
def detail(token):
 with db() as c:r=c.execute('SELECT * FROM results WHERE token=?',(token,)).fetchone()
 if not r:abort(404)
 qs=BANK[(r['ticket']-1)*5:r['ticket']*5];answers=json.loads(r['answers']);rows=[]
 for q,a in zip(qs,answers):
  correct=q['answer'];good=sorted(a)==sorted(correct) if isinstance(correct,list) else a==correct
  given=a if isinstance(a,list) else [a];corr=correct if isinstance(correct,list) else [correct]
  rows.append(dict(q=q['question'],given='; '.join(q['options'][v] for v in given),correct='; '.join(q['options'][v] for v in corr),good=good))
 return render_template_string(STYLE+'''<main><a href="/admin">← Panel</a><div class="card"><h1>{{r['name']}} — Bilet {{r['ticket']}}</h1><h2>{{r['score']}}/5</h2><small>{{r['submitted']}}</small></div>{% for x in rows %}<div class="card"><h3>{{loop.index}}. {{x.q}}</h3><p class="{{'ok' if x.good else 'bad'}}">{{'Düzgün' if x.good else 'Səhv'}}</p><p><b>Verilən cavab:</b> {{x.given}}</p><p><b>Düzgün cavab:</b> {{x.correct}}</p></div>{% endfor %}</main>''',r=r,rows=rows)
@app.route('/admin/export')
@admin_required
def export():
 with db() as c:rows=c.execute('SELECT * FROM results ORDER BY submitted DESC').fetchall()
 out=io.StringIO();w=csv.writer(out);w.writerow(['Ad soyad','Bilet','Nəticə (5 üzərindən)','Tarix','Sual ID','Sual','Verilən cavab','Düzgün cavab','Status'])
 for r in rows:
  for q,a in zip(BANK[(r['ticket']-1)*5:r['ticket']*5],json.loads(r['answers'])):
   correct=q['answer'];given=a if isinstance(a,list) else [a];corr=correct if isinstance(correct,list) else [correct];good=sorted(given)==sorted(corr)
   w.writerow([r['name'],r['ticket'],r['score'],r['submitted'],q['id'],q['question'],'; '.join(q['options'][v] for v in given),'; '.join(q['options'][v] for v in corr),'Düzgün' if good else 'Səhv'])
 return Response('\ufeff'+out.getvalue(),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=qeyt_results.csv'})
@app.route('/exam/<token>')
def exam(token):
 with db() as c:
  i=c.execute('SELECT * FROM invitations WHERE token=?',(token,)).fetchone();r=c.execute('SELECT * FROM results WHERE token=?',(token,)).fetchone()
 if not i:abort(404)
 if r:return render_template_string(STYLE+'<main><div class="card"><h2>İmtahan artıq tamamlanıb</h2><p>Bu dəvətnamə ilə cavabları yenidən dəyişmək mümkün deyil.</p></div></main>')
 qs=[dict(id=q['id'],question=q['question'],options=q['options'],multi=isinstance(q['answer'],list)) for q in BANK[(i['ticket']-1)*5:i['ticket']*5]]
 return render_template_string(STYLE+'''<main><div class="card"><h1>QƏYT MTİ — Bilet {{ticket}}</h1><p>Ad və soyadınızı daxil edin, bütün 5 suala cavab verin. Cavablar yalnız yekun təsdiqdən sonra yoxlanacaq.</p><label>Ad, soyad <input id="name" maxlength="120" required></label></div><div id="questions"></div><button id="send">Cavabları yekun təsdiqlə</button><div id="message"></div></main><script>const qs={{qs|tojson}},token={{token|tojson}};let sent=false;let root=document.getElementById('questions');qs.forEach((q,i)=>{let box=document.createElement('div');box.className='card';let h=document.createElement('h3');h.textContent=(i+1)+'. '+q.question;box.append(h);if(q.multi){let tip=document.createElement('small');tip.textContent='Bir neçə cavab seçilə bilər';box.append(tip)}q.options.forEach((o,j)=>{let label=document.createElement('label');label.className='opt';let inp=document.createElement('input');inp.type=q.multi?'checkbox':'radio';inp.name='q'+i;inp.value=j;label.append(inp,document.createTextNode(' '+o));box.append(label)});root.append(box)});document.getElementById('send').onclick=async()=>{if(sent)return;let name=document.getElementById('name').value.trim();if(!name){alert('Ad və soyadınızı yazın');return}let answers=qs.map((q,i)=>{let selected=[...document.querySelectorAll('input[name=q'+i+']:checked')].map(x=>+x.value);return q.multi?selected:(selected.length?selected[0]:null)});if(answers.some((a,i)=>qs[i].multi?!a.length:a===null)){alert('Bütün sualları cavablandırın');return}if(!confirm('Cavablar yekunlaşdırılsın? Sonradan dəyişdirilə bilməz.'))return;sent=true;document.getElementById('send').disabled=true;try{let resp=await fetch('/api/submit/'+token,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,answers})});let data=await resp.json();if(!resp.ok){alert(data.error||'Xəta');return}document.querySelector('main').innerHTML='<div class="card"><h1>İmtahan tamamlandı</h1><h2>Nəticə: '+data.score+'/5 ('+data.score*20+'%)</h2><p>Cavablar yekunlaşdırılıb və kilidlənib.</p></div>';data.details.forEach((d,i)=>{let div=document.createElement('div');div.className='card';let h=document.createElement('h3');h.textContent=(i+1)+'. '+d.question;div.append(h);for(let [label,val] of [['Status',d.good?'Düzgün':'Səhv'],['Sizin cavabınız',d.given.join('; ')],['Düzgün cavab',d.correct.join('; ')]]){let p=document.createElement('p');let b=document.createElement('b');b.textContent=label+': ';p.append(b,document.createTextNode(val));div.append(p)}document.querySelector('main').append(div)})}catch(e){alert('Bağlantı xətası. Yenidən daxil olub statusu yoxlayın.')} }; </script>''',qs=qs,ticket=i['ticket'],token=token)
@app.route('/api/submit/<token>',methods=['POST'])
def submit(token):
 data=request.get_json(silent=True) or {};name=data.get('name','');a=data.get('answers')
 if not isinstance(name,str) or not (2<=len(name.strip())<=120) or not isinstance(a,list) or len(a)!=5:return jsonify(error='Məlumat düzgün deyil'),400
 with db() as c:
  i=c.execute('SELECT ticket FROM invitations WHERE token=?',(token,)).fetchone()
  if not i:return jsonify(error='Dəvətnamə tapılmadı'),404
  if c.execute('SELECT 1 FROM results WHERE token=?',(token,)).fetchone():return jsonify(error='Bu bilet artıq yekunlaşdırılıb'),409
  qs=BANK[(i['ticket']-1)*5:i['ticket']*5];details=[];score=0
  for q,v in zip(qs,a):
   multi=isinstance(q['answer'],list)
   if multi:
    if not isinstance(v,list) or not v or any(type(n)!=int or n not in range(len(q['options'])) for n in v) or len(set(v))!=len(v):return jsonify(error='Cavab səhv formatdadır'),400
   elif type(v)!=int or v not in range(len(q['options'])):return jsonify(error='Cavab səhv formatdadır'),400
   corr=q['answer'];good=sorted(v)==sorted(corr) if multi else v==corr;score+=good
   given=v if multi else [v];correct=corr if multi else [corr]
   details.append(dict(question=q['question'],given=[q['options'][n] for n in given],correct=[q['options'][n] for n in correct],good=good))
  try:c.execute('INSERT INTO results VALUES (?,?,?,?,?,?)',(token,name.strip(),i['ticket'],json.dumps(a,ensure_ascii=False),score,datetime.now(timezone.utc).isoformat()))
  except sqlite3.IntegrityError:return jsonify(error='Bu bilet artıq yekunlaşdırılıb'),409
 return jsonify(score=score,details=details)
@app.route('/')
def home():return redirect('/admin')
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
@app.route('/admin/qr/<token>')
@admin_required
def qr(token):
 import qrcode
 with db() as c:r=c.execute('SELECT 1 FROM invitations WHERE token=?',(token,)).fetchone()
 if not r:abort(404)
 img=qrcode.make(request.url_root.rstrip('/')+'/exam/'+token);b=io.BytesIO();img.save(b,format='PNG');b.seek(0)
 return Response(b.getvalue(),mimetype='image/png')
