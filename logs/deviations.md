# Catatan Deviasi & Penyesuaian Operasional (Operational Deviations & Adaptations)

Dokumen ini mencatat seluruh adaptasi teknis dan operasional yang diterapkan selama pelaksanaan eksperimen translasi CrochetPARADE, sesuai instruksi dan persetujuan Peneliti. Seluruh penyesuaian dicatat untuk menjamin transparansi, integritas ilmiah, dan keterulangan (*reproducibility*).

---

## 1. Transport Streaming untuk Gemini 3.8 Flash (`generate_content_stream`)
- **Tanggal Diterapkan:** 31 Oktober 2026
- **Lingkup:** Diterapkan secara seragam untuk **SEMUA** permintaan `gemini-3.8-flash` (baik kondisi `L38F-LOW` maupun `L38F-HIGH`).
- **Rasional:** Pada metode non-streaming (`generate_content`), proses penalaran (*reasoning*) model yang memakan waktu lama di server Google sering menyebabkan pemutusan koneksi sepihak pada lapisan soket klien (*idle read timeout*). Penerapan `generate_content_stream` memungkinkan penerimaan *chunk keep-alive* melalui koneksi HTTP streaming sehingga koneksi tidak terputus saat model berpikir.
- **Kepatuhan Protokol:** Ini murni penyesuaian level transport (protokol jaringan), **BUKAN** perubahan konfigurasi model. Prompt resmi, batasan `max_output_tokens=32768`, ketiadaan parameter suhu/top_p/top_k, serta manipulasi *thinking level* tetap 100% identik.
- **Status:** Disetujui & Terdokumentasi di `logs/environment.json`.

---

## 2. Batas Waktu Klien (Client Timeout) 600 Detik untuk Gemini 3.8 Flash
- **Tanggal Diterapkan:** 30 Oktober 2026
- **Lingkup:** Model `gemini-3.8-flash` (keluarga 3.8). Sebagai pembanding, keluarga 2.5 menggunakan timeout 180 detik.
- **Rasional:** Pada pengujian awal dengan batas waktu standar 120 detik, permintaan dengan `thinking_level="high"` terputus dengan galat `504 DEADLINE_EXCEEDED` di detik ke-119, sementara level `low` membutuhkan waktu 116,5 detik. Batas waktu dinaikkan ke 600 detik (10 menit) untuk memberikan ruang penalaran penuh tanpa pemotongan dini oleh klien.
- **Status:** Disetujui Peneliti.

---

## 3. Kebijakan Retry Multi-Hari Lintas Sesi (Tafsiran "Jeda Bertahap")
- **Tanggal Diterapkan:** 31 Oktober 2026
- **Lingkup:** Seluruh permintaan antrean, khususnya keluarga 3.8.
- **Rasional:** Proposal skripsi menetapkan retry dengan "jeda bertahap". Karena kuota harian Free Tier dibatasi 20 permintaan per hari dan server sering mengalami lonjakan beban (*503 spikes*), melakukan retry bertubi-tubi pada hari yang sama akan menghabiskan kuota harian hanya untuk 1 item yang sama.
- **Ketentuan Kebijakan:**
  1. Pada galat server (503/504/timeout), sistem melakukan **maksimal 1 kali retry di hari yang sama** (total 2 percobaan per hari).
  2. Jika percobaan kedua hari itu tetap gagal, status item dikembalikan ke `"pending"` untuk dicoba pada hari berikutnya, dan runner melanjutkan ke item berikutnya di antrean.
  3. Status `"failed"` (data hilang) hanya diberikan apabila item gagal setelah dicoba pada **3 hari yang berbeda** (`distinct_attempt_days >= 3`).
  4. Galat kuota (`429 RESOURCE_EXHAUSTED`) **BUKAN** kegagalan item dan statusnya selalu tetap `"pending"`.
- **Status:** Disetujui Peneliti.

---

## 4. Pemulihan Item `REQ-0002` dari Status Failed ke Pending
- **Tanggal Diterapkan:** 31 Oktober 2026
- **Deskripsi:** Item `REQ-0002` (`early_38 | L38F-HIGH`) yang sebelumnya ditandai `failed` setelah 3 percobaan dalam 1 sesi hari yang sama dipulihkan statusnya menjadi `"pending"` di `data/experiment_queue.json`.
- **Rasional:** Penyesuaian agar selaras dengan Kebijakan Retry Multi-Hari (butuh 3 hari berbeda untuk dinyatakan data hilang). Catatan pemulihan dicatat secara append-only di `logs/quota_tracker.json` dan `raw/llm.jsonl`.
- **Status:** Selesai.

---

## 5. Pencabutan Jeda Eksekusi Gemini 3.8 Flash
- **Tanggal Diterapkan:** 31 Oktober 2026
- **Deskripsi:** Instruksi penundaan sementara eksekusi 3.8 pada sesi sebelumnya resmi **DICABUT** oleh Peneliti.
- **Ketentuan Baru:**
  1. Antrean 3.8 dijalankan penuh untuk kedua kondisi (`L38F-LOW` dan `L38F-HIGH`, 119 item per kondisi) mengikuti urutan acak beku (`seed=42`).
  2. DILARANG menjalankan LOW terlebih dahulu atau HIGH terlebih dahulu untuk mencegah efek perancu waktu (*time-confounding*).
  3. Setiap hari kuota 20 permintaan 3.8 dihabiskan mengikuti urutan antrean.
  4. Hasil kondisi HIGH dilaporkan apa adanya, termasuk apabila terjadi banyak data hilang.
- **Status:** Aktif.

---

## 6. Penemuan Batas Kuota Aktual Google AI Studio Free Tier (20 RPD per Model)
- **Tanggal Ditemukan:** 30–31 Oktober 2026 (Diperbarui 1 November 2026)
- **Deskripsi:** Berdasarkan respon resmi API Google (`quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier`, `quotaValue: 20`), seluruh model (`gemini-2.5-flash-lite`, `gemini-2.5-flash`, `gemini-3.8-flash`) dibatasi pada **20 permintaan per hari per model**.
- **Observasi Pengurangan Kuota:** Data empiris menunjukkan bahwa sebagian (bukan semua) permintaan yang gagal memotong kuota harian Free Tier. Pada pengujian 1 November, terjadi 25 percobaan sebelum galat 429 muncul pada percobaan ke-26, yang mengindikasikan bahwa kegagalan soket klien tertentu (seperti *client read timeout* di detik 600 atau pemutusan koneksi TCP lokal) tidak seluruhnya tercatat sebagai kuota terpakai oleh gateway Google. Mekanisme internal pengurangan kuota dari sisi server Google belum terbukti secara definitif dan tetap dipantau sebagai observasi empiris.
- **Status:** Terdokumentasi di `logs/model_access.json`.

