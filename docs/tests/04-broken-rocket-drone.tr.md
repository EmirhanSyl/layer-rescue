# Test 4: Kırılan roket drone burnu, destekleriyle birlikte yeniden basıldı

[English](04-broken-rocket-drone.md)

**Mod:** destekleri yeniden basmalı yerleştirme (beta) · **Yazıcı:** Bambu Lab P1S · **Sonuç:** başarılı

![Testin özeti](../../images/RocketTest/Rocket.gif)

## Ne oldu?

Bu sefer gerçek hayata daha yakın bir şey denemek istedim: basılıp monte edildikten sonra kırılan işlevsel bir parça. Bunun için gerçek bir roket drone modeli bulup normal şekilde bastım ve monte ettim. Sonra gövdenin üst kısmını, burun üstü bir çarpışmada kırılacağı gibi bilerek kırdım.

Gövde içi boş bir tüp ve burnu, tabladan başlayıp tüpün içinden yükselen ağaç desteklerle basılmıştı. Bu testi [Benchy'den](03-detached-benchy.tr.md) farklı kılan da bu: burnu yeniden basabilmek için o desteklerin de tabladan başlayarak yeniden basılması gerekiyor, hem de plakaya geri koyacağım parçanın _içinde_.

|                      |                                                  |
| -------------------- | ------------------------------------------------ |
| Model                | roket drone gövdesi (burun konili içi boş tüp)   |
| Filament             | SUNLU Silk PLA+                                  |
| Parça yüksekliği     | 52 mm (zımparadan sonra ölçüldü)                 |
| Duvar yüksekliği     | 15 mm (önerilen)                                 |
| Boşluk               | 0,20 mm                                          |
| Devam ettiği yer     | katman 261 / 360                                 |
| Layer Rescue sürümü  | 0.3.0                                            |

## Adım adım

### 1. Kırın, sonra düz zımparalayın

![Kırma ve zımparalama](../../images/RocketTest/breaking_sanding.mp4)

Basılmış gövdeyi drone'dan söktüm ve üstten sert bir darbeyle tepesini kırdım. Kırık yer pürüzlü ve düzensizdi, bu yüzden bütün kenar aynı yüksekliğe gelene kadar zımpara üstünde düzledim, sonra kumpasla ölçtüm: 52 mm.

Burada düz bir kenar önemli. İlk yeni katman doğrudan onun üstüne basılıyor; bir basamak ya da tırtıklı bir kenar birleşim yerinde boşluk olarak kendini gösterir.

### 2. Tam modeli dilimleyin ve yerleştirme modunu ayarlayın

![Layer Rescue seçenekleri](../../images/RocketTest/layerrescue_options_rocket.mp4)

Bambu Studio'da gövdenin plakasını, burun ve destekler dahil, eksiksiz dilimledim. Layer Rescue penceresinde **Parça ayrıldı / bitmiş parçanın üstüne bas** sekmesini açtım:

- **Parça yüksekliği:** 52 mm. Modelde 260. katman tam 52 mm'de olduğu için kapatılması gereken bir fark yoktu.
- **Duvar yüksekliği:** boş bıraktım, önerilen 15 mm kullanıldı.
- **Parça ile duvar arası boşluk:** 0,20 mm (**Gelişmiş ayarları göster** altında).

**Önizle**'ye bastıktan sonra sonuç kısmında şunlar göründü:

- duvar: 1–75. katmanlar, 15 mm'ye kadar,
- bir duraklama, ardından 360 katmanın 261.'sinden, 0,20 mm'lik bir ilk katmanla devam,
- **destekler duraklamadan önce 260. katmana kadar yeniden basılıyor**: üstten görünümde, tüpün tam ortasındaki yeşil alan.

İki uyarı vardı, ikisi de beklenen şeyler. Biri, parçanın yeni desteklerin üzerinden kayabilmesi için eski desteklerden kalanları temizlemenizi hatırlatıyor. Diğeri, parçanın döndürüldüğünde aynı göründüğünü (yuvarlak olduğu için) ve duvarın yönünü sabitleyemeyeceğini, yani parçayı Bambu Studio'daki yönüyle oturtmanız gerektiğini söylüyor.

Sonra güvenlik kontrolünü işaretleyip G-code'u oluşturdum.

### 3. Yazıcı duvarı ve destekleri basıyor

![Duvarın ve desteklerin basılması](../../images/RocketTest/printing_supports.mp4)

En çok hoşuma giden kısım bu. Yazıcı duraklamadan önce yuvarlak tutucu duvarı ve onun içinde ağaç desteklerin alt kısmını, parça yüksekliğine kadar basıyor.

Layer Rescue, parçanın yoluna çıkmadığı sürece **seçilen yüksekliğin üstüne uzanan bütün destekleri** tabladan başlayarak yeniden kuruyor. Tüpün duvarlarının geleceği yere denk gelen destekler dışarıda bırakılıyor, çünkü parçanın onların üzerinden aşağı kayması gerekiyor. Yalnızca kırık yerin altında kalan bir şeyi taşıyan destekler de basılmıyor, çünkü o kısım zaten var. Böylece yeni üst kısmın ihtiyaç duyduğu destekler tam olarak basılıyor, eski parçayı engelleyen hiçbir şey basılmıyor.

### 4. Kırık parçayı oturtun

![Kırık parçanın yerleştirilmesi](../../images/RocketTest/placing_part.mp4)

Eski desteklerin kalıntılarını tüpün içinden temizledim, sonra parçayı yeni desteklerin üzerinden kaydırarak duvara, Bambu Studio'daki yönüyle oturttum. 0,20 mm boşlukla zorlamadan girdi ve bu sefer yapıştırmaya gerek kalmadı. Ardından **Resume**'a bastım.

### 5. Yazıcı kalanını basıyor

![Kalan kısmın basılması](../../images/RocketTest/printing_rest_rocket.mp4)

Yazıcı ısınıyor, purge yapıyor ve burnu, içerideki yeniden basılmış desteklerin taşıdığı şekilde gövdenin üstüne basıyor.

### 6. Sonuç

![Temizlik ve sonuç](../../images/RocketTest/final_result_rocket.mp4)

Baskıdan sonra parçayı duvardan çıkardım, içindeki destekleri temizledim ve gövdeyi drone'a geri taktım.

Yeni burun, eski kırığın üstüne sağlam bir şekilde oturdu. Birleşim yerinde görünür bir katman izi var; yükseklik tam doğru olduğunda bile bu normal. Henüz düzgün dayanıklılık testleri yapmadım ama parçayı elime aldığımda birleşim yerinde yırtılma, kopma ya da ezilme olmuyor. Ne kadar sağlam olacağı yine de modelin şekline ve filamente bağlı.

Parçayı yazıcıdan çıktığı haliyle bıraktım, yapıştırıcı kullanmadım. Yine de bunun gibi çarpışmada darbe alan bir parçada birleşim yerine birkaç damla japon yapıştırıcısı sürerdim. Hiçbir maliyeti yok ve tamiri çok daha güvenli hale getiriyor.

## Çıkarımlar

- Yerleştirme modu, geri koyduğunuz parçanın içinde gizli kalsalar bile tabladan başlayan destekleri yeniden kurabiliyor. Bu da bunun gibi içi boş parçaları tamir etmeyi mümkün kılıyor.
- Parçayı oturtmadan önce eski destekleri içinden temizleyin, yoksa yenilerinin üzerinden kaymaz.
- Yuvarlak bir parçada duvar sadece yana kaymayı engeller. Resume'a basmadan önce parçanın Bambu Studio'daki yönüne baktığından emin olun.
- Bu parça için 0,20 mm boşluk iyi ve sıkı bir oturma sağladı.
- Yük ya da darbe alan işlevsel parçalarda, baskıdan sonra birleşim yerine birkaç damla japon yapıştırıcısı sürmeniz tavsiye edilir.
- Ölçülen parça yüksekliği, diğer testlerdeki katman numarasıyla aynı rolü oynuyor ve sadece 2–3 katmanlık (0,2 mm katmanlarda 0,4–0,6 mm) bir hata bile belli oluyor:
  - **Fazla yüksek:** ilk yeni katmanlar parçanın üstünde basılır ve ona zar zor değer. Birleşim yeri çok belirginleşir ve kırılmaya çok daha yatkın olur.
  - **Fazla düşük:** nozzle parçaya bastırır ve onu duvardan dışarı itebilir.
