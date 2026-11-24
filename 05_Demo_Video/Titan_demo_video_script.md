# Current: take 7 (24 Nov 2026)

Take 7 is about 2:00. It uses an Indian English voice from ElevenLabs, holds the screens longer, and puts the Titan logo on every app screen and both logos on the first and last slides. The narration (8 scenes), the logos and the change list are in `take7_audio/README.md`. It replaces the plan below:

- the text is the take-6 wording, slightly expanded;
- the "Next step" line has been dropped;
- the voice is ElevenLabs, not Lathiesh.

# Titan Shift Logger: PoC demo video, 1:30, spoken by Lathiesh (19 Nov 2026) - superseded by take 7

Lathiesh speaks over a screen recording of the real PoC (no mock-ups). About 190 words, about 80 s of speech plus short pauses on screen.

**Flow: problem → demo → value → errors → human in the loop → next step.**
- **Problem first:** this is Titan's first look, so start with their pain.
- **Value early:** the result comes right after the reading, at about 0:24 ("show the result first").
- **Errors + human in the loop answer the objection** "can I trust these numbers?" right before the close.

| # | Part | Time | On screen | Say |
|---|---|---|---|---|
| 1 | **Problem** | 0:00-0:12 | The C02 photo full screen, then a simple card: job card → register → Excel → report | "Titan's press shop has about eighty operators across two shifts, and each one hand-writes a job card. It's copied into a register, typed into Excel, and only then does management get a report." |
| 2 | **Demo: reading** | 0:12-0:24 | Upload C02, then the split view: photo on the left, extracted rows on the right. Zoom on a ditto row | "Here's what we built. We scan the card, and the AI reads every field: the handwriting, the ditto marks, all of it." |
| 3 | **Value** | 0:24-0:46 | Chat: "Which CNC machine lost the most hours to breakdowns?" → text + bar chart. "Who has the highest absenteeism?" → ranked table. "Who's least productive?" → table. Click "Show details": the query | "And management asks the questions you told us matter. Which CNC machine lost the most hours? Who has the highest absenteeism? Who's least productive? The answer comes with a chart, straight from the database, and the query behind it is one click away." |
| 4 | **Errors** (the bridge) | 0:46-1:03 | C04: flag "10613 not on code sheet → 10813". Then C08: "Accepted 650 > produced 600" | "But can you trust these numbers? Handwriting isn't perfect, and people make mistakes. So every card is checked against the code sheet, the shift hours and the master lists. This code doesn't exist, so it suggests the right one. Here, accepted is more than produced." |
| 5 | **Human in the loop** | 1:03-1:18 | Review screen: photo beside fields; click the suggestion, Approve. Then the card list: most "Saved", a few "Needs review" | "Cards like these never reach the data on their own. The supervisor sees the photo beside the reading, corrects it, and approves. Clean cards save automatically, so only the doubtful ones need a person." |
| 6 | **Close + next step** | 1:18-1:30 | End card: "Read · Ask · Check · Review", "Runs on Titan's own server", "Next step: pilot on 50 real job cards" | "It all runs on open-source AI, on Titan's own server, so the data never leaves the plant. Next step: we try it on fifty of Titan's real job cards." |

Covers 3 of the 4 MoM questions (CNC downtime, absenteeism, least productive). The manual troubleshooting question is left out: it needs a manual loaded and would push past 1:30.

**Speaking tips**
- Say it as if you're showing a colleague. Pause for half a second each time a result or flag appears.
- **Part 4's first line is the turn.** Pause before "But can you trust these numbers?" and slow down through parts 4-5.
- If it runs over 1:30, cut in this order: (1) "Here, accepted is more than produced." (about 3 s); (2) "Who's least productive?" (about 2 s).
- Don't quote accuracy figures or model names. "About eighty operators" is from the MoM (5 Nov 2026); drop the number if unsure.

**Must work on screen:** upload + reading (C02); chat with bar chart, ranked tables and "Show details" on synthetic data; flags on C04 and C08; review screen with approve; card list with statuses; end card.

---

# Full version: demo video script v2 (target 1:25 to 1:30), for later

v2 (19 Nov 2026) restructures v1 using standard demo-pitch practice:
- **"Last thing first"** (Peter Cohan, *Great Demo!*): open on the result the buyer wants, then show how it's made.
- **Hook in the first 5-10 s**, then problem, solution, proof, and **one clear call to action**.
- **The customer's own words:** the questions are the ones Titan asked in the 5 Nov 2026 MoM.
- **About 180 words** of narration for 90 s (the median pace is about 135 words a minute, plus on-screen holds).

Format: 1920x1080, AIRA look (navy cards, orange accent). Calm, warm voice, one clip per scene. Subtitles burned in.
Client-facing: no model or framework names. Synthetic cards and data only.

## Components: v1 → v2

