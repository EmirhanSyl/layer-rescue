"""Window texts in English and Turkish, switchable at runtime.

The core modules (G-code parsing, resume, insert) raise and warn in English, which keeps the CLI
output and bug reports stable. The window translates those messages with ``MESSAGE_PATTERNS``;
a message without a pattern is shown in English.
"""

from __future__ import annotations

import json
import locale
import os
import re
import sys
from pathlib import Path
from typing import Callable

LANGUAGES = {"en": "English", "tr": "Türkçe"}
DEFAULT_LANGUAGE = "en"

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # Window and header
        "app.title": "Layer Rescue",
        "header.version": "version {version}",
        "header.language": "Language:",
        "file.frame": "Sliced file",
        "file.name": "File",
        "file.printer": "Printer",
        "file.filament": "Filament",
        "file.layers": "Layers",
        "file.layers_value": "{first}–{last} (of {total})",
        "choose_mode": "What happened to the print? Choose the matching tab:",
        "tab.resume": "Part is still on the plate",
        "tab.insert": "Part came off / print on a finished part",
        "untested.frame": "Untested setup",
        "untested.intro": (
            "Layer Rescue hasn't been tested with this kind of job yet. It may work, but the moves it adds "
            "(parking, purging, homing) were made for a single-filament P1S."
        ),
        "untested.check": (
            "I understand the risks and want to try it anyway. I'll stay at the printer and stop it if anything "
            "looks wrong."
        ),
        "status.untested": "Accept the risks of the untested setup (top of the window) to continue.",
        # Bottom buttons
        "button.leave": "Leave G-code unchanged",
        "button.create": "Create G-code",
        "status.ready": "Ready. Check the preview in Bambu Studio after creating the G-code.",
        "status.resume_layer": "Enter the last good layer (step 1).",
        "status.resume_checks": "Tick the safety checks (step 3) to continue.",
        "status.insert_height": "Enter the part height (step 1).",
        "status.insert_check": "Tick the safety check to continue.",
        # Resume tab
        "resume.intro": (
            "The print stopped (filament ran out, clog, power cut…) but the part is still stuck to the plate. "
            "The new G-code continues printing on top of it from the next layer."
        ),
        "resume.step1": "1. Where did the print stop?",
        "resume.last_layer": "Last layer that printed correctly:",
        "resume.last_layer_hint": (
            "The last layer that really got filament. If the filament ran out at layer 462 but the printer "
            "kept going until 490, enter 461."
        ),
        "resume.next_layer": "Printing restarts at layer {layer} of {total} (Z = {z:g} mm).",
        "resume.layer_range": "Enter a whole number between {first} and {last}.",
        "resume.step2": "2. Was the printer turned off or restarted?",
        "resume.mode_retained": "No, it stayed on the whole time (Z position is kept)",
        "resume.mode_manual": "Yes, it was turned off or restarted (Z position is lost)",
        "resume.help_retained": (
            "The job uses the Z position the printer still knows. Choose this only if the printer stayed "
            "powered on and nobody moved the Z axis. The job never homes Z or levels the bed."
        ),
        "resume.help_manual": (
            "Before sending: clean the nozzle, move it over a flat area of the last good layer and lower it "
            "until it just touches the surface. Every Z move in the job is relative to that position, so it "
            "does not matter what Z the printer thinks it is at. The job lifts 2 mm and homes X/Y only; it "
            "never homes Z or levels the bed."
        ),
        "resume.step3": "3. Safety checks",
        "resume.checks_intro": (
            "Layer Rescue cannot see your printer. Tick each box only if it is true; the G-code is created "
            "only when all of them are ticked."
        ),
        "resume.check_attached": "The part is still firmly stuck to the same plate, and the plate was not moved.",
        "resume.check_retained": "The printer never lost power and the Z axis was not moved.",
        "resume.check_manual": (
            "Before starting the job I will lower the clean nozzle until it just touches the last good layer."
        ),
        "resume.options": "Options (usually leave as they are)",
        "resume.nozzle": "Nozzle temperature (°C):",
        "resume.bed": "Bed temperature (°C):",
        "resume.temp_hint": "blank = from the file",
        "resume.home": "Home X and Y before continuing (G28 X, never Z)",
        "resume.home_forced": "Home X and Y before continuing (G28 X, never Z) — required after a restart",
        # Resume errors and result
        "resume.err_layer": "Step 1: enter the last good layer as a whole number.",
        "resume.err_attached": "Safety check: confirm that the part is still firmly attached to the plate.",
        "resume.err_retained": "Safety check: confirm that the printer never lost power or its Z position.",
        "resume.err_manual": "Safety check: confirm that you will align the nozzle to the last good layer.",
        "resume.err_temperature": "{field}: enter a whole number in °C, or leave it blank.",
        "resume.done_title": "Recovery G-code created",
        "resume.done": (
            "Recovery G-code created.\n\n"
            "Starts at layer {layer}/{total}\n"
            "Z: {z:g} mm\n"
            "Z mode: {mode}\n"
            "Nozzle: {nozzle}°C\n"
            "Bed: {bed}°C\n\n"
            "Inspect Bambu Studio Preview before sending."
        ),
        "resume.done_retained": "printer stayed on (Z kept)",
        "resume.done_manual": "restarted, nozzle touching the Z = {z:g} mm surface",
        "resume.done_manual_reminder": (
            "\n\nBefore sending: align the clean nozzle so it just touches the top of the last good layer. "
            "Do not start unless this is exact."
        ),
        # Insert tab
        "insert.intro": (
            "For a part that came off the plate, broke (cut the break flat first) or is finished and gets an "
            "addition. Slice the complete model. The printer prints a wall that holds the part, pauses so you "
            "can put the part into it, then prints the rest on top."
        ),
        "insert.step1": "1. Part and wall",
        "insert.part_height": "Part height (mm, measured):",
        "insert.part_layer": "or the part's last layer:",
        "insert.wall_height": "Wall height (mm):",
        "insert.wall_hint": "blank = recommended",
        "insert.preview": "Preview",
        "insert.show_advanced": "Show advanced settings",
        "insert.advanced": "Advanced settings",
        "insert.clearance": "Gap between part and wall (mm)",
        "insert.lines": "Wall thickness (lines)",
        "insert.brim": "Brim (mm)",
        "insert.fine": "Z fine adjust (mm, − = more squish)",
        "insert.standby": "Nozzle while paused (°C, 0 = keep hot)",
        "insert.adhesion": "Adhesion layers (hotter, slower, no fan)",
        "insert.chamfer": "Lead-in chamfer at the wall rim",
        "insert.supports": "Reprint the supports below the part height (before the pause)",
        "insert.step2": "2. Result",
        "insert.info_start": "Enter the part height and press Preview.",
        "insert.info": (
            "Wall: layers 1–{wall_last}, up to {wall_top:g} mm (recommended {recommended:g} mm).\n"
            "Pause, then print from layer {resume}/{total}. Model Z {model_z:g} mm → measured {part:g} mm "
            "(offset {offset:+.2f} mm), first layer on top {first:.2f} mm."
        ),
        "insert.info_supports": "\nSupports: reprinted up to layer {layer} before the pause (green).",
        "insert.step3": "3. Safety check",
        "insert.check_intro": "The job pauses halfway and waits for you. Tick the box only if it is true.",
        "insert.check_attended": "I will stay at the printer, seat the part when it pauses and watch the first layers.",
        "insert.legend_title": "Top view (front of the plate at the bottom)",
        "legend.silhouette": "part",
        "legend.wall-bottom": "wall bottom",
        "legend.wall-top": "wall rim",
        "legend.addition": "first layer on top",
        "legend.support": "reprinted support",
        "insert.canvas_front": "front of the plate",
        "insert.err_number": "{field}: enter a number in millimetres.",
        "insert.err_whole": "{field}: enter a whole number.",
        "insert.err_attended": (
            "Safety check: confirm that you will stay at the printer to seat the part and watch the first layers."
        ),
        "insert.done": (
            "Insert G-code created.\n\n"
            "1. The printer prints a {wall_top:g} mm wall ({wall_layers} layers){supports}.\n"
            "2. It lifts to {park_z:g} mm, parks at the back and pauses.\n"
            "3. Clean the part's bottom and top, press it into the wall facing the same way as in Bambu Studio, "
            "without removing or shifting the plate, then press Resume.\n"
            "{supports_hint}"
            "4. It reheats, purges and prints from layer {resume} on top (first layer {first:.2f} mm).\n\n"
            "Inspect Bambu Studio Preview before sending."
        ),
        "insert.done_supports": " and the supports up to layer {layer}",
        "insert.done_supports_hint": (
            "   Remove the old supports from the part first and lower it slowly over the new ones.\n"
        ),
        "warnings": "Warnings:",
        # Setup window (app opened directly)
        "setup.text": (
            "Layer Rescue runs from Bambu Studio after slicing.\n\n"
            "In Bambu Studio, switch to Advanced mode, open the process settings and paste this command into "
            "Post-processing Scripts:"
        ),
        "setup.copy": "Copy",
        "setup.copied": "Copied",
        "setup.close": "Close",
        "error.tk_missing": "Tkinter is unavailable; use --start-layer/--last-layer from the CLI.",
        "error.no_window": "Could not open the window: {error}",
    },
    "tr": {
        "app.title": "Layer Rescue",
        "header.version": "sürüm {version}",
        "header.language": "Dil:",
        "file.frame": "Dilimlenen dosya",
        "file.name": "Dosya",
        "file.printer": "Yazıcı",
        "file.filament": "Filament",
        "file.layers": "Katmanlar",
        "file.layers_value": "{first}–{last} (toplam {total})",
        "choose_mode": "Baskıya ne oldu? Uygun sekmeyi seçin:",
        "tab.resume": "Parça hâlâ plakada",
        "tab.insert": "Parça ayrıldı / bitmiş parçanın üstüne bas",
        "untested.frame": "Test edilmemiş kurulum",
        "untested.intro": (
            "Layer Rescue bu tür bir işle henüz test edilmedi. Çalışabilir, ama eklediği hareketler (park, "
            "purge, home) tek filamentli bir P1S için hazırlandı."
        ),
        "untested.check": (
            "Riskleri anlıyorum ve yine de denemek istiyorum. Yazıcının başında kalacağım ve bir terslik "
            "görürsem durduracağım."
        ),
        "status.untested": "Devam etmek için test edilmemiş kurulumun risklerini kabul edin (pencerenin üstünde).",
        "button.leave": "G-code'u değiştirme",
        "button.create": "G-code oluştur",
        "status.ready": "Hazır. G-code oluşturduktan sonra Bambu Studio önizlemesini kontrol edin.",
        "status.resume_layer": "Son düzgün katmanı girin (adım 1).",
        "status.resume_checks": "Devam etmek için güvenlik kontrollerini işaretleyin (adım 3).",
        "status.insert_height": "Parça yüksekliğini girin (adım 1).",
        "status.insert_check": "Devam etmek için güvenlik kontrolünü işaretleyin.",
        "resume.intro": (
            "Baskı durdu (filament bitti, nozzle tıkandı, elektrik kesildi…) ama parça hâlâ plakaya yapışık. "
            "Yeni G-code, bir sonraki katmandan parçanın üstüne basmaya devam eder."
        ),
        "resume.step1": "1. Baskı nerede durdu?",
        "resume.last_layer": "Düzgün basılan son katman:",
        "resume.last_layer_hint": (
            "Gerçekten filament basılmış son katman. Filament 462. katmanda bittiyse ama yazıcı 490'a kadar "
            "devam ettiyse 461 girin."
        ),
        "resume.next_layer": "Baskı {layer}. katmandan devam eder (toplam {total} katman, Z = {z:g} mm).",
        "resume.layer_range": "{first} ile {last} arasında bir tam sayı girin.",
        "resume.step2": "2. Yazıcı kapatıldı ya da yeniden başlatıldı mı?",
        "resume.mode_retained": "Hayır, hep açık kaldı (Z konumu korundu)",
        "resume.mode_manual": "Evet, kapatıldı ya da yeniden başlatıldı (Z konumu kayboldu)",
        "resume.help_retained": (
            "İş, yazıcının hâlâ bildiği Z konumunu kullanır. Bunu yalnızca yazıcı hiç kapanmadıysa ve Z eksenini "
            "kimse oynatmadıysa seçin. İş hiçbir zaman Z'yi home etmez ve tabla seviyelemesi yapmaz."
        ),
        "resume.help_manual": (
            "Göndermeden önce: nozzle'ı temizleyin, son düzgün katmanın düz bir bölgesinin üstüne getirin ve "
            "yüzeye hafifçe değene kadar indirin. İşteki bütün Z hareketleri bu konuma göre görelidir; yazıcının "
            "kendini hangi Z'de sandığı önemli değildir. İş 2 mm yükselir ve yalnızca X/Y'yi home eder; Z'yi "
            "hiçbir zaman home etmez ve tabla seviyelemesi yapmaz."
        ),
        "resume.step3": "3. Güvenlik kontrolleri",
        "resume.checks_intro": (
            "Layer Rescue yazıcınızı göremez. Her kutuyu yalnızca doğruysa işaretleyin; G-code ancak hepsi "
            "işaretlendiğinde oluşturulur."
        ),
        "resume.check_attached": "Parça hâlâ aynı plakaya sağlam yapışık ve plaka yerinden oynatılmadı.",
        "resume.check_retained": "Yazıcının elektriği hiç kesilmedi ve Z ekseni oynatılmadı.",
        "resume.check_manual": "İşi başlatmadan önce temiz nozzle'ı son düzgün katmana hafifçe değene kadar indireceğim.",
        "resume.options": "Seçenekler (genelde olduğu gibi bırakın)",
        "resume.nozzle": "Nozzle sıcaklığı (°C):",
        "resume.bed": "Tabla sıcaklığı (°C):",
        "resume.temp_hint": "boş = dosyadaki değer",
        "resume.home": "Devam etmeden önce X ve Y'yi home et (G28 X, Z asla)",
        "resume.home_forced": "Devam etmeden önce X ve Y'yi home et (G28 X, Z asla) — yeniden başlatmadan sonra zorunlu",
        "resume.err_layer": "Adım 1: son düzgün katmanı tam sayı olarak girin.",
        "resume.err_attached": "Güvenlik kontrolü: parçanın hâlâ plakaya sağlam yapışık olduğunu onaylayın.",
        "resume.err_retained": "Güvenlik kontrolü: yazıcının elektriğinin ve Z konumunun hiç kaybolmadığını onaylayın.",
        "resume.err_manual": "Güvenlik kontrolü: nozzle'ı son düzgün katmana hizalayacağınızı onaylayın.",
        "resume.err_temperature": "{field}: °C cinsinden bir tam sayı girin ya da boş bırakın.",
        "resume.done_title": "Kurtarma G-code'u oluşturuldu",
        "resume.done": (
            "Kurtarma G-code'u oluşturuldu.\n\n"
            "Başlangıç katmanı: {layer}/{total}\n"
            "Z: {z:g} mm\n"
            "Z modu: {mode}\n"
            "Nozzle: {nozzle}°C\n"
            "Tabla: {bed}°C\n\n"
            "Göndermeden önce Bambu Studio önizlemesini kontrol edin."
        ),
        "resume.done_retained": "yazıcı açık kaldı (Z korundu)",
        "resume.done_manual": "yeniden başlatıldı, nozzle Z = {z:g} mm yüzeyine değiyor",
        "resume.done_manual_reminder": (
            "\n\nGöndermeden önce: temiz nozzle'ı son düzgün katmanın üstüne hafifçe değecek şekilde hizalayın. "
            "Tam olarak hizalanmadıysa başlatmayın."
        ),
        "insert.intro": (
            "Plakadan kopmuş, kırılmış (kırık yeri önce düz kesin) ya da bitmiş ve üstüne ekleme yapılacak bir "
            "parça için. Tam modeli dilimleyin. Yazıcı parçayı tutan bir duvar basar, parçayı içine koymanız "
            "için duraklar, sonra kalanını üstüne basar."
        ),
        "insert.step1": "1. Parça ve duvar",
        "insert.part_height": "Parça yüksekliği (mm, ölçülen):",
        "insert.part_layer": "ya da parçanın son katmanı:",
        "insert.wall_height": "Duvar yüksekliği (mm):",
        "insert.wall_hint": "boş = önerilen",
        "insert.preview": "Önizle",
        "insert.show_advanced": "Gelişmiş ayarları göster",
        "insert.advanced": "Gelişmiş ayarlar",
        "insert.clearance": "Parça ile duvar arası boşluk (mm)",
        "insert.lines": "Duvar kalınlığı (çizgi)",
        "insert.brim": "Brim (mm)",
        "insert.fine": "Z ince ayarı (mm, − = daha fazla ezme)",
        "insert.standby": "Duraklarken nozzle (°C, 0 = sıcak kalsın)",
        "insert.adhesion": "Yapışma katmanları (daha sıcak, yavaş, fansız)",
        "insert.chamfer": "Duvar ağzında giriş pahı",
        "insert.supports": "Parça yüksekliğinin altındaki destekleri yeniden bas (duraklamadan önce)",
        "insert.step2": "2. Sonuç",
        "insert.info_start": "Parça yüksekliğini girip Önizle'ye basın.",
        "insert.info": (
            "Duvar: 1–{wall_last}. katmanlar, {wall_top:g} mm'ye kadar (önerilen {recommended:g} mm).\n"
            "Duraklama, ardından {resume}. katmandan devam (toplam {total}). Model Z {model_z:g} mm → ölçülen "
            "{part:g} mm (fark {offset:+.2f} mm), parçanın üstündeki ilk katman {first:.2f} mm."
        ),
        "insert.info_supports": "\nDestekler: duraklamadan önce {layer}. katmana kadar yeniden basılır (yeşil).",
        "insert.step3": "3. Güvenlik kontrolü",
        "insert.check_intro": "İş yarıda duraklar ve sizi bekler. Kutuyu yalnızca doğruysa işaretleyin.",
        "insert.check_attended": (
            "Yazıcının başında kalacağım, duraklayınca parçayı yerleştireceğim ve ilk katmanları izleyeceğim."
        ),
        "insert.legend_title": "Üstten görünüm (plakanın önü altta)",
        "legend.silhouette": "parça",
        "legend.wall-bottom": "duvarın tabanı",
        "legend.wall-top": "duvar ağzı",
        "legend.addition": "üstteki ilk katman",
        "legend.support": "yeniden basılan destek",
        "insert.canvas_front": "plakanın önü",
        "insert.err_number": "{field}: milimetre cinsinden bir sayı girin.",
        "insert.err_whole": "{field}: bir tam sayı girin.",
        "insert.err_attended": (
            "Güvenlik kontrolü: parçayı yerleştirmek ve ilk katmanları izlemek için yazıcının başında "
            "kalacağınızı onaylayın."
        ),
        "insert.done": (
            "Yerleştirme G-code'u oluşturuldu.\n\n"
            "1. Yazıcı {wall_top:g} mm yüksekliğinde bir duvar basar ({wall_layers} katman){supports}.\n"
            "2. {park_z:g} mm'ye yükselir, arkaya park eder ve duraklar.\n"
            "3. Parçanın altını ve üstünü temizleyin, plakayı çıkarmadan ve oynatmadan parçayı Bambu Studio'daki "
            "yönüyle duvara bastırın, sonra Resume'a (Devam) basın.\n"
            "{supports_hint}"
            "4. Yazıcı ısınır, purge yapar ve {resume}. katmandan itibaren parçanın üstüne basar "
            "(ilk katman {first:.2f} mm).\n\n"
            "Göndermeden önce Bambu Studio önizlemesini kontrol edin."
        ),
        "insert.done_supports": " ve {layer}. katmana kadar destekleri",
        "insert.done_supports_hint": (
            "   Önce eski destekleri parçadan temizleyin ve parçayı yeni desteklerin üzerine yavaşça indirin.\n"
        ),
        "warnings": "Uyarılar:",
        "setup.text": (
            "Layer Rescue, Bambu Studio'da dilimlemeden sonra çalışır.\n\n"
            "Bambu Studio'yu Advanced (Gelişmiş) moda alın, process ayarlarını açın ve şu komutu "
            "Post-processing Scripts alanına yapıştırın:"
        ),
        "setup.copy": "Kopyala",
        "setup.copied": "Kopyalandı",
        "setup.close": "Kapat",
        "error.tk_missing": "Tkinter bulunamadı; komut satırından --start-layer/--last-layer kullanın.",
        "error.no_window": "Pencere açılamadı: {error}",
    },
}


