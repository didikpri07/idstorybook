import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Crown, Heart } from "lucide-react";
import axios from "axios";
import { useLanguage } from "@/i18n";
import { Shell } from "@/components/Shell";
import { API, COUNTRIES } from "@/lib/constants";
import { usePricing, formatMoney } from '@/context/PricingContext';
import { useAuth } from '@/context/AuthContext';

export default function Checkout() {
  const { text, language } = useLanguage();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { prices, region, setRegion, refresh } = usePricing();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [format, setFormat] = useState("Hardcover");
  const [country, setCountry] = useState(region === 'ID' ? 'Indonesia' : region ? 'Other' : '');
  const [story, setStory] = useState(null);
  const countryEdited = useRef(false);
  const requestId = useRef(crypto.randomUUID());
  const submitting = useRef(false);
  const [paymentConfig, setPaymentConfig] = useState(null);
  const [form, setForm] = useState({ customer_name: user?.name || '', email: user?.email || '', address: "", city: "", postal_code: "" });
  const update = e => setForm({ ...form, [e.target.name]: e.target.value });
  const isIndonesia = country === "Indonesia";
  const table = prices?.regions[isIndonesia ? 'ID' : 'OTHER'];
  const row = table?.prices.find(r => r.pages === story?.page_count);
  const amount = row?.[format.toLowerCase()];
  const displayPrice = amount !== undefined && country ? formatMoney(amount, table.currency) : '—';
  const unavailable = paymentConfig && !(isIndonesia ? paymentConfig.midtrans_enabled : paymentConfig.stripe_enabled);
  useEffect(() => { axios.get(`${API}/payments/config`).then(r => setPaymentConfig(r.data)).catch(() => setPaymentConfig({})); }, []);
  useEffect(() => { if (!countryEdited.current && region) setCountry(region === 'ID' ? 'Indonesia' : 'Other'); }, [region]);
  useEffect(() => {
    const storyId = params.get('story_id');
    if (!storyId) { setError(language === 'id' ? 'Pilih buku dari perpustakaanmu terlebih dahulu.' : 'Choose a book from your library first.'); return; }
    let active = true;
    axios.get(`${API}/stories/${storyId}`).then(({ data }) => {
      if (!active) return;
      if (!['complete', 'completed'].includes(data.status)) { setError(language === 'id' ? 'Selesaikan ceritamu sebelum memesan cetak.' : 'Finish your story before ordering a printed book.'); return; }
      setStory(data);
    }).catch(() => { if (active) setError(language === 'id' ? 'Buku tidak ditemukan di akunmu.' : 'This book was not found in your account.'); });
    return () => { active = false; };
  }, [params, language]);

  const submit = async e => {
    e.preventDefault(); if (submitting.current || !story || !row || !country) return;
    submitting.current = true; setError(""); setLoading(true);
    try {
      const payload = { ...form, story_id: story.id, format, country, expected_amount: amount, pricing_version: prices.version, request_id: requestId.current };
      const { data } = await axios.post(`${API}/orders`, payload, { timeout: 20000, withCredentials: true });
      navigate(`/payment/${data.id}`);
    } catch (err) {
      if (err.response?.status === 409) await refresh();
      setError(typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : text.orderError);
    } finally { setLoading(false); submitting.current = false; }
  };

  return (
    <Shell>
      <main className="checkout checkout-page">
        <div className="checkout-summary" data-testid="checkout-summary">
          <div className="eyebrow" data-testid="checkout-eyebrow">{text.printOrders}</div>
          <h1 data-testid="checkout-title">{text.checkoutTitleA}<br /><em>{text.checkoutTitleB}</em></h1>
          <p data-testid="checkout-description">{text.checkoutDescription}</p>
          {story && <p data-testid="checkout-book-details">{story.title} · {story.page_count} {language === 'id' ? 'halaman' : 'pages'}</p>}
          <div className="format-cards format-options">
            {["Hardcover", "Softcover"].map(f => (
              <button
                key={f}
                type="button"
                className={`format-card format-option ${format === f ? "chosen" : ""}`}
                onClick={() => setFormat(f)}
                data-testid={`format-${f.toLowerCase()}`}
              >
                {f === "Hardcover" ? <Crown size={20} /> : <Heart size={20} />}
                <b>{f === "Hardcover" ? text.hardcover : text.softcover}</b>
              </button>
            ))}
          </div>
          <div className="price-display" data-testid="price-display">
            <span>{language === 'id' ? 'Total' : 'Total'}</span>
            <b>{displayPrice}</b>
          </div>
          <small data-testid="checkout-payment-provider">{isIndonesia ? 'Midtrans' : 'Stripe · Test mode'}</small>
          <p className="creation-price-note" data-testid="print-additional-note">{language === 'id' ? 'Harga cetak terpisah dari pembelian buku digital. Unduhan PDF tetap gratis.' : 'Print price is additional to your digital purchase. PDF downloads remain free.'}</p>
        </div>
        <form className="checkout-form" onSubmit={submit} data-testid="checkout-form">
          {error && <div className="error-message" role="alert" data-testid="checkout-error">{error}</div>}
          {unavailable && <div className="error-message" role="status" data-testid="checkout-unavailable">{language === 'id' ? 'Pemesanan cetak untuk negara ini belum tersedia. Ceritamu tetap tersimpan.' : 'Print checkout for this country isn’t available yet. Your story is safely saved.'}</div>}
          <label>{text.fullName}<input name="customer_name" value={form.customer_name} onChange={update} required data-testid="customer-name-input" /></label>
          <label>{text.email}<input name="email" type="email" value={form.email} onChange={update} required data-testid="customer-email-input" /></label>
          <label>{text.address}<input name="address" value={form.address} onChange={update} required data-testid="customer-address-input" /></label>
          <div className="two-col">
            <label>{text.city}<input name="city" value={form.city} onChange={update} required data-testid="customer-city-input" /></label>
            <label>{text.postal}<input name="postal_code" value={form.postal_code} onChange={update} required data-testid="customer-postal-input" /></label>
          </div>
          <label>{text.country}
            <select value={country} required onChange={e => { countryEdited.current = true; setCountry(e.target.value); setRegion(e.target.value === 'Indonesia' ? 'ID' : 'OTHER'); }} data-testid="customer-country-select">
              <option value="" disabled>{language === 'id' ? 'Pilih negara' : 'Choose your country'}</option>
              {COUNTRIES.map(c => <option key={c}>{c}</option>)}
            </select>
          </label>
          <button className="btn btn-primary full" disabled={loading || !paymentConfig || unavailable || !story || !row || !country} data-testid="place-order-button">
            {loading ? <><span className="spinner" /> {text.paymentProcessing}</> : <>{text.placeOrder} · {displayPrice}</>}
          </button>
        </form>
      </main>
    </Shell>
  );
}
