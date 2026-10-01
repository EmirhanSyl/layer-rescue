# Test 2: Dragon after a power cut

[Türkçe](02-power-loss-dragon.tr.md)

**Mode:** resume (part still on the plate), printer restarted · **Printer:** Bambu Lab P1S · **Result:** worked, with a lesson about picking the layer

![Test overview](../../images/DragonTest/Dragon.gif)

## What happened

This test covers the case people fear most: the power goes off in the middle of a print. I simulated it by switching the printer off at the power switch while it was printing an 80 mm dragon with tree supports. When it comes back on, the printer has no idea where Z is anymore, so Layer Rescue can't rely on the printer's own Z coordinate the way it did in the [plane test](01-lw-pla-plane-part.md). Instead, I place the nozzle on the part by hand and the job continues from there.

|                      |                                                                      |
| -------------------- | -------------------------------------------------------------------- |
| Model                | dragon, 80 mm tall, lots of thin details, tree supports (400 layers) |
| Filament             | SUNLU Silk PLA+                                                      |
| Process              | 0.20 mm Standard                                                     |
| Plate                | textured PEI                                                         |
| Nozzle               | 0.4 mm                                                               |
| Last good layer      | entered 265, the real one was 268 (see [the result](#6-the-result)) |
| Layer Rescue version | 0.2.2                                                                |

## Step by step

### 1. The first part prints, then the power goes off

![Printing the base](../../images/DragonTest/base_print.mp4)

The print ran normally up to around two thirds of the height. Then I turned the printer off at the switch on the back and waited a bit before turning it back on.

![Power cycle](../../images/DragonTest/power_cycle.mp4)

From this point on, don't touch the part or the plate. The part has to stay exactly where it was printed.

### 2. Heat the bed back up

![Heating the bed](../../images/DragonTest/heat_bed.mp4)

After the restart, nothing is heated. On the printer's screen I set the bed back to its printing temperature (55 °C), so the part keeps sticking to the plate and stays the same size it was printed at. I also set the nozzle to 140 °C, but there's no special reason for that and it isn't required.

### 3. Bring the nozzle down onto the part by hand

![Adjusting Z manually](../../images/DragonTest/adjust_z.mp4)

This is the most important step of this test. On the printer's screen, open the axis controls and move Z until the clean nozzle **just touches** the top of the last good layer.

> **Never accept homing.** When you try to move Z after a restart, the printer warns _"Axis z has not been homed! Press OK to home."_ Don't press OK. Homing Z on the P1S uses the bed itself to find zero, and with the part still on the plate it would drive the part straight into the nozzle. Back out of the message and move Z by hand.

Move in small steps near the end. The nozzle should sit on a flat area of the last layer, not on a support or an edge, and should only just touch it without pressing into it.

I judged it by eye: I lowered Z in small steps and stopped as soon as the nozzle visibly touched the top surface.

Once the nozzle is in place, don't move Z again. From here on, Layer Rescue makes every Z move relative to this position.

### 4. Slice and choose the options in Layer Rescue

![Layer Rescue options](../../images/DragonTest/layerrescue_options_dragon.mp4)

I sliced the same project again (the post-processing script was already set up, see step 2 of the [plane test](01-lw-pla-plane-part.md)). In the Layer Rescue window:

- **Last layer that printed correctly:** 265. As it turned out later, this was wrong, more on that in the result.
- **Z mode:** _printer was restarted (manual Z reference)_ (in 0.3: "Yes, it was turned off or restarted").
- **Re-home X/Y:** on and locked, because X and Y also have to be homed after a restart. Z is never homed.
- **Confirmations:** I will align the clean nozzle to the last good layer before starting (already done in step 3), and the part is still firmly attached to the plate.

The file shows `Layers: 1–396 / 400`. That's normal when the supports use their own layer height: Bambu counts those extra support layers in the total, and Layer Rescue handles it.

> **In 0.3** the restarted mode only shows the checks that apply to it, and the window shows which layer and Z it will restart from as you type.

### 5. Check the preview and send

![Slice results](../../images/DragonTest/slice_results.mp4)

In the preview, only the part above layer 265 is left: the rest of the body, the wings and the head. Nothing starts from the bed.

![Printing the rest](../../images/DragonTest/printing_rest_dragon.mp4)

After sending, the printer heats up, lifts the nozzle 2 mm from where I left it, homes only X and Y, purges, comes back above the part and continues from layer 266. Because the nozzle was placed on the part by hand, I watched the first layers closely.

### 6. The result

![Final result](../../images/DragonTest/final_result_dragon.mp4)

The dragon finished with its wings and head, but around the seam on the head and the wings there were more marks and gaps than I expected. One wing broke off at the seam and I had to glue it back.

When I went through the recordings afterwards, I found the reason: the last layer that had really printed was **268**, not 265. I had restarted the print 3 layers too low.

Here the restarted mode actually saved the print. In this mode Z doesn't come from the layer number but from where I put the nozzle by hand. Layer Rescue took the surface I touched (the real top of layer 268) as the top of layer 265, so the nozzle didn't crash into the part or break the supports; it simply carried on from there. But it printed layers 266–268 a second time, on top of the real 268. The whole upper half sits about 0.6 mm higher than it should, and where the model changes quickly from layer to layer (the thin wing structure, the head), the new layers don't line up with the old ones. That's where the gaps and the weak seam come from.

So the program did exactly what it was told, and everything after the seam printed correctly, which is why I count this test as a success. The weak seam is down to the layer I entered, not the algorithm.

Apart from that, the usual applies: there's always a visible layer line where a print restarts, even with the exact right layer. I haven't done proper strength tests yet, but when the layer is right the seam doesn't tear, crack or crush when I handle the part. How strong it ends up still depends on the shape of the model and the filament.

## Takeaways

- After a power cut, the result depends on you placing the nozzle on the part. Take your time with it: everything above is printed relative to that point.
- Never let the printer home Z while the part is on the plate.
- Heat the bed back up before anything else, so the part doesn't come loose while you work on it.
- Check the last good layer carefully before you enter it; if you have a recording or a timelapse, use it. Being off by only 2–3 layers already shows, but in restarted mode it shows differently from the [plane test](01-lw-pla-plane-part.md), because Z comes from your nozzle, not from the layer number:
  - **Too low** (this test): the layers between the number you entered and the real top are printed twice. Nothing crashes, but the upper half ends up higher than it should and details stop lining up at the seam, so it's visibly worse and weaker.
  - **Too high**: those layers are skipped. The nozzle still starts right on the part, but the shape jumps, so you get a step at the seam and a weaker join.
- The nozzle position from step 3 is the other half of it. If it's too high, the first new layer barely touches the part and the seam is weak; if it's pressed into the part, the nozzle can scrape it or knock it off the plate.
