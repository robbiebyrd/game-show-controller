# Show Asset Checklist

Production checklist of the external assets each show file expects: **sound
cues** to collect, **lighting cues** to create on the DMX/lighting controller,
and **OBS scenes** to build. Generated from the `shows/*.y*ml` files; regenerate
after editing a show or adding assets.

_Last generated: 2026-07-09_

**Sound status legend** — paths resolve relative to the working directory, so
the show files reference them as `music/…`, and the engine loads the *exact*
filename (extension included):

- ✅ **present** — the exact file exists in `music/`.
- ⚠️ **wrong ext** — a file with that name exists but a different extension than
  the show references. It will **not** load until the show path matches the
  real filename (or the file is re-encoded to the referenced format).
- ⬜ **missing** — nothing with that name is in `music/` yet.

## Summary

| Show | File | ✅ present | ⚠️ wrong ext | ⬜ missing | Lighting cues | OBS scenes |
|------|------|-----------|--------------|-----------|---------------|------------|
| Family Feud | `shows/family_feud.yaml` | 13 | 0 | 1 | 20 | 18 |
| $10,000 Pyramid | `shows/pyramid.yaml` | 0 | 0 | 13 | 15 | 11 |
| Trivia Night | `shows/trivia.yml` | 0 | 0 | 14 | 15 | 16 |

## Family Feud

`shows/family_feud.yaml`

### 🔊 Sound cues — 13 present, 0 wrong-ext, 1 missing (of 14)

| Status | Referenced by show | Found in `music/` |
|--------|--------------------|-------------------|
| ✅ present | `music/FamilyFeud_Answer_Reveal.wav` | FamilyFeud_Answer_Reveal.wav |
| ✅ present | `music/FamilyFeud_Board_Reveal.wav` | FamilyFeud_Board_Reveal.wav |
| ⬜ missing | `music/FamilyFeud_FaceOff_Buzz.mp3` | — |
| ✅ present | `music/FamilyFeud_FaceOff_Sting.wav` | FamilyFeud_FaceOff_Sting.wav |
| ✅ present | `music/FamilyFeud_FaceOff_Win.wav` | FamilyFeud_FaceOff_Win.wav |
| ✅ present | `music/FamilyFeud_Round_Start.mp3` | FamilyFeud_Round_Start.mp3 |
| ✅ present | `music/FamilyFeud_SpeedRound_Intro.wav` | FamilyFeud_SpeedRound_Intro.wav |
| ✅ present | `music/FamilyFeud_SpeedRound_Tick.wav` | FamilyFeud_SpeedRound_Tick.wav |
| ✅ present | `music/FamilyFeud_SpeedRound_TimeUp.mp3` | FamilyFeud_SpeedRound_TimeUp.mp3 |
| ✅ present | `music/FamilyFeud_Steal_Win.wav` | FamilyFeud_Steal_Win.wav |
| ✅ present | `music/FamilyFeud_Strike_Buzz.wav` | FamilyFeud_Strike_Buzz.wav |
| ✅ present | `music/FamilyFeud_Theme.wav` | FamilyFeud_Theme.wav |
| ✅ present | `music/FamilyFeud_Three_Strikes.wav` | FamilyFeud_Three_Strikes.wav |
| ✅ present | `music/FamilyFeud_Winner_Celebration.wav` | FamilyFeud_Winner_Celebration.wav |

### 💡 Lighting cues to create (20)

- `/live/Control_Panel/cue/Board_Reveal/activate`
- `/live/Control_Panel/cue/Buzz_Left/activate`
- `/live/Control_Panel/cue/Buzz_Right/activate`
- `/live/Control_Panel/cue/Correct_Answer/activate`
- `/live/Control_Panel/cue/FaceOff_Buzz/activate`
- `/live/Control_Panel/cue/FaceOff_Ready/activate`
- `/live/Control_Panel/cue/FaceOff_Win/activate`
- `/live/Control_Panel/cue/Game/activate`
- `/live/Control_Panel/cue/Intro_Sweep/activate`
- `/live/Control_Panel/cue/Round_Play/activate`
- `/live/Control_Panel/cue/Round_Start/activate`
- `/live/Control_Panel/cue/SpeedRound_P1/activate`
- `/live/Control_Panel/cue/SpeedRound_Play/activate`
- `/live/Control_Panel/cue/SpeedRound_Ready/activate`
- `/live/Control_Panel/cue/SpeedRound_TimeUp/activate`
- `/live/Control_Panel/cue/Steal_Win/activate`
- `/live/Control_Panel/cue/Strike/activate`
- `/live/Control_Panel/cue/Three_Strikes/activate`
- `/live/Control_Panel/cue/Winner_Celebration/activate`
- `/live/Control_Panel/cue/Winner_Reveal/activate`

_Also uses the built-in clear-all command `/live/*/cue/*/deactivate 0` (not a cue to build)._

### 🎬 OBS scenes to make (18)

- `Answer_Reveal`
- `Board_Reveal`
- `FaceOff_Buzz`
- `FaceOff_Ready`
- `FaceOff_Win`
- `FamilyFeud_Intro`
- `FamilyFeud_Outro`
- `Game_Idle`
- `Game_Over`
- `Round_Board`
- `Round_Start`
- `SpeedRound_Player1`
- `SpeedRound_Player2`
- `SpeedRound_Reveal`
- `SpeedRound_TimeUp`
- `Steal_Win`
- `Strike_Display`
- `Three_Strikes`

