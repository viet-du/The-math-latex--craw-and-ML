# The-math-latex--craw-and-ML

Script hiện tại crawl cac trang cong thuc tren Math Formula Atlas, trich cac bieu thuc toan hoc ve dang LaTeX va gom ket qua vao thu muc `formulas` theo dinh dang de dua vao pipeline ML.

## Chạy

```bash
npm install
npm start
```

Lưu ý: Project dùng Puppeteer để render trang động, nên `npm install` sẽ tải Chromium lần đầu.
Nếu muốn dùng trình duyệt đã cài sẵn, đặt biến môi trường `PUPPETEER_EXECUTABLE_PATH` và `PUPPETEER_SKIP_DOWNLOAD=1`.

## Tùy chọn

Script ho tro doi URL bat dau, so trang crawl, pham vi subject va thu muc dau ra qua bien moi truong:

```bash
$env:CRAWL_START_URL='https://mathformulaatlas.com/subjects/algebra/college-algebra/'
$env:CRAWL_MAX_PAGES='25'
$env:CRAWL_SCOPE_PATH_PREFIX='/subjects/algebra/'
$env:CRAWL_OUTPUT_DIR='formulas'
$env:CRAWL_FORMULASHEET_URLS='https://formulasheet.com/#q|l|1228'
npm start
```

- `CRAWL_SCOPE_PATH_PREFIX`: gioi han crawl trong cung mot nhanh subject. Neu bo trong, script tu suy ra tu `CRAWL_START_URL`.
- `CRAWL_FORMULASHEET_URLS`: danh sach URL formulasheet (phan cach boi dau phay) de lay LaTeX tu `pre.resultsSrc`.
## Xuat HTML/PDF tu dataset.json

Sau khi crawl xong, co the doc lai `formulas/dataset.json` de xuat HTML/PDF:

```bash
npm run export
```

Output:
- `formulas/preview.html`: xem cong thuc va label tren trinh duyet
- `formulas/preview.pdf`: PDF in tu HTML (dung MathJax qua CDN)

Neu muon chi tao HTML (khong tao PDF), dat:

```bash
$env:EXPORT_PDF_ENABLED='0'
npm run export
```

Co the chi dinh duong dan:

```bash
$env:EXPORT_INPUT='formulas\\dataset.json'
$env:EXPORT_OUTPUT_DIR='formulas'
$env:EXPORT_HTML='formulas\\preview.html'
$env:EXPORT_PDF='formulas\\preview.pdf'
npm run export
``` 

## Kết quả

- `formulas/dataset.tex`: tap cong thuc tong hop voi comment marker co cau truc co the tach record de dua vao parser
- `formulas/dataset.json`: metadata day du cua lan crawl, danh sach trang va danh sach cong thuc
- `formulas/dataset.jsonl`: moi dong la mot record cong thuc, hop voi pipeline ML va batch processing
- `formulas/*.tex`: file theo trang voi ten gon hon nhu `college-algebra.tex`, `linear-algebra.tex`

## Cách trích xuất

Script uu tien doc noi dung trong vung `entry-content` cua bai viet WordPress va tach cac block LaTeX dang `\[ ... \]` tu paragraph hoac list item. Neu mot trang khong co block nay, script se fallback sang cac node toan hoc tong quat nhu `data-tex`, `annotation[encoding="application/x-tex"]`, `script[type^="math/tex"]` hoac text math da render.

Script khong chi lay link trong noi dung bai viet ma con doi them link trong `main` va `body`, sau do loc theo `CRAWL_SCOPE_PATH_PREFIX` de mo rong crawl trong cung subject ma khong tran sang subject khac.

## Dinh dang phu hop cho ML

- Trong `dataset.json`, moi cong thuc co cac truong on dinh nhu `formulaId`, `pageSlug`, `subjectSlug`, `subjectPath`, `section`, `subsection`, `source`, `indexInPage`, `indexGlobal`, `latex`.
- Trong `dataset.jsonl`, moi dong la mot object JSON doc lap de import vao pandas, Spark, Hugging Face datasets hoac vector pipeline.
- Trong `dataset.tex`, moi cong thuc duoc bao quanh boi marker comment `% formula_record_start` va `% formula_record_end` de parser co the cat block an toan.
