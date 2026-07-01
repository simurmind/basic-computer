# شبیه‌ساز کامپیوتر پایه (Basic Computer Simulator)

شبیه‌سازی کامل معماری Mano's Basic Computer — بک‌اند Flask و فرانت‌اند داشبورد وب.

## اجرا

```bash
pip install -r requirements.txt
python app.py
```

سپس آدرس زیر را در مرورگر باز کنید:

```
http://127.0.0.1:5000
```

## ساختار پروژه

```
app.py                     نقطه‌ی ورود Flask و تعریف API
simulator/
  memory.py                کلاس Memory (4096 × 16-bit)
  bus.py                   کلاس Bus (باس مشترک)
  cpu.py                   کلاس CPU (رجیسترها و چرخه‌ی دستور)
  assembler.py             اسمبلر دو-پاسی
templates/index.html       صفحه‌ی داشبورد
static/css/style.css       استایل
static/js/app.js           منطق فرانت‌اند و فراخوانی API
```

## API

| Method | Route              | توضیح                                   |
|--------|--------------------|------------------------------------------|
| POST   | /api/assemble      | تبدیل کد اسمبلی به کد ماشین              |
| POST   | /api/load          | بارگذاری کد ماشین در حافظه و ریست CPU    |
| POST   | /api/step          | اجرای یک گام (micro-step) از چرخه دستور  |
| POST   | /api/run           | اجرای کامل برنامه تا HLT                 |
| POST   | /api/reset         | ریست کامل سیستم                          |
| GET    | /api/state         | دریافت وضعیت فعلی رجیسترها                |
| GET    | /api/memory        | دامپ بازه‌ای از حافظه                     |
| POST   | /api/input         | شبیه‌سازی ورودی دستگاه خارجی (INPR/FGI)   |
