"""
Fill Arabic msgstr entries in locale/ar/LC_MESSAGES/django.po (stdlib only).
Run from project root: python tools/fill_ar_translations.py
Then: msgfmt -o locale/ar/LC_MESSAGES/django.mo locale/ar/LC_MESSAGES/django.po
"""
from __future__ import annotations

import re
from pathlib import Path


def po_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


# UI + model verbose strings used in the MVP
AR: dict[str, str] = {
    "Accounts": "الحسابات",
    "Full name": "الاسم الكامل",
    "Role": "الدور",
    "Profile active": "الملف الشخصي مفعّل",
    "Login enabled": "تسجيل الدخول مفعّل",
    "Management": "الإدارة",
    "Employee": "موظف",
    "full name": "الاسم الكامل",
    "role": "الدور",
    "profile active": "الملف الشخصي مفعّل",
    "user profile": "ملف المستخدم",
    "user profiles": "ملفات المستخدمين",
    "Employees & users": "الموظفون والمستخدمون",
    "User created.": "تم إنشاء المستخدم.",
    "Create user": "إنشاء مستخدم",
    "User updated.": "تم تحديث المستخدم.",
    "Edit user": "تعديل المستخدم",
    "Sky report matching": "مطابقة كشف سكاي",
    "Estimated deficit (Sky)": "العجز المقدّر (سكاي)",
    "Settlements (excluded)": "تسويات (مستثناة من العجز)",
    "In Sky, not in system": "في سكاي وغير موجود في النظام",
    "In system, not in Sky": "في النظام وغير موجود في سكاي",
    "Sales differences (Sky vs system)": "فروقات المبيعات (سكاي مقابل النظام)",
    "Balance anomalies": "شواذ الرصيد",
    "Sky cost": "تكلفة سكاي",
    "End balance not found in Sky report.": "لم يُعثر على رصيد ختامي في تقرير سكاي.",
    "Sky report processed (%(rows)s rows).": "تمت معالجة تقرير سكاي (%(rows)s صف).",
    "Could not fetch Sky report: %(error)s": "تعذّر جلب تقرير سكاي: %(error)s",
    "Could not run Sky matching: %(error)s": "تعذّر تشغيل مطابقة سكاي: %(error)s",
    "Sky report matching is only available for Sky.": "مطابقة كشف سكاي متاحة لشركة سكاي فقط.",
    "1 · Review first": "1 · راجع أولاً",
    "2 · Cost differences": "2 · فروقات التكلفة",
    "3 · Info only": "3 · للمعلومة فقط",
    "Review first": "راجع أولاً",
    "Cost differences": "فروقات التكلفة",
    "Info only": "للمعلومة فقط",
    "Missing / wrong supplier": "ناقص أو مورّد خاطئ",
    "Sky vs system amount": "مبلغ سكاي مقابل النظام",
    "Settlements (not in deficit)": "تسويات (خارج العجز)",
    "Estimated deficit": "العجز المقدّر",
    "Sky rows": "صفوف سكاي",
    "Why": "السبب",
    "Compare Sky vs system lines": "قارن أسطر سكاي والنظام",
    "Sky charges": "خصومات سكاي",
    "System sales": "مبيعات النظام",
    "No system sale in this period.": "لا مبيع في النظام لهذه الفترة.",
    "Nothing in the review-first queue.": "لا يوجد شيء في طابور المراجعة الأولى.",
    "No informational items.": "لا عناصر للمعلومة.",
    "Section total": "مجموع القسم",
    "Absolute gap total": "مجموع الفروقات المطلقة",
    "Often eSIM fee or package cost mismatch — compare lines below.": "غالباً فرق رسوم eSIM أو سعر الباقة — قارن الأسطر بالأسفل.",
    "Below this amount counts as matched. Use 0 to show all.": "تحت هذا المبلغ يُحسب متطابقاً. استخدم 0 لعرض كل الفروقات.",
    "Choose a period, then run matching. Live Sky charges are compared to sales in the system.": "حدد الفترة ثم شغّل المطابقة. تُقارن خصومات سكاي الحية بمبيعات النظام.",
    "Set the date range": "حدد نطاق التاريخ",
    "From / to — the days you want to review.": "من / إلى — الأيام التي تريد مراجعتها.",
    "Fetches the Sky balance report for that period.": "يجلب تقرير رصيد سكاي لتلك الفترة.",
    "Review red and amber first": "راجع الأحمر والبرتقالي أولاً",
    "Open one tab at a time; each row explains the gap.": "افتح تبويباً واحداً كل مرة؛ كل صف يوضح سبب الفرق.",
    "Start with the red/amber cards after matching. Open one tab at a time. Each number shows why it flagged and a Sky vs system line compare.": "بعد المطابقة ابدأ بالبطاقات الحمراء/البرتقالية. افتح تبويباً واحداً كل مرة. كل رقم يوضح السبب ومقارنة أسطر سكاي والنظام.",
    "These usually need a sale recorded (or a correction).": "عادة تحتاج تسجيل مبيع (أو تصحيح).",
    "Sale exists locally but Sky report has no charge for this number in the period.": "المبيع موجود محلياً لكن تقرير سكاي بلا خصم لهذا الرقم في الفترة.",
    "Open “Compare Sky vs system lines” on a row to see eSIM splits and package costs (like 75 vs 80).": "افتح «قارن أسطر سكاي والنظام» على الصف لترى تقسيم eSIM وتكاليف الباقة (مثل 75 مقابل 80).",
    "Settlements are charge + disconnect cycles. They are shown so you do not treat them as missing sales, and they do not increase estimated deficit.": "التسويات هي شحن + فصل. تُعرض حتى لا تُحسب كمبيعات ناقصة، ولا تزيد العجز المقدّر.",
    "Within the minimum difference — usually no action.": "ضمن الحد الأدنى للفرق — عادة لا يلزم إجراء.",
    "In Sky for %(amount)s — no matching sale in the system for this period.": "في سكاي بمبلغ %(amount)s — لا مبيع مطابق في النظام لهذه الفترة.",
    "In the system for %(amount)s — not found on the Sky balance report.": "في النظام بمبلغ %(amount)s — غير موجود في تقرير رصيد سكاي.",
    "Charged on Sky (%(sky)s) but logged under %(suppliers)s.": "مخصوم في سكاي (%(sky)s) لكنه مسجّل تحت %(suppliers)s.",
    "Charge + disconnect settlement on Sky. Informational only — not included in estimated deficit.": "تسوية شحن+فصل في سكاي. للمعلومة فقط — لا تدخل في العجز المقدّر.",
    "Sky cost %(sky)s is higher than system %(rd)s by %(gap)s.": "تكلفة سكاي %(sky)s أعلى من النظام %(rd)s بمقدار %(gap)s.",
    "System cost %(rd)s is higher than Sky %(sky)s by %(gap)s.": "تكلفة النظام %(rd)s أعلى من سكاي %(sky)s بمقدار %(gap)s.",
    "Sky and system costs match within the minimum difference.": "تكاليف سكاي والنظام متطابقة ضمن الحد الأدنى للفرق.",
    "Upload the Layan charges Excel report. After matching, use the priority cards and open one tab at a time — same review flow as Sky, without live portal fetch.": "ارفع كشف ليان (Excel). بعد المطابقة استخدم بطاقات الأولوية وافتح تبويباً واحداً كل مرة — نفس أسلوب سكاي بدون سحب حي من البوابة.",
    "Layan vs system amount": "مبلغ ليان مقابل النظام",
    "3 · Settlements": "3 · التسويات",
    "Included in estimated deficit": "داخلة في العجز المقدّر",
    "report rows": "صفوف الكشف",
    "Compare Layan vs system lines": "قارن أسطر ليان والنظام",
    "Layan report lines": "أسطر كشف ليان",
    "Open “Compare Layan vs system lines” on a row to see report lines and local sales.": "افتح «قارن أسطر ليان والنظام» لرؤية أسطر الكشف والمبيعات المحلية.",
    "Settlements are charge + disconnect cycles. For Layan, retained settlement amounts are still included in estimated deficit (unlike Sky).": "التسويات هي شحن+فصل. في ليان ما زال مبلغ التسوية المحفوظ يدخل العجز المقدّر (بخلاف سكاي).",
    "In Layan for %(amount)s — no matching sale in the system for this period.": "في ليان بمبلغ %(amount)s — لا مبيع مطابق في النظام لهذه الفترة.",
    "In the system for %(amount)s — not found on the uploaded Layan report.": "في النظام بمبلغ %(amount)s — غير موجود في كشف ليان المرفوع.",
    "Charged on Layan (%(layan)s) but logged under %(suppliers)s.": "مخصوم في ليان (%(layan)s) لكنه مسجّل تحت %(suppliers)s.",
    "Charge + disconnect settlement on Layan. Review retained amount; it is included in estimated deficit.": "تسوية شحن+فصل في ليان. راجع المبلغ المحفوظ؛ وهو داخل العجز المقدّر.",
    "Layan cost %(layan)s is higher than system %(rd)s by %(gap)s.": "تكلفة ليان %(layan)s أعلى من النظام %(rd)s بمقدار %(gap)s.",
    "System cost %(rd)s is higher than Layan %(layan)s by %(gap)s.": "تكلفة النظام %(rd)s أعلى من ليان %(layan)s بمقدار %(gap)s.",
    "Layan and system costs match within the minimum difference.": "تكاليف ليان والنظام متطابقة ضمن الحد الأدنى للفرق.",
    "Settlements": "التسويات",
    "hidden": "مخفي",
    "Upload the Layan charges Excel report. After matching, use the priority cards and open one tab at a time — same review flow as Sky, without live portal fetch.": "ارفع كشف ليان (Excel). بعد المطابقة استخدم بطاقات الأولوية وافتح تبويباً واحداً كل مرة — نفس أسلوب سكاي بدون سحب حي من البوابة.",
    "Layan vs system amount": "مبلغ ليان مقابل النظام",
    "3 · Settlements": "3 · التسويات",
    "Included in estimated deficit": "داخلة في العجز المقدّر",
    "report rows": "صفوف الكشف",
    "Compare Layan vs system lines": "قارن أسطر ليان والنظام",
    "Layan report lines": "أسطر كشف ليان",
    "Open “Compare Layan vs system lines” on a row to see report lines and local sales.": "افتح «قارن أسطر ليان والنظام» لرؤية أسطر الكشف والمبيعات المحلية.",
    "Settlements are charge + disconnect cycles. For Layan, retained settlement amounts are still included in estimated deficit (unlike Sky).": "التسويات هي شحن+فصل. في ليان ما زال مبلغ التسوية المحفوظ يدخل العجز المقدّر (بخلاف سكاي).",
    "In Layan for %(amount)s — no matching sale in the system for this period.": "في ليان بمبلغ %(amount)s — لا مبيع مطابق في النظام لهذه الفترة.",
    "In the system for %(amount)s — not found on the uploaded Layan report.": "في النظام بمبلغ %(amount)s — غير موجود في كشف ليان المرفوع.",
    "Charged on Layan (%(layan)s) but logged under %(suppliers)s.": "مخصوم في ليان (%(layan)s) لكنه مسجّل تحت %(suppliers)s.",
    "Charge + disconnect settlement on Layan. Review retained amount; it is included in estimated deficit.": "تسوية شحن+فصل في ليان. راجع المبلغ المحفوظ؛ وهو داخل العجز المقدّر.",
    "Layan cost %(layan)s is higher than system %(rd)s by %(gap)s.": "تكلفة ليان %(layan)s أعلى من النظام %(rd)s بمقدار %(gap)s.",
    "System cost %(rd)s is higher than Layan %(layan)s by %(gap)s.": "تكلفة النظام %(rd)s أعلى من ليان %(layan)s بمقدار %(gap)s.",
    "Layan and system costs match within the minimum difference.": "تكاليف ليان والنظام متطابقة ضمن الحد الأدنى للفرق.",
    "name": "الاسم",
    "opening balance": "الرصيد الافتتاحي",
    "current balance": "الرصيد الحالي",
    "notes": "ملاحظات",
    "active": "نشط",
    "company": "الشركة",
    "companies": "الشركات",
    "cost price": "سعر التكلفة",
    "default sell price": "سعر البيع الافتراضي",
    "product": "المنتج",
    "products": "المنتجات",
    "Companies": "الشركات",
    "Company saved.": "تم حفظ الشركة.",
    "New company": "شركة جديدة",
    "Company updated.": "تم تحديث الشركة.",
    "Edit company": "تعديل الشركة",
    "Products": "المنتجات",
    "Product saved.": "تم حفظ المنتج.",
    "New product": "منتج جديد",
    "Product updated.": "تم تحديث المنتج.",
    "Edit product": "تعديل المنتج",
    "Access denied": "الوصول مرفوض",
    "title": "العنوان",
    "category": "التصنيف",
    "amount": "المبلغ",
    "Amount": "المبلغ",
    "date": "التاريخ",
    "created by": "أنشأه",
    "expense": "مصروف",
    "expenses": "المصروفات",
    "Expenses": "المصروفات",
    "Expense saved.": "تم حفظ المصروف.",
    "New expense": "مصروف جديد",
    "Expense updated.": "تم تحديث المصروف.",
    "Edit expense": "تعديل المصروف",
    "Date from": "من تاريخ",
    "Date to": "إلى تاريخ",
    "Expense report": "تقرير المصروفات",
    "Dashboard": "لوحة التحكم",
    "Profit report": "تقرير الأرباح",
    "Sales report": "تقرير المبيعات",
    "Deposit recorded.": "تم تسجيل الإيداع.",
    "Adjustment recorded.": "تم تسجيل التسوية.",
    "Company report": "تقرير الشركة",
    "Company": "الشركة",
    "Choose company": "اختر الشركة",
    "Product": "المنتج",
    "Choose product": "اختر المنتج",
    "Phone or shipment number": "رقم الهاتف أو الشحنة",
    "Selling price": "سعر البيع",
    "Payment method": "طريقة الدفع",
    "Choose payment method": "اختر طريقة الدفع",
    "Payer name": "اسم الدافع",
    "Customer name": "اسم العميل",
    "Notes": "ملاحظات",
    "Selected product does not belong to the company.": "المنتج المختار لا يتبع الشركة المحددة.",
    "Status": "الحالة",
    "All": "الكل",
    "Signed adjustment (+/-)": "تسوية موقعة (+/-)",
    "payment method": "طريقة الدفع",
    "payment methods": "طرق الدفع",
    "Pending": "معلّق",
    "Paid": "مدفوع",
    "Cancelled": "ملغى",
    "phone or shipment number": "رقم الهاتف أو الشحنة",
    "customer name": "اسم العميل",
    "payer name": "اسم الدافع",
    "actual selling price": "سعر البيع الفعلي",
    "cost price (snapshot)": "سعر التكلفة (لقطة)",
    "profit (snapshot)": "الربح (لقطة)",
    "status": "الحالة",
    "created at": "تاريخ الإنشاء",
    "updated at": "تاريخ التحديث",
    "marked paid at": "تاريخ التعليم كمدفوع",
    "marked paid by": "عُلِّم كمدفوع بواسطة",
    "cancelled at": "تاريخ الإلغاء",
    "cancelled by": "ألغاه",
    "sale": "عملية بيع",
    "sales": "المبيعات",
    "Deposit": "إيداع",
    "Deduction": "خصم",
    "Adjustment": "تسوية",
    "Reversal": "عكس حركة",
    "Sale": "بيع",
    "Manual": "يدوي",
    "Opening balance": "الرصيد الافتتاحي",
    "Cancellation": "إلغاء",
    "type": "النوع",
    "reference type": "نوع المرجع",
    "reference id": "معرّف المرجع",
    "balance transaction": "حركة رصيد",
    "balance transactions": "حركات الرصيد",
    "Sale recorded successfully.": "تم تسجيل البيع بنجاح.",
    "New sale": "بيع جديد",
    "Sales": "المبيعات",
    "Pending payments": "المدفوعات المعلّقة",
    "Marked as paid.": "تم التعليم كمدفوع.",
    "Sale cancelled and supplier balance restored.": "تم إلغاء البيع واسترجاع رصيد المورّد.",
    "Payment methods": "طرق الدفع",
    "Payment method saved.": "تم حفظ طريقة الدفع.",
    "New payment method": "طريقة دفع جديدة",
    "Payment method updated.": "تم تحديث طريقة الدفع.",
    "Edit payment method": "تعديل طريقة الدفع",
    "Sign in": "تسجيل الدخول",
    "Recharge Desk": "المحاسب الهامل",
    "Please correct the errors below.": "يرجى تصحيح الأخطاء أدناه.",
    "Save": "حفظ",
    "Cancel": "إلغاء",
    "Users": "المستخدمون",
    "Username": "اسم المستخدم",
    "Active": "نشط",
    "Yes": "نعم",
    "No": "لا",
    "Edit": "تعديل",
    "No users.": "لا يوجد مستخدمون.",
    "Sales entry": "إدخال مبيعات",
    "Log out": "تسجيل الخروج",
    "Name": "الاسم",
    "Opening": "افتتاحي",
    "Current balance": "الرصيد الحالي",
    "Report": "تقرير",
    "No companies.": "لا توجد شركات.",
    "Cost": "التكلفة",
    "Default sell": "البيع الافتراضي",
    "No products.": "لا توجد منتجات.",
    "You do not have permission to view this page.": "ليس لديك صلاحية لعرض هذه الصفحة.",
    "Go home": "الرئيسية",
    "Date": "التاريخ",
    "Title": "العنوان",
    "Category": "التصنيف",
    "By": "بواسطة",
    "No expenses.": "لا توجد مصروفات.",
    "Category breakdown and totals": "التصنيفات والإجماليات",
    "Apply": "تطبيق",
    "Reset": "إعادة ضبط",
    "Total profit (same date filter)": "إجمالي الربح (نفس نطاق التاريخ)",
    "Total expenses (filtered)": "إجمالي المصروفات (بعد التصفية)",
    "Net profit": "صافي الربح",
    "Profit minus expenses": "الربح ناقص المصروفات",
    "By category": "حسب التصنيف",
    "No data.": "لا توجد بيانات.",
    "Rows": "الصفوف",
    "Supplier statement & internal ledger": "كشف المورّد وسجل الرصيد الداخلي",
    "Back": "رجوع",
    "Total deposits": "إجمالي الإيداعات",
    "Consumed (sales)": "المستهلك (مبيعات)",
    "Reversals (cancellations)": "العكس (إلغاءات)",
    "Adjustments": "التسويات",
    "Sales count (non-cancelled)": "عدد المبيعات (غير الملغاة)",
    "Total sell": "إجمالي البيع",
    "Total profit": "إجمالي الربح",
    "Manual balance top-up": "تعبئة رصيد يدوية",
    "Save deposit": "حفظ الإيداع",
    "Balance adjustment": "تسوية الرصيد",
    "Save adjustment": "حفظ التسوية",
    "Sales detail": "تفاصيل المبيعات",
    "When": "متى",
    "Ref": "المرجع",
    "Sell": "البيع",
    "Profit": "الربح",
    "No sales.": "لا توجد مبيعات.",
    "Balance ledger": "سجل الرصيد",
    "Type": "النوع",
    "Reference": "المرجع",
    "No ledger rows.": "لا توجد حركات في السجل.",
    "Operational snapshot": "لمحة تشغيلية",
    "Today's sales": "مبيعات اليوم",
    "Volume": "الحجم",
    "Today's profit": "ربح اليوم",
    "All-time profit": "الربح الكلي",
    "All-time expenses": "المصروفات الكلية",
    "Net profit (all time)": "صافي الربح (كلّي)",
    "This month profit": "ربح هذا الشهر",
    "Net (month)": "الصافي (شهري)",
    "Supplier balances": "أرصدة المورّدين",
    "No companies yet.": "لا توجد شركات بعد.",
    "Recent activity": "النشاط الأخير",
    "No sales yet.": "لا توجد مبيعات بعد.",
    "Excludes cancelled sales": "باستثناء المبيعات الملغاة",
    "By company": "حسب الشركة",
    "Count": "العدد",
    "By payment method": "حسب طريقة الدفع",
    "Method": "الطريقة",
    "By employee": "حسب الموظف",
    "By product": "حسب المنتج",
    "Daily profit trend": "اتجاه الربح اليومي",
    "Day": "اليوم",
    "Monthly profit trend": "اتجاه الربح الشهري",
    "Month": "الشهر",
    "Filter, review, and export-friendly table layout": "تصفية ومراجعة وجدول مناسب للتصدير",
    "Filtered profit (excl. cancelled)": "الربح بعد التصفية (باستثناء الملغاة)",
    "Filtered volume": "الحجم بعد التصفية",
    "Filtered rows": "الصفوف بعد التصفية",
    "Results": "النتائج",
    "Copy/paste friendly": "مناسب للنسخ",
    "No rows.": "لا توجد صفوف.",
    "optional": "اختياري",
    "Save sale": "حفظ البيع",
    "Recent entries": "آخر الإدخالات",
    "No recent entries yet.": "لا توجد إدخالات حديثة بعد.",
    "Mark paid": "تعليم كمدفوع",
    "Cancel this sale?": "إلغاء هذا البيع؟",
    "New": "جديد",
    "Inactive": "غير نشط",
    "No payment methods.": "لا توجد طرق دفع.",
    "All sales": "كل المبيعات",
    "Payer": "الدافع",
    "No pending sales.": "لا توجد مبيعات معلّقة.",
    "Color theme": "مظهر الألوان",
    "Light theme": "الوضع الفاتح",
    "Dark theme": "الوضع الداكن",
    "Light": "فاتح",
    "Dark": "داكن",
    "Show more": "عرض المزيد",
    "Choose a company to see products.": "اختر شركة لعرض المنتجات.",
    "No active companies.": "لا توجد شركات نشطة.",
    "Lines for disconnect": "أرقام للفصل",
    "Idle threshold": "عتبة عدم النشاط",
    "Days without a new sale entry": "أيام من دون إدخال بيع جديد",
    "Save threshold": "حفظ العتبة",
    "Saved on your user profile until you change it again.": "يُحفَظ في ملف المستخدم حتى تغيّره مرة أخرى.",
    "Number / reference": "الرقم / المرجع",
    "SIM / chip": "الشريحة / رقم الشريحة",
    "Last sale entry": "آخر إدخال بيع",
    "Customer or payer": "الزبون أو الدافع",
    "Days since last sale": "أيام منذ آخر بيع",
    "Remove this line from the report only? Sales in the system are not deleted; the number can appear again if it becomes idle.": (
        "إزالة هذا السطر من التقرير فقط؟ لا تُحذف المبيعات من النظام؛ قد يظهر الرقم مجدداً إذا عاد راكداً."
    ),
    "No lines match this threshold.": "لا توجد خطوط تطابق هذه العتبة.",
    "Threshold saved.": "تم حفظ العتبة.",
    "Could not save threshold.": "تعذّر حفظ العتبة.",
    "Line updated.": "تم تحديث الخط.",
    "Please correct the errors below.": "يرجى تصحيح الأخطاء أدناه.",
    "Removed from this list.": "أُزيل من هذه القائمة.",
    "Edit line": "تعديل الخط",
    "Back to list": "العودة للقائمة",
    "Line": "الخط",
    # System settings (recent)
    "Approval workflows": "سير الموافقات",
    "Management panel defaults": "افتراضيات لوحة الإدارة",
    "Sales entry screen": "شاشة إدخال المبيعات",
    "System (match device)": "تلقائي (حسب الجهاز)",
    "Allow creating customers from sales entry": "السماح بإنشاء زبائن من شاشة المبيعات",
    "When off, on-account sales require an existing customer created from the Customers screen.": (
        "عند الإيقاف، تتطلب مبيعات الآجل زبوناً موجوداً مسبقاً من شاشة الزبائن."
    ),
    "Require approval for debt requests": "طلبات الدين تتطلب موافقة",
    "Require approval for settlement requests": "طلبات التسديد تتطلب موافقة",
    "Require approval for payment requests": "طلبات الدفع تتطلب موافقة",
    "Show record payment on sales entry": "عرض تسجيل الدفعة في شاشة المبيعات",
    "Show payment to employee on sales entry": "عرض دفع لدى موظف في شاشة المبيعات",
    "Used on first visit before the user picks a language or theme. Personal choices in the header still override these defaults.": (
        "تُستخدم في الزيارة الأولى قبل اختيار المستخدم للغة أو الثيم. الاختيارات الشخصية في الشريط العلوي تبقى لها الأولوية."
    ),
    "Could not read clipboard. Allow paste permission or use Ctrl+V.": (
        "تعذّر قراءة الحافظة. اسمح بإذن اللصق أو استخدم Ctrl+V."
    ),
    "Default language": "اللغة الافتراضية",
    "Default theme": "الثيم الافتراضي",
    "system settings": "إعدادات النظام",
    "System settings": "إعدادات النظام",
    "System settings updated.": "تم تحديث إعدادات النظام.",
    "General": "عام",
    "Database": "قواعد البيانات",
    "Database backup": "نسخة احتياطية لقاعدة البيانات",
    "Download a full copy of the application database or restore from a file you saved earlier. Only management users can use this screen.": (
        "نزّل نسخة كاملة من قاعدة بيانات التطبيق أو استعد من ملف حفظته سابقاً. هذه الشاشة للإدارة فقط."
    ),
    "Engine": "المحرك",
    "Database name": "اسم قاعدة البيانات",
    "Download backup": "تنزيل النسخة الاحتياطية",
    "Download database": "تنزيل قاعدة البيانات",
    "Restore from backup": "استيراد من نسخة احتياطية",
    "Import database": "استيراد قاعدة البيانات",
    "Database restored from backup.": "تم استيراد قاعدة البيانات من النسخة الاحتياطية.",
    "I understand this will erase existing data and replace it with the backup.": (
        "أفهم أن هذا سيحذف البيانات الحالية ويستبدلها بالنسخة الاحتياطية."
    ),
    "Close": "إغلاق",
    "Choose a payment method tile.": "اختر بلاطة طريقة الدفع.",
    "Turn a switch off to skip management approval for that queue. Sales and balances apply immediately.": (
        "عطّل المفتاح لتجاوز موافقة الإدارة على هذا الطابور. تُسجَّل المبيعات والأرصدة فوراً."
    ),
    "On-account sales posted to customers or distributors. When off, they are recorded on the customer account immediately.": (
        "مبيعات الآجل المسجّلة للزبائن أو الموزّعين. عند الإيقاف، تُسجَّل على حساب الزبون مباشرة."
    ),
    "Customer settlement submissions from the sales screen. When off, the payment applies to the balance immediately.": (
        "طلبات تسديد الزبون من شاشة المبيعات. عند الإيقاف، تُطبَّق الدفعة على الرصيد فوراً."
    ),
    "Cash sales awaiting “mark paid”. When off, new cash sales are marked paid as soon as they are saved.": (
        "مبيعات نقدية بانتظار «تعليم مدفوع». عند الإيقاف، تُعلَّم المبيعات النقدية الجديدة مدفوعة عند الحفظ."
    ),
    "Controls what employees see and how sales are recorded on the entry form.": (
        "يتحكّم فيما يراه الموظفون وكيف تُسجَّل المبيعات في نموذج الإدخال."
    ),
    "When off, on-account sales require an existing customer — create customers from the Customers screen.": (
        "عند الإيقاف، تتطلب مبيعات الآجل زبوناً موجوداً — أنشئ الزبائن من شاشة الزبائن."
    ),
    "When off, on-account sales post to the customer immediately without awaiting management approval.": (
        "عند الإيقاف، تُسجَّل مبيعات الآجل على حساب الزبون فوراً دون انتظار موافقة الإدارة."
    ),
    "When off, customer settlement submissions apply to the balance immediately without management approval.": (
        "عند الإيقاف، تُطبَّق طلبات تسديد الزبون على الرصيد فوراً دون موافقة الإدارة."
    ),
    "When off, cash sales are marked paid immediately without appearing in pending payments.": (
        "عند الإيقاف، تُعلَّم المبيعات النقدية مدفوعة فوراً دون الظهور في المدفوعات المعلّقة."
    ),
    "Debt requests require approval": "طلبات الدين تتطلب موافقة",
    "Settlement requests require approval": "طلبات التسديد تتطلب موافقة",
    "Payment requests require approval": "طلبات الدفع تتطلب موافقة",
    "Create customers from sales entry": "إنشاء زبائن من شاشة المبيعات",
    "Record payment button on sales entry": "زر تسجيل الدفعة في شاشة المبيعات",
    "Payment to employee button on sales entry": "زر دفع لدى موظف في شاشة المبيعات",
    "When off, the payment-to-employee option is hidden on the sales entry screen.": (
        "عند الإيقاف، يُخفى خيار الدفع لدى موظف من شاشة إدخال المبيعات."
    ),
    "Payment to employee is disabled on the sales screen.": (
        "الدفع لدى موظف معطّل في شاشة المبيعات."
    ),
    "Recorded on account and posted to the customer.": "تم التسجيل على الحساب وإضافته للزبون مباشرة.",
    "Sale recorded and marked paid.": "تم تسجيل البيع واعتباره مدفوعاً.",
    "Payment recorded on the customer account.": "تم تسجيل الدفعة على حساب الزبون.",
    "Recording payments from the sales screen is disabled.": "تسجيل الدفعات من شاشة المبيعات معطّل.",
    "Adjustment amount cannot be zero.": "مبلغ التسوية لا يمكن أن يكون صفراً.",
    "Testing correction": "تصحيح للاختبار",
    "Record": "تسجيل",
    "Filter": "تصفية",
    "submitted by": "مُقدَّم بواسطة",
    "reject reason": "سبب الرفض",
    "Employees": "الموظفين",
    "Employees & payroll": "الموظفون والرواتب",
    "employee": "موظف",
    "employees": "الموظفين",
    "monthly salary": "الراتب الشهري",
    "Salary accrual": "استحقاق راتب",
    "Sales payment received": "دفعة مبيعات مستلمة",
    "Movement statement": "كشف حركات",
    "Received sales payments": "دفعات مبيعات مستلمة",
    "Payment to employee": "دفع لدى موظف",
    "Payment to employee: %(name)s": "دفع لدى موظف: %(name)s",
    "payment to employee": "دفع لدى موظف",
    "Employee who received payment": "الموظف الذي استلم الدفعة",
    "Employee recipient": "موظف المستلم",
    "employee recipient": "موظف المستلم",
    "Add employee": "إضافة موظف",
    "Employee saved.": "تم حفظ الموظف.",
    "Employee updated.": "تم تحديث الموظف.",
    "New employee": "موظف جديد",
    "Edit employee": "تعديل موظف",
    "Run salary accrual": "تشغيل استحقاق الرواتب",
    "Accrue salaries for month": "استحقاق رواتب الشهر",
    "Payroll accounts, balances, and salary accrual.": "حسابات الرواتب والأرصدة واستحقاق الراتب.",
    "Shop owes the employee.": "المحل مدين للموظف.",
    "Employee holds cash for the shop.": "الموظف يحتفظ بمبلغ نيابة عن المحل.",
    "Select the employee who received the payment.": "اختر الموظف الذي استلم الدفعة.",
    "You can only edit or delete your last %(count)s entries.": "يمكنك تعديل أو حذف آخر %(count)s إدخالات فقط.",
    "Sales you entered. You can edit or delete only your last 10 entries.": "مبيعاتك المُدخلة. يمكنك تعديل أو حذف آخر 10 إدخالات فقط.",
    "Salaries": "رواتب",
    "Salary: %(name)s — %(month)s": "راتب: %(name)s — %(month)s",
    "Auto-created from salary accrual.": "أُنشئ تلقائياً من استحقاق الراتب.",
    "You are not registered as a payroll employee.": "حسابك غير مسجّل في نظام الموظفين.",
    "Payment will be recorded to your account: %(name)s": "ستُسجّل الدفعة في حسابك: %(name)s",
    "Your balance:": "رصيدك:",
    "Sale recorded; payment credited to employee ledger.": "تم تسجيل البيع؛ أُضيفت الدفعة إلى كشف الموظف.",
    "Sale recorded; employee payment awaits management approval.": "تم تسجيل البيع؛ دفعة الموظف بانتظار موافقة الإدارة.",
    "No payroll employees configured.": "لم يُعدّ موظفون في نظام الرواتب.",
    "Salary accrual complete: %(count)s new entries for %(month)s.": "اكتمل استحقاق الرواتب: %(count)s قيداً جديداً لشهر %(month)s.",
    # Remaining UI / model strings (2026 pass)
    "Monthly salary": "الراتب الشهري",
    "Not set": "غير محدّد",
    "Sales last %(n)s day": "مبيعات آخر %(n)s يوم",
    "Payment to employee: ON": "دفع لدى موظف: مفعّل",
    "%(n)s item needs attention": "عنصر يحتاج متابعة",
    "Sale is not an employee payment sale.": "هذه ليست مبيعة دفع لدى موظف.",
    "Salary accrual row is missing salary month.": "صف استحقاق الراتب بلا شهر محدّد.",
    "Only salary accrual rows can create expenses.": "المصروفات تُنشأ من صفوف استحقاق الراتب فقط.",
    "First day of the month for salary accrual rows.": "أول يوم في الشهر لصفوف استحقاق الراتب.",
    "Positive credits the employee; negative debits them.": "موجب يُضاف للموظف؛ سالب يُخصم منه.",
    "Employee payment sales require an employee recipient.": "مبيعات الدفع لدى موظف تتطلب موظفاً مستلماً.",
    "A sale cannot be both on-account and paid via employee.": "لا يمكن أن تكون المبيعة آجل ودفع لدى موظف معاً.",
    "Choose either on-account or payment to employee, not both.": "اختر إما الآجل أو الدفع لدى موظف، وليس الاثنين.",
    "Positive: shop owes employee. Negative: employee owes shop.": "موجب: المحل مدين للموظف. سالب: الموظف مدين للمحل.",
    "Positive: the shop owes the employee (salary / credits). Negative: the employee holds cash on behalf of the shop.": (
        "موجب: المحل مدين للموظف (راتب/دائن). سالب: الموظف يحتفظ بمبلغ نيابة عن المحل."
    ),
    "Also runnable via: python manage.py accrue_employee_salaries": (
        "يمكن تشغيله أيضاً عبر: python manage.py accrue_employee_salaries"
    ),
    "Cash received by an employee on behalf of the shop; no payment method at entry.": (
        "نقد استلمه موظف نيابة عن المحل؛ بلا طريقة دفع عند الإدخال."
    ),
    "Customer not found. Check the name or ask management to add the customer.": (
        "الزبون غير موجود. تحقّق من الاسم أو اطلب من الإدارة إضافته."
    ),
    "Ledger": "كشف الحركات",
    "Settled.": "مساوٍ.",
    "No employees yet.": "لا يوجد موظفون بعد.",
    "No sales payments yet.": "لا توجد دفعات مبيعات بعد.",
    "No ledger entries.": "لا توجد حركات في الكشف.",
    "Username or name…": "اسم المستخدم أو الاسم…",
    "Invalid month.": "شهر غير صالح.",
    "User": "المستخدم",
    "Balance": "الرصيد",
    "Amount cannot be zero.": "المبلغ لا يمكن أن يكون صفراً.",
    "Mark as on account": "تسجيل آجل",
    "On account: ON": "آجل: مفعّل",
    "Where did you receive the money?": "أين استلمت المبلغ؟",
    "Payment method is required for this sale.": "طريقة الدفع مطلوبة لهذه المبيعة.",
    "Close": "إغلاق",
    "Adjust (+/-)": "تسوية (+/-)",
    "employee ledger entry": "حركة كشف موظف",
    "employee ledger entries": "حركات كشف الموظف",
    "expense": "مصروف",
    "Paid via employee": "دفع لدى موظف",
    "On account": "آجل",
    "Credit account": "حساب أجل",
    "Cash payer": "بدون أجل",
    "View all": "عرض الكل",
    "My entries": "إدخالاتي",
    "Edit entry": "تعديل الإدخال",
    "Delete": "حذف",
    "Delete this entry permanently? Supplier balance will be corrected. This cannot be undone.": (
        "حذف هذا الإدخال نهائياً؟ يُصحَّح رصيد المورّد. لا يمكن التراجع."
    ),
    "Entry was permanently removed.": "أُزيل الإدخال نهائياً.",
    "Sale updated.": "تم تحديث البيع.",
    "Company, product and eSIM flag can't be changed here. If those need fixing, delete this entry and create a new one.": (
        "لا يمكن تغيير الشركة أو المنتج أو خيار eSIM هنا. للتصحيح، احذف الإدخال وأنشئ واحداً جديداً."
    ),
    "Pick a payment method.": "اختر طريقة الدفع.",
    "eSIM: extra cost applied to this sale": "eSIM: تكلفة إضافية على هذه المبيعة",
    "reconcile provider": "مزوّد المطابقة",
    "Which supplier report matching applies to this company. Leave empty to match from the company name.": (
        "أي مطابقة لتقرير المورّد تنطبق على هذه الشركة. اتركه فارغاً للمطابقة حسب اسم الشركة."
    ),
    "When off, the payment-to-employee option is hidden on the employee sales screen.": (
        "عند الإيقاف، يُخفى خيار الدفع لدى موظف من شاشة مبيعات الموظف."
    ),
    # Payment method recipients + payment methods report
    "payment recipient": "مستلم الدفعة",
    "payment recipients": "مستلمو الدفعات",
    "Recipient": "المستلم",
    "Recipients": "المستلمون",
    "Add recipient": "إضافة مستلم",
    "Received by": "المستلم",
    "No recipient": "بدون مستلم",
    "By recipient": "حسب المستلم",
    "Sort order": "ترتيب العرض",
    "Pick who received the payment.": "اختر مستلم الدفعة.",
    "Selected recipient does not belong to this payment method.": "المستلم المختار لا يتبع طريقة الدفع هذه.",
    "People who receive money on this method. Sellers pick one when recording a payment.": (
        "الأشخاص الذين يستلمون المبالغ عبر هذه الطريقة. يختار البائع أحدهم عند تسجيل الدفعة."
    ),
    "Recipients already used by sales or payments cannot be deleted — untick Active to hide them instead.": (
        "لا يمكن حذف المستلمين المستخدَمين في مبيعات أو دفعات — ألغِ تحديد «نشط» لإخفائهم بدلاً من ذلك."
    ),
    "“%(name)s” is used by existing records and was not deleted. Deactivate it instead.": (
        "«%(name)s» مرتبط بسجلات موجودة ولم يُحذف. اجعله غير نشط بدلاً من ذلك."
    ),
    "Payment methods report": "تقارير طرق الدفع",
    "Money received per payment method and recipient, for statement matching.": (
        "المبالغ المستلمة حسب طريقة الدفع والمستلم، لمطابقة كشوف الحساب."
    ),
    "Choose a payment method to see the report.": "اختر طريقة دفع لعرض التقرير.",
    "Total received": "إجمالي المستلم",
    "Movements": "الحركات",
    "Sale": "بيع",
    "Settlement": "تسديد",
    "Pending confirmation": "قيد التأكيد",
    "Show settled sales": "عرض المبيعات المسدّدة",
    "Settled sales": "المبيعات المسدّدة",
    "Reference number": "الرقم المرجعي",
    "Company / product": "الشركة / المنتج",
    "Export Excel": "تصدير Excel",
}


