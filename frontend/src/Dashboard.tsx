import {useEffect, useRef, useState} from 'react';
import {api, type DashboardData, type DashboardStatus} from './api';

const STATUSES: {key: DashboardStatus; label: string}[] = [
  {key:'DRAFT',label:'Черновики'},
  {key:'ASSESSMENT_REQUIRED',label:'Ожидают оценки'},
  {key:'PENDING_APPROVAL',label:'На согласовании'},
  {key:'INTERNALLY_APPROVED',label:'Внутренне одобрены'},
  {key:'APPLIED',label:'Применены'},
  {key:'REJECTED',label:'Отклонены'},
];
const captionFor=(status:string)=>STATUSES.find(item=>item.key===status)?.label??'Неизвестный статус';

export default function Dashboard({token}:{token:string}){
  const [data,setData]=useState<DashboardData|null>(null);
  const [filter,setFilter]=useState<DashboardStatus|''>('');
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const requestId=useRef(0);

  // Prevent showing cached data after the operator changes credentials.
  useEffect(()=>{
    requestId.current+=1;
    setData(null);
    setError('');
    setLoading(false);
  },[token]);

  async function load(next:DashboardStatus|''=filter){
    const id=++requestId.current;
    setLoading(true);
    setError('');
    try{
      const result=await api.analytics(token,next||undefined);
      if(id===requestId.current)setData(result);
    }catch(e){
      if(id===requestId.current){
        setData(null);
        setError(e instanceof Error?e.message:'Не удалось загрузить аналитику');
      }
    }finally{
      if(id===requestId.current)setLoading(false);
    }
  }

  return <section className="panel dashboard" aria-label="Бизнес-аналитика">
    <div className="heading">
      <span className="overline">BUSINESS ANALYTICS · READ ONLY</span>
      <h2>Дашборд изменений</h2>
      <p>Реальные статусы сохранённых заявок. Доступ: менеджер или руководитель. Данные не изменяются.</p>
    </div>
    <div className="dash-toolbar">
      <label>Фильтр статуса
        <select aria-label="Фильтр статуса" value={filter} onChange={event=>{
          const next=event.target.value as DashboardStatus|'';
          setFilter(next);
          if(data)void load(next);
        }}>
          <option value="">Все статусы</option>
          {STATUSES.map(item=><option key={item.key} value={item.key}>{item.label}</option>)}
        </select>
      </label>
      <button type="button" className="button neutral" disabled={loading} onClick={()=>void load()}>
        {loading?'Загружаем…':'Обновить аналитику ↻'}
      </button>
    </div>
    {error&&<p role="alert" className="alert error">Аналитика недоступна: {error}</p>}
    {!data&&!loading&&!error&&<p className="dash-hint">Введи токен менеджера или руководителя выше и нажми «Обновить аналитику».</p>}
    {data&&<>
      <div className="dash-kpis">
        <div className="dash-kpi"><small>Всего заявок</small><strong>{data.total.toLocaleString('ru-RU')}</strong></div>
        <div className="dash-kpi"><small>На согласовании</small><strong>{data.by_status.PENDING_APPROVAL.toLocaleString('ru-RU')}</strong></div>
        <div className="dash-kpi"><small>Внутренне одобрены</small><strong>{data.by_status.INTERNALLY_APPROVED.toLocaleString('ru-RU')}</strong></div>
        <div className="dash-kpi"><small>Применены</small><strong>{data.by_status.APPLIED.toLocaleString('ru-RU')}</strong></div>
        <div className="dash-kpi"><small>Отклонены</small><strong>{data.by_status.REJECTED.toLocaleString('ru-RU')}</strong></div>
      </div>
      <div className="dash-content">
        <div className="dash-plot" role="group" aria-label="Распределение заявок по статусам">
          <h3>Распределение статусов</h3>
          {data.total===0?<p className="dash-hint">Пока нет заявок на изменение. График появится после создания первой заявки.</p>:
          STATUSES.map(item=>{
            const count=data.by_status[item.key];
            return <div key={item.key} className="dash-bar-row">
              <div className="dash-bar-head"><span>{item.label}</span><b>{count}</b></div>
              <div className="dash-track" aria-label={item.label+': '+count+' из '+data.total} role="img">
                <span className="dash-fill" style={{width:(100*count/data.total)+'%'}}/>
              </div>
            </div>;
          })}
          {data.unknown_count>0&&<p className="dash-hint">Есть {data.unknown_count} заявок с нераспознанным статусом; они учтены в общем количестве.</p>}
        </div>
        <div className="dash-table-wrap">
          <h3>Заявки <small>Показано {data.items.length} из {data.filtered_total}; максимум {data.limit}</small></h3>
          {data.items.length===0?<p className="dash-hint">Для выбранного статуса заявок нет.</p>:
          <div className="dash-table-scroll"><table aria-label="Таблица заявок на изменения">
            <thead><tr><th scope="col">Заказ</th><th scope="col">Статус</th><th scope="col">Количество</th><th scope="col">Версия</th></tr></thead>
            <tbody>{data.items.map(item=><tr key={item.id}>
              <td title={item.order_id}><code>{item.order_id.slice(0,8)}</code></td>
              <td>{captionFor(item.status)}</td>
              <td>{item.requested_quantity??'—'}</td>
              <td>V{item.baseline_revision} → V{item.current_order_revision}</td>
            </tr>)}</tbody>
          </table></div>}
        </div>
      </div>
      <p className="footnote">Показатели относятся ко всем синтетическим заявкам в базе демо; фильтр меняет только таблицу, а не общие KPI. Порядок строк стабилен по UUID, не по дате создания. Без персональных данных и без автоматических решений.</p>
    </>}
  </section>;
}
