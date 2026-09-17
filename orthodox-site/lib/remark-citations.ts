// Remark plugin: turns the model's inline citation markers ("[3]", "[2][5]", "[1, 4]") into
// `citation` nodes that render as <sup class="cite-group" data-cites="2,5">. Markers that
// follow each other with only whitespace between them become one group. Text inside links
// and code is left alone.

type MdNode = {
  type: string;
  value?: string;
  children?: MdNode[];
  data?: Record<string, unknown>;
};

const CITATION_RE = /\[(\d{1,3}(?:\s*[,;،]\s*\d{1,3})*)\]/g;
const SKIP = new Set(["link", "linkReference", "inlineCode", "code", "html"]);

function citationNode(numbers: number[]): MdNode {
  const cites = numbers.join(",");
  return {
    type: "citation",
    data: { hName: "sup", hProperties: { className: ["cite-group"], dataCites: cites } },
    children: [{ type: "text", value: cites }],
  };
}

function splitText(value: string): MdNode[] {
  const out: MdNode[] = [];
  let cursor = 0;
  let group: number[] = [];
  let groupEnd = 0;

  const flushGroup = () => {
    if (group.length) out.push(citationNode(group));
    group = [];
  };

  for (const match of value.matchAll(CITATION_RE)) {
    const start = match.index ?? 0;
    const between = value.slice(group.length ? groupEnd : cursor, start);
    const numbers = match[1]
      .split(/[,;،]/)
      .map((token) => Number(token.trim()))
      .filter((number) => Number.isInteger(number) && number > 0);

    if (group.length && /^\s*$/.test(between)) {
      group.push(...numbers.filter((number) => !group.includes(number)));
    } else {
      flushGroup();
      // Drop the space before a marker so it sits against the word it supports.
      const text = value.slice(cursor, start).replace(/[ \t]+$/, "");
      if (text) out.push({ type: "text", value: text });
      group = [...new Set(numbers)];
    }
    groupEnd = start + match[0].length;
    cursor = groupEnd;
  }

  flushGroup();
  const rest = value.slice(cursor);
  if (rest) out.push({ type: "text", value: rest });
  return out.length ? out : [{ type: "text", value }];
}

function walk(node: MdNode) {
  if (!node.children || SKIP.has(node.type)) return;
  const next: MdNode[] = [];
  for (const child of node.children) {
    if (child.type === "text" && typeof child.value === "string" && child.value.includes("[")) {
      next.push(...splitText(child.value));
    } else {
      walk(child);
      next.push(child);
    }
  }
  node.children = next;
}

export default function remarkCitations() {
  return (tree: MdNode) => {
    walk(tree);
  };
}
