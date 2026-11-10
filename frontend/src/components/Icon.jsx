const PATHS = {
  logo: <><path d="M4 18V9l8-5 8 5v9" /><path d="M8 18v-5M12 18v-8M16 18v-3" /></>,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4-4" /></>,
  dash: <><rect x="4" y="4" width="7" height="8" rx="1.5" /><rect x="13" y="4" width="7" height="5" rx="1.5" /><rect x="13" y="11" width="7" height="9" rx="1.5" /><rect x="4" y="14" width="7" height="6" rx="1.5" /></>,
  receipt: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" /><path d="M9 8h6M9 12h6" /></>,
  report: <><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5M10 13h6M10 17h6" /></>,
  bell: <><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" /><path d="M10 21h4" /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h10" />,
  dots: <><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>,
  compose: <><path d="M12 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-6" /><path d="M18.5 3.5a2.1 2.1 0 0 1 3 3L12 16l-4 1 1-4z" /></>,
  panel: <><rect x="3.5" y="4" width="17" height="16" rx="3.5" /><path d="M9.5 4v16" /></>,
  income: <><path d="M12 4v12M7 11l5 5 5-5" /><path d="M5 20h14" /></>,
  goal: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="4" /><circle cx="12" cy="12" r=".8" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  clip: <path d="m20 11-8.5 8.5a5 5 0 0 1-7-7L13 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L14 7" />,
  up: <path d="M12 19V5M6 11l6-6 6 6" />,
  expense: <><rect x="3" y="6" width="18" height="13" rx="2.5" /><path d="M3 10h18M7 15h3" /></>,
  balance: <path d="M4 19V10M10 19V5M16 19v-7M21 19H3" />,
  upload: <><path d="M12 16V4M7 9l5-5 5 5" /><path d="M5 15v4h14v-4" /></>,
  x: <path d="m6 6 12 12M18 6 6 18" />,
  out: <path d="M10 4H5v16h5M15 8l4 4-4 4M19 12H9" />,
}

export default function Icon({ name, size, className }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={className}
      style={size ? { width: size, height: size } : undefined}
    >
      {PATHS[name]}
    </svg>
  )
}
