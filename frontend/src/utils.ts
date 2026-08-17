export function shortAddress(value?: string | null): string {
  if (!value) return "-";
  return `${value.slice(0, 7)}...${value.slice(-5)}`;
}

export function percent(value?: number | null, digits = 1): string {
  return value == null ? "n/a" : `${(value * 100).toFixed(digits)}%`;
}
