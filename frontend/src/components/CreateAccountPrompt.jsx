import { ArrowRight, BookHeart } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useLanguage } from '@/i18n';

export const CreateAccountPrompt = ({ open, onOpenChange, onContinue }) => {
  const { language } = useLanguage();
  const id = language === 'id';
  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="creation-auth-dialog" data-testid="create-account-prompt" closeLabel={id ? 'Tutup' : 'Close'}>
      <div className="creation-auth-icon" aria-hidden="true"><BookHeart size={27} /></div>
      <DialogHeader>
        <DialogTitle data-testid="create-account-prompt-title">{id ? 'Buat akun untuk membuat dan menyimpan cerita.' : 'Create an account to create and save your story.'}</DialogTitle>
        <DialogDescription data-testid="create-account-prompt-description">{id ? 'Detail cerita dan foto si kecil akan tetap tersimpan selama kamu mendaftar. Buku yang dibuat akan masuk ke perpustakaan pribadimu.' : 'Your story details and photo will be kept while you sign up. Your finished book will belong in your private library.'}</DialogDescription>
      </DialogHeader>
      <Button className="btn btn-primary full" onClick={() => onContinue('signup')} data-testid="create-account-signup-button">{id ? 'Buat akun' : 'Sign up'}<ArrowRight size={16} /></Button>
      <Button variant="outline" className="creation-auth-login" onClick={() => onContinue('login')} data-testid="create-account-login-button">{id ? 'Sudah punya akun? Masuk' : 'Already have an account? Sign in'}</Button>
      <Button variant="ghost" onClick={() => onOpenChange(false)} data-testid="create-account-keep-editing-button">{id ? 'Lanjutkan mengisi cerita' : 'Keep editing my story'}</Button>
    </DialogContent>
  </Dialog>;
};