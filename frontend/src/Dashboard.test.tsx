import {afterEach, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import Dashboard from './Dashboard';
import {api, type DashboardData} from './api';

afterEach(()=>{cleanup();vi.restoreAllMocks();sessionStorage.clear();});

const response:DashboardData={
  total:3,
  by_status:{
    DRAFT:1,ASSESSMENT_REQUIRED:0,PENDING_APPROVAL:1,
    INTERNALLY_APPROVED:0,APPLIED:1,REJECTED:0,
  },
  unknown_count:0,filter:null,filtered_total:3,limit:25,
  items:[{id:'change-one',order_id:'3461fe89-712f-465a-a263-8694ed109d2b',
    status:'APPLIED',baseline_revision:1,current_order_revision:2,requested_quantity:120}],
};

describe('business analytics dashboard',()=>{
  it('loads actual API data when requested and displays KPI, chart and rows',async()=>{
    const mock=vi.spyOn(api,'analytics').mockResolvedValue(response);
    render(<Dashboard token="sales-test-token"/>);
    expect(screen.getByText(/Введи токен менеджера/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:/Обновить аналитику/}));
    await waitFor(()=>expect(mock).toHaveBeenCalledWith('sales-test-token',undefined));
    expect(screen.getByRole('group',{name:'Распределение заявок по статусам'})).toBeTruthy();
    expect(screen.getByRole('img',{name:'Применены: 1 из 3'})).toBeTruthy();
    expect(screen.getByRole('table',{name:'Таблица заявок на изменения'})).toBeTruthy();
    expect(screen.getByText('3461fe89')).toBeTruthy();
    expect(screen.getByText('V1 → V2')).toBeTruthy();
    expect(screen.getByText('Показано 1 из 3; максимум 25')).toBeTruthy();
  });

  it('applies a typed server-side status filter and keeps overall totals',async()=>{
    const filtered={...response,filter:'APPLIED' as const,filtered_total:1};
    const mock=vi.spyOn(api,'analytics')
      .mockResolvedValueOnce(response)
      .mockResolvedValueOnce(filtered);
    render(<Dashboard token="sales-token"/>);
    fireEvent.click(screen.getByRole('button',{name:/Обновить аналитику/}));
    await waitFor(()=>expect(mock).toHaveBeenCalledTimes(1));
    await screen.findByRole('table',{name:'Таблица заявок на изменения'});
    fireEvent.change(screen.getByLabelText('Фильтр статуса'),{target:{value:'APPLIED'}});
    await waitFor(()=>expect(mock).toHaveBeenCalledWith('sales-token','APPLIED'));
    expect(screen.getByText('Показано 1 из 1; максимум 25')).toBeTruthy();
  });

  it('shows an honest empty state without fabricated bars or rows',async()=>{
    vi.spyOn(api,'analytics').mockResolvedValue({
      ...response,total:0,filtered_total:0,items:[],
      by_status:{DRAFT:0,ASSESSMENT_REQUIRED:0,PENDING_APPROVAL:0,INTERNALLY_APPROVED:0,APPLIED:0,REJECTED:0},
    });
    render(<Dashboard token="sales-token"/>);
    fireEvent.click(screen.getByRole('button',{name:/Обновить аналитику/}));
    expect(await screen.findByText(/Пока нет заявок на изменение/)).toBeTruthy();
    expect(screen.getByText(/Для выбранного статуса заявок нет/)).toBeTruthy();
    expect(screen.queryByRole('table',{name:'Таблица заявок на изменения'})).toBeNull();
  });

  it('clears previous data and never renders a stale pending response after token changes',async()=>{
    let release!:(value:DashboardData)=>void;
    vi.spyOn(api,'analytics').mockReturnValue(new Promise(resolve=>{release=resolve;}));
    const {rerender}=render(<Dashboard token="old-token"/>);
    fireEvent.click(screen.getByRole('button',{name:/Обновить аналитику/}));
    rerender(<Dashboard token="new-token"/>);
    release(response);
    await waitFor(()=>expect(screen.queryByText('3461fe89')).toBeNull());
    expect(screen.getByText(/Введи токен менеджера/)).toBeTruthy();
  });

  it('renders authorization failures without displaying a fake chart',async()=>{
    vi.spyOn(api,'analytics').mockRejectedValue(new Error('403: Insufficient role'));
    render(<Dashboard token="production-token"/>);
    fireEvent.click(screen.getByRole('button',{name:/Обновить аналитику/}));
    expect(await screen.findByRole('alert')).toHaveProperty('textContent',
      'Аналитика недоступна: 403: Insufficient role');
    expect(screen.queryByRole('group',{name:'Распределение заявок по статусам'})).toBeNull();
  });
});
