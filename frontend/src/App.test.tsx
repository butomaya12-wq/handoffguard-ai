import {render,screen,cleanup,fireEvent,waitFor,within} from '@testing-library/react';
import {describe,it,expect,afterEach,vi} from 'vitest';
import App from './App';
import {api,type BusinessRole,type DashboardData} from './api';

afterEach(()=>{cleanup();vi.restoreAllMocks();sessionStorage.clear();});

const dashboard:DashboardData={
  total:0,
  by_status:{DRAFT:0,ASSESSMENT_REQUIRED:0,PENDING_APPROVAL:0,INTERNALLY_APPROVED:0,APPLIED:0,REJECTED:0},
  unknown_count:0,filter:null,filtered_total:0,limit:25,items:[],
};

async function login(role:BusinessRole){
  const check=vi.spyOn(api,'currentSession').mockResolvedValue({role});
  vi.spyOn(api,'analytics').mockResolvedValue(dashboard);
  render(<App/>);
  expect(screen.queryByRole('navigation',{name:'Основная навигация'})).toBeNull();
  fireEvent.change(screen.getByLabelText('Ключ доступа'),{target:{value:'synthetic-role-key'}});
  fireEvent.click(screen.getByRole('button',{name:/Войти в рабочее пространство/}));
  await waitFor(()=>expect(check).toHaveBeenCalledWith('synthetic-role-key'));
  return await screen.findByRole('navigation',{name:'Основная навигация'});
}

describe('role-gated navigation and one-token login',()=>{
  it('denies invalid credentials before showing any app navigation',async()=>{
    const check=vi.spyOn(api,'currentSession').mockRejectedValue(new Error('401: Invalid token'));
    render(<App/>);
    fireEvent.change(screen.getByLabelText('Ключ доступа'),{target:{value:'wrong'}});
    fireEvent.click(screen.getByRole('button',{name:/Войти в рабочее пространство/}));
    expect(await screen.findByRole('alert')).toHaveProperty('textContent','Не удалось войти: 401: Invalid token');
    expect(check).toHaveBeenCalledWith('wrong');
    expect(screen.queryByRole('navigation',{name:'Основная навигация'})).toBeNull();
  });

  it('lands sales on dashboard and keeps their allowed workflow in separate screens',async()=>{
    const nav=await login('sales');
    expect(within(nav).getByRole('button',{name:/Обзор/})).toBeTruthy();
    expect(within(nav).getByRole('button',{name:/Заказы/})).toBeTruthy();
    expect(within(nav).getByRole('button',{name:/Изменения/})).toBeTruthy();
    expect(within(nav).getByRole('button',{name:/История версий/})).toBeTruthy();
    expect(within(nav).queryByRole('button',{name:/Производство/})).toBeNull();
    expect(within(nav).queryByRole('button',{name:/Согласования/})).toBeNull();
    expect(await screen.findByRole('heading',{name:'Дашборд изменений'})).toBeTruthy();
    fireEvent.click(within(nav).getByRole('button',{name:/Заказы/}));
    expect(screen.getByRole('heading',{name:'Создать заказ V1'})).toBeTruthy();
    expect(screen.queryByRole('heading',{name:'Дашборд изменений'})).toBeNull();
    fireEvent.click(within(nav).getByRole('button',{name:/Изменения/}));
    expect(screen.getByRole('heading',{name:'Оценка последствий'})).toBeTruthy();
    fireEvent.click(within(nav).getByRole('button',{name:/История версий/}));
    expect(screen.getByRole('heading',{name:'История версий заказа'})).toBeTruthy();
  });

  it('production role gets its own inspection page, never global dashboard or approval',async()=>{
    const nav=await login('production');
    expect(within(nav).queryByRole('button',{name:/Обзор/})).toBeNull();
    expect(within(nav).getByRole('button',{name:/Производство/})).toBeTruthy();
    expect(within(nav).queryByRole('button',{name:/Согласования/})).toBeNull();
    expect(within(nav).queryByRole('button',{name:/Изменения/})).toBeNull();
    expect(screen.queryByRole('heading',{name:'Дашборд изменений'})).toBeNull();
    fireEvent.click(within(nav).getByRole('button',{name:/Производство/}));
    expect(screen.getByRole('heading',{name:'Проверка производства'})).toBeTruthy();
    expect((screen.getByRole('button',{name:'Сохранить проверку'}) as HTMLButtonElement).disabled).toBe(true);
  });

  it('approver opens saved state via a single role token; apply remains blocked before customer acceptance',async()=>{
    const nav=await login('approver');
    const saved={
      id:'change-one',order_id:'order-one',baseline_revision:1,
      reason:'Customer requested larger order',requested_quantity:120,
      status:'PENDING_APPROVAL',
      assessment:{fingerprint:'a'.repeat(64),readiness:'READY_FOR_APPROVAL',
        delta_revenue_kopeks:2000000,proposed_quantity:120,
        proposed_delivery_date:'2026-11-12',issues:[]},
      customer_accepted:false,
    };
    vi.spyOn(api,'getOrder').mockResolvedValue({
      id:'order-one',product_code:'FRAME-01',quantity:100,
      unit_sales_price_kopeks:100000,unit_est_cost_kopeks:60000,
      delivery_date:'2026-11-12',approved_source_id:'synthetic',
      revision:1,production_status:'NOT_STARTED',completed_quantity:0,
    });
    vi.spyOn(api,'revisions').mockResolvedValue([{
      id:'v1',revision_number:1,quantity:100,
      unit_sales_price_kopeks:100000,delivery_date:'2026-11-12',
      approved_change_id:null,created_at:'2026-10-13',
    }]);
    const changes=vi.spyOn(api,'listChanges').mockResolvedValue([saved]);
    fireEvent.click(within(nav).getByRole('button',{name:/Заказы/}));
    fireEvent.change(screen.getByLabelText('Order ID'),{target:{value:'order-one'}});
    fireEvent.click(screen.getByRole('button',{name:'Открыть заказ →'}));
    await waitFor(()=>expect(changes).toHaveBeenCalledWith('synthetic-role-key','order-one'));
    fireEvent.click(within(nav).getByRole('button',{name:/Согласования/}));
    expect((screen.getByRole('button',{name:'Утвердить'}) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByRole('button',{name:/Применить V2/}) as HTMLButtonElement).disabled).toBe(true);
    expect(within(nav).queryByRole('button',{name:/Производство/})).toBeNull();
    expect(within(nav).queryByRole('button',{name:/Изменения/})).toBeNull();
  });

  it('logout removes active credentials and selected order from memory',async()=>{
    await login('sales');
    sessionStorage.setItem('handoffguard-demo-order-id','test-order');
    fireEvent.click(screen.getByRole('button',{name:/Выйти из системы/}));
    expect(screen.getByLabelText('Ключ доступа')).toBeTruthy();
    expect(sessionStorage.getItem('handoffguard-demo-order-id')).toBeNull();
    expect(screen.queryByRole('navigation',{name:'Основная навигация'})).toBeNull();
  });
});