| Component | v1 | v2 | Why |
|---|---|---|---|
| Hook (0-8 s) | Title card + "Meet the Shift Logger…" | **Cold open on the answer:** Titan's own CNC-downtime question, answered with a chart, then the title | Viewers decide in the first seconds. Show the outcome, not the logo |
| Problem | "eighty operators… every shift" (inaccurate) | MoM wording: about 80 operators **across two shifts**; card → register → Excel | Their process in their words. Accurate to the MoM |
| Solution | Read, then check, as two separate features | Read → check → review as one flow | One idea at a time, one continuous story |
| Proof / trust | Implied | Said outright: only unclear cards reach a person; every number traces back to the database; manual page cited | Management's real worry is "can I trust the number?" |
| Value | Generic questions | **All 4 MoM questions**: downtime (hook), absenteeism, least productive, troubleshooting | Shows we listened. Discovery-based demo |
| Close | Tagline only | On-prem promise + **call to action: "run it on fifty of your own job cards"** | One concrete next step. Matches the proposal (Titan gives 50-100 sample cards) |

## Narration and shots

| # | Scene (audio) | Time | Narration | On screen |
|---|---|---|---|---|
| 1 | `hook` | 0:00-0:08 | Which CNC machine lost the most hours to breakdowns in the last four months? Answered in seconds, from handwritten job cards. | **Cold open:** the chat with the question already typed, the answer streaming in and a bar chart by machine. At 0:06, a 2 s lower-third or title: "Shift Logger · Titan Watch Division" |
| 2 | `today` | 0:08-0:17 | Today, about eighty operators across two shifts hand-write a job card. Each card is copied into a register, then typed into Excel, before anyone sees a number. | Card: job card → register → Excel → report, each arrow drawn in turn. "~80 operators · 2 shifts" |
| 3 | `read` | 0:17-0:28 | Now the scanned card goes straight in. The AI reads the handwriting, ditto marks and all, and fills every field in seconds. | Upload `C02_front.jpeg`, wait compressed to about 1 s. Split view: photo on the left, fields on the right. Zoom on a ditto row |
| 4 | `check` | 0:28-0:43 | Every card is checked against the code sheet, the shift hours and the master lists. This code isn't on the sheet, so it goes to the supervisor, with the likely fix. Clean cards save automatically. | Review page: `C04` flag "10613 not on code sheet → 10813?". Zoom on it. Click the suggestion, then "Approve". Cut to the list: most cards "Saved", a few "Needs review" |
| 5 | `ask` | 0:43-1:05 | Then management asks the questions you told us matter. Which operator has the highest absenteeism? Which operators have the lowest productivity? Every number comes straight from the database, and the query behind it is one click away. | Type question 1 → ranked table. Type question 2 → bar chart. Click "Show details": the SQL and rows. Zoom on the query. Close |
| 6 | `manual` | 1:05-1:15 | And on the shop floor: the press won't start. What do I check first? Steps from the machine manual, page cited. | Type "Press 604020.08 won't start, what should I check first?". Numbered steps with "Manual, p. 42". Click: the manual page opens |
| 7 | `close` | 1:15-1:28 | Open-source AI, on Titan's own server. Your data never leaves the plant. Next step: we run it on fifty of your own job cards. | End card: "Read · Check · Ask", "Runs on-premises · no public AI services", then "Next step: a pilot on 50 of your job cards". TYN footer |

About 180 words in total.

## Full text (single-file option)

Which CNC machine lost the most hours to breakdowns in the last four months? Answered in seconds, from handwritten job cards.
Today, about eighty operators across two shifts hand-write a job card. Each card is copied into a register, then typed into Excel, before anyone sees a number.
Now the scanned card goes straight in. The AI reads the handwriting, ditto marks and all, and fills every field in seconds.
Every card is checked against the code sheet, the shift hours and the master lists. This code isn't on the sheet, so it goes to the supervisor, with the likely fix. Clean cards save automatically.
Then management asks the questions you told us matter. Which operator has the highest absenteeism? Which operators have the lowest productivity? Every number comes straight from the database, and the query behind it is one click away.
And on the shop floor: the press won't start. What do I check first? Steps from the machine manual, page cited.
Open-source AI, on Titan's own server. Your data never leaves the plant. Next step: we run it on fifty of your own job cards.

## Checks before production

- **Read it aloud with a timer.** If it's over 1:30, shorten scene 2 to "Today, every card is copied into a register, then typed into Excel." (saves about 4 s) before cutting anything else.
- **Test it on 2-3 people** who haven't seen the project (for example Amit, and someone non-technical). Ask what it does and what the next step is. If they can't say both, fix the script before recording.
- **No accuracy figures are spoken.** The bake-off ran on 10 synthetic cards; quoting "99.6%" to a client would over-promise before real cards are tested.
- **Confirm "about eighty operators"** with Titan, or drop the number (source: MoM 5 Nov 2026, line 16; pilot department only).
- **Titan logo:** only with approval.

## What must exist before recording

| Needed for | Item |
|---|---|
| Scenes 1, 5 | About 4 months of synthetic data (about 80 operators, 2 shifts) with planted patterns: one CNC machine with clearly the most breakdown hours, 2-3 often-absent operators, a spread of output. Chat with text, bar chart, table and "Show details" |
| Scenes 3-4 | Upload with split view; review page with flag, suggestion, approve. Synthetic photos C02 and C04 |
| Scene 6 | One public press-machine manual in the knowledge base, with page citations |
| Cards | Problem and end cards in the AIRA style (reuse `DCM-Shriram/05_Demo_Video/tools/cards.html`) |

Production follows the AIRA tools: Playwright recording, ElevenLabs clips, `edit.py`, then `subtitles.py`.
