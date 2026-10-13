import {afterEach,describe,expect,it,vi} from 'vitest';
import {api,toKopeks,rubles} from './api';
afterEach(()=>vi.unstubAllGlobals());
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
  it('preserves conflict details',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:409,json:async()=>({detail:'Baseline revision is stale'})}));
    await expect(api.getOrder('local','123')).rejects.toThrow('409: Baseline revision is stale');
  });
});