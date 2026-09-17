import { Link } from 'react-router-dom';
import { ArrowRight, BookHeart } from 'lucide-react';
import { useLanguage } from '@/i18n';

export const GuestSavePrompt = ({ storyId }) => {
  const { language } = useLanguage();
  const id = language === 'id';
  return <section className="guest-save-banner" data-testid="guest-save-prompt">
    <BookHeart size={25} /><div><strong data-testid="guest-save-title">{id ? 'Simpan cerita istimewa ini.' : 'Keep this little adventure.'}</strong><p data-testid="guest-save-description">{id ? 'Buat akun untuk menyimpan cerita di perpustakaan pribadimu.' : 'Create an account to save this story to your private library.'}</p></div>
    <Link to={`/signup?next=${encodeURIComponent(`/storybook/${storyId}`)}`} className="btn btn-primary" data-testid="save-story-signup-button">{id ? 'Simpan cerita saya' : 'Save my story'}<ArrowRight size={15} /></Link>
  </section>;
};