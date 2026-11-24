# Take 7 inputs

- `01.mp3` … `08.mp3`: ElevenLabs narration (Indian English voice "Sid", Multilingual v2, speed 0.9), one clip per scene.
  `narration_full.mp3` is the uncut file.

  | Clip | Scene | Length |
  |---|---|---|
  | 01 | Problem | 10.9 s |
  | 02 | What it does | 14.8 s |
  | 03 | Reading | 16.5 s |
  | 04 | Ask | 15.6 s |
  | 05 | Trust | 11.6 s |
  | 06 | Errors | 9.2 s |
  | 07 | Human in the loop | 13.1 s |
  | 08 | Close | 6.5 s |

- `titan-logo.svg` / `titan-logo-3840.png`: Titan Company logo (2018, from Wikipedia), for the first and last slides.
  `titan-logo.png` (162 px) is only for the small mark on the app rail.
- `TYN_Horizontal_Logo.png`: The Yellow Network logo.

## Take 7 changes

1. **Voice:** use clips 01–08 in order, and time each scene to its clip, with a gap of about 0.7 s between scenes.
2. **Pacing:** hold each chat answer (CNC / absenteeism / least productive) and each error close-up for at least
   5 s, even if the screen stays on after the voice ends. Target about 2:00.
3. **Fix:** in the "More accepted than produced" close-up, the "Read by the AI" table renders as an empty grey box.
4. **Logos:**
   - App rail: a small Titan mark top-left, beside "Shift Logger" (on a white tile, about 32 px).
   - First and last slides: the Titan and The Yellow Network logos side by side on a white rounded panel, centred and
     prominent. Use `titan-logo.svg`. Keep the original colours.
5. **Captions:** match the new wording. Scenes 03, 04, 06 and 07 changed slightly; the script is below.

## Narration script

01. In Titan's press shop, about eighty operators hand-write a job card every shift. Each one is copied into a
    register, and then typed into Excel.
02. Shift Logger reads every field of the scanned card, checks it against the codes, the hours and the master lists,
    sends only the doubtful cards to the supervisor, and lets management ask questions in plain English.
03. Here's a card going in. The AI reads it in seconds. Every value is read exactly as written. The operator number
    is filled on every row, and these ditto marks become S10202 and 1163.
04. Which CNC machine lost the most hours? Who has the highest absenteeism? Who is the least productive? Every answer
    comes with a chart, straight from the database, and the query behind it is just one click away.
05. But can you trust these numbers? Handwriting isn't perfect, and people make mistakes. So every card is checked
    against the code sheet, the shift hours, and the master lists.
06. This code doesn't exist on the code sheet, so the system suggests the right one. And here, the accepted quantity
    is more than what was produced.
07. Cards like these never reach the data on their own. The supervisor sees the photo beside the reading, corrects
    it, and approves. Clean cards are saved automatically, so only the doubtful ones need a person.
08. It all runs on open-source AI, on Titan's own server, so the data never leaves the plant.