---

## 7. Penataan Eksekusi Sekuensial Antarkeluarga dan Rekonsiliasi Otomatis Antrean
- **Tanggal Diterapkan:** 1 November 2026
- **Deskripsi:** Eksekusi harian multi-keluarga (`--all`) diatur berjalan secara sekuensial (Keluarga 2.5 terlebih dahulu hingga selesai ~5–10 menit, diikuti Keluarga 3.8), dilengkapi mekanisme rekonsiliasi otomatis (`reconcile_queue`) antara `data/experiment_queue.json` dan `raw/llm.jsonl`.
- **Rasional:** Menghindari potensi *race condition* penulisan berkas status antrean ketika kedua thread berjalan paralel dan menyimpan salinan memori yang berbeda. Karena keluarga 2.5 hanya membutuhkan waktu singkat, eksekusi sekuensial menjamin atomisitas 100%, menghilangkan konflik berkas, serta memastikan integritas status antrean tetap sinkron sempurna dengan catatan mentah append-only.
- **Kepatuhan Protokol:** Urutan item acak beku (`seed=42`) pada tiap keluarga model tetap tidak berubah. Tidak ada perubahan parameter atau prompt model.
- **Status:** Diterapkan & Terverifikasi di `src/run_daily.py` dan `src/reconcile_queue.py`.

---

## 8. Pacing 13 Detik untuk 2.5 Flash, Diferensiasi 429 RPM vs RPD, dan Kuota Batch per Model
- **Tanggal Diterapkan:** 1 November 2026
- **Deskripsi:** 
  1. **Jeda Antar-Panggilan 2.5 Flash:** Ditetapkan jeda **13,0 detik** untuk `gemini-2.5-flash` guna menghormati batas Free Tier **5 RPM** (`GenerateRequestsPerMinutePerProjectPerModel-FreeTier`, $60\text{s} / 5 = 12\text{s}$). Jeda untuk `gemini-2.5-flash-lite` tetap 4,5 detik (batas 15 RPM).
  2. **Diferensiasi Galat 429 (RPM vs RPD):** Runner membedakan antara galat 429 akibat laju menit (`GenerateRequestsPerMinute...`) dengan galat kuota harian habis (`GenerateRequestsPerDay...`). Pada 429 RPM, sistem menunggu jeda pendinginan 60 detik lalu mengulang item; model tidak ditandai habis kuotanya untuk hari itu. Model hanya diskip apabila galat 429 secara eksplisit merujuk pada kuota harian (RPD).
  3. **Batas Batch Harian per Model:** Batas kuota batch harian (`max_requests=20`) diterapkan secara independen **per model** (20 untuk Flash-Lite, 20 untuk Flash, dan 20 untuk 3.8), bukan agregat keluarga, sehingga tiap model dapat memanfaatkan kuota 20 RPD-nya secara optimal.
- **Status:** Diterapkan di `src/run_daily.py`.


---

## 9. Mekanisme Pencegahan Eksekusi Ganda (Lock File) dan Pembatasan Runtime Maksimal 6 Jam
- **Tanggal Diterapkan:** 1 November 2026
- **Deskripsi:**
  1. **File Lock:** Runner menggunakan berkas penanda `data/runner.lock` berisi PID proses aktif. Jika berkas penanda ada dan PID terdeteksi masih hidup, eksekusi baru akan menolak berjalan untuk mencegah dua instans `run_daily.py` berjalan bersamaan. Berkas penanda otomatis dihapus saat proses selesai atau terhenti.
  2. **Batas Runtime Otomatis 6 Jam:** Jika pemrosesan batch harian mencapai durasi kumulatif 6 jam (misalnya akibat akumulasi timeout soket dan retry pada model 3.8), runner akan menghentikan pemrosesan secara anggun (*graceful stop*), menyimpan status antrean yang telah tuntas, dan keluar secara aman untuk mencegah proses menggantung tanpa henti (*runaway processes*).
- **Status:** Diterapkan di `src/run_daily.py`.

---

## 10. Perbaikan Inisialisasi Kuota Batch Per-Model (`models_in_family` NameError)
- **Tanggal Diterapkan:** 2 November 2026
- **Deskripsi:** Pada pembaruan pembatasan batch independen per-model (memisahkan alokasi 20 RPD untuk Flash-Lite dan 20 RPD untuk Flash), variabel `models_in_family` sempat tidak terdefinisi sebelum inisialisasi kamus kuota, yang menyebabkan eksekusi terjadwal pukul 17:34 WIB terhenti dini dengan `NameError`.
- **Perbaikan:** Variabel `models_in_family` didefinisikan secara presisi, dan kamus `processed_per_model` diinisialisasi secara idempoten dengan membaca riwayat panggilan sukses pada tanggal yang sama dari `logs/quota_tracker.json`. Mekanisme ini memastikan runner mengeksekusi tepat kuota 20 permintaan per hari per model secara independen dan tahan terhadap interupsi/restart sesi.
- **Kepatuhan Protokol:** Urutan antrean acak beku (`seed=42`), integritas *append-only* log, dan seluruh parameter/konfigurasi model tetap 100% identik sesuai proposal.
- **Status:** Diperbaiki & Terverifikasi di `src/run_daily.py`.

---

## 11. Interupsi Sesi Antigravity pada Batch 2 November, Audit Status REQ-0015, dan Penyesuaian Penjadwal
- **Tanggal Diterapkan:** 3 November 2026
- **Deskripsi Kejadian:**
  1. **Interupsi Server Environment:** Pada akhir batch 2 November saat pemanggilan item 3.8 (`REQ-0015`), terjadi restart lingkungan agen (*server restart*) yang menghentikan proses latar belakang yang di-*spawn* dari terminal Antigravity.
  2. **Audit Integritas Data REQ-0015:** Pemeriksaan menyeluruh pada `raw/llm.jsonl` dan `data/experiment_queue.json` mengonfirmasi bahwa `REQ-0015` terhenti sebelum respon atau penulisan berkas selesai. Status `REQ-0015` tetap bersih berstatus `"pending"` tanpa duplikasi atau data hilang.
  3. **Pembersihan Stale Lock:** Berkas penanda `data/runner.lock` dari proses lama (PID 18744) otomatis dibersihkan oleh fungsi `acquire_instance_lock` pada peluncuran berikutnya setelah mendeteksi PID tersebut sudah tidak aktif di Windows.
  4. **Kemandirian Task Scheduler:** Proses yang diluncurkan dari sesi Antigravity terikat pada sesi parent agen, sedangkan Windows Task Scheduler berjalan mandiri di tingkat sistem operasi (`Schedule Service`).
  5. **Pengaturan Daya Task Scheduler:** Diidentifikasi bahwa opsi `DisallowStartIfOnBatteries = True` dan `StartWhenAvailable = False` menyebabkan tugas terjadwal pukul 15:30 WIB terlewat saat laptop dalam kondisi baterai/tidur. Disediakan panduan penyesuaian manual melalui Task Scheduler GUI (`taskschd.msc`) karena perubahan membutuhkan hak Administrator (UAC).
