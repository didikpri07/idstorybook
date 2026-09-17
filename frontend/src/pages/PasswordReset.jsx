import { useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { ArrowLeft, KeyRound } from 'lucide-react';
import axios from 'axios';
import { Shell } from '@/components/Shell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useLanguage } from '@/i18n';
import { API } from '@/lib/constants';

export default function PasswordReset() {
  const { language } = useLanguage();
  const id = language === 'id';
  const location = useLocation();
  const reset = location.pathname === '/reset-password';
  const [params] = useSearchParams();
  const [value, setValue] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  const submit = async e => {
    e.preventDefault(); setError('');
    if (reset && value !== confirmation) { setError(id ? 'Kata sandi tidak cocok.' : 'Passwords do not match.'); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/auth/${reset ? 'reset-password' : 'forgot-password'}`, reset ? { token: params.get('token') || '', password: value } : { email: value }, { headers: { 'X-Language': language } });
      setDone(true);
    } catch (e) {
      const detail = e.response?.data?.detail;
      setError(e.response?.status === 503 ? (id ? 'Email pemulihan belum tersedia. Silakan coba lagi nanti.' : 'Password reset email isn’t available yet. Please try again later.') : typeof detail === 'string' ? detail : (id ? 'Tautan tidak valid atau detail belum lengkap.' : 'Invalid link or details. Please check and try again.'));
    } finally { setBusy(false); }
  };
  return <Shell><main className="account-page"><section className="auth-card" data-testid="password-reset-card">
    <div className="reset-icon"><KeyRound size={28} /></div>
    <h1 data-testid="reset-title">{reset ? (id ? 'Kata sandi baru.' : 'A fresh start.') : (id ? 'Lupa kata sandi?' : 'Forgot your password?')}</h1>
    <p data-testid="reset-description">{reset ? (id ? 'Pilih kata sandi baru untuk akunmu.' : 'Choose a new password for your account.') : (id ? 'Masukkan email akunmu.' : 'Enter the email address for your account.')}</p>
    {error && <div className="error-message" role="alert" data-testid="reset-error">{error}</div>}
    {done ? <div role="status" className="account-success" data-testid="reset-success">{reset ? (id ? 'Kata sandi diperbarui. Silakan masuk.' : 'Password updated. You can now sign in.') : (id ? 'Jika akun tersedia, tautan pemulihan akan dikirim melalui email.' : 'If an account exists, a password reset email will be sent.')}</div> : <form className="account-form" onSubmit={submit}>
      <label htmlFor="reset-value">{reset ? (id ? 'Kata sandi baru' : 'New password') : (id ? 'Alamat email' : 'Email address')}<Input id="reset-value" type={reset ? 'password' : 'email'} autoComplete={reset ? 'new-password' : 'email'} required minLength={reset ? 8 : undefined} maxLength={reset ? 72 : undefined} value={value} onChange={e => setValue(e.target.value)} data-testid="reset-value-input" /></label>
      {reset && <label htmlFor="reset-confirm">{id ? 'Konfirmasi kata sandi' : 'Confirm password'}<Input id="reset-confirm" type="password" autoComplete="new-password" required value={confirmation} onChange={e => setConfirmation(e.target.value)} data-testid="reset-confirm-input" /></label>}
      <Button className="btn btn-primary full" disabled={busy} type="submit" data-testid="reset-submit-button">{busy ? <span className="spinner" /> : reset ? (id ? 'Simpan kata sandi' : 'Save password') : (id ? 'Kirim tautan pemulihan' : 'Send reset link')}</Button>
    </form>}
    <Link to="/login" className="guest-continue" data-testid="reset-back-login"><ArrowLeft size={14} />{id ? 'Kembali ke masuk' : 'Back to sign in'}</Link>
  </section></main></Shell>;
}