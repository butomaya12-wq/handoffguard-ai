import { useState } from 'react';
import { api, rubles, toKopeks, type Order, type Revision, type Change, type ChangeWorkflow, type Assessment } from './api';

const nextMonth=()=>{const d=new Date();d.setDate(d.getDate()+30);return d.toISOString().slice(0,10);};
type Credentials={sales:string;production:string;approver:string};
const LOCAL_ROLE_TOKENS:Credentials={sales:'demo-sales',production:'demo-production',approver:'demo-approver'};
export function roleToken(role:keyof Credentials,manual:Credentials,localDemoEnabled:boolean):string{
  return localDemoEnabled?LOCAL_ROLE_TOKENS[role]:manual[role];
}
export default function App(){
  const [tokens,setTokens]=useState<Credentials>({sales:'',production:'',approver:''});
  const [useLocalDemo,setUseLocalDemo]=useState(false);
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
    const records=await api.listChanges(selectedToken('sales'),id);
    selectSavedWorkflow(records,preferredId);
  }
  async function load(id:string){
    const normalized=id.trim();if(!normalized)throw new Error('Введите идентификатор заказа.');
    const [current,approved,records]=await Promise.all([
      api.getOrder(selectedToken('sales'),normalized),api.revisions(selectedToken('sales'),normalized),
      api.listChanges(selectedToken('sales'),normalized)]);
    setOrder(current);setHistory(approved);setLookup(current.id);
    sessionStorage.setItem('handoffguard-demo-order-id',current.id);
    selectSavedWorkflow(records);
  }
  async function refresh(id:string){const [current,approved]=await Promise.all([api.getOrder(selectedToken('sales'),id),api.revisions(selectedToken('sales'),id)]);setOrder(current);setHistory(approved);}
  const localDemo=import.meta.env.DEV && ['127.0.0.1','localhost'].includes(window.location.hostname);
  const selectedToken=(role:keyof Credentials)=>roleToken(role,tokens,localDemo&&useLocalDemo);
  const canAssess=!!change&&(change.status==='DRAFT'||change.status==='ASSESSMENT_REQUIRED');
  const canSubmit=!!change&&change.status==='ASSESSMENT_REQUIRED'&&assessment?.readiness==='READY_FOR_APPROVAL';
  const canDecide=!!change&&change.status==='PENDING_APPROVAL'&&!!assessment;
  const approved=change?.status==='INTERNALLY_APPROVED';
  return <div className="shell">
    <header className="bar"><div className="logo">HG<span> / HandoffGuard</span></div><div className="meta">PROJECT 1 · EDUCATIONAL DEMO · CD-PROOF-01</div></header>
    <div className="wrapper">
      <section className="intro"><div><span className="overline">ORDER CHANGE CONTROL</span><h1>Заказ под контролем.</h1><p>Проверяем изменение до принятия обязательств. Сохраняем V1, согласовываем и создаём V2 только после подтверждения условий.</p></div><div className="version"><small>ТЕКУЩАЯ ВЕРСИЯ</small><strong>{order?'V'+order.revision:'—'}</strong><span>{order?order.quantity+' изделий':'Выбери заказ'}</span></div></section>
      <section className="panel">
        <div className="heading"><h2>Демо-доступ</h2><small>Только синтетические токены из локального backend. Не использовать реальные секреты.</small></div>
        <div className="grid three">{(['sales','production','approver'] as const).map(role=><label key={role}>{role==='sales'?'Менеджер':role==='production'?'Производство':'Руководитель'} <em>{role}</em><input aria-label={'Token '+role} autoComplete="new-password" type="password" placeholder="Bearer token" disabled={localDemo&&useLocalDemo} value={localDemo&&useLocalDemo?LOCAL_ROLE_TOKENS[role]:tokens[role]} onChange={e=>setTokens(t=>({...t,[role]:e.target.value}))}/></label>)}</div>
        {localDemo&&<button type="button" className="button neutral" onClick={()=>setUseLocalDemo(v=>!v)}>{useLocalDemo?'✓ Локальные демо-роли активны · отключить':'Использовать локальные демо-роли'}</button>}
        <p className="footnote">При активном локальном демо-режиме запросы используют заданные тестовые токены, даже если менеджер паролей пытается подставить другое значение в поле. В production необходим персональный защищённый вход. ID учебного заказа сохраняется только в этой вкладке.</p>
      </section>
      {error&&<div role="alert" className="alert error">Операция заблокирована: {error}</div>}
      {message&&<div role="status" className="alert success">✓ {message}</div>}
      <div className="layout"><main className="column">
        <section className="panel">
          <div className="heading"><span className="overline">01 · BASELINE</span><h2>Первоначальный заказ</h2><p>Операция создаёт заказ и утверждённую историю V1 одной транзакцией.</p></div>
          <form onSubmit={e=>{e.preventDefault();void run('Создание заказа',async()=>{const result=await api.createOrder(selectedToken('sales'),{product_code:baseline.product,quantity:Number(baseline.quantity),unit_sales_price_kopeks:toKopeks(baseline.price),...(baseline.cost?{unit_est_cost_kopeks:toKopeks(baseline.cost)}:{}),delivery_date:baseline.date,approved_source_id:baseline.source});await load(result.id);});}}>
            <div className="grid two">
              <label>Код изделия<input required value={baseline.product} onChange={e=>setBaseline(s=>({...s,product:e.target.value}))}/></label>
              <label>Количество<input required min="1" type="number" value={baseline.quantity} onChange={e=>setBaseline(s=>({...s,quantity:e.target.value}))}/></label>
              <label>Цена за единицу, ₽<input required value={baseline.price} onChange={e=>setBaseline(s=>({...s,price:e.target.value}))}/></label>
              <label>Себестоимость, ₽<input value={baseline.cost} onChange={e=>setBaseline(s=>({...s,cost:e.target.value}))}/></label>
              <label>Срок поставки<input required type="date" value={baseline.date} onChange={e=>setBaseline(s=>({...s,date:e.target.value}))}/></label>
              <label>Основание<input required value={baseline.source} onChange={e=>setBaseline(s=>({...s,source:e.target.value}))}/></label>
            </div><button disabled={busy} type="submit" className="button primary">Создать V1 →</button>
          </form>
          <div className="lookup"><label>Или открыть заказ по ID<input aria-label="Order ID" value={lookup} onChange={e=>setLookup(e.target.value)} placeholder="UUID заказа" /></label><button disabled={busy} className="button neutral" onClick={()=>void run('Загрузка заказа',()=>load(lookup))}>Открыть</button></div>
          {order&&<div className="summary"><div><small>АКТИВНЫЙ ЗАКАЗ</small><strong>{order.product_code} · {order.quantity} шт.</strong><span>V{order.revision} · {rubles(order.unit_sales_price_kopeks)} за шт. · {order.delivery_date}</span></div><b>Утверждён</b></div>}
        </section>
        <section className="panel">
          <div className="heading"><span className="overline">02 · PRODUCTION</span><h2>Проверка производства</h2><p>Изменение производственного состояния делает прежние оценки устаревшими.</p></div>
          <form onSubmit={e=>{e.preventDefault();void run('Проверка производства',async()=>{if(!order)return;await api.productionReview(selectedToken('production'),order.id,{production_status:review.status,completed_quantity:Number(review.count),feasibility:review.feasibility,note:review.note});setAssessment(null);setAccepted(false);await refresh(order.id);await reloadWorkflows(order.id,change?.id);});}}>
            <div className="grid two"><label>Стадия<select value={review.status} onChange={e=>setReview(s=>({...s,status:e.target.value}))}><option value="NOT_STARTED">Не начато</option><option value="IN_PRODUCTION">В производстве</option><option value="COMPLETED">Завершено</option></select></label><label>Изготовлено<input type="number" min="0" value={review.count} onChange={e=>setReview(s=>({...s,count:e.target.value}))}/></label><label>Возможность<select value={review.feasibility} onChange={e=>setReview(s=>({...s,feasibility:e.target.value}))}><option value="CONFIRMED">Подтверждена</option><option value="UNKNOWN">Неизвестна</option><option value="NOT_FEASIBLE">Невозможна</option></select></label><label>Комментарий<input value={review.note} onChange={e=>setReview(s=>({...s,note:e.target.value}))}/></label></div>
            <button disabled={busy||!order} className="button neutral">Сохранить проверку</button>
          </form>
        </section>
        <section className="panel">
          <div className="heading"><span className="overline">03 · PROPOSAL</span><h2>Запрос клиента</h2><p>Предложение не меняет текущую утверждённую версию.</p></div>
          <form onSubmit={e=>{e.preventDefault();void run('Запрос на изменение',async()=>{if(!order)return;const record=await api.createChange(selectedToken('sales'),order.id,{reason,requested_quantity:Number(newQty)});await reloadWorkflows(order.id,record.id);});}}>
            <div className="grid two"><label>Запрошено, изделий<input required type="number" min="1" value={newQty} onChange={e=>setNewQty(e.target.value)}/></label><label>Причина запроса<input required value={reason} onChange={e=>setReason(e.target.value)}/></label></div>
            <button disabled={busy||!order} className="button neutral">Создать изменение</button>
          </form>
          {changes.length>0&&<label>Сохранённые заявки этого заказа
            <select aria-label="Выбрать сохранённое изменение" value={change?.id??''} onChange={e=>{
              const found=changes.find(item=>item.id===e.target.value);
              if(found)selectSavedWorkflow(changes,found.id);
            }}>{changes.map(item=><option key={item.id} value={item.id}>{item.requested_quantity??'—'} шт. · {item.status} · {item.reason}</option>)}</select>
          </label>}
          {change&&<div className="summary"><div><small>НЕУТВЕРЖДЁННОЕ ИЗМЕНЕНИЕ</small><strong>{change.requested_quantity} изделий</strong><span>База V{change.baseline_revision} · {change.status}</span></div><b>Запрос</b></div>}
        </section>
        <section className="panel">
          <div className="heading"><span className="overline">04–07 · APPROVALS</span><h2>Оценка и согласование</h2><p>Каждый шаг выполняется отдельно; сервер повторно проверяет версию и полномочия.</p></div>
          <div className="actions"><button className="button neutral" disabled={busy||!canAssess} onClick={()=>void run('Расчёт последствий',async()=>{if(!change)return;await api.assess(selectedToken('sales'),change.id);if(order)await reloadWorkflows(order.id,change.id);})}>1. Рассчитать</button><button className="button neutral" disabled={busy||!canSubmit} onClick={()=>void run('Передача руководителю',async()=>{if(!change)return;await api.submit(selectedToken('sales'),change.id);if(order)await reloadWorkflows(order.id,change.id);})}>2. На согласование</button></div>
          {assessment&&<div className="assessment"><div><small>ГОТОВНОСТЬ</small><strong>{assessment.readiness}</strong></div><div><small>ИЗМЕНЕНИЕ ВЫРУЧКИ</small><strong>{rubles(assessment.delta_revenue_kopeks)}</strong></div>{assessment.issues.length>0&&<p>Ограничения: {assessment.issues.join(', ')}</p>}</div>}
          <label>Комментарий руководителя<input value={decisionNote} onChange={e=>setDecisionNote(e.target.value)}/></label>
          <div className="actions"><button className="button primary" disabled={busy||!canDecide} onClick={()=>void run('Утверждение руководителем',async()=>{if(!change||!assessment)return;await api.decision(selectedToken('approver'),change.id,assessment.fingerprint,'APPROVE',decisionNote);if(order)await reloadWorkflows(order.id,change.id);})}>3. Утвердить</button><button className="button warning" disabled={busy||!canDecide} onClick={()=>void run('Отказ руководителя',async()=>{if(!change||!assessment)return;await api.decision(selectedToken('approver'),change.id,assessment.fingerprint,'REJECT',decisionNote);if(order)await reloadWorkflows(order.id,change.id);})}>Отклонить</button></div>
          <div className="confirmation"><strong>Подтверждение клиента</strong><p>{change?.requested_quantity??order?.quantity??'—'} шт. · {rubles(order?.unit_sales_price_kopeks??null)} / шт. · {order?.delivery_date??'—'}</p><label>Источник подтверждения<input value={evidence} onChange={e=>setEvidence(e.target.value)}/></label><button className="button neutral" disabled={busy||!approved||accepted} onClick={()=>void run('Подтверждение клиента',async()=>{if(!change||!order)return;await api.accept(selectedToken('sales'),change.id,{quantity:change.requested_quantity??order.quantity,unit_sales_price_kopeks:order.unit_sales_price_kopeks,delivery_date:order.delivery_date,source_name:'synthetic-confirmation',evidence_text:evidence});await reloadWorkflows(order.id,change.id);})}>{accepted?'Подтверждение записано':'4. Зафиксировать подтверждение'}</button></div>
          <div className="final-action"><div><strong>Новая утверждённая версия</strong><p>История V1 не переписывается. Сервер создаёт V2 только после согласований.</p></div><button className="button primary" disabled={busy||!approved||!accepted} onClick={()=>void run('Применение V2',async()=>{if(!change||!order)return;await api.apply(selectedToken('approver'),change.id);await refresh(order.id);await reloadWorkflows(order.id,change.id);})}>5. Применить V2 →</button></div>
          <p className="footnote">После перезагрузки заполни локальные демо-роли и открой заказ по ID: расчёт, решение руководителя и подтверждение клиента будут восстановлены из FastAPI. Сервер повторно проверяет условия перед применением V2.</p>
        </section>
      </main>
      <aside><section className="panel history"><div className="heading"><span className="overline">IMMUTABLE SNAPSHOTS</span><h2>История версий</h2><p>Только утверждённые снимки заказа.</p></div>{history.length===0?<p className="empty">Создай или открой заказ — здесь появится V1.</p>:<ol>{history.map(rev=><li key={rev.id}><span className="bubble">V{rev.revision_number}</span><div><strong>{rev.quantity} изделий</strong><p>{rubles(rev.unit_sales_price_kopeks)} / шт.</p><small>До {rev.delivery_date}</small><small>{rev.approved_change_id?'После согласования':'Первоначальная версия'}</small></div></li>)}</ol>}<button className="button neutral full" disabled={busy||!order} onClick={()=>void run('Обновление истории',async()=>{if(order)await refresh(order.id);})}>Обновить историю ↻</button></section><div className="disclaimer"><b>Граница учебного MVP</b><p>Ролевые проверки выполняет FastAPI. Здесь нет производственной аутентификации, электронных подписей и реальных персональных данных.</p></div></aside>
      </div>
      <footer>HANDOFFGUARD AI · DATALALKS.CLUB ZOOMCAMP 2026 · SYNTHETIC DATA ONLY</footer>
    </div>
  </div>;
}