# Stream Deck Control Surface

Drives an Elgato Stream Deck (15-key MK.2 / Original, 3×5) as a hardware control
surface for the game-show controller. Runs in-process alongside the other
components and is configured entirely from `config.yaml` under the top-level
`control_surface:` key.

## Prerequisites

The `streamdeck` library talks to the device over USB HID via `hidapi`, a native
library that is **not** a pip package:

```bash
brew install hidapi          # macOS (Apple Silicon → /opt/homebrew/lib/libhidapi.dylib)
```

- No macOS "Input Monitoring" permission is needed — the deck is a vendor HID
  device, not a keyboard.
- If startup logs `ProbeError: ... functional HID backend` or a `TransportError`,
  `hidapi` is missing or not on the library search path. Install it
  (`brew install hidapi`) and verify with `ls /opt/homebrew/lib/libhidapi*`.
- **Quit the Elgato Stream Deck desktop app first.** It claims the device
  exclusively; the controller and the Elgato app cannot both own the deck.
- If the backend or device is unavailable, the control surface logs a warning
  and runs inert — the rest of the service (buzzers, OSC, OBS, audio) still runs.

Python dependencies (`streamdeck`, `pillow`) install via `poetry install`.
Requires Python ≥ 3.11.

## Behaviour

- Keys are 0-indexed, left-to-right, top-to-bottom: key 0 = top-left,
  key 4 = top-right, key 10 = **bottom-left**, key 14 = bottom-right.
- Each button's slot is derived from its **`button_<N>`** name, where `N` is the
  key index (0–14). Names are YAML mapping keys, so they must be unique per page.
- A `page` button opens a nested page. **Every sub-page reserves key 10 for an
  automatic "return to previous page" button** — don't use `button_10` on a
  sub-page (it would be skipped with a warning).
- Live keys re-render from bus events: `countdown` (display), `scene_current`,
  and `state_display`.
- If no deck is connected at startup, the component logs a warning and stays
  inert — the rest of the service runs normally.

## Configuration

`buttons` is a **mapping** of an arbitrary name to a button spec. The name is
just an identifier (handy for readability and log messages); declaration order
determines auto-placement.

```yaml
control_surface:
  enabled: true          # default true
  brightness: 60         # 0-100
  serial: "AL1234"       # optional: select a specific deck by serial
  font_path: "assets/Roboto-Regular.ttf"   # default TTF for labels
  font_size: 16          # default label size          (default 16)
  text_color: white      # default label color         (default white)
  label_align: center    # top | center | bottom       (default bottom)
  label_wrap: true       # word-wrap long labels        (default false)
  label_marquee: true    # scroll labels that overflow  (default true)
  root:
    buttons:
      player_1:
        type: buzz
        label: "P1"
        player_id: 1
        key: 1
      audio_folder:
        type: page
        label: "Audio"
        page:
          buttons:
            applause:
              type: sound
              label: "Applause"
              path: "music/applause.mp3"
            stop_all:
              type: stop_sounds
              label: "Stop All"
```

### Common button fields

| Field           | Meaning                                                    |
|-----------------|------------------------------------------------------------|
| `type`          | Button type (see below)                                    |
| `label`         | Text drawn on the key                                      |
| `icon`          | Optional icon path (reserved; label-only for now)          |
| `color`         | Key background, e.g. `"#224422"`                           |
| `text_color`    | Label color — overrides `text_color`                       |
| `font_path`     | TTF for this key — overrides `font_path`                   |
| `font_size`     | Label size for this key — overrides `font_size`            |
| `key`           | Explicit slot 0–14 (else derived from a `button_<N>` name) |
| `label_align`   | `top`/`center`/`bottom` — overrides `label_align`          |
| `label_wrap`    | `true`/`false` — overrides `label_wrap`                    |
| `label_marquee` | `true`/`false` — overrides `label_marquee`                 |
| `pressed`       | Appearance/value overrides while the key is held (see below)|

