<img src="https://raw.githubusercontent.com/EmirhanSyl/layer-rescue/main/src/layer_rescue/assets/icon.png" alt="" width="88" align="right">

# Layer Rescue

[![CI](https://github.com/EmirhanSyl/layer-rescue/actions/workflows/ci.yml/badge.svg)](https://github.com/EmirhanSyl/layer-rescue/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/EmirhanSyl/layer-rescue?include_prereleases)](https://github.com/EmirhanSyl/layer-rescue/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/EmirhanSyl/layer-rescue/blob/main/LICENSE)

[Türkçe](https://github.com/EmirhanSyl/layer-rescue/blob/main/README.tr.md)

A failed print doesn't always have to go in the bin. Layer Rescue lets your printer pick up a print where it stopped, even after a power cut, and it can put a broken or loose part back on the plate and print the missing part on top of it.

It runs inside Bambu Studio as a post-processing script. You slice as usual, answer a few questions in a small window, and Layer Rescue rewrites the G-code. Before anything reaches the printer, you see the result in Bambu Studio's preview.

![A broken rocket drone part repaired with Layer Rescue](https://raw.githubusercontent.com/EmirhanSyl/layer-rescue/main/images/readme/rocket.gif)

_A rocket drone body, broken on purpose, put back on the plate and reprinted with its supports. [Full test](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/04-broken-rocket-drone.md)_

<p align="center"><a href="https://www.youtube.com/watch?v=efotZIYpkzM"><img src="https://img.youtube.com/vi/efotZIYpkzM/maxresdefault.jpg" alt="Watch the Layer Rescue video on YouTube" width="640"></a></p>

<p align="center"><em>▶ Watch the full video: how it works, all three modes and every test print, in one go.</em></p>

> [!CAUTION]
> Resuming a print can drive the nozzle into the existing part. Stay at the printer during startup and be ready to stop it. See [SECURITY.md](https://github.com/EmirhanSyl/layer-rescue/blob/main/SECURITY.md).

## What it can do

- **Continue a print that stopped.** Filament ran out, the nozzle clogged, you hit stop: tell Layer Rescue the last layer that printed properly, and the job continues from the next one, right on top of the part that is still on the plate. ([Test 1](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/01-lw-pla-plane-part.md))
- **Even after a power cut.** After a restart the printer no longer knows where Z is, and homing Z would drive the part into the nozzle. Instead, you lower the nozzle onto the part by hand and Layer Rescue makes every Z move relative to that point. Z is never homed. ([Test 2](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/02-power-loss-dragon.md))
- **Put a loose or broken part back and print the rest on it.** For a part that came off the plate, broke later or needs an addition. The printer prints a low wall shaped from the part's own outline, pauses so you can put the part in, then prints the missing top onto it. ([Test 3](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/03-detached-benchy.md), [Test 4](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/04-broken-rocket-drone.md))
- **Rebuild the supports the new part needs.** If the missing top was printed on supports, Layer Rescue prints them again from the bed, even inside a hollow part, and leaves out everything that would get in the part's way. ([Test 4](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/04-broken-rocket-drone.md))
- **Save what's left of a full plate.** If a few parts on a crowded plate came loose, delete them in Bambu Studio and finish the rest. ([Test 5](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/05-multi-object-spiders.md))
- **No G-code editing by hand.** Bambu Studio keeps its filament mapping and `.gcode.3mf` data, and the preview shows exactly what will be printed.
- **Careful by default.** It never homes Z or levels the bed over a part, checks its own output before saving it, refuses files it can't handle safely instead of guessing, and keeps a backup of the original G-code. The window asks you to confirm what it can't see for itself.
- **English and Turkish**, switchable in the window at any time.

## Real-world tests

I tested every feature on my own P1S with real prints and wrote down each one step by step, with videos, settings and what I learned. All five worked; two of them taught me something worth knowing before you try it yourself.

<p align="center"><img src="https://raw.githubusercontent.com/EmirhanSyl/layer-rescue/main/images/readme/tested-parts.jpg" alt="The five rescued test prints: rocket drone body, Benchy, spiders, dragon and plane nose cover" width="720"></p>

<p align="center"><em>All five rescued prints. From left: the rocket drone body, the Benchy, the three spiders, the dragon and the plane's nose cover.</em></p>

| Test                                                       | Situation                       | What it shows                                                                    |
| ---------------------------------------------------------- | ------------------------------- | -------------------------------------------------------------------------------- |
| [1. LW-PLA plane part](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/01-lw-pla-plane-part.md) | filament jam, printer stayed on | the basic resume                                                                 |
| [2. Dragon](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/02-power-loss-dragon.md)            | power cut                       | resuming after a restart, and what happens when you pick the wrong layer         |
| [3. Benchy](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/03-detached-benchy.md)              | print came off the plate        | insert mode, and why parts that get wider towards the top need a bit of hot glue |
| [4. Rocket drone](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/04-broken-rocket-drone.md)    | finished part broke             | insert mode with supports rebuilt from the bed inside a hollow part              |
| [5. Spiders](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/05-multi-object-spiders.md)        | 2 of 5 parts came off           | finishing only the parts that are left, with a seam you can't see                |

## Tested on

- Bambu Lab P1S, single filament
- Windows and macOS (Linux from source)
- Bambu Studio G-code, by-layer printing, relative extrusion
- The part is still firmly attached to the same plate (resume mode), or it came off / is finished and fits back into a wall printed around it (insert mode, beta)

Supported printer families: the Bambu Lab P1/X1 series (P1S tested; P1P, X1, X1C and X1E use the same moves) and, experimentally, the H2 series (H2D, H2S, H2C: purge, wipe and hotend selection follow the stock H2 G-code but have not been run on a printer yet, and only the printer-stayed-on mode is available). Other printers, including the A1 and A1 mini, are refused because their stations are elsewhere.

Not tested yet: other printer models and AMS/multi-filament jobs. When a job falls outside what's been tested, Layer Rescue tells you why and asks you to accept the risks before it continues (CLI: `--allow-untested`). With several filaments it loads the filament that was active at the layer you continue from. If you try one of these, please [share your results](#share-your-results).

By-object printing and spiral vase don't fit the way Layer Rescue works yet, so those jobs are still turned down.

## Install

Downloads are on the [Releases](https://github.com/EmirhanSyl/layer-rescue/releases) page.

**Windows:** run `LayerRescue-Setup-<version>-win-x64.exe`. The last page of the installer shows the command to paste into Bambu Studio.

**macOS (Apple Silicon):** unzip `LayerRescue-<version>-macos-arm64.zip` and move `LayerRescue.app` to Applications. The app is not signed with an Apple Developer ID yet, so macOS blocks it the first time:

1. Double-click `LayerRescue.app`. macOS says it cannot be opened; click **Done**.
2. Open **System Settings → Privacy & Security**, scroll down and click **Open Anyway** next to Layer Rescue.
3. The app opens and shows the command to paste into Bambu Studio.

Do this once before using it from Bambu Studio, otherwise Studio cannot start it. Alternatively run `xattr -dr com.apple.quarantine /Applications/LayerRescue.app`.

**Intel Macs, Linux and everything else:** install the [PyPI package](https://pypi.org/project/layer-rescue/) with Python 3.10+ (the window needs Tkinter; with Homebrew Python also run `brew install python-tk`):

```bash
pipx install layer-rescue
```

## Set up Bambu Studio

1. Switch Bambu Studio to Advanced mode.
2. In the process settings, open **Others** and find **Post-processing Scripts**.
3. Enter the full path to Layer Rescue, in quotes:

   | Install           | Command                                                                           |
   | ----------------- | --------------------------------------------------------------------------------- |
   | Windows installer | `"C:\Users\<you>\AppData\Local\Programs\LayerRescue\LayerRescue.exe"`             |
   | macOS app         | `"/Applications/LayerRescue.app/Contents/MacOS/LayerRescue"`                      |
   | pipx              | the output of `which layer-rescue`, e.g. `"/Users/<you>/.local/bin/layer-rescue"` |

   Opening the app directly (without Bambu Studio) shows the exact command for your install.

Studio may show a warning because post-processing scripts are executables. Only approve tools you installed from a source you trust.

Tip: save the process preset with the script in it, so it's there the next time something goes wrong.

## The window

After slicing, Layer Rescue opens a small window. At the top it shows the file it got (printer, filament, layer count), and below that there's a tab for each situation:

- **Part is still on the plate**: resume an interrupted print (below).
- **Part came off / print on a finished part**: insert mode (further below).

<p align="center"><img src="https://raw.githubusercontent.com/EmirhanSyl/layer-rescue/main/images/readme/ui-resume.png" alt="The Layer Rescue window on the resume tab" width="400"></p>

Each tab is a short list of numbered steps. On the resume tab you enter where the print stopped, say whether the printer was turned off, and confirm a few things Layer Rescue can't see for itself under **Safety checks**. **Create G-code** stays disabled until everything required is filled in, and the line at the bottom left says what is still missing. **Leave G-code unchanged** closes the window without touching the file; use it for normal prints.

If the job is for a printer or filament setup that hasn't been tested yet, an extra **Untested setup** box appears above the tabs. It explains why and asks you to accept the risks before you can continue.

**Language:** use the **English / Türkçe** buttons at the top right. The change applies immediately and is remembered for next time. On first start the language follows your system language. (Command-line output stays in English.)

## Resume a print

![Resuming a plane part after a filament jam](https://raw.githubusercontent.com/EmirhanSyl/layer-rescue/main/images/readme/plane.gif)

1. Find the last layer that actually got filament (see [Picking the layer](#picking-the-layer) below).
2. Slice the original project again, without changing anything. The Layer Rescue window opens on **Part is still on the plate**.
3. **Step 1 – Where did the print stop?** Enter the last good layer. The window shows the layer and Z height that printing restarts at.
4. **Step 2 – Was the printer turned off or restarted?**
   - **No, it stayed on the whole time** (`retained`): the printer kept its Z position. Nothing else to do.
   - **Yes, it was turned off or restarted** (`manual`): after a power cycle Z is not homed. Heat the bed back up, clean the nozzle, move it over a flat printed area of the last good layer and lower it until it just touches the surface. If the printer offers to home Z, don't accept. Do not move the part or the plate. ([Test 2](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/02-power-loss-dragon.md) shows this step by step.)
5. **Step 3 – Safety checks.** Layer Rescue cannot see the printer, so you confirm what it has to assume. Tick each box only if it is true:
   - the part is still firmly stuck to the same plate and the plate was not moved;
   - with _No, it stayed on_: the printer never lost power and the Z axis was not moved;
   - with _Yes, it was restarted_: you will lower the clean nozzle onto the last good layer before starting the job.

   Only the check for the selected answer in step 2 is shown.

6. **Options** can usually stay as they are: nozzle and bed temperature (blank = taken from the file) and homing X/Y before continuing (always on after a restart; Z is never homed).
7. Click **Create G-code**, check the preview in Bambu Studio and send the job.

### Picking the layer

This is the one decision Layer Rescue can't make for you, and it matters more than anything else. When a print fails, the last few layers are often thin or missing even though the printer counts them as done, so go by the part, not by the counter. If filament ran out at layer 462 but the printer kept going until 490, enter 461. A recording or timelapse helps a lot.

Being off by only 2–3 layers already shows:

- **Printer stayed on:** too high leaves a gap, so the seam is weak and very visible; too low drives the nozzle into the part and can knock it off the plate. ([Test 1](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/01-lw-pla-plane-part.md))
- **After a restart:** Z comes from where you put the nozzle, so nothing crashes, but the wrong layers get printed there. Too low prints a few layers twice, too high skips them, and the details stop lining up at the seam. ([Test 2](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/02-power-loss-dragon.md) is exactly this mistake.)

If you can choose when to stop the print, stop it right after a layer has finished. In [Test 5](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/05-multi-object-spiders.md) that gave a seam you can't see at all.

### Several objects on the plate

If some parts on a crowded plate came loose, take them off, delete them in Bambu Studio and slice again. Layer Rescue continues everything that is in the G-code, so anything you leave in the project gets printed, in the air if it's no longer on the plate. Don't move, rotate or **Arrange** the remaining parts; they have to stay exactly where they were printed. ([Test 5](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/05-multi-object-spiders.md))

## Seat a loose part and print on top (insert mode, beta)

![Reseating a Benchy that came off the plate](https://raw.githubusercontent.com/EmirhanSyl/layer-rescue/main/images/readme/benchy.gif)

For a part that came off the plate halfway, a finished part that broke, or a finished part that gets an addition. You slice the complete model (the old part plus what goes on top, one object). Layer Rescue replaces the layers below the part's top with a holding wall that follows the part's outline, pauses, and prints the rest on top of the part you put into the wall.

1. Prepare the part: remove brim and strings. A broken part must be cut or sanded flat first. Measure its height with calipers.
2. Slice the complete model. In the Layer Rescue window open **Part came off / print on a finished part**.
3. Enter the **part height** (or the last layer the part contains) and optionally the **wall height** (blank = recommended: half the part, 3–15 mm, always at least 1 mm below the top). Press **Preview** to see the wall from above and, under **Result**, where printing continues and any warnings.
4. Tick the **Safety check** (you will stay at the printer, seat the part when it pauses and watch the first layers), click **Create G-code** and send the job. The printer levels the empty bed, prints the wall, lifts to 15 mm above the part height, parks at the back and pauses (`M400 U1`).
5. Without removing or shifting the plate, press the part into the wall the same way round as in Bambu Studio (front of the model to the front of the plate), then press **Resume**.
6. The printer reheats, purges, travels above the part and prints the rest. The first 2 layers on the part are 10 °C hotter, half speed and without part cooling for adhesion.

<p align="center"><img src="https://raw.githubusercontent.com/EmirhanSyl/layer-rescue/main/images/readme/ui-insert.png" alt="The insert tab after pressing Preview" width="400"></p>

After **Preview**, the right side shows the plate from above: the part (beige), the bottom and the rim of the wall (grey and red), the first layer that will be printed on the part (blue) and the supports that will be reprinted (green). **Result** on the left says which layers become the wall, where printing continues after the pause and how thick the first layer on the part will be, followed by any warnings. The advanced settings open under the preview.

How the wall is made: the part's own outline is read from the sliced layers below the wall height. The opening at every height lets all sections below it pass (the part is lowered from above), with 0.25 mm clearance, a 4-line wall, a 5 mm brim and a small lead-in chamfer at the rim. All of these can be changed after ticking **Show advanced settings** (next to the preview).

**Supports.** If the model has supports that reach above the part height (for example tree supports inside a hollow part, or next to it), their lower part is printed again before the pause, wherever the part will not hit them when it is lowered in. Remove the old supports from the part before seating it. Supports that only held the part's own overhangs are left out. Turn this off with **Reprint the supports below the part height** in the advanced settings (CLI `--no-reprint-supports`). [Test 4](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/04-broken-rocket-drone.md) shows this on a hollow rocket body.

**Getting a good fit:**

- If the part sits loose in the wall, lower the clearance. On a round part, the default 0.25 mm was clearly too loose and 0.12 mm gave a much tighter fit.
- **Parts that widen upwards** (like a boat hull) touch the wall only on sloped surfaces, so the nozzle can drag them up and out. Fix such a part with a few dots of hot glue over the seam, squeezed onto the wall rather than the part: it comes off the part cleanly afterwards. ([Test 3](https://github.com/EmirhanSyl/layer-rescue/blob/main/docs/tests/03-detached-benchy.md))
- Seat the part level all around. Even 0.2 mm higher on one side shows up as layer lines on the other.

Limits: one object on the plate, no prime tower, part at least 3 mm tall and 5 mm wide. The Z of everything printed on top is shifted by the difference between the measured height and the nearest model layer, so the first layer sits on the real part. If the top surface is a cut (infill exposed), add a height range modifier in Bambu Studio from the part height to about 0.6 mm above it with 100 % sparse infill density, so the first layers are solid.

## What the generated job does

It keeps the original header and settings, drops the start sequence and the finished layers, restores temperatures, fans and motion limits, lifts the nozzle, homes X/Y only (`G28 X`), purges at the rear chute, moves above the first point of the layer, lowers onto it and continues with the original G-code to the end.

It never homes Z and never runs bed leveling. In manual mode every Z move is relative to the position you aligned, so the job does not depend on the Z the printer thinks it is at after a restart.

The file is rewritten in place and a `.layer-rescue.bak` copy of the original is kept next to it.

## Limitations and what's next

Layer Rescue saves prints, but it can't make the repair invisible or do everything yet. Here's what to expect:

- **The seam usually shows.** In most tests there was a visible layer line where the print restarted, even with the exact right layer. With the right layer, the seams I've handled didn't tear, crack or crush, but I haven't done proper strength tests yet, and the result depends on the model and the filament. For functional parts, a few drops of superglue on the seam don't hurt.
- **You pick the layer, and mistakes show.** There's no automatic detection of where the print really stopped. See [Picking the layer](#picking-the-layer).
- **After a restart, the result depends on your hands.** The nozzle is placed on the part by eye.
- **Insert mode is still beta.** How well a part fits the wall depends a lot on its shape: some drop in and sit snugly, some can shift, some need glue, and some may not fit at all. Round parts can't be oriented by the wall, so you have to seat them facing the right way. It handles one object on the plate and no prime tower.
- **Tested on one printer so far.** Everything above was tested on a Bambu Lab P1S with a single filament. You can try other printers and multi-filament jobs by accepting the risks in the window, but watch the start closely: the P1/X1 moves were made on a P1S, and the H2 sequence has only been checked against sliced files.

### Roadmap

**Short term: make what's there reliable**

- Fixed test files from the real prints, so a new feature can't quietly break an old case.
- A "copy report" button that puts the version, printer, settings and warnings into one text for bug reports.
- Help with finding the last good layer, for example turning a caliper height into a layer number.
- Dropping failed objects from a crowded plate without re-slicing.
- A short guide in the window that asks what happened and picks the right mode.
- Reports from people testing on other printers (X1C, A1, H2D and more), plus an FAQ.

**Mid term: insert mode for more shapes**

- Parts that widen towards the top, and other shapes that don't sit well in the wall today.
- Clearance presets based on the part's shape.
- Taking insert mode out of beta once it works on a wider range of parts.
- Research: setting Z after a power loss automatically, by touching the nozzle to the part or by using the camera or other printer data instead of doing it by eye. Idea from [u/robiebab](https://www.reddit.com/r/BambuLab/comments/1wvchb4/comment/pdcqgs8/).

**Long term: supports that don't start from the bed**

- Research: holding up a tall overhang without printing the whole support underneath. A few small ledges on the model carry a metal bar or another rigid part placed mid-print, and the overhang is printed on top of it. Idea from [u/Thing1_Tokyo](https://www.reddit.com/r/3Dprinting/comments/1wvcdxq/comment/pdayrw4/).
- OrcaSlicer support and other printer families.

Got an idea or a use case that doesn't fit here? [Open an issue](https://github.com/EmirhanSyl/layer-rescue/issues/new/choose).

## Share your results

Layer Rescue gets better with every real print it sees. If something didn't work, or the result looked odd, please [open an issue](https://github.com/EmirhanSyl/layer-rescue/issues/new/choose) with the G-code, your printer and firmware version, the settings you used and a few photos. And if it saved a print for you, especially on a printer or with a filament I haven't tried, I'd love to hear about that too: successful prints on new setups are exactly what's needed before they can be enabled.

## Command line

```bash
layer-rescue --analyze print.gcode
layer-rescue --last-layer 461 --z-mode retained print.gcode
layer-rescue --last-layer 461 --z-mode manual --confirm-manual-z-aligned print.gcode
```

Insert mode:

```bash
layer-rescue --part-height 23.4 --wall-height 10 --confirm-attended print.gcode
layer-rescue --part-layer 117 --confirm-attended --preview-svg wall.svg print.gcode
```

Insert options: `--clearance`, `--wall-lines`, `--brim`, `--no-chamfer`, `--z-fine`, `--standby-temp`, `--adhesion-layers`, `--no-reprint-supports`.

`--allow-untested` accepts the risks of an untested printer or multi-filament job. `--nozzle-temp` and `--bed-temp` override the detected temperatures. Run `layer-rescue --help` for all options.

## Credits

The idea of resuming a print from a chosen layer comes from CNC Kitchen's [guide to resuming a failed 3D print](https://www.cnckitchen.com/blog/guide-resuming-a-failed-3d-print). When I started this project, I mostly wanted to automate the manual steps from that guide for Bambu Studio, so thanks to CNC Kitchen for explaining it so clearly. Everything else (insert mode with its holding wall, support reprinting, the safety checks and output validation) was designed from scratch for Layer Rescue.

Thanks also to the designers of the models I used in the tests:

- Plane part: [Talon 1400](https://flightory.com/product/talon-1400/) by Flightory
- Dragon: [Mystic Dragon](https://makerworld.com/tr/models/3015782-mystic-dragon-breathtaking-dragon-figure#profileId-3435682) by DElex3D on MakerWorld
- Boat: the classic [3DBenchy](https://www.3dbenchy.com/)
- Rocket drone: [Sub-250g SpeedDrone](https://makerworld.com/tr/models/2637662-sub-250g-speeddrone-320km-h-fast#profileId-2913683) by luisengineering on MakerWorld
- Spiders: [The World's Smallest Spider](https://makerworld.com/tr/models/2864339-the-world-s-smallest-spider-nozzle-0-4#profileId-3196930) by formastampa on MakerWorld

The roadmap also has ideas from the community: thanks to [u/robiebab](https://www.reddit.com/r/BambuLab/comments/1wvchb4/comment/pdcqgs8/) for automatic Z after a power loss, and to [u/Thing1_Tokyo](https://www.reddit.com/r/3Dprinting/comments/1wvcdxq/comment/pdayrw4/) for placed-object supports.

## Contributing

Bug reports with the printer model, firmware version and G-code are the most useful contribution. See [CONTRIBUTING.md](https://github.com/EmirhanSyl/layer-rescue/blob/main/CONTRIBUTING.md).

## License

[MIT](https://github.com/EmirhanSyl/layer-rescue/blob/main/LICENSE). Not affiliated with or endorsed by Bambu Lab.
