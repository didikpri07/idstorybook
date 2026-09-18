import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Save, Tags } from 'lucide-react';
import axios from 'axios';
import { API } from '@/lib/constants';
import { Shell } from '@/components/Shell';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useLanguage } from '@/i18n';
import { usePricing } from '@/context/PricingContext';

export default function AdminPricing() {
  const { language } = useLanguage();
  const id = language === 'id';
  const { refresh } = usePricing();
  const [catalog, setCatalog] = useState(null);
  const [values, setValues] = useState({});
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/pricing`); setCatalog(data); setError('');
      const v = {}; Object.entries(data.regions).forEach(([region, table]) => { table.prices.forEach(row => ['digital', 'softcover', 'hardcover'].forEach(type => { v[`${region}-${row.pages}-${type}`] = String(row[type] / (region === 'OTHER' ? 100 : 1)); })); }); setValues(v);
    } catch { setError(id ? 'Harga belum dapat dimuat.' : 'Could not load prices.'); }
  }, [id]);
  useEffect(() => { load(); }, [load]);
  const submit = async e => {
    e.preventDefault(); setBusy(true); setSaved(false); setError('');
    try {
      const next = JSON.parse(JSON.stringify(catalog));
      for (const [region, table] of Object.entries(next.regions)) for (const row of table.prices) for (const type of ['digital', 'softcover', 'hardcover']) row[type] = Math.round(Number(values[`${region}-${row.pages}-${type}`]) * (region === 'OTHER' ? 100 : 1));
      await axios.put(`${API}/admin/pricing`, next); await load(); await refresh(); setSaved(true);
    } catch (e) { setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : (id ? 'Periksa semua harga dan coba lagi.' : 'Check all prices and try again.')); }
    finally { setBusy(false); }
  };
  return <Shell><main className="pricing-page admin-pricing-page"><Link to="/admin" className="back-link" data-testid="pricing-back-admin"><ArrowLeft size={15} />{id ? 'Pesanan admin' : 'Admin orders'}</Link><header className="pricing-heading"><div><div className="eyebrow" data-testid="admin-pricing-eyebrow"><Tags size={15} />{id ? 'Pengaturan harga' : 'Price settings'}</div><h1 data-testid="admin-pricing-title">{id ? 'Harga ' : 'Your '}<em>{id ? 'buku.' : 'price list.'}</em></h1><p data-testid="admin-pricing-description">{id ? 'Perubahan berlaku untuk pesanan baru. Pesanan yang sudah dibuat tidak berubah.' : 'Changes apply to new orders. Existing order totals stay the same.'}</p></div><Link to="/pricing" className="text-link" data-testid="admin-pricing-public-link">{id ? 'Lihat halaman harga' : 'View public pricing'}</Link></header>
    {error && <div className="error-message" role="alert" data-testid="admin-pricing-error">{error}<Button variant="ghost" onClick={load} data-testid="admin-pricing-reload">{id ? 'Muat ulang' : 'Reload'}</Button></div>}
    {saved && <div className="account-success" role="status" data-testid="admin-pricing-saved">{id ? 'Harga berhasil disimpan.' : 'Prices saved successfully.'}</div>}
    {!catalog && !error && <p data-testid="admin-pricing-loading">{id ? 'Memuat harga…' : 'Loading prices…'}</p>}
    {catalog && <form onSubmit={submit}>{Object.entries(catalog.regions).map(([region, table]) => <section className="admin-price-section" key={region}><h2 data-testid={`admin-region-${region}`}>{region === 'ID' ? 'Indonesia · IDR' : (id ? 'Negara lainnya · USD' : 'Other countries · USD')}</h2><div className="admin-price-grid"><div className="admin-price-head"><span>{id ? 'Halaman' : 'Pages'}</span>{['digital', 'softcover', 'hardcover'].map(type => <span key={type}>{type === 'digital' ? 'Digital' : type === 'softcover' ? (id ? 'Sampul lunak' : 'Softcover') : (id ? 'Sampul keras' : 'Hardcover')}</span>)}</div>{table.prices.map(row => <div className="admin-price-row" key={row.pages}><b data-testid={`admin-${region}-pages-${row.pages}`}>{row.pages}</b>{['digital', 'softcover', 'hardcover'].map(type => <Input key={type} type="number" inputMode="decimal" required min={region === 'ID' ? '1000' : '0.50'} max={region === 'ID' ? '100000000' : '1000000'} step={region === 'ID' ? '1' : '0.01'} aria-label={`${region} ${row.pages} ${type}`} value={values[`${region}-${row.pages}-${type}`] ?? ''} onChange={e => { setSaved(false); setValues(v => ({ ...v, [`${region}-${row.pages}-${type}`]: e.target.value })); }} data-testid={`price-input-${region}-${row.pages}-${type}`} />)}</div>)}</div></section>)}<div className="admin-price-footer"><p data-testid="admin-fixed-policy">{id ? 'Tetap termasuk: satu buku digital 8 halaman gratis per akun dan unduhan PDF gratis.' : 'Always included: one free 8-page digital book per account and free PDF downloads.'}</p><Button type="submit" className="btn btn-primary" disabled={busy} data-testid="save-prices-button"><Save size={16} />{busy ? (id ? 'Menyimpan…' : 'Saving…') : (id ? 'Simpan harga' : 'Save prices')}</Button></div></form>}
  </main></Shell>;
}