def _strip_fuzzy_headers(head: str) -> str:
    head = re.sub(r"^#, fuzzy[^\n]*\n", "", head, flags=re.MULTILINE)
    head = re.sub(r"^#\| [^\n]*\n", "", head, flags=re.MULTILINE)
    return head


def _entry_has_translation(block: str) -> bool:
    for line in block.splitlines():
        if line.startswith("msgstr[") or line.startswith('msgstr "'):
            value = line.split(" ", 1)[1].strip().strip('"')
            if value:
                return True
    return False


def unfuzzy_translated_entries(text: str) -> tuple[str, int]:
    """Drop fuzzy flags on entries that already have Arabic msgstr."""
    unfuzzied = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal unfuzzied
        block = match.group(0)
        if "#, fuzzy" not in block or not _entry_has_translation(block):
            return block
        head = match.group("head")
        if "#, fuzzy" in head:
            unfuzzied += 1
            head = _strip_fuzzy_headers(head)
        return head + match.group("msgid") + match.group("msgstr") + "\n"

    text = _ENTRY_RE.sub(repl, text)
    return text, unfuzzied


def _po_unquote(block: str) -> str:
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', block)
    return "".join(p.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\") for p in parts)


def _po_quote_msgstr(text: str) -> str:
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    if len(text) <= 72 and "\n" not in text:
        return f'msgstr "{text}"'
    lines = [text[i : i + 72] for i in range(0, len(text), 72)] if "\n" not in text else text.split("\n")
    out = ['msgstr ""']
    for line in lines:
        out.append(f'"{po_escape(line)}"')
    return "\n".join(out)


_ENTRY_RE = re.compile(
    r"(?P<head>(?:^#.*\n)*)"
    r"(?P<msgid>msgid\s+(?:\"(?:[^\"\\]|\\.)*\"(?:\n\"(?:[^\"\\]|\\.)*\")*)\s*\n)"
    r'(?P<msgstr>msgstr\s+(?:"(?:[^"\\]|\\.)*"(?:\n"(?:[^"\\]|\\.)*")*)\s*)',
    re.MULTILINE,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    po_path = root / "locale" / "ar" / "LC_MESSAGES" / "django.po"
    text = po_path.read_text(encoding="utf-8")
    text = text.replace('"Language: \\n"', '"Language: ar\\n"', 1)

    updated = 0
    missing: list[str] = []

    def repl(match: re.Match[str]) -> str:
        nonlocal updated
        head = match.group("head")
        msgid_block = match.group("msgid")
        msgstr_block = match.group("msgstr")
        key = _po_unquote(msgid_block)
        if not key or key not in AR:
            return match.group(0)
        head = _strip_fuzzy_headers(head)
        new_msgstr = _po_quote_msgstr(AR[key])
        updated += 1
        return head + msgid_block + new_msgstr + "\n"

    text = _ENTRY_RE.sub(repl, text)

    text, unfuzzied = unfuzzy_translated_entries(text)

    for en in AR:
        if f'msgid "{po_escape(en)}"' not in text and f'msgid ""\n"{po_escape(en[:40])}' not in text:
            # multiline msgid check
            if en not in {_po_unquote(m.group("msgid")) for m in _ENTRY_RE.finditer(text)}:
                missing.append(en)

    po_path.write_text(text, encoding="utf-8")
    print(f"Updated {updated} entries in {po_path}")
    if unfuzzied:
        print(f"Unfuzzy: {unfuzzied} translated entries activated")
    if missing:
        print(f"Note: {len(missing)} AR keys not found in .po (run makemessages first):")
        for m in missing[:10]:
            print(f"  - {m[:70]}...")


if __name__ == "__main__":
    main()
