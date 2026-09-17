import { useEffect, useState } from "react";
import { Package } from "lucide-react";
import axios from "axios";
import { useLanguage } from "@/i18n";
import { Shell } from "@/components/Shell";
import { API } from "@/lib/constants";

export default function Admin() {
  const { text, language } = useLanguage();
  const [orders, setOrders] = useState([]);

  useEffect(() => {
    axios.get(`${API}/admin/orders`, { withCredentials: true })
      .then(response => setOrders(response.data))
      .catch(err => console.error("Admin orders load failed:", err));
  }, []);

  const change = async (order, status) => {
    await axios.patch(`${API}/orders/${order.id}`, { status }, { withCredentials: true });
    setOrders(orders.map(item => item.id === order.id ? { ...item, status } : item));
  };

  const statusLabels = language === "id"
    ? { received: "Pesanan diterima", production: "Dalam produksi", shipped: "Dikirim" }
    : { received: "Order received", production: "In production", shipped: "Shipped" };

  return (
    <Shell>
      <main className="dashboard">
        <div className="dashboard-head">
          <div>
            <div className="eyebrow"><Package size={14} /> {text.adminEyebrow}</div>
            <h1>{text.printA} <em>{text.printB}</em></h1>
          </div>
          <span className="admin-badge">{text.adminView}</span>
        </div>
        <div className="metric-row">
          <div><span>{text.incoming}</span><b>{orders.length}</b></div>
          <div><span>{text.production}</span><b>{orders.filter(o => o.status === "In production").length}</b></div>
          <div><span>{text.shipped}</span><b>{orders.filter(o => o.status === "Shipped").length}</b></div>
        </div>
        <section className="orders-table">
          <div className="table-head"><span>{text.customer}</span><span>{text.book}</span><span>{text.orders}</span></div>
          {orders.length ? orders.map(order => (
            <div className="table-row" key={order.id} data-testid={`admin-order-${order.id}`}>
              <div><b>{order.customer_name}</b><small>{order.email}</small></div>
              <span>{order.format === "Hardcover" ? text.hardcover : text.softcover}</span>
              <select value={order.status} onChange={e => change(order, e.target.value)} data-testid={`order-status-${order.id}`}>
                <option value="Order received">{statusLabels.received}</option>
                <option value="In production">{statusLabels.production}</option>
                <option value="Shipped">{statusLabels.shipped}</option>
              </select>
            </div>
          )) : <div className="empty-order">{text.newOrders}</div>}
        </section>
      </main>
    </Shell>
  );
}
