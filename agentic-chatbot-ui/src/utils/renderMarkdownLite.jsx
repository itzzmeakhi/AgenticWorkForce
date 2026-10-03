import React from 'react';

/**
 * Minimal, dependency-free renderer for the subset of markdown the backend
 * actually produces: **bold**, "* " / "- " bullet lists, and blank-line
 * paragraph breaks. Not a general markdown parser -- just enough to stop
 * raw asterisks from showing up literally in the chat bubble.
 */

function renderInline(text, keyPrefix) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g).filter((p) => p !== '');
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 3) {
      return <strong key={`${keyPrefix}-b-${i}`}>{part.slice(2, -2)}</strong>;
    }
    return <React.Fragment key={`${keyPrefix}-t-${i}`}>{part}</React.Fragment>;
  });
}

const BULLET_RE = /^\s*[*-]\s+(.*)$/;

export default function MarkdownLite({ text }) {
  if (!text) return null;

  const lines = text.split('\n');
  const blocks = [];
  let currentList = null;
  let currentPara = [];

  const flushPara = () => {
    if (currentPara.length) {
      blocks.push({ type: 'p', lines: currentPara });
      currentPara = [];
    }
  };
  const flushList = () => {
    if (currentList) {
      blocks.push(currentList);
      currentList = null;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.replace(/\r$/, '');
    const bulletMatch = line.match(BULLET_RE);

    if (bulletMatch) {
      flushPara();
      if (!currentList) currentList = { type: 'ul', items: [] };
      currentList.items.push(bulletMatch[1]);
    } else if (line.trim() === '') {
      flushPara();
      flushList();
    } else {
      flushList();
      currentPara.push(line);
    }
  }
  flushPara();
  flushList();

  return (
    <>
      {blocks.map((block, i) => {
        if (block.type === 'ul') {
          return (
            <ul className="md-lite-list" key={`b-${i}`}>
              {block.items.map((item, j) => (
                <li key={`b-${i}-li-${j}`}>{renderInline(item, `b-${i}-li-${j}`)}</li>
              ))}
            </ul>
          );
        }
        return (
          <p className="md-lite-p" key={`b-${i}`}>
            {block.lines.map((l, j) => (
              <React.Fragment key={`b-${i}-l-${j}`}>
                {j > 0 && <br />}
                {renderInline(l, `b-${i}-l-${j}`)}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </>
  );
}
