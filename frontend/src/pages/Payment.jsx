import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowRight, Check, CreditCard, LockKeyhole, RefreshCw } from 'lucide-react';
import axios from 'axios';
import { API } from '@/lib/constants';
import { Shell } from '@/components/Shell';
import { Button } from '@/components/ui/button';
import { useLanguage } from '@/i18n';
import { usePricing, formatMoney } from '@/context/PricingContext';

export default function Payment() {
  const { language } = useLanguage();
  const id = language === 'id';
  const route = useParams();
  const [params] = useSearchParams();
  const orderId = route.orderId || params.get('order_id');
  const navigate = useNavigate();
  const { refreshAllowance } = usePricing();
  const [order, setOrder] = useState(null);
  const [error, setError] = useState('');
  const [checkoutError, setCheckoutError] = useState('');
  const [busy, setBusy] = useState(false);
  const [checkKey, setCheckKey] = useState(0);
  useEffect(() => {
    let active = true, timer;
    if (!orderId) { setError(id ? 'Pesanan tidak ditemukan.' : 'No order was selected.'); return; }
    const check = async () => {
      try {
        const { data } = await axios.get(`${API}/payments/status/${orderId}`, { timeout: 18000 });
        if (!active) return;
        setOrder(data); setError('');
        if (data.payment_status === 'paid') {
          refreshAllowance();
          if (data.kind === 'digital') navigate(`/storybook/${data.story_id}`, { replace: true });
          return;
        }
        if (data.payment_status === 'refunded') return;
      } catch (e) {
        if (!active) return;
        if (e.response?.status === 401) { navigate(`/login?next=${encodeURIComponent(`/payment/${orderId}`)}`); return; }
        setError(e.response?.status === 404 ? (id ? 'Pesanan ini tidak ditemukan di akunmu.' : 'This order was not found in your account.') : (id ? 'Status pembayaran belum dapat diperiksa. Coba lagi sebentar.' : 'Payment status could not be checked. Please try again shortly.'));
        if (e.response?.status === 404) return;
      }
      if (active) timer = setTimeout(check, 3000);
    };
    check(); return () => { active = false; clearTimeout(timer); };
  }, [orderId, checkKey, id, navigate, refreshAllowance]);
  const pay = async () => {
    setBusy(true); setCheckoutError('');
    try { const { data } = await axios.post(`${API}/orders/${orderId}/checkout`, {}, { timeout: 30000 }); window.location.assign(data.checkout_url); }
    catch (e) { setCheckoutError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : (id ? 'Pembayaran belum bisa dibuka. Coba lagi.' : 'Checkout could not be opened. Please try again.')); setBusy(false); }
  };
  const paid = order?.payment_status === 'paid';
  const refunded = order?.payment_status === 'refunded';
  const failed = order?.payment_status === 'failed';
  const returning = params.get('returned') === '1' || window.location.pathname.includes('/checkout/success');
  return <Shell><main className="center-page payment-page" data-testid="payment-page"><div className="success-icon">{paid ? <Check /> : <CreditCard />}</div><div className="eyebrow" data-testid="payment-eyebrow">{paid ? (id ? 'Pembayaran terkonfirmasi' : 'Payment confirmed') : (id ? 'Pembayaran aman' : 'Secure checkout')}</div>
    <h1 data-testid="payment-title">{refunded ? (id ? 'Pembayaran dikembalikan.' : 'Payment refunded.') : paid ? (id ? 'Pesananmu sudah diterima.' : 'Your order is in.') : returning ? (id ? 'Memeriksa pembayaranmu…' : 'Checking your payment…') : (id ? 'Satu langkah lagi.' : 'One little step to go.')}</h1>
    <p className="center-sub" data-testid="payment-description">{refunded ? (id ? 'Dana pesanan ini telah dikembalikan.' : 'This order has been refunded.') : paid ? (id ? 'Lihat perkembangan pesanan di perpustakaanmu.' : 'Follow your print order in your library.') : failed ? (id ? 'Pembayaran belum berhasil. Kamu bisa mencoba lagi.' : 'Payment wasn’t completed. You can try again.') : returning ? (id ? 'Cerita baru dimulai setelah penyedia mengonfirmasi pembayaran.' : 'Your story starts only after the payment provider confirms payment.') : order?.kind === 'digital' ? (id ? 'Detail ceritamu tersimpan. Kami akan mulai membuat buku setelah pembayaran terkonfirmasi.' : 'Your story details are saved. We’ll start creating your book after payment is confirmed.') : (id ? 'Periksa pesanan cetakmu sebelum membayar.' : 'Review your printed book before paying.')}</p>
    {order && <section className="payment-order-summary" data-testid="payment-summary"><div><span>{order.child_name}</span><strong data-testid="payment-book-description">{order.page_count} {id ? 'halaman' : 'pages'} · {order.format}</strong></div><div><span>{id ? 'Total' : 'Total'}</span><b data-testid="payment-total">{formatMoney(order.amount_minor, order.currency)}</b></div><div><span>{id ? 'Metode pembayaran' : 'Payment provider'}</span><strong data-testid="payment-provider">{order.payment_gateway === 'midtrans' ? 'Midtrans' : 'Stripe · Test mode'}</strong></div></section>}
    {(error || checkoutError) && <div className="error-message payment-error" role="alert" data-testid="payment-error">{checkoutError || error}</div>}
    <div className="payment-actions">{order && !paid && !refunded && <Button className="btn btn-primary" onClick={pay} disabled={busy} data-testid="pay-order-button">{busy ? <span className="spinner" /> : <><LockKeyhole size={16} />{id ? 'Lanjutkan pembayaran' : 'Continue to payment'}<ArrowRight size={16} /></>}</Button>}
      {!paid && orderId && <Button variant="ghost" onClick={() => setCheckKey(k => k + 1)} data-testid="check-payment-button"><RefreshCw size={14} />{id ? 'Periksa status pembayaran' : 'Check payment status'}</Button>}
      <Link to="/dashboard" className="text-link" data-testid="payment-back-library">{id ? 'Kembali ke perpustakaan' : 'Back to my library'}</Link>
    </div>
    {order?.payment_gateway === 'stripe' && <p className="payment-mode-note" data-testid="payment-test-mode">{id ? 'Mode uji Stripe: tidak ada pembayaran sungguhan.' : 'Stripe test mode: no real payment is collected.'}</p>}
    {order?.payment_gateway === 'midtrans' && !paid && <p className="payment-mode-note" data-testid="payment-live-mode">{id ? 'Midtrans menggunakan pembayaran sungguhan. Konfirmasi jumlah sebelum membayar.' : 'Midtrans uses real payments. Confirm the amount before paying.'}</p>}
  </main></Shell>;
}