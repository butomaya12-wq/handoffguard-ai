/** The only UI-to-server boundary. No role is passed in JSON; server resolves the token. */
export type Order = {id:string; product_code:string; quantity:number; unit_sales_price_kopeks:number; unit_est_cost_kopeks:number|null; delivery_date:string; approved_source_id:string; revision:number; production_status:string; completed_quantity:number};
export type Revision = {id:string; revision_number:number; quantity:number; unit_sales_price_kopeks:number; delivery_date:string; approved_change_id:string|null; created_at:string};
export type CreateOrder = {product_code:string; quantity:number; unit_sales_price_kopeks:number; delivery_date:string; approved_source_id:string; unit_est_cost_kopeks?:number};
export type Change = {id:string;order_id:string;baseline_revision:number;reason:string;requested_quantity:number|null;status:string};
export type ChangeWorkflow = Change & {assessment:Assessment|null;customer_accepted:boolean};
export type Assessment = {readiness:string;fingerprint:string;delta_revenue_kopeks:number;issues:string[];proposed_quantity:number;proposed_delivery_date:string};
export type BusinessRole = 'sales' | 'production' | 'approver';
export type DashboardStatus =
  'DRAFT' | 'ASSESSMENT_REQUIRED' | 'PENDING_APPROVAL' |
  'INTERNALLY_APPROVED' | 'APPLIED' | 'REJECTED';
export type DashboardRow = {
  id:string; order_id:string; status:string; baseline_revision:number;
  current_order_revision:number; requested_quantity:number|null;
};
export type DashboardData = {
  total:number; by_status:Record<DashboardStatus,number>;
  unknown_count:number; filter:DashboardStatus|null; filtered_total:number;
  limit:number; items:DashboardRow[];
};

// Non-secret, random per-tab correlation ID. Never represents identity/authorization.
const TRACE_STORAGE_KEY='handoffguard-workflow-trace';
const UUID4=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function workflowTraceId():string{
  const existing=sessionStorage.getItem(TRACE_STORAGE_KEY);
  if(existing&&UUID4.test(existing))return existing;
  const bytes=globalThis.crypto.getRandomValues(new Uint8Array(16));
  bytes[6]=(bytes[6]&15)|64;
  bytes[8]=(bytes[8]&63)|128;
  const hex=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
  const trace=[hex.slice(0,8),hex.slice(8,12),hex.slice(12,16),hex.slice(16,20),hex.slice(20)].join('-');
  sessionStorage.setItem(TRACE_STORAGE_KEY,trace);
  return trace;
}

async function request<T>(path:string,token:string,method:'GET'|'POST'='GET',data?:object):Promise<T>{
  if(!token.trim())throw new Error('Введите токен нужной роли в панели демо.');
  const response=await fetch('/api/v1'+path,{method,headers:{Authorization:'Bearer '+token.trim(),'X-Workflow-Trace':workflowTraceId(),...(data?{'Content-Type':'application/json'}:{})},...(data?{body:JSON.stringify(data)}:{})});
  if(!response.ok){let reason='HTTP '+response.status;try{const body=(await response.json()) as {detail?:unknown};if(typeof body.detail==='string')reason=body.detail;}catch{/* Non-JSON response */}throw new Error(response.status+': '+reason);}
  return await response.json() as T;
}
const id=(value:string)=>encodeURIComponent(value);
export const api={
  currentSession:(token:string)=>request<{role:BusinessRole}>('/me',token),
  analytics:(token:string,status?:DashboardStatus)=>request<DashboardData>('/analytics/changes'+(status?'?status='+encodeURIComponent(status):''),token),
  createOrder:(token:string,data:CreateOrder)=>request<Order>('/orders',token,'POST',data),
  getOrder:(token:string,orderId:string)=>request<Order>('/orders/'+id(orderId),token),
  revisions:(token:string,orderId:string)=>request<Revision[]>('/orders/'+id(orderId)+'/revisions',token),
  getChange:(token:string,changeId:string)=>request<Change>('/changes/'+id(changeId),token),
  listChanges:(token:string,orderId:string)=>request<ChangeWorkflow[]>('/orders/'+id(orderId)+'/changes',token),
  productionReview:(token:string,orderId:string,data:{production_status:string;completed_quantity:number;feasibility:string;note:string})=>request<object>('/orders/'+id(orderId)+'/production-reviews',token,'POST',data),
  createChange:(token:string,orderId:string,data:{reason:string;requested_quantity:number})=>request<Change>('/orders/'+id(orderId)+'/changes',token,'POST',data),
  assess:(token:string,changeId:string)=>request<Assessment>('/changes/'+id(changeId)+'/assess',token,'POST'),
  submit:(token:string,changeId:string)=>request<Change>('/changes/'+id(changeId)+'/submit',token,'POST'),
  decision:(token:string,changeId:string,fingerprint:string,action:'APPROVE'|'REJECT',note:string)=>request<object>('/changes/'+id(changeId)+'/decision',token,'POST',{action,assessment_fingerprint:fingerprint,note}),
  accept:(token:string,changeId:string,data:{quantity:number;unit_sales_price_kopeks:number;delivery_date:string;source_name:string;evidence_text:string})=>request<object>('/changes/'+id(changeId)+'/customer-acceptance',token,'POST',data),
  apply:(token:string,changeId:string)=>request<{approved_revision:number}>('/changes/'+id(changeId)+'/apply',token,'POST')
};
export function toKopeks(text:string):number{
  const value=text.trim().replace(',','.');
  if(!/^\d+(?:\.\d{1,2})?$/.test(value))throw new Error('Стоимость должна содержать рубли и не более двух знаков после запятой.');
  const [whole,fraction='']=value.split('.');
  const amount=Number(whole)*100+Number(fraction.padEnd(2,'0'));
  if(!Number.isSafeInteger(amount))throw new Error('Слишком большая сумма.');
  return amount;
}
export const rubles=(kopeks:number|null)=>kopeks===null?'неизвестно':(kopeks/100).toLocaleString('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2})+' ₽';