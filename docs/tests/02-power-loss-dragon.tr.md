# Test 2: Elektrik kesintisinden sonra ejderha

[English](02-power-loss-dragon.md)

**Mod:** devam (parça hâlâ plakada), yazıcı yeniden başlatıldı · **Yazıcı:** Bambu Lab P1S · **Sonuç:** başarılı, katman seçimiyle ilgili bir dersle birlikte

![Testin özeti](../../images/DragonTest/Dragon.gif)

## Ne oldu?

Bu test, en çok korkulan durumu ele alıyor: baskının ortasında elektrik kesiliyor. Bunu, 80 mm'lik ağaç destekli bir ejderha basılırken yazıcıyı güç düğmesinden kapatarak canlandırdım. Yazıcı yeniden açıldığında Z'nin nerede olduğu hakkında hiçbir fikri yok, bu yüzden Layer Rescue [uçak testindeki](01-lw-pla-plane-part.tr.md) gibi yazıcının kendi Z koordinatına güvenemez. Bunun yerine nozzle'ı parçanın üstüne elle yerleştiriyorum ve iş oradan devam ediyor.

|                      |                                                                          |
| -------------------- | ------------------------------------------------------------------------ |
| Model                | ejderha, 80 mm yüksek, bol ince detaylı, ağaç destekli (400 katman)      |
| Filament             | SUNLU Silk PLA+                                                          |
| Process              | 0.20 mm Standard                                                         |
| Plaka                | textured PEI                                                             |
| Nozzle               | 0,4 mm                                                                   |
| Son düzgün katman    | 265 girildi, gerçeği 268'di ([sonuca](#6-sonuç) bakın)                   |
| Layer Rescue sürümü  | 0.2.2                                                                    |

## Adım adım

### 1. İlk kısım basılıyor, sonra elektrik kesiliyor

https://github.com/user-attachments/assets/e9440fcf-7a82-4344-b5a7-e8cd98d5a446

Baskı, yüksekliğin yaklaşık üçte ikisine kadar normal ilerledi. Sonra yazıcıyı arkasındaki düğmeden kapattım ve tekrar açmadan önce biraz bekledim.

https://github.com/user-attachments/assets/f6343c49-2493-4312-bed7-0b3e2657b8eb

Bu noktadan sonra parçaya ve plakaya dokunmayın. Parça, basıldığı yerde aynen durmalı.

### 2. Tablayı yeniden ısıtın

https://github.com/user-attachments/assets/ac19b8f3-ae5d-44ca-8377-af8a1c3ca9ae

Yeniden başlatmadan sonra hiçbir şey ısınmıyor. Yazıcının ekranından tablayı baskı sıcaklığına (55 °C) geri getirdim; böylece parça plakaya yapışık kalıyor ve basıldığı boyutta duruyor. Nozzle'ı da 140 °C'ye ayarladım, ama bunun özel bir sebebi yok ve gerekli değil.

### 3. Nozzle'ı parçanın üstüne elle indirin

https://github.com/user-attachments/assets/8f918724-6462-474f-b3f4-d2d6adb6ccf3

Bu testin en önemli adımı bu. Yazıcının ekranında eksen kontrollerini açın ve Z'yi, temiz nozzle son düzgün katmanın tepesine **hafifçe değene** kadar hareket ettirin.

> **Home etmeyi asla kabul etmeyin.** Yeniden başlatmadan sonra Z'yi oynatmaya çalıştığınızda yazıcı _"Axis z has not been homed! Press OK to home."_ uyarısı verir. OK'e basmayın. P1S, Z'yi home ederken sıfırı tablanın kendisiyle bulur; parça hâlâ plakadayken bu, parçayı doğrudan nozzle'a sürer. Mesajdan geri çıkın ve Z'yi elle oynatın.

Sona doğru küçük adımlarla ilerleyin. Nozzle, son katmanın düz bir bölgesinde durmalı, bir desteğin ya da kenarın üstünde değil; yüzeye sadece hafifçe değmeli, içine bastırmamalı.

Ben bunu gözle ayarladım: Z'yi küçük adımlarla indirdim ve nozzle'ın üst yüzeye değdiğini gördüğüm anda durdum.

Nozzle yerine oturduktan sonra Z'yi bir daha oynatmayın. Bundan sonra Layer Rescue bütün Z hareketlerini bu konuma göre yapar.

### 4. Dilimleyin ve Layer Rescue'da seçenekleri belirleyin

https://github.com/user-attachments/assets/199ced9a-5a05-4514-81a5-f988cc77827a

