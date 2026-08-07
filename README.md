# XAU Signal — M15 entry / H1 vùng / H4 xu hướng

App Streamlit đọc dữ liệu XAU/USD từ Twelve Data. Chạy được trên Windows, macOS, Linux và deploy lên Streamlit Cloud.

## Yêu cầu

- Python 3.10 trở lên (không còn ràng buộc 3.11 như bản MT5)
- Một khóa API Twelve Data miễn phí: https://twelvedata.com/register

---

## Phần 1 — Chạy trên máy cá nhân

### 1. Lấy khóa API

Đăng ký tài khoản Twelve Data, vào Dashboard, copy API key.

### 2. Cài đặt

```bash
cd xau_signal
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

### 3. Khai báo khóa

Trong thư mục `.streamlit`, đổi tên `secrets.toml.example` thành `secrets.toml`, rồi sửa dòng đầu:

```toml
TWELVEDATA_API_KEY = "khóa_của_bạn"
```

Phần `[gcp_service_account]` để nguyên nếu chưa dùng Google Sheets — app sẽ tự ghi ra `signals.csv`.

### 4. Chạy

```bash
streamlit run app.py
```

---

## Phần 2 — Đưa lên GitHub

### 1. Tạo repo

Vào github.com → **New repository** → đặt tên `xau-signal` → chọn **Private** → **Create**.

### 2. Đẩy code lên

```bash
git init
git add .
git commit -m "XAU signal app"
git branch -M main
git remote add origin https://github.com/TEN_CUA_BAN/xau-signal.git
git push -u origin main
```

**Kiểm tra ngay sau khi push:** vào repo trên GitHub, xác nhận **không thấy file `.streamlit/secrets.toml`**. File `.gitignore` đã chặn sẵn, nhưng vẫn nên tự mắt nhìn — khóa API lộ lên repo là mất luôn.

---

## Phần 3 — Deploy lên Streamlit Cloud

1. Vào https://share.streamlit.io → **Sign in with GitHub** → cho phép truy cập repo
2. **Create app** → chọn repo `xau-signal`, branch `main`, file `app.py`
3. Bấm **Advanced settings** → ô **Secrets**, dán vào:

```toml
TWELVEDATA_API_KEY = "khóa_của_bạn"
```

4. **Deploy**. Đợi 2–3 phút.

App sẽ có địa chỉ dạng `https://ten-app.streamlit.app`, mở được từ điện thoại.

---

## Phần 4 — Nhật ký trên Google Sheets

Bỏ qua phần này nếu chỉ chạy máy cá nhân — CSV là đủ.

**Streamlit Cloud xoá sạch ổ đĩa mỗi lần khởi động lại**, nên file CSV không sống được ở đó. Muốn giữ lịch sử tín hiệu để đo WR thì phải ghi ra Google Sheets.

### 1. Tạo service account

1. Vào https://console.cloud.google.com → tạo project mới
2. Menu → **APIs & Services** → **Library** → tìm **Google Sheets API** → **Enable**
3. **APIs & Services** → **Credentials** → **Create Credentials** → **Service account**
4. Đặt tên bất kỳ → **Done**
5. Bấm vào service account vừa tạo → tab **Keys** → **Add key** → **Create new key** → chọn **JSON** → tải file về

### 2. Tạo bảng tính

1. Tạo một Google Sheet mới, đặt tên đúng là **XAU Signal Journal**
2. Mở file JSON vừa tải, tìm dòng `client_email` (dạng `...@....iam.gserviceaccount.com`)
3. Trong Google Sheet bấm **Share**, dán email đó vào, cấp quyền **Editor**

### 3. Khai báo vào secrets

Mở file JSON, chép các giá trị sang phần `[gcp_service_account]` trong secrets. Riêng `private_key` phải giữ nguyên các ký tự `\n`.

Khi cấu hình đúng, tab **Nhật ký** trong app sẽ hiện "Đang lưu tại: Google Sheets".

---

## Những giới hạn cần biết

