export function HighlightedSolution({ solution, answer, language }: { solution: string; answer: string; language: string }) {
  const trimmedAnswer = answer.trim();
  if (!trimmedAnswer) return <span lang={language}>{solution}</span>;

  // Treat the answer as literal text, allowing differences in whitespace and case.
  const pattern = trimmedAnswer.split(/\s+/).map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\s+');
  const parts = solution.split(new RegExp(`(${pattern})`, 'giu'));

  return <span lang={language}>{parts.map((part, index) => index % 2 === 1 ? <b key={index}>{part}</b> : part)}</span>;
}