# Core messages (English) → Turkish. Each pattern must match the whole message.
MESSAGE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p), t)
    for p, t in [
        # gcode.py
        (r"Layer (?P<n>\d+) is not present in this G-code file\.", "{n}. katman bu G-code dosyasında yok."),
        (r"Layer\(s\) (?P<l>\[.*\]) are not present in this G-code file\.", "Şu katmanlar bu G-code dosyasında yok: {l}."),
        (r"Required Bambu Studio marker is missing: (?P<m>.+)", "Gerekli Bambu Studio işareti eksik: {m}"),
        (r"No Bambu Studio layer markers were found\.", "Bambu Studio katman işaretleri bulunamadı."),
        (r"Duplicate layer marker found for layer (?P<n>\d+)\.", "{n}. katman için tekrarlanan katman işareti var."),
        (r"Layer (?P<n>\d+) has no '; Z_HEIGHT:' marker\.", "{n}. katmanda '; Z_HEIGHT:' işareti yok."),
        (r"Layer markers disagree about the total layer count\.", "Katman işaretleri toplam katman sayısında uyuşmuyor."),
        (r"Layer markers are not strictly increasing\.", "Katman işaretleri artan sırada değil."),
        (r"The G-code file is empty\.", "G-code dosyası boş."),
        (r"This G-code has already been processed by Layer Rescue\.", "Bu G-code zaten Layer Rescue ile işlenmiş."),
        (
            r"The Bambu Studio header/config/executable blocks are out of order\.",
            "Bambu Studio başlık/ayar/komut blokları beklenen sırada değil.",
        ),
        (r"The source contains non-contiguous layer numbers\.", "Dosyadaki katman numaraları ardışık değil."),
        # fileio.py
        (r"G-code file does not exist: (?P<p>.+)", "G-code dosyası bulunamadı: {p}"),
        (r"Post-processing MVP accepts raw \.gcode files only\.", "Yalnızca düz .gcode dosyaları işlenebilir."),
        # machine_state.py
        (
            r"MVP safety guard: sequential/by-object printing is not supported\.",
            "Güvenlik kontrolü: nesne bazlı (sıralı) baskı desteklenmiyor.",
        ),
        (r"MVP safety guard: spiral-vase G-code is not supported\.", "Güvenlik kontrolü: spiral vazo modu desteklenmiyor."),
        (
            r"MVP safety guard: the selected layer must begin from known absolute positioning \(G90\)\.",
            "Güvenlik kontrolü: seçilen katman bilinen mutlak konumlandırmayla (G90) başlamalı.",
        ),
        (
            r"MVP safety guard: only known relative extrusion \(M83\) is supported\.",
            "Güvenlik kontrolü: yalnızca göreli ekstrüzyon (M83) destekleniyor.",
        ),
        (
            r"Could not determine the active nozzle temperature at the selected layer\.",
            "Seçilen katmandaki nozzle sıcaklığı belirlenemedi; elle girin.",
        ),
        (
            r"Could not determine the active bed temperature at the selected layer\.",
            "Seçilen katmandaki tabla sıcaklığı belirlenemedi; elle girin.",
        ),
        (
            r"Untested printer: this G-code is for '(?P<m>.*)', and Layer Rescue has only been tested on the "
            r"Bambu Lab P1S\. Parking, purging and homing positions may not fit this printer\.(?P<h>.*)",
            "Test edilmemiş yazıcı: bu G-code '{m}' için hazırlanmış, Layer Rescue ise şimdiye kadar yalnızca "
            "Bambu Lab P1S'te test edildi. Park, purge ve home konumları bu yazıcıya uymayabilir.{h}",
        ),
        (
            r"Untested setup: this job uses (?P<n>\d+) filaments \(AMS/tool changes\), and Layer Rescue has only "
            r"been tested with a single filament\. It loads the filament that was active at the selected layer\.(?P<h>.*)",
            "Test edilmemiş kurulum: bu iş {n} filament kullanıyor (AMS/filament değişimi), Layer Rescue ise "
            "şimdiye kadar yalnızca tek filamentle test edildi. Seçilen katmanda kullanılan filamenti yükler.{h}",
        ),
        # resume.py
        (
            r"Manual Z reference requires a preceding successfully printed layer\.",
            "Manuel Z referansı için daha önce düzgün basılmış bir katman gerekir.",
        ),
        (
            r"Manual Z reference requires contiguous selected and preceding layers\.",
            "Manuel Z referansı için seçilen katman ile bir önceki katman ardışık olmalı.",
        ),
        (
            r"Restarted mode cannot convert a conditional firmware block that changes Z \(source body lines "
            r"(?P<a>\d+)-(?P<b>\d+)\); the result would depend on whether the printer executes it\.",
            "Yeniden başlatma modu, Z'yi değiştiren koşullu bir firmware bloğunu dönüştüremez (satır {a}-{b}); "
            "sonuç yazıcının bu bloğu çalıştırıp çalıştırmamasına bağlı olurdu.",
        ),
        (
            r"Restarted mode cannot convert a source that reassigns Z with G92\.",
            "Yeniden başlatma modu, Z'yi G92 ile yeniden atayan bir dosyayı dönüştüremez.",
        ),
        (
            r"Restarted mode cannot convert an extruding move that also changes Z: (?P<c>.+)",
            "Yeniden başlatma modu, ekstrüzyon yaparken Z'yi de değiştiren bir hareketi dönüştüremez: {c}",
        ),
        (
            r"Restarted mode found an unterminated conditional firmware block\.",
            "Yeniden başlatma modu kapanmamış bir koşullu firmware bloğu buldu.",
        ),
        (
            r"Nozzle temperature (?P<t>-?\d+)°C is outside the allowed 150–300°C range\.",
            "Nozzle sıcaklığı {t}°C, izin verilen 150–300°C aralığının dışında.",
        ),
        (
            r"Bed temperature (?P<t>-?\d+)°C is outside the allowed 0–120°C range\.",
            "Tabla sıcaklığı {t}°C, izin verilen 0–120°C aralığının dışında.",
        ),
        (
            r"The relative Z safety lift must be between 0\.5 and 10 mm\.",
            "Z güvenlik yükselmesi 0,5 ile 10 mm arasında olmalı.",
        ),
        (
            r"The purge length must be between 0 and 100 mm of filament\.",
            "Purge uzunluğu 0 ile 100 mm filament arasında olmalı.",
        ),
        (
            r"Manual Z reference mode requires CoreXY homing after the safety lift\.",
            "Manuel Z modu, güvenlik yükselmesinden sonra X/Y home işlemi gerektirir.",
        ),
        (
            r"Choose a start layer after the first layer; a normal print should be used instead\.",
            "Başlangıç katmanı ilk katmandan sonra olmalı; baştan başlayacaksanız normal baskı yapın.",
        ),
        (
            r"The selected start layer is beyond the end of the print\.",
            "Seçilen başlangıç katmanı baskının sonundan sonra geliyor; devam ettirilecek katman kalmıyor.",
        ),
        (
            r"Manual Z mode depends on the operator aligning the nozzle to the last successful layer before "
            r"job start\.",
            "Manuel Z modu, iş başlamadan önce nozzle'ı son düzgün katmana sizin hizalamanıza bağlıdır.",
        ),
        # insert.py
        (
            r"The part must be at least (?P<v>[\d.]+) mm tall for insert mode\.",
            "Yerleştirme modu için parça en az {v} mm yüksek olmalı.",
        ),
        (r"The holding wall must be at least (?P<v>[\d.]+) mm tall\.", "Tutucu duvar en az {v} mm yüksek olmalı."),
        (
            r"The holding wall must end at least (?P<g>[\d.]+) mm below the top of the part \(at most "
            r"(?P<m>-?[\d.]+) mm here\), or the nozzle hits it\.",
            "Tutucu duvar parçanın tepesinden en az {g} mm aşağıda bitmeli (burada en fazla {m} mm), yoksa "
            "nozzle duvara çarpar.",
        ),
        (r"The wall clearance must be between 0\.05 and 1\.0 mm\.", "Duvar boşluğu 0,05 ile 1,0 mm arasında olmalı."),
        (r"The wall must be 2 to 12 lines thick\.", "Duvar kalınlığı 2 ile 12 çizgi arasında olmalı."),
        (r"The brim must be between 0 and 15 mm\.", "Brim 0 ile 15 mm arasında olmalı."),
        (r"The Z fine adjustment must be within ±(?P<v>[\d.]+) mm\.", "Z ince ayarı ±{v} mm içinde olmalı."),
        (r"The park lift must be between 5 and 50 mm\.", "Park yüksekliği 5 ile 50 mm arasında olmalı."),
        (
            r"The standby temperature must be 0 \(off\) or between 100 and 250°C\.",
            "Duraklama sıcaklığı 0 (kapalı) ya da 100–250°C arasında olmalı.",
        ),
        (r"Adhesion layers must be between 0 and 10\.", "Yapışma katmanı sayısı 0 ile 10 arasında olmalı."),
        (
            r"The adhesion temperature boost must be between 0 and 30°C\.",
            "Yapışma sıcaklık artışı 0 ile 30°C arasında olmalı.",
        ),
        (r"The adhesion speed must be between 20 and 100 %\.", "Yapışma hızı %20 ile %100 arasında olmalı."),
        (
            r"Insert mode needs the complete job starting at layer 1\.",
            "Yerleştirme modu, 1. katmandan başlayan tam işi gerektirir.",
        ),
        (
            r"The part is as tall as the whole model \((?P<z>[\d.]+) mm\): there is nothing left to print on top\.",
            "Parça bütün model kadar yüksek ({z} mm): üstüne basılacak bir şey kalmıyor.",
        ),
        (
            r"The layers around the part height are not contiguous\.",
            "Parça yüksekliği civarındaki katmanlar ardışık değil.",
        ),
        (
            r"The Z fine adjustment leaves no room for the first layer on top of the part\.",
            "Z ince ayarı, parçanın üstündeki ilk katmana yer bırakmıyor.",
        ),
        (r"The holding wall must span at least two layers\.", "Tutucu duvar en az iki katman yüksekliğinde olmalı."),
        (r"The holding wall must end below the top of the part\.", "Tutucu duvar parçanın tepesinin altında bitmeli."),
        (
            r"(?P<p>\d+)% of the support below the part height lies where the part is lowered in \(or stands on "
            r"the part\) and is not reprinted\.",
            "Parça yüksekliğinin altındaki desteklerin %{p} kadarı parçanın indirileceği yerde (ya da parçanın "
            "üstünde) kaldığı için yeniden basılmıyor.",
        ),
        (
            r"Supports below the part height are printed again before the pause\. Remove what is left of the old "
            r"supports from the part so it slides over the new ones\.",
            "Parça yüksekliğinin altındaki destekler duraklamadan önce yeniden basılır. Parçanın yeni desteklerin "
            "üzerinden kayabilmesi için eski desteklerden kalanları parçadan temizleyin.",
        ),
        (
            r"About (?P<a>\d+) mm² of support just above the part height has nothing under it and will start in "
            r"the air\.",
            "Parça yüksekliğinin hemen üstündeki yaklaşık {a} mm² desteğin altında bir şey yok; havada başlayacak.",
        ),
        (
            r"The job has supports but reprinting them is off: supports above the part height start in the air "
            r"unless the old ones are still on the part\.",
            "İşte destek var ama yeniden basma kapalı: eski destekler parçanın üstünde durmuyorsa parça "
            "yüksekliğinin üstündeki destekler havada başlar.",
        ),
        (
            r"Layer (?P<n>\d+) has no printed outline to derive the holding wall from\.",
            "{n}. katmanda tutucu duvarın çıkarılabileceği basılı bir dış hat yok.",
        ),
        (
            r"The part is too small to hold in a wall \(narrowest side (?P<b>[\d.]+) mm, minimum "
            r"(?P<m>[\d.]+) mm\)\.",
            "Parça bir duvarda tutulamayacak kadar küçük (en dar kenar {b} mm, en az {m} mm).",
        ),
        (
            r"The part's footprint is narrow \((?P<b>[\d.]+) mm\); the wall may not hold it firmly\. Seat it "
            r"gently\.",
            "Parçanın tabanı dar ({b} mm); duvar parçayı sıkı tutamayabilir. Dikkatlice oturtun.",
        ),
        (
            r"The part is shorter than 5 mm; the wall can only grip a small area\.",
            "Parça 5 mm'den kısa; duvar parçayı yalnızca küçük bir alandan tutabilir.",
        ),
        (
            r"The first layer on top reaches (?P<a>\d+) mm² beyond the part's top surface; that area is printed "
            r"in the air\.",
            "Üstteki ilk katman parçanın üst yüzeyinin {a} mm² dışına taşıyor; bu alan havada basılır.",
        ),
        (
            r"The part looks the same when turned, so the wall cannot fix its orientation\. Seat it facing the "
            r"same way as in Bambu Studio \(the plate's front edge is the front\)\.",
            "Parça döndürüldüğünde aynı göründüğü için duvar yönünü sabitleyemez. Parçayı Bambu Studio'daki "
            "yönüyle oturtun (plakanın ön kenarı öndür).",
        ),
        (
            r"The part is too tall to park the toolhead safely above it\.",
            "Parça, baskı kafasının üstünde güvenle park edebileceği yükseklikten fazla.",
        ),
        (
            r"Insert mode does not support a prime tower\. Disable it and slice again\.",
            "Yerleştirme modu prime tower desteklemez. Kapatıp yeniden dilimleyin.",
        ),
        (
            r"Insert mode supports a single object on the plate; this job prints (?P<n>\d+) objects below the "
            r"part height\.",
            "Yerleştirme modu plakada tek obje destekler; bu iş parça yüksekliğinin altında {n} obje basıyor.",
        ),
        (
            r"The holding wall \(with its brim\) does not fit on the bed\. Move the model inwards\.",
            "Tutucu duvar (brim ile birlikte) tablaya sığmıyor. Modeli içeri doğru taşıyın.",
        ),
        (
            r"The holding wall would cross the bed's excluded area\. Move the model away from it\.",
            "Tutucu duvar tablanın yasak bölgesine giriyor. Modeli oradan uzaklaştırın.",
        ),
        (
            r"Layer (?P<n>\d+): a firmware conditional block runs into the toolpaths\.",
            "{n}. katman: koşullu bir firmware bloğu takım yollarının içine uzanıyor.",
        ),
        (
            r"Insert mode cannot shift a source that reassigns Z with G92\.",
            "Yerleştirme modu, Z'yi G92 ile yeniden atayan bir dosyayı kaydıramaz.",
        ),
        # Bugs: keep the English details for the bug report.
        (
            r"Internal validation failed: (?P<d>.+)",
            "İç doğrulama başarısız oldu, dosya değiştirilmedi. Lütfen bu mesajla bir hata kaydı açın: {d}",
        ),
        (
            r"Unsafe (?P<d>.+)",
            "Güvenli olmayan bir komut kaldı, dosya değiştirilmedi. Lütfen bu mesajla bir hata kaydı açın: Unsafe {d}",
        ),
    ]
]


