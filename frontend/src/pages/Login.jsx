import { useEffect, useState } from 'react';
import { Link, Navigate, useLocation, useSearchParams } from 'react-router-dom';
import { ArrowRight, BookOpen, LockKeyhole, Mail } from 'lucide-react';
import axios from 'axios';
import { useAuth } from '@/context/AuthContext';
import { useLanguage } from '@/i18n';
import { Shell } from '@/components/Shell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { API } from '@/lib/constants';

export default function Login() {
  const { user, setUser } = useAuth();
  const { language } = useLanguage();
  const id = language === 'id';
  const location = useLocation();
  const [params] = useSearchParams();
  const signup = location.pathname === '/signup';
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [config, setConfig] = useState(null);
  const requested = params.get('next') || (location.state?.from ? location.state.from.pathname + (location.state.from.search || '') : '/dashboard');
  const next = requested.startsWith('/') && !requested.startsWith('//') && !requested.includes('\\') ? requested : '/dashboard';
  useEffect(() => { axios.get(`${API}/auth/config`).then(r => setConfig(r.data)).catch(() => setConfig({})); }, []);
  useEffect(() => { setError(''); }, [signup]);
  if (user) return <Navigate to={next} replace />;
  const update = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  const submit = async e => {
    e.preventDefault(); setBusy(true); setError('');
    try {
      const { data } = await axios.post(`${API}/auth/${signup ? 'signup' : 'login'}`, form, { withCredentials: true });
      setUser(data.user);
    } catch (e) {
      const detail = e.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : (id ? 'Periksa detail akunmu dan coba lagi.' : 'Please check your details and try again.'));
    } finally { setBusy(false); }
  };
  return <Shell><main className="account-page"><section className="auth-card" data-testid="login-card">
    <div className="auth-brand" data-testid="auth-brand"><span className="auth-brand-mark"><BookOpen size={20} /></span>ID<b>Storybook</b></div>
    <h1 data-testid="auth-title">{signup ? (id ? 'Awal cerita indah.' : 'A new chapter begins.') : (id ? 'Selamat datang kembali.' : 'Welcome back.')}</h1>
    <p data-testid="auth-description">{signup ? (id ? 'Simpan cerita si kecil di perpustakaan pribadimu.' : 'A little library for all their big adventures.') : (id ? 'Cerita favorit si kecil menunggumu.' : 'Their favourite stories are waiting for you.')}</p>
    {(error || params.get('error')) && <div className="error-message" role="alert" data-testid="auth-error">{error || (id ? 'Google belum dapat masuk. Coba lagi.' : 'Google sign-in could not be completed.')}</div>}
    <form className="account-form" onSubmit={submit}>
      {signup && <label htmlFor="parent-name">{id ? 'Nama orang tua' : 'Parent’s name'}<Input id="parent-name" name="name" autoComplete="name" required maxLength={80} value={form.name} onChange={update} data-testid="signup-name-input" /></label>}
      <label htmlFor="account-email">{id ? 'Alamat email' : 'Email address'}<Input id="account-email" name="email" type="email" autoComplete="email" required value={form.email} onChange={update} data-testid="auth-email-input" /></label>
      <label htmlFor="account-password">{id ? 'Kata sandi' : 'Password'}<Input id="account-password" name="password" type="password" autoComplete={signup ? 'new-password' : 'current-password'} required minLength={signup ? 8 : 1} maxLength={72} value={form.password} onChange={update} data-testid="auth-password-input" /></label>
      {signup && <small data-testid="password-requirement">{id ? 'Minimal 8 karakter.' : 'At least 8 characters.'}</small>}
      {!signup && <Link className="account-forgot" to="/forgot-password" data-testid="forgot-password-link">{id ? 'Lupa kata sandi?' : 'Forgot password?'}</Link>}
      <Button className="btn btn-primary full" type="submit" disabled={busy} data-testid="auth-submit-button">{busy ? <span className="spinner" /> : <>{signup ? (id ? 'Buat akun' : 'Create an account') : (id ? 'Masuk' : 'Sign in')}<ArrowRight size={16} /></>}</Button>
    </form>
    <div className="auth-divider" data-testid="auth-divider">{id ? 'atau' : 'or'}</div>
    <Button variant="outline" className="btn-google" disabled={!config?.google_enabled || busy} onClick={() => { window.location.href = `${API}/auth/google?next=${encodeURIComponent(next)}`; }} data-testid="google-signin-button"><Mail size={17} />{id ? 'Lanjutkan dengan Google' : 'Continue with Google'}</Button>
    {config && !config.google_enabled && <small className="integration-note" data-testid="google-unavailable-note">{id ? 'Google belum tersedia. Gunakan email untuk saat ini.' : 'Google sign-in isn’t available yet. Please use email for now.'}</small>}
    <p className="auth-switch" data-testid="auth-switch">{signup ? (id ? 'Sudah punya akun? ' : 'Already have an account? ') : (id ? 'Baru di sini? ' : 'New here? ')}<Link to={`${signup ? '/login' : '/signup'}?next=${encodeURIComponent(next)}`} data-testid="auth-switch-link">{signup ? (id ? 'Masuk' : 'Sign in') : (id ? 'Buat akun' : 'Create an account')}</Link></p>
    <Link to="/create" className="guest-continue" data-testid="continue-as-guest-link">{id ? 'Lanjutkan sebagai tamu' : 'Continue as a guest'}<ArrowRight size={14} /></Link>
    <small className="auth-privacy" data-testid="auth-privacy-note"><LockKeyhole size={12} />{id ? 'Perpustakaanmu, hanya untukmu.' : 'Your library. Just for you.'}</small>
  </section></main></Shell>;
}