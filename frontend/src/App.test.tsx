import {render,screen,cleanup} from '@testing-library/react';
import {describe,it,expect,afterEach} from 'vitest';
afterEach(cleanup);
import App from './App';
describe('workflow UI',()=>{
  it('shows real workflow stages, not fabricated revisions',()=>{
    render(<App/>);
    expect(screen.getByRole('heading',{name:'Первоначальный заказ'})).toBeTruthy();
    expect(screen.getByRole('heading',{name:'Проверка производства'})).toBeTruthy();
    expect(screen.getByRole('heading',{name:'История версий'})).toBeTruthy();
    expect(screen.getByText(/Создай или открой заказ/)).toBeTruthy();
  });
  it('cannot apply V2 until both approval steps',()=>{
    render(<App/>);
    const apply=screen.getByRole('button',{name:/Применить V2/}) as HTMLButtonElement;
    expect(apply.disabled).toBe(true);
  });
});