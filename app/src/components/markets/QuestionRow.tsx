import type { QuestionResponse } from '../../lib/types';

interface QuestionRowProps {
  question: QuestionResponse;
  inPair: boolean;
}

export default function QuestionRow({ question, inPair }: QuestionRowProps) {
  const pct = Math.round(question.price * 100);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
        padding: '8px 12px',
        borderBottom: '1px solid #0a0d1a',
        borderLeft: `2px solid ${inPair ? '#ff6b35' : 'transparent'}`,
        background: inPair ? 'rgba(255,107,53,0.03)' : 'transparent',
        transition: 'background 0.1s',
        cursor: 'default',
      }}
    >
      {/* Probability */}
      <span style={{
        flexShrink: 0,
        fontSize: '16px',
        fontWeight: '600',
        color: inPair ? '#ff6b35' : '#2a3060',
        letterSpacing: '-0.02em',
        lineHeight: 1,
        fontVariantNumeric: 'tabular-nums',
        minWidth: '32px',
        textAlign: 'right',
        textShadow: inPair ? '0 0 10px rgba(255,107,53,0.5)' : 'none',
      }}>
        {pct}
      </span>
      <span style={{ fontSize: '8px', color: inPair ? 'rgba(255,107,53,0.5)' : '#1a2040', flexShrink: 0, marginTop: '3px' }}>%</span>

      {/* Text */}
      <p style={{
        margin: 0,
        flex: 1,
        fontSize: '10px',
        color: inPair ? '#c0c8d8' : '#3a4060',
        lineHeight: 1.5,
        letterSpacing: '0.01em',
        overflow: 'hidden',
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
      }}>
        {question.text}
      </p>

      {inPair && (
        <span style={{
          flexShrink: 0,
          fontSize: '7px',
          color: '#ff6b35',
          letterSpacing: '0.1em',
          marginTop: '2px',
          opacity: 0.7,
        }}>
          ARBIT
        </span>
      )}
    </div>
  );
}