## $10,000 Pyramid

`shows/pyramid.yaml`

### 🔊 Sound cues — 0 present, 0 wrong-ext, 13 missing (of 13)

| Status | Referenced by show | Found in `music/` |
|--------|--------------------|-------------------|
| ⬜ missing | `music/Pyramid_Circle_Correct.mp3` | — |
| ⬜ missing | `music/Pyramid_Cuckoo.mp3` | — |
| ⬜ missing | `music/Pyramid_Item_Correct.mp3` | — |
| ⬜ missing | `music/Pyramid_Jackpot.mp3` | — |
| ⬜ missing | `music/Pyramid_Outro.mp3` | — |
| ⬜ missing | `music/Pyramid_Perfect_21.mp3` | — |
| ⬜ missing | `music/Pyramid_Subject_Clock.mp3` | — |
| ⬜ missing | `music/Pyramid_Subject_Score.mp3` | — |
| ⬜ missing | `music/Pyramid_Theme.mp3` | — |
| ⬜ missing | `music/Pyramid_Tiebreaker.mp3` | — |
| ⬜ missing | `music/Pyramid_Time_Up.mp3` | — |
| ⬜ missing | `music/Pyramid_Winner_Reveal.mp3` | — |
| ⬜ missing | `music/Pyramid_Winners_Circle_Start.mp3` | — |

### 💡 Lighting cues to create (15)

- `/live/Control_Panel/cue/Board_Reveal/activate`
- `/live/Control_Panel/cue/Circle_Correct/activate`
- `/live/Control_Panel/cue/Cuckoo/activate`
- `/live/Control_Panel/cue/Intro_Sweep/activate`
- `/live/Control_Panel/cue/Item_Correct/activate`
- `/live/Control_Panel/cue/Perfect_21/activate`
- `/live/Control_Panel/cue/Reveal/activate`
- `/live/Control_Panel/cue/Subject_Clock/activate`
- `/live/Control_Panel/cue/Subject_Score/activate`
- `/live/Control_Panel/cue/Team_Ready/activate`
- `/live/Control_Panel/cue/Time_Up/activate`
- `/live/Control_Panel/cue/Winner_Celebration/activate`
- `/live/Control_Panel/cue/Winner_Reveal/activate`
- `/live/Control_Panel/cue/Winners_Circle_Ready/activate`
- `/live/Control_Panel/cue/Winners_Circle_Win/activate`

_Also uses the built-in clear-all command `/live/*/cue/*/deactivate 0` (not a cue to build)._

### 🎬 OBS scenes to make (11)

- `Pyramid_Board`
- `Pyramid_Game_Over`
- `Pyramid_Intro`
- `Pyramid_Outro`
- `Pyramid_Perfect_21`
- `Pyramid_Subject_Play`
- `Pyramid_Subject_Score`
- `Pyramid_Team_Ready`
- `Pyramid_Time_Up`
- `Pyramid_Winners_Circle`
- `Pyramid_Winners_Circle_Win`

## Trivia Night

`shows/trivia.yml`

### 🔊 Sound cues — 0 present, 0 wrong-ext, 14 missing (of 14)

| Status | Referenced by show | Found in `music/` |
|--------|--------------------|-------------------|
| ⬜ missing | `music/Trivia_Buzz_P1.mp3` | — |
| ⬜ missing | `music/Trivia_Buzz_P2.mp3` | — |
| ⬜ missing | `music/Trivia_Buzz_P3.mp3` | — |
| ⬜ missing | `music/Trivia_Buzz_P4.mp3` | — |
| ⬜ missing | `music/Trivia_Correct.mp3` | — |
| ⬜ missing | `music/Trivia_Final_Question.mp3` | — |
| ⬜ missing | `music/Trivia_Final_Reveal.mp3` | — |
| ⬜ missing | `music/Trivia_Final_Think.mp3` | — |
| ⬜ missing | `music/Trivia_Game_Over.mp3` | — |
| ⬜ missing | `music/Trivia_Outro.mp3` | — |
| ⬜ missing | `music/Trivia_Round_Start.mp3` | — |
| ⬜ missing | `music/Trivia_Theme.mp3` | — |
| ⬜ missing | `music/Trivia_Timeout.mp3` | — |
| ⬜ missing | `music/Trivia_Wrong.mp3` | — |

### 💡 Lighting cues to create (15)

- `/palette/Buzz_P1/activate`
- `/palette/Buzz_P2/activate`
- `/palette/Buzz_P3/activate`
- `/palette/Buzz_P4/activate`
- `/palette/Correct/activate`
- `/palette/FinalCategory/activate`
- `/palette/FinalThink/activate`
- `/palette/GameOver/activate`
- `/palette/Idle/activate`
- `/palette/Incorrect/activate`
- `/palette/Intro/activate`
- `/palette/Locked/activate`
- `/palette/Reveal/activate`
- `/palette/RoundStart/activate`
- `/palette/Timeout/activate`

### 🎬 OBS scenes to make (16)

- `Allow_Next`
- `Buzz_Locked`
- `Buzz_Timeout`
- `Correct`
- `Final_Reveal`
- `Final_Think`
- `Game_Over`
- `Idle`
- `Incorrect`
- `Round_Start`
- `Trivia_Final`
- `Trivia_Final_Category`
- `Trivia_Intro`
- `Trivia_Outro`
- `Trivia_Round1_Board`
- `Trivia_Round2_Board`

