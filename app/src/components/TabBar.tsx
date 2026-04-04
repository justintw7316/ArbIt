import { NavLink } from 'react-router-dom';

interface TabBarProps {
  candidateCount: number;
  isLive: boolean;
}

export default function TabBar({ candidateCount, isLive }: TabBarProps) {
  const tabs = [
    { label: 'SIGNALS', to: '/signals' },
    { label: 'MARKETS', to: '/markets' },
    { label: 'PIPELINE', to: '/pipeline' },
    { label: 'SIMULATION', to: '/simulation' },
  ];

  return (
    <header className="flex items-stretch shrink-0" style={{ height: '48px', borderBottom: '1px solid #1a2040', background: '#060810' }}>
      {/* Wordmark */}
      <div className="flex items-center px-5" style={{ borderRight: '1px solid #1a2040', minWidth: '80px' }}>
        <span
          className="glow-orange font-bold tracking-[6px] select-none"
          style={{ fontSize: '15px', color: '#ff6b35', letterSpacing: '0.35em' }}
        >
          ARBX
        </span>
      </div>

      {/* Divider tick */}
      <div style={{ width: '1px', background: 'linear-gradient(180deg, transparent, #1a2040 30%, #1a2040 70%, transparent)', margin: '0' }} />

      {/* Tabs */}
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className="tab-active-wrapper"
          style={({ isActive }) => ({
            display: 'flex',
            alignItems: 'center',
            padding: '0 20px',
            borderRight: '1px solid #1a2040',
            borderBottom: isActive ? '2px solid #ff6b35' : '2px solid transparent',
            background: isActive ? 'linear-gradient(180deg, rgba(255,107,53,0.07) 0%, transparent 100%)' : 'transparent',
            color: isActive ? '#ffffff' : '#4a5568',
            fontSize: '10px',
            letterSpacing: '0.2em',
            fontFamily: 'IBM Plex Mono, monospace',
            fontWeight: isActive ? '500' : '400',
            textDecoration: 'none',
            transition: 'color 0.15s, background 0.15s',
            cursor: 'pointer',
            position: 'relative',
          })}
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <span style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: '1px',
                  background: 'linear-gradient(90deg, transparent, rgba(255,107,53,0.4), transparent)',
                }} />
              )}
              {tab.label}
            </>
          )}
        </NavLink>
      ))}

      {/* Right cluster */}
      <div className="ml-auto flex items-center gap-4 px-5" style={{ borderLeft: '1px solid #1a2040' }}>
        {candidateCount > 0 && (
          <span style={{ fontSize: '10px', color: '#ff6b35', letterSpacing: '0.15em', fontWeight: '500' }}>
            {candidateCount}
            <span style={{ color: '#4a5568', marginLeft: '4px', fontWeight: '400' }}>SIGNALS</span>
          </span>
        )}
        <div className="flex items-center gap-2">
          <span className="live-dot" />
          <span style={{ fontSize: '9px', color: isLive ? '#00e676' : '#4a5568', letterSpacing: '0.2em' }}>
            {isLive ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </header>
  );
}
