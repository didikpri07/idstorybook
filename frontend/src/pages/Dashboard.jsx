import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BookOpen, LockKeyhole, Package, WandSparkles } from 'lucide-react';
import axios from 'axios';
import { useLanguage } from '@/i18n';
import { Shell } from '@/components/Shell';
import { useAuth } from '@/context/AuthContext';
import { API, BACKEND, resolveImage } from '@/lib/constants';

export default function Dashboard() {
  const { text, language } = useLanguage();
  const { user } = useAuth();
  const [stories, setStories] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true, timer;
    const load = async () => {
      try {
        const [sr, or] = await Promise.all([axios.get(`${API}/stories`), axios.get(`${API}/orders`)]);
        if (active) { setStories(sr.data); setOrders(or.data); setError(''); }
      } catch { if (active) setError(language === 'id' ? 'Perpustakaan belum dapat dimuat.' : 'Your library could not be loaded. Please refresh.'); }
      finally { if (active) { setLoading(false); timer = setTimeout(load, 10000); } }
    };
    load(); return () => { active = false; clearTimeout(timer); };
  }, [user.user_id, language]);
  return <Shell><main className="dashboard">
    <div className="dashboard-head"><div>
      <div className="eyebrow" data-testid="library-greeting">{text.welcomeA} <b>{user?.name?.split(' ')[0]}</b></div>
      <h1 data-testid="library-title">{language === 'id' ? 'Perpustakaan ' : 'Your little '}<em>{language === 'id' ? 'ceritamu.' : 'library.'}</em></h1>
      <small className="private-note" data-testid="library-privacy"><LockKeyhole size={12} />{language === 'id' ? 'Cerita pribadi keluargamu.' : 'Stories that belong to your family.'}</small>
    </div><Link to="/create" className="btn btn-primary" data-testid="create-new-story-button">{text.createBook}<WandSparkles size={16} /></Link></div>
    {error && <div className="error-message" role="alert" data-testid="library-error">{error}</div>}
    <section className="stories-grid" data-testid="stories-grid"><div className="section-heading"><h2 data-testid="library-stories-heading">{text.stories}</h2><span data-testid="library-story-count">{stories.length} {text.saved}</span></div>
      {loading ? <div className="empty-state" role="status" data-testid="library-loading">{text.storyLoading}</div> : stories.length ? <div className="story-cards">{stories.map(story => <Link to={`/storybook/${story.id}`} className="story-card" key={story.id} data-testid={`story-card-${story.id}`}>
        <div className="story-card-image"><img src={resolveImage(story.cover_image) || `${BACKEND}/api/images/placeholder.png`} alt={story.title} data-testid={`story-cover-${story.id}`} /></div>
        <div className="story-card-body"><b data-testid={`story-title-${story.id}`}>{story.title}</b><small data-testid={`story-meta-${story.id}`}>{story.child_name} · {story.page_count} {text.pagesWord}</small>
          {['processing', 'generating'].includes(story.status) && <span className="story-status" data-testid={`story-generating-${story.id}`}>{language === 'id' ? 'Sedang dibuat…' : 'Being created…'}</span>}
          {['partial', 'failed'].includes(story.status) && <span className="story-status" data-testid={`story-partial-${story.id}`}>{language === 'id' ? 'Dijeda · Lanjutkan cerita' : 'Paused · Continue your story'}</span>}
        </div><ArrowRight size={17} /></Link>)}</div> : !error && <div className="empty-state" data-testid="empty-stories"><BookOpen size={32} /><b>{text.firstWaiting}</b><Link to="/create" className="btn btn-primary" data-testid="start-creating-button">{text.startCreating}<ArrowRight size={16} /></Link></div>}
    </section>
    <section className="orders-section" id="orders"><div className="section-heading"><h2 data-testid="library-orders-heading">{text.printOrders}</h2><span data-testid="library-order-count">{orders.length} {text.ordersCount}</span></div>
      {orders.length ? orders.map(order => <div className="order-row" key={order.id} data-testid={`order-row-${order.id}`}><span className="order-icon"><Package size={18} /></span><div><b data-testid={`order-title-${order.id}`}>{order.format === 'Hardcover' ? text.hardcover : text.softcover} · {order.child_name}</b><small data-testid={`order-city-${order.id}`}>{order.city}</small></div><span className="status-pill" data-testid={`order-status-${order.id}`}>{order.status === 'Shipped' ? text.shipped : order.status === 'In production' ? text.production : text.orderReceived}</span></div>) : !loading && <div className="empty-order" data-testid="empty-orders">{text.noOrders}</div>}
    </section>
  </main></Shell>;
}