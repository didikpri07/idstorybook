export const SentenceText = ({ page, currentMs, playing, onSeek }) => {
  const timings = page.sentence_timestamps;
  if (!page.audio || !Array.isArray(timings) || !timings.length) return <p data-testid="storybook-page-text">{page.text}</p>;
  return <p data-testid="storybook-page-text">{timings.map((timing, index) => {
    const active = playing && currentMs >= timing.start_ms && currentMs < timing.end_ms;
    return <span key={index}><button type="button" className={`sentence-highlight${active ? ' is-active' : ''}`} data-testid={`story-sentence-${index}`} aria-current={active ? 'true' : undefined} onClick={() => onSeek(timing.start_ms)}>{timing.sentence}</button>{index < timings.length - 1 ? ' ' : ''}</span>;
  })}</p>;
};