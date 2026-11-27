/**
 * Bộ tách Markdown GỌN cho tin của AI (thay react-markdown của frontend/src/components/chat/ChatMarkdown.tsx,
 * không thêm thư viện). Hàm thuần: chuỗi → cây khối/đoạn chữ; ChatMarkdown.tsx chỉ việc vẽ bằng <Text>.
 *
 * Hỗ trợ: đoạn văn (mỗi dấu xuống dòng là một dòng, như remarkSoftBreaks của web), tiêu đề #, danh sách - * + và
 * 1. 1), trích dẫn >, đường kẻ ---, khối code ```, `code`, **đậm** / __đậm__, *nghiêng* / _nghiêng_, liên kết
 * [chữ](url) và <https://…>, ký tự thoát \*.
 * An toàn (giống web): HTML thô bị bỏ (skipHtml), ảnh ![…](…) bị bỏ hẳn; liên kết chỉ nhận http/https
 * (safeHttpUrl), giao thức khác (javascript:, data:, mailto:, tương đối…) hiện thành chữ thường.
 * Markdown lạ (bảng, chú thích…) hiện nguyên dạng chữ thường.
 */

/** Chỉ nhận liên kết tuyệt đối http/https không có khoảng trắng; còn lại → null (hiện thành chữ thường). */
export function safeHttpUrl(url: string): string | null {
  // Bỏ tab/xuống dòng ở bất kỳ đâu và ký tự điều khiển/khoảng trắng ở hai đầu (trình duyệt cũng bỏ như vậy,
  // nên "  java\tscript:…" vẫn bị nhận ra là javascript:)
  const cleaned = url.replace(/[\t\n\r]/g, "").replace(/^[\u0000- ]+|[\u0000- ]+$/g, "");
  return /^https?:\/\/[^\s/?#\\]+[^\s\\]*$/i.test(cleaned) ? cleaned : null;
}

export type Inline =
  | { t: "text"; v: string }
  | { t: "code"; v: string }
  | { t: "strong"; c: Inline[] }
  | { t: "em"; c: Inline[] }
  /** href null = liên kết không an toàn: chỉ hiện chữ */
  | { t: "link"; href: string | null; c: Inline[] };

export type Block =
  | { t: "paragraph"; lines: Inline[][] }
  | { t: "heading"; level: number; c: Inline[] }
  | { t: "list"; ordered: boolean; items: { depth: number; marker: string; c: Inline[] }[] }
  | { t: "quote"; lines: Inline[][] }
  | { t: "code"; v: string }
  | { t: "hr" };

const HTML_TAG = /<\/?[A-Za-z][^<>]*>/g;
const HTML_COMMENT = /<!--[\s\S]*?-->/g;

/** Bỏ thẻ HTML thô trong đoạn chữ (nội dung giữa thẻ vẫn giữ, như skipHtml của react-markdown). */
function stripHtml(s: string): string {
  return s.replace(HTML_COMMENT, "").replace(HTML_TAG, "");
}

interface Rule {
  re: RegExp;
  build: (m: RegExpExecArray) => Inline | null;
  /** false → bỏ qua lần khớp này (vd. _ giữa chữ như snake_case) */
  accept?: (m: RegExpExecArray, src: string) => boolean;
}

const isWordChar = (ch: string | undefined) => !!ch && /[A-Za-z0-9À-ỹ]/.test(ch);

const RULES: Rule[] = [
  { re: /\\([\\`*_[\]()#+\-.!>~|{}])/, build: (m) => ({ t: "text", v: m[1] }) },
  { re: /`([^`\n]+)`/, build: (m) => ({ t: "code", v: m[1] }) },
  // Ảnh: bỏ hẳn (web chặn img)
  { re: /!\[[^\]\n]*\]\([^)\n]*\)/, build: () => null },
  {
    re: /\[([^\]\n]+)\]\(\s*<?([^)\s>]*)>?(?:\s+"[^"\n]*")?\s*\)/,
    build: (m) => ({ t: "link", href: safeHttpUrl(m[2]), c: parseInline(m[1]) }),
  },
  { re: /<(https?:\/\/[^>\s]+)>/i, build: (m) => ({ t: "link", href: safeHttpUrl(m[1]), c: [{ t: "text", v: m[1] }] }) },
  { re: /\*\*(?=\S)([\s\S]+?)\*\*/, build: (m) => ({ t: "strong", c: parseInline(m[1]) }) },
  {
    re: /__(?=\S)([\s\S]+?)__/,
    build: (m) => ({ t: "strong", c: parseInline(m[1]) }),
    accept: (m, src) => !isWordChar(src[m.index - 1]) && !isWordChar(src[m.index + m[0].length]),
  },
  { re: /\*(?=[^\s*])([^*]+?)\*/, build: (m) => ({ t: "em", c: parseInline(m[1]) }) },
  {
    re: /_(?=[^\s_])([^_]+?)_/,
    build: (m) => ({ t: "em", c: parseInline(m[1]) }),
    accept: (m, src) => !isWordChar(src[m.index - 1]) && !isWordChar(src[m.index + m[0].length]),
  },
];

/** Tìm lần khớp sớm nhất của một luật từ vị trí `from`; bỏ các lần khớp bị `accept` từ chối. */
function findFrom(rule: Rule, src: string, from: number): RegExpExecArray | null {
  const re = new RegExp(rule.re.source, rule.re.flags.includes("g") ? rule.re.flags : rule.re.flags + "g");
  re.lastIndex = from;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src)) !== null) {
    if (!rule.accept || rule.accept(m, src)) return m;
    re.lastIndex = m.index + 1;
  }
  return null;
}

