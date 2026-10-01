# Test 5: Beş örümcek, ikisi yolda kayboldu

[English](05-multi-object-spiders.md)

**Mod:** birden fazla objeyle devam (parçalar hâlâ plakada) · **Yazıcı:** Bambu Lab P1S · **Sonuç:** başarılı

![Testin özeti](../../images/SpiderTest/Spiders.gif)

## Ne oldu?

Küçük parçalarla dolu bir plakanın kendine has bir arıza şekli vardır: bir ya da ikisi yarıda kopar, nozzle onları ortalıkta sürükler ve plakanın geri kalanı da tehlikeye girer. Genelde yapılan, her şeyi iptal etmektir. Ben hâlâ sağlam olan parçaları kurtarabilir miyim, onu görmek istedim.

Bunun için beş küçük, destekli örümceği aynı anda bastım. Yarı yolda ikisini bilerek kazıyıcıyla plakadan düşürdüm ve kimse fark etmemiş gibi baskının bir süre devam etmesine izin verdim. Sonra baskıyı durdurdum ve Layer Rescue ile yalnızca plakada kalan üç örümceği bitirdim.

|                      |                                          |
| -------------------- | ---------------------------------------- |
| Model                | 5 küçük destekli örümcek, 89 katman      |
| Plaka                | textured PEI                             |
| Son düzgün katman    | 44 / 89                                  |
| Layer Rescue sürümü  | 0.2.2                                    |

## Adım adım

### 1. Plakayı basın ve iki örümceği kaybedin

https://github.com/user-attachments/assets/92b0d53f-ab6a-4d06-9af6-b55bd06e5d24

İlk yarı normal şekilde basıldı. Sonra yazıcı çalışmaya devam ederken örümceklerden ikisini kazıyıcıyla ittim. Bir süre çalışmasına izin verdim; kimse fark etmeseydi olacağı gibi o ikisini havaya basmaya devam etti.

### 2. Baskıyı durdurun ve temizleyin

https://github.com/user-attachments/assets/e60b3fb8-a746-496c-bbaf-7d701ea37f77

Baskıyı şanslı bir anda durdurdum: kalan üç örümcek 44. katmanı yeni bitirmişti ve yazıcı, zaten yerinde olmayan iki örümceğin 44. katmanını basıyordu. Yani gerçek parçalar tamamlanmış bir katmanla bitmişti.

Sonra kopan örümcekleri ve onlardan geriye kalan ipleri temizledim. Kalan üç örümcek yerinde duruyor: onları oynatmayın ve plakayı çıkarmayın. Yazıcı açık kalıyor, yani Z'nin nerede olduğunu hâlâ biliyor.

### 3. Kaybolan örümcekleri Bambu Studio'da silin

https://github.com/user-attachments/assets/9a47acf3-27bc-4e04-961b-f78b08442f6a

Birden fazla objeli durumu çalıştıran adım bu. Layer Rescue G-code'da ne varsa ona devam ediyor; beş örümcek de projede kalsaydı yazıcı, eksik iki örümceği 45. katmandan itibaren havaya yeniden basmaya çalışırdı.

Bu yüzden Bambu Studio'da artık plakada olmayan iki örümceği sildim, diğer üçünü olduğu yerde bıraktım. **Arrange**'a basmayın ve hiçbir şeyi taşımayın: kalan objeler plakada aynı yerlerde durmalı, yoksa nozzle zaten basılmış parçalarla hizalanmaz.

### 4. Dilimleyin ve Layer Rescue'da seçenekleri belirleyin

https://github.com/user-attachments/assets/b78bde26-abee-437b-a84b-0cbfb7c96782

Ardından düzenlenmiş projeyi dilimledim. Layer Rescue penceresinde:

- **Düzgün basılan son katman:** 44.
- **Z modu:** _printer stayed powered on_ (0.3'te: "Hayır, hep açık kaldı").
- **X/Y'yi yeniden home et:** açık (Z hiçbir zaman home edilmez).
- **Onaylar:** yazıcının elektriği hiç kesilmedi ve parçalar hâlâ aynı plakaya sağlam yapışık.

Önizlemede yalnızca kalan üç örümcek vardı ve 45. katmandan devam ediyordu.

### 5. Kalanını basın

https://github.com/user-attachments/assets/ecd8bcdf-a435-4bbf-84e4-81fa062b4a40

Yazıcı X ve Y'yi home ediyor, purge yapıyor ve üç örümceğe birden, destekleri dahil, 45. katmandan sona kadar devam ediyor.

### 6. Sonuç

https://github.com/user-attachments/assets/32290bc5-ad5a-4b27-9729-b00bc73d565b

Üç örümcek de destekleriyle birlikte düzgünce tamamlandı ve plakadan normal bir baskı gibi çıktı. Beşini birden çöpe atmak yerine iki parça kayıp, üç parça kurtarıldı.

Sürpriz, birleşim yerinde oldu: ortada bir iz yok. Diğer bütün testlerde baskının yeniden başladığı yerde görünür bir katman izi kalmıştı, ama burada 44'ten 45'e geçiş tertemiz ve baskının nerede durduğu anlaşılmıyor. Bence sebebi 2. adımdaki zamanlama: kalan örümceklerin üst katmanı tamamen bitmişti, yani yazıcı yarım basılmış değil tamamlanmış bir yüzeyin üstüne devam etti. Tek bir temiz sonuç bunun her seferinde olacağını söylemeye yetmez ama iyi bir ipucu.

Henüz düzgün dayanıklılık testleri yapmadım ama doğru katmanla, parçaları elime aldığımda birleşim yerinde yırtılma, kopma ya da ezilme olmuyor. Ne kadar sağlam olacakları yine de modelin şekline ve filamente bağlı.

## Çıkarımlar

- Plakada birden fazla obje varsa, yeniden dilimlemeden önce kaybolanları silin. Geri kalan her şeyi olduğu gibi bırakın: Arrange yok, taşımak yok, döndürmek yok.
- Başka hiçbir ayarı da değiştirmeyin. Kalan objelerin katmanları plakada duranlarla birebir uyuşmalı.
- Ne zaman durduracağınızı seçme şansınız varsa, saklamak istediğiniz parçalarda bir katman bittikten hemen sonra durdurun. Bu testte bu, görünmeyen bir birleşim sağladı.
- Kopan bir parça nozzle tarafından sürüklendiyse, devam etmeden önce kalan parçaların tepesinde ip ya da topak olup olmadığına bakın. Nozzle önce onların üstüne iner.
- Bu, [uçak testindekiyle](01-lw-pla-plane-part.tr.md) aynı devam ettirme; dolayısıyla katman numarası için de aynı kural geçerli. Sadece 2–3 katmanlık bir hata bile belli oluyor:
  - **Fazla yüksek** (hiç basılmamış bir katmanı girerseniz): nozzle parçaların üstünde başlar ve yeni katmanlar onlara zar zor değer. Birleşim yeri çok belirginleşir ve parçalar oradan kırılmaya çok daha yatkın olur.
  - **Fazla düşük** (gerçek tepenin altındaki bir katmanı girerseniz): nozzle parçalara girer ve onları plakadan kolayca sökebilir. Bunun gibi küçük parçalarda bu çabucak olur.
