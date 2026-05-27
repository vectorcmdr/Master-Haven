import React from 'react';
import { GLYPH_NAMES, glyphImageSrc } from '../utils/glyphAssets';

/**
 * GlyphDisplay Component
 *
 * Displays a 12-digit glyph code as visual NMS portal glyphs.
 * Read-only display version of GlyphPicker.
 */
const GlyphDisplay = ({ glyphCode, size = 'medium' }) => {
  // Size presets
  const sizeClasses = {
    small: 'w-5 h-5',
    medium: 'w-7 h-7',
    large: 'w-10 h-10',
  };

  const glyphSize = sizeClasses[size] || sizeClasses.medium;

  if (!glyphCode || glyphCode.length !== 12) {
    return (
      <span className="font-mono text-gray-400">
        {glyphCode || 'No glyph code'}
      </span>
    );
  }

  const glyphs = glyphCode.toUpperCase().split('');

  return (
    <div className="flex items-center gap-0.5 flex-wrap">
      {glyphs.map((digit, index) => (
        <div
          key={index}
          className={`${glyphSize} flex items-center justify-center bg-gray-800 rounded border border-purple-600/50 overflow-hidden`}
          title={`${GLYPH_NAMES[digit]} (${digit})`}
        >
          {glyphImageSrc(digit) ? (
            <img
              src={glyphImageSrc(digit)}
              alt={GLYPH_NAMES[digit]}
              className="w-full h-full object-contain p-0.5"
            />
          ) : (
            <span className="text-purple-300 font-mono text-xs">
              {digit}
            </span>
          )}
        </div>
      ))}
    </div>
  );
};

export default GlyphDisplay;