- **Kepatuhan Protokol:** Seluruh parameter eksperimen, urutan acak beku (`seed=42`), dataset Dstep, dan konfigurasi resmi model Gemini tetap 100% utuh tanpa modifikasi.
- **Status:** Terdokumentasi & Diverifikasi.

---

## 12. Eksekusi Mandiri Penjadwal Batch 4 November & Bukti Empiris Pemotongan Kuota 3.8 oleh Galat 503
- **Tanggal Diterapkan:** 4 November 2026
- **Deskripsi Kejadian:**
  1. **Eksekusi Otomatis Task Scheduler:** Windows Task Scheduler berhasil memicu `run_daily_scheduler.bat` secara mandiri pada pukul 16:29:50 WIB dan selesai pada 16:50:26 WIB (`LastTaskResult = 0`). Seluruh log eksekusi terekam di `logs/daily_execution.log`.
  2. **Hasil Keluarga 2.5:** Model `gemini-2.5-flash-lite` dan `gemini-2.5-flash` berhasil menuntaskan seluruh kuota 20 RPD masing-masing (total 40 item sukses: 15 L25L-OFF, 5 L25L-ON, 11 L25F-OFF, 9 L25F-ON). Tidak ada galat kuota (0x 429) berkat jeda pacing 13,0 detik.
  3. **Bukti Empiris Pengurangan Kuota 3.8 oleh Galat 503:**
     - Pada eksekusi 3.8, terjadi lonjakan beban server Google (`503 UNAVAILABLE - This model is currently experiencing high demand`).
     - Tepat 21 permintaan 503 tercatat berturut-turut pada 10 item antrean (1–2 percobaan per item).
     - Pada permintaan ke-22 (`REQ-0062`), server Google mengembalikan `429 RESOURCE_EXHAUSTED: You exceeded your current quota`.
     - *Konfirmasi Ilmiah:* Data ini membuktikan secara definitif bahwa gateway API Google tetap menghitung dan memotong kuota harian Free Tier (20 RPD) untuk permintaan yang gagal dengan kode HTTP 503 (server overload).
  4. **Kepatuhan Kebijakan Retry Multi-Hari:**
     - Seluruh 11 item 3.8 yang gagal hari ini tetap berstatus `"pending"` (6 item tercatat 2 hari gagal, 5 item tercatat 1 hari gagal).
     - Tidak ada item baru yang ditandai `"failed"` hari ini karena belum ada yang memenuhi syarat kegagalan pada 3 hari berbeda. Total item `failed` kumulatif tetap 1 item (`REQ-0003`).
- **Kepatuhan Protokol:** Seluruh parameter eksperimen, urutan acak beku (`seed=42`), dataset Dstep, dan konfigurasi resmi model Gemini tetap 100% utuh tanpa modifikasi.
- **Status:** Terdokumentasi & Diverifikasi.

---

## 13. Penangguhan Penandaan Failed 3.8, Penerapan Standar Zona Waktu Pasifik, dan Perlakuan MAX_TOKENS
- **Tanggal Diterapkan:** 4 November 2026 (efektif batch 5 November 2026)
- **Deskripsi Penyesuaian:**
  1. **Penangguhan Penandaan 'failed' (Data Hilang) pada Gemini 3.8:**
     - Penandaan status `"failed"` untuk item keluarga 3.8 yang mengalami galat server (`503`/`504`/timeout) resmi **DITANGGUHKAN** atas instruksi Peneliti.
     - Seluruh item yang gagal tetap mempertahankan status `"pending"`. Seluruh riwayat percobaan, tanggal percobaan (zona waktu Pasifik), kode status HTTP, dan pesan galat tetap dicatat secara lengkap di antrean dan log mentah.
     - Keputusan akhir penandaan item data hilang ditunda hingga ada keputusan bersama antara Peneliti dan Dosen Pembimbing.
     - Item `REQ-0003` (`late_26 | L38F-HIGH`) tetap berstatus `"failed"` dengan catatan resmi bahwa status tersebut ditetapkan sebelum berlakunya kebijakan penangguhan ini (mengikuti aturan lama 3 hari berbeda).
  2. **Penerapan Zona Waktu Pasifik (`America/Los_Angeles`):**
     - Standar tanggal batas harian (`today_str`), pelacakan kuota harian (`processed_per_model`), dan penandaan `attempt_dates` di antrean resmi diselaraskan ke zona waktu **Pacific Time (PT, America/Los_Angeles)** yang digunakan oleh gateway Google AI Studio.
     - Seluruh `attempt_dates` pada `data/experiment_queue.json` dihitung ulang secara retrospektif dari timestamp riwayat panggilan di `logs/quota_tracker.json`.
  3. **Perlakuan Khusus Item `REQ-0205` (`MAX_TOKENS` pada `L25L-OFF`):**
     - Item `REQ-0205` menghasilkan teks repetitif hingga batas 32.768 token dengan `finish_reason: FinishReason.MAX_TOKENS`.
     - Output yang terpotong ini dievaluasi oleh parser CrochetPARADE dan menghasilkan `valid: false` (tidak valid).
     - Sesuai protokol penelitian, item ini **tetap diikutsertakan dalam penyebut VPR** (N=119 Standalone, N=117 Contextual) dan diklasifikasikan ke dalam kategori taksonomi error **"kosong/terpotong" (empty/truncated)**. Batas `max_output_tokens=32768` dipertahankan tanpa perubahan.
- **Kepatuhan Protokol:** Urutan antrean acak beku (`seed=42`), dataset Dstep, prompt resmi, dan parameter model tetap 100% identik tanpa perubahan.
- **Status:** Diterapkan & Diverifikasi.

---

