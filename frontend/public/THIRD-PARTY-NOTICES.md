kickoff original software: MIT; see LICENSE.

Public schedule data is separate from the MIT software license:

openfootball contributors — football.json; CC0 1.0 Universal.
https://github.com/openfootball/football.json
https://creativecommons.org/publicdomain/zero/1.0/
Changes: selected nine leagues and calendar-year dates, mapped into kickoff's
schema, retained supplied final scores, omitted canceled/postponed fixtures and
unzoned kickoff times. Separately attributed ESPN team facts and clocks retain
ESPN terms. No league endorsement.

openfootball contributors: worldcup.json; CC0 1.0 Universal.
https://github.com/openfootball/worldcup.json
https://creativecommons.org/publicdomain/zero/1.0/
Changes: selected World Cup fixtures, converted explicit UTC offsets, labeled
groups/knockout phases, retained final on-field and penalty shootout scores,
and added national-team flag identities. Revisions and file hashes accompany
each snapshot. Venue-country facts use FIFA's 16-city host list, checked
2026-10-31; each event includes that source link and check date. FIFA grants no
data license for those separately attributed host facts.
https://www.fifa.com/en/articles/fifa-world-cup-2026-hosts-cities-dates-usa-mexico-canada

F1DB and contributors — Formula 1 database; CC BY 4.0.
https://github.com/f1db/f1db
https://creativecommons.org/licenses/by/4.0/
Changes: selected race/session date and UTC time fields, simplified names,
normalized into kickoff's event schema and grouped by calendar year. Host country
uses the circuit's explicit country ID and ISO code from the same pinned F1DB revision.
Pinned source revisions, file hashes and attribution travel with each public
snapshot. F1DB is community maintained, not an official Formula 1 service.

Wikipedia contributors — selected sports schedules; CC BY-SA 4.0.
https://creativecommons.org/licenses/by-sa/4.0/
https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content
Changes: selected reviewed date-only events, normalized inclusive date spans,
simplified labels and venues, classified competition phases; omitted article
prose, images, results and unverified clocks. Adaptations remain CC BY-SA 4.0,
including their records in the combined calendar. Per-page contributor credits,
pinned revision links, hashes, retrieval dates and detailed changes accompany
all rows in the public bundle and the separately downloadable component.
Preserve applicable attribution and share-alike obligations on redistribution.

ESPN, the MLB Stats API and the NHL schedule API — league schedules (NFL,
NBA, MLB, NHL, UEFA Champions League, PGA Tour, LPGA Tour, UFC, NASCAR Cup, IndyCar).
https://www.espn.com/  https://statsapi.mlb.com/  https://www.nhl.com/schedule
These sources grant no data license. kickoff republishes factual schedule
information only (dates, times, participants, venues, team records, short names,
round labels and confirmed final scores), attributes each event to its source
with checked dates, and omits feed logos, odds, articles and raw payloads.
Agenda golf sections and popups request leaderboard facts directly from ESPN: positions, player
names, total and round scores, tee times and holes completed. Those results
carry ESPN's terms, not MIT or a new open-data license.
OpenLigaDB (ODbL) is consulted only to find Champions League match dates; none of
its data is republished.

World Climbing and the event organizers: manually reviewed 2026 and 2027
climbing schedule facts; no data license granted.
https://www.worldclimbing.com/calendar
https://www.worldclimbing.com/terms-and-conditions/index
Per-event official links, checked dates, source hashes, organizer timetable
references and uncertainties accompany data/reviewed/2026-climbing-sessions.json
and 2027-climbing-sessions.json. Only published round/category dates and
venue-local clocks are included. Shared starts, mixed events, date-only spans
and conflicting clocks remain explicit. No raw payloads, prose, results or
media are republished; no automated collection from these sites is configured.

IWF, EWF, AWF, Commonwealth Weightlifting Federation, IMWA and the Glasgow,
Aichi-Nagoya and Lima Games organizers: reviewed weightlifting schedule facts;
no data license granted. Per-event official links, checked dates, document
versions, timezone and category details are in data/reviewed/2026-weightlifting.json
and 2027-weightlifting.json. Combined timetable rows stay single sessions;
parallel Masters platforms stay separate. Only published clocks are converted
to UTC. Unpublished timetables retain confirmed date spans; unconfirmed months
and absent Games editions are omitted with source-linked reasons. No source
documents, athlete entries, results, logos or prose are republished. Hash
receipts identify raw document bytes where available and explicitly identify
reviewed-fact hashes otherwise. These facts carry their sources' terms, not MIT
or a new CC0 grant.

NFL team logos identify teams in factual schedule and results reporting;
no endorsement is implied. The 32 unmodified PNG/SVG assets and their original
source, license URL, usage-basis and review receipts were copied read-only from
sideline at 9b6963f90c64042532c9cd71b082bd4f1ce891c4:
https://github.com/snowball-projects/sideline/tree/9b6963f90c64042532c9cd71b082bd4f1ce891c4/web/team-logos
Per-file metadata: https://github.com/snowball-projects/kickoff/blob/main/frontend/src/team-assets.json
Twenty PNG logos retain team/NFL copyright and the original limited editorial
identification basis; no redistribution license is claimed. Twelve SVG files
carry the per-file public-domain designations listed in the metadata. Original
sideline usage notes remain sourcing records; kickoff displays the small logos
beside identified NFL teams in schedules and event popups, at 28 CSS pixels.
These assets are separate from the MIT software and schedule-data licenses.
Other leagues use text team identities.

React and React DOM: MIT, Meta Platforms, Inc. and affiliates.
https://github.com/facebook/react/blob/main/LICENSE
The distributed source/build tool licenses remain in package distributions;
frontend/package-lock.json fixes their versions. Vendored license text is
included below for the browser runtime.
MIT License

Copyright (c) Meta Platforms, Inc. and affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Material Design Icons, Pictogrammers and contributors: Apache License 2.0.
https://pictogrammers.com/docs/general/license/
https://github.com/Templarian/MaterialDesign/tree/2424e748e0cc63ab7b9c095a099b9fe239b737c0/svg
Checked 2026-10-28. Bundled icons: soccer, car-sports, football, basketball,
baseball, hockey-sticks, karate, golf, terrain and weight-lifter.
Upstream authors: Google (soccer, football, basketball, hockey-sticks, karate,
golf, terrain), Nick (baseball), GreenTurtwig (car-sports) and Michael Irigoyen
(weight-lifter), as identified in the pinned upstream meta.json.
Changes: extracted the ten SVG path shapes into a local currentColor component;
omitted XML wrappers and IDs. Shapes are unchanged. No brand or logo icons.


                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
