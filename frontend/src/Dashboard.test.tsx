import {afterEach, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import Dashboard from './Dashboard';
import {api, type DashboardData} from './api';

afterEach(()=>{cleanup();vi.restoreAllMocks();sessionStorage.clear();});

const response:DashboardData={
  total:3,
  by_status:{DRAFT:1,ASSESSMENT_REQUIRED:0,PENDING_APPROVAL:1,INTERNALLY_APPROVED:0,APPLIED:1,REJECTED:0},
  unknown_count:0,filter:null,filtered_total:3,limit:25,
  items:[{id:'change-one',order_id:'3461fe89-712f-465a-a263-8694ed109d2b',
    status:'APPLIED',baseline_revision:1,current_order_revision:2,requested_quantity:120}],
};

describe('business analytics dashboard',()=>{
  it('loads verified role data automatically after login and opens a selected order',async()=>{
    const mock=vi.spyOn(api,'analytics').mockResolvedValue(response);
    const open=vi.fn();
    render(<Dashboard token="sales-test-token" onOpenOrder={open}/>);
    await waitFor(()=>expect(mock).toHaveBeenCalledWith('sales-test-token',undefined));
    expect(await screen.findByRole('group',{name:'Распределение заявок по статусам'})).toBeTruthy();
    expect(screen.getByRole('img',{name:'Применены: 1 из 3'})).toBeTruthy();
    expect(screen.getByRole('table',{name:'Таблица заявок на изменения'})).toBeTruthy();
    expect(screen.getByText('3461fe89')).toBeTruthy();
    expect(screen.getByText('V1 → V2')).toBeTruthy();
    expect(screen.getByText('Показано 1 из 3; максимум 25')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'Открыть заказ →'}));
    expect(open).toHaveBeenCalledWith('3461fe89-712f-465a-a263-8694ed109d2b');
  });

  it('applies a typed server-side status filter and keeps overall totals',async()=>{
    const filtered={...response,filter:'APPLIED' as const,filtered_total:1};
    const mock=vi.spyOn(api,'analytics')
      .mockResolvedValueOnce(response)
      .mockResolvedValueOnce(filtered);
    render(<Dashboard token="sales-token"/>);
    await screen.findByRole('table',{name:'Таблица заявок на изменения'});
    fireEvent.change(screen.getByLabelText('Фильтр статуса'),{target:{value:'APPLIED'}});
    await waitFor(()=>expect(mock).toHaveBeenCalledWith('sales-token','APPLIED'));
    expect(await screen.findByText('Показано 1 из 1; максимум 25')).toBeTruthy();
  });

  it('shows an honest empty state without fabricated bars or rows',async()=>{
    vi.spyOn(api,'analytics').mockResolvedValue({
      ...response,total:0,filtered_total:0,items:[],
      by_status:{DRAFT:0,ASSESSMENT_REQUIRED:0,PENDING_APPROVAL:0,INTERNALLY_APPROVED:0,APPLIED:0,REJECTED:0},
    });
    render(<Dashboard token="sales-token"/>);
    expect(await screen.findByText(/Пока нет заявок на изменение/)).toBeTruthy();
    expect(screen.getByText(/Для выбранного статуса заявок нет/)).toBeTruthy();
    expect(screen.queryByRole('table',{name:'Таблица заявок на изменения'})).toBeNull();
  });

  it('clears old chart data and rejects stale pending results after token changes',async()=>{
    const releases:((data:DashboardData)=>void)[]=[];
    const mock=vi.spyOn(api,'analytics').mockImplementation(
      ()=>new Promise(resolve=>{releases.push(resolve);})
    );
    const {rerender}=render(<Dashboard token="old-token"/>);
    await waitFor(()=>expect(mock).toHaveBeenCalledTimes(1));
    rerender(<Dashboard token="new-token"/>);
    await waitFor(()=>expect(mock).toHaveBeenCalledTimes(2));
    releases[0](response);
    await waitFor(()=>expect(screen.queryByText('3461fe89')).toBeNull());
    const empty={...response,total:0,filtered_total:0,items:[]};
    releases[1](empty);
    expect(await screen.findByText(/Для выбранного статуса заявок нет/)).toBeTruthy();
    expect(screen.queryByText('3461fe89')).toBeNull();
  });

  it('renders authorization failures without displaying a fake chart',async()=>{
    vi.spyOn(api,'analytics').mockRejectedValue(new Error('403: Insufficient role'));
    render(<Dashboard token="production-token"/>);
    expect(await screen.findByRole('alert')).toHaveProperty('textContent',
      'Аналитика недоступна: 403: Insufficient role');
    expect(screen.queryByRole('group',{name:'Распределение заявок по статусам'})).toBeNull();
  });
});
