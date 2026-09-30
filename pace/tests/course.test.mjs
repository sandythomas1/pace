import test from 'node:test';
import assert from 'node:assert/strict';
import {pointAtDistance, milestoneTiming, projectRoute} from '../static/course.js';
import {course} from '../static/course-data.js';
import {HALF, MILE} from '../static/metrics.js';

test('route interpolation clamps endpoints and interpolates distance and elevation', () => {
  const points = [[0, 34, -117, 200], [100, 36, -115, 220]];
  assert.deepEqual(pointAtDistance(points, 50), {distance:50, lat:35, lng:-116, elevation:210});
  assert.equal(pointAtDistance(points, -10).distance, 0);
  assert.equal(pointAtDistance(points, 200).distance, 100);
  assert.throws(() => pointAtDistance([], 0), RangeError);
  assert.throws(() => pointAtDistance(points, NaN), RangeError);
});

test('milestone times use the exact half distance and finish at the goal', () => {
  assert.equal(milestoneTiming(HALF, 7200).elapsed, 7200);
  assert.equal(milestoneTiming(HALF, 7200).arrival, '8:30 AM');
  assert.equal(milestoneTiming(0, 7200).arrival, '6:30 AM');
  assert.ok(Math.abs(milestoneTiming(MILE, 7200).elapsed - 549.23) < .1);
  assert.equal(milestoneTiming(HALF + 100, 7200).elapsed, 7200);
  assert.equal(milestoneTiming(1000, null), null);
});

test('bundled historical route has ordered distances, real elevation and explicit provenance', () => {
  assert.equal(course.routeYear, 2024);
  assert.equal(course.raceDate, '2026-10-18');
  assert.equal(course.ascentM, 121.1);
  assert.match(course.routeSource, /5584656262/);
  assert.ok(course.points.length > 500);
  assert.equal(course.points[0][0], 0);
  assert.ok(Math.abs(course.points.at(-1)[0] - HALF) < 20);
  for (let i=1; i<course.points.length; i++) {
    assert.ok(course.points[i].every(Number.isFinite));
    assert.ok(course.points[i][0] >= course.points[i-1][0]);
  }
  const projected = projectRoute(course.points);
  assert.ok(projected.every(p => p.x >= 30 && p.x <= 870 && p.y >= 30 && p.y <= 450));
});
