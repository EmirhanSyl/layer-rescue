# Layer Rescue

[English](README.md)

Yarım kalan Bambu Lab P1S baskılarını seçilen katmandan devam ettirir.

Layer Rescue, Bambu Studio'da post-processing script olarak çalışır. Dilimlemeden sonra düzgün basılan son katmanı sorar ve G-code'u, baskı plakada duran parçanın üzerinden bir sonraki katmandan devam edecek şekilde yeniden yazar. Filament eşlemesi ve `.gcode.3mf` bilgileri Bambu Studio'da kalır; sonucu göndermeden önce önizlemede görürsünüz.

> [!CAUTION]
> Baskıyı devam ettirirken nozzle mevcut parçaya çarpabilir. Başlangıç sırasında yazıcının başında durun ve gerekirse hemen durdurun. Ayrıntılar için [SECURITY.md](SECURITY.md).

## Desteklenenler

- Bambu Lab P1S, tek filament
- Bambu Studio G-code'u, katman bazlı baskı, göreli ekstrüzyon
- Parça aynı plakada sağlam duruyor olmalı

Henüz desteklenmeyenler: AMS/çok filamentli işler, nesne bazlı baskı, spiral vazo, diğer yazıcı modelleri.

## Kurulum

**Windows:** [Releases](https://github.com/EmirhanSyl/layer-rescue/releases) sayfasından `LayerRescue-Setup-<sürüm>-win-x64.exe` dosyasını indirip çalıştırın. Kurulumun son sayfasında Bambu Studio'ya yapıştırılacak komut yazar.

**Kaynaktan** (her işletim sistemi, Python 3.10+; pencere için Tkinter gerekir):

```bash
pipx install git+https://github.com/EmirhanSyl/layer-rescue.git
```

## Bambu Studio ayarı

1. Bambu Studio'yu Advanced moda alın.
2. Process ayarlarında **Post-processing Scripts** alanını bulun.
3. `LayerRescue.exe` dosyasının (ya da `layer-rescue` komutunun) tam yolunu tırnak içinde yazın.

Post-processing script'ler çalıştırılabilir dosya olduğu için Studio uyarı gösterebilir. Yalnızca güvendiğiniz kaynaktan kurduğunuz araçları onaylayın.

## Baskıyı devam ettirme

1. Gerçekten filament basılmış son katmanı bulun. Filament 462. katmanda bittiyse ama yazıcı 490'da durduysa 461 girin.
2. Orijinal projeyi dilimleyin. Layer Rescue penceresi açılır.
3. Son düzgün katmanı yazın ve Z modunu seçin:
   - **Printer stayed powered on (`retained`)**: yazıcı hiç kapanmadı, Z konumu korundu. Başka bir şey yapmanız gerekmez.
   - **Printer was restarted (`manual`)**: yazıcı kapatılıp açıldıysa Z home edilmemiştir. Nozzle'ı temizleyin, son katmanın düz bir bölgesinin üstüne getirin ve yüzeye hafifçe değene kadar indirin. Parçayı ve plakayı oynatmayın.
4. Önizlemeyi kontrol edip işi gönderin.

Normal baskılarda **Leave unchanged** düğmesine basın.

### Oluşturulan iş ne yapar

Orijinal başlık ve ayarları korur, başlangıç rutinini ve basılmış katmanları çıkarır, sıcaklıkları, fanları ve hareket limitlerini geri yükler. Nozzle'ı kaldırır, yalnızca X/Y eksenlerini home eder (`G28 X`), arkadaki atık kanalında purge yapar, katmanın ilk noktasının üstüne gider, aşağı iner ve orijinal G-code ile sona kadar devam eder.

Z eksenini hiçbir zaman home etmez ve tabla seviyelemesi yapmaz. Manuel modda bütün Z hareketleri sizin hizaladığınız konuma göre görelidir; yazıcı yeniden başlatıldıktan sonra kendini hangi Z'de sanırsa sansın sonuç değişmez.

Dosya yerinde değiştirilir, orijinalin bir kopyası `.layer-rescue.bak` uzantısıyla yanında kalır.

## Komut satırı

```bash
layer-rescue --analyze print.gcode
layer-rescue --last-layer 461 --z-mode retained print.gcode
layer-rescue --last-layer 461 --z-mode manual --confirm-manual-z-aligned print.gcode
```

`--nozzle-temp` ve `--bed-temp` algılanan sıcaklıkları değiştirir. Bütün seçenekler için `layer-rescue --help`.

## Katkı

En faydalı katkı; yazıcı modeli, firmware sürümü ve G-code dosyasıyla birlikte açılan hata kayıtlarıdır. Ayrıntılar için [CONTRIBUTING.md](CONTRIBUTING.md).

## Lisans

[MIT](LICENSE). Bambu Lab ile bağlantılı değildir ve Bambu Lab tarafından onaylanmamıştır.
