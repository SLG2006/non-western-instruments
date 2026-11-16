# Label guide (draft: fill in before labeling)

Label by ear. The label is the instrument you hear, whatever the uploader called it.

- **reject (x):** not one of the listed instruments, or unusable (speech, noise, heavy effects, synthesized).
- **unsure (u):** you cannot tell. These clips stay out of the test set.
- **solo = n:** another instrument or voice is clearly audible.
- **confident = n:** you think you know, but would not defend it.

| Key | Label | Tradition | Family | Accepted names / variants | Exclude | Notes |
|---|---|---|---|---|---|---|
| 1 | erhu | chinese | bowed | erhu, 二胡 | other huqin: jinghu, gaohu, zhonghu, banhu; "huqin" without erhu | Other huqin are rejected (x), even when the uploader calls them erhu. Unsure erhu vs. other huqin = u. |
| 2 | pipa | chinese | plucked | pipa lute, chinese pipa, 琵琶 | TODO | 'pipa' also means pipe (Swedish) and a frog genus; screen titles. |
| 3 | dizi | chinese | wind | dizi flute, chinese bamboo flute, 笛子 | TODO |  |
| 4 | guzheng | chinese | zither | guzheng, gu zheng, 古筝 | TODO | Cousin is a proposal; no Western zither is collected. Confirm. |
| 5 | charango | andean | plucked | charango | TODO |  |
| 6 | quena | andean | wind | quena, kena flute, andean flute | TODO |  |
| 7 | siku | andean | wind | siku, zampoña, zampona, antara panpipe, andean panpipe | TODO |  |
| 8 | bombo | andean | drum | bombo legüero, bombo leguero, bombo andino | TODO |  |
| 9 | oud | middle_east | plucked | oud, ud lute, عود | TODO | 'oud' is Dutch for 'old'; Commons search is noisy. |
| 10 | ney | middle_east | wind | ney flute, nay flute, ney turkish, ney arabic | TODO | Include Turkish and Arab ney; exclude Persian ney only if the label guide says so. |
| 11 | qanun | middle_east | zither | qanun, kanun instrument, qanoun | TODO | Cousin is a proposal. Confirm. |
| 12 | darbuka | middle_east | drum | darbuka, darbouka, doumbek, dumbek, goblet drum, derbake | TODO | Exclude Persian tombak. |
| 13 | sitar | control | plucked | sitar | TODO |  |
| 14 | tabla | control | drum | tabla | TODO |  |
| 15 | violin | western | bowed | violin solo, solo violin | TODO |  |
| 16 | flute | western | wind | flute solo, concert flute | TODO |  |
| 17 | acoustic_guitar | western | plucked | acoustic guitar solo, fingerstyle acoustic guitar | TODO |  |
| 18 | snare_drum | western | drum | snare drum solo, snare drum | TODO | Proposed Western drum cousin. Confirm. |

## Decisions to record here
- **erhu vs. other huqin (decided 2026-11-15):** exclude jinghu, gaohu, zhonghu and banhu. Reason: they share erhu's construction but differ in register and timbre (jinghu and gaohu are much higher; banhu has a wooden soundboard), so folding them in widens the class beyond one instrument and makes the erhu vs. violin comparison noisier. Metadata mentions of other huqin do not reject a clip on their own; the label is decided by ear.
- **Ceremonial and consent context (decided 2026-11-15):** reject recordings of funerals and other rites whose participants could not reasonably have agreed to dataset use (first case: fs:453003, Taoist funeral, Bangkok). Recordings that only mention a temple as the venue are labeled normally, unless what you hear suggests a rite is in progress.
- Which ney variants count (Turkish, Arab, Persian)?
- Is a zampoña ensemble 'solo' siku? (Proposed: no, unless one player.)
- Is an erhu with light reverb acceptable? (Proposed: yes; reject heavy effects.)
