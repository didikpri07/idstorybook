import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BookOpen, Package, WandSparkles } from "lucide-react";
import axios from "axios";
import { useLanguage } from "@/i18n";
import { Shell } from "@/components/Shell";
import { useAuth } from "@/context/AuthContext";
import { API, resolveImage } from "@/lib/constants";

export default function Dashboard() {
  const { text } = useLanguage();
  const { user } = useAuth();
  const [stories, setStories] = useState([]);
  const [orders, setOrders] = useState([]);

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/stories`, { withCredentials: true }),
      axios.get(`${API}/orders`, { withCredentials: true }),
    ]).then(([sr, or]) => { setStories(sr.data); setOrders(or.data); })
      .catch(err => console.error("Dashboard load failed:", err));
  }, []);

  return (
    <Shell>
      <main className="dashboard">
        <div className="dashboard-head">
          <div>
            <div className="eyebrow">{text.welcomeBack}, <b>{user?.name?.split(" ")[0] || "there"}</b></div>
            <h1>{text.libraryTitleA} <em>{text.libraryTitleB}</em></h1>
          </div>
          <Link to="/create" className="btn btn-primary" data-testid="create-new-story-button">
            {text.createBook} <WandSparkles size={16} />
          </Link>
        </div>

        <section className="stories-grid" data-testid="stories-grid">
          <h2>{text.myStories}</h2>
          {stories.length ? (
            <div className="story-cards">
              {stories.map(story => (
                <Link to={`/storybook/${story.id}`} className="story-card" key={story.id} data-testid={`story-card-${story.id}`}>
                  <div className="story-card-image">
                    <img src={resolveImage(story.cover_image)} alt={story.title} />
                    {story.status === "processing" && <span className="processing-badge">Generating…</span>}
                  </div>
                  <div className="story-card-body">
                    <b>{story.title}</b>
                    <small>{story.child_name} · {story.page_count} {text.pages}</small>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="empty-state" data-testid="empty-stories">
              <BookOpen size={32} />
              <p>{text.noStories}</p>
              <Link to="/create" className="btn btn-primary" data-testid="start-creating-button">{text.startCreating} <ArrowRight size={16} /></Link>
            </div>
          )}
        </section>

        <section className="orders-section" id="orders">
          <h2>{text.printOrders}</h2>
          {orders.length ? orders.map(order => (
            <div className="order-row" key={order.id} data-testid={`order-row-${order.id}`}>
              <span className="order-icon"><Package size={18} /></span>
              <div><b>{order.format === "Hardcover" ? text.hardcover : text.softcover} storybook</b><small>{order.status} · {order.city}</small></div>
              <span className="status-pill">{order.status}</span>
            </div>
          )) : <div className="empty-order">{text.noOrders}</div>}
        </section>
      </main>
    </Shell>
  );
}
