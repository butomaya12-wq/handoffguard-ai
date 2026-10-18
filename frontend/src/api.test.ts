import {afterEach,describe,expect,it,vi} from 'vitest';
import {api,toKopeks,rubles} from './api';
afterEach(()=>{vi.unstubAllGlobals();sessionStorage.clear();});
describe('monetary conversion',()=>{
  it('uses exact integer kopeks',()=>{expect(toKopeks('1000,25')).toBe(100025);expect(toKopeks('0.01')).toBe(1);expect(rubles(null)).toBe('неизвестно');});
  it('rejects malformed values',()=>{expect(()=>toKopeks('1.234')).toThrow();expect(()=>toKopeks('-1')).toThrow();});
});
describe('API security boundary',()=>{
  it('sends bearer header, never request-body role',async()=>{
    const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({id:'demo'})});vi.stubGlobal('fetch',fetchMock);
    await api.createOrder('local-token',{product_code:'FRAME',quantity:100,unit_sales_price_kopeks:100000,delivery_date:'2026-11-12',approved_source_id:'synthetic'});
    const [url,config]=fetchMock.mock.calls[0] as [string,RequestInit];
    expect(url).toBe('/api/v1/orders');
    expect((config.headers as Record<string,string>).Authorization).toBe('Bearer local-token');
    expect(JSON.parse(String(config.body))).not.toHaveProperty('role');
  });
  it('uses the same non-secret workflow UUID4 for multiple API calls in a tab',async()=>{
    const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({id:'safe'})});
    vi.stubGlobal('fetch',fetchMock);
    await api.createOrder('secret-role-token',{product_code:'SYNTHETIC',quantity:100,unit_sales_price_kopeks:100000,delivery_date:'2026-11-12',approved_source_id:'synthetic'});
    await api.getOrder('secret-role-token','order-id');
    const header=(index:number)=>((fetchMock.mock.calls[index] as [string,RequestInit])[1].headers as Record<string,string>);
    const first=header(0)['X-Workflow-Trace'];
    const second=header(1)['X-Workflow-Trace'];
    expect(first).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(second).toBe(first);
    expect(first).not.toContain('secret-role-token');
    expect(sessionStorage.getItem('handoffguard-workflow-trace')).toBe(first);
  });
  it('preserves conflict details',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:409,json:async()=>({detail:'Baseline revision is stale'})}));
    await expect(api.getOrder('local','123')).rejects.toThrow('409: Baseline revision is stale');
  });
});