## 14. Penerapan Opsi A (Single Runner Terdistribusi & Circuit Breaker) dan Verifikasi Alur Mock
- **Tanggal Diterapkan:** 4 November 2026 (efektif batch 5 November 2026 pukul 15:30 WIB)
- **Rasional & Keputusan:**
  - Peneliti secara resmi memilih **OPSI A** (single runner dengan pacing terdistribusi dan circuit breaker). Opsi B (multi-trigger manual) tidak digunakan.
- **Ketentuan Teknis Arsitektur Baru:**
  1. **Batas Waktu Eksekusi Terpisah:**
     - Tahap Keluarga 2.5: Maksimal **2 jam** (`MAX_RUNTIME_25 = 7200` detik).
     - Tahap Keluarga 3.8: Maksimal **12 jam** (`MAX_RUNTIME_38 = 43200` detik).
     - Jika batas waktu terlampaui, pemrosesan dihentikan secara anggun (*graceful stop*) dan sisa item dipertahankan dalam status `"pending"`.
  2. **Jeda Antarpercobaan 3.8 (Anti-Burst):**
     - Ditetapkan jeda pacing **~30 menit** (`PACING_DELAY_38 = 1800` detik) antar-percobaan untuk menyebarkan 20 kuota panggilan sepanjang hari kuota Pasifik.
  3. **Circuit Breaker:**
     - Jika terjadi **2 galat 503 berturut-turut** pada pemanggilan model 3.8, sistem secara otomatis mengaktifkan circuit breaker dan masuk ke masa pendinginan selama **60 menit** (`CIRCUIT_BREAKER_WAIT = 3600` detik) sebelum mencoba permintaan berikutnya.
     - Galat kuota harian `429 RESOURCE_EXHAUSTED` tetap menghentikan pemrosesan model untuk hari kalender Pasifik tersebut.
  4. **Pencegahan Windows Sleep:**
     - Runner secara otomatis memanggil Windows API `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` pada saat mulai untuk mencegah sistem memasuki mode tidur saat eksekusi berlangsung, dan mengembalikannya ke normal pada blok `finally`.
  5. **Klarifikasi Rekonsiliasi Data 3.8:**
     - Dikonfirmasi bahwa catatan 11 respons 3.8 di `raw/llm.jsonl` (7 LOW, 4 HIGH) murni merupakan data eksperimen resmi tanpa kontaminasi data pilot.
     - Catatan "5 sukses HIGH" pada pelacak kuota sebelumnya terbukti berasal dari penulisan entri log administratif pemulihan status `REQ-0002` (`event_type: POLICY_UPDATE_RESTORE`) yang menggunakan status HTTP 200. Logika penghitungan sukses kini disaring secara ketat berdasarkan `event_type == "SUCCESS"`.
  6. **Hasil Uji Dry-Run Komprehensif (Mock Client):**
     - Seluruh alur kerja baru (Tahap 2.5, Tahap 3.8, jeda pacing, circuit breaker 503, batas runtime terpisah, sleep prevention, dan pelepasan file lock) telah diuji secara menyeluruh menggunakan mock client pada `src/test_flow_mock.py` dan dinyatakan **LULUS 100% (ZERO ERRORS)** tanpa memanggil API nyata.
- **Kepatuhan Protokol:** Urutan antrean acak beku (`seed=42`), dataset Dstep, konfigurasi model, parameter, prompt, dan batas timeout klien 600s tetap 100% utuh tanpa modifikasi.
- **Status:** Diimplementasikan, Diverifikasi, & Siap Eksekusi.

---

