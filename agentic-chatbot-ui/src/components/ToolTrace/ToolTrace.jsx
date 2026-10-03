import React, { useState } from 'react';
import PropTypes from 'prop-types';

import './ToolTrace.scss';

const ToolTrace = ({ toolCalls }) => {
  const [expanded, setExpanded] = useState(false);

  if (!toolCalls || toolCalls.length === 0) return null;

  const callCount = toolCalls.filter((tc) => tc.tool).length;

  return (
    <div className="tool-trace">
      <button
        type="button"
        className="tool-trace-toggle"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className={`tool-trace-chevron ${expanded ? 'is-open' : ''}`}>▸</span>
        <span className="tool-icon">🔧</span>
        <span>
          strace: {callCount} tool call{callCount === 1 ? '' : 's'}
        </span>
      </button>

      {expanded && (
        <div className="tool-trace-body">
          {toolCalls.map((tc, i) => (
            <div key={i} className="tool-trace-entry">
              {tc.tool && (
                <div className="tool-trace-line tool-call">
                  <span className="tool-icon">→</span>
                  <code>
                    {tc.tool}({JSON.stringify(tc.args)})
                  </code>
                </div>
              )}
              {tc.output !== undefined && (
                <div className="tool-trace-line tool-result">
                  <span className="tool-icon">⇠</span>
                  <code>{typeof tc.output === 'string' ? tc.output : JSON.stringify(tc.output, null, 2)}</code>
                </div>
              )}
              {tc.tool_result && (
                <div className="tool-trace-line tool-result">
                  <span className="tool-icon">⇠</span>
                  <span>
                    <strong>{tc.tool_result}</strong>
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
};

ToolTrace.propTypes = {
  toolCalls: PropTypes.arrayOf(
    PropTypes.shape({
      tool: PropTypes.string,
      args: PropTypes.object,
      tool_result: PropTypes.string,
      output: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    }),
  ),
};

export default ToolTrace;
