import { useEffect, useRef, useState } from 'react';
import { BookOpen, Check, Image, Mic, PenLine, RefreshCw } from 'lucide-react';
import axios from 'axios';
import { API } from '@/lib/constants';
import { useLanguage } from '@/i18n';
import { Button } from '@/components/ui/button';

export const GenerationProgress = ({ storyId, childName, onReady }) => {
  const { language } = useLanguage();
  const id = language === 'id';
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const ready = useRef(onReady);
  ready.current = onReady;
  useEffect(() => {
    let active = true, timer;
    const poll = async () => {
      try {
        const { data } = await axios.get(`${API}/stories/${storyId}/progress`, { timeout: 15000 });
        if (!active) return;
        setProgress(data); setError('');
        if (['complete', 'completed', 'partial', 'failed'].includes(data.status)) { await ready.current(); return; }
      } catch (e) {
        if (!active) return;
        setError(e.response?.status === 401 || e.response?.status === 404 ? 'access' : 'connection');
      }
      if (active) timer = setTimeout(poll, 3000);
    };
    poll();
    return () => { active = false; clearTimeout(timer); };
  }, [storyId, attempt]);
  const stage = progress?.stage || 'writing';
  const page = progress?.current_page || 1, total = progress?.total_pages || '…';
  const label = stage === 'illustrating_cover' ? (id ? 'Melukis sampul buku…' : 'Illustrating the book cover…')
    : stage === 'illustrating' ? (id ? `Melukis halaman ${page} dari ${total}…` : `Illustrating page ${page} of ${total}…`)
    : stage === 'narrating' ? (id ? `Merekam halaman ${page} dari ${total}…` : `Narrating page ${page} of ${total}…`)
    : (id ? `Menulis halaman ${page} dari ${total}…` : `Writing page ${page} of ${total}…`);
  const minutes = Math.ceil((progress?.estimated_seconds_remaining || 0) / 60);
  return <main className="center-page generating-page live-progress" data-testid="generating-page">
    <div className="generating-icon-wrap"><div className="generating-book-pulse"><BookOpen size={32} /></div></div>
    <div className="eyebrow" data-testid="generating-step-label" role="status" aria-live="polite">{label}</div>
    <h1 data-testid="generation-title">{id ? 'Cerita istimewa untuk ' : 'A little magic for '}<em>{childName}</em>.</h1>
    <div className="generating-progress-track" role="progressbar" aria-label={id ? 'Kemajuan cerita' : 'Story progress'} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress?.percent || 0} data-testid="generation-progress-track">
      <div className="generating-progress-fill" style={{ width: `${progress?.percent || 0}%` }} data-testid="generating-progress-bar" />
    </div>
    <div className="progress-details"><span data-testid="generation-percent">{progress?.percent || 0}%</span><span data-testid="generation-eta">{progress ? (id ? `Perkiraan ${minutes} menit lagi` : `About ${minutes} min remaining`) : (id ? 'Menghubungkan…' : 'Connecting…')}</span></div>
    <p className="progress-status-note" data-testid="generation-completed-pages">{id ? `${progress?.completed_pages || 0} dari ${total} halaman selesai` : `${progress?.completed_pages || 0} of ${total} pages complete`}</p>
    <div className="generating-steps-list">
      {[[PenLine, id ? 'Cerita' : 'Story', 'writing'], [Image, id ? 'Ilustrasi' : 'Illustrations', 'illustrating'], [Mic, id ? 'Narasi' : 'Narration', 'narrating']].map(([Icon, title, key]) => {
        const done = key === 'writing' && progress?.percent > 0 && stage !== 'writing';
        const active = stage.startsWith(key);
        return <div key={key} className={`generating-step-item ${done ? 'step-done' : active ? 'step-active' : 'step-pending'}`} data-testid={`generation-stage-${key}`}><span className="step-icon">{done ? <Check size={13} /> : <Icon size={13} />}</span><span>{title}</span></div>;
      })}
    </div>
    {error && <div className="progress-status-note" role="alert" data-testid="generation-poll-error">{error === 'access' ? (id ? 'Sesi berakhir. Masuk kembali untuk melanjutkan.' : 'Your session has expired. Sign in again to continue.') : (id ? 'Koneksi terputus. Kemajuanmu tersimpan. Menghubungkan kembali…' : 'Connection interrupted. Your progress is saved. Reconnecting…')}<Button variant="ghost" onClick={() => setAttempt(a => a + 1)} data-testid="retry-progress-poll"><RefreshCw size={14} />{id ? 'Coba lagi' : 'Reconnect'}</Button></div>}
  </main>;
};