**Hạn mức API.** Gói miễn phí cho 8 credit/phút và 800 credit/ngày. Mỗi lần tải nến tốn 3 credit (M15 + H1 + H4), mỗi lần hỏi giá tốn 1. Sidebar hiện số credit đã dùng. Tuỳ chọn *Chỉ hỏi giá trong giờ phiên* giúp tiết kiệm đáng kể — ngoài phiên app dùng giá đóng cửa nến gần nhất.

**Không có spread thật.** Twelve Data chỉ trả giá giữa. App dùng spread giả định (chỉnh ở sidebar) để tính RR. Đặt bằng spread trung bình của broker bạn để con số sát thực tế; vào giờ tin spread thật giãn rộng hơn nhiều.

**Giá lệch với broker.** Twelve Data lấy từ nguồn liên ngân hàng, broker của bạn có giá riêng, thường chênh vài chục cent. Cấu trúc H4 và vùng H1 không bị ảnh hưởng, nhưng mức entry/SL/TP hiển thị cần đối chiếu lại trên nền tảng bạn đặt lệnh.

**Không có volume thật.** Forex và kim loại không có volume tập trung, nên VWAP ở đây là đường trung bình giá điển hình theo ngày, và thành phần điểm liên quan tới volume của vùng S/R luôn ở mức trung tính.

**App ngủ khi không ai mở.** Streamlit Cloud gói miễn phí cho app ngủ sau một thời gian không có người truy cập. Tín hiệu chỉ được ghi vào nhật ký khi app đang chạy, nghĩa là **khi bạn đang mở trang**. Muốn ghi liên tục 24/5 thì cần một dịch vụ chạy nền riêng — chuyện đó để sau.

---

## Logic

**5 cổng cứng** — thiếu một cổng là không có tín hiệu:

1. H4 có cấu trúc rõ ràng (HH+HL hoặc LH+LL)
2. Đang trong khung giờ phiên đã chọn
3. Giá nằm trong vùng giá trị H1 (fibo 38.2–78.6% **hoặc** vùng S/R điểm ≥ 60)
4. Có mẫu price action trên M15 (engulfing **hoặc** pin bar **hoặc** micro-BOS)
5. RR ≥ 2 sau khi trừ spread

**Điểm chất lượng 0–100** không loại lệnh, chỉ xếp hạng: chất lượng mẫu nến 20, Stoch RSI 12, độ tươi của vùng 15, trùng vùng S/R mạnh 20, VWAP/mốc tròn 10, chế độ biến động 13, độ trẻ của trend 10.

Kéo thanh trượt ngưỡng điểm ở sidebar để tự chỉnh cán cân giữa số lệnh và chất lượng.

## Nhật ký và thống kê

Mỗi tín hiệu ghi một dòng. Bấm **Cập nhật kết quả** ở tab Nhật ký để app kéo nến M15 sau đó và phân định WIN / LOSS / EXPIRED, kèm MAE/MFE.

Quy ước: **giữ nguyên SL/TP tới khi chạm** — không dời hòa vốn, không chốt một phần.

Tab Thống kê tách WR theo khoảng điểm, mẫu PA, phiên và bias H4. Dưới 30 lệnh đã chốt, app cảnh báo số liệu chưa đáng tin.

## Cấu trúc

```
app.py                  giao diện Streamlit
config.py               toàn bộ tham số — sửa ở đây, không sửa trong core/
core/data_client.py     Twelve Data: nến, giá, đếm credit
core/indicators.py      EMA, ATR, RSI, Stoch RSI, VWAP
core/structure.py       pivot, cấu trúc HH/HL, fibo hồi
core/zones.py           gom cụm và chấm điểm vùng S/R
core/patterns.py        engulfing, pin bar, micro-BOS trên M15
core/strategy.py        5 cổng cứng + điểm chất lượng
core/risk.py            SL / TP / khối lượng lệnh
journal/store.py        chọn nơi lưu: Google Sheets hoặc CSV
journal/logger.py       ghi và tự phân định WIN/LOSS
```

---

Công cụ hỗ trợ ra quyết định, không phải lời khuyên đầu tư. Chạy demo một thời gian đủ dài trước khi dùng tiền thật.
