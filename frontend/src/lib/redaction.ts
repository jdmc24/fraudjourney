type RedactionPattern = {
  label: string;
  pattern: RegExp;
};

const patterns: RedactionPattern[] = [
  { label: "card_number", pattern: /\b(?:\d[ -]*?){13,19}\b/g },
  { label: "ssn", pattern: /\b\d{3}-\d{2}-\d{4}\b/g },
  { label: "account_number", pattern: /\b(?:acct|account)\s*#?\s*\d{6,17}\b/gi },
  { label: "email", pattern: /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi },
  { label: "phone", pattern: /\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b/g }
];

export function redactText(value: string): { text: string; labels: string[] } {
  const labels = new Set<string>();
  let text = value;

  for (const item of patterns) {
    if (item.pattern.test(text)) {
      labels.add(item.label);
      text = text.replace(item.pattern, `[REDACTED_${item.label.toUpperCase()}]`);
    }
    item.pattern.lastIndex = 0;
  }

  return { text, labels: Array.from(labels).sort() };
}

