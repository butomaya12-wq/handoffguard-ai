import type {BusinessRole, OrderInboxData, OrderInboxItem} from './api';

type Props={
  data:OrderInboxData|null;
  role:BusinessRole;
  loading:boolean;
  error:string;
  busy:boolean;
  onRefresh:()=>void;
  onPage:(offset:number)=>void;
  onOpen:(item:OrderInboxItem)=>void;
};

const PRODUCTION_LABELS:Record<string,string>={
  NOT_STARTED:'Не начато',IN_PRODUCTION:'В производстве',COMPLETED:'Изготовлено',
};

export default function OrderInbox({data,role,loading,error,busy,onRefresh,onPage,onOpen}:Props){
  const isProduction=role==='production';
  return <section className="panel order-inbox" aria-label="Очередь заказов">
    <div className="heading">
      <span className="overline">LIVE ORDER INBOX · READ ONLY</span>
      <h2>{isProduction?'Очередь производства':'Список заказов'}</h2>
      <p>Заказы появляются здесь автоматически после сохранения менеджером. Открывать технический UUID не нужно.</p>
    </div>
    <div className="inbox-head">
      <div className="inbox-counter" role="status">
        <span className="inbox-alert-dot" aria-hidden="true"/>
        <strong>{data?.needs_review??'—'}</strong>
        <span>{isProduction?'Требуют проверки производства':'Ожидают производственной проверки'}</span>
      </div>
      <button type="button" className="button neutral" disabled={loading} onClick={onRefresh}>
        {loading?'Обновляем…':'Обновить список ↻'}
      </button>
    </div>
    {error&&<p className="alert error" role="alert">Не удалось загрузить очередь: {error}</p>}
    {!data&&!error&&<p className="dash-hint">Получаем актуальные заказы…</p>}
    {data&&data.total===0&&<p className="dash-hint">Заказов пока нет. Новый заказ появится здесь автоматически после сохранения менеджером.</p>}
    {data&&data.total>0&&<>
      <div className="inbox-list">
        {data.items.map(item=><article className={'inbox-item'+(item.needs_review?' requires-review':'')} key={item.id}>
          <div className="inbox-item-main">
            <div className="inbox-item-top">
              <strong>{item.product_code} <span>· V{item.revision}</span></strong>
              {item.needs_review?
                <span className="inbox-priority"><span className="inbox-alert-dot" aria-hidden="true"/>Требует проверки</span>
                :<span className="inbox-complete">Проверен для V{item.revision}</span>}
            </div>
            <p>{item.quantity} шт. · Срок {item.delivery_date} · {PRODUCTION_LABELS[item.production_status]??'Статус уточняется'}</p>
          </div>
          <button type="button" className="button neutral inbox-open" disabled={busy}
            onClick={()=>onOpen(item)}>{isProduction?'Открыть для проверки →':'Открыть заказ →'}</button>
        </article>)}
      </div>
      <div className="inbox-footer">
        <span>Показано {data.items.length} из {data.total} заказов</span>
        <div className="inbox-page-controls">
          <button className="button neutral" disabled={loading||data.offset===0}
            onClick={()=>onPage(Math.max(0,data.offset-data.limit))}>← Назад</button>
          <button className="button neutral" disabled={loading||data.offset+data.items.length>=data.total}
            onClick={()=>onPage(data.offset+data.limit)}>Далее →</button>
        </div>
      </div>
    </>}
    <p className="footnote">Список обновляется каждые 15 секунд при открытой странице приложения. Индикатор исчезает только после сохранённой производственной проверки текущей версии заказа. Это не push-уведомление при закрытом приложении.</p>
  </section>;
}