Aynı projeyi yeniden dilimledim (post-processing script'i zaten ayarlıydı, [uçak testinin](01-lw-pla-plane-part.tr.md) 2. adımına bakın). Layer Rescue penceresinde:

- **Düzgün basılan son katman:** 265. Sonradan anlaşıldı ki bu yanlışmış, ayrıntısı sonuç kısmında.
- **Z modu:** _printer was restarted (manual Z reference)_ (0.3'te: "Evet, kapatıldı ya da yeniden başlatıldı").
- **X/Y'yi yeniden home et:** açık ve kilitli, çünkü yeniden başlatmadan sonra X ve Y'nin de home edilmesi gerekiyor. Z hiçbir zaman home edilmez.
- **Onaylar:** işi başlatmadan önce temiz nozzle'ı son düzgün katmana hizalayacağım (3. adımda zaten yapıldı) ve parça hâlâ plakaya sağlam yapışık.

Dosyada `Layers: 1–396 / 400` yazıyor. Destekler kendi katman yüksekliklerini kullandığında bu normal: Bambu bu ekstra destek katmanlarını toplama ekliyor, Layer Rescue de bunu hesaba katıyor.

> **0.3'te** yeniden başlatma modu yalnızca kendisine ait kontrolleri gösteriyor ve pencere, siz yazarken baskının hangi katmandan ve hangi Z'den devam edeceğini gösteriyor.

### 5. Önizlemeyi kontrol edin ve gönderin

https://github.com/user-attachments/assets/98190da3-f06d-4a18-a94c-6f221534b44c

Önizlemede yalnızca 265. katmanın üstü kalıyor: gövdenin geri kalanı, kanatlar ve kafa. Hiçbir şey tabladan başlamıyor.

https://github.com/user-attachments/assets/235606a0-eecc-4e89-a785-0b0489d10e19

Gönderdikten sonra yazıcı ısınıyor, nozzle'ı bıraktığım yerden 2 mm kaldırıyor, yalnızca X ve Y'yi home ediyor, purge yapıyor, parçanın üstüne geri geliyor ve 266. katmandan devam ediyor. Nozzle parçanın üstüne elle yerleştirildiği için ilk katmanları yakından izledim.

### 6. Sonuç

https://github.com/user-attachments/assets/685ae02d-1f09-4bd6-936d-02aaa284354c

Ejderha kanatları ve kafasıyla birlikte tamamlandı, ama kafada ve kanatlarda birleşim yerinin çevresinde beklediğimden fazla iz ve boşluk vardı. Kanatlardan biri birleşim yerinden kırıldı ve geri yapıştırmak zorunda kaldım.

Sonradan kayıtları incelediğimde sebebini buldum: gerçekten basılmış son katman 265 değil **268**'di. Baskıyı 3 katman aşağıdan yeniden başlatmıştım.

Burada aslında baskıyı yeniden başlatma modu kurtardı. Bu modda Z, katman numarasından değil, nozzle'ı elle koyduğum yerden geliyor. Layer Rescue değdiğim yüzeyi (268. katmanın gerçek tepesini) 265. katmanın tepesi olarak kabul etti; bu yüzden nozzle parçaya çarpmadı, destekleri de kırmadı, oradan devam etti. Ama 266–268 arasındaki katmanları gerçek 268'in üstüne ikinci kez bastı. Üst yarının tamamı olması gerekenden yaklaşık 0,6 mm yukarıda duruyor ve modelin katmandan katmana hızla değiştiği yerlerde (ince kanat yapısı, kafa) yeni katmanlar eskileriyle üst üste oturmuyor. Boşluklar ve zayıf birleşim yeri buradan geliyor.

Yani program kendisine söyleneni tam olarak yaptı ve birleşim yerinden sonraki her şey doğru basıldı; bu yüzden bu testi başarılı sayıyorum. Zayıf birleşim yerinin sebebi algoritma değil, girdiğim katman.

Bunun dışında her zamanki durum geçerli: baskının yeniden başladığı yerde, katman tam doğru seçilse bile, her zaman görünür bir katman izi kalıyor. Henüz düzgün dayanıklılık testleri yapmadım ama katman doğru olduğunda parçayı elime aldığımda birleşim yerinde yırtılma, kopma ya da ezilme olmuyor. Ne kadar sağlam olacağı yine de modelin şekline ve filamente bağlı.

## Çıkarımlar

- Elektrik kesintisinden sonra sonuç, nozzle'ı parçanın üstüne sizin yerleştirmenize bağlı. Acele etmeyin: üstteki her şey o noktaya göre basılıyor.
- Parça plakadayken yazıcının Z'yi home etmesine asla izin vermeyin.
- Her şeyden önce tablayı yeniden ısıtın, böylece siz uğraşırken parça yerinden kopmaz.
- Son düzgün katmanı girmeden önce dikkatle kontrol edin; elinizde kayıt ya da timelapse varsa kullanın. Sadece 2–3 katmanlık bir hata bile belli oluyor, ama yeniden başlatma modunda [uçak testinden](01-lw-pla-plane-part.tr.md) farklı şekilde, çünkü Z katman numarasından değil sizin nozzle'ınızdan geliyor:
  - **Fazla düşük** (bu test): girdiğiniz numara ile gerçek tepe arasındaki katmanlar iki kez basılır. Hiçbir şey çarpmaz, ama üst yarı olması gerekenden yukarıda kalır ve detaylar birleşim yerinde üst üste oturmaz; sonuç gözle görülür derecede kötü ve zayıf olur.
  - **Fazla yüksek**: o katmanlar atlanır. Nozzle yine tam parçanın üstünden başlar ama şekil sıçrar; birleşim yerinde bir basamak oluşur ve bağlantı zayıflar.
- 3. adımdaki nozzle konumu işin diğer yarısı. Fazla yüksekte kalırsa ilk yeni katman parçaya zar zor değer ve birleşim zayıf olur; parçaya bastırılırsa nozzle parçayı kazıyabilir ya da plakadan sökebilir.
