import {render,screen,cleanup,fireEvent,waitFor} from '@testing-library/react';
import {describe,it,expect,afterEach,vi} from 'vitest';
afterEach(()=>{cleanup();vi.unstubAllGlobals();sessionStorage.clear();});
import App,{roleToken} from './App';
describe('workflow UI',()=>{
  it('shows real workflow stages, not fabricated revisions',()=>{
    render(<App/>);
    // Deployment proof marker is visible only in the candidate cloud build.
    expect(screen.getByText(/CD-PROOF-01/)).toBeTruthy();
    expect(screen.getByRole('heading',{name:'Первоначальный заказ'})).toBeTruthy();
    expect(screen.getByRole('heading',{name:'Проверка производства'})).toBeTruthy();
    expect(screen.getByRole('heading',{name:'История версий'})).toBeTruthy();
    expect(screen.getByText(/Создай или открой заказ/)).toBeTruthy();
  });
  it('restores an already approved change from server after opening V1',async()=>{
    const saved={
      id:'change-one',order_id:'order-one',baseline_revision:1,
      reason:'Customer requested larger order',requested_quantity:120,
      status:'INTERNALLY_APPROVED',
      assessment:{fingerprint:'a'.repeat(64),readiness:'READY_FOR_APPROVAL',
        delta_revenue_kopeks:2000000,proposed_quantity:120,
        proposed_delivery_date:'2026-11-12',issues:[]},
      customer_accepted:false
    };
    const response=(result:unknown)=>({ok:true,json:async()=>result});
    vi.stubGlobal('fetch',vi.fn(async (url:string)=>{
      if(url.endsWith('/orders/order-one/revisions'))return response([{
        id:'v1',revision_number:1,quantity:100,
        unit_sales_price_kopeks:100000,delivery_date:'2026-11-12',
        approved_change_id:null,created_at:'2026-10-13'
      }]);
      if(url.endsWith('/orders/order-one/changes'))return response([saved]);
      if(url.endsWith('/orders/order-one'))return response({
        id:'order-one',product_code:'FRAME-01',quantity:100,
        unit_sales_price_kopeks:100000,unit_est_cost_kopeks:60000,
        delivery_date:'2026-11-12',approved_source_id:'synthetic',
        revision:1,production_status:'NOT_STARTED',completed_quantity:0
      });
      throw new Error('Unexpected request '+url);
    }));
    render(<App/>);
    fireEvent.change(screen.getByLabelText('Token sales'),{target:{value:'demo-sales'}});
    fireEvent.change(screen.getByLabelText('Order ID'),{target:{value:'order-one'}});
    fireEvent.click(screen.getByRole('button',{name:'Открыть'}));
    await waitFor(()=>expect(screen.getByText(/База V1 · INTERNALLY_APPROVED/)).toBeTruthy());
    expect((screen.getByRole('button',{name:'4. Зафиксировать подтверждение'}) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByRole('button',{name:/Применить V2/}) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/20 000,00 ₽/)).toBeTruthy();
  });
  it('ignores browser autofilled role values when local demo mode is active',()=>{
    const wrongAutofill={sales:'demo-approver',production:'demo-sales',approver:'demo-production'};
    expect(roleToken('sales',wrongAutofill,true)).toBe('demo-sales');
    expect(roleToken('production',wrongAutofill,true)).toBe('demo-production');
    expect(roleToken('approver',wrongAutofill,true)).toBe('demo-approver');
    expect(roleToken('sales',wrongAutofill,false)).toBe('demo-approver');
  });
  it('cannot apply V2 until both approval steps',()=>{
    render(<App/>);
    const apply=screen.getByRole('button',{name:/Применить V2/}) as HTMLButtonElement;
    expect(apply.disabled).toBe(true);
  });
});