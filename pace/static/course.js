import {HALF} from './metrics.js';

/** Interpolate the published track without inventing elevation outside its extent. */
export function pointAtDistance(points, meters) {
  if (!points.length || !Number.isFinite(meters)) throw new RangeError('A track and finite distance are required.');
  const distance = Math.max(points[0][0], Math.min(points.at(-1)[0], meters));
  const high = points.findIndex(p => p[0] >= distance);
  const b = points[high], a = points[Math.max(0, high - 1)];
  const ratio = b[0] === a[0] ? 0 : (distance - a[0]) / (b[0] - a[0]);
  const at = i => a[i] + (b[i] - a[i]) * ratio;
  return {distance, lat:at(1), lng:at(2), elevation:at(3)};
}

/** Even-pace timing reference, starting at the announced 6:30 a.m. Pacific gun time. */
export function milestoneTiming(meters, goal) {
  if (!Number.isFinite(goal) || goal <= 0 || !Number.isFinite(meters)) return null;
  const elapsed = Math.max(0, Math.min(HALF, meters)) / HALF * goal;
  const minutes = (390 + Math.round(elapsed / 60)) % 1440;
  const hour = Math.floor(minutes / 60);
  return {elapsed, arrival:`${hour % 12 || 12}:${String(minutes % 60).padStart(2, '0')} ${hour < 12 ? 'AM' : 'PM'}`};
}

/** Local equirectangular projection preserving proportions over this small course area. */
export function projectRoute(points) {
  const cos = Math.cos(points[0][1] * Math.PI / 180);
  const xs = points.map(p => p[2] * cos), ys = points.map(p => -p[1]);
  const minX = Math.min(...xs), minY = Math.min(...ys);
  const width = Math.max(...xs) - minX, height = Math.max(...ys) - minY;
  const scale = Math.min(840 / (width || 1), 420 / (height || 1));
  return points.map((p, i) => ({x:(900 - width * scale) / 2 + (xs[i] - minX) * scale,
    y:(480 - height * scale) / 2 + (ys[i] - minY) * scale}));
}
