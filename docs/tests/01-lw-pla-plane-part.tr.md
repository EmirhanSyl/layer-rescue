# Test 1: Filament sıkışmasından sonra LW-PLA uçak parçası

[English](01-lw-pla-plane-part.md)

**Mod:** devam (parça hâlâ plakada) · **Yazıcı:** Bambu Lab P1S · **Sonuç:** başarılı

![Testin özeti](../../images/PlaneTest/PlanePart.gif)

## Ne oldu?

Bir RC uçağın burun kapağını (`Flightory's Talon1400` modelinin burun parçası) hafif PLA ile basıyordum ve filament sıkıştı. Baskı 180 katmanın 64'üne, yani yarısını biraz geçmiş bir noktaya gelmişti ve parça hâlâ plakaya sıkıca yapışıktı. Baştan başlamak, saatlerce süren baskıyı ve epey filamenti çöpe atmak demekti. Layer Rescue tam da bu durum için yapıldı.

|                      |                                                                  |
| -------------------- | ---------------------------------------------------------------- |
| Model                | RC uçak burun kapağı, havalandırma yarıklı kavisli kabuk, 180 katman |
| Filament             | Creality PLA Hyper Low Weight (LW-PLA)                           |
| Sıcaklıklar          | nozzle 230 °C, tabla 55 °C                                       |
| Plaka                | textured PEI                                                     |
| Nozzle               | 0,4 mm                                                           |
| Durduğu yer          | katman 64 / 180 (%53)                                            |
| Layer Rescue sürümü  | 0.2.2                                                            |

## Adım adım

### 1. Baskı duruyor

![İlk kısmın basılması](../../images/PlaneTest/base_print_plane.mp4)

İlk yarı normal şekilde basıldı. Sıkışmadan sonra işi Bambu Studio'nun **Device** sekmesinden durdurdum. (Yazıcının kendi ekranından durdurmak da aynı işi görür.) İlerleme çubuğunda `Layer: 64/180` yazıyor.

![Baskının durdurulması](../../images/PlaneTest/stop_printing.mp4)

Burada asıl önemli olan, yapmadığım şeyler: plakayı çıkarmadım, parçaya dokunmadım ve yazıcıyı kapatmadım. Yazıcı açık kaldığı için Z'nin nerede olduğunu hâlâ tam olarak biliyor ve bu da devam ettirmeyi olabilecek en kolay hale getiriyor.

Dilimlemeden önce parçaya iyice bakın ve gerçekten düzgün basılmış son katmanı bulun. Sıkışma başladığında son birkaç katman çoğu zaman incecik kalır ya da hiç basılmamıştır, yazıcı yine de onları basılmış sayar. Sayaca değil parçaya güvenin. Benim testimde sayaç 64'te durmuştu ve üst katman sağlam görünüyordu, bu yüzden düzgün basılan son katman olarak 64 girdim.

### 2. Layer Rescue'yu Bambu Studio projesine ekleyin (yalnızca bir kez)

![Post-processing script'inin eklenmesi](../../images/PlaneTest/add_layerrescue.mp4)

Bunu sadece bir kez yaparsınız:

1. Bambu Studio'yu **Advanced** moda alın (process preset'inin yanındaki anahtar).
2. Process ayarlarında **Others** sekmesini açın ve **Post-processing scripts** alanına kadar inin.
3. Layer Rescue'nun yolunu tırnak içinde yapıştırın, örneğin:

   ```text
   "C:\Users\<kullanıcı>\AppData\Local\Programs\LayerRescue\LayerRescue.exe"
   ```

Ben bunu kendi LW-PLA process preset'ime kaydettim, böylece ne zaman lazım olsa orada.

### 3. Aynı projeyi yeniden dilimleyin

Aynı projeyi hiçbir şeyini değiştirmeden yeniden dilimledim. Modeli, konumunu ya da ayarları değiştirmeyin: katman numaraları ve yükseklikleri plakada duran parçayla birebir uyuşmalı, yani iş tamamen aynı olmalı. Dilimleme bitince Studio post-processing script'ini çalıştırır ve Layer Rescue penceresi açılır.

