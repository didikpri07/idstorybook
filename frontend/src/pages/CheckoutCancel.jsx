import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useLanguage } from "@/i18n";
import { Shell } from "@/components/Shell";

export default function CheckoutCancel() {
  const { text } = useLanguage();
  const [params] = useSearchParams();
  const orderId = params.get("order_id");
  return (
    <Shell>
      <div className="center-page" data-testid="checkout-cancel-page">
        <div className="success-icon" style={{ background: "var(--clr-coral, #f97316)" }}>✕</div>
        <div className="eyebrow">{text.payCancelTitle}</div>
        <h1>{text.payCancelTitle}</h1>
        <p className="center-sub">{text.payCancelDesc}</p>
        <Link to={orderId ? `/checkout` : "/dashboard"} className="btn btn-coral" data-testid="retry-checkout-button">
          {text.payRetry} <ArrowRight size={17} />
        </Link>
      </div>
    </Shell>
  );
}
