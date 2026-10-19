import {useState} from 'react';
import Dashboard from './Dashboard';
import {api, rubles, toKopeks, type Order, type Revision, type Change, type ChangeWorkflow, type Assessment, type BusinessRole} from './api';

const nextMonth=()=>{const d=new Date();d.setDate(d.getDate()+30);return d.toISOString().slice(0,10);};
type Page='overview'|'orders'|'production'|'changes'|'approvals'|'history';
const ROLE_LABELS:Record<BusinessRole,string>={sales:'Менеджер',production:'Производство',approver:'Руководитель'};
const PAGES:{id:Page;title:string;caption:string;roles:BusinessRole[]}[]=[
  {id:'overview',title:'Обзор',caption:'01',roles:['sales','approver']},
  {id:'orders',title:'Заказы',caption:'02',roles:['sales','production','approver']},
  {id:'production',title:'Производство',caption:'03',roles:['production']},
  {id:'changes',title:'Изменения',caption:'04',roles:['sales']},
  {id:'approvals',title:'Согласования',caption:'05',roles:['approver']},
  {id:'history',title:'История версий',caption:'06',roles:['sales','production','approver']},
];

export default function App(){
  const [credential,setCredential]=useState('');
  const [token,setToken]=useState('');
  const [role,setRole]=useState<BusinessRole|null>(null);
  const [page,setPage]=useState<Page>('overview');
  const [authBusy,setAuthBusy]=useState(false);
  const [authError,setAuthError]=useState('');
  const [order,setOrder]=useState<Order|null>(null);
  const [history,setHistory]=useState<Revision[]>([]);
  const [change,setChange]=useState<Change|null>(null);
  const [changes,setChanges]=useState<ChangeWorkflow[]>([]);
  const [assessment,setAssessment]=useState<Assessment|null>(null);
  const [accepted,setAccepted]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  const [lookup,setLookup]=useState(()=>sessionStorage.getItem('handoffguard-demo-order-id')??'');
  const [baseline,setBaseline]=useState({product:'FRAME-01',quantity:'100',price:'1000',cost:'600',date:nextMonth(),source:'synthetic-order-100'});
  const [review,setReview]=useState({status:'NOT_STARTED',count:'0',feasibility:'CONFIRMED',note:'Мощности подтверждены'});
  const [newQty,setNewQty]=useState('120');
  const [reason,setReason]=useState('Клиент просит увеличить заказ');
  const [evidence,setEvidence]=useState('Клиент подтвердил количество, цену и срок');
  const [decisionNote,setDecisionNote]=useState('Коммерческие условия подтверждены');

  async function signIn(){
    if(!credential.trim()){setAuthError('Введите ключ доступа, выданный для вашей роли.');return;}
    setAuthBusy(true);setAuthError('');
    try{
      // Role comes from FastAPI after authenticating the token, never from the browser.
      const result=await api.currentSession(credential.trim());
      if(!['sales','production','approver'].includes(result.role))throw new Error('Сервер вернул неизвестную роль.');
      setToken(credential.trim());
      setRole(result.role);
      setPage(result.role==='production'?'orders':'overview');
      setCredential('');
      setError('');
      setMessage('');
    }catch(e){
      setAuthError(e instanceof Error?e.message:'Не удалось войти.');
    }finally{setAuthBusy(false);}
  }

  function signOut(){
    setToken('');setRole(null);setCredential('');setPage('overview');setAuthError('');
    setOrder(null);setHistory([]);setChange(null);setChanges([]);setAssessment(null);setAccepted(false);
    setError('');setMessage('');setLookup('');
    sessionStorage.removeItem('handoffguard-demo-order-id');
    sessionStorage.removeItem('handoffguard-demo-change-id');
  }

  async function run(name:string,task:()=>Promise<void>){
    setBusy(true);setError('');setMessage('');
    try{await task();setMessage(name+' — выполнено');}
    catch(e){setError(e instanceof Error?e.message:'Неизвестная ошибка');}
    finally{setBusy(false);}
  }

  function selectSavedWorkflow(records:ChangeWorkflow[],preferredId?:string){
    setChanges(records);
    const priorities=['INTERNALLY_APPROVED','PENDING_APPROVAL','ASSESSMENT_REQUIRED','DRAFT','APPLIED','REJECTED'];
    const current=records.find(record=>record.id===(preferredId??''))
      ??records.find(record=>record.id===sessionStorage.getItem('handoffguard-demo-change-id'))
      ??[...records].sort((a,b)=>priorities.indexOf(a.status)-priorities.indexOf(b.status))[0];
    setChange(current??null);setAssessment(current?.assessment??null);setAccepted(Boolean(current?.customer_accepted));
    if(current)sessionStorage.setItem('handoffguard-demo-change-id',current.id);
    else sessionStorage.removeItem('handoffguard-demo-change-id');
  }
  async function reloadWorkflows(id:string,preferredId?:string){
    if(role==='production')return;
    const records=await api.listChanges(token,id);
    selectSavedWorkflow(records,preferredId);
  }
  async function load(id:string){
    const normalized=id.trim();if(!normalized)throw new Error('Введите идентификатор заказа.');
    const [current,approved,records]=await Promise.all([
      api.getOrder(token,normalized),
      api.revisions(token,normalized),
      role==='production'?Promise.resolve([] as ChangeWorkflow[]):api.listChanges(token,normalized),
    ]);
    setOrder(current);setHistory(approved);setLookup(current.id);
    sessionStorage.setItem('handoffguard-demo-order-id',current.id);
    selectSavedWorkflow(records);
  }
  async function refresh(id:string){
    const [current,approved]=await Promise.all([api.getOrder(token,id),api.revisions(token,id)]);
    setOrder(current);setHistory(approved);
  }
  function openFromDashboard(orderId:string){
    void run('Открытие заказа',async()=>{await load(orderId);setPage('orders');});
  }

  const canAssess=!!change&&(change.status==='DRAFT'||change.status==='ASSESSMENT_REQUIRED');
  const canSubmit=!!change&&change.status==='ASSESSMENT_REQUIRED'&&assessment?.readiness==='READY_FOR_APPROVAL';
  const canDecide=!!change&&change.status==='PENDING_APPROVAL'&&!!assessment;
  const approved=change?.status==='INTERNALLY_APPROVED';

  if(!role){
    return <div className="login-scene">
      <div className="login-logo">HG <span>/ HandoffGuard AI</span></div>
      <main className="login-card">
        <span className="overline">WORKSPACE ACCESS</span>
        <h1>Управление изменениями. Без хаоса.</h1>
        <p>Заказы, согласования и аналитика — в одном рабочем пространстве. Войди под своей ролью, чтобы увидеть доступные разделы.</p>
        <form onSubmit={e=>{e.preventDefault();void signIn();}}>
          <label>Ключ доступа для вашей роли
            <input aria-label="Ключ доступа" autoComplete="off" type="password" value={credential}
              onChange={e=>setCredential(e.target.value)} placeholder="Ключ вашей роли" required/>
          </label>
          <button className="button primary full" type="submit" disabled={authBusy}>{authBusy?'Проверяем доступ…':'Войти в рабочее пространство →'}</button>
        </form>
        {authError&&<p role="alert" className="alert error">Не удалось войти: {authError}</p>}
        <p className="login-note">Каждый ключ закреплён за одной ролью: менеджер, производство или руководитель. Роль определяет сервер. Чтобы войти под другой ролью, нажми «Сменить пользователя» и введи её тестовый ключ. Не используй реальные секреты.</p>
      </main>
      <small className="login-footer">DATALALKS.CLUB · AI DEV TOOLS 2026 · SYNTHETIC DATA ONLY</small>
    </div>;
  }

  const available=PAGES.filter(item=>item.roles.includes(role));
  const currentPage=available.find(item=>item.id===page)??available[0];

  return <div className="workspace">
    <aside className="workspace-sidebar">
      <div className="workspace-brand"><strong>HG</strong><span>HandoffGuard <small>AI Workspace</small></span></div>
      <div className="nav-caption">РАБОЧИЕ РАЗДЕЛЫ</div>
      <nav aria-label="Основная навигация" className="workspace-nav">
        {available.map((item,index)=><button key={item.id} type="button" aria-current={page===item.id?'page':undefined}
          className={'workspace-nav-item'+(page===item.id?' is-active':'')}
          onClick={()=>{setPage(item.id);setError('');setMessage('');}}>
          <span className="workspace-nav-num">{String(index+1).padStart(2,'0')}</span><span>{item.title}</span>
        </button>)}
      </nav>
      <div className="workspace-sidebottom">
        <div className="workspace-identity"><small>ТЕКУЩАЯ РОЛЬ</small><strong>{ROLE_LABELS[role]}</strong><span>Права проверяет FastAPI</span></div>
        <button type="button" className="workspace-logout" onClick={signOut}>Сменить пользователя ↗</button>
      </div>
    </aside>
    <div className="workspace-main">
      <header className="workspace-top">
        <div><span className="overline">HANDOFFGUARD / {String(available.indexOf(currentPage)+1).padStart(2,'0')}</span><h1>{currentPage.title}</h1></div>
        <div className="workspace-order-pill" title={order?.id??''}>
          <small>ТЕКУЩИЙ ЗАКАЗ</small>
          <strong>{order?order.product_code+' · V'+order.revision:'Не выбран'}</strong>
        </div>
      </header>
      <div className="workspace-content">
        {error&&<div role="alert" className="alert error">Операция заблокирована: {error}</div>}
        {message&&<div role="status" className="alert success">✓ {message}</div>}

        {page==='overview'&&role!=='production'&&<Dashboard token={token} onOpenOrder={openFromDashboard}/>}

        {page==='orders'&&<>
          <section className="panel">
            <div className="heading"><span className="overline">ORDER WORKSPACE</span><h2>Открыть заказ</h2>
              <p>Укажи ID существующего учебного заказа. Все дальнейшие действия выполняются в отдельных разделах меню.</p></div>
            <form className="lookup" onSubmit={e=>{e.preventDefault();void run('Загрузка заказа',()=>load(lookup));}}>
              <label>Идентификатор заказа<input aria-label="Order ID" value={lookup} onChange={e=>setLookup(e.target.value)}
                placeholder="UUID заказа"/></label>
              <button type="submit" disabled={busy} className="button neutral">Открыть заказ →</button>
            </form>
            {order&&<div className="summary">
              <div><small>АКТИВНЫЙ ЗАКАЗ</small><strong>{order.product_code} · {order.quantity} шт.</strong>
                <span>V{order.revision} · {rubles(order.unit_sales_price_kopeks)} за шт. · до {order.delivery_date}</span></div><b>Утверждён</b>
            </div>}
            {!order&&<p className="dash-hint">Заказ не выбран. Менеджер может создать новый ниже; руководитель может открыть его из таблицы дашборда.</p>}
          </section>
          {role==='sales'&&<section className="panel">
            <div className="heading"><span className="overline">01 · BASELINE</span><h2>Создать заказ V1</h2>
              <p>Только менеджер создаёт учебный заказ. Первоначальная версия сохраняется атомарно.</p></div>
            <form onSubmit={e=>{e.preventDefault();void run('Создание заказа',async()=>{
              const result=await api.createOrder(token,{product_code:baseline.product,quantity:Number(baseline.quantity),
                unit_sales_price_kopeks:toKopeks(baseline.price),
                ...(baseline.cost?{unit_est_cost_kopeks:toKopeks(baseline.cost)}:{}),
                delivery_date:baseline.date,approved_source_id:baseline.source});
              await load(result.id);
            });}}>
              <div className="grid two">
                <label>Код изделия<input required value={baseline.product} onChange={e=>setBaseline(s=>({...s,product:e.target.value}))}/></label>
                <label>Количество<input required min="1" type="number" value={baseline.quantity} onChange={e=>setBaseline(s=>({...s,quantity:e.target.value}))}/></label>
                <label>Цена за единицу, ₽<input required value={baseline.price} onChange={e=>setBaseline(s=>({...s,price:e.target.value}))}/></label>
                <label>Себестоимость, ₽<input value={baseline.cost} onChange={e=>setBaseline(s=>({...s,cost:e.target.value}))}/></label>
                <label>Срок поставки<input required type="date" value={baseline.date} onChange={e=>setBaseline(s=>({...s,date:e.target.value}))}/></label>
                <label>Основание<input required value={baseline.source} onChange={e=>setBaseline(s=>({...s,source:e.target.value}))}/></label>
              </div><button disabled={busy} type="submit" className="button primary">Создать заказ V1 →</button>
            </form>
          </section>}
        </>}

        {page==='production'&&role==='production'&&<section className="panel">
          <div className="heading"><span className="overline">02 · PRODUCTION</span><h2>Проверка производства</h2>
            <p>Производство проверяет заказ и фиксирует фактическое состояние. Внести изменение может только уполномоченная роль.</p></div>
          {!order&&<p className="dash-hint">Сначала открой заказ в разделе «Заказы».</p>}
          <form onSubmit={e=>{e.preventDefault();void run('Проверка производства',async()=>{
            if(!order)return;
            await api.productionReview(token,order.id,{production_status:review.status,
              completed_quantity:Number(review.count),feasibility:review.feasibility,note:review.note});
            setAssessment(null);setAccepted(false);await refresh(order.id);
          });}}>
            <div className="grid two">
              <label>Стадия<select value={review.status} onChange={e=>setReview(s=>({...s,status:e.target.value}))}>
                <option value="NOT_STARTED">Не начато</option><option value="IN_PRODUCTION">В производстве</option><option value="COMPLETED">Завершено</option>
              </select></label>
              <label>Изготовлено<input type="number" min="0" value={review.count} onChange={e=>setReview(s=>({...s,count:e.target.value}))}/></label>
              <label>Возможность<select value={review.feasibility} onChange={e=>setReview(s=>({...s,feasibility:e.target.value}))}>
                <option value="CONFIRMED">Подтверждена</option><option value="UNKNOWN">Неизвестна</option><option value="NOT_FEASIBLE">Невозможна</option>
              </select></label>
              <label>Комментарий<input value={review.note} onChange={e=>setReview(s=>({...s,note:e.target.value}))}/></label>
            </div><button disabled={busy||!order} className="button neutral">Сохранить проверку</button>
          </form>
        </section>}

        {page==='changes'&&role==='sales'&&<>
          <section className="panel">
            <div className="heading"><span className="overline">03 · CHANGE REQUEST</span><h2>Изменения заказа</h2>
              <p>Запрос клиента не меняет утверждённую версию. Менеджер создаёт предложение и передаёт его руководителю.</p></div>
            {!order&&<p className="dash-hint">Сначала открой или создай заказ в разделе «Заказы».</p>}
            <form onSubmit={e=>{e.preventDefault();void run('Запрос на изменение',async()=>{
              if(!order)return;const record=await api.createChange(token,order.id,{reason,requested_quantity:Number(newQty)});
              await reloadWorkflows(order.id,record.id);
            });}}>
              <div className="grid two">
                <label>Запрошено, изделий<input required type="number" min="1" value={newQty} onChange={e=>setNewQty(e.target.value)}/></label>
                <label>Причина запроса<input required value={reason} onChange={e=>setReason(e.target.value)}/></label>
              </div>
              <button disabled={busy||!order} className="button neutral">Создать изменение →</button>
            </form>
            {changes.length>0&&<label>Сохранённые заявки этого заказа
              <select aria-label="Выбрать сохранённое изменение" value={change?.id??''} onChange={e=>{
                const found=changes.find(item=>item.id===e.target.value);
                if(found)selectSavedWorkflow(changes,found.id);
              }}>{changes.map(item=><option key={item.id} value={item.id}>{item.requested_quantity??'—'} шт. · {item.status} · {item.reason}</option>)}</select>
            </label>}
            {change&&<div className="summary"><div><small>ТЕКУЩЕЕ ИЗМЕНЕНИЕ</small><strong>{change.requested_quantity??'—'} изделий</strong>
              <span>База V{change.baseline_revision} · {change.status}</span></div><b>Запрос</b></div>}
          </section>
          <section className="panel">
            <div className="heading"><span className="overline">04 · ASSESS & SUBMIT</span><h2>Оценка последствий</h2>
              <p>Сервер проверяет производственные условия и создаёт воспроизводимый расчёт до согласования.</p></div>
            <div className="actions">
              <button className="button neutral" disabled={busy||!canAssess} onClick={()=>void run('Расчёт последствий',async()=>{
                if(!change)return;await api.assess(token,change.id);if(order)await reloadWorkflows(order.id,change.id);
              })}>1. Рассчитать</button>
              <button className="button neutral" disabled={busy||!canSubmit} onClick={()=>void run('Передача руководителю',async()=>{
                if(!change)return;await api.submit(token,change.id);if(order)await reloadWorkflows(order.id,change.id);
              })}>2. На согласование →</button>
            </div>
            {assessment&&<div className="assessment"><div><small>ГОТОВНОСТЬ</small><strong>{assessment.readiness}</strong></div>
              <div><small>ИЗМЕНЕНИЕ ВЫРУЧКИ</small><strong>{rubles(assessment.delta_revenue_kopeks)}</strong></div>
              {assessment.issues.length>0&&<p>Ограничения: {assessment.issues.join(', ')}</p>}</div>}
          </section>
          <section className="panel">
            <div className="heading"><span className="overline">06 · CUSTOMER</span><h2>Подтверждение клиента</h2>
              <p>Внутреннее согласование само по себе не означает принятие клиентом.</p></div>
            <p>{change?.requested_quantity??order?.quantity??'—'} шт. · {rubles(order?.unit_sales_price_kopeks??null)} / шт. · {order?.delivery_date??'—'}</p>
            <label>Источник подтверждения<input value={evidence} onChange={e=>setEvidence(e.target.value)}/></label>
            <div className="actions"><button className="button neutral" disabled={busy||!approved||accepted} onClick={()=>void run('Подтверждение клиента',async()=>{
              if(!change||!order)return;await api.accept(token,change.id,{
                quantity:change.requested_quantity??order.quantity,unit_sales_price_kopeks:order.unit_sales_price_kopeks,
                delivery_date:order.delivery_date,source_name:'synthetic-confirmation',evidence_text:evidence});
              await reloadWorkflows(order.id,change.id);
            })}>{accepted?'Подтверждение записано':'Зафиксировать подтверждение →'}</button></div>
          </section>
        </>}

        {page==='approvals'&&role==='approver'&&<section className="panel">
          <div className="heading"><span className="overline">05 · APPROVALS</span><h2>Решение руководителя</h2>
            <p>Решение требует текущего расчёта и привязано к его fingerprint. Одобрение и применение — разные действия.</p></div>
          {!order&&<p className="dash-hint">Сначала открой заказ из дашборда или укажи его ID в разделе «Заказы».</p>}
          {changes.length>0&&<label>Заявка на согласование
            <select aria-label="Выбрать сохранённое изменение" value={change?.id??''} onChange={e=>{
              const found=changes.find(item=>item.id===e.target.value);
              if(found)selectSavedWorkflow(changes,found.id);
            }}>{changes.map(item=><option key={item.id} value={item.id}>{item.requested_quantity??'—'} шт. · {item.status}</option>)}</select>
          </label>}
          {change&&<div className="summary"><div><small>ЗАЯВКА</small><strong>{change.requested_quantity??'—'} шт.</strong>
            <span>{change.status} · база V{change.baseline_revision}</span></div><b>Решение</b></div>}
          {assessment&&<div className="assessment"><div><small>ГОТОВНОСТЬ</small><strong>{assessment.readiness}</strong></div>
            <div><small>ИЗМЕНЕНИЕ ВЫРУЧКИ</small><strong>{rubles(assessment.delta_revenue_kopeks)}</strong></div>
            {assessment.issues.length>0&&<p>Ограничения: {assessment.issues.join(', ')}</p>}</div>}
          <label>Комментарий решения<input value={decisionNote} onChange={e=>setDecisionNote(e.target.value)}/></label>
          <div className="actions">
            <button className="button primary" disabled={busy||!canDecide} onClick={()=>void run('Утверждение руководителем',async()=>{
              if(!change||!assessment)return;await api.decision(token,change.id,assessment.fingerprint,'APPROVE',decisionNote);
              if(order)await reloadWorkflows(order.id,change.id);
            })}>Утвердить</button>
            <button className="button warning" disabled={busy||!canDecide} onClick={()=>void run('Отказ руководителя',async()=>{
              if(!change||!assessment)return;await api.decision(token,change.id,assessment.fingerprint,'REJECT',decisionNote);
              if(order)await reloadWorkflows(order.id,change.id);
            })}>Отклонить</button>
          </div>
          <div className="final-action">
            <div><strong>Применить новую версию</strong><p>V2 создаётся только после внутреннего согласования и подтверждения клиента, записанного менеджером.</p></div>
            <button className="button primary" disabled={busy||!approved||!accepted}
              onClick={()=>void run('Применение V2',async()=>{
                if(!change||!order)return;await api.apply(token,change.id);
                await refresh(order.id);await reloadWorkflows(order.id,change.id);
              })}>Применить V2 →</button>
          </div>
        </section>}

        {page==='history'&&<section className="panel">
          <div className="heading"><span className="overline">IMMUTABLE APPROVED SNAPSHOTS</span><h2>История версий заказа</h2>
            <p>Здесь только официально утверждённые версии; предложения не переписывают прошлое.</p></div>
          {history.length===0?<p className="dash-hint">Открой заказ в разделе «Заказы» — здесь появится история V1, V2 и последующих утверждений.</p>:
            <ol className="workspace-history">{history.map(rev=><li key={rev.id}>
              <span className="bubble">V{rev.revision_number}</span><div><strong>{rev.quantity} изделий</strong>
              <p>{rubles(rev.unit_sales_price_kopeks)} / шт. · до {rev.delivery_date}</p>
              <small>{rev.approved_change_id?'После согласования':'Первоначальная версия'}</small></div>
            </li>)}</ol>}
          <button type="button" className="button neutral" disabled={busy||!order} onClick={()=>void run('Обновление истории',async()=>{
            if(order)await refresh(order.id);
          })}>Обновить историю ↻</button>
        </section>}

        <p className="workspace-disclaimer">Учебная система с синтетическими данными. Сервер ограничивает права каждой роли; AI не утверждает и не применяет изменения самостоятельно.</p>
      </div>
    </div>
  </div>;
}
