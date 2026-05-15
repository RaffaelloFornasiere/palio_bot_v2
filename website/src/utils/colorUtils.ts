/**
 * Converts a hex color to RGB components
 */
export function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16),
      }
    : null;
}

/**
 * Converts RGB components to hex color
 */
export function rgbToHex(r: number, g: number, b: number): string {
  return '#' + [r, g, b].map(x => {
    const hex = x.toString(16);
    return hex.length === 1 ? '0' + hex : hex;
  }).join('');
}

/**
 * Blends two colors together with a given alpha
 * @param color1 - The base color (hex string)
 * @param color2 - The color to blend (hex string)
 * @param alpha - The blend amount (0-1, where 0 = pure color1, 1 = pure color2)
 */
export function blendColors(color1: string, color2: string, alpha: number): string {
  const rgb1 = hexToRgb(color1);
  const rgb2 = hexToRgb(color2);
  
  if (!rgb1 || !rgb2) {
    return color1; // Return base color if conversion fails
  }
  
  const r = Math.round(rgb1.r * (1 - alpha) + rgb2.r * alpha);
  const g = Math.round(rgb1.g * (1 - alpha) + rgb2.g * alpha);
  const b = Math.round(rgb1.b * (1 - alpha) + rgb2.b * alpha);
  
  return rgbToHex(r, g, b);
}

/**
 * Gets a village color blended with the current theme background
 * @param villageColor - The village color (hex string)
 * @param backgroundColor - The background color to blend with (hex string)
 * @param alpha - The blend amount for the village color (default 0.4)
 */
export function getVillageBackgroundColor(
  villageColor: string,
  backgroundColor: string,
  alpha: number = 0.2
): string {
  return blendColors(backgroundColor, villageColor, alpha);
}

/**
 * A curated, theme-harmonious 5-colour set. Raw village colours are
 * snapped to the nearest of these by hue so the identity is preserved
 * (blue stays blue, the "black" borgo stays a visible dark) while the
 * palette looks intentional on the warm dark theme.
 */
const CURATED = {
  red: '#e2444d',
  yellow: '#f0c23c',
  green: '#3fae5a',
  blue: '#3d8bff',
  black: '#3a3733', // a visible warm charcoal — "black" without vanishing
};

/**
 * Maps a raw village hex to its curated equivalent, preserving the
 * semantic hue. Low-saturation / very dark inputs map to "black".
 */
export function curatedVillageColor(hex: string): string {
  const rgb = hexToRgb(hex);
  if (!rgb) return hex;
  const r = rgb.r / 255, g = rgb.g / 255, b = rgb.b / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;
  const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
  if (s < 0.18 || l < 0.16) return CURATED.black;
  let h = 0;
  if (max === r) h = ((g - b) / d) % 6;
  else if (max === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  h *= 60;
  if (h < 0) h += 360;
  if (h < 35 || h >= 330) return CURATED.red;
  if (h < 75) return CURATED.yellow;
  if (h < 170) return CURATED.green;
  return CURATED.blue;
}

/**
 * Determines if a color is light or dark
 * @param color - Hex color string
 * @returns true if the color is light, false if dark
 */
export function isLightColor(color: string): boolean {
  const rgb = hexToRgb(color);
  if (!rgb) return false;
  
  // Calculate perceived brightness
  const brightness = (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000;
  return brightness > 128;
}

/**
 * Gets an appropriate text color (black or white) based on background color
 * @param backgroundColor - Hex color string
 * @returns '#000000' for light backgrounds, '#ffffff' for dark backgrounds
 */
export function getContrastTextColor(backgroundColor: string): string {
  return isLightColor(backgroundColor) ? '#000000' : '#ffffff';
}