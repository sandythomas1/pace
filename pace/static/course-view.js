import {course} from './course-data.js';
import {pointAtDistance, milestoneTiming, projectRoute} from './course.js';
import {HALF, MILE, clock, unitMeters, daysUntil} from './metrics.js';

const official = 'https://www.missioninnrun.org/Race/MissionInnRun/';
const link = (page, label) => `<a href="${official}${page}" target="_blank" rel="noreferrer">${label} ↗</a>`;
const positions = [[753,370],[637,259],[801,152],[603,197],[488,341],[416,449],
  [314,506],[182,582],[141,599],[192,606],[321,532],[431,471],[583,416],[747,397],[765,378]];
const milestones = positions.map(([x,y], i) => ({x,y,meters:i===14?HALF:i*MILE,
  label:i===0?'Start':i===14?'Finish':`Mile ${i}`}));
let selected = 0, mode = 'official', previewGoal = null;
const projected = projectRoute(course.points);
const routePath = projected.map((p,i)=>`${i?'L':'M'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ');
const trackLength = course.points.at(-1)[0];
const profileX = d => 42 + d / trackLength * 816;
const profileY = e => 135 - (e - 220) / 60 * 110;
const profilePath = course.points.map((p,i)=>`${i?'L':'M'}${profileX(p[0]).toFixed(2)},${profileY(p[3]).toFixed(2)}`).join(' ');

export function courseTeaser() {
  return `<article class="course-teaser"><div><span class="eyebrow">MISSION INN · OCTOBER 18, 2026</span>
    <h2>Get to know your 13.1.</h2><p>The course, the climbing, and a calmer race morning.</p></div>
    <button class="button primary" data-view="course">Explore the course ↗</button></article>`;
}

export function coursePage(settings) {
  const units = settings.units, imperial = units === 'mi';
  const elevation = n => `${Math.round(n*(imperial?3.28084:1))} <small>${imperial?'ft':'m'}</small>`;
  const days = daysUntil(course.raceDate);
  const configured = settings.race_date === course.raceDate && /mission inn/i.test(settings.race_name);
  return `<div id="course-hub" class="course-hub">
    <div class="page-heading"><div><div class="eyebrow">YOUR COURSE COMPANION · RIVERSIDE, CA</div>
      <h1>Know the route. <em>Own the day.</em></h1><p>Mission Inn Foundation Run · Half marathon · Sunday, October 18, 2026</p></div>
      <button class="button" data-view="race">← Race & goals</button></div>
    <section class="course-banner"><div><span class="pill">THE ROAD TO 13.1</span><h2>From downtown to the river.<br>And back to your finish line.</h2>
      <p>6:30 AM Pacific start · Market Street, between 10th & 11th</p>
      ${configured?'<span class="course-saved">✓ Your race is set</span>':'<button class="button" data-action="use-mission-inn">Set as my race</button>'}</div>
      <div class="course-count"><strong>${Math.max(0,days)}</strong><span>${days<0?'RACE DAY HAS PASSED':days===0?'IT’S RACE DAY':'DAYS TO THE START'}</span></div></section>
    <div class="course-facts">
      <article><span>THE DISTANCE</span><strong>${imperial?'13.1':'21.1'} <small>${units}</small></strong><p>21.0975 km · Half marathon</p></article>
      <article><span>REFERENCE CLIMB · 2024</span><strong>↗ ${elevation(course.ascentM)}</strong><p>2026 total gain not confirmed</p></article>
      <article><span>REFERENCE DESCENT · 2024</span><strong>↘ ${elevation(course.descentM)}</strong><p>From the organizer-linked GPS route</p></article>
      <article><span>YOUR START TIME</span><strong>6:30 <small>AM</small></strong><p>Pacific time · October 18</p></article>
    </div>
    <section class="panel course-explorer" aria-labelledby="explorer-title">
      <div class="panel-head"><div><span class="eyebrow">A LITTLE RECONNAISSANCE</span><h2 id="explorer-title">Explore every mile.</h2></div>
        <div class="segmented course-modes" aria-label="Course map version">
          <button data-course-mode="official" aria-pressed="${mode==='official'}" class="${mode==='official'?'selected':''}">2026 course map</button>
          <button data-course-mode="reference" aria-pressed="${mode==='reference'}" class="${mode==='reference'?'selected':''}">2024 elevation reference</button>
        </div></div>
      <p class="course-notice" id="course-version-note"></p>
      <div class="course-map-layout"><div><div class="course-map-frame">
        <div class="course-map-tools" aria-label="Map controls"><button type="button" data-map-zoom="in" aria-label="Zoom in">+</button><button type="button" data-map-zoom="out" aria-label="Zoom out">−</button><button type="button" data-map-zoom="reset" aria-label="Reset map">Reset</button></div>
        <div id="course-map"></div></div>
        <p class="course-caption" id="course-map-caption"></p></div>
        <aside class="course-readout"><span class="eyebrow">YOUR PLACE ON THE COURSE</span><h3 id="course-position"></h3>
          <p id="course-location"></p><dl><div><dt>Distance remaining</dt><dd id="course-remaining"></dd></div>
          <div><dt>Elapsed at target pace</dt><dd id="course-elapsed"></dd></div><div><dt>Estimated arrival · Pacific</dt><dd id="course-arrival"></dd></div>
          <div id="course-elevation-row"><dt>2024 reference elevation</dt><dd id="course-elevation"></dd></div></dl>
          <p class="course-timing-note">Even-pace estimate from a 6:30 AM start. Allow for your start-line delay and stops.</p>
          <label for="course-goal">Explore a finish time <span id="course-goal-label"></span></label>
          <input id="course-goal" type="range" min="3600" max="14400" step="60" value="${Math.max(3600,Math.min(14400,previewGoal??settings.goal_seconds??7200))}">
          <p class="course-timing-note" id="course-goal-note"></p>
        </aside></div>
      <div id="course-mile-buttons" class="course-mile-buttons" aria-label="Explore official mile markers">
        ${milestones.map((m,i)=>`<button type="button" data-course-mile="${i}" aria-pressed="false">${m.label}</button>`).join('')}</div>
      <div id="course-reference-profile" hidden><div class="course-profile-heading"><h3>The shape of the effort</h3><span>2024 elevation · ${imperial?'feet':'meters'}</span></div>
        <svg id="course-profile" viewBox="0 0 900 170" role="img" aria-label="Historical elevation profile. Use the distance slider below to explore the route.">
          ${[230,250,270].map(e=>`<path d="M42 ${profileY(e)}H858" class="profile-grid"/><text x="4" y="${profileY(e)+4}">${Math.round(e*(imperial?3.28084:1))}</text>`).join('')}
          <path d="${profilePath} L858 142 L42 142Z" class="profile-fill"/><path d="${profilePath}" class="profile-line"/>
          ${[0,5,10,15,20].map(k=>{const d=imperial?k*MILE:k*1000;return d>trackLength?'':`<text x="${profileX(d)}" y="162">${k} ${units}</text>`;}).join('')}
          <path id="profile-cursor" class="profile-cursor"/><circle id="profile-dot" r="5"/>
        </svg><label for="course-distance">Explore the historical route <output id="course-distance-label"></output></label>
        <input id="course-distance" type="range" min="0" max="${trackLength}" step="10" value="0">
        <p class="course-caption">Drag the slider, or select a point on the elevation chart. Elevations and distances are from the published 2024 GPS track.</p></div>
    </section>
    <section class="course-guide" aria-label="Race morning guide">
      <article class="panel"><span class="eyebrow">01 / BEFORE THE START</span><h2>Make morning easy.</h2>
        <div class="course-tip"><strong>Pick up on Saturday</strong><p>October 17, 1–5 PM at White Park, 3900 Market Street. Bring your confirmation email and photo ID.</p>${link('Page-16','Packet pickup')}</div>
        <div class="course-tip"><strong>Leave room for parking</strong><p>No dedicated runner parking. Garages and Convention Center lot 33 charge fees; check posted signs for other spaces.</p>${link('Page-19','Parking details')}</div>
        <div class="course-tip"><strong>Race-morning pickup needs a recheck</strong><p>The pickup page says 5:30 AM; the FAQ says 5:45 AM. Confirm before relying on either for a 6:30 start.</p>${link('Page-6','Organizer FAQ')}</div></article>
      <article class="panel"><span class="eyebrow">02 / OUT ON THE COURSE</span><h2>Have a simple plan.</h2>
        <div class="course-tip"><strong>Find your pace people</strong><p>Published pacer goals run from 1:30 to 3:00 in 10-minute steps. Look for finish-time signs at the start; no separate signup.</p>${link('Page-39','Pace groups')}</div>
        <div class="course-tip"><strong>Know your support stops</strong><p>The 2026 map marks water, first aid, and restrooms. Exact supplies and station distances are not confirmed here; check the final runner instructions.</p>${link('Page-25','Course & support map')}</div>
        <div class="course-tip"><strong>Save something for the return</strong><p>Planning suggestion: start controlled, use familiar fuel and gear, and run climbs by effort. The older elevation profile is a training reference, not a 2026 pacing prescription.</p></div></article>
      <article class="panel"><span class="eyebrow">03 / THE FINAL DETAILS</span><h2>Arrive ready.</h2>
        <div class="course-tip"><strong>Meet at the right finish</strong><p>2026 finishes on Main Street between 10th & 11th, a different street from the start. Agree on a post-race meeting spot.</p>${link('Page-25','Start & finish details')}</div>
        <div class="course-tip"><strong>Check the weather close to race day</strong><p>Live weather is not included in this guide. Check conditions during race week and plan your layers.</p><a href="https://forecast.weather.gov/MapClick.php?lat=33.98&lon=-117.38" target="_blank" rel="noreferrer">Riverside NWS forecast ↗</a></div>
        <div class="course-tip"><strong>Your night-before check</strong><p>Bib and pins · charged watch · familiar shoes and socks · practiced fuel · parking plan · meetup spot.</p></div></article>
    </section>
    <details class="course-sources"><summary>Sources & course versions · Checked September 24, 2026</summary>
      <p>The 2026 organizer illustration is the current course overview. Its mile-marker highlights are approximate positions on a diagram, not GPS navigation. The organizer says the course may change.</p>
      <p>The separately labeled 2024 reference preserves the 530 published track points and their elevations. Its endpoints differ from 2026. The ${elevation(course.ascentM)} gain is the source’s reported total ascent; it is not recomputed from noisy samples. No verified 2026 GPS profile or total gain was available in these sources.</p>
      <p>${link('Page-25','Organizer map & elevation links')} · <a href="${course.routeSource}" target="_blank" rel="noreferrer">2024 MapMyRun track ↗</a> · <a href="${course.mapSource}" target="_blank" rel="noreferrer">Original 2026 map ↗</a></p>
    </details></div>`;
}

/** Bind only within the current page; discarded page nodes own their listeners. */
export function mountCourse(root, settings) {
  if (!root) return;
  const $ = selector => root.querySelector(selector);
  const imperial = settings.units === 'mi', size = unitMeters(settings.units);
  let distance = milestones[selected].meters;
  const elevationLabel = e => `${Math.round(e*(imperial?3.28084:1))} ${imperial?'ft':'m'}`;
  const goal = () => Number($('#course-goal').value);
  let box, fullHeight, drag;

  function updateReadout() {
    const reference = mode === 'reference';
    const point = pointAtDistance(course.points, distance);
    const meters = reference ? point.distance : milestones[selected].meters;
    const timing = milestoneTiming(meters, goal());
    $('#course-position').textContent = reference ? `${(meters/size).toFixed(1)} ${settings.units}` : milestones[selected].label;
    $('#course-location').textContent = reference ? 'Historical GPS route · 2024' : selected===0 ? 'Market St, between 10th & 11th' : selected===14 ? 'Main St, between 10th & 11th' : 'Approximate marker on the 2026 organizer map';
    $('#course-remaining').textContent = `${(Math.max(0,HALF-meters)/size).toFixed(1)} ${settings.units}`;
    $('#course-elapsed').textContent = clock(timing.elapsed,true);
    $('#course-arrival').textContent = timing.arrival;
    $('#course-elevation-row').hidden = !reference;
    $('#course-elevation').textContent = elevationLabel(point.elevation);
    $('#course-goal-label').textContent = clock(goal(),true);
    $('#course-goal').setAttribute('aria-valuetext',`${clock(goal(),true)} finish time`);
    $('#course-goal-note').textContent = previewGoal!==null ? 'Exploring only. Your saved goal has not changed.' : settings.goal_seconds ? 'Starting from your saved goal (limited to the 1–4 hour slider range).' : '2-hour example. No finish-time goal has been saved.';
    root.querySelectorAll('[data-course-mile]').forEach(el=>el.setAttribute('aria-pressed',Number(el.dataset.courseMile)===selected));
    if (reference) {
      // Project the interpolated point with the same extent as the published track.
      const p = projectRoute([...course.points,[point.distance,point.lat,point.lng,point.elevation]]).at(-1);
      $('#map-position').setAttribute('cx',p.x); $('#map-position').setAttribute('cy',p.y);
      const x=profileX(point.distance), y=profileY(point.elevation);
      $('#profile-cursor').setAttribute('d',`M${x} 18V142`);
      $('#profile-dot').setAttribute('cx',x); $('#profile-dot').setAttribute('cy',y);
      $('#course-distance').value = point.distance;
      $('#course-distance-label').textContent = `${(point.distance/size).toFixed(1)} ${settings.units} · ${elevationLabel(point.elevation)}`;
      $('#course-distance').setAttribute('aria-valuetext',$('#course-distance-label').textContent);
    } else {
      $('#map-position').setAttribute('cx',milestones[selected].x);
      $('#map-position').setAttribute('cy',milestones[selected].y);
    }
  }

  function setBox() { $('#course-map svg').setAttribute('viewBox',box.join(' ')); }
  function renderMap() {
    const reference = mode==='reference';
    fullHeight = reference?480:696; box=[0,0,900,fullHeight];
    $('#course-version-note').textContent = reference
      ? '2024 reference only. The organizer still links this older GPS route; the 2026 start and finish have moved. Its climbing totals and profile are not verified for 2026.'
      : '2026 organizer map · Orange dashed line = half marathon. Select a mile below or on the map. Marker highlights are approximate; the route is subject to change.';
    $('#course-map-caption').textContent = reference ? 'Geographic route outline · North is up · Start S / Finish F · Drag to pan; use + / − to zoom.' : 'Map: Mission Inn Foundation · Drag to pan; use + / − to zoom. Reset fits the full course.';
    $('#course-mile-buttons').hidden = reference;
    $('#course-reference-profile').hidden = !reference;
    root.querySelectorAll('[data-course-mode]').forEach(el=>{const active=el.dataset.courseMode===mode;el.classList.toggle('selected',active);el.setAttribute('aria-pressed',active);});
    const endpoints = [projected[0],projected.at(-1)];
    $('#course-map').innerHTML = `<svg viewBox="0 0 900 ${fullHeight}" aria-label="${reference?'2024 historical GPS route outline':'2026 official half-marathon course map'}" role="img">
      ${reference?`<rect width="900" height="480" fill="#f1f3e8"/><path d="${routePath}" class="route-outline"/><path d="${routePath}" class="route-line"/>
        <text x="38" y="42" class="map-north">↑ N</text><text x="38" y="465" class="map-reference-label">2024 REFERENCE · NOT THE 2026 COURSE</text>
        ${endpoints.map((p,i)=>`<circle cx="${p.x}" cy="${p.y}" r="10" class="route-endpoint"/><text x="${p.x}" y="${p.y+4}" text-anchor="middle" class="route-endpoint-label">${i?'F':'S'}</text>`).join('')}`
      :`<image href="/mission-inn-2026.jpg" width="900" height="696"/><g>${milestones.map((m,i)=>`<circle cx="${m.x}" cy="${m.y}" r="14" class="map-hotspot" data-map-mile="${i}"><title>${m.label}</title></circle>`).join('')}</g>`}
      <circle id="map-position" r="${reference?7:18}" class="map-position"/>
    </svg>`;
    updateReadout();
    const svg=$('#course-map svg');
    svg.addEventListener('pointerdown',e=>{
      if(e.button!==0)return;
      const point=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());
      drag={point,x:e.clientX,y:e.clientY,mile:e.target.dataset.mapMile};svg.setPointerCapture(e.pointerId);
    });
    svg.addEventListener('pointermove',e=>{
      if(!drag)return;
      const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());
      box[0]+=drag.point.x-p.x;box[1]+=drag.point.y-p.y;setBox();
    });
    svg.addEventListener('pointerup',e=>{
      if(drag && Math.hypot(e.clientX-drag.x,e.clientY-drag.y)<6 && drag.mile!==undefined){selected=Number(drag.mile);distance=milestones[selected].meters;updateReadout();}
      drag=null;
    });
    svg.addEventListener('pointercancel',()=>{drag=null;});
  }

  root.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    if(b.dataset.courseMode){mode=b.dataset.courseMode;renderMap();}
    if(b.dataset.courseMile!==undefined){selected=Number(b.dataset.courseMile);distance=milestones[selected].meters;updateReadout();}
    if(b.dataset.mapZoom){
      const action=b.dataset.mapZoom;
      if(action==='reset')box=[0,0,900,fullHeight];
      else {const width=Math.max(225,Math.min(900,box[2]*(action==='in'?.75:1/.75))),height=width*fullHeight/900;
        box=[box[0]+(box[2]-width)/2,box[1]+(box[3]-height)/2,width,height];}
      setBox();
    }
  });
  $('#course-goal').addEventListener('input',()=>{previewGoal=goal();updateReadout();});
  $('#course-distance').addEventListener('input',e=>{distance=Number(e.target.value);updateReadout();});
  $('#course-profile').addEventListener('click',e=>{
    const svg=$('#course-profile'),p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());
    distance=Math.max(0,Math.min(trackLength,(p.x-42)/816*trackLength));updateReadout();
  });
  renderMap();
}
