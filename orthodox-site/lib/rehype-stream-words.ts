// Rehype plugin for a streaming answer (UI-026): every word of the text becomes its own <span>,
// and a word that has just appeared gets the `stream-word` class, which fades it in. Words keep
// their span (and its place among its siblings) after the fade, so later renders change only a
// class and never replay the animation. Citation markers and code are left alone.

type HastNode = {
  type: string;
  tagName?: string;
  value?: string;
  properties?: Record<string, unknown>;
  children?: HastNode[];
};

export type StreamWordsOptions = {
  /** Whether the word at this position (0, 1, 2… in reading order) should fade in now. */
  isFresh: (index: number) => boolean;
};

const SKIP = new Set(["sup", "code", "pre"]);

export default function rehypeStreamWords(options: StreamWordsOptions) {
  return (tree: HastNode) => {
    let index = 0;
    const visit = (node: HastNode) => {
      if (!node.children || (node.tagName && SKIP.has(node.tagName))) return;
      const next: HastNode[] = [];
      for (const child of node.children) {
        if (child.type !== "text" || !child.value) {
          visit(child);
          next.push(child);
          continue;
        }
        for (const part of child.value.split(/(\s+)/)) {
          if (!part) continue;
          if (/^\s+$/.test(part)) {
            next.push({ type: "text", value: part });
            continue;
          }
          const fresh = options.isFresh(index);
          index += 1;
          next.push({
            type: "element",
            tagName: "span",
            properties: fresh ? { className: ["stream-word"] } : {},
            children: [{ type: "text", value: part }],
          });
        }
      }
      node.children = next;
    };
    visit(tree);
  };
}
