# Layer Rescue

[English](README.md)

Yarım kalan Bambu Lab P1S baskılarını seçilen katmandan devam ettirir.

Layer Rescue, Bambu Studio'da post-processing script olarak çalışır. Dilimlemeden sonra düzgün basılan son katmanı sorar ve G-code'u, baskı plakada duran parçanın üzerinden bir sonraki katmandan devam edecek şekilde yeniden yazar. Filament eşlemesi ve `.gcode.3mf` bilgileri Bambu Studio'da kalır; sonucu göndermeden önce önizlemede görürsünüz.

> [!CAUTION]
> Baskıyı devam ettirirken nozzle mevcut parçaya çarpabilir. Başlangıç sırasında yazıcının başında durun ve gerekirse hemen durdurun. Ayrıntılar için [SECURITY.md](SECURITY.md).

## Desteklenenler

- Bambu Lab P1S, tek filament
- Windows ve macOS (Linux kaynaktan kurulumla)
- Bambu Studio G-code'u, katman bazlı baskı, göreli ekstrüzyon
- Parça aynı plakada sağlam duruyor olmalı

Henüz desteklenmeyenler: AMS/çok filamentli işler, nesne bazlı baskı, spiral vazo, diğer yazıcı modelleri.

## Kurulum

İndirmeler [Releases](https://github.com/EmirhanSyl/layer-rescue/releases) sayfasında.

**Windows:** `LayerRescue-Setup-<sürüm>-win-x64.exe` dosyasını çalıştırın. Kurulumun son sayfasında Bambu Studio'ya yapıştırılacak komut yazar.

**macOS (Apple Silicon):** `LayerRescue-<sürüm>-macos-arm64.zip` dosyasını açıp `LayerRescue.app` uygulamasını Uygulamalar klasörüne taşıyın. Uygulama henüz Apple Developer ID ile imzalı olmadığı için macOS ilk açılışta engeller:

1. `LayerRescue.app` uygulamasına çift tıklayın. macOS açılamayacağını söyler; **Bitti**'ye basın.
2. **Sistem Ayarları → Gizlilik ve Güvenlik** bölümünde aşağı inip Layer Rescue'nun yanındaki **Yine de Aç** düğmesine basın.
3. Uygulama açılır ve Bambu Studio'ya yapıştırılacak komutu gösterir.

Bunu Bambu Studio'dan kullanmadan önce bir kez yapın, yoksa Studio uygulamayı başlatamaz. Alternatif olarak `xattr -dr com.apple.quarantine /Applications/LayerRescue.app` komutunu çalıştırabilirsiniz.

**Intel Mac, Linux ve diğerleri:** Python 3.10+ ile kaynaktan kurun (pencere için Tkinter gerekir; Homebrew Python kullanıyorsanız `brew install python-tk` de çalıştırın):

```bash
pipx install git+https://github.com/EmirhanSyl/layer-rescue.git
```

## Bambu Studio ayarı

1. Bambu Studio'yu Advanced moda alın.
2. Process ayarlarında **Post-processing Scripts** alanını bulun.
3. Layer Rescue'nun tam yolunu tırnak içinde yazın:

   | Kurulum | Komut |
   | --- | --- |
   | Windows kurulumu | `"C:\Users\<kullanıcı>\AppData\Local\Programs\LayerRescue\LayerRescue.exe"` |
   | macOS uygulaması | `"/Applications/LayerRescue.app/Contents/MacOS/LayerRescue"` |
   | pipx | `which layer-rescue` çıktısı, örn. `"/Users/<kullanıcı>/.local/bin/layer-rescue"` |

   Uygulamayı Bambu Studio olmadan doğrudan açarsanız kendi kurulumunuza ait komutu gösterir.

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