# Fixed suffixes captured by the patterns above, in Turkish.
HINTS = {
    " To try it anyway, accept the risks (CLI: --allow-untested).": (
        " Yine de denemek isterseniz riskleri kabul edin (CLI: --allow-untested)."
    ),
}


def translate_message(message: str, language: str) -> str:
    """Translate an English message from the core modules; unknown messages stay as they are."""
    if language == "en":
        return message
    text = message.strip()
    for pattern, template in MESSAGE_PATTERNS:
        match = pattern.fullmatch(text)
        if match:
            values = {key: HINTS.get(value, value) for key, value in match.groupdict().items()}
            return template.format(**values)
    return message


def _settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "LayerRescue" / "settings.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "LayerRescue" / "settings.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "layer-rescue" / "settings.json"


def _system_language() -> str:
    candidates = [os.environ.get(name, "") for name in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE")]
    try:
        candidates.append(locale.getlocale()[0] or "")
    except ValueError:
        pass
    if sys.platform == "win32":
        try:
            import ctypes

            candidates.append(locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), ""))
        except Exception:  # noqa: BLE001 - any failure just means "unknown"
            pass
    for value in candidates:
        lowered = value.lower()
        if lowered.startswith("tr") or lowered.startswith("turkish"):
            return "tr"
    return DEFAULT_LANGUAGE


