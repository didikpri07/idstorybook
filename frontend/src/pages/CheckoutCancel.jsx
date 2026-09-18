import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRight, CreditCard } from 'lucide-react';
import { Shell } from '@/components/Shell';
import { useLanguage } from '@/i18n';

export default function CheckoutCancel() {
  const [params] = useSearchParams();
  const { language } = useLanguage();
  const id = language === 'id';
  const orderId = params.get('order_id');
  return <Shell><main className="center-page" data-testid="checkout-cancel-page"><div className="success-icon"><CreditCard /></div><h1 data-testid="checkout-cancel-title">{id ? 'Pembayaran ditutup.' : 'Checkout closed.'}</h1><p className="center-sub" data-testid="checkout-cancel-note">{id ? 'Detail pesananmu tersimpan. Periksa status pembayaran sebelum mencoba lagi.' : 'Your order details are saved. Check the payment status before trying again.'}</p><Link to={orderId ? `/payment/${orderId}` : '/dashboard'} className="btn btn-primary" data-testid="resume-payment-link">{id ? 'Lihat pesanan' : 'View my order'}<ArrowRight size={16} /></Link></main></Shell>;
}