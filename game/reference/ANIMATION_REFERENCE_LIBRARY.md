# Animation Reference Library

## ALADDIN SNES

**Reference status (2026-08-27):** A locally available ROM was found in
`C:\SNES\Nes Roms\SNES ROMs Pack (Romspack.com)\Aladdin (U) [!].zip`.
The archive contains `Aladdin (U) [!].smc`. BizHawk is installed at
`C:\SNES\Tools\BizHawk\runtime\EmuHawk.exe`.

The startup probe was subsequently advanced through the title flow with
emulated SNES Start input. A playable level was reached and a rightward input
produced a visible player-position change. A reusable BizHawk baseline was
saved at `analysis/reference_games/aladdin/aladdin_gameplay_baseline.State`,
with screenshot `aladdin_gameplay_baseline.png`.

### Capture folders

Analysis-only captures are under `analysis/reference_games/aladdin/`. These
screenshots and the save state are reference material only, not game assets.

### Pending observations

Animation analysis has not started yet. The baseline is now suitable for the
next approved capture pass covering idle, run, stop, crouch, jump, landing,
gestures, and hip/thigh structure.

### ALADDIN SNES – IDLE

The supplied baseline state loaded successfully, but it does not hold Aladdin
in a stable standing position: during a neutral 180-frame capture the scene
changes position and then fades to black. Consequently no complete idle cycle
or body-part motion is attributed to this capture. A corrected standing state
is required before idle timing and anchors can be documented.

### KAEL LESSONS FROM ALADDIN IDLE

No idle-specific lessons were added because a valid idle cycle was not
observed.

### ALADDIN SNES – VERIFIED IDLE ANALYSIS

Using the verified quick-save, 600 consecutive neutral frames were captured.
Gameplay and camera remained stable. Pixel comparison of Aladdin's sprite crop
showed no change across the capture (`maxDiff=0`), so this state presents a
static standing pose rather than a measurable idle loop or longer gesture.
No head, torso, shoulder, arm, hip, thigh, leg, or foot movement can be
attributed to an idle animation from this state. Timing, anticipation,
recovery, and return-to-neutral are therefore not observable.

The only supported reference lesson is to verify that a save state is actually
animating before inferring body hierarchy or timing.

The existing BizHawk quick-save
`C:\SNES\Tools\BizHawk\runtime\SNES\State\Aladdin (USA).Snes9x.QuickSave1.State`
was also loaded successfully with the specified ROM and remained in the same
playable camera area for 300 neutral frames. It is the preferred reference
state for subsequent captures; no replacement state was created.

## KAEL LESSONS FROM ALADDIN

No Aladdin-specific lessons are asserted until playable frames are captured.
The following are the observation checklist to apply during the next verified
capture: anchor the pelvis over the supporting leg; overlap the upper thigh
under the belt/waist; let the torso lead a gesture; stage anticipation before
the main action; hold the peak briefly; return each limb to a defined base pose;
keep feet on a stable ground line; shift weight before moving the free leg;
use recovery frames after landing or stopping; and keep every expressive pose
within one connected body structure.
