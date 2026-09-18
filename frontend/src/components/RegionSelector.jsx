import { Globe2 } from 'lucide-react';
import { useId } from 'react';
import { useLanguage } from '@/i18n';
import { usePricing } from '@/context/PricingContext';

export const RegionSelector = ({ testId = 'pricing-region-select', compact = false }) => {
  const { language } = useLanguage();
  const id = language === 'id';
  const selectId = useId();
  const { region, setRegion, source } = usePricing();
  return <div className={`region-selector ${compact ? 'region-compact' : ''}`}>
    <label htmlFor={selectId} data-testid={`${testId}-label`}><Globe2 size={16} />{id ? 'Negara / mata uang' : 'Country / currency'}</label>
    <select id={selectId} value={region || ''} onChange={e => setRegion(e.target.value)} data-testid={testId}>
      <option value="" disabled>{id ? 'Pilih negara' : 'Choose your country'}</option>
      <option value="ID">{id ? 'Indonesia · Rupiah (IDR)' : 'Indonesia · Rupiah (IDR)'}</option>
      <option value="OTHER">{id ? 'Negara lainnya · Dolar AS (USD)' : 'Other countries · US Dollar (USD)'}</option>
    </select>
    {!compact && <small data-testid={`${testId}-source`}>{source === 'detected' ? (id ? 'Terdeteksi otomatis. Kamu bisa mengubahnya.' : 'Detected automatically. You can change this.') : source === 'detecting' ? (id ? 'Mendeteksi negara…' : 'Detecting your country…') : !region ? (id ? 'Negara belum terdeteksi. Silakan pilih.' : 'We couldn’t detect your country. Please choose.') : (id ? 'Harga mengikuti negara yang dipilih.' : 'Prices reflect your selected country.')}</small>}
  </div>;
};