def load_language(path: Path | None = None) -> str:
    """The saved language, else the system language, else English."""
    try:
        data = json.loads((path or _settings_path()).read_text(encoding="utf-8"))
        if data.get("language") in LANGUAGES:
            return data["language"]
    except (OSError, ValueError, AttributeError):
        pass
    return _system_language()


def save_language(language: str, path: Path | None = None) -> None:
    target = path or _settings_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
        if not isinstance(data, dict):
            data = {}
        data["language"] = language
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (OSError, ValueError):
        pass  # The choice still applies to this window; it is just not remembered.


class Translator:
    """Current language plus the callbacks that refresh the window when it changes."""

    def __init__(self, language: str | None = None, *, remember: bool = True) -> None:
        self.language = language if language in LANGUAGES else load_language()
        self.remember = remember
        self._listeners: list[Callable[[], None]] = []

    def __call__(self, key: str, **values: object) -> str:
        text = STRINGS[self.language].get(key) or STRINGS[DEFAULT_LANGUAGE][key]
        return text.format(**values) if values else text

    def message(self, text: str) -> str:
        return translate_message(str(text), self.language)

    def on_change(self, callback: Callable[[], None]) -> None:
        """Run ``callback`` now and whenever the language changes."""
        self._listeners.append(callback)
        callback()

    def set_language(self, language: str) -> None:
        if language not in LANGUAGES or language == self.language:
            return
        self.language = language
        if self.remember:
            save_language(language)
        for callback in list(self._listeners):
            callback()
