import { AudioLines } from 'lucide-react';
import { useLanguage } from '@/i18n';

export const VoicePicker = ({ value, onChange }) => {
  const { language } = useLanguage();
  const id = language === 'id';
  return <div className="field-block voice-field" data-testid="voice-picker">
    <label htmlFor="narrator-voice" className="field-label" data-testid="narrator-voice-label"><AudioLines size={15} />{id ? 'Suara Narator' : 'Narrator Voice'}</label>
    <select id="narrator-voice" name="voice_id" value={value} onChange={e => onChange(e.target.value)} data-testid="narrator-voice-select">
      <option value="nova">Sulafat · {id ? 'Hangat' : 'Warm'}</option>
      <option value="onyx">Algenib · {id ? 'Dalam & bertekstur' : 'Deep & textured'}</option>
      <option value="shimmer">Achernar · {id ? 'Lembut' : 'Soft'}</option>
    </select>
  </div>;
};