function pushText(out: Inline[], v: string) {
  const text = stripHtml(v);
  if (!text) return;
  const last = out[out.length - 1];
  if (last && last.t === "text") last.v += text;
  else out.push({ t: "text", v: text });
}

export function parseInline(src: string): Inline[] {
  const out: Inline[] = [];
  let pos = 0;
  while (pos < src.length) {
    let best: { m: RegExpExecArray; rule: Rule } | null = null;
    for (const rule of RULES) {
      const m = findFrom(rule, src, pos);
      if (m && (!best || m.index < best.m.index)) best = { m, rule };
    }
    if (!best) break;
    pushText(out, src.slice(pos, best.m.index));
    const node = best.rule.build(best.m);
    if (node && node.t === "text") pushText(out, node.v);
    else if (node) out.push(node);
    pos = best.m.index + best.m[0].length;
  }
  pushText(out, src.slice(pos));
  return out;
}

const FENCE = /^\s*(```|~~~)/;
const HEADING = /^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/;
const HR = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/;
const BULLET = /^(\s*)([-*+])\s+(.*)$/;
const ORDERED = /^(\s*)(\d{1,9})([.)])\s+(.*)$/;
const QUOTE = /^\s{0,3}>\s?(.*)$/;

export function parseMarkdown(src: string): Block[] {
  const lines = src.replace(/\r\n?/g, "\n").replace(HTML_COMMENT, "").split("\n");
  const blocks: Block[] = [];
  let para: string[] = [];
  const flushPara = () => {
    if (para.length > 0) {
      const parsed = para.map(parseInline).filter((l) => l.length > 0);
      if (parsed.length > 0) blocks.push({ t: "paragraph", lines: parsed });
    }
    para = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (FENCE.test(line)) {
      flushPara();
      const fence = line.trim().slice(0, 3);
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence)) body.push(lines[i++]);
      blocks.push({ t: "code", v: body.join("\n") });
      continue;
    }
    if (line.trim() === "") {
      flushPara();
      continue;
    }
    // Đường kẻ phải xét trước danh sách ("- - -" / "***")
    if (HR.test(line)) {
      flushPara();
      blocks.push({ t: "hr" });
      continue;
    }
    const h = HEADING.exec(line);
    if (h) {
      flushPara();
      blocks.push({ t: "heading", level: h[1].length, c: parseInline(h[2]) });
      continue;
    }
    const b = BULLET.exec(line);
    const o = b ? null : ORDERED.exec(line);
    if (b || o) {
      flushPara();
      const indent = (b ? b[1] : o![1]).replace(/\t/g, "    ").length;
      const item = {
        depth: Math.min(3, Math.floor(indent / 2)),
        marker: b ? "•" : `${o![2]}.`,
        c: parseInline(b ? b[3] : o![4]),
      };
      const last = blocks[blocks.length - 1];
      if (last && last.t === "list" && last.ordered === !!o) last.items.push(item);
      else blocks.push({ t: "list", ordered: !!o, items: [item] });
      continue;
    }
    const q = QUOTE.exec(line);
    if (q) {
      flushPara();
      const last = blocks[blocks.length - 1];
      const parsed = parseInline(q[1]);
      if (last && last.t === "quote") last.lines.push(parsed);
      else blocks.push({ t: "quote", lines: [parsed] });
      continue;
    }
    // Dòng tiếp nối ngay sau một mục danh sách (thụt vào) thuộc về mục đó
    const last = blocks[blocks.length - 1];
    if (para.length === 0 && last && last.t === "list" && /^\s{2,}\S/.test(line)) {
      const item = last.items[last.items.length - 1];
      item.c = [...item.c, { t: "text", v: " " }, ...parseInline(line.trim())];
      continue;
    }
    para.push(line);
  }
  flushPara();
  return blocks;
}

/** Chữ thuần của một dãy đoạn (cho accessibilityLabel, kiểm thử). */
export function inlineText(nodes: Inline[]): string {
  return nodes.map((n) => (n.t === "text" || n.t === "code" ? n.v : inlineText(n.c))).join("");
}
