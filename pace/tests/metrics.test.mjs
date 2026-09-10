import test from 'node:test';
import assert from 'node:assert/strict';
import {MILE, HALF, averagePace, clock, weeks, dateRange, day, monday, localDate, goalSplits, previewRuns, daysUntil} from '../static/metrics.js';

test('weighted pace uses total distance rather than averaging run paces',()=>{
  const runs=[{distance_m:MILE,duration_s:600},{distance_m:MILE*3,duration_s:1620}];
  assert.equal(averagePace(runs,'mi'),555);
  assert.equal(averagePace([]),null);
});
test('Monday boundaries and Sunday runs remain in their local week',()=>{
  assert.equal(localDate(monday(day('2026-09-09'))),'2026-09-07');
  const runs=[{date:'2026-09-06T23:55:00',distance_m:1000,duration_s:300},{date:'2026-09-07T00:05:00',distance_m:2000,duration_s:600}];
  const result=weeks(runs,2,day('2026-09-09'));
  assert.deepEqual(result.map(w=>w.distance),[1000,2000]);
  assert.equal(dateRange(runs,day('2026-09-07'),day('2026-09-09')).length,1);
});
test('pace display carries rounded seconds correctly',()=>{
  assert.equal(clock(599.9),'10:00');assert.equal(clock(7200,true),'2:00:00');assert.equal(clock(null),'—');
});
test('half-marathon split sheet ends at exact goal with a fractional final mile',()=>{
  const splits=goalSplits(7200,'mi');
  assert.equal(splits.length,14);assert.equal(splits.at(-1).cumulative,7200);
  assert.ok(Math.abs(splits.reduce((n,s)=>n+s.distance,0)*MILE-HALF)<1e-7);
  assert.equal(goalSplits(7200,'km').length,22);
});
test('preview contains only marked sample records and no future dates',()=>{
  const runs=previewRuns(day('2026-09-09'));
  assert.equal(runs.length,22);
  assert.ok(runs.every(r=>r.id.startsWith('sample:')&&r.source==='Sample data'&&r.date.slice(0,10)<='2026-09-09'));
});

test('unset race dates stay unset and countdown uses calendar days across daylight saving',()=>{
  assert.equal(daysUntil(null,day('2026-09-09')),null);
  assert.equal(daysUntil('',day('2026-09-09')),null);
  assert.equal(daysUntil('2026-11-02',day('2026-10-31')),2);
});
