/** Word wrap with explicit final-line ellipsis; long single tokens also fit. */
export function monitorTextLines(text: string, measure: (value: string) => number, width: number, maxLines: number): string[] {
  let remaining = text.replace(/\s+/g, ' ').trim();
  const lines: string[] = [];
  if (width <= 0 || maxLines <= 0) return lines;
  function prefix(value: string, suffix = '') {
    const chars = Array.from(value);
    let low = 0, high = chars.length;
    while (low < high) {
      const mid = Math.ceil((low + high) / 2);
      if (measure(chars.slice(0, mid).join('') + suffix) <= width) low = mid;
      else high = mid - 1;
    }
    return chars.slice(0, low).join('');
  }
  while (remaining && lines.length < maxLines) {
    if (measure(remaining) <= width) { lines.push(remaining); break; }
    if (lines.length === maxLines - 1) {
      if (measure('…') <= width) lines.push(prefix(remaining, '…').trimEnd() + '…');
      break;
    }
    let line = prefix(remaining);
    if (!line) break;
    const space = line.lastIndexOf(' ');
    if (space > 0) line = line.slice(0, space);
    lines.push(line);
    remaining = remaining.slice(line.length).trimStart();
  }
  return lines;
}
