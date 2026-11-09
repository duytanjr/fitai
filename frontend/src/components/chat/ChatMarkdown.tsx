import Markdown, { type Components } from "react-markdown";
import { cn } from "@/lib/utils";

/*
 * Hiển thị Markdown trong tin nhắn của AI, an toàn:
 *  - skipHtml: mọi HTML thô trong tin (<img>, <script>, <iframe>…) bị bỏ hẳn, không render.
 *  - Không dùng rehype-raw hay plugin nào cho phép HTML.
 *  - disallowedElements: chặn thêm các phần tử nhúng/biểu mẫu nếu được tạo từ cú pháp Markdown (vd. ![ảnh](…)).
 *  - urlTransform: chỉ nhận liên kết http/https; mọi giao thức khác (javascript:, data:, vbscript:, mailto:,
 *    đường dẫn tương đối…) bị bỏ và liên kết hiện thành chữ thường.
 */

const ALLOWED_PROTOCOLS = new Set(["http:", "https:"]);

export function safeHttpUrl(url: string): string | null {
  const trimmed = url.trim();
  if (!trimmed) return null;
  try {
    // Không có base: URL tương đối sẽ lỗi → bị bỏ. Trình duyệt và WHATWG URL đều bỏ khoảng trắng/ký tự điều
    // khiển ở đầu, nên "  javascript:…" vẫn được nhận ra là javascript:.
    const parsed = new URL(trimmed);
    return ALLOWED_PROTOCOLS.has(parsed.protocol) ? parsed.href : null;
  } catch {
    return null;
  }
}

const DISALLOWED = [
  "img",
  "script",
  "iframe",
  "style",
  "object",
  "embed",
  "video",
  "audio",
  "source",
  "form",
  "input",
  "button",
  "textarea",
  "select",
];

/* Plugin remark nhỏ: một dấu xuống dòng đơn trong đoạn văn thành <br> (giữ cách hiển thị cũ, mỗi dòng của
 * AI là một dòng). Viết tay để không thêm thư viện; chỉ tách nút text, không đụng code block. */
type MdNode = { type: string; value?: string; children?: MdNode[] };

function splitSoftBreaks(node: MdNode) {
  if (!node.children) return;
  const out: MdNode[] = [];
  for (const child of node.children) {
    if (child.type === "text" && typeof child.value === "string" && child.value.includes("\n")) {
      child.value.split("\n").forEach((part, i) => {
        if (i > 0) out.push({ type: "break" });
        if (part) out.push({ type: "text", value: part });
      });
    } else {
      if (child.type !== "code" && child.type !== "inlineCode") splitSoftBreaks(child);
      out.push(child);
    }
  }
  node.children = out;
}

function remarkSoftBreaks() {
  return (tree: MdNode) => splitSoftBreaks(tree);
}

const components: Components = {
  p: ({ node: _node, ...props }) => <p className="my-2 first:mt-0 last:mb-0" {...props} />,
  strong: ({ node: _node, ...props }) => <strong className="font-semibold text-ink" {...props} />,
  em: ({ node: _node, ...props }) => <em className="italic" {...props} />,
  ul: ({ node: _node, ...props }) => <ul className="my-2 list-disc space-y-1 pl-5 first:mt-0 last:mb-0" {...props} />,
  ol: ({ node: _node, ...props }) => <ol className="my-2 list-decimal space-y-1 pl-5 first:mt-0 last:mb-0" {...props} />,
  li: ({ node: _node, ...props }) => <li className="pl-0.5 marker:text-muted" {...props} />,
  h1: ({ node: _node, ...props }) => <h3 className="mb-1 mt-3 text-base font-semibold text-ink first:mt-0" {...props} />,
  h2: ({ node: _node, ...props }) => <h3 className="mb-1 mt-3 text-base font-semibold text-ink first:mt-0" {...props} />,
  h3: ({ node: _node, ...props }) => <h4 className="mb-1 mt-3 text-sm font-semibold text-ink first:mt-0" {...props} />,
  h4: ({ node: _node, ...props }) => <h4 className="mb-1 mt-3 text-sm font-semibold text-ink first:mt-0" {...props} />,
  h5: ({ node: _node, ...props }) => <h4 className="mb-1 mt-3 text-sm font-semibold text-ink first:mt-0" {...props} />,
  h6: ({ node: _node, ...props }) => <h4 className="mb-1 mt-3 text-sm font-semibold text-ink first:mt-0" {...props} />,
  blockquote: ({ node: _node, ...props }) => (
    <blockquote className="my-2 border-l-4 border-line pl-3 text-muted" {...props} />
  ),
  hr: () => <hr className="my-3 border-line" />,
  pre: ({ node: _node, ...props }) => (
    <pre className="my-2 overflow-x-auto rounded-control bg-gray-100 p-3 text-xs leading-relaxed text-ink" {...props} />
  ),
  code: ({ node: _node, className, ...props }) => (
    <code
      className={cn("rounded bg-gray-100 px-1 py-0.5 font-mono text-[0.85em] text-ink [pre_&]:bg-transparent [pre_&]:p-0", className)}
      {...props}
    />
  ),
  a: ({ node: _node, href, children }) => {
    const safe = href ? safeHttpUrl(href) : null;
    if (!safe) return <span>{children}</span>;
    return (
      <a
        href={safe}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-brand-700 underline underline-offset-2 hover:text-brand-800"
      >
        {children}
      </a>
    );
  },
};

export function ChatMarkdown({ content }: { content: string }) {
  return (
    <div className="break-words">
      <Markdown
        skipHtml
        disallowedElements={DISALLOWED}
        unwrapDisallowed
        remarkPlugins={[remarkSoftBreaks]}
        urlTransform={(url) => safeHttpUrl(url)}
        components={components}
      >
        {content}
      </Markdown>
    </div>
  );
}
