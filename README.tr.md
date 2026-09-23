# Layer Rescue

Layer Rescue, yarım kalan Bambu Lab P1S baskılarını seçilen katmandan devam ettirmek için deneysel ve tedbirli bir G-code son işlem aracıdır. Bambu Studio'nun **Post-processing Scripts** özelliğine bağlanır; böylece filament eşlemesi ve `.gcode.3mf` metadatası Studio tarafından korunur, değiştirilmiş takım yolu Preview ekranında yeniden okunur.

> [!CAUTION]
> Yarım baskıyı devam ettirmek nozzle'ın mevcut parçaya çarpmasına yol açabilir. Yeniden başlatılmış yazıcı modu hassas manuel Z hizalaması ve başlangıcın sürekli gözetimini gerektirir.

## İlk sürümün kapsamı

- Bambu Lab P1S
- Tek mantıksal filament (`T0`)
- Katman bazlı baskı
- Göreli ekstrüzyon (`M83`)
- Yazıcı açık kaldığında korunan-Z modu
- Yazıcı yeniden başlatıldığında, ilk Z hareketinden önce `G92 Z` kullanan manuel referans modu
- Parça aynı plakada sağlam biçimde durmalı

Henüz desteklenmeyenler: çok filamentli/AMS geçişli işler, nesne bazlı sıralı baskı, spiral vase, gözetimsiz kurtarma, diğer yazıcı modelleri ve `.gcode.3mf` dosyasını doğrudan düzenleme.

## Z referans modları

### Yazıcı açık kaldı (`retained`)

Yalnızca yazıcı hiç kapanmadıysa ve Z motorları konum kaybetmediyse kullanılmalıdır. Araç yazıcının mevcut mantıksal Z koordinatını korur, 2 mm göreli güvenlik boşluğu açar ve isteğe bağlı olarak `G28 X` ile CoreXY referanslaması yapar.

### Yazıcı yeniden başlatıldı (`manual`)

Güç döngüsünden sonra tablanın fiziksel konumu ile firmware'in mantıksal Z koordinatı aynı olmayabilir. Kurtarma işini göndermeden önce:

1. nozulu temizleyin;
2. nozulu son başarılı katmanın gerçekten basılmış, düz bir bölgesinin üzerine getirin;
3. Z'yi, nozul yüzeye yalnızca temas edene kadar ayarlayın;
4. parçayı ve plakayı yerinden oynatmayın;
5. **Yazıcı yeniden başlatıldı (manuel Z referansı)** modunu seçip hizalamayı onaylayın.

Üretilen iş, bu fiziksel konuma `G92 Z...` ile bir önceki katmanın slicer'daki bilinen yüksekliğini atar. Bu komut bütün Z hareketlerinden önce yazılır. Ardından göreli güvenlik kaldırması yapılır, yalnızca CoreXY home edilir ve sonraki katmanın mutlak Z yüksekliğine gidilir.

Manuel mod hiçbir zaman `G28 Z` çalıştırmaz. Tabla üzerinde yarım parça varken Z home yapmak parçayı gantriye kaldırabilir. Manuel modda `G28 X` zorunludur; `--no-home-corexy` ile birlikte kullanılamaz.

## Kurulum

```bash
python3 -m pip install .
```

İzole kurulum için `pipx install .` önerilir.

## Bambu Studio'ya bağlama

1. Bambu Studio'yu Advanced/Expert moda alın.
2. Process ayarlarında **Post-processing Scripts** alanını arayın.
3. Kurulu `layer-rescue` komutunun mutlak yolunu girin.
4. Dilimleme yapın.
5. Normal baskıda **Leave unchanged** düğmesine basın.
6. Kurtarma işleminde gerçekten filament basılmış son katmanı yazın. Araç bir sonraki katmandan başlar.
7. Göndermeden önce Preview ekranını mutlaka inceleyin.

Studio, çalıştırılabilir bir komut olduğu için güvenlik uyarısı gösterebilir. Yalnızca güvendiğiniz kaynaktan kurduğunuz aracı onaylayın.

## Komut satırı örneği

Yazıcı açık kaldıysa:

```bash
layer-rescue --last-layer 461 --z-mode retained --nozzle-temp 220 print.gcode
```

Yazıcı yeniden başlatıldıysa ve nozul 461. katmanın yüzeyine elle hizalandıysa:

```bash
layer-rescue --last-layer 461 --z-mode manual --confirm-manual-z-aligned --nozzle-temp 220 print.gcode
```

Eski `--assume-z-known` seçeneği, geriye uyumluluk için `--z-mode retained` takma adı olarak kalır.

## Kritik ayrım

Girilecek katman, yazıcının hatayı fark ettiği katman değil, fiziksel olarak filament basılmış son katmandır. Örneğin filament 462'de bittiyse fakat sensör 490'da fark ettiyse son başarılı katman 461 olarak girilmelidir.

Bu proje Bambu Lab ile bağlantılı veya Bambu Lab tarafından onaylanmış değildir.

## Test

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Lisans: MIT.