### 4. Layer Rescue'da seçenekleri belirleyin

![Layer Rescue seçenekleri](../../images/PlaneTest/layerrescue_options.mp4)

Pencerede:

- **Düzgün basılan son katman:** 1. adımda seçtiğim katman.
- **Z modu:** _printer stayed powered on_ (0.3'te: "Hayır, hep açık kaldı"), çünkü yazıcı hiç kapanmadı.
- **X/Y'yi yeniden home et:** açık (Z hiçbir zaman home edilmez).
- **Onaylar:** yazıcının elektriği hiç kesilmedi ve parça hâlâ aynı plakaya sağlam yapışık.
- Sıcaklıkları boş bıraktım, böylece dosyadan okundular (230 / 55 °C).

Ardından **Create G-code**'a bastım.

> **0.3'te** aynı seçimler **Parça hâlâ plakada** sekmesinde numaralı adımlar halinde: "1. Baskı nerede durdu?", "2. Yazıcı kapatıldı ya da yeniden başlatıldı mı?" ve "3. Güvenlik kontrolleri". Pencere ayrıca siz yazarken baskının hangi katmandan ve hangi Z'den devam edeceğini gösteriyor.

### 5. Önizlemeyi kontrol edin ve gönderin

Bambu Studio önizlemesinde iş artık girdiğim katmandan bir sonrakiyle başlıyor; altındaki hiçbir şey basılmıyor. Önizleme tabladan başlıyorsa bir şeyler yanlış gitmiştir, göndermeyin.

![Kalan kısmın basılması](../../images/PlaneTest/printing_rest.mp4)

Gönderdikten sonra yazıcı:

1. ısınır,
2. nozzle'ı biraz kaldırır ve yalnızca X ve Y'yi home eder,
3. arkadaki atık kanalında purge yapar,
4. parçanın üstüne gelir, son katmana iner ve oradan devam eder.

Yine de ilk birkaç hareket boyunca yazıcının yanında durun. Bir şey ters görünürse hemen durdurabilirsiniz.

### 6. Sonuç

![Sonuç](../../images/PlaneTest/final_result.mp4)

Parça plakadan tek parça halinde çıktı ve üst yarı, alt yarının durduğu yerden tam olarak devam etti.

Baskının yeniden başladığı yerde görünür bir katman izi var. Bu, katman tam doğru seçildiğinde bile oluyor; yani görünmez bir birleşim beklemeyin.

Henüz düzgün dayanıklılık testleri yapmadım ama doğru katmanla birleşim yeri sağlam duruyor: parçayı elime aldığımda orada yırtılma, kopma ya da ezilme olmuyor. Ne kadar sağlam olacağı yine de modelin şekline ve filamente bağlı.

## Çıkarımlar

- Yazıcı açık kaldıysa bu en kolay durum: Z hizalaması yok, elle yapılacak adım yok, sadece doğru katmanı seçin.
- Katmanı seçmek kritik karar ve sadece 2–3 katmanlık bir hata bile kendini belli ediyor:
  - **Fazla yüksek** (hiç basılmamış bir katmanı girerseniz): nozzle parçanın üstünde başlar ve yeni katmanlar parçaya zar zor değer. Birleşim çizgisi çok belirginleşir ve parça oradan kırılmaya çok daha yatkın olur.
  - **Fazla düşük** (gerçek tepenin altındaki bir katmanı girerseniz): nozzle parçaya girer ve onu plakadan kolayca sökebilir.

  Emin değilseniz parçanın tepesini Studio önizlemesindeki katman görünümüyle karşılaştırın.
- LW-PLA yüksek sıcaklıkta köpürerek genleşir, bu yüzden normal PLA'dan daha fazla akıntı yapar. Devam etmeden önceki purge burada önemli.
