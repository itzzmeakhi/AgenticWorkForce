import React from 'react';
import PropTypes from 'prop-types';

import './DomainBadge.scss';

const LABELS = {
  ecommerce: { text: 'E-commerce', color: '#22c55e' },
  insurance: { text: 'Insurance', color: '#f59e0b' },
  general: { text: 'General', color: '#64748b' },
};

const DomainBadge = ({ domain }) => {
  const info = LABELS[domain] || LABELS.general;
  const style = { '--badge-color': info.color }
  return (
    <span className="domain-badge" style={style}>
      <span className="domain-dot" />
      {info.text}
    </span>
  )
};

DomainBadge.propTypes = {
  domain: PropTypes.oneOf(['ecommerce', 'insurance', 'general']),
};

export default DomainBadge;
