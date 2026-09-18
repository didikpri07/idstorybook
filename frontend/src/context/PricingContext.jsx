import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { API } from '@/lib/constants';
import { useAuth } from '@/context/AuthContext';

const PricingContext = createContext(null);
const REGION_KEY = 'idstorybook-pricing-region';
const storedRegion = () => { try { const r = localStorage.getItem(REGION_KEY); return ['ID', 'OTHER'].includes(r) ? r : null; } catch { return null; } };

export const PricingProvider = ({ children }) => {
  const { user } = useAuth();
  const [region, updateRegion] = useState(storedRegion);
  const [source, setSource] = useState(storedRegion() ? 'selected' : 'detecting');
  const [prices, setPrices] = useState(null);
  const [error, setError] = useState('');
  const [allowance, setAllowance] = useState(null);
  const manualChoice = useRef(Boolean(storedRegion()));
  const setRegion = value => {
    manualChoice.current = true; updateRegion(value); setSource('selected');
    try { localStorage.setItem(REGION_KEY, value); } catch { /* Selection still works in this session. */ }
  };
  const refresh = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/pricing`); setPrices(data); setError(''); return data; }
    catch { setError('pricing-unavailable'); return null; }
  }, []);
  const refreshAllowance = useCallback(async () => {
    if (!user) { setAllowance(null); return; }
    try { const { data } = await axios.get(`${API}/billing/allowance`); setAllowance(data); }
    catch { setAllowance(null); }
  }, [user]);
  useEffect(() => {
    refresh();
    const refreshOnFocus = () => refresh();
    window.addEventListener('focus', refreshOnFocus);
    return () => window.removeEventListener('focus', refreshOnFocus);
  }, [refresh]);
  useEffect(() => { refreshAllowance(); }, [refreshAllowance]);
  useEffect(() => {
    if (manualChoice.current) return;
    let active = true;
    axios.get(`${API}/region`, { timeout: 5000 }).then(({ data }) => {
      if (active && !manualChoice.current) { updateRegion(data.region); setSource(data.region ? 'detected' : 'unavailable'); }
    }).catch(() => { if (active && !manualChoice.current) setSource('unavailable'); });
    return () => { active = false; };
  }, []);
  return <PricingContext.Provider value={{ region, setRegion, source, prices, error, refresh, allowance, refreshAllowance }}>{children}</PricingContext.Provider>;
};

export const usePricing = () => useContext(PricingContext);
export const formatMoney = (minor, currency, language = 'en') => {
  if (minor === undefined || minor === null) return '—';
  return new Intl.NumberFormat(currency === 'IDR' ? 'id-ID' : 'en-US', {
    style: 'currency', currency, minimumFractionDigits: currency === 'IDR' ? 0 : 2,
    maximumFractionDigits: currency === 'IDR' ? 0 : 2,
  }).format(currency === 'USD' ? minor / 100 : minor);
};