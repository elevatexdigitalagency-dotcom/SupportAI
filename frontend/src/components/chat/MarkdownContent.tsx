"use client";

import React from "react";

function renderInline(text: string): React.ReactNode[] {
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return tokens.map((token, idx) => {
    if (token.startsWith("`") && token.endsWith("`") && token.length >= 2) {
      return (
        <code
          key={idx}
          className="rounded bg-slate-900/90 px-1.5 py-0.5 font-mono text-xs text-blue-300 border border-white/10"
        >
          {token.slice(1, -1)}
        </code>
      );
    }
    if (token.startsWith("**") && token.endsWith("**") && token.length >= 4) {
      return (
        <strong key={idx} className="font-semibold text-white">
          {token.slice(2, -2)}
        </strong>
      );
    }
    return <React.Fragment key={idx}>{token}</React.Fragment>;
  });
}

export function MarkdownContent({ content }: { content: string }) {
  const blocks = content.split(/(```[\s\S]*?```)/g);

  return (
    <div className="space-y-2.5 text-sm leading-relaxed text-slate-200">
      {blocks.map((block, blockIdx) => {
        if (block.startsWith("```") && block.endsWith("```")) {
          const inner = block.slice(3, -3);
          const firstNewline = inner.indexOf("\n");
          const code = firstNewline >= 0 ? inner.slice(firstNewline + 1) : inner;
          return (
            <pre
              key={blockIdx}
              className="overflow-x-auto rounded-xl border border-white/10 bg-[#050912] p-3 font-mono text-xs text-slate-200"
            >
              <code>{code.trimEnd()}</code>
            </pre>
          );
        }

        const lines = block.split("\n");
        const elements: React.ReactNode[] = [];
        let listItems: string[] = [];

        const flushList = (keyPrefix: string) => {
          if (listItems.length === 0) return;
          elements.push(
            <ul key={`${keyPrefix}-ul`} className="list-disc space-y-1 pl-5">
              {listItems.map((item, i) => (
                <li key={i}>{renderInline(item)}</li>
              ))}
            </ul>
          );
          listItems = [];
        };

        lines.forEach((rawLine, lineIdx) => {
          const line = rawLine.trimEnd();
          const trimmed = line.trim();
          const key = `${blockIdx}-${lineIdx}`;

          if (!trimmed) {
            flushList(key);
            return;
          }

          if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
            listItems.push(trimmed.slice(2));
            return;
          }

          if (/^\d+\.\s+/.test(trimmed)) {
            listItems.push(trimmed.replace(/^\d+\.\s+/, ""));
            return;
          }

          flushList(key);

          if (trimmed.startsWith("### ")) {
            elements.push(
              <h4 key={key} className="text-sm font-semibold text-white pt-1">
                {renderInline(trimmed.slice(4))}
              </h4>
            );
          } else if (trimmed.startsWith("## ")) {
            elements.push(
              <h3 key={key} className="text-base font-semibold text-white pt-1">
                {renderInline(trimmed.slice(3))}
              </h3>
            );
          } else if (trimmed.startsWith("# ")) {
            elements.push(
              <h2 key={key} className="text-lg font-bold text-white pt-1">
                {renderInline(trimmed.slice(2))}
              </h2>
            );
          } else {
            elements.push(<p key={key}>{renderInline(line)}</p>);
          }
        });

        flushList(`${blockIdx}-end`);
        return <React.Fragment key={blockIdx}>{elements}</React.Fragment>;
      })}
    </div>
  );
}
