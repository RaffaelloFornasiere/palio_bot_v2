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
 * @param alpha - The blend amount for the village color (default 0.2)
 */
export function getVillageBackgroundColor(
  villageColor: string,
  backgroundColor: string,
  alpha: number = 0.2
): string {
  return blendColors(backgroundColor, villageColor, alpha);
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