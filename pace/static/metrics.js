export const MILE = 1609.344;
export const HALF = 21097.5;
export const unitMeters = units => units === 'km' ? 1000 : MILE;
export const sum = (rows, field) => rows.reduce((n, r) => n + (+r[field] || 0), 0);
export function localDate(date = new Date()) { return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`; }
export function day(value) { return new Date(String(value).slice(0,10) + 'T12:00:00'); }
export function addDays(value, n) { const d = new Date(value); d.setDate(d.getDate()+n); return d; }
export function monday(value = new Date()) { const d = day(localDate(value)); return addDays(d, -(d.getDay()+6)%7); }
export function dateRange(runs, start, end) { const a=localDate(start), b=localDate(end); return runs.filter(r=>r.date.slice(0,10)>=a&&r.date.slice(0,10)<=b); }
export function averagePace(runs, units='mi') { const distance=sum(runs,'distance_m'); return distance ? sum(runs,'duration_s') / distance * unitMeters(units) : null; }
export function clock(seconds, hours=false) { if (seconds === null || seconds === undefined || !Number.isFinite(+seconds)) return '—'; const s=Math.round(+seconds), h=Math.floor(s/3600), m=Math.floor(s%3600/60), rest=String(s%60).padStart(2,'0'); return h||hours ? `${h}:${String(m).padStart(2,'0')}:${rest}` : `${m}:${rest}`; }
export function weeks(runs, count=8, today=new Date()) { const start=monday(today); return Array.from({length:count},(_,i)=>{const d=addDays(start,(i-count+1)*7), rows=dateRange(runs,d,addDays(d,6));return {date:localDate(d),distance:sum(rows,'distance_m'),duration:sum(rows,'duration_s'),runs:rows.length,rows};}); }
export function goalSplits(seconds, units='mi') { const size=unitMeters(units), out=[]; let d=0; while(d<HALF){const next=Math.min(d+size,HALF);out.push({distance:(next-d)/size,totalDistance:next/size,time:seconds*(next-d)/HALF,cumulative:seconds*next/HALF});d=next;}return out; }
export function previewRuns(today = new Date()) {
  const rows=[], start=monday(today), lengths=[3.2,4.1,3,6,3.7,4.6,3.1,7,4,5.2,3.2,8,4.1,5.3,3.4,8.5,4.5,5.7,3.5,9,4.2,5.2,3.2,9.5];
  for(let w=0;w<6;w++) for(let j=0;j<4;j++) { const d=addDays(start,(w-5)*7+[0,2,4,6][j]); if(localDate(d)>localDate(today))continue;const i=w*4+j, meters=lengths[i]*MILE, p=[600,540,620,605][j]-w*4;rows.push({id:`sample:${i}`,source:'Sample data',name:['Morning miles','A little more tempo','Easy does it','Sunday long run'][j],date:localDate(d)+'T07:15:00',distance_m:meters,duration_s:meters/MILE*p,hr:[141,159,136,148][j],elevation_m:24+i*3,cadence:166+w,kind:['Easy','Tempo','Recovery','Long run'][j],rpe:[3,7,2,5][j],notes:'Illustrative run. Connect Garmin or add your first run to start your own journal.',shoe:'',device:'Sample Garmin device'}); }
  return rows.sort((a,b)=>b.date.localeCompare(a.date));
}

export function daysUntil(value, today=new Date()) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const target=Date.parse(value+'T00:00:00Z');
  if (!Number.isFinite(target)) return null;
  return Math.round((target-Date.parse(localDate(today)+'T00:00:00Z'))/86400000);
}
