import React from 'react';
import PropTypes from 'prop-types';

import './ToolTrace.scss';

const ToolTrace = ({ toolCalls }) => {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="tool-trace">
      {toolCalls.map((tc, i) =>
        tc.tool ? (
          <div key={i} className="tool-trace-line tool-call">
            <span className="tool-icon">🔧</span>
            <code>
              {tc.tool}({JSON.stringify(tc.args)})
            </code>
          </div>
        ) : (
          <div key={i} className="tool-trace-line tool-result">
            <span className="tool-icon">→</span>
            <span>
              <strong>{tc.tool_result}</strong>: {tc.output}
            </span>
          </div>
        ),
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
      output: PropTypes.string,
    }),
  ),
};

export default ToolTrace;