Every appearance option has a **surface-wide default** on `control_surface` and
a **per-button override** using the same key name (a button's value wins). The
full set: `color`, `text_color`, `font_path`, `font_size`, `label_align`,
`label_wrap`, `label_marquee`, `fa_type`, `fa_weight`, `fa_size`, `fa_color`.
So you can, for example, set `color: "#222"` and `fa_color: white` once at the
top level and only override the exceptions per button.

- **Font / size / color:** `font_path`, `font_size`, `text_color` set the label
  face, size and color; `color` sets the key background.
- **Placement:** `label_align` positions the label; `label_wrap` breaks it on
  spaces to fit the 72 px key width.
- **Marquee:** when a label is still too wide to fit (wrapping off, or a single
  word/line longer than the key), it **scrolls horizontally**. Set
  `label_marquee: false` to disable and let it clip instead.

### Pressed appearance

Give a button a `pressed:` block to change how it looks (and what it says) *while
it is physically held down*. The moment the key is released the button snaps back
to its normal values. Only the fields you list change; everything else is
inherited from the button (and then the surface defaults).

```yaml
button_1:
  type: buzz
  label: "P1"
  player_id: 1
  color: "#222222"
  pressed:
    color: "#00AA00"     # green while held
    label: "IN!"         # text swaps too, if you want
    text_color: "#000000"
    fa_icon: "hand"      # any of the appearance fields below can be overridden
```

Overridable fields inside `pressed`: `label`, `icon`, `color`, `text_color`,
`font_path`, `font_size`, `label_align`, `label_wrap`, `label_marquee`, and the
Font Awesome set `fa_icon`, `fa_type`, `fa_weight`, `fa_size`, `fa_color`.
`type`, `key`, and the action fields (`player_id`, `state`, …) cannot change —
a press only affects the button's look, never what it does. Navigating to a
sub-page (or back) resets any held-down styling.

### Font Awesome icons

A button can display a Font Awesome icon instead of (or above) its label.

The Font Awesome **Pro** assets are licensed and are **not** committed to the
repo. They are fetched from Font Awesome's private npm registry into
`node_modules/` whenever you run `mise run install` (which runs `npm install`
alongside `poetry install`). This requires a Pro npm token — see
[Font Awesome setup](#font-awesome-pro-setup) below.

Point the surface at the installed assets, then set `fa_icon` on a button:

```yaml
control_surface:
  fa_path: "node_modules/@fortawesome/fontawesome-pro"   # webfonts/ + metadata/
  fa_type: pro              # default family (per-button override wins)
  fa_weight: solid          # default weight (per-button override wins)
  root:
    buttons:
      button_5:
        type: state
        state: correct
        fa_icon: "check"     # icon name from Font Awesome
        fa_color: "#00FF00"
      button_1:
        type: buzz
        player_id: 1
        fa_icon: "circle-user"
        fa_type: duotone     # pro | brands | duotone | sharp | sharp-duotone
        fa_weight: light     # solid | regular | light | thin (where applicable)
        label: "P1"          # optional: drawn small beneath the icon
```

Per-button icon fields: `fa_icon`, `fa_type`, `fa_weight`, `fa_size`, `fa_color`.
If a `label` is also set, the icon sits above it. The family/weight resolve to a
Font Awesome webfont under `<fa_path>/webfonts/` (e.g. `fa-sharp-solid-900.woff2`);
`brands` always uses its single Regular weight. If the icon name or font can't be
resolved, the key falls back to rendering the label.

> **Note:** Duotone/Sharp/Light/Thin styles require Font Awesome Pro.

#### Font Awesome Pro setup

The Pro fonts and metadata are delivered through the `@fortawesome/fontawesome-pro`
npm package rather than being checked into git (they are licensed and large).
Installation is wired into the standard install task:

1. Get a Pro npm token from your Font Awesome account
   (Account → **Package Manager Tokens**).
2. Put it in a `.env` file at the repo root (both are gitignored):

   ```
   FONTAWESOME_PACKAGE_TOKEN=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
   ```

3. Run `mise run install`. mise loads `.env`, `.npmrc` reads the token from
   `FONTAWESOME_PACKAGE_TOKEN`, and `npm install` drops the fonts into
   `node_modules/@fortawesome/fontawesome-pro/` (the `otfs/` and `metadata/`
   directories the surface reads).

Without a valid token the `npm install` step fails; the app still runs but Font
Awesome icons fall back to their text labels.

### Symbols / glyph coverage

Labels may include symbols like `▶ ◀ ✔ ✓ ●`. These render only if the chosen
font contains the glyph — otherwise the deck shows a tofu box. The default font
is picked from broad-coverage system faces (Arial Unicode / DejaVu Sans / Menlo)
that include them. If you set a custom `font_path`, make sure that font also
contains any symbols you use (plain Helvetica/Arial, for example, do not).

### Button types

| `type`           | Extra fields                         | Action |
|------------------|--------------------------------------|--------|
| `buzz`           | `player_id`                          | Buzz that player in (`BuzzerPressed`) |
| `reset_buzzer`   | —                                    | `clear` — reset to idle |
| `state`          | `state`, `duration` (timed_lockout)  | Set state machine state: `clear`, `round_start`, `game_over`, `correct`, `incorrect`, `allow_next`, `timed_lockout` |
| `countdown`      | `action`                             | `display` = live buzz-in timer readout; `pause`/`resume`/`reset`/`cancel`/`toggle` control it |
| `scene_advance`  | —                                    | Next scene |
| `scene_previous` | —                                    | Previous scene |
| `scene_goto`     | `target` (name or index)             | Jump to a scene |
| `scene_current`  | —                                    | Live current-scene readout |
| `state_display`  | —                                    | Live current-state readout |
| `lighting`       | `osc`                                | Send a DMX/lighting OSC cue |
| `sound`          | `path`                               | Play a sound effect |
| `stop_sounds`    | —                                    | Stop all effects and background audio |
| `obs_scene`      | `scene`                              | Switch OBS program scene (websocket) |
| `obs_request`    | `request_type`, `request_data`       | Any OBS-WebSocket request, e.g. `SetInputMute` |
| `config_reload`  | `config` (optional)                  | Hot-load a show config (see below) |
| `show_browser`   | —                                    | Open a live, auto-built page listing every show in `shows/` (see below) |
| `page`           | `page: { buttons: [...] }`           | Open a nested page (return button auto-added) |

`countdown cancel` stops the auto-timeout but leaves the player locked in — the
host then has unlimited time. `reset` restores the full duration.

See the bottom of `config.yaml` for a complete worked example.

### Hot-reloading a show config

A whole new `.yml` config can be loaded at runtime without restarting the
service — from a `config_reload` button or the OSC `/config/reload` command.

- **`config`** (button) / the OSC argument names the file. A bare name resolves
  under the top-level **`shows/`** folder (`trivia.yml` → `shows/trivia.yml`);
  an absolute or already-existing path is used as-is.
- **Omit it** to re-read the file that is currently loaded (picks up edits).
- On success the service resets to a **clean slate**: the state machine returns
  to the new config's `initial`, scores/counters/bans clear, no scene is
  selected, and the surface re-renders from the new root page. The new show's
  `name`/`description` are pushed to `/feedback/show/name` and
  `/feedback/show/description`.
- If the file is missing or malformed the reload is **logged and ignored** — the
  running config is left untouched.

Only *show content* reloads. Network settings — the OSC listen port, DMX target,
and OBS connection — keep their startup values; changing those still needs a
restart.

Top-level show metadata lives in the `show:` section:

```yaml
show:
  name: "Trivia Night"
  description: "The house trivia showdown"
  scenes: [...]
```

A **`show_browser`** button opens a page that is built on the fly from the
`shows/` folder: one `config_reload` button per file, labelled by the show's
`name` (falling back to the filename). If there are more shows than fit on one
page, a **Next ▶** button chains to the next; the automatic return key (key 10)
steps back. Drop a new `.yml` in `shows/` and it appears the next time the
browser is opened — no config change needed.

OSC:

| Address | Arg | Action |
|---------|-----|--------|
| `/config/reload` | show file (optional) | Hot-load a show config; omit to reload the current file |
| `/config/list` | — | Emit the `shows/` listing as feedback (see below) |
| `/config/load` | index | Load the Nth show from the listing |

Feedback:
- On reload: `/feedback/show/name`, `/feedback/show/description`.
- On `/config/list`: `/feedback/shows/count` (total), then one
  `/feedback/shows/item` per show with `[index, filename, name]`.
