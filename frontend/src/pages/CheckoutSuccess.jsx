import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, Check } from "lucide-react";
import axios from "axios";
import { useLanguage } from "@/i18n";
import { Shell } from "@/components/Shell";
import { API } from "@/lib/constants";

export default function CheckoutSuccess() {
  const { text } = useLanguage();
  const [params] = useSearchParams();
  const orderId = params.get("order_id");
  const isPending = params.get("pending") === "1";
  const [payStatus, setPayStatus] = useState(isPending ? "pending" : "checking");

  useEffect(() => {
    if (!orderId || payStatus === "paid") return;
    const check = async () => {
      try {
        const { data } = await axios.get(`${API}/payments/status/${orderId}`);
        if (data.payment_status === "paid") setPayStatus("paid");
        else if (data.payment_status === "failed") setPayStatus("failed");
      } catch (err) { console.error("Payment status check failed:", err); }
    };
    check();
    const timer = setInterval(check, 3000);
    return () => clearInterval(timer);
  }, [orderId, payStatus]);

  const isPaid = payStatus === "paid";
  const isFailed = payStatus === "failed";

  return (
    <Shell>
      <div className="center-page" data-testid="checkout-success-page">
        <div className={`success-icon ${isFailed ? "failed" : ""}`}>
          {isFailed ? "✕" : isPaid ? <Check /> : <span className="spinner" />}
        </div>
        <div className="eyebrow">{isPaid ? text.confirmed : isFailed ? text.payFailedTitle : text.checkingPayment}</div>
        <h1>{isPaid ? text.paySuccessTitle : isFailed ? text.payFailedDesc : (isPending ? text.payPendingTitle : text.checkingPayment)}</h1>
        <p className="center-sub">{isPaid ? text.paySuccessDesc : isFailed ? text.payFailedDesc : text.payPendingDesc}</p>
        {isPaid && <Link to="/dashboard" className="btn btn-primary" data-testid="track-order-button">{text.track} <ArrowRight size={17} /></Link>}
        {isFailed && <Link to="/checkout" className="btn btn-coral" data-testid="retry-checkout-button">{text.payRetry} <ArrowRight size={17} /></Link>}
        {!isPaid && !isFailed && <Link to="/" className="text-link" data-testid="back-home-link">{text.backHome}</Link>}
      </div>
    </Shell>
  );
}
