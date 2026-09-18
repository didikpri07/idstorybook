import { Link } from 'react-router-dom';
import { Gift } from 'lucide-react';
import { usePricing, formatMoney } from '@/context/PricingContext';
import { useLanguage } from '@/i18n';
import { useAuth } from '@/context/AuthContext';
import { RegionSelector } from '@/components/RegionSelector';

export const CreationPrice = ({ pages }) => {
  const { language } = useLanguage();
  const id = language === 'id';
  const { user } = useAuth();
  const { prices, region, allowance, error } = usePricing();
  const table = region && prices?.regions[region];
  const row = table?.prices.find(r => r.pages === Number(pages));
  const free = Number(pages) === 8 && (user ? allowance?.free_book_available : true);
  return <section className="creation-price-summary" data-testid="creation-price-summary"><RegionSelector testId="create-region-select" compact />
    <div className="creation-price-total"><span data-testid="create-price-label">{id ? 'Buku cerita digital' : 'Digital storybook'}</span><b data-testid="create-total-price">{free ? (id ? 'Gratis' : 'Free') : row ? formatMoney(row.digital, table.currency) : '—'}</b></div>
    {free && <span className="free-allowance" data-testid="free-book-allowance"><Gift size={15} />{id ? 'Buku 8 halaman gratis pertama · satu per akun' : 'First free 8-page book · one per account'}</span>}
    {Number(pages) !== 8 && (!user || allowance?.free_book_available) && <span className="creation-price-note" data-testid="eight-pages-free-note">{id ? 'Pilih 8 halaman untuk menggunakan buku gratis pertamamu.' : 'Choose 8 pages to use your first free book.'}</span>}
    <small className="creation-price-note" data-testid="creation-payment-note">{free ? (id ? 'Termasuk ilustrasi, narasi, dan PDF gratis.' : 'Illustrations, narration, and free PDF included.') : (id ? 'Cerita dibuat setelah pembayaran terkonfirmasi. Unduhan PDF selalu gratis.' : 'Generation starts after payment is confirmed. PDF downloads are always free.')}</small>
    {!free && region === 'OTHER' && <small className="creation-price-note" data-testid="stripe-test-mode-note">{id ? 'Pembayaran internasional masih dalam mode uji Stripe.' : 'International payments are currently in Stripe test mode.'}</small>}
    {error && <span role="alert" className="error-message" data-testid="create-pricing-error">{id ? 'Harga belum dapat dimuat. Muat ulang halaman sebelum melanjutkan.' : 'Prices are unavailable. Reload before continuing.'}</span>}
    <Link to="/pricing" target="_blank" rel="noopener noreferrer" data-testid="create-view-pricing">{id ? 'Lihat semua harga' : 'View all prices'}</Link>
  </section>;
};