// Comprende Ya — UI primitives & icons
// Exposed on window for use across script files.

const { useState, useEffect, useRef, useMemo, useCallback, Fragment } = React;

// ── Icons (24×24 viewBox, stroke 1.5) ────────────────────
const ic = (path, opts = {}) => (props) => (
  <svg
    className={`i ${props.className || ''}`}
    viewBox="0 0 24 24"
    fill={opts.fill || 'none'}
    stroke="currentColor"
    strokeWidth={opts.sw || 1.5}
    strokeLinecap="round"
    strokeLinejoin="round"
    style={props.style}
    aria-hidden="true"
  >
    {path}
  </svg>
);

const IconHome = ic(<path d="M4 11.5 12 5l8 6.5V19a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1z" />);
const IconLibrary = ic(
  <Fragment>
    <rect x="4" y="5" width="4" height="14" rx="1" />
    <rect x="10" y="5" width="4" height="14" rx="1" />
    <path d="m17 6 3 .8-2.5 12.6L14.5 18.6z" />
  </Fragment>
);
const IconAutopsy = ic(
  <Fragment>
    <circle cx="11" cy="11" r="6" />
    <path d="m20 20-4.5-4.5" />
  </Fragment>
);
const IconChunks = ic(
  <Fragment>
    <rect x="4" y="4" width="7" height="7" rx="1" />
    <rect x="13" y="4" width="7" height="7" rx="1" />
    <rect x="4" y="13" width="7" height="7" rx="1" />
    <rect x="13" y="13" width="7" height="7" rx="1" />
  </Fragment>
);
const IconStats = ic(
  <Fragment>
    <path d="M4 19V5" />
    <path d="m4 19 5-5 4 3 7-8" />
  </Fragment>
);
const IconSettings = ic(
  <Fragment>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 3v2m0 14v2M5 12H3m18 0h-2m-2.5-6.5L18 4m-12 16 1.5-1.5M18 20l-1.5-1.5M6 6 4.5 4.5" />
  </Fragment>
);
const IconPlay = ic(<path d="M7 5v14l12-7z" />, { fill: 'currentColor', sw: 0 });
const IconPause = ic(
  <Fragment>
    <rect x="6" y="5" width="4" height="14" />
    <rect x="14" y="5" width="4" height="14" />
  </Fragment>,
  { fill: 'currentColor', sw: 0 }
);
const IconBack = ic(<path d="M11 17 6 12l5-5M7 12h12" />);
const IconFwd = ic(<path d="m13 7 5 5-5 5M18 12H6" />);
const IconBookmark = ic(<path d="M6 4h12v17l-6-4-6 4z" />);
const IconBookmarkFilled = ic(<path d="M6 4h12v17l-6-4-6 4z" />, { fill: 'currentColor' });
const IconClose = ic(<path d="M6 6l12 12M18 6 6 18" />);
const IconChev = ic(<path d="m9 6 6 6-6 6" />);
const IconMic = ic(
  <Fragment>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
  </Fragment>
);
const IconRefresh = ic(
  <Fragment>
    <path d="M3 12a9 9 0 0 1 15.5-6.3L21 8M21 4v4h-4" />
    <path d="M21 12a9 9 0 0 1-15.5 6.3L3 16M3 20v-4h4" />
  </Fragment>
);
const IconSearch = ic(
  <Fragment>
    <circle cx="11" cy="11" r="6" />
    <path d="m20 20-4.5-4.5" />
  </Fragment>
);
const IconSpark = ic(
  <path d="M12 3v6m0 6v6m-9-9h6m6 0h6M5.6 5.6l4.2 4.2m4.4 4.4 4.2 4.2M5.6 18.4l4.2-4.2m4.4-4.4 4.2-4.2" />,
  { sw: 1.2 }
);
const IconArrow = ic(<path d="M5 12h14m-5-5 5 5-5 5" />);

Object.assign(window, {
  React, useState, useEffect, useRef, useMemo, useCallback, Fragment,
  IconHome, IconLibrary, IconAutopsy, IconChunks, IconStats, IconSettings,
  IconPlay, IconPause, IconBack, IconFwd, IconBookmark, IconBookmarkFilled,
  IconClose, IconChev, IconMic, IconRefresh, IconSearch, IconSpark, IconArrow,
});

// ── Format helpers ────────────────────────────────────
function fmtTime(secs) {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}
window.fmtTime = fmtTime;

// ── Stripey thumbnail (used for video & cards) ────────
function Thumb({ color, label, pattern = 'a', duration, progress }) {
  // Different stripe patterns for visual variety
  const angle = { a: 135, b: 110, c: 60, d: 25, e: 95, f: 145 }[pattern] || 135;
  const stripeColor = 'rgba(0,0,0,0.08)';
  const stripeColor2 = 'rgba(0,0,0,0.04)';
  return (
    <div className="thumb" style={{ background: color }}>
      <div
        className="thumb-stripes"
        style={{
          backgroundImage: `repeating-linear-gradient(${angle}deg, ${stripeColor} 0px, ${stripeColor} 2px, transparent 2px, transparent 18px), repeating-linear-gradient(${angle + 90}deg, ${stripeColor2} 0px, ${stripeColor2} 1px, transparent 1px, transparent 9px)`,
        }}
      />
      <div className="thumb-label">{label}</div>
      {duration && <div className="thumb-dur">{duration}</div>}
      {progress !== undefined && progress > 0 && (
        <div className="thumb-progress"><span style={{ width: `${progress * 100}%` }} /></div>
      )}
    </div>
  );
}
window.Thumb = Thumb;
