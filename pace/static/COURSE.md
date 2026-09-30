# Mission Inn course companion

Open **Race day → Explore the course** (`/#course`). The feature uses native SVG and
local assets; there are no map keys, third-party scripts, tiles, or runtime network
dependencies. External links open only when selected.

## Sources and versions

Checked September 24, 2026:

- [Organizer course page](https://www.missioninnrun.org/Race/MissionInnRun/Page-25):
  current 2026 illustrated map, Market Street start and Main Street finish between
  10th and 11th. The course is subject to change.
- [2024 MapMyRun reference](https://www.mapmyrun.com/routes/view/5584656262/): linked
  by the organizer as “1/2 Marathon Map and Elevation 2024.” Contains 530 ordered
  track points, 121.1 m ascent and 119.6 m descent. These are historical figures,
  **not verified 2026 elevation totals**.
- [Start time](https://www.missioninnrun.org/Race/MissionInnRun/Page-17),
  [packet pickup](https://www.missioninnrun.org/Race/MissionInnRun/Page-16),
  [parking](https://www.missioninnrun.org/Race/MissionInnRun/Page-19),
  [pacers](https://www.missioninnrun.org/Race/MissionInnRun/Page-39), and
  [FAQ](https://www.missioninnrun.org/Race/MissionInnRun/Page-6).

The pickup page says 5:30 AM on race morning; the FAQ says 5:45 AM. The UI discloses
the conflict. The Saturday pickup window agrees. Recheck all logistics before the race.

## Implementation and updates

- `mission-inn-2026.jpg` is the organizer's unmodified illustration. Its original URL
  is recorded in `course-data.js`. Hotspot coordinates in `course-view.js` are pixel
  positions on its 900 × 696 diagram, not geographic coordinates.
- `course-data.js` stores only public route measurements and provenance, extracted
  from the organizer-linked page's route object. Each point is
  `[distance_m, latitude, longitude, elevation_m]`. Do not copy page-wide state,
  account information, or service keys when refreshing the track.
- `course.js` contains interpolation, a local geographic projection, and even-pace
  milestone calculations using the exact 21,097.5 m half-marathon distance. Published
  track distances are preserved (the reference ends at 21,094.88 m). Total ascent
  comes from the provider, not a raw sum of noisy elevation samples.
- `course-view.js` renders and binds the explorer. `course.css` scopes its styling.
  Pan/zoom, mile buttons, keyboard sliders, and chart clicks work offline. Metric
  preferences use the same source measurements. Finish-time exploration is temporary;
  **Set as my race** explicitly saves only race metadata through the existing API.
- Static files are individually allowlisted by the server. The existing content
  security policy is retained. Documentation files are not served.

To refresh for a new course, replace the source asset and its hotspot positions
together. Only replace the historical profile after obtaining a verified matching
GPS track; update source year, notices, dates, and attribution together.

## Verification

Run `node --test tests/*.test.mjs` and `python -m unittest discover -s tests -v`
from the application directory. Core tests cover interpolation boundaries, exact
goal timing, data validity, and static asset serving with the existing CSP.

Browser checks: navigate from Race day; select Start, a mile, and Finish; change the
goal; zoom, pan, and reset; switch to the historical profile and move its slider;
click the profile; verify kilometers; use keyboard controls; check a phone viewport;
save the event and confirm that the existing finish goal remains unchanged.

On the development Mac, all 9 JavaScript tests and 17 of 19 Python tests passed.
The two failures (`test_dpapi_round_trip` and
`test_paged_sync_and_offline_catchup_keep_notes`) also reproduce on unchanged HEAD:
they reach Windows-only token encryption. The feature's HTTP test passes.