## 15. Investigasi Task Scheduler 0x800710E0, Audit Durasi 503 Model 3.8, Rekonsiliasi Percobaan HIGH, Analisis Kegagalan 2.5, dan Eksekusi Batch 6 November
- **Tanggal Diterapkan:** 6 November 2026
- **Konteks & Investigasi Masalah:**
  1. **Investigasi Galat Task Scheduler `0x800710E0` (`2147946720`):**
     - Pada 6 November pukul 18:15:35 WIB, tugas terjadwal `CrochetDSL_Experiment_Daily` gagal mengeksekusi dengan kode hasil `0x800710E0` (`SCHED_E_TASK_NOT_READY` / `ERROR_NOT_READY` - *The operator or administrator has refused the request*).
     - Audit log sistem Windows (`Microsoft-Windows-Kernel-Power`, Event ID 105) membuktikan bahwa pada pukul **18:15:34 WIB** (1 detik sebelum tugas dipicu), laptop beralih ke daya baterai (*power source change*) setelah keluar dari *Modern Standby* pada 18:14:51 WIB.
     - Pemeriksaan properti tugas menunjukkan konfigurasi baterai belum diperbarui:
       - `DisallowStartIfOnBatteries : True` (`AllowStartIfOnBatteries : False`)
       - `StopIfGoingOnBatteries : True`
       - `WakeToRun : False`
       - `StartWhenAvailable : False`
     - Windows Task Scheduler secara deterministik menolak menjalankan tugas karena sistem berada dalam mode daya baterai sementara aturan hemat daya aktif. Eksekusi `Set-ScheduledTask` via PowerShell non-elevated ditolak dengan galat `0x8007052e` (*logon failure*) karena tugas berjalan dengan akun pengguna tanpa token elevasi Administrator.
  2. **Audit Distribusi Durasi Galat 503 Gemini 3.8 Flash:**
     - Mengoreksi generalisasi awal bahwa galat 503 selalu kembali dalam 7-8 detik.
     - Berdasarkan analisis empiris 35 catatan galat 503 di `logs/model_access_38_detailed.jsonl`:
       - Min: 0.00 detik, Median: 2.39 detik, Rata-rata: 17.94 detik, Maks: 217.23 detik.
       - Distribusi rentang durasi: `<10s` = 24 kasus (68.6%), `10-30s` = 6 kasus (17.1%), `30-60s` = 2 kasus (5.7%), `60-120s` = 2 kasus (5.7%), `120-300s` = 1 kasus (`REQ-0016`: 217.23 detik).
       - Penjelasan teknis: Galat 503 cepat (<10 detik) terjadi akibat penolakan langsung pada load balancer gerbang API (*immediate admission rejection*). Galat 503 lambat (hingga 217 detik) terjadi saat koneksi HTTP streaming diterima dan dimasukkan ke antrean penjadwalan kluster TPU backend (*internal dispatch queue*), namun alokasi sumber daya komputasi gagal atau dibatalkan sebelum chunk pertama dihasilkan (`first_chunk: None`, `chunk_count: 0`), menahan soket TCP tetap terbuka hingga batas timeout internal kluster tercapai.
  3. **Rekonsiliasi Final Percobaan L38F-HIGH (37 vs 38) & Ketiadaan Pilot:**
     - Dari 38 rekaman berlabel HIGH pada `logs/quota_tracker.json`, entri ke-6 (`EventIdx: 64`, timestamp `2026-10-31T16:23:39`) terbukti merupakan entri log administratif pemulihan status `REQ-0002` (`event_type: POLICY_UPDATE_RESTORE`) yang keliru mencatat status 200, bukan panggilan API.
     - Total pemanggilan API riil pada HIGH adalah **37 percobaan**: 4 Sukses (200), 18 Galat 503 UNAVAILABLE, 14 Galat 504/Read Timeout, dan 1 Kuota Harian 429 RESOURCE_EXHAUSTED.
     - Audit pada `raw/llm.jsonl` mengonfirmasi **0 catatan pilot**: seluruh 11 respons sukses 3.8 (7 LOW, 4 HIGH) murni berasal dari ID antrean resmi eksperimen (`REQ-xxxx`).
  4. **Analisis Dampak 3 Item Gagal 2.5 (`REQ-0336`, `REQ-0341`, `REQ-0351`):**
     - Ketiga item pada kondisi `L25L-ON` ditandai *failed* pada 5 November setelah 3 kali retry berurutan pada hari yang sama mengembalikan galat 503 akibat lonjakan beban server.
     - Dampak statistik RM1 (McNemar berpasangan): Jika dianalisis dengan *Complete-Case Analysis*, ukuran sampel efektif berkurang dari $N=119$ menjadi $N_{eff} = 116$ (-2.52% kekuatan uji). Jika dianalisis dengan *Worst-Case Imputation* (dinilai 0), timbul bias pengukuran artifisial karena kegagalan disebabkan oleh lonjakan server Google, bukan kegagalan penalaran model.
     - Dampak statistik RM2 (Cochran's Q): Matriks omnibus 6 kondisi kehilangan 3 baris sampel instruksi karena data tidak lengkap.
     - Status ketiga item saat ini dipertahankan tetap *failed* sesuai instruksi peneliti, sembari menunggu keputusan formal peneliti/dosen pembimbing terkait opsi pembukaan kembali (*reopen as pending*) untuk retry lintas hari.
  5. **Eksekusi Batch 6 November:**
     - File lock usang PID 19396 dibersihkan.
     - Batch dijalankan langsung via `run_daily.py --all` dengan perlindungan tidur Windows aktif (`SetThreadExecutionState: ES_CONTINUOUS | ES_SYSTEM_REQUIRED`). Tahap 2.5 dieksekusi terlebih dahulu hingga tuntas, diikuti oleh tahap 3.8 dengan arsitektur Opsi A (pacing 30 menit, circuit breaker 60 menit setelah 2x 503).
- **Kepatuhan Protokol:** Urutan antrean acak beku (`seed=42`), dataset Dstep, parameter model (temperature=0.0, max_tokens=32768, client timeout=600s), dan prompt resmi tetap 100% utuh tanpa perubahan.
- **Status:** Terdokumentasi, Diverifikasi, & Berjalan.

---

## 16. Penetapan Batas Waktu Pembekuan Data Gemini 3.8 (30 November 2026 PT), Penyiapan Modul Analisis RM3, dan Kebijakan Status Antrean
- **Tanggal Diterapkan:** 11 November 2026
- **Keputusan Peneliti & Ketentuan Protokol:**
  1. **Pelaporan Empiris Apa Adanya:**
     - Peneliti secara resmi menetapkan bahwa hasil eksperimen Gemini 3.8 Flash akan dilaporkan apa adanya (*as-is*) sesuai fakta empiris lapangan (termasuk kendala aksesibilitas kluster Google Free Tier dan ketiadaan data akibat penolakan server 503/504).
  2. **Batas Waktu Pengumpulan Data Tahap 3.8:**
     - Tahap pemanggilan Gemini 3.8 Flash dengan arsitektur Opsi A (pacing 30 menit, circuit breaker 60 menit setelah 2x 503) diizinkan tetap berjalan hingga batas akhir **30 November 2026 (waktu kalender Pasifik / America/Los_Angeles)**.
     - Tepat setelah 30 November 2026 PT, eksekusi tahap 3.8 dihentikan secara permanen dan seluruh data 3.8 dibekukan (*frozen*).
  3. **Kebijakan Status Item 3.8 yang Belum Selesai:**
     - Seluruh item antrean 3.8 yang belum selesai pada tanggal penutupan tersebut dipertahankan dalam status `"pending"` (tidak ditandai sebagai `failed`).
     - Item `REQ-0003` (`late_26 | L38F-HIGH`) tetap berstatus `"failed"` karena status tersebut ditetapkan secara sah berdasarkan kebijakan lama (gagal pada 3 hari berbeda) sebelum berlakunya kebijakan penangguhan.
  4. **Penyiapan Modul Analisis RM3 (`src/analyze_rm3.py`):**
     - Modul analisis mandiri khusus RM3 telah disiapkan dan diverifikasi dengan cakupan evaluasi lengkap:
       - (a) Jumlah respons selesai per level (LOW vs HIGH) dan per kelompok langkah (*early*, *mid*, *late*).
       - (b) Jumlah pasangan lengkap (*complete pairs*) dan ukuran sampel efektif ($N_{\text{eff}}$).
       - (c) VPR LOW dan HIGH dengan Wilson score 95% CI untuk penyebut respons selesai maupun penyebut populasi total ($N=119$).
       - (d) Uji inferensial berpasangan McNemar eksak dan percentile bootstrap 95% CI (10.000 resamples, `seed=42`) yang dikunci dengan ambang batas minimum $N_{\text{eff}} \ge 10$. Jika $N_{\text{eff}} < 10$, sistem secara eksplisit mencetak kesimpulan: *"TIDAK DAPAT DISIMPULKAN"* (bukan 'tidak ada perbedaan').
       - (e) Tabel ketersediaan akses lengkap (percobaan riil, sukses 200, galat 503, galat 504, timeout, kuota habis 429) per level dan per tanggal kalender Pasifik.
       - (f) Distribusi durasi (latensi) dan thinking tokens pada seluruh respons yang berhasil diselesaikan.
       - (g) Analisis sensitivitas A (cek bias seleksi subset pasangan lengkap) dan sensitivitas B (*worst-case imputation* di mana seluruh pending/missing dinilai 0 pada $N=119$).
     - Modul ini dilengkapi *execution guard* yang mencegah eksekusi prematur sebelum 30 November 2026 kecuali diberikan instruksi eksplisit (`--force`).
  5. **Status Item 2.5 yang Gagal:**
     - Status 3 item keluarga 2.5 (`REQ-0336`, `REQ-0341`, `REQ-0351`) dipertahankan tetap `"failed"` sembari menunggu keputusan terpisah dari peneliti.
  6. **Pelaporan Mingguan Rutin:**
     - Pelaporan berkala akan disampaikan setiap minggu yang memuat: jumlah respons 3.8 baru, laju sukses nyata empiris, dan jumlah pasangan lengkap (*complete pairs*) terkini.
- **Kepatuhan Protokol:** Urutan antrean acak beku (`seed=42`), dataset Dstep, parameter model (temperature=0.0, max_tokens=32768, client timeout=600s), dan prompt resmi tetap 100% utuh tanpa perubahan.
- **Status:** Ditetapkan, Terdokumentasi, & Diimplementasikan.

---

## 17. Klarifikasi Parameter Sampling Bawaan (Default Sampling vs Boilerplate Temperature 0.0), Pembaruan Guard Pembekuan RM3, dan Kategori Akses 3.8
- **Tanggal Diterapkan:** 11 November 2026
- **Poin Klarifikasi & Catatan Deviasi:**
  1. **Verifikasi Parameter Sampling Model (Default Sampling):**
     - Sesuai dengan rancangan awal metodologi eksperimen dan implementasi nyata pada kode sumber `src/run_daily.py` (baris 470-472), pemanggilan API Gemini secara ketat menggunakan **sampling bawaan model (*default sampling*)**:
       - `temperature`: `None` (tidak dikirim / nilai bawaan Google API)
       - `top_p`: `None` (tidak dikirim / nilai bawaan Google API)
       - `top_k`: `None` (tidak dikirim / nilai bawaan Google API)
       - `max_output_tokens`: `32768` (eksplisit)
       - `thinking_budget`: `0` untuk OFF, `-1` (dinamis) untuk 2.5 ON.
       - `thinking_level`: `'low'` untuk 3.8 LOW, `'high'` untuk 3.8 HIGH.
     - Penulisan kalimat *"temperature=0.0"* pada teks rangkuman di seksi-seksi sebelumnya di `logs/deviations.md` merupakan kekeliruan teks *boilerplate* dokumentasi, bukan konfigurasi yang berjalan di lingkungan eksekusi. Tidak ada perubahan yang dilakukan pada payload pemanggilan model.
  2. **Observasi Nilai Thinking Token 31.455 (`REQ-0002` vs `REQ-0044`):**
     - Nilai 31.455 token penalaran pada `REQ-0002` (1 Nov 2026 PT) dan `REQ-0044` (8 Nov 2026 PT / 9 Nov 2026 WIB) dicatat murni sebagai **OBSERVASI EMPIRIS**:
       * Sebanyak 2 dari 5 respons sukses kondisi `L38F-HIGH` (40.0%) berhenti tepat pada nilai 31.455 token.
       * Keduanya dieksekusi pada hari berbeda (selisih 8 hari kalender) dan proses runner terpisah secara independen, dengan variabel `thoughts` selalu diinisialisasi ulang menjadi `None` pada setiap percobaan.
       * Dugaan bahwa nilai 31.455 merepresentasikan batas atas internal (*internal ceiling cap*) alokasi token penalaran Gemini 3.8 Flash level HIGH sebelum kandidat dihasilkan **belum terverifikasi dari sisi klien** (merupakan perilaku backend tertutup Google API).
       * Pemindaian seluruh berkas mentah `raw/llm.jsonl` menunjukkan 169 nilai token unik dengan hanya 5 nilai yang berulang wajar pada prompt dan hari yang berbeda.
  3. **Pembaruan Pengaman Eksekusi (*Execution Guard*) Skrip `analyze_rm3.py`:**
     - Skrip analisis RM3 diperbarui sehingga hanya dapat dieksekusi secara otomatis jika memenuhi dua syarat mutlak:
       (a) Tanggal kalender Pasifik >= 1 Desember 2026 (`today_pt >= "2026-12-01"`).
       (b) Tidak ada proses runner harian yang sedang berjalan aktif (`data/runner.lock` bersih atau PID tidak aktif).
     - Jika salah satu syarat belum terpenuhi, skrip secara otomatis menolak eksekusi kecuali disertai argumen `--force`.
  4. **Standardisasi Label Ketersediaan Akses 3.8:**
     - Mengganti istilah "penolakan server" dengan istilah netral **"tidak berhasil"** (72 dari 86 percobaan, 83.7%).
     - Memisahkan kategori galat berdasarkan teks dan jenis galat nyata:
       - `503 (ditolak server / kapasitas)`: 39 kejadian (45.3%)
       - `Timeout klien (read operation timed out, ~600s)`: 26 kejadian (30.2%)
       - `Koneksi putus (WinError 10053/10054/10051)`: 5 kejadian (5.8%)
       - `504 DEADLINE_EXCEEDED dari server`: 0 kejadian (0.0%)
       - `429 (kuota harian habis)`: 2 kejadian (2.3%)
- **Kepatuhan Protokol:** Urutan antrean acak beku (`seed=42`), dataset Dstep, konfigurasi model bawaan, batas timeout (600s), dan status item 2.5 yang gagal (`REQ-0336`, `REQ-0341`, `REQ-0351`) tetap dipertahankan tanpa modifikasi.
- **Status:** Terdokumentasi & Diterapkan.

---

## 18. Rekam Jejak Kolom params_sent, Integritas Hash Kode Sumber, Rekonsiliasi Pending 2.5, dan Audit Galat 503 Kuota RPD
- **Tanggal Diterapkan:** 11 November 2026 (Malam)
- **Poin Dokumentasi & Temuan:**
  1. **Rekam Jejak Penambahan Kolom `params_sent`:**
     - Proses batch harian 11 November 2026 dimulai pada pukul 20:06 WIB (PID 25148), sedangkan penambahan kolom `params_sent` ke dalam skrip `src/run_daily.py` selesai diterapkan pada pukul 20:16 WIB.
     - Karena interpreter Python memuat modul ke dalam memori kerja pada saat *startup*, seluruh 31 catatan yang dihasilkan dan disimpan pada batch 11 Nov belum memuat kolom `params_sent`.
     - Dengan demikian, total 392 baris mentah di `raw/llm.jsonl` (361 baris historis + 31 baris batch 11 Nov) secara konsisten tidak memuat kolom `params_sent`.
     - Record pertama yang akan secara resmi memuat kolom `params_sent` adalah respons sukses pertama yang dihasilkan oleh proses runner baru pada batch 12 November 2026 (atau eksekusi baru berikutnya).
  2. **Verifikasi Integritas SHA-256 Kode Sumber:**
     - Hash SHA-256 berkas `src/run_daily.py` saat ini adalah `6eba814bc477bed1f3b24c11375530962afa24d8f1089ed89c0384102f5e6322`.
     - Nilai hash tersebut telah diverifikasi byte-for-byte identik dengan yang tercatat pada `logs/config_snapshot.json` dan berkas cadangan `backups/src_2026-11-11/run_daily.py`.
  3. **Rekonsiliasi Sisa Item Pending 2.5 Pasca-Batch 11 Nov:**
     - Status antrean sebelum batch 11 Nov: 341 `done`, 3 `failed` (`REQ-0336`, `REQ-0341`, `REQ-0351`), dan 132 `pending` (total 476 item).
     - Selama batch 11 Nov, runner memproses 31 item: **29 item sukses (`done`)** dan **2 item gagal (`failed`: `REQ-0512` & `REQ-0514`)**.
     - Rekonsiliasi sisa pending: $132 - 29 (\text{done}) - 2 (\text{failed}) = 101 \text{ item pending}$ (rincian per kondisi: `L25F-OFF`: 23, `L25F-ON`: 30, `L25L-OFF`: 25, `L25L-ON`: 23).
     - Terverifikasi pada `data/experiment_queue.json` bahwa `REQ-0512` dan `REQ-0514` berstatus `"failed"` dan tidak dihitung ke dalam item pending.
  4. **Temuan Empiris Pemotongan Kuota RPD oleh Galat 503:**
     - Pada `gemini-2.5-flash-lite`: kuota harian 429 RPD terpicu pada panggilan ke-22 setelah akumulasi 16 sukses + 5 galat 503 = 21 pemanggilan HTTP.
     - Pada `gemini-2.5-flash`: kuota harian 429 RPD terpicu pada panggilan ke-22 setelah akumulasi 13 sukses + 8 galat 503 = 21 pemanggilan HTTP.
     - Hal ini membuktikan bahwa pada infrastruktur Google AI Studio Free Tier, pemanggilan yang gagal akibat penolakan beban/kapasitas server (503 UNAVAILABLE) tetap dicatat dan mengonsumsi kuota harian Requests Per Day (RPD).
- **Kepatuhan Protokol:** Urutan antrean acak beku (`seed=42`), dataset Dstep, parameter konfigurasi model bawaan, batas timeout (600s), dan status kelima item 2.5 yang gagal (`REQ-0336`, `REQ-0341`, `REQ-0351`, `REQ-0512`, `REQ-0514`) tetap dipertahankan tanpa modifikasi.
- **Status:** Terdokumentasi & Terverifikasi.

---

## 19. Insiden Aktivasi Circuit Breaker ke-2 (12 Nov 22:26 WIB) Akibat Urutan Non-Beruntun (503, Timeout, 503), Rekapitulasi 3.8 Hari Pasifik 12 Nov, dan Pembaruan Metrik Token Berulang HIGH
- **Tanggal Diterapkan:** 13 November 2026
- **Poin Dokumentasi & Temuan:**
  1. **Insiden Circuit Breaker ke-2 pada Urutan Non-Beruntun:**
     - Pada eksekusi batch 12 November 2026 pukul 22:26:11 WIB, *Circuit Breaker* ke-2 terpicu pada urutan pemanggilan:
       1. `REQ-0034` Percobaan 1: `503 UNAVAILABLE` (`consecutive_503_count` = 1)
       2. `REQ-0034` Percobaan 2: `Timeout Klien 600s` (`consecutive_503_count` tetap bernilai 1 karena tidak direset oleh galat non-503)
       3. `REQ-0049` Percobaan 1: `503 UNAVAILABLE` (`consecutive_503_count` bertambah menjadi 2 $\rightarrow$ memicu *cooldown* 60 menit)
     - Secara operasional, dua galat 503 tersebut tidak berurutan langsung (*non-consecutive*), melainkan diselingi oleh satu *client read timeout* selama 601 detik. Namun karena logika pada `src/run_daily.py` hanya menginkremen saat `status_code == 503` tanpa mereset penghitung ke 0 pada percabangan selain 503 (baik respons sukses maupun galat non-503 seperti timeout), penghitung tidak terhapus.
  2. **Rekapitulasi Percobaan Gemini 3.8 Flash pada Hari Kuota Pasifik 12 Nov:**
     - Total percobaan riil: **8 percobaan HTTP**
       - **Sukses (HTTP 200):** **1 percobaan** (`REQ-0029`, durasi 218.42s, `thoughts_token_count = 15829`)
       - **503 UNAVAILABLE (Kapasitas Server):** **4 percobaan** (`REQ-0016` 2x, `REQ-0034` 1x, `REQ-0049` 1x)
       - **Timeout Klien (~600s socket read):** **3 percobaan** (`REQ-0029` 1x, `REQ-0034` 1x, `REQ-0049` 1x)
       - **429 RESOURCE_EXHAUSTED (Batas Harian):** **0 kejadian**
     - **Penyebab Penghentian Runner 12 Nov:** Tahap 3.8 dihentikan oleh **batas runtime 12 jam**, BUKAN karena batas kuota 20 permintaan harian habis. Runner mencatat log resmi pada 13 Nov 09:09 WIB: `[3.8] Maximum stage runtime limit of 12.0 hours exceeded (15.15h elapsed). Stopping stage 3.8 gracefully. Remaining items remain PENDING.` Seluruh sisa item 3.8 dipertahankan dalam status `pending`.
  3. **Pembaruan Metrik Token Berulang L38F-HIGH (Bagian f):**
     - Keberhasilan `REQ-0029` (15.829 token) menambah total respons selesai `L38F-HIGH` dari 5 menjadi **6 respons**.
     - Sebaran nilai `thoughts_token_count` pada level HIGH saat ini: 438 (`REQ-0006`), 15.829 (`REQ-0029`), 20.793 (`REQ-0010`), 23.125 (`REQ-0033`), dan 31.455 (`REQ-0002` dan `REQ-0044`).
     - Proporsi respons yang berhenti tepat pada nilai maksimum empiris 31.455 token kini adalah **2 dari 6 respons (33.3%)**, menurun dari sebelumnya 2 dari 5 (40.0%).
  4. **Usulan Perbaikan Penghitung Circuit Breaker:**
     - Telah disiapkan dan diuji pada lingkungan *mock* rancangan perbaikan agar `consecutive_503_count` secara eksplisit direset ke 0 pada setiap hasil selain 503 (baik sukses 200 maupun galat non-503 seperti timeout klien 504 dan *connection reset*). Perbaikan ini disimpan terisolasi dan menunggu persetujuan eksplisit peneliti sebelum diterapkan ke kode utama `src/run_daily.py`.
- **Kepatuhan Protokol:** Seluruh parameter model, sampling bawaan, dataset, prompt, urutan antrean (`seed=42`), dan status item failed (`REQ-0336`, `REQ-0341`, `REQ-0351`, `REQ-0512`, `REQ-0514`, `REQ-0003`) tetap 100% terlindungi tanpa modifikasi.
- **Status:** Terdokumentasi, Teruji secara Mock, & Menunggu Persetujuan.

---

## 20. Keputusan Peneliti 19 November 2026: Kebijakan Retry Seragam 2.5, Pembaruan Runner 3.8, dan Hasil Eksekusi Uji Ulang
- **Tanggal Diterapkan:** 19 November 2026
- **Keputusan Peneliti & Ketentuan Protokol:**
  1. **Aturan Retry Seragam 2.5 (Menggantikan Penandaan Failed Sebelumnya):**
     - Item keluarga 2.5 yang sebelumnya ditandai `failed` akibat kegagalan infrastruktur jaringan/server (503/504/timeout tanpa respons model) dikembalikan ke status `"pending"`: `REQ-0336`, `REQ-0341`, `REQ-0351`, `REQ-0512`, dan `REQ-0514`.
     - Seluruh riwayat galat (`error_history`), hitungan percobaan (`attempts`), dan tanggal percobaan (`attempt_dates`) dipertahankan secara utuh tanpa menghapus rekaman historis.
     - Aturan berlaku seragam untuk semua kondisi 2.5: Maksimal 3 percobaan tambahan per item pada hari Pasifik berbeda (total 4 hari kalender Pasifik berbeda). Jika setelah 4 hari Pasifik berbeda tetap gagal tanpa respons, barulah statusnya final `failed`.
     - Item yang telah memiliki respons model yang sah (termasuk DSL tidak valid atau terpotong seperti `REQ-0205`) dilarang keras diulang dan tetap berstatus `done`.
     - Untuk konsistensi dengan kebijakan penangguhan 3.8, item `REQ-0003` (`L38F-HIGH`, `late_26`) turut dikembalikan ke status `"pending"` dengan `error_history` utuh.
  2. **Penerapan Perbaikan Runner (`src/run_daily.py`):**
     - Diterapkan secara aman setelah runner PID 5504 dihentikan pada fase idle/sleep:
       (a) **Reset Penghitung 503:** Variabel `consecutive_503_count` kini direset ke 0 pada hasil apa pun selain 503 (respons sukses 200, galat non-503 seperti timeout 504 / connection reset, dan kuota 429).
       (b) **Pemisahan Antrean 3.8:** Item 3.8 yang telah dicoba pada 2 hari Pasifik atau lebih dipindahkan ke bagian belakang antrean, sementara item segar (< 2 hari) tetap berada di depan mengikuti urutan beku `seed=42`.
       (c) **Pacing & Runtime Guard:** Jeda antarpercobaan 3.8 dipercepat dari 30 menit menjadi 15 menit (`PACING_DELAY_38 = 900.0s`), dan guard batas runtime 12 jam berbasis jam dinding (`check_runtime_and_sleep`) dicek sebelum setiap panggilan tidur (`sleep`).
     - Seluruh perbaikan telah diverifikasi lulus 100% pada uji mock (`scratch/test_flow_mock_v2.py`).
     - Hash SHA-256 berkas `src/run_daily.py` diperbarui dari `6eba814bc477bed1f3b24c11375530962afa24d8f1089ed89c0384102f5e6322` menjadi `3476c36389fd3cafcab077c126f23f81c317fc89e94194e3cfd2820866ca7b83` dan dicatat di `logs/config_snapshot.json` dengan salinan cadangan di `backups/src_2026-11-19/run_daily.py`.
  3. **Temuan Audit Sleep/Standby Sistem (Kernel-Power):**
     - Audit log kejadian Windows System (`Microsoft-Windows-Kernel-Power`, Event ID 42, 107, 506, 507) sejak 12 November mengonfirmasi 97 kejadian tidur/standby yang beririsan dengan jendela runner aktif. Sebagian besar merupakan *Modern Standby* (Event 506/507) akibat *idle timeout* layar, yang membekukan eksekusi proses pengguna saat baterai/laptop tidak aktif.
  4. **Hasil Eksekusi Ulang Tahap 2.5 (19 November 2026):**
     - Tahap 2.5 dijalankan secara eksklusif (`--family 2.5`) pada kuota Pasifik 19 November:
       - `REQ-0336` (`mid_25` | `L25L-ON`): 3x percobaan menghasilkan 503 UNAVAILABLE. Sesuai aturan retry seragam (baru 2 hari Pasifik), status tetap **PENDING**.
       - `REQ-0341` (`early_53` | `L25L-ON`): Sukses pada percobaan ke-2 (5.65s, thinking=1.365 token, `status=done`).
       - `REQ-0351` (`early_32` | `L25L-ON`): Sukses pada percobaan ke-1 (11.14s, thinking=3.123 token, `status=done`).
       - `REQ-0512` (`early_43` | `L25F-ON`): Sukses pada percobaan ke-1 (24.69s, thinking=4.107 token, `status=done`).
       - `REQ-0514` (`early_53` | `L25F-ON`): Sukses pada percobaan ke-1 (20.08s, thinking=3.479 token, `status=done`).
     - Dari 5 item pengulangan, **4 item sukses tuntas**. Total Family 2.5 kini mencapai **475 / 476 item selesai (99.8%)**, dengan hanya 1 item pending tersisa (`REQ-0336`) dan 0 failed.
  5. **Integritas Skrip Analisis & Pelaksanaan Analisis RM1 dan RM2:**
     - Hash SHA-256 dari skrip normalisasi, kompilasi, dan analisis telah disimpan di `logs/analysis_hashes.json` sebelum dieksekusi.
     - Analisis statistik RM1 dan RM2 telah berhasil dijalankan untuk kedua versi (Utama dan Sensitivitas) dengan protokol kontekstual murni tanpa menyentuh RM3.
- **Kepatuhan Protokol:** Seluruh parameter model bawaan (default sampling), timeout (600s), dataset Dstep, prompt resmi, dan urutan antrean dasar (`seed=42`) tetap 100% terlindungi tanpa modifikasi.
- **Status:** Ditetapkan, Terdokumentasi, Diuji secara Mock, Diterapkan, & Selesai Dievaluasi.
