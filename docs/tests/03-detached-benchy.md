# Test 3: Benchy that came off the plate

[Türkçe](03-detached-benchy.tr.md)

**Mode:** insert (beta) · **Printer:** Bambu Lab P1S · **Result:** worked, with hot glue and a small tilt

![Test overview](../../images/BenchyTest/Benchy.gif)

## What happened

This Benchy failed halfway because of a filament problem and came off the plate. When a part is no longer on the plate, normal resuming is out: there's nothing left for the printer to continue on. This is what insert mode is for. The printer prints a low wall that follows the outline of the part, pauses so you can put the part into it, then prints the rest on top.

It's also a good stress test, because the Benchy is a tricky shape for this: its hull is oval at the front and gets wider towards the top.

|                      |                 |
| -------------------- | --------------- |
| Model                | 3DBenchy        |
| Filament             | SUNLU Silk PLA+ |
| Part height          | 21 mm           |
| Wall height          | 10 mm           |
| Clearance            | 0.13 mm         |
| Layer Rescue version | 0.2.2           |

## Step by step

### 1. Clean up and sand the part

![Cleaning and sanding](../../images/BenchyTest/cleaning_sanding.mp4)

The top of the failed part was covered in loose strings ("spaghetti"). I pulled those off, then sanded the top flat with sandpaper until I was down to a clean, solid layer. I also cleaned the bottom so the part sits flat.

The flat top matters: the first new layer is printed straight onto it, so any bumps or loose bits end up in the seam.

After sanding, I measured the height of the part with calipers. That measured height is what goes into Layer Rescue, not the layer the print failed at.

### 2. Slice the complete model and set up insert mode

I sliced the complete Benchy (the whole model, not just the missing top). In the Layer Rescue window I opened the insert tab (in 0.3: **Part came off / print on a finished part**), entered the measured part height, checked the wall in **Preview**, ticked the safety check and created the G-code.

### 3. The printer prints the holding wall

![Printing the support wall](../../images/BenchyTest/printing_wall.mp4)

The printer starts on an empty plate and prints only the wall: a low ring shaped like the bottom of the Benchy with a small gap around it. Then it lifts, parks at the back and pauses.

### 4. Seat the part (and glue it)

![Seating the part](../../images/BenchyTest/seating_part.mp4)

Without taking the plate off or moving it, I put the Benchy into the wall facing the same way as in Bambu Studio.

Here the Benchy's shape got in the way. The front of the hull is oval and slopes outwards, so the part only touches the wall on sloped surfaces. It sits in the right place, but nothing really holds it down, and a small push can lift it out. That's expected for parts that get wider towards the top: a wall around the bottom can stop them sliding sideways, but not lifting up.

#### First try: without glue

![Failed attempt without glue](../../images/BenchyTest/failed_benchy.mp4)

Before using glue, I tried it the normal way: I put the part into the wall and pressed Resume. As soon as the nozzle started printing on top, it dragged the part along and lifted it out of the wall. I put it back a couple of times, and each time it happened again. With only sloped surfaces touching the wall, there was simply nothing holding the hull down.

#### Second try: with glue

So I fixed the part with hot glue at 4 points along the seam between the wall rim and the hull.

> **Put the glue on the wall, not on the part.** The glue comes off the part cleanly afterwards, but leaves traces on whatever it was squeezed onto. The wall gets thrown away anyway, so let it take the mess.

While gluing, I accidentally pushed the right side of the part up by about 0.2 mm, so it ended up slightly tilted. More on that in the result.

Then I pressed **Resume** on the printer.

### 5. The printer prints the rest on top

![Printing the rest](../../images/BenchyTest/printing_rest_benchy.mp4)

The printer heats up again, purges, moves above the part and prints the cabin and the rest of the boat on top of the seated hull. The first layers on the part are printed a bit hotter, slower and without part cooling, so they stick to the old part better.

### 6. The result

![Final result](../../images/BenchyTest/final_result_benchy.mp4)

Getting the Benchy out was easier than I expected, even with 4 dots of glue: one light touch with a utility knife and the part came off the wall, with no glue left on it.

The new top is firmly attached. Because of the 0.2 mm tilt from gluing, the left side has clearly visible layer lines at the seam, but that's only cosmetic: it didn't cause any gaps or weak spots, and the part holds together well.

A visible layer line at the seam is normal anyway, even when everything lines up perfectly. I haven't done proper strength tests yet, but when the height is right the seam doesn't tear, crack or crush when I handle the part. How strong it ends up still depends on the shape of the model and the filament.

## Takeaways

- Insert mode is still in beta, and how well a part fits into the wall depends a lot on its shape. Some parts drop in and sit snugly, some can shift like this one, and some may not fit at all. Improving this is one of the main things I want to work on in the next versions.
- Parts that get wider towards the top (like the Benchy's hull) can't be held down by the wall. Fix them with a few dots of hot glue on the wall side of the seam.
- If the part sits loose in the wall, print the wall with a smaller clearance (**Gap between part and wall** under the advanced settings, CLI `--clearance`). On a round part in an earlier test, the default 0.25 mm was clearly too loose, while 0.12 mm gave a much tighter and better fit.
- Seat the part carefully and check that it sits level all around before pressing Resume. Even 0.2 mm on one side shows up as layer lines there.
- The measured part height plays the same role as the layer number in the other tests, and being off by just 2–3 layers (0.4–0.6 mm at 0.2 mm layers) already shows:
  - **Too high:** the first new layers are printed above the part and barely touch it. The seam gets very noticeable and is much more likely to break.
  - **Too low:** the nozzle presses into the part and can push it out of the wall.
