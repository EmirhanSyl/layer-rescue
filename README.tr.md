# Layer Rescue

Layer Rescue, yarım kalan Bambu Lab P1S baskılarını seçilen katmandan devam ettirmek için deneysel ve tedbirli bir G-code son işlem aracıdır. Bambu Studio'nun **Post-processing Scripts** özelliğine bağlanır; böylece filament eşlemesi ve `.gcode.3mf` metadatası Studio tarafından korunur, değiştirilmiş takım yolu Preview ekranında yeniden okunur.

> [!CAUTION]
> Yarım baskıyı devam ettirmek nozzle'ın mevcut parçaya çarpmasına yol açabilir. Yazıcı Z konumunu kaybettiyse aracı kesinlikle kullanmayın.

## İlk sürümün kapsamı

- Bambu Lab P1S
- Tek mantıksal filament (`T0`)
- Katman bazlı baskı
- Göreli ekstrüzyon (`M83`)
- Yazıcı açık kalmış ve Z koordinatı korunmuş olmalı
- Parça aynı plakada sağlam biçimde durmalı

Henüz desteklenmeyenler: çok filamentli/AMS geçişli işler, nesne bazlı sıralı baskı, spiral vase, Z konumunun kaybolduğu durumlar, diğer yazıcı modelleri ve `.gcode.3mf` dosyasını doğrudan düzenleme.

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

```bash
layer-rescue --last-layer 461 --assume-z-known --nozzle-temp 220 print.gcode
```

`--assume-z-known` seçeneğinin zorunlu olması bilinçli bir güvenlik önlemidir.

## Kritik ayrım

Girilecek katman, yazıcının hatayı fark ettiği katman değil, fiziksel olarak filament basılmış son katmandır. Örneğin filament 462'de bittiyse fakat sensör 490'da fark ettiyse son başarılı katman 461 olarak girilmelidir.

Bu proje Bambu Lab ile bağlantılı veya Bambu Lab tarafından onaylanmış değildir.

## Test

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Lisans: MIT.
