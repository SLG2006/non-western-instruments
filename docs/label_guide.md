# Label guide (draft: fill in before labeling)

Label by ear. The label is the instrument you hear, whatever the uploader called it.

- **reject (x):** not one of the listed instruments, or unusable (speech, noise, heavy effects, synthesized).
- **unsure (u):** you cannot tell. These clips stay out of the test set.
- **solo = n:** another instrument or voice is clearly audible.
- **confident = n:** you think you know, but would not defend it.

| Key | Label | Tradition | Family | Accepted names / variants | Exclude | Notes |
|---|---|---|---|---|---|---|
| 1 | erhu | chinese | bowed | erhu, 二胡 | other huqin: jinghu, gaohu, zhonghu, banhu; "huqin" without erhu | Other huqin are rejected (x), even when the uploader calls them erhu. Unsure erhu vs. other huqin = u. |
| 2 | pipa | chinese | plucked | pipa lute, chinese pipa, 琵琶 | other Chinese lutes (liuqin, ruan, yueqin, sanxian); Japanese biwa | 'pipa' also means pipe (Swedish) and a frog genus; screen titles. |
| 3 | dizi | chinese | wind | dizi flute, chinese bamboo flute, 笛子 | end-blown xiao; free-reed bawu and hulusi; Western concert flute |  |
| 4 | guzheng | chinese | zither | guzheng, gu zheng, 古筝 | guqin (no bridges); Japanese koto; Korean gayageum; Vietnamese dan tranh | Cousin is a proposal; no Western zither is collected. Confirm. |
| 5 | charango | andean | plucked | charango, ronroco, walaycho (hualaycho) | ukulele, cuatro, mandolin and other non-Andean small lutes (proposed 2026-11-19, unconfirmed) | Ronroco and walaycho count as charango (decided 2026-11-16). |
| 6 | quena | andean | wind | quena, kena flute, andean flute | quenacho (larger, lower); pinkillo and other duct flutes; ney |  |
| 7 | siku | andean | wind | siku, zampoña, zampona, antara panpipe, andean panpipe | non-Andean panpipes (Romanian nai, Western pan flute); ensembles of more than one player are solo = n |  |
| 8 | bombo | andean | drum | bombo legüero, bombo leguero, bombo andino | Western bass drum, kick drums, synthesized drums, maracatu and other non-Andean bombos | Reported as insufficient data (decided 2026-11-16). |
| 9 | oud | middle_east | plucked | oud, ud lute, عود | European lute; baglama/saz and other long-necked lutes; cumbus | 'oud' is Dutch for 'old'; Commons search is noisy. |
| 10 | ney | middle_east | wind | ney flute, nay flute, ney turkish, ney arabic | kaval; shakuhachi; quena; Western flute | Include Turkish and Arab ney; exclude Persian ney only if the label guide says so. |
| 11 | qanun | middle_east | zither | qanun, kanun instrument, qanoun | santur, cimbalom and other hammered zithers; guzheng and other East Asian zithers; harp | Cousin is a proposal. Confirm. |
| 12 | darbuka | middle_east | drum | darbuka, darbouka, doumbek, dumbek, goblet drum, derbake | Persian tombak; frame drums (riq, daf, bendir); djembe (proposed 2026-11-19, unconfirmed) | Exclude Persian tombak. |
| 13 | sitar | control | plucked | sitar | sarod, surbahar; tanpura drone without sitar; electric sitar (proposed 2026-11-19, unconfirmed) |  |
| 14 | tabla | control | drum | tabla | pakhawaj, dholak, mridangam; tabla samples arranged as loops (proposed 2026-11-19, unconfirmed) |  |
| 15 | violin | western | bowed | violin solo, solo violin | viola, cello and other bowed strings; erhu; heavily processed electric violin (proposed 2026-11-19, unconfirmed) |  |
| 16 | flute | western | wind | flute solo, concert flute | piccolo, recorder, dizi, bansuri, ney, quena and panpipes (proposed 2026-11-19, unconfirmed) |  |
| 17 | acoustic_guitar | western | plucked | acoustic guitar solo, fingerstyle acoustic guitar | electric guitar, bass guitar, steel/slide guitar, ukulele, charango (proposed 2026-11-19, unconfirmed) |  |
| 18 | snare_drum | western | drum | snare drum solo, snare drum | drum-kit grooves, tom-toms, marching tenor drums, electronic snare samples (proposed 2026-11-19, unconfirmed) | Proposed Western drum cousin. Confirm. |

## Clip window rule (decided 2026-11-15; replaces "first 10 s after the first sustained onset")
- Each recording is decoded to mono at its source sample rate. 10 s windows are scored by RMS level in dBFS, stepping 5 s at a time.
- Windows are ranked loudest first; a window that overlaps an already chosen one is skipped; windows below -45 dBFS are never used; at most 3 per recording.
- Pass 1 takes the loudest window of every approved recording, walking uploaders round-robin. Later passes take the 2nd and 3rd loudest, until the instrument reaches 60 clips or 12 per uploader. This spends the clip budget on more uploaders first.
- Recordings of 5 to 10 s give one clip, padded with silence to 10 s; `content_s` in the manifest gives the real length.
- Reason: the rule is deterministic and lands on playing rather than on a quiet start. Risk: it can pick a loud non-musical event; listening catches that (reject x).
- Clip ids end in the window rank (`_0` = loudest). The first cut (2026-11-15, 32 kHz, up to 3 clips per recording before moving on) was set aside in `data/clips_v0/` and is not used.

## Decisions to record here
- **charango variants (decided 2026-11-16):** ronroco (larger, lower-tuned) and walaycho (smaller, higher-tuned) count as charango. They share the charango's construction and playing tradition; register differs. Record the variant in the clip note when you can hear it.
- **bombo (decided 2026-11-16):** kept in the plan but reported as insufficient data. After broadened searches, Freesound and Commons gave 15 approved recordings whose metadata point to synth kicks, rhythm exercises, maracatu and a street march, with 0 to 2 plausible bombo legüero. Label them by ear anyway; report bombo with its real n and the reason.
- **erhu vs. other huqin (decided 2026-11-15):** exclude jinghu, gaohu, zhonghu and banhu. Reason: they share erhu's construction but differ in register and timbre (jinghu and gaohu are much higher; banhu has a wooden soundboard), so folding them in widens the class beyond one instrument and makes the erhu vs. violin comparison noisier. Metadata mentions of other huqin do not reject a clip on their own; the label is decided by ear.
- **Ceremonial and consent context (decided 2026-11-15):** reject recordings of funerals and other rites whose participants could not reasonably have agreed to dataset use (first case: fs:453003, Taoist funeral, Bangkok). Recordings that only mention a temple as the venue are labeled normally, unless what you hear suggests a rite is in progress.
- **ney variants (decided 2026-11-19):** Turkish, Arab and Persian ney all count as ney. They are the same rim-blown cane flute; playing technique differs, so variant is noted in the clip note when audible.
- **siku ensembles (decided 2026-11-19):** a zampoña ensemble is not solo (solo = n) unless one player is heard. Antara (single-row panpipe) counts as siku.
- **reverb (decided 2026-11-19):** light reverb is acceptable for every instrument; heavy effects are rejected (x).
