// remark-math only understands $...$ and $$...$$; LLMs often emit \(...\) and \[...\].
export function normalizeMathDelimiters(text) {
  return text
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, expr) => `$$${expr}$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_, expr) => `$${expr}$`)
}
