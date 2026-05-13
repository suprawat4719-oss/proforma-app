# Pro Forma Financial Statement App
S.P.N. Corporate Services Co., Ltd.

## วิธีรัน

### 1. ติดตั้ง Python dependencies
```bash
cd proforma-app
pip install -r requirements.txt
```

### 2. รัน PDF Server (Flask)
```bash
python server.py
# Server จะรันที่ http://localhost:5055
```

### 3. เปิด Frontend
เปิดไฟล์ `index.html` ใน browser โดยตรง (ไม่ต้องใช้ server)

```
file:///D:/xx2/proforma-app/index.html
```

## ฟีเจอร์

- **Dashboard**: รายการบริษัททั้งหมด พร้อมปีที่มีข้อมูล
- **ส่วน A (ปีฐาน)**: กรอกตัวเลขจากงบจริง
- **ส่วน B (ร่างปรับใหม่)**: ปรับตัวเลข Pro Forma พร้อมคำนวณ real-time
- **3 โหมดภาษี**: Auto / Target Tax → REV / Target Tax → COGS
- **Cash Auto-Balance**: คำนวณเงินสดให้งบดุลโดยอัตโนมัติ
- **KPI Panel**: Gross Margin, Net Margin, D/E, Current Ratio
- **Export Excel**: 3 sheets (P&L, Balance Sheet, อัตราส่วน)
- **Export PDF**: งบการเงินรูปแบบจริง ผ่าน wkhtmltopdf

## โครงสร้าง

```
proforma-app/
├── index.html          # Frontend SPA (Vanilla JS)
├── server.py           # Flask PDF server (port 5055)
├── templates/
│   └── statement.html  # Jinja2 template งบการเงิน
├── requirements.txt
└── README.md
```

## Firebase

ใช้ project `advance-tracker-cadf5` (shared กับ advance-tracker.html)

Collections:
- `proforma_companies` — ข้อมูลบริษัท
- `proforma_years` — ข้อมูลงบแต่ละปี (key: `{companyId}_{year}`)

## Health Check

```bash
curl http://localhost:5055/api/health
```
