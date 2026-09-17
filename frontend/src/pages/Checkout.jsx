import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Crown, Heart } from "lucide-react";
import axios from "axios";
import { useLanguage } from "@/i18n";
import { Shell } from "@/components/Shell";
import { API, BOOK_PRICES, COUNTRIES, loadMidtransSnap } from "@/lib/constants";

export default function Checkout() {
  const { text, language } = useLanguage();
  const [params] = useSearchParams();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [format, setFormat] = useState("Hardcover");
  const [country, setCountry] = useState("Other");
  const [paymentConfig, setPaymentConfig] = useState(null);
  const [form, setForm] = useState({ customer_name: "", email: "", address: "", city: "", postal_code: "" });
  const update = e => setForm({ ...form, [e.target.name]: e.target.value });
  const isIndonesia = country === "Indonesia";
  const price = BOOK_PRICES[format] || BOOK_PRICES.Hardcover;
  const displayPrice = isIndonesia ? price.idr : price.usd;
  const unavailable = paymentConfig && !(isIndonesia ? paymentConfig.midtrans_enabled : paymentConfig.stripe_enabled);
  useEffect(() => { axios.get(`${API}/payments/config`).then(r => setPaymentConfig(r.data)).catch(() => setPaymentConfig({})); }, []);

  const submit = async e => {
    e.preventDefault(); setError(""); setLoading(true);
    try {
      const payload = { ...form, story_id: params.get("story_id") || "demo", child_name: params.get("child_name") || "Story friend", format, gift_box: false, country, origin_url: window.location.origin };
      const { data } = await axios.post(`${API}/orders`, payload, { timeout: 20000, withCredentials: true });
      if (data.gateway === "stripe") { window.location.href = data.checkout_url; }
      else if (data.gateway === "midtrans") {
        const snap = await loadMidtransSnap();
        setLoading(false);
        snap.pay(data.snap_token, {
          onSuccess: () => { window.location.href = `/checkout/success?order_id=${data.id}`; },
          onPending: () => { window.location.href = `/checkout/success?order_id=${data.id}&pending=1`; },
          onError: () => setError(text.orderError),
          onClose: () => setError(""),
        });
      }
    } catch (err) {
      setError(typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : text.orderError);
      setLoading(false);
    }
  };

  return (
    <Shell>
      <main className="checkout checkout-page">
        <div className="checkout-summary" data-testid="checkout-summary">
          <div className="eyebrow" data-testid="checkout-eyebrow">{text.printOrders}</div>
          <h1 data-testid="checkout-title">{text.checkoutTitleA}<br /><em>{text.checkoutTitleB}</em></h1>
          <p data-testid="checkout-description">{text.checkoutDescription}</p>
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
            <select value={country} onChange={e => setCountry(e.target.value)} data-testid="customer-country-select">
              {COUNTRIES.map(c => <option key={c}>{c}</option>)}
            </select>
          </label>
          <button className="btn btn-primary full" disabled={loading || !paymentConfig || unavailable} data-testid="place-order-button">
            {loading ? <><span className="spinner" /> {text.paymentProcessing}</> : <>{text.placeOrder} · {displayPrice}</>}
          </button>
        </form>
      </main>
    </Shell>
